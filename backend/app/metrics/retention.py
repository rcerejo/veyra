from datetime import date, timedelta

from app.database.sqlite import SQLiteAdapter
from app.metrics.activity import MetricSchemaError


def retention(adapter: SQLiteAdapter) -> dict:
    schema = {t.name: {c.name for c in t.columns} for t in adapter.discover_schema()}
    for table, fields in {"users": {"user_id", "signup_date"}, "events": {"user_id", "event_timestamp"}}.items():
        missing = fields - schema.get(table, set())
        if missing:
            raise MetricSchemaError(f"Retention requires {table}: {', '.join(sorted(missing))}")

    def run(sql):
        _, rows, truncated = adapter.execute_readonly(sql, 100000, 8)
        if truncated:
            raise MetricSchemaError("Retention input exceeds the current 100,000-row analysis limit")
        return rows

    through = run("SELECT MAX(DATE(event_timestamp)) AS day FROM events")[0]["day"]
    if not through:
        raise MetricSchemaError("Retention requires timestamped events")
    cutoff = date.fromisoformat(through)
    rows = run("SELECT DATE(signup_date) AS cohort, COUNT(DISTINCT user_id) AS users FROM users WHERE DATE(signup_date) IS NOT NULL GROUP BY cohort ORDER BY cohort")
    counts = run("SELECT DATE(u.signup_date) AS cohort, CAST(julianday(DATE(e.event_timestamp)) - julianday(DATE(u.signup_date)) AS INTEGER) AS offset, COUNT(DISTINCT u.user_id) AS retained FROM users u JOIN events e ON e.user_id = u.user_id WHERE DATE(u.signup_date) IS NOT NULL GROUP BY cohort, offset")
    lookup = {(r['cohort'], r['offset']): r['retained'] for r in counts}
    cohorts = []
    for row in rows:
        cells = []
        for day in (1, 7, 30):
            mature = date.fromisoformat(row['cohort']) + timedelta(days=day) <= cutoff
            retained = lookup.get((row['cohort'], day), 0) if mature else None
            cells.append({"day": day, "eligible_users": row['users'] if mature else 0, "retained_users": retained, "rate": retained / row['users'] if mature else None})
        cohorts.append({"cohort": row['cohort'], "users": row['users'], "cells": cells})
    return {"data_through": through, "timezone": "UTC", "definition": "Exact-day retention: users with any event on UTC day N after signup divided by signup cohort users. Immature cohorts are excluded. Observation completeness is inferred from the latest event date.", "cohorts": cohorts}
