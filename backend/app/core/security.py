"""A gateway credential protects a single private workspace, not individual users."""
import asyncio
import hmac
import logging
import time
import uuid

from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.core.config import get_settings

logger=logging.getLogger('veyra.requests')


class RequestBoundary:
    def __init__(self,app):
        self.app=app
        self.limit=None

    async def __call__(self,scope,receive,send):
        if scope['type']!='http':
            return await self.app(scope,receive,send)
        settings=get_settings()
        request_id=uuid.uuid4().hex
        scope.setdefault('state',{})['request_id']=request_id
        started=time.monotonic()
        headers=dict(scope['headers'])
        path=scope.get('path','')
        is_api=path.startswith('/api/')
        async def reject(status,detail,retry=False):
            logger.info('request_id=%s method=%s status=%d duration_ms=%.2f',request_id,scope.get('method'),status,(time.monotonic()-started)*1000)
            response_headers={'X-Request-ID':request_id,'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}
            if retry:
                response_headers['Retry-After']='2'
            return await JSONResponse({'detail':detail},status_code=status,headers=response_headers)(scope,receive,send)
        if is_api and (settings.environment=='production' or settings.gateway_api_key):
            supplied=headers.get(b'x-veyra-key',b'')
            expected=settings.gateway_api_key.get_secret_value().encode() if settings.gateway_api_key else b''
            if not expected or not hmac.compare_digest(supplied,expected):
                return await reject(401,'Authentication required')
        if settings.environment=='production' and not settings.enable_admin_jobs and path in ('/api/evaluation','/api/prediction'):
            return await reject(403,'Administrative analysis jobs are disabled')
        if self.limit is None:
            self.limit=asyncio.Semaphore(settings.max_concurrent_requests)
        acquired=False
        if is_api:
            try:
                await asyncio.wait_for(self.limit.acquire(),timeout=.01)
                acquired=True
            except TimeoutError:
                return await reject(503,'Server is busy; retry later',retry=True)
        status=500
        consumed=0
        body_limit=100*1024*1024 if path=='/api/databases/upload' else 1024*1024
        async def bounded_receive():
            nonlocal consumed
            message=await receive()
            if message['type']=='http.request':
                consumed+=len(message.get('body',b''))
                if consumed>body_limit:
                    raise HTTPException(status_code=413,detail='Request body exceeds the limit')
            return message
        async def secured_send(message):
            nonlocal status
            if message['type']=='http.response.start':
                status=message['status']
                message['headers'] = list(message.get('headers',[]))+[(b'x-request-id',request_id.encode()),(b'x-content-type-options',b'nosniff'),(b'cache-control',b'no-store')]
            await send(message)
        try:
            await self.app(scope,bounded_receive,secured_send)
        finally:
            if acquired:
                self.limit.release()
            logger.info('request_id=%s method=%s status=%d duration_ms=%.2f',request_id,scope.get('method'),status,(time.monotonic()-started)*1000)
