"""Development counterexamples: typed literals and requested distinct identity."""
import asyncio
from contextlib import closing
import sqlite3

import pytest

from app.core.config import Settings
from app.database.schema import SchemaCatalog
from app.database.sqlite import SQLiteAdapter
from app.query_engine.compositional import CoverageError, plan_compositional, validate_coverage
from app.query_engine.service import QueryService
from app.query_engine.validator import UnsafeQueryError, validate_sql
from app.schemas.query import ClarificationResponse, QueryRequest, QueryResponse


@pytest.fixture
def grounding(tmp_path):
    path=tmp_path/'grounding.db'
    with closing(sqlite3.connect(path)) as db:
        db.executescript('''PRAGMA foreign_keys=ON;
        CREATE TABLE people(person_id INTEGER PRIMARY KEY);
        CREATE TABLE inspections(inspection_id INTEGER PRIMARY KEY,
          inspector_id INTEGER REFERENCES people,reviewer_id INTEGER REFERENCES people,
          score REAL,fee INTEGER,label TEXT);
        INSERT INTO people VALUES(1),(2),(3),(4);
        INSERT INTO inspections VALUES
          (1,1,2,0,0,'clear'),(2,1,3,1.5,0,'clear'),(3,2,1,-2.5,10,'zero'),
          (4,NULL,2,5,5,'PASS'),(5,3,2,NULL,1,'clear'),(6,NULL,NULL,0,0,'clear');''')
        db.commit()
    adapter=SQLiteAdapter(path)
    return path,adapter,SchemaCatalog(adapter.discover_schema(),adapter.profile_values())


@pytest.mark.parametrize('question,expected',[
    ('Count inspections where fee is zero',3),
    ('Count inspections where fee equals ZERO',3),
    ('Count inspections where fee is 0',3),
    ('Count inspections where fee is "0"',3),
    ('Count inspections where fee is one',1),
    ('Count inspections where fee is ten',1),
    ('Count inspections where score is 1.5',1),
    ('Count inspections where score is -2.5',1),
    ('Count inspections where score is 1.5E0',1),
    ('Count inspections where label is zero',1),
    ('Count inspections where label is "PASS"',1),
    ('Count inspections where label equals "clear"',4),
    ('Count distinct inspectors from inspections',3),
    ('Count distinct reviewers from inspections',3),
    ('How many different reviewers from inspections?',3),
    ('Count unique inspector_id from inspections',3),
    ('Count distinct inspector id from inspections',3),
    ('Count distinct inspections.inspector_id from inspections',3),
    ('Count distinct inspections from inspections',6),
    ('Count distinct labels from inspections',3),
    ('Count distinct scores from inspections',4),
    ('Count distinct inspectors from inspections where fee is zero',1),
])
def test_grounded_answers(grounding,question,expected):
    _,adapter,catalog=grounding
    answer=plan_compositional(question,catalog)
    assert answer.sql,answer.clarification
    sql=validate_sql(answer.sql,catalog)
    validate_coverage(answer.plan.composition,sql)
    _,rows,truncated=adapter.execute_readonly(sql,5000,2)
    assert not truncated
    assert list(rows[0].values())==[expected]
    if 'fee is zero' in question:
        assert len(answer.plan.composition.filters)==1
        assert answer.plan.composition.filters[0].value==0
        assert type(answer.plan.composition.filters[0].value) is int


@pytest.mark.parametrize('question',[
    'Count inspections where fee is high',
    'Count inspections where fee is "zero"',
    'Count inspections where fee is infinity',
    'Count inspections where fee is 1e999',
    'Count inspections where fee is 999999999999999999999999',
    'Count inspections where fee is one hundred',
    'Count inspections where fee is zero and fee is ten',
    'Count distinct people from inspections',
    'Count distinct inspectors and reviewers from inspections',
    'Count distinct customers from inspections',
    'Count distinct people.person_id from inspections',
    'Count distinct from inspections',
    'List distinct inspectors from inspections',
])
def test_unknown_or_ambiguous_interpretations_are_withheld(grounding,question):
    _,_,catalog=grounding
    answer=plan_compositional(question,catalog)
    assert answer.sql is None
    assert answer.clarification


@pytest.mark.parametrize('question,mutation',[
    ('Count inspections where fee is zero',lambda s:s.replace(' = 0'," = 'zero'")),
    ('Count inspections where fee is zero',lambda s:s.replace(' = 0',' = 1')),
    ('Count distinct inspectors from inspections',lambda s:s.replace('"inspector_id"','"inspection_id"')),
    ('Count distinct reviewers from inspections',lambda s:s.replace('"reviewer_id"','"inspector_id"')),
    ('Count distinct inspectors from inspections',lambda s:s.replace('DISTINCT ','')),
])
def test_mutated_sql_cannot_override_grounded_intent(grounding,question,mutation):
    _,_,catalog=grounding
    answer=plan_compositional(question,catalog)
    assert answer.sql
    with pytest.raises(CoverageError):
        validate_coverage(answer.plan.composition,mutation(answer.sql))


def test_service_preserves_identity_and_refuses_model_substitution(grounding):
    path,adapter,_=grounding
    service=QueryService(Settings(_env_file=None,database_path=path,prefer_model_sql=False,sql_examples_path=None))
    service.adapter=adapter
    async def offline():
        return False
    service.ollama.available=offline
    request=QueryRequest(question='Count distinct inspectors from inspections')
    answer=asyncio.run(service.ask(request))
    assert isinstance(answer,QueryResponse)
    assert list(answer.rows[0].values())==[3]
    service.settings.prefer_model_sql=True
    async def online():
        return True
    async def wrong(*_):
        return 'SELECT COUNT(DISTINCT inspections.inspection_id) AS record_count FROM inspections'
    service.ollama.available=online
    service.ollama.generate_sql=wrong
    answer=asyncio.run(service.ask(request))
    assert isinstance(answer,ClarificationResponse)
    assert 'not preserved' in answer.message


def test_declared_text_values_are_not_numeric_rewrites_and_sql_stays_readonly(grounding):
    _,_,catalog=grounding
    answer=plan_compositional('Count inspections where label is zero',catalog)
    assert answer.plan.composition.filters[0].value=='zero'
    with pytest.raises(UnsafeQueryError):
        validate_sql('DELETE FROM inspections',catalog)
