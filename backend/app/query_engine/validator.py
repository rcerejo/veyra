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
    return statement.sql(dialect="sqlite")

