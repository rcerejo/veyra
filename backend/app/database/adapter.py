from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    data_type: str
    nullable: bool
    primary_key: bool
    primary_key_position: int = 0


@dataclass(frozen=True)
class ForeignKeyInfo:
    column: str
    target_table: str
    target_column: str | None
    constraint_id: int = 0
    sequence: int = 0


@dataclass(frozen=True)
class TableInfo:
    name: str
    columns: tuple[ColumnInfo, ...]
    foreign_keys: tuple[ForeignKeyInfo, ...] = field(default_factory=tuple)


class DatabaseAdapter(ABC):
    @abstractmethod
    def discover_schema(self) -> tuple[TableInfo, ...]: ...

    @abstractmethod
    def execute_readonly(self, sql: str, row_limit: int, timeout_seconds: float) -> tuple[list[str], list[dict[str, Any]], bool]: ...

    @property
    @abstractmethod
    def path(self) -> Path: ...

