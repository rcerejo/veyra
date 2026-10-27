"""In-app multi-source snapshots: correctness, provenance and unchanged query boundaries."""
import asyncio
from contextlib import closing
import copy
import sqlite3

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.database.combine import DatabaseCombiner, digest
from app.database.registry import DatabaseRegistry, DatabaseRegistryError
from app.database.schema import SchemaCatalog
from app.database.sqlite import SQLiteAdapter
from app.query_engine.service import QueryService
from app.query_engine.validator import UnsafeQueryError, validate_sql
from app.schemas.database import CombineDatabases
from app.schemas.query import QueryRequest, QueryResponse


def create(path,sql):
    with closing(sqlite3.connect(path)) as db:
        db.executescript(sql)
        db.commit()


@pytest.fixture
def sources(tmp_path):
    crm=tmp_path/'crm.db'
    product=tmp_path/'product.db'
    create(crm,'''CREATE TABLE organizations(org_id INTEGER PRIMARY KEY,plan TEXT);
        CREATE TABLE people(person_id INTEGER PRIMARY KEY);
        CREATE TABLE memberships(person_id INTEGER REFERENCES people,org_id INTEGER REFERENCES organizations,
          PRIMARY KEY(person_id,org_id));
        INSERT INTO organizations VALUES(1,'free'),(2,'pro'),(3,'unused');
        INSERT INTO people VALUES(1),(2),(3);
        INSERT INTO memberships VALUES(1,1),(1,2),(2,2);''')
    create(product,'''CREATE TABLE actions(action_id INTEGER PRIMARY KEY,category TEXT);
        CREATE TABLE activity(event_id INTEGER PRIMARY KEY,workspace_id INTEGER,actor_id INTEGER,
          action_id INTEGER REFERENCES actions,value REAL);
        INSERT INTO actions VALUES(1,'app_open');
        INSERT INTO activity VALUES(1,1,1,1,0),(2,1,1,1,2.5),(3,2,2,1,-1),(4,NULL,NULL,1,NULL);''')
    request=dict(name='demo',sources=[dict(name='crm.db',alias='crm'),dict(name='product.db',alias='product')],
        relationships=[dict(child_source='product',child_table='activity',child_columns=['workspace_id'],
                            parent_source='crm',parent_table='organizations',parent_columns=['org_id']),
                       dict(child_source='product',child_table='activity',child_columns=['actor_id'],
                            parent_source='crm',parent_table='people',parent_columns=['person_id'])])
    return tmp_path,DatabaseRegistry(crm),request


def build(sources,request=None):
    _,registry,configuration=sources
    return DatabaseCombiner(registry).create(CombineDatabases(**(request or configuration)))


def test_snapshot_preserves_rows_keys_provenance_and_active_selection(sources):
    root,registry,_=sources
    before={p.name:digest(p) for p in (root/'crm.db',root/'product.db')}
    previous=registry.active_path()
    result=build(sources)
    path=registry.resolve_source(result['database']['name'])
    assert not result['database']['active']
    assert registry.active_path()==previous
    assert before=={p.name:digest(p) for p in (root/'crm.db',root/'product.db')}
    adapter=SQLiteAdapter(path)
    schema=SchemaCatalog(adapter.discover_schema())
    assert set(schema.tables)=={'crm__organizations','crm__people','crm__memberships','product__actions','product__activity'}
    assert len(schema.tables['product__activity'].foreign_keys)==3
    _,rows,_=adapter.execute_readonly('SELECT o.plan,COUNT(*) AS n FROM product__activity a JOIN crm__organizations o ON o.org_id=a.workspace_id GROUP BY o.plan',20,2)
    assert sorted([list(r.values()) for r in rows])==[['free',2],['pro',1]]
    assert result['provenance']['row_counts']['product__activity']==4
    assert result['provenance']['dataset_sha256']==digest(path)
    assert DatabaseCombiner(registry).provenance(result['database']['name'])['provenance']==result['provenance']
    registry.activate(result['database']['name'])
    assert registry.active_path()==path
    assert not list(root.glob('.veyra-combine-*'))


def test_query_service_uses_new_declared_cross_source_join(sources):
    _,registry,_=sources
    result=build(sources)
    path=registry.resolve_source(result['database']['name'])
    service=QueryService(Settings(_env_file=None,database_path=path,prefer_model_sql=False,sql_examples_path=None))
    service.adapter=SQLiteAdapter(path)
    async def offline():
        return False
    service.ollama.available=offline
    answer=asyncio.run(service.ask(QueryRequest(question='Count activity by organization plan')))
    assert isinstance(answer,QueryResponse),answer
    assert sorted([list(r.values()) for r in answer.rows])==[['free',2],['pro',1]]
    assert answer.plan.composition.joins


def test_same_table_names_and_repeat_builds_do_not_overwrite(sources):
    root,registry,configuration=sources
    with closing(sqlite3.connect(root/'product.db')) as db:
        db.execute('CREATE TABLE people(person_id INTEGER PRIMARY KEY)')
        db.execute('INSERT INTO people VALUES(42)')
        db.commit()
    a=build(sources)
    b=build(sources)
    assert a['database']['name']!=b['database']['name']
    assert a['provenance']['dataset_sha256']==b['provenance']['dataset_sha256']
    assert 'product__people' in a['provenance']['row_counts']
    assert 'crm__people' in a['provenance']['row_counts']
    assert len(registry.list())==4
    assert configuration['sources'][0]['alias']=='crm'


@pytest.mark.parametrize('change,reason',[
    (lambda r:r['sources'][1].update(name='../escape.db'),'escapes'),
    (lambda r:r['relationships'][0].update(parent_table='missing'),'unknown'),
    (lambda r:r['relationships'][0].update(child_columns=['missing']),'missing'),
    (lambda r:r['relationships'][0].update(parent_columns=['plan']),'unique'),
    (lambda r:r['relationships'][0].update(parent_source='product',parent_table='actions'),'different'),
    (lambda r:r['relationships'].append(copy.deepcopy(r['relationships'][0])),'Duplicate'),
])
def test_invalid_mappings_fail_without_publishing_or_switching(sources,change,reason):
    root,registry,request=sources
    configuration=copy.deepcopy(request)
    change(configuration)
    previous=registry.active_path()
    with pytest.raises(DatabaseRegistryError,match=reason):
        build(sources,configuration)
    assert registry.active_path()==previous
    assert len(registry.list())==2
    assert not list(root.glob('.veyra-combine-*'))


def test_orphans_are_rejected_without_dropping_rows(sources):
    root,registry,_=sources
    with closing(sqlite3.connect(root/'product.db')) as db:
        db.execute('UPDATE activity SET workspace_id=999 WHERE event_id=1')
        db.commit()
    before=digest(root/'product.db')
    with pytest.raises(DatabaseRegistryError,match='no matching parent'):
        build(sources)
    assert before==digest(root/'product.db')
    assert len(registry.list())==2


def test_incompatible_key_types_are_rejected(sources):
    root,registry,request=sources
    create(root/'strings.db',"CREATE TABLE events(event_id INTEGER PRIMARY KEY,workspace_id TEXT); INSERT INTO events VALUES(1,'1');")
    configuration=copy.deepcopy(request)
    configuration['sources'][1]['name']='strings.db'
    configuration['relationships']=configuration['relationships'][:1]
    configuration['relationships'][0]['child_table']='events'
    with pytest.raises(DatabaseRegistryError,match='affinities'):
        build(sources,configuration)
    assert registry.active_path()==root/'crm.db'


def test_disconnected_sources_are_rejected(sources):
    root,_,request=sources
    create(root/'third.db','CREATE TABLE unused(id INTEGER PRIMARY KEY);')
    configuration=copy.deepcopy(request)
    configuration['sources'].append(dict(name='third.db',alias='third'))
    with pytest.raises(DatabaseRegistryError,match='Every selected source'):
        build(sources,configuration)


def test_composite_parent_key_and_duplicate_codes(tmp_path):
    create(tmp_path/'parent.db',"CREATE TABLE catalog(namespace TEXT,code TEXT,label TEXT,PRIMARY KEY(namespace,code)); INSERT INTO catalog VALUES('a','x','first'),('b','x','second');")
    create(tmp_path/'child.db',"CREATE TABLE records(id INTEGER PRIMARY KEY,namespace TEXT,code TEXT); INSERT INTO records VALUES(1,'a','x'),(2,'b','x'),(3,NULL,'x');")
    registry=DatabaseRegistry(tmp_path/'parent.db')
    request=CombineDatabases(name='composite',sources=[dict(name='parent.db',alias='parent'),dict(name='child.db',alias='child')],relationships=[dict(child_source='child',child_table='records',child_columns=['namespace','code'],parent_source='parent',parent_table='catalog',parent_columns=['namespace','code'])])
    result=DatabaseCombiner(registry).create(request)
    adapter=SQLiteAdapter(registry.resolve_source(result['database']['name']))
    _,rows,_=adapter.execute_readonly('SELECT p.label,COUNT(*) AS n FROM child__records c JOIN parent__catalog p ON p.namespace=c.namespace AND p.code=c.code GROUP BY p.label',10,2)
    assert sorted([list(r.values()) for r in rows])==[['first',1],['second',1]]
    request.relationships[0].child_columns=['code']
    request.relationships[0].parent_columns=['code']
    with pytest.raises(DatabaseRegistryError,match='unique'):
        DatabaseCombiner(registry).create(request)


def test_explicit_unique_non_primary_key_is_preserved(sources):
    root,registry,request=sources
    create(root/'unique.db',"CREATE TABLE targets(id INTEGER PRIMARY KEY,external_id INTEGER UNIQUE); INSERT INTO targets VALUES(10,1),(20,2);")
    configuration=copy.deepcopy(request)
    configuration['sources'][0]['name']='unique.db'
    configuration['relationships']=configuration['relationships'][:1]
    configuration['relationships'][0].update(parent_table='targets',parent_columns=['external_id'])
    result=build(sources,configuration)
    assert result['provenance']['row_counts']['crm__targets']==2
    assert registry.active_path()==root/'crm.db'


def test_views_triggers_are_disclosed_and_never_executed(sources):
    root,_,_=sources
    with closing(sqlite3.connect(root/'product.db')) as db:
        db.executescript('CREATE TABLE effects(id INTEGER); CREATE VIEW danger_view AS SELECT * FROM activity; CREATE TRIGGER danger_trigger AFTER INSERT ON activity BEGIN INSERT INTO effects VALUES(1); END;')
        db.commit()
    result=build(sources)
    assert result['provenance']['row_counts']['product__effects']==0
    assert set(result['provenance']['sources'][1]['ignored_objects'])=={'danger_trigger','danger_view'}


@pytest.mark.parametrize('ddl',[
    'CREATE TABLE bad(id INTEGER PRIMARY KEY,code TEXT COLLATE NOCASE)',
    'CREATE TABLE bad(id INTEGER PRIMARY KEY,derived INTEGER GENERATED ALWAYS AS (id+1))',
    'CREATE TABLE bad(id INTEGER PRIMARY KEY,v TEXT); CREATE UNIQUE INDEX special ON bad(v) WHERE v IS NOT NULL',
    'CREATE TABLE bad(id INTEGER PRIMARY KEY,v ANY) STRICT',
])
def test_unsupported_schema_semantics_fail_closed(sources,ddl):
    root,_,_=sources
    with closing(sqlite3.connect(root/'product.db')) as db:
        db.executescript(ddl)
    with pytest.raises(DatabaseRegistryError):
        build(sources)


def test_row_budget_cleanup(sources,monkeypatch):
    root,registry,_=sources
    monkeypatch.setattr('app.database.combine.MAX_ROWS',1)
    with pytest.raises(DatabaseRegistryError,match='row limit'):
        build(sources)
    assert len(registry.list())==2
    assert not list(root.glob('.veyra-combine-*'))


def test_time_budget_fails_without_publishing(sources,monkeypatch):
    root,registry,_=sources
    monkeypatch.setattr('app.database.combine.MAX_SECONDS',-1)
    with pytest.raises(DatabaseRegistryError,match='budget'):
        build(sources)
    assert len(registry.list())==2
    assert not list(root.glob('.veyra-combine-*'))


def test_identifier_quotes_remain_data_not_sql(sources):
    root,registry,_=sources
    create(root/'product.db','CREATE TABLE "odd""table; DROP TABLE people;--"("id" INTEGER PRIMARY KEY);')
    result=build(sources)
    catalog=SchemaCatalog(SQLiteAdapter(registry.resolve_source(result['database']['name'])).discover_schema())
    assert 'product__odd"table; DROP TABLE people;--' in catalog.tables
    assert 'crm__people' in catalog.tables


def test_wal_committed_rows_are_captured(sources):
    root,_,_=sources
    with closing(sqlite3.connect(root/'product.db')) as writer:
        writer.execute('PRAGMA journal_mode=WAL')
        writer.execute("INSERT INTO activity VALUES(5,2,3,1,7)")
        writer.commit()
        result=build(sources)
    assert result['provenance']['row_counts']['product__activity']==5


def test_inspection_and_provenance_do_not_change_selection(sources):
    root,registry,_=sources
    description=DatabaseCombiner(registry).schema('product.db')
    assert 'unique_keys' in description['tables'][0]
    assert registry.active_path()==root/'crm.db'
    with pytest.raises(DatabaseRegistryError,match='not a generated'):
        DatabaseCombiner(registry).provenance('product.db')
    result=build(sources)
    path=registry.resolve_source(result['database']['name'])
    with closing(sqlite3.connect(path)) as db:
        db.execute('INSERT INTO crm__people VALUES(77)')
        db.commit()
    with pytest.raises(DatabaseRegistryError,match='fingerprint'):
        DatabaseCombiner(registry).provenance(result['database']['name'])


def test_build_files_are_not_visible_or_selectable(sources):
    root,registry,_=sources
    hidden=root/'.veyra-combine-example'
    hidden.mkdir()
    create(hidden/'partial.db','CREATE TABLE partial(id INTEGER);')
    assert len(registry.list())==2
    with pytest.raises(DatabaseRegistryError,match='In-progress'):
        registry.activate('.veyra-combine-example/partial.db')


@pytest.mark.parametrize('change',[
    lambda r:r.update(name='../escape'),
    lambda r:r['sources'][0].update(alias='crm;DROP TABLE x'),
    lambda r:r['sources'][1].update(alias='crm'),
    lambda r:r['sources'][1].update(name='crm.db'),
    lambda r:r['relationships'][0].update(parent_columns=[]),
    lambda r:r['relationships'][0].update(child_columns=['workspace_id','workspace_id'],parent_columns=['org_id','org_id']),
])
def test_typed_request_rejects_invalid_configuration(sources,change):
    _,_,request=sources
    configuration=copy.deepcopy(request)
    change(configuration)
    with pytest.raises(ValidationError):
        CombineDatabases(**configuration)


def test_query_boundary_still_blocks_attach_and_writes(sources):
    _,registry,_=sources
    result=build(sources)
    adapter=SQLiteAdapter(registry.resolve_source(result['database']['name']))
    catalog=SchemaCatalog(adapter.discover_schema())
    with pytest.raises(UnsafeQueryError):
        validate_sql("ATTACH DATABASE 'elsewhere.db' AS other",catalog)
    with pytest.raises(sqlite3.DatabaseError):
        adapter.execute_readonly("ATTACH DATABASE ':memory:' AS other",10,2)
    with pytest.raises(sqlite3.DatabaseError):
        adapter.execute_readonly('DELETE FROM crm__people',10,2)


@pytest.mark.parametrize('winerror',[5,32,33])
def test_transient_windows_publication_lock_recovers(sources,monkeypatch,winerror):
    import app.database.combine as module
    original=module.os.rename
    attempts=[]
    def transient(left,right):
        attempts.append((left,right))
        if len(attempts)<=2:
            error=PermissionError(13,'Synthetic Windows sharing error')
            error.winerror=winerror
            raise error
        return original(left,right)
    monkeypatch.setattr(module.os,'rename',transient)
    monkeypatch.setattr(module.time,'sleep',lambda _:None)
    result=build(sources)
    assert 3<=len(attempts)<=10
    assert len(set(attempts))==1
    assert not result['database']['active']


def test_permanent_windows_publication_lock_fails_closed(sources,monkeypatch):
    import app.database.combine as module
    _,registry,_=sources
    attempts=[]
    def locked(*_):
        attempts.append(1)
        error=PermissionError(13,'Synthetic persistent lock')
        error.winerror=5
        raise error
    monkeypatch.setattr(module.os,'rename',locked)
    monkeypatch.setattr(module.time,'sleep',lambda _:None)
    with pytest.raises(DatabaseRegistryError,match='locked'):
        build(sources)
    assert len(attempts)==10
    assert len(registry.list())==2


def test_publication_never_overwrites_a_destination(tmp_path):
    import time
    from app.database.combine import publish_snapshot
    stage=tmp_path/'stage'
    destination=tmp_path/'existing'
    stage.mkdir(); destination.mkdir()
    with pytest.raises(DatabaseRegistryError,match='already exists'):
        publish_snapshot(stage,destination,time.monotonic()+5)
    assert stage.is_dir() and destination.is_dir()


def test_publication_does_not_retry_unknown_permission_errors(tmp_path,monkeypatch):
    import time
    import app.database.combine as module
    stage=tmp_path/'stage'
    stage.mkdir()
    attempts=[]
    def denied(*_):
        attempts.append(1)
        raise PermissionError(13,'Non-sharing permission failure')
    monkeypatch.setattr(module.os,'rename',denied)
    with pytest.raises(PermissionError):
        module.publish_snapshot(stage,tmp_path/'destination',time.monotonic()+5)
    assert len(attempts)==1


def test_api_create_review_activate_and_query(client,database):
    create(database.parent/'purchases.db','CREATE TABLE purchases(purchase_id INTEGER PRIMARY KEY,buyer_id INTEGER); INSERT INTO purchases VALUES(1,1),(2,1),(3,2);')
    original=client.get('/api/health').json()['database']['name']
    schema=client.get('/api/databases/schema',params={'name':'purchases.db'})
    assert schema.status_code==200
    payload=dict(name='api-demo',sources=[dict(name=database.name,alias='core'),dict(name='purchases.db',alias='shop')],relationships=[dict(child_source='shop',child_table='purchases',child_columns=['buyer_id'],parent_source='core',parent_table='users',parent_columns=['user_id'])])
    response=client.post('/api/databases/combine',json=payload)
    assert response.status_code==201,response.text
    result=response.json()
    assert not result['database']['active']
    assert client.get('/api/health').json()['database']['name']==original
    assert client.get('/api/databases/provenance',params={'name':result['database']['name']}).status_code==200
    assert client.post('/api/databases/activate',json={'name':result['database']['name']}).status_code==200
    answer=client.post('/api/query',json={'question':'Count purchases by user country'})
    assert answer.status_code==200,answer.text
    assert sorted([list(r.values()) for r in answer.json()['rows']])==[['CA',1],['US',2]]
    assert client.get('/api/databases/schema',params={'name':'../escape.db'}).status_code==422
    payload['relationships'][0]['parent_columns']=['country']
    assert client.post('/api/databases/combine',json=payload).status_code==422


def test_new_endpoints_inherit_gateway_auth(client,monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setenv('VEYRA_GATEWAY_API_KEY','x'*32)
    get_settings.cache_clear()
    assert client.get('/api/databases/schema',params={'name':'test.db'}).status_code==401
    assert client.post('/api/databases/combine',json={}).status_code==401
    assert client.get('/api/databases/provenance',params={'name':'test.db'}).status_code==401
