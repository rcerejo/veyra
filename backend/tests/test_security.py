import asyncio

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.database.registry import DatabaseRegistry, DatabaseRegistryError, SQLITE_HEADER
from app.database.sqlite import SQLiteAdapter
from app.core.security import RequestBoundary


def test_production_requires_explicit_security_configuration():
    with pytest.raises(ValidationError):
        Settings(environment='production')
    settings=Settings(environment='production',gateway_api_key='x'*32,allowed_hosts=['veyra.example.com'],cors_origins=[])
    assert settings.environment=='production'
    assert settings.enable_admin_jobs is False
    assert 'xxxxxxxx' not in repr(settings)
    with pytest.raises(ValidationError):
        Settings(environment='production',gateway_api_key='REPLACE_WITH_A_RANDOM_SECRET_AT_LEAST_32_CHARACTERS',allowed_hosts=['example.com'],cors_origins=[])


def test_gateway_key_protects_every_workspace_endpoint(client,monkeypatch):
    monkeypatch.setenv('VEYRA_GATEWAY_API_KEY','x'*32)
    get_settings.cache_clear()
    assert client.get('/api/schema').status_code==401
    assert client.get('/api/health').status_code==401
    assert client.get('/api/schema',headers={'X-Veyra-Key':'wrong'}).status_code==401
    assert client.get('/api/schema',headers={'X-Veyra-Key':'x'*32}).status_code==200
    assert client.get('/livez').status_code==200


def test_untrusted_host_is_rejected(client):
    assert client.get('/api/schema',headers={'host':'attacker.example'}).status_code==400


def test_production_disables_admin_jobs_by_default(client,monkeypatch):
    monkeypatch.setenv('VEYRA_ENVIRONMENT','production')
    monkeypatch.setenv('VEYRA_GATEWAY_API_KEY','x'*32)
    monkeypatch.setenv('VEYRA_ALLOWED_HOSTS','["localhost"]')
    monkeypatch.setenv('VEYRA_CORS_ORIGINS','[]')
    get_settings.cache_clear()
    headers={'X-Veyra-Key':'x'*32,'host':'localhost'}
    assert client.post('/api/prediction',headers=headers).status_code==403
    assert client.post('/api/evaluation',headers=headers).status_code==403
    assert client.get('/api/schema',headers=headers).status_code==200


def test_request_ids_and_safe_headers(client):
    response=client.get('/api/schema')
    assert len(response.headers['x-request-id'])==32
    assert response.headers['x-content-type-options']=='nosniff'
    assert response.headers['cache-control']=='no-store'


def test_readiness_checks_database_not_just_process(client,database):
    assert client.get('/readyz').status_code==200
    database.rename(database.with_suffix('.offline'))
    assert client.get('/livez').status_code==200
    assert client.get('/readyz').status_code==503


def test_upload_rejects_header_only_file_and_cleans_partial_file(database):
    registry=DatabaseRegistry(database)
    with pytest.raises(DatabaseRegistryError):
        registry.upload('corrupt.db',SQLITE_HEADER+b'invalid'*100)
    assert not list(registry.uploads.glob('*.db'))


def test_streamed_upload_is_bounded_without_content_length(client,monkeypatch,database):
    monkeypatch.setattr('app.api.routes.MAX_DATABASE_BYTES',32)
    response=client.post('/api/databases/upload?filename=large.db',content=iter([b'a'*20,b'b'*20]))
    assert response.status_code==413
    assert not (database.parent/'uploads'/'large.db').exists()


def test_connections_close_and_uri_special_characters_work(database):
    special=database.with_name('database #1.db')
    special.write_bytes(database.read_bytes())
    adapter=SQLiteAdapter(special)
    adapter.discover_schema()
    adapter.profile_values()
    assert adapter.execute_readonly('SELECT COUNT(*) AS users FROM users',10,2)[1][0]['users']==2
    renamed=special.with_name('renamed.db')
    special.rename(renamed)
    assert renamed.exists()


def test_json_body_limit_is_enforced(client):
    response=client.post('/api/query',content=b' '* (1024*1024+1),headers={'content-type':'application/json'})
    assert response.status_code==413


def test_concurrency_limit_rejects_excess_work_and_recovers(monkeypatch):
    monkeypatch.setenv('VEYRA_MAX_CONCURRENT_REQUESTS','1')
    get_settings.cache_clear()
    async def scenario():
        entered=asyncio.Event()
        release=asyncio.Event()
        async def application(scope,receive,send):
            entered.set()
            await release.wait()
            await send({'type':'http.response.start','status':200,'headers':[]})
            await send({'type':'http.response.body','body':b'ok'})
        boundary=RequestBoundary(application)
        statuses=[]
        async def receive():
            return {'type':'http.request','body':b'','more_body':False}
        async def send(message):
            if message['type']=='http.response.start':
                statuses.append(message['status'])
        def scope():
            return {'type':'http','path':'/api/schema','headers':[],'method':'GET'}
        first=asyncio.create_task(boundary(scope(),receive,send))
        await entered.wait()
        await boundary(scope(),receive,send)
        assert statuses==[503]
        release.set()
        await first
        await boundary(scope(),receive,send)
        assert statuses==[503,200,200]
    try:
        asyncio.run(scenario())
    finally:
        get_settings.cache_clear()
