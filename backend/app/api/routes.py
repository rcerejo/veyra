from __future__ import annotations

import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.config import Settings, get_settings
from app.database.schema import SchemaCatalog
from app.database.sqlite import QueryTimeoutError, SQLiteAdapter
from app.database.registry import DatabaseRegistry, DatabaseRegistryError, MAX_DATABASE_BYTES
from app.metrics.activity import ACTIVITY_DEFINITIONS, ActivityMetricService, MetricSchemaError
from app.query_engine.service import QueryService
from app.query_engine.validator import UnsafeQueryError
from app.schemas.query import ClarificationResponse, QueryRequest, QueryResponse
from app.schemas.database import DatabaseInfo, DatabaseList, DatabaseSelection
from app.schemas.metrics import ActivityMetrics, MetricDefinition
from app.metrics.retention import retention
from app.metrics.funnel import FunnelRequest, funnel
from app.metrics.experiments import experiments
from app.metrics.statistics import power_plan
from app.metrics.investigations import InvestigationRequest, investigate

router = APIRouter(prefix="/api")


@router.post('/investigations')
def investigation(request: InvestigationRequest, settings: Settings = Depends(get_settings)) -> dict:
    try:
        return investigate(_active_adapter(settings), request)
    except MetricSchemaError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get('/experiments/power')
def experiment_power(baseline: float = Query(gt=0, lt=1), effect: float = Query(gt=0, lt=1), per_arm: int = Query(ge=2), target: float = Query(default=.8, gt=.5, lt=1)) -> dict:
    try:
        return power_plan(baseline, effect, per_arm, target)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/experiments")
def experiment_analysis(expected_treatment_share: float | None = Query(default=None, gt=0, lt=1), conversion_event: str = Query(default='purchase', min_length=1, max_length=100), window_days: int = Query(default=7, ge=1, le=90), settings: Settings = Depends(get_settings)) -> list[dict]:
    try:
        return experiments(_active_adapter(settings), expected_treatment_share, conversion_event, window_days)
    except MetricSchemaError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/metrics/funnel")
def funnel_metrics(request: FunnelRequest, settings: Settings = Depends(get_settings)) -> dict:
    try:
        return funnel(_active_adapter(settings), request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/metrics/retention")
def retention_metrics(settings: Settings = Depends(get_settings)) -> dict:
    try:
        return retention(_active_adapter(settings))
    except MetricSchemaError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _active_adapter(settings: Settings) -> SQLiteAdapter:
    return SQLiteAdapter(DatabaseRegistry(settings.database_path).active_path())


@router.get("/health")
async def health(settings: Settings = Depends(get_settings)) -> dict:
    service = QueryService(settings)
    active_path = DatabaseRegistry(settings.database_path).active_path()
    database_ready = active_path.is_file()
    return {
        "status": "ok" if database_ready else "degraded",
        "database": {"connected": database_ready, "name": active_path.name},
        "ollama": {"available": await service.ollama.available(), "model": settings.ollama_model},
    }


@router.get("/schema")
def schema(settings: Settings = Depends(get_settings)) -> dict:
    try:
        adapter = _active_adapter(settings)
        return SchemaCatalog(adapter.discover_schema(), adapter.profile_values()).as_dict()
    except (FileNotFoundError, OSError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/query", response_model=QueryResponse | ClarificationResponse)
async def query(request: QueryRequest, settings: Settings = Depends(get_settings)) -> QueryResponse | ClarificationResponse:
    try:
        return await QueryService(settings).ask(request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except UnsafeQueryError as exc:
        raise HTTPException(status_code=422, detail=f"Generated query was rejected: {exc}") from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=422, detail=f"Query execution failed: {exc}") from exc
    except QueryTimeoutError as exc:
        raise HTTPException(status_code=408, detail=str(exc)) from exc


@router.get("/databases", response_model=DatabaseList)
def databases(settings: Settings = Depends(get_settings)) -> DatabaseList:
    registry = DatabaseRegistry(settings.database_path)
    return DatabaseList(databases=[DatabaseInfo(**item.__dict__) for item in registry.list()])


@router.post("/databases/activate", response_model=DatabaseInfo)
def activate_database(selection: DatabaseSelection, settings: Settings = Depends(get_settings)) -> DatabaseInfo:
    registry = DatabaseRegistry(settings.database_path)
    try:
        active = registry.activate(selection.name)
    except DatabaseRegistryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return DatabaseInfo(name=active.relative_to(registry.root).as_posix(), size_bytes=active.stat().st_size, active=True)


@router.get("/metrics/definitions", response_model=list[MetricDefinition])
def metric_definitions() -> tuple[MetricDefinition, ...]:
    return ACTIVITY_DEFINITIONS


@router.get("/metrics/activity", response_model=ActivityMetrics)
def activity_metrics(
    start: date | None = None,
    end: date | None = None,
    settings: Settings = Depends(get_settings),
) -> ActivityMetrics:
    try:
        return ActivityMetricService(_active_adapter(settings), settings.query_timeout_seconds).calculate(start, end)
    except (MetricSchemaError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/databases/upload", response_model=DatabaseInfo, status_code=201)
async def upload_database(
    request: Request,
    filename: str = Query(min_length=1, max_length=255),
    settings: Settings = Depends(get_settings),
) -> DatabaseInfo:
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_DATABASE_BYTES:
        raise HTTPException(status_code=413, detail="Database exceeds the 100 MB upload limit")
    content = await request.body()
    registry = DatabaseRegistry(settings.database_path)
    try:
        path = registry.upload(filename, content)
        active = registry.activate(path.relative_to(registry.root).as_posix())
    except DatabaseRegistryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return DatabaseInfo(name=active.relative_to(registry.root).as_posix(), size_bytes=active.stat().st_size, active=True)

