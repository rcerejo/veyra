"""Development-only existence fixtures, including counterexamples to accidental passes."""
import asyncio
from contextlib import closing
import sqlite3

import pytest

from app.core.config import Settings
from app.database.sqlite import SQLiteAdapter
from app.database.schema import SchemaCatalog
from app.query_engine.compositional import CoverageError,compile_query,plan_compositional,validate_coverage
from app.query_engine.service import QueryService
from app.query_engine.validator import validate_sql
from app.schemas.query import ClarificationResponse,ColumnRef,CompositionalQuery,QueryExistence,QueryMeasure


@pytest.fixture
def fixture(tmp_path):
    path=tmp_path/'relations.db'
    with closing(sqlite3.connect(path)) as db:
        db.executescript('''
        CREATE TABLE learners(learner_id INTEGER PRIMARY KEY);
        CREATE TABLE courses(course_id INTEGER PRIMARY KEY);
        CREATE TABLE enrollments(enrollment_id INTEGER PRIMARY KEY,learner_id INTEGER REFERENCES learners,course_id INTEGER REFERENCES courses);
        CREATE TABLE completions(completion_id INTEGER PRIMARY KEY,enrollment_id INTEGER REFERENCES enrollments);
        INSERT INTO learners VALUES(1),(2),(3),(4);
        INSERT INTO courses VALUES(1),(2),(3);
        INSERT INTO enrollments VALUES(1,1,1),(2,1,1),(3,2,2),(4,NULL,2),(5,999,2);
        INSERT INTO completions VALUES(1,1),(2,1),(3,2);
        CREATE TABLE people(person_id INTEGER PRIMARY KEY);
        CREATE TABLE organizations(org_id INTEGER PRIMARY KEY);
        CREATE TABLE memberships(person_id INTEGER REFERENCES people,org_id INTEGER REFERENCES organizations,PRIMARY KEY(person_id,org_id));
        CREATE TABLE audit_log(log_id INTEGER PRIMARY KEY,person_id INTEGER REFERENCES people,org_id INTEGER REFERENCES organizations);
        CREATE TABLE invoices(invoice_id INTEGER PRIMARY KEY,org_id INTEGER REFERENCES organizations,state TEXT);
        INSERT INTO people VALUES(1),(2),(3);
        INSERT INTO organizations VALUES(1),(2),(3),(4);
        INSERT INTO memberships VALUES(1,1),(1,2),(2,1);
        INSERT INTO audit_log VALUES(1,3,3);
        INSERT INTO invoices VALUES(1,1,'paid'),(2,1,'paid'),(3,2,'void'),(4,NULL,'paid');
        CREATE TABLE depots(depot_id INTEGER PRIMARY KEY);
        CREATE TABLE parcels(parcel_id INTEGER PRIMARY KEY,origin_depot INTEGER REFERENCES depots,destination_depot INTEGER REFERENCES depots);
        CREATE TABLE checkpoints(checkpoint_id INTEGER PRIMARY KEY,parcel_id INTEGER REFERENCES parcels,stage TEXT);
        INSERT INTO depots VALUES(1),(2);
        INSERT INTO parcels VALUES(1,1,2),(2,1,NULL),(3,2,1),(4,2,1);
        INSERT INTO checkpoints VALUES(1,1,'delivered'),(2,1,'delivered'),(3,2,'accepted'),(4,NULL,'delivered');
        CREATE TABLE compound_parent(a INTEGER,b INTEGER,PRIMARY KEY(a,b));
        CREATE TABLE compound_child(x INTEGER,y INTEGER,FOREIGN KEY(x,y) REFERENCES compound_parent);
        INSERT INTO compound_parent VALUES(1,1),(1,2),(2,1);
        INSERT INTO compound_child VALUES(1,1),(1,1),(2,1),(NULL,2);
        ''')
        db.commit()
    adapter=SQLiteAdapter(path)
    return adapter,SchemaCatalog(adapter.discover_schema(),adapter.profile_values())


@pytest.mark.parametrize('question,expected',[
    ('List learners without an enrollment',[[3],[4]]),
    ('Count learners without enrollments',[[2]]),
    ('How many different learners have enrolled?',[[2]]),
    ('List learners with enrollments',[[1],[2]]),
    ('List courses without completions',[[2],[3]]),
    ('Count courses with completions',[[1]]),
    ('How many distinct people belong to an organization?',[[2]]),
    ('List people with no memberships',[[3]]),
    ('List organizations with no paid invoices',[[2],[3],[4]]),
    ('List organizations without invoices',[[3],[4]]),
    ('Count organizations with paid invoices',[[1]]),
    ('How many distinct parcels have checkpoints?',[[2]]),
    ('List parcels without a delivered checkpoint',[[2,1,None],[3,2,1],[4,2,1]]),
    ('List compound_parent without compound_child',[[1,2]]),
    ('Count compound_parent with compound_child',[[2]]),
    ('List parcels without a destination depot',[[2,1,None]]),
])
def test_exists_preserves_grain_nulls_and_predicates(fixture,question,expected):
    adapter,catalog=fixture
    result=plan_compositional(question,catalog)
    assert result.sql is not None,result.clarification
    assert result.plan.composition.existence
    sql=validate_sql(result.sql,catalog)
    validate_coverage(result.plan.composition,sql)
    _,rows,truncated=adapter.execute_readonly(sql,5000,2)
    assert not truncated
    assert sorted([list(r.values()) for r in rows],key=str)==sorted(expected,key=str)


@pytest.mark.parametrize('question',[
    'List parcels without depots',  # origin versus destination
    'Count people with organizations',  # membership versus activity path
    'List learners without urgent enrollments',
    'List people without memberships after March 1, 2026',
    'Count parcels with checkpoints by stage',
    'List parcels without delivered or accepted checkpoints',
    'Count parcels that have both delivered checkpoints and depots',
    'List learners with at least two enrollments',
    'List learners with enrollments then completions',
    'List inactive learners without enrollments',
    'Count unique compound_parent with compound_child',
    'List organizations with no overdue invoices',
    'List 1 people without memberships',  # do not silently discard an outer limit
    'List learners with enrollments or completions',
])
def test_ambiguous_or_unrepresented_conditions_stay_withheld(fixture,question):
    _,catalog=fixture
    answer=plan_compositional(question,catalog)
    assert answer.sql is None
    assert answer.clarification


@pytest.mark.parametrize('mutation',[
    lambda s:s.replace('NOT EXISTS','EXISTS'),
    lambda s:s.replace('EXISTS','NOT EXISTS'),
    lambda s:s.replace('"invoices"."org_id" = "organizations"."org_id"','1 = 1'),
    lambda s:s.replace(" AND \"invoices\".\"state\" = 'paid'",''),
    lambda s:s.replace("'paid'","'void'"),
    lambda s:s.replace('"invoices"."org_id" = "organizations"."org_id"','"invoices"."org_id" = "invoices"."org_id"'),
])
def test_existence_coverage_rejects_removed_correlations_negation_or_filters(fixture,mutation):
    _,catalog=fixture
    answer=plan_compositional('List organizations with no paid invoices',catalog)
    sql=answer.sql
    assert sql
    changed=mutation(sql)
    assert changed!=sql
    with pytest.raises(CoverageError):
        validate_coverage(answer.plan.composition,changed)


def test_multi_hop_join_predicate_cannot_be_removed(fixture):
    _,catalog=fixture
    answer=plan_compositional('List courses without completions',catalog)
    sql=answer.sql
    assert sql and 'JOIN' in sql
    import re
    changed=re.sub(r'ON .*? WHERE','ON 1 = 1 WHERE',sql)
    assert changed!=sql
    with pytest.raises(CoverageError):
        validate_coverage(answer.plan.composition,changed)


def test_composite_correlation_cannot_lose_one_key_component(fixture):
    _,catalog=fixture
    answer=plan_compositional('List compound_parent without compound_child',catalog)
    sql=answer.sql
    changed=sql.replace(' AND "compound_child"."y" = "compound_parent"."b"','')
    assert changed!=sql
    with pytest.raises(CoverageError):
        validate_coverage(answer.plan.composition,changed)


def test_model_cannot_uncorrelate_an_existence_request(fixture,monkeypatch):
    adapter,_=fixture
    service=QueryService(Settings(database_path=adapter.path,prefer_model_sql=True))
    service.adapter=adapter
    async def available():
        return True
    async def incorrect(*_):
        return 'SELECT organizations.* FROM organizations WHERE NOT EXISTS (SELECT 1 FROM invoices)'
    monkeypatch.setattr(service.ollama,'available',available)
    monkeypatch.setattr(service.ollama,'generate_sql',incorrect)
    from app.schemas.query import QueryRequest
    answer=asyncio.run(service.ask(QueryRequest(question='List organizations without invoices')))
    assert isinstance(answer,ClarificationResponse)
    assert 'not preserved' in answer.message


def test_programmatic_uncorrelated_or_self_repeated_plan_is_rejected():
    f=lambda t,c:ColumnRef(table=t,column=c)
    with pytest.raises(ValueError):
        QueryExistence(entity='children',correlations=[])
    for entity,pair in [('parents',(f('parents','id'),f('parents','id'))),
                        ('children',(f('children','id'),f('children','parent_id')))]:
        plan=CompositionalQuery(entity='parents',measure=QueryMeasure(function='count'),
            existence=[QueryExistence(entity=entity,correlations=[pair])])
        with pytest.raises(CoverageError):
            compile_query(plan)


def test_two_membership_bridges_require_explicit_definition(fixture):
    adapter,_=fixture
    with closing(sqlite3.connect(adapter.path)) as db:
        db.executescript('''CREATE TABLE permissions(person_id INTEGER REFERENCES people,
            org_id INTEGER REFERENCES organizations,PRIMARY KEY(person_id,org_id));''')
    catalog=SchemaCatalog(adapter.discover_schema(),adapter.profile_values())
    answer=plan_compositional('How many distinct people belong to an organization?',catalog)
    assert answer.sql is None
    assert 'unique' in answer.clarification


def test_unique_activity_path_is_not_interpreted_as_membership(fixture):
    adapter,_=fixture
    with closing(sqlite3.connect(adapter.path)) as db:
        db.execute('DROP TABLE memberships')
        db.commit()
    catalog=SchemaCatalog(adapter.discover_schema(),adapter.profile_values())
    answer=plan_compositional('How many distinct people belong to an organization?',catalog)
    assert answer.sql is None
    assert 'unique' in answer.clarification


def test_mutated_plan_cannot_clear_correlations(fixture):
    _,catalog=fixture
    answer=plan_compositional('List organizations with no paid invoices',catalog)
    plan=answer.plan.composition
    plan.existence[0].correlations.clear()
    with pytest.raises(CoverageError,match='correlated'):
        compile_query(plan)


def test_matching_category_values_in_two_fields_are_ambiguous(fixture):
    adapter,_=fixture
    with closing(sqlite3.connect(adapter.path)) as db:
        db.executescript("ALTER TABLE invoices ADD COLUMN category TEXT; UPDATE invoices SET category='paid';")
        db.commit()
    catalog=SchemaCatalog(adapter.discover_schema(),adapter.profile_values())
    answer=plan_compositional('List organizations with no paid invoices',catalog)
    assert answer.sql is None
    assert 'multiple fields' in answer.clarification


def test_invalid_foreign_key_target_never_becomes_an_uncorrelated_query(tmp_path):
    path=tmp_path/'invalid.db'
    with closing(sqlite3.connect(path)) as db:
        db.executescript('CREATE TABLE parents(a INTEGER); CREATE TABLE children(x INTEGER REFERENCES parents);')
    catalog=SchemaCatalog(SQLiteAdapter(path).discover_schema())
    answer=plan_compositional('List parents without children',catalog)
    assert answer.sql is None
    assert 'unresolved' in answer.clarification
