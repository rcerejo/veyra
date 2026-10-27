from __future__ import annotations

import time
import sqlite3
import re
from datetime import datetime
from starlette.concurrency import run_in_threadpool

from app.ai.ollama import OllamaClient
from app.core.config import Settings
from app.database.schema import SchemaCatalog
from app.database.sqlite import SQLiteAdapter
from app.database.registry import DatabaseRegistry
from app.query_engine.planner import deterministic_sql, plan_question
from app.query_engine.semantic import _date_column
from app.query_engine.compositional import plan_compositional, validate_coverage, CoverageError
from app.query_engine.temporal import temporal_fields,validate_timestamp_column
from app.query_engine.validator import UnsafeQueryError, validate_sql
from app.schemas.query import ClarificationResponse, QueryMetadata, QueryRequest, QueryResponse


class QueryService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.adapter = SQLiteAdapter(DatabaseRegistry(settings.database_path).active_path())
        self.ollama = OllamaClient(settings.ollama_url, settings.ollama_model,settings.sql_examples_path)

    async def ask(self, request: QueryRequest) -> QueryResponse | ClarificationResponse:
        if re.match(r'^\s*(delete|drop|update|insert|alter|truncate)\b',request.question,re.IGNORECASE):
            return ClarificationResponse(question=request.question,message='VEYRA supports read-only analysis. Data modification requests cannot be executed.',suggestions=[])
        started = time.perf_counter()
        def discover_catalog():
            return SchemaCatalog(self.adapter.discover_schema(), self.adapter.profile_values())
        catalog = await run_in_threadpool(discover_catalog)
        sql = deterministic_sql(request.question)
        # Extra predicates must not be swallowed by a canonical count/lookup template.
        if re.search(r'\b(missing|null|nonmissing|at least|at most|greater than|less than|negative|whose)\b|[<>!=]',request.question,re.I) or (re.search(r'\bwhere\b',request.question,re.I) and 'all instances where' not in request.question.casefold()):
            sql=None
        if sql and re.search(r'\b(by|per|in each)\b',request.question,re.I) and 'GROUP BY' not in sql.upper():
            sql=None
        if sql and re.fullmatch(r'SELECT COUNT\(\*\) AS \w+ FROM \w+',sql,re.I) and not re.fullmatch(r'(?:how many|count)\s+\w+(?:\s+are there)?[?.! ]*',request.question,re.I):
            sql=None
        if sql is not None:
            try:
                validate_sql(sql,catalog)
            except UnsafeQueryError:
                # Demo-specific templates must not override an unfamiliar schema.
                sql=None
        if sql is not None:
            plan = plan_question(request.question)
            source = "deterministic"
        else:
            semantic = plan_compositional(request.question, catalog)
            plan = semantic.plan
            sql = semantic.sql
            source = "semantic"
            if sql is None and semantic.clarification:
                return ClarificationResponse(
                    question=request.question,
                    message=semantic.clarification,
                    suggestions=list(semantic.suggestions),
                )
            if sql is not None and plan.composition and temporal_fields(plan.composition):
                try:
                    for field in temporal_fields(plan.composition):
                        await run_in_threadpool(validate_timestamp_column,self.adapter,field)
                except CoverageError as exc:
                    return ClarificationResponse(question=request.question,message=str(exc),suggestions=[])
            elif sql is not None and plan.time_range and plan.relevant_tables:
                table=plan.relevant_tables[0]
                column=(plan.composition.dates[0].field.column if plan.composition and plan.composition.dates else _date_column(catalog,table))
                if column:
                    quoted_table=table.replace('"','""')
                    quoted_column=column.replace('"','""')
                    _,sample,_=await run_in_threadpool(self.adapter.execute_readonly,f'SELECT "{quoted_column}" AS value FROM "{quoted_table}" WHERE "{quoted_column}" IS NOT NULL LIMIT 1000',1000,2)
                    invalid=False
                    for row in sample:
                        try:
                            if not re.match(r'^\d{4}-\d{2}-\d{2}(?:$|[T ])',str(row['value'])):
                                raise ValueError('Non-lexically sortable date format')
                            datetime.fromisoformat(str(row['value']).replace('Z','+00:00'))
                        except ValueError:
                            invalid=True
                            break
                    if invalid:
                        return ClarificationResponse(question=request.question,message=f'{table}.{column} contains mixed or invalid date formats. Confirm the date interpretation or normalize the field before filtering by calendar dates.',suggestions=[])
        if (sql is None or self.settings.prefer_model_sql) and await self.ollama.available():
            source = "ollama"
            sql = await self.ollama.generate_sql(request.question, plan, catalog.prompt_context(plan.relevant_tables or None))
        if sql is None:
            return ClarificationResponse(
                question=request.question,
                message="I could not map that question to a safe deterministic query, and the local model is unavailable. Please make the metric and grouping explicit.",
                suggestions=["How many users are there?", "Show users by acquisition channel", "Show daily active users"],
            )
        correction_attempts = 0
        schema_context = catalog.prompt_context(plan.relevant_tables or None)
        while True:
            try:
                validated = validate_sql(sql, catalog)
                if plan.composition:
                    validate_coverage(plan.composition,validated)
                columns, rows, truncated = await run_in_threadpool(
                    self.adapter.execute_readonly, validated, self.settings.max_result_rows, self.settings.query_timeout_seconds
                )
                break
            except CoverageError as exc:
                return ClarificationResponse(question=request.question,
                    message=f'I withheld this query because an analytical operation was not preserved: {exc}',suggestions=[])
            except (UnsafeQueryError, sqlite3.Error) as exc:
                if source != "ollama" or correction_attempts >= 2:
                    raise
                correction_attempts += 1
                sql = await self.ollama.correct_sql(
                    request.question, plan, schema_context, sql, str(exc)
                )
        duration = (time.perf_counter() - started) * 1000
        explanation = f"Returned {len(rows)} row{'s' if len(rows) != 1 else ''} from a validated, read-only query."
        return QueryResponse(
            question=request.question, plan=plan, sql=validated, columns=columns, rows=rows,
            metadata=QueryMetadata(source=source, duration_ms=round(duration, 2), row_count=len(rows), truncated=truncated,
                                   model=self.settings.ollama_model if source == "ollama" else None,
                                   correction_attempts=correction_attempts),
            explanation=explanation,
        )

