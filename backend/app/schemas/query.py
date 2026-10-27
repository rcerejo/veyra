from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class ColumnRef(BaseModel):
    table: str
    column: str


class QueryMeasure(BaseModel):
    function: Literal['count', 'sum', 'average']
    field: ColumnRef | None = None
    distinct: bool = False


class QueryFilter(BaseModel):
    field: ColumnRef
    operator: Literal['eq', 'ne', 'gt', 'gte', 'lt', 'lte', 'is_null', 'not_null']
    value: str | int | float | None = None


class QueryGrouping(BaseModel):
    field: ColumnRef
    grain: Literal['day', 'week'] | None = None


class QueryActivity(BaseModel):
    source: str
    identity: ColumnRef
    entity_table: str
    definition: Literal['distinct non-null entity IDs observed in selected fact rows'] = 'distinct non-null entity IDs observed in selected fact rows'
    timezone: Literal['UTC'] = 'UTC'


class QueryDateConstraint(BaseModel):
    field: ColumnRef
    start: str | None = None
    end: str | None = None  # exclusive
    start_inclusive: bool = True
    end_inclusive: bool = False
    normalized: bool = False
    resolution: str | None = None


class QueryTimestampComparison(BaseModel):
    left: ColumnRef
    operator: Literal['gt', 'gte', 'lt', 'lte', 'eq']
    right: ColumnRef
    null_policy: Literal['exclude_missing_anchors'] = 'exclude_missing_anchors'


class QueryJoin(BaseModel):
    left_table: str
    right_table: str
    equalities: list[tuple[ColumnRef, ColumnRef]]
    constraint_id: int


class QueryRanking(BaseModel):
    field: ColumnRef | None = None  # None means the aggregate output
    descending: bool = True


class QueryExistence(BaseModel):
    entity: str
    correlations: list[tuple[ColumnRef, ColumnRef]] = Field(min_length=1)
    joins: list[QueryJoin] = Field(default_factory=list)
    filters: list[QueryFilter] = Field(default_factory=list)
    negated: bool = False
    dates: list[QueryDateConstraint] = Field(default_factory=list)
    timestamps: list[QueryTimestampComparison] = Field(default_factory=list)


class CompositionalQuery(BaseModel):
    version: Literal[1] = 1
    entity: str
    measure: QueryMeasure | None = None
    filters: list[QueryFilter] = Field(default_factory=list)
    groupings: list[QueryGrouping] = Field(default_factory=list)
    dates: list[QueryDateConstraint] = Field(default_factory=list)
    joins: list[QueryJoin] = Field(default_factory=list)
    existence: list[QueryExistence] = Field(default_factory=list)
    activity: QueryActivity | None = None
    distinct: bool = False
    ranking: list[QueryRanking] = Field(default_factory=list)
    limit: int = Field(default=5000, ge=1, le=5000)
    requested_operations: list[str] = Field(default_factory=list)
    unresolved_operations: list[str] = Field(default_factory=list)


class QueryPlan(BaseModel):
    intent: Literal["aggregation", "trend", "lookup", "schema", "unknown"]
    metric: str | None = None
    dimensions: list[str] = Field(default_factory=list)
    filters: dict[str, str | int | float | bool] = Field(default_factory=dict)
    time_range: str | None = None
    relevant_tables: list[str] = Field(default_factory=list)
    composition: CompositionalQuery | None = None


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

