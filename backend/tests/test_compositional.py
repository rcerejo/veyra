"""Development regressions, never final/holdout fixtures."""
import asyncio
from contextlib import closing
import sqlite3

import pytest

from app.core.config import Settings
from app.database.sqlite import SQLiteAdapter
from app.database.schema import SchemaCatalog
from app.query_engine.compositional import compile_query,plan_compositional,validate_coverage,CoverageError
from app.query_engine.service import QueryService
from app.query_engine.validator import validate_sql,UnsafeQueryError
from app.schemas.query import (ColumnRef,CompositionalQuery,QueryMeasure,QueryFilter,QueryGrouping,
    QueryDateConstraint,QueryJoin,QueryRanking,QueryRequest,ClarificationResponse)


@pytest.fixture
def development(tmp_path):
    path=tmp_path/'development.db'
    with closing(sqlite3.connect(path)) as db:
        db.executescript('''
        CREATE TABLE courses(course_id INTEGER PRIMARY KEY,subject TEXT);
        CREATE TABLE enrollments(enrollment_id INTEGER PRIMARY KEY,course_id INTEGER REFERENCES courses,
          joined_on TEXT,state TEXT);
        CREATE TABLE completions(completion_id INTEGER PRIMARY KEY,score REAL);
        CREATE TABLE depots(depot_id INTEGER PRIMARY KEY,zone TEXT);
        CREATE TABLE parcels(parcel_id INTEGER PRIMARY KEY,origin_depot INTEGER REFERENCES depots,
          destination_depot INTEGER REFERENCES depots,shipped_on TEXT,weight_grams INTEGER);
        CREATE TABLE organizations(org_id INTEGER PRIMARY KEY,plan TEXT);
        CREATE TABLE invoices(invoice_id INTEGER PRIMARY KEY,org_id INTEGER REFERENCES organizations,
          usd_cents INTEGER,state TEXT,issued_on TEXT);
        INSERT INTO courses VALUES(1,'science'),(2,'art');
        INSERT INTO enrollments VALUES(1,1,'2026-03-01','active'),(2,1,'2026-03-15','cancelled'),(3,2,'2026-04-01','active');
        INSERT INTO completions VALUES(1,NULL),(2,40),(3,70),(4,90);
        INSERT INTO depots VALUES(1,'east'),(2,'west');
        INSERT INTO parcels VALUES(1,1,2,'2026-03-10',100),(2,2,1,'2026-03-20',500);
        INSERT INTO organizations VALUES(1,'free'),(2,'team');
        INSERT INTO invoices VALUES(1,1,100,'paid','2026-03-01'),(2,1,300,'void','2026-03-02'),(3,2,400,'paid','2026-03-03');
        ''')
        db.commit()
    adapter=SQLiteAdapter(path)
    return adapter,SchemaCatalog(adapter.discover_schema(),adapter.profile_values())


@pytest.mark.parametrize('question,expected',[
    ('How many completion scores are missing?',[[1]]),
    ('Average nonmissing completion score',[[200/3]]),
    ('List completions with scores at least 50',[[3,70.0],[4,90.0]]),
    ('Count completions with scores at least 50 and at most 80',[[1]]),
    ('List enrollments whose state is active',[[1,1,'2026-03-01','active'],[3,2,'2026-04-01','active']]),
    ('Enrollment counts by course subject',[['science',2],['art',1]]),
    ('Parcel counts by destination zone',[['west',1],['east',1]]),
    ('List parcels heavier than 400 grams',[[2,2,1,'2026-03-20',500]]),
    ('Average paid invoice amount in USD cents',[[250.0]]),
    ('List void invoices',[[2,1,300,'void','2026-03-02']]),
    ('List 1 void invoices',[[2,1,300,'void','2026-03-02']]),
    ('List organizations with no paid invoices',[]),
    ('Count invoices by organization plan',[['free',2],['team',1]]),
    ('Show enrollments joined in March 2026',[[1,1,'2026-03-01','active'],[2,1,'2026-03-15','cancelled']]),
    ('Count parcels on or after March 10 and before March 20, 2026',[[1]]),
    ('Daily count of invoices', [['2026-03-01',1],['2026-03-02',1],['2026-03-03',1]]),
])
def test_development_operations_compile_and_execute(development,question,expected):
    adapter,catalog=development
    answer=plan_compositional(question,catalog)
    assert answer.sql is not None,answer.clarification
    assert answer.plan.composition is not None
    sql=validate_sql(answer.sql,catalog)
    validate_coverage(answer.plan.composition,sql)
    _,rows,truncated=adapter.execute_readonly(sql,5000,2)
    assert not truncated
    assert sorted([list(r.values()) for r in rows],key=str)==sorted(expected,key=str)


@pytest.mark.parametrize('question',[
    'Show parcel counts by zone',
    'Count parcels shipped then accepted then delivered',
    'Which depot is best?',
    'List platinum invoices',
    'Count invoices by nonsense',
    'List completions where score > 50 OR score < 10',
    'Count courses by enrollment state',  # reverse one-to-many would change fact grain
    'Top three parcels by weight',
    'List 0 invoices',
    'List 9000 invoices',
    'List invoices in 2026',
    'Count parcels from March 20 through March 10, 2026',
])
def test_unresolved_requests_are_not_simplified(development,question):
    _,catalog=development
    answer=plan_compositional(question,catalog)
    assert answer.sql is None
    assert answer.clarification


def contract():
    f=lambda t,c:ColumnRef(table=t,column=c)
    return CompositionalQuery(entity='invoices',measure=QueryMeasure(function='sum',field=f('invoices','usd_cents')),
        filters=[QueryFilter(field=f('invoices','state'),operator='eq',value='paid')],
        groupings=[QueryGrouping(field=f('organizations','plan'))],
        dates=[QueryDateConstraint(field=f('invoices','issued_on'),start='2026-03-01',end='2026-04-01')],
        joins=[QueryJoin(left_table='invoices',right_table='organizations',constraint_id=0,
            equalities=[(f('invoices','org_id'),f('organizations','org_id'))])],
        ranking=[QueryRanking()],limit=10,requested_operations=['measure','filters','grouping','date_window','relationships','ranking'])


@pytest.mark.parametrize('mutation',[
    lambda s:s.replace('"invoices"."state" = \'paid\' AND ',''),
    lambda s:s.replace('GROUP BY 1',''),
    lambda s:s.replace("'2026-04-01'","'2026-05-01'"),
    lambda s:s.replace('"invoices"."org_id" = "organizations"."org_id"','1 = 1'),
    lambda s:s.replace('SUM(', 'COUNT('),
    lambda s:s.replace('LIMIT 10','LIMIT 5'),
    lambda s:s.replace('ORDER BY 2 DESC','ORDER BY 2 ASC'),
    lambda s:s.replace(' AND ',' OR ',1),
    lambda s:s.replace('FROM "invoices"','FROM "other"'),
    lambda s:s.replace('GROUP BY 1','GROUP BY 1 HAVING 1 = 0'),
])
def test_coverage_rejects_deleted_or_changed_operations(mutation):
    plan=contract()
    sql=compile_query(plan)
    validate_coverage(plan,sql)
    mutated=mutation(sql)
    assert mutated!=sql
    with pytest.raises(CoverageError):
        validate_coverage(plan,mutated)


def test_model_cannot_drop_a_planned_filter(development,monkeypatch):
    adapter,_=development
    service=QueryService(Settings(database_path=adapter.path,prefer_model_sql=True))
    service.adapter=adapter
    async def available():
        return True
    async def incomplete(*_):
        return 'SELECT * FROM invoices'
    monkeypatch.setattr(service.ollama,'available',available)
    monkeypatch.setattr(service.ollama,'generate_sql',incomplete)
    answer=asyncio.run(service.ask(QueryRequest(question='List void invoices')))
    assert isinstance(answer,ClarificationResponse)
    assert 'not preserved' in answer.message


def test_sql_safety_remains_independent_of_coverage(development):
    _,catalog=development
    with pytest.raises(UnsafeQueryError):
        validate_sql('DELETE FROM invoices',catalog)


def test_explicit_filter_literal_is_escaped_and_preserved():
    plan=CompositionalQuery(entity='items',filters=[QueryFilter(field=ColumnRef(table='items',column='status'),operator='eq',value="x' OR 1=1 --")])
    sql=compile_query(plan)
    validate_coverage(plan,sql)
    assert "x'' OR 1=1 --" in sql
