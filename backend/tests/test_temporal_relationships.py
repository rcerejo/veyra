import asyncio
from contextlib import closing
from datetime import date
import sqlite3

import pytest

from app.core.config import Settings
from app.database.sqlite import SQLiteAdapter
from app.database.schema import SchemaCatalog
from app.query_engine.compositional import plan_compositional,compile_query,validate_coverage,CoverageError
from app.query_engine.temporal import validate_timestamp_column
from app.query_engine.validator import validate_sql
from app.query_engine.service import QueryService
from app.schemas.query import QueryRequest,ClarificationResponse


@pytest.fixture
def temporal(tmp_path):
    path=tmp_path/'dates.db'
    with closing(sqlite3.connect(path)) as db:
        db.executescript('''
        CREATE TABLE enrollments(enrollment_id INTEGER PRIMARY KEY,joined_on TEXT);
        CREATE TABLE lesson_views(view_id INTEGER PRIMARY KEY,enrollment_id INTEGER REFERENCES enrollments,viewed_on TEXT);
        CREATE TABLE completions(completion_id INTEGER PRIMARY KEY,enrollment_id INTEGER REFERENCES enrollments,completed_on TEXT);
        INSERT INTO enrollments VALUES(1,'2026-03-01'),(2,'2026-03-02'),(3,NULL),(4,'2026-02-01'),(5,'2026-03-01');
        INSERT INTO lesson_views VALUES(1,1,'2026-03-01'),(2,1,'2026-03-02'),(3,2,'2026-03-01'),(4,3,'2026-03-03'),(5,4,NULL),(6,5,'2026-03-01T01:00:00+02:00');
        INSERT INTO completions VALUES(1,4,'2026-03-10'),(2,4,'2026-04-01'),(3,1,'2026-03-31');
        CREATE TABLE parcels(parcel_id INTEGER PRIMARY KEY,shipped_on TEXT);
        CREATE TABLE checkpoints(checkpoint_id INTEGER PRIMARY KEY,parcel_id INTEGER REFERENCES parcels,stage TEXT,occurred_on TEXT);
        INSERT INTO parcels VALUES(1,'2026-03-01'),(2,'2026-03-02'),(3,NULL),(4,'2026-03-05');
        INSERT INTO checkpoints VALUES(1,1,'delivered','2026-03-01'),(2,1,'delivered','2026-03-02'),(3,2,'delivered','2026-03-01'),(4,3,'delivered','2026-03-04');
        ''')
        db.commit()
    adapter=SQLiteAdapter(path)
    return adapter,SchemaCatalog(adapter.discover_schema(),adapter.profile_values())


@pytest.mark.parametrize('question,expected',[
    ('Count enrollments with a lesson view on or after their join date',[[1]]),
    ('Count enrollments with a lesson view after their join date',[[1]]),
    ('List enrollments without a lesson view on or after their join date',[[2,'2026-03-02'],[4,'2026-02-01'],[5,'2026-03-01']]),
    ('Count enrollments with lesson views before their join date',[[2]]),
    ('Count enrollments with completions during March 2026',[[2]]),
    ('How many enrollments joined before March 1, 2026 but completed during March?',[[1]]),
    ('Count parcels delivered on or after their shipping date',[[1]]),
    ('Count enrollments with completions from March 10 through March 31, 2026 inclusive',[[2]]),
    ('Count enrollments with completions on or before March 10, 2026',[[1]]),
    ('Count enrollments with completions after March 10, 2026',[[2]]),
    ('Count enrollments with completions from 2026-03-10 to 2026-04-01 exclusive',[[2]]),
])
def test_temporal_relationship_results(temporal,question,expected):
    adapter,catalog=temporal
    answer=plan_compositional(question,catalog)
    assert answer.sql is not None,answer.clarification
    sql=validate_sql(answer.sql,catalog)
    validate_coverage(answer.plan.composition,sql)
    _,rows,truncated=adapter.execute_readonly(sql,5000,2)
    assert not truncated
    assert sorted([list(r.values()) for r in rows],key=str)==sorted(expected,key=str)


@pytest.mark.parametrize('window,start,end',[
    ('last 7 days','2026-03-25','2026-04-01'),
    ('in the last 7 UTC calendar days','2026-03-25','2026-04-01'),
    ('last week','2026-03-23','2026-03-30'),
    ('this week','2026-03-30','2026-04-06'),
    ('last month','2026-03-01','2026-04-01'),
])
def test_relative_windows_resolve_from_injected_utc_clock(temporal,window,start,end):
    _,catalog=temporal
    answer=plan_compositional('Count enrollments with completions '+window,catalog,today=date(2026,4,1))
    assert answer.sql is not None,answer.clarification
    constraint=answer.plan.composition.existence[0].dates[0]
    assert (constraint.start,constraint.end)==(start,end)
    assert constraint.resolution and 'UTC' in constraint.resolution


@pytest.mark.parametrize('question',[
    'Count enrollments with completions last 0 days',
    'Count enrollments with completions last 900 days',
    'Count enrollments with completions from March 31 to March 1, 2026 exclusive',
    'Count enrollments with completions from March 1 to March 20, 2026',
    'Count enrollments with completions last 24 hours',
    'Count enrollments with completions in March 2026 or April 2026',
    'Count enrollments with lesson views after their cancellation date',
    'Count enrollments with lesson views within 7 days of their join date',
    'Count enrollments with completions during March 2026 and lesson views',
])
def test_unrepresented_or_ambiguous_temporal_requests_are_withheld(temporal,question):
    _,catalog=temporal
    answer=plan_compositional(question,catalog)
    assert answer.sql is None
    assert answer.clarification


def test_multiple_inner_timestamp_roles_are_not_guessed(temporal):
    adapter,_=temporal
    with closing(sqlite3.connect(adapter.path)) as db:
        db.execute('ALTER TABLE lesson_views ADD COLUMN imported_at TEXT')
        db.commit()
    catalog=SchemaCatalog(adapter.discover_schema(),adapter.profile_values())
    answer=plan_compositional('Count enrollments with lesson views during March 2026',catalog)
    # viewed_on is explicitly grounded by the view stem; ambiguous generic names
    # must instead require a role.
    assert answer.sql is not None
    with closing(sqlite3.connect(adapter.path)) as db:
        db.executescript('CREATE TABLE actions(id INTEGER PRIMARY KEY,enrollment_id INTEGER REFERENCES enrollments,created_at TEXT,updated_at TEXT);')
    catalog=SchemaCatalog(adapter.discover_schema(),adapter.profile_values())
    answer=plan_compositional('Count enrollments with actions during March 2026',catalog)
    assert answer.sql is None
    assert 'timestamp' in answer.clarification


@pytest.mark.parametrize('value',['03/01/2026','2026-02-30','1772323200','garbage'])
def test_full_timestamp_validation_rejects_invalid_values_beyond_old_sample(temporal,value):
    adapter,catalog=temporal
    with closing(sqlite3.connect(adapter.path)) as db:
        db.executemany('INSERT INTO lesson_views VALUES(?,?,?)',[(100+i,1,'2026-03-01') for i in range(1001)])
        db.execute('INSERT INTO lesson_views VALUES(9999,1,?)',(value,))
        db.commit()
    field=plan_compositional('Count enrollments with lesson views after their join date',catalog).plan.composition.existence[0].timestamps[0].left
    with pytest.raises(CoverageError,match='invalid or mixed'):
        validate_timestamp_column(adapter,field)
    service=QueryService(Settings(database_path=adapter.path))
    service.adapter=adapter
    result=asyncio.run(service.ask(QueryRequest(question='Count enrollments with lesson views after their join date')))
    assert isinstance(result,ClarificationResponse)


@pytest.mark.parametrize('mutation',[
    lambda s:s.replace(' >= ',' > '),
    lambda s:s.replace('JULIANDAY("lesson_views"."viewed_on")','JULIANDAY("enrollments"."joined_on")'),
    lambda s:s.replace('JULIANDAY("enrollments"."joined_on") IS NOT NULL AND ',''),
    lambda s:s.replace(' AND JULIANDAY("lesson_views"."viewed_on") >= JULIANDAY("enrollments"."joined_on")',''),
])
def test_temporal_comparison_mutations_fail_coverage(temporal,mutation):
    _,catalog=temporal
    answer=plan_compositional('Count enrollments with lesson views on or after their join date',catalog)
    sql=compile_query(answer.plan.composition)
    changed=mutation(sql)
    assert changed!=sql
    with pytest.raises(CoverageError):
        validate_coverage(answer.plan.composition,changed)


def test_inner_window_cannot_move_outside_exists_or_change_end(temporal):
    _,catalog=temporal
    answer=plan_compositional('Count enrollments with completions during March 2026',catalog)
    sql=answer.sql
    assert sql
    for changed in (sql.replace("'2026-04-01'","'2026-05-01'"),sql.replace(" < JULIANDAY('2026-04-01')"," <= JULIANDAY('2026-04-01')")):
        assert changed!=sql
        with pytest.raises(CoverageError):
            validate_coverage(answer.plan.composition,changed)
