from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class QueryPlan(BaseModel):
    intent: Literal["aggregation", "trend", "lookup", "schema", "unknown"]
    metric: str | None = None
    dimensions: list[str] = Field(default_factory=list)
    filters: dict[str, str | int | float | bool] = Field(default_factory=dict)
    time_range: str | None = None
    relevant_tables: list[str] = Field(default_factory=list)


class QueryMetadata(BaseModel):
    source: Literal["deterministic", "semantic", "ollama"]
    duration_ms: float
    row_count: int
    truncated: bool
    model: str | None = None
    correction_attempts: int = 0


class QueryResponse(BaseModel):
    question: str
    plan: QueryPlan
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    metadata: QueryMetadata
    explanation: str


class ClarificationResponse(BaseModel):
    status: Literal["clarification_required"] = "clarification_required"
    question: str
    message: str
    suggestions: list[str]

