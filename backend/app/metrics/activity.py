from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.database.sqlite import SQLiteAdapter
from app.schemas.metrics import ActivityMetrics, ActivityPoint, ActivitySummary, MetricDefinition


class MetricSchemaError(ValueError):
    pass


ACTIVITY_DEFINITIONS = (
    MetricDefinition(
        key="dau",
        name="Daily active users",
        description="Distinct users with at least one event in a UTC calendar day.",
        formula="COUNT(DISTINCT events.user_id) grouped by UTC date",
        required_fields=["events.user_id", "events.event_timestamp"],
    ),
    MetricDefinition(
        key="wau",
        name="Weekly active users",
        description="Distinct users with at least one event in a Monday-to-Sunday UTC calendar week.",
        formula="COUNT(DISTINCT events.user_id) grouped by UTC week starting Monday",
        required_fields=["events.user_id", "events.event_timestamp"],
    ),
    MetricDefinition(
        key="mau",
        name="Monthly active users",
        description="Distinct users with at least one event in a UTC calendar month.",
        formula="COUNT(DISTINCT events.user_id) grouped by UTC calendar month",
        required_fields=["events.user_id", "events.event_timestamp"],
    ),
    MetricDefinition(
        key="sessions_per_user",
        name="Sessions per active user",
        description="Sessions that start in the selected window divided by distinct session users.",
        formula="COUNT(sessions.session_id) / COUNT(DISTINCT sessions.user_id)",
        required_fields=["sessions.session_id", "sessions.user_id", "sessions.session_start"],
    ),
    MetricDefinition(
        key="average_session_duration",
        name="Average session duration",
        description="Average elapsed seconds for completed sessions that start in the selected window.",
        formula="AVG(session_end - session_start) in seconds, excluding incomplete and negative durations",
        required_fields=["sessions.session_start", "sessions.session_end"],
    ),
)


class ActivityMetricService:
    def __init__(self, adapter: SQLiteAdapter, timeout_seconds: float = 8.0) -> None:
        self.adapter = adapter
        self.timeout_seconds = timeout_seconds

    def calculate(self, start: date | None = None, end: date | None = None) -> ActivityMetrics:
        self._require_schema()
        data_start, data_through = self._data_range()
        resolved_end = end or data_through
        resolved_start = start or max(data_start, resolved_end - timedelta(days=29))
        if resolved_start > resolved_end:
            raise ValueError("start must be on or before end")

        start_iso, end_iso = resolved_start.isoformat(), resolved_end.isoformat()
        daily = self._points(self._activity_sql("day", start_iso, end_iso))
        week_start = resolved_start - timedelta(days=resolved_start.weekday())
        week_end = resolved_end + timedelta(days=6 - resolved_end.weekday())
        month_start = resolved_start.replace(day=1)
        next_month = (resolved_end.replace(day=28) + timedelta(days=4)).replace(day=1)
        month_end = next_month - timedelta(days=1)
        weekly = self._points(self._activity_sql("week", week_start.isoformat(), week_end.isoformat()))
        monthly = self._points(self._activity_sql("month", month_start.isoformat(), month_end.isoformat()))
        session_values = self._session_summary(start_iso, end_iso)

        latest_dau = daily[-1].active_users if daily else 0
        latest_month = daily[-1].period[:7] + "-01" if daily else resolved_end.strftime("%Y-%m-01")
        latest_mau = next((point.active_users for point in monthly if point.period == latest_month), 0)
        ratio = round(latest_dau / latest_mau, 4) if latest_mau else None
        return ActivityMetrics(
            start=resolved_start,
            end=resolved_end,
            data_start=data_start,
            data_through=data_through,
            timezone="UTC",
            daily=daily,
            weekly=weekly,
            monthly=monthly,
            summary=ActivitySummary(
                latest_dau=latest_dau,
                latest_wau=weekly[-1].active_users if weekly else 0,
                latest_mau=latest_mau,
                dau_mau_ratio=ratio,
                sessions_per_user=session_values["sessions_per_user"],
                average_session_duration_seconds=session_values["average_session_duration_seconds"],
            ),
        )

    def _require_schema(self) -> None:
        actual = {table.name: {column.name for column in table.columns} for table in self.adapter.discover_schema()}
        required = {
            "events": {"user_id", "event_timestamp"},
            "sessions": {"session_id", "user_id", "session_start", "session_end"},
        }
        missing = [
            f"{table}.{column}"
            for table, columns in required.items()
            for column in sorted(columns - actual.get(table, set()))
        ]
        if missing:
            raise MetricSchemaError(
                "Activity metrics need a compatible product schema. Missing: " + ", ".join(missing)
            )

    def _data_range(self) -> tuple[date, date]:
        rows = self._run("SELECT MIN(DATE(event_timestamp)) AS first_date, MAX(DATE(event_timestamp)) AS last_date FROM events")
        if not rows or not rows[0]["first_date"] or not rows[0]["last_date"]:
            raise MetricSchemaError("Activity metrics need at least one event with a valid timestamp")
        return date.fromisoformat(rows[0]["first_date"]), date.fromisoformat(rows[0]["last_date"])

    def _activity_sql(self, grain: str, start: str, end: str) -> str:
        period = {
            "day": "DATE(event_timestamp)",
            "week": "DATE(event_timestamp, '-' || ((CAST(strftime('%w', event_timestamp) AS INTEGER) + 6) % 7) || ' days')",
            "month": "strftime('%Y-%m-01', event_timestamp)",
        }[grain]
        return (
            f"SELECT {period} AS period, COUNT(DISTINCT user_id) AS active_users "
            f"FROM events WHERE DATE(event_timestamp) BETWEEN '{start}' AND '{end}' "
            "AND user_id IS NOT NULL GROUP BY period ORDER BY period"
        )

    def _session_summary(self, start: str, end: str) -> dict[str, float | None]:
        rows = self._run(
            "SELECT COUNT(session_id) AS session_count, COUNT(DISTINCT user_id) AS session_users, "
            "AVG(CASE WHEN session_end IS NOT NULL AND julianday(session_end) >= julianday(session_start) "
            "THEN (julianday(session_end) - julianday(session_start)) * 86400.0 END) AS avg_duration "
            f"FROM sessions WHERE DATE(session_start) BETWEEN '{start}' AND '{end}'"
        )
        row = rows[0]
        users = int(row["session_users"] or 0)
        return {
            "sessions_per_user": round(int(row["session_count"] or 0) / users, 2) if users else None,
            "average_session_duration_seconds": round(float(row["avg_duration"]), 1) if row["avg_duration"] is not None else None,
        }

    def _points(self, sql: str) -> list[ActivityPoint]:
        return [ActivityPoint(period=row["period"], active_users=row["active_users"]) for row in self._run(sql)]

    def _run(self, sql: str) -> list[dict[str, Any]]:
        return self.adapter.execute_readonly(sql, row_limit=5000, timeout_seconds=self.timeout_seconds)[1]

