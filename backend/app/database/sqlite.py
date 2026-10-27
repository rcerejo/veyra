from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any
from contextlib import closing

from app.database.adapter import ColumnInfo, DatabaseAdapter, ForeignKeyInfo, TableInfo


class QueryTimeoutError(RuntimeError):
    pass


class SQLiteAdapter(DatabaseAdapter):
    def __init__(self, path: Path) -> None:
        self._path = path.resolve()

    @property
    def path(self) -> Path:
        return self._path

    def _connect(self) -> sqlite3.Connection:
        if not self._path.is_file():
            raise FileNotFoundError(f"Database not found: {self._path}")
        connection = sqlite3.connect(f"{self._path.as_uri()}?mode=ro", uri=True,timeout=2)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        connection.execute('PRAGMA trusted_schema = OFF')
        connection.enable_load_extension(False)
        connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH,2*1024*1024)
        connection.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH,1024*1024)
        deadline=time.monotonic()+8
        connection.set_progress_handler(lambda: int(time.monotonic()>deadline),1000)
        return connection

    def discover_schema(self) -> tuple[TableInfo, ...]:
        with closing(self._connect()) as connection:
            names = [row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )]
            tables: list[TableInfo] = []
            infos = {name: list(connection.execute('PRAGMA table_info("' + name.replace('"', '""') + '")')) for name in names}
            for name in names:
                quoted = name.replace('"', '""')
                columns = tuple(
                    ColumnInfo(row[1], row[2] or "UNKNOWN", not bool(row[3]), bool(row[5]), int(row[5]))
                    for row in infos[name]
                )
                raw_keys = list(connection.execute(f'PRAGMA foreign_key_list("{quoted}")'))
                keys = []
                for row in raw_keys:
                    target = row[4]
                    if target is None:
                        primary = sorted((c for c in infos.get(row[2], []) if c[5]), key=lambda c: c[5])
                        width = sum(k[0] == row[0] for k in raw_keys)
                        if len(primary) == width and row[1] < len(primary):
                            target = primary[row[1]][1]
                    keys.append(ForeignKeyInfo(row[3], row[2], target, int(row[0]), int(row[1])))
                foreign_keys = tuple(keys)
                tables.append(TableInfo(name, columns, foreign_keys))
            return tuple(tables)

    def profile_values(self, sample_limit: int = 5, max_columns: int = 60) -> dict[str, dict[str, list[Any]]]:
        """Return bounded, non-sensitive examples for likely categorical columns."""
        profiles: dict[str, dict[str, list[Any]]] = {}
        inspected = 0
        sensitive_terms = ("email", "name", "address", "phone", "token", "password", "secret", "key")
        categorical_terms = ("type", "status", "category", "channel", "country", "device", "variant", "plan", "tier", "action", "state", "stage", "role")
        with closing(self._connect()) as connection:
            for table in self.discover_schema():
                table_profile: dict[str, list[Any]] = {}
                for column in table.columns:
                    if inspected >= max_columns:
                        break
                    lowered = column.name.casefold()
                    data_type = column.data_type.casefold()
                    is_text = any(token in data_type for token in ("char", "text", "clob"))
                    category_name=lowered in {'action_name','event_name','status_name','category_name','plan_name'}
                    if not is_text or any(term in lowered for term in sensitive_terms if term!='name') or ('name' in lowered and not category_name):
                        continue
                    if not any(term in lowered for term in categorical_terms):
                        continue
                    inspected += 1
                    quoted_table = table.name.replace('"', '""')
                    quoted_column = column.name.replace('"', '""')
                    sql = (
                        f'SELECT "{quoted_column}", COUNT(*) AS frequency FROM "{quoted_table}" '
                        f'WHERE "{quoted_column}" IS NOT NULL GROUP BY "{quoted_column}" '
                        f'ORDER BY frequency DESC, "{quoted_column}" LIMIT ?'
                    )
                    values = [
                        row[0][:80] if isinstance(row[0], str) else row[0]
                        for row in connection.execute(sql, (sample_limit,))
                    ]
                    if values:
                        table_profile[column.name] = values
                if table_profile:
                    profiles[table.name] = table_profile
        return profiles

    def execute_readonly(self, sql: str, row_limit: int, timeout_seconds: float) -> tuple[list[str], list[dict[str, Any]], bool]:
        started = time.monotonic()
        denied = {
            sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE,
            sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_DROP_TABLE, sqlite3.SQLITE_DROP_INDEX,
            sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH, sqlite3.SQLITE_PRAGMA,
            sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_CREATE_INDEX,
        }
        with closing(self._connect()) as connection:
            connection.set_authorizer(lambda action, *_: sqlite3.SQLITE_DENY if action in denied else sqlite3.SQLITE_OK)

            def progress() -> int:
                return 1 if time.monotonic() - started > timeout_seconds else 0

            connection.set_progress_handler(progress, 1000)
            try:
                cursor = connection.execute(sql)
                columns = [description[0] for description in cursor.description or []]
                rows=[]
                output_bytes=0
                truncated=False
                try:
                    for row in cursor:
                        size=sum(len(value) if isinstance(value,bytes) else len(str(value).encode('utf-8')) for value in row)
                        if len(rows)>=row_limit or output_bytes+size>16*1024*1024:
                            truncated=True
                            break
                        output_bytes+=size
                        rows.append(dict(row))
                finally:
                    cursor.close()
            except sqlite3.OperationalError as exc:
                if "interrupted" in str(exc).lower():
                    raise QueryTimeoutError("Query exceeded the execution time limit") from exc
                raise
            return columns, rows, truncated

