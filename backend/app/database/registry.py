from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from contextlib import closing
import os
import sqlite3
import tempfile
import time


SQLITE_HEADER = b"SQLite format 3\x00"
ALLOWED_SUFFIXES = {".db", ".sqlite", ".sqlite3"}
MAX_DATABASE_BYTES = 100 * 1024 * 1024


class DatabaseRegistryError(ValueError):
    pass


@dataclass(frozen=True)
class RegisteredDatabase:
    name: str
    size_bytes: int
    active: bool


class DatabaseRegistry:
    def __init__(self, default_path: Path) -> None:
        self.root = default_path.resolve().parent
        self.default_name = default_path.name
        self.uploads = self.root / "uploads"
        self.marker = self.root / ".active_database"

    def active_path(self) -> Path:
        name = self.default_name
        if self.marker.is_file():
            candidate = self.marker.read_text(encoding="utf-8").strip()
            if candidate:
                name = candidate
        try:
            return self._resolve(name, require_exists=True)
        except DatabaseRegistryError:
            return self._resolve(self.default_name, require_exists=False)

    def list(self) -> list[RegisteredDatabase]:
        active = self.active_path()
        if not self.root.exists():
            return []
        results: list[RegisteredDatabase] = []
        for path in sorted(self.root.rglob("*")):
            if not path.is_file() or path.suffix.casefold() not in ALLOWED_SUFFIXES:
                continue
            resolved = path.resolve()
            if not resolved.is_relative_to(self.root):
                continue
            results.append(RegisteredDatabase(
                name=resolved.relative_to(self.root).as_posix(),
                size_bytes=resolved.stat().st_size,
                active=resolved == active,
            ))
        return results

    def activate(self, name: str) -> Path:
        path = self._resolve(name, require_exists=True)
        self._validate_file(path)
        self.root.mkdir(parents=True, exist_ok=True)
        fd,temporary=tempfile.mkstemp(prefix='.active-',dir=self.root)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as handle:
                handle.write(path.relative_to(self.root).as_posix())
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary,self.marker)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return path

    def upload(self, filename: str, content: bytes) -> Path:
        if len(content) > MAX_DATABASE_BYTES:
            raise DatabaseRegistryError("Database exceeds the 100 MB upload limit")
        if not content.startswith(SQLITE_HEADER):
            raise DatabaseRegistryError("The uploaded file is not a valid SQLite database")
        original = Path(filename)
        suffix = original.suffix.casefold()
        if suffix not in ALLOWED_SUFFIXES:
            raise DatabaseRegistryError("Use a .db, .sqlite, or .sqlite3 file")
        stem = re.sub(r"[^a-zA-Z0-9_-]+", "-", original.stem).strip("-") or "database"
        self.uploads.mkdir(parents=True, exist_ok=True)
        target = self.uploads / f"{stem}{suffix}"
        counter = 2
        while True:
            try:
                with target.open('xb') as handle:
                    handle.write(content)
                break
            except FileExistsError:
                target=self.uploads/f'{stem}-{counter}{suffix}'
                counter+=1
        try:
            self._validate_file(target)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return target

    def _resolve(self, name: str, require_exists: bool) -> Path:
        if not name or Path(name).is_absolute():
            raise DatabaseRegistryError("Database name must be relative to the datasets directory")
        path = (self.root / Path(name)).resolve()
        if not path.is_relative_to(self.root):
            raise DatabaseRegistryError("Database path escapes the datasets directory")
        if path.suffix.casefold() not in ALLOWED_SUFFIXES:
            raise DatabaseRegistryError("Unsupported database file extension")
        if require_exists and not path.is_file():
            raise DatabaseRegistryError("Database does not exist")
        return path

    @staticmethod
    def _validate_file(path: Path) -> None:
        try:
            with path.open("rb") as handle:
                header = handle.read(len(SQLITE_HEADER))
        except OSError as exc:
            raise DatabaseRegistryError(f"Unable to read database: {exc}") from exc
        if header != SQLITE_HEADER:
            raise DatabaseRegistryError("The selected file is not a valid SQLite database")
        try:
            with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=2)) as connection:
                connection.execute('PRAGMA trusted_schema=OFF')
                deadline=time.monotonic()+3
                connection.set_progress_handler(lambda:int(time.monotonic()>deadline),1000)
                checked=connection.execute('PRAGMA quick_check(1)').fetchone()
                if not checked or checked[0]!='ok':
                    raise DatabaseRegistryError('SQLite integrity validation failed')
        except sqlite3.Error as exc:
            raise DatabaseRegistryError('The database is corrupt, unsupported, or could not be validated in time') from exc

