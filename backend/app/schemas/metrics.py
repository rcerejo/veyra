from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class MetricDefinition(BaseModel):
    key: str
    name: str
    description: str
    formula: str
    required_fields: list[str]


class ActivityPoint(BaseModel):
    period: str
    active_users: int


class ActivitySummary(BaseModel):
    latest_dau: int
    latest_wau: int
    latest_mau: int
    dau_mau_ratio: float | None
    sessions_per_user: float | None
    average_session_duration_seconds: float | None


class ActivityMetrics(BaseModel):
    start: date
    end: date
    data_start: date
    data_through: date
    timezone: str
    daily: list[ActivityPoint]
    weekly: list[ActivityPoint]
    monthly: list[ActivityPoint]
    summary: ActivitySummary

