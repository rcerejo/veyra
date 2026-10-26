from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import logging
import sqlite3

from app.api.routes import router
from app.core.config import get_settings
from app.core.security import RequestBoundary
from app.database.registry import DatabaseRegistry
from app.database.sqlite import SQLiteAdapter, QueryTimeoutError

settings=get_settings()
application_logger=logging.getLogger('veyra')
if not application_logger.handlers:
    handler=logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s level=%(levelname)s logger=%(name)s %(message)s'))
    application_logger.addHandler(handler)
application_logger.setLevel(logging.INFO)
application_logger.propagate=False
app = FastAPI(title="VEYRA API", version="0.1.0", description="Local-first product intelligence",docs_url=None if settings.environment=='production' else '/docs',redoc_url=None if settings.environment=='production' else '/redoc',openapi_url=None if settings.environment=='production' else '/openapi.json')
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type","X-Veyra-Key"],
)
app.add_middleware(RequestBoundary)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=settings.allowed_hosts)
app.include_router(router)


@app.get('/livez')
def livez():
    return {'status':'ok'}


@app.get('/readyz')
def readyz():
    try:
        path=DatabaseRegistry(get_settings().database_path).active_path()
        SQLiteAdapter(path).execute_readonly('SELECT 1 FROM sqlite_master LIMIT 1',1,1)
        return {'status':'ready'}
    except (OSError,sqlite3.Error,QueryTimeoutError):
        return JSONResponse({'status':'not_ready'},status_code=503)


@app.exception_handler(Exception)
async def unexpected_error(request,exc):
    request_id=getattr(request.state,'request_id','unavailable')
    logging.getLogger('veyra.errors').error('request_id=%s unhandled_error_type=%s',request_id,type(exc).__name__)
    return JSONResponse({'detail':'An unexpected server error occurred'},status_code=500,headers={'X-Request-ID':request_id,'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

