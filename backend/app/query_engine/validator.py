from __future__ import annotations

from sqlglot import exp, parse
from sqlglot.errors import ParseError

from app.database.schema import SchemaCatalog


class UnsafeQueryError(ValueError):
    pass


def validate_sql(sql: str, catalog: SchemaCatalog) -> str:
    try:
        statements = parse(sql, read="sqlite")
    except ParseError as exc:
        raise UnsafeQueryError(f"Invalid SQL: {exc}") from exc
    if len(statements) != 1:
        raise UnsafeQueryError("Exactly one SQL statement is required")
    statement = statements[0]
    if not isinstance(statement, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise UnsafeQueryError("Only read-only SELECT queries are allowed")
    forbidden = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter, exp.Command, exp.Create, exp.Transaction)
    if any(statement.find(kind) for kind in forbidden):
        raise UnsafeQueryError("The query contains a forbidden operation")
    cte_names = {cte.alias_or_name for cte in statement.find_all(exp.CTE)}
    referenced_tables = {table.name for table in statement.find_all(exp.Table) if table.name not in cte_names}
    unknown = sorted(referenced_tables - set(catalog.tables))
    if unknown:
        raise UnsafeQueryError(f"Unknown table(s): {', '.join(unknown)}")

    aliases = {table.alias_or_name: table.name for table in statement.find_all(exp.Table)}
    known_columns = {
        table_name: {column.name for column in catalog.tables[table_name].columns}
        for table_name in referenced_tables
    }
    all_columns = set().union(*known_columns.values()) if known_columns else set()
    select_aliases = {alias.alias for alias in statement.find_all(exp.Alias) if alias.alias}
    for column in statement.find_all(exp.Column):
        if column.is_star:
            continue
        if column.table:
            table_name = aliases.get(column.table, column.table)
            if table_name in known_columns and column.name not in known_columns[table_name]:
                raise UnsafeQueryError(f"Unknown column: {table_name}.{column.name}")
        elif column.name not in all_columns and column.name not in select_aliases:
            # Derived CTE columns are validated by SQLite's read-only execution boundary.
            if not cte_names:
                raise UnsafeQueryError(f"Unknown column: {column.name}")
    return statement.sql(dialect="sqlite")

