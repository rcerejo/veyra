from __future__ import annotations

import sqlite3


def test_activity_metrics_are_deterministic(client):
    response = client.get("/api/metrics/activity?start=2026-01-03&end=2026-01-04")
    assert response.status_code == 200
    body = response.json()
    assert body["timezone"] == "UTC"
    assert body["daily"] == [
        {"period": "2026-01-03", "active_users": 2},
        {"period": "2026-01-04", "active_users": 1},
    ]
    assert body["summary"]["latest_dau"] == 1
    assert body["summary"]["latest_mau"] == 2
    assert body["summary"]["dau_mau_ratio"] == 0.5
    assert body["summary"]["sessions_per_user"] == 1.5
    assert body["summary"]["average_session_duration_seconds"] == 1200.0


def test_activity_metrics_default_to_available_data(client):
    response = client.get("/api/metrics/activity")
    assert response.status_code == 200
    body = response.json()
    assert body["start"] == "2026-01-03"
    assert body["end"] == "2026-01-04"
    assert body["data_through"] == "2026-01-04"


def test_metric_definitions_document_formulas(client):
    response = client.get("/api/metrics/definitions")
    assert response.status_code == 200
    keys = {definition["key"] for definition in response.json()}
    assert keys == {"dau", "wau", "mau", "sessions_per_user", "average_session_duration"}


def test_activity_metrics_report_incompatible_schema(client, database):
    with sqlite3.connect(database) as connection:
        connection.execute("DROP TABLE sessions")
    response = client.get("/api/metrics/activity")
    assert response.status_code == 422
    assert "sessions.session_id" in response.json()["detail"]


def test_activity_metrics_reject_reversed_range(client):
    response = client.get("/api/metrics/activity?start=2026-01-05&end=2026-01-01")
    assert response.status_code == 422
    assert response.json()["detail"] == "start must be on or before end"
