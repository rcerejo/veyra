from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import Settings, get_settings
from app.database.schema import SchemaCatalog
from app.database.sqlite import SQLiteAdapter
from app.query_engine.service import QueryService
from app.query_engine.validator import UnsafeQueryError
from app.schemas.query import ClarificationResponse, QueryRequest, QueryResponse

router = APIRouter(prefix="/api")


@router.get("/health")
async def health(settings: Settings = Depends(get_settings)) -> dict:
    service = QueryService(settings)
    database_ready = settings.database_path.is_file()
    return {
        "status": "ok" if database_ready else "degraded",
        "database": {"connected": database_ready, "name": settings.database_path.name},
        "ollama": {"available": await service.ollama.available(), "model": settings.ollama_model},
    }


@router.get("/schema")
def schema(settings: Settings = Depends(get_settings)) -> dict:
    try:
        return SchemaCatalog(SQLiteAdapter(settings.database_path).discover_schema()).as_dict()
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

