from __future__ import annotations

import time

from app.ai.ollama import OllamaClient
from app.core.config import Settings
from app.database.schema import SchemaCatalog
from app.database.sqlite import SQLiteAdapter
from app.database.registry import DatabaseRegistry
from app.query_engine.planner import deterministic_sql, plan_question
from app.query_engine.validator import validate_sql
from app.schemas.query import ClarificationResponse, QueryMetadata, QueryRequest, QueryResponse


class QueryService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.adapter = SQLiteAdapter(DatabaseRegistry(settings.database_path).active_path())
        self.ollama = OllamaClient(settings.ollama_url, settings.ollama_model)

    async def ask(self, request: QueryRequest) -> QueryResponse | ClarificationResponse:
        started = time.perf_counter()
        catalog = SchemaCatalog(self.adapter.discover_schema(), self.adapter.profile_values())
        plan = plan_question(request.question)
        sql = deterministic_sql(request.question)
        source = "deterministic"
        if sql is None and await self.ollama.available():
            source = "ollama"
            sql = await self.ollama.generate_sql(request.question, plan, catalog.prompt_context(plan.relevant_tables or None))
        if sql is None:
            return ClarificationResponse(
                question=request.question,
                message="I could not map that question to a safe deterministic query, and the local model is unavailable. Please make the metric and grouping explicit.",
                suggestions=["How many users are there?", "Show users by acquisition channel", "Show daily active users"],
            )
        validated = validate_sql(sql, catalog)
        columns, rows, truncated = self.adapter.execute_readonly(
            validated, self.settings.max_result_rows, self.settings.query_timeout_seconds
        )
        duration = (time.perf_counter() - started) * 1000
        explanation = f"Returned {len(rows)} row{'s' if len(rows) != 1 else ''} from a validated, read-only query."
        return QueryResponse(
            question=request.question, plan=plan, sql=validated, columns=columns, rows=rows,
            metadata=QueryMetadata(source=source, duration_ms=round(duration, 2), row_count=len(rows), truncated=truncated,
                                   model=self.settings.ollama_model if source == "ollama" else None),
            explanation=explanation,
        )

