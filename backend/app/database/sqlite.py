from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

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
        connection = sqlite3.connect(f"file:{self._path.as_posix()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        return connection

    def discover_schema(self) -> tuple[TableInfo, ...]:
        with self._connect() as connection:
            names = [row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )]
            tables: list[TableInfo] = []
            for name in names:
                quoted = name.replace('"', '""')
                columns = tuple(
                    ColumnInfo(row[1], row[2] or "UNKNOWN", not bool(row[3]), bool(row[5]))
                    for row in connection.execute(f'PRAGMA table_info("{quoted}")')
                )
                foreign_keys = tuple(
                    ForeignKeyInfo(row[3], row[2], row[4])
                    for row in connection.execute(f'PRAGMA foreign_key_list("{quoted}")')
                )
                tables.append(TableInfo(name, columns, foreign_keys))
            return tuple(tables)

    def execute_readonly(self, sql: str, row_limit: int, timeout_seconds: float) -> tuple[list[str], list[dict[str, Any]], bool]:
        started = time.monotonic()
        denied = {
            sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE,
            sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_DROP_TABLE, sqlite3.SQLITE_DROP_INDEX,
            sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH, sqlite3.SQLITE_PRAGMA,
            sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_CREATE_INDEX,
        }
        with self._connect() as connection:
            connection.set_authorizer(lambda action, *_: sqlite3.SQLITE_DENY if action in denied else sqlite3.SQLITE_OK)

            def progress() -> int:
                return 1 if time.monotonic() - started > timeout_seconds else 0

            connection.set_progress_handler(progress, 1000)
            try:
                cursor = connection.execute(sql)
                raw_rows = cursor.fetchmany(row_limit + 1)
            except sqlite3.OperationalError as exc:
                if "interrupted" in str(exc).lower():
                    raise QueryTimeoutError("Query exceeded the execution time limit") from exc
                raise
            columns = [description[0] for description in cursor.description or []]
            truncated = len(raw_rows) > row_limit
            rows = [dict(row) for row in raw_rows[:row_limit]]
            return columns, rows, truncated

