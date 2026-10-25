from __future__ import annotations

import sqlite3
from datetime import date

from app.database.adapter import ColumnInfo, TableInfo
from app.database.schema import SchemaCatalog
from app.database.sqlite import SQLiteAdapter
from app.query_engine.semantic import _time_window, plan_semantic_query
from app.query_engine.validator import validate_sql


def analytics_catalog(tmp_path):
    path = tmp_path / "unfamiliar.sqlite"
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE customers (
              customer_id INTEGER PRIMARY KEY,
              created_at TEXT NOT NULL,
              segment TEXT NOT NULL
            );
            CREATE TABLE payments (
              payment_id INTEGER PRIMARY KEY,
              customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
              status TEXT NOT NULL,
              amount REAL NOT NULL,
              paid_at TEXT NOT NULL
            );
            INSERT INTO customers VALUES
              (1, '2026-01-10', 'enterprise'),
              (2, '2026-02-10', 'consumer');
            INSERT INTO payments VALUES
              (1, 1, 'failed', 100.0, '2026-03-05T10:00:00'),
              (2, 1, 'completed', 150.0, '2026-03-06T10:00:00'),
              (3, 2, 'completed', 20.0, '2026-04-01T10:00:00');
        """)
    adapter = SQLiteAdapter(path)
    return adapter, SchemaCatalog(adapter.discover_schema(), adapter.profile_values())


def execute(adapter, catalog, question):
    result = plan_semantic_query(question, catalog)
    assert result.sql is not None, result.clarification
    sql = validate_sql(result.sql, catalog)
    return result, adapter.execute_readonly(sql, 5000, 2)[1]


def test_counts_entity_in_unfamiliar_schema(tmp_path):
    adapter, catalog = analytics_catalog(tmp_path)
    result, rows = execute(adapter, catalog, "How many customers are there?")
    assert result.plan.relevant_tables == ["customers"]
    assert rows == [{"record_count": 2}]


def test_matches_sampled_value_and_month(tmp_path):
    adapter, catalog = analytics_catalog(tmp_path)
    result, rows = execute(adapter, catalog, "Show failed payments in March 2026")
    assert result.plan.filters == {"payments.status": "failed"}
    assert result.plan.time_range == "march_2026"
    assert [row["payment_id"] for row in rows] == [1]


def test_compiles_explicit_foreign_key_join(tmp_path):
    adapter, catalog = analytics_catalog(tmp_path)
    result, rows = execute(adapter, catalog, "Break down payments by customer segment")
    assert result.plan.relevant_tables == ["payments", "customers"]
    assert rows == [
        {"dimension": "enterprise", "record_count": 2},
        {"dimension": "consumer", "record_count": 1},
    ]


def test_resolves_relative_calendar_window():
    assert _time_window("customers from last month", date(2026, 10, 24)) == (
        "2026-09-01", "2026-10-01", "last_month"
    )


def test_requests_clarification_for_equal_table_matches():
    columns = (ColumnInfo("customer_id", "INTEGER", False, True),)
    catalog = SchemaCatalog((TableInfo("customer_accounts", columns), TableInfo("customer_profiles", columns)))
    result = plan_semantic_query("Show customer records", catalog)
    assert result.sql is None
    assert "multiple equally likely tables" in (result.clarification or "")
    assert all("Show customer records using" in suggestion for suggestion in result.suggestions)

