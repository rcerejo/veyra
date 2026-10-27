import asyncio
from contextlib import closing
import sqlite3

import pytest

from app.core.config import Settings
from app.database.sqlite import SQLiteAdapter
from app.database.schema import SchemaCatalog
from app.query_engine.compositional import plan_compositional,validate_coverage,CoverageError
from app.query_engine.service import QueryService
from app.query_engine.validator import validate_sql
from app.schemas.query import QueryRequest,ClarificationResponse


@pytest.fixture
def activity(tmp_path):
    path=tmp_path/'activity.db'
    with closing(sqlite3.connect(path)) as db:
        db.executescript('''
        CREATE TABLE people(person_id INTEGER PRIMARY KEY);
        CREATE TABLE audit_log(log_id INTEGER PRIMARY KEY,actor_id INTEGER REFERENCES people,occurred_on TEXT,state TEXT);
        INSERT INTO people VALUES(1),(2),(3),(4),(5),(6);
        INSERT INTO audit_log VALUES(1,1,'2026-03-01T10:00:00','active'),(2,1,'2026-03-01T11:00:00','active'),
          (3,2,'2026-03-01T12:00:00','inactive'),(4,1,'2026-03-02','active'),
          (5,3,'2026-03-02','inactive'),(6,NULL,'2026-03-02','active'),(7,1,'2026-03-03', 'active'),
          (8,2,'2026-03-08','active'),(9,4,'2026-03-09','active'),(10,5,NULL,'active');
        CREATE TABLE parcels(parcel_id INTEGER PRIMARY KEY);
        CREATE TABLE checkpoints(checkpoint_id INTEGER PRIMARY KEY,parcel_id INTEGER REFERENCES parcels,stage TEXT,occurred_on TEXT);
        INSERT INTO parcels VALUES(1),(2),(3);
        INSERT INTO checkpoints VALUES(1,1,'delivered','2026-03-01'),(2,1,'delivered','2026-03-01'),
          (3,2,'accepted','2026-03-01'),(4,2,'delivered','2026-03-02');
        CREATE TABLE learners(learner_id INTEGER PRIMARY KEY);
        CREATE TABLE enrollments(enrollment_id INTEGER PRIMARY KEY,learner_id INTEGER REFERENCES learners);
        CREATE TABLE lesson_views(view_id INTEGER PRIMARY KEY,enrollment_id INTEGER REFERENCES enrollments,viewed_on TEXT);
        INSERT INTO learners VALUES(1),(2),(3);
        INSERT INTO enrollments VALUES(1,1),(2,1),(3,2);
        INSERT INTO lesson_views VALUES(1,1,'2026-03-01'),(2,2,'2026-03-01'),(3,3,'2026-03-01');
        ''')
        db.commit()
    adapter=SQLiteAdapter(path)
    return adapter,SchemaCatalog(adapter.discover_schema(),adapter.profile_values())


@pytest.mark.parametrize('question,expected',[
    ('Daily distinct active people from the audit log',[['2026-03-01',2],['2026-03-02',2],['2026-03-03',1],['2026-03-08',1],['2026-03-09',1]]),
    ('Weekly distinct active people from the audit log',[['2026-02-23',2],['2026-03-02',3],['2026-03-09',1]]),
    ('Count distinct actors active March 1 through March 8, 2026 inclusive',[[3]]),
    ('Count distinct delivered parcels per day',[['2026-03-01',1],['2026-03-02',1]]),
    ('Number of distinct viewing learners each day',[['2026-03-01',2]]),
    ('Count distinct active people from audit log',[[5]]),
])
def test_observed_identity_counts_not_rows_or_registered_population(activity,question,expected):
    adapter,catalog=activity
    answer=plan_compositional(question,catalog)
    assert answer.sql is not None,answer.clarification
    assert answer.plan.composition.activity is not None
    sql=validate_sql(answer.sql,catalog)
    validate_coverage(answer.plan.composition,sql)
    _,rows,truncated=adapter.execute_readonly(sql,5000,2)
    assert not truncated
    assert sorted([list(r.values()) for r in rows],key=str)==sorted(expected,key=str)


@pytest.mark.parametrize('question',[
    'Daily distinct active people',  # no observed fact/category/role evidence
    'Daily distinct active people from audit log by nonsense',
    'Count distinct people from audit log then checkpoints per day',
    'Daily and weekly distinct actors',
    'Daily distinct active people from audit log in local timezone',
    'Daily distinct inactive people from audit log except actors',
    'Count distinct accepted or delivered parcels per day',
])
def test_ambiguous_meanings_and_unsupported_qualifiers_remain_withheld(activity,question):
    _,catalog=activity
    answer=plan_compositional(question,catalog)
    assert answer.sql is None
    assert answer.clarification


def test_two_actor_roles_require_explicit_key(activity):
    adapter,_=activity
    with closing(sqlite3.connect(adapter.path)) as db:
        db.executescript('ALTER TABLE audit_log ADD COLUMN reviewer_id INTEGER REFERENCES people;')
    catalog=SchemaCatalog(adapter.discover_schema(),adapter.profile_values())
    answer=plan_compositional('Daily distinct active people from audit log',catalog)
    assert answer.sql is None
    assert 'Multiple' in answer.clarification


def test_distinct_and_filter_and_week_grain_are_coverage_checked(activity):
    _,catalog=activity
    answer=plan_compositional('Count distinct delivered parcels per day',catalog)
    sql=answer.sql
    for changed in (sql.replace('DISTINCT ',''),sql.replace("\"checkpoints\".\"stage\" = 'delivered' AND ",''),sql.replace('parcel_id','checkpoint_id')):
        assert changed!=sql
        with pytest.raises(CoverageError):
            validate_coverage(answer.plan.composition,changed)
    weekly=plan_compositional('Weekly distinct active people from audit log',catalog)
    changed=weekly.sql.replace(", 'weekday 0', '-6 days'",'')
    assert changed!=weekly.sql
    with pytest.raises(CoverageError):
        validate_coverage(weekly.plan.composition,changed)


def test_model_counting_all_registered_people_is_withheld(activity,monkeypatch):
    adapter,_=activity
    service=QueryService(Settings(database_path=adapter.path,prefer_model_sql=True))
    service.adapter=adapter
    async def available():
        return True
    async def wrong(*_):
        return 'SELECT COUNT(*) FROM people'
    monkeypatch.setattr(service.ollama,'available',available)
    monkeypatch.setattr(service.ollama,'generate_sql',wrong)
    answer=asyncio.run(service.ask(QueryRequest(question='Count distinct active people from audit log')))
    assert isinstance(answer,ClarificationResponse)


def test_invalid_fact_dates_do_not_silently_form_a_null_cohort(activity):
    adapter,_=activity
    with closing(sqlite3.connect(adapter.path)) as db:
        db.execute("UPDATE audit_log SET occurred_on='03/01/2026' WHERE log_id=1")
        db.commit()
    service=QueryService(Settings(database_path=adapter.path))
    service.adapter=adapter
    answer=asyncio.run(service.ask(QueryRequest(question='Daily distinct active people from audit log')))
    assert isinstance(answer,ClarificationResponse)
    assert 'invalid or mixed' in answer.message


def test_utc_offsets_use_utc_calendar_boundaries(activity):
    adapter,catalog=activity
    with closing(sqlite3.connect(adapter.path)) as db:
        db.execute("INSERT INTO audit_log VALUES(11,4,'2026-03-02T00:30:00+01:00','active')")
        db.commit()
    answer=plan_compositional('Weekly distinct active people from audit log',catalog)
    _,rows,_=adapter.execute_readonly(validate_sql(answer.sql,catalog),5000,2)
    assert next(list(r.values())[1] for r in rows if list(r.values())[0]=='2026-02-23')==3


def test_null_calendar_filter_cannot_be_removed(activity):
    _,catalog=activity
    answer=plan_compositional('Daily distinct active people from audit log',catalog)
    changed=answer.sql.replace(' WHERE "audit_log"."occurred_on" IS NOT NULL','')
    assert changed!=answer.sql
    with pytest.raises(CoverageError):
        validate_coverage(answer.plan.composition,changed)
