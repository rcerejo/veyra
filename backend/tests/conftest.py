from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


@pytest.fixture
def database(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE users (user_id INTEGER PRIMARY KEY, signup_date TEXT NOT NULL, acquisition_channel TEXT, country TEXT, device_type TEXT);
            CREATE TABLE events (event_id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(user_id), event_type TEXT, event_timestamp TEXT, session_id INTEGER);
            INSERT INTO users VALUES (1, '2026-01-01', 'organic', 'US', 'mobile'), (2, '2026-01-02', 'paid', 'CA', 'desktop');
            INSERT INTO events VALUES (1, 1, 'app_open', '2026-01-03T10:00:00', 1), (2, 2, 'app_open', '2026-01-03T11:00:00', 2);
        """)
    return path


@pytest.fixture
def client(database: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("VEYRA_DATABASE_PATH", str(database))
    get_settings.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()

