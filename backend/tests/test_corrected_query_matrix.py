"""Development fixture/oracle integrity and metamorphic checks, not held-out tests."""
from contextlib import closing
import importlib.util
import json
from pathlib import Path
import random
import sqlite3

import pytest

from app.database.combine import DatabaseCombiner, digest
from app.database.registry import DatabaseRegistry
from app.database.schema import SchemaCatalog
from app.database.sqlite import SQLiteAdapter
from app.query_engine.compositional import CoverageError, plan_compositional, validate_coverage
from app.query_engine.validator import validate_sql
from app.schemas.database import CombineDatabases

ROOT=Path(__file__).resolve().parents[2]


def load(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/file)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder=load('corrected_matrix_builder','build_corrected_query_matrix.py')
evaluation=load('corrected_matrix_evaluation','run_independent_evaluation.py')


@pytest.mark.parametrize('seed',[23,59])
def test_matrix_python_oracles_and_labels(tmp_path,seed):
    pack=tmp_path/'pack'
    builder.build(pack,seed)
    manifest=evaluation.verify_suite(pack)
    cases=[c for d in manifest['datasets'] for c in d['cases']]
    assert len(cases)==168
    assert sum(c['expected_outcome']=='query' for c in cases)==144
    assert sum('corrected_control' in c['tags'] for c in cases)==100
    assert sum('nearby_wording' in c['tags'] for c in cases)==44
    assert manifest['exposure'].startswith('development-exposed')
    assert not manifest['external_blind']


def test_matrix_reproducibility_variation_and_no_overwrite(tmp_path):
    first=builder.build(tmp_path/'first',23)
    assert first==builder.build(tmp_path/'same',23)
    second=builder.build(tmp_path/'different',59)
    assert [c['question'] for d in first['datasets'] for c in d['cases']]==[c['question'] for d in second['datasets'] for c in d['cases']]
    assert all(a['sha256']!=b['sha256'] for a,b in zip(first['datasets'],second['datasets']))
    assert any(a['expected_rows']!=b['expected_rows'] for a,b in zip(first['datasets'][0]['cases'],second['datasets'][0]['cases']))
    with pytest.raises(FileExistsError):
        builder.build(tmp_path/'first',23)


def test_matrix_rejects_corrupted_oracle(tmp_path):
    pack=tmp_path/'pack'
    manifest=builder.build(pack)
    manifest['datasets'][0]['cases'][0]['expected_rows']=[[9999]]
    (pack/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='oracle disagreement'):
        evaluation.verify_suite(pack)


@pytest.mark.parametrize('seed',[23,59])
def test_contrastive_probes_reuse_source_data_but_have_distinct_nonempty_targets(tmp_path,monkeypatch,seed):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    probes=load('literal_collision_builder','build_literal_collision_probes.py')
    matrix=builder.build(tmp_path/'matrix',seed)
    probe_pack=tmp_path/'probes'
    result=probes.build(probe_pack,seed)
    evaluation.verify_suite(probe_pack)
    assert sum(len(d['cases']) for d in result['datasets'])==32
    for source,probe in zip(matrix['datasets'],result['datasets']):
        assert source['sha256']==probe['sha256']
        assert probe['cases'][0]['expected_rows']!=probe['cases'][3]['expected_rows']
        assert all(c['expected_rows'][0][0]>0 for c in probe['cases'])


def answer(path,question):
    adapter=SQLiteAdapter(path)
    catalog=SchemaCatalog(adapter.discover_schema(),adapter.profile_values())
    planned=plan_compositional(question,catalog)
    assert planned.sql,planned.clarification
    sql=validate_sql(planned.sql,catalog)
    validate_coverage(planned.plan.composition,sql)
    _,rows,truncated=adapter.execute_readonly(sql,5000,3)
    assert not truncated
    return [list(r.values()) for r in rows],planned


def create_roles(path,seed,mode='mixed'):
    rng=random.Random(seed)
    rows=[] if mode=='empty' else [(i,None if mode=='null' or i%11==0 else rng.randint(1,4),
        None if mode=='null' or i%7==0 else rng.randint(5,6),
        0 if i<=3 else rng.choice([0,1.5,-2.5,None]),'zero' if i%4==0 else 'clear') for i in range(1,41)]
    with closing(sqlite3.connect(path)) as db:
        db.executescript('''PRAGMA foreign_keys=ON;
            CREATE TABLE people(person_id INTEGER PRIMARY KEY);
            CREATE TABLE audits(audit_id INTEGER PRIMARY KEY,inspector_id INTEGER REFERENCES people,
              reviewer_id INTEGER REFERENCES people,fee REAL,status TEXT);''')
        db.executemany('INSERT INTO people VALUES(?)',[(i,) for i in range(1,9)])
        db.executemany('INSERT INTO audits VALUES(?,?,?,?,?)',rows)
        db.commit()
    return rows


@pytest.mark.parametrize('seed',[7,23,59,101,203])
def test_duplication_and_inactive_registration_do_not_change_distinct_identity(tmp_path,seed):
    path=tmp_path/'metamorphic.db'
    rows=create_roles(path,seed)
    distinct=len({r[1] for r in rows if r[1] is not None})
    assert answer(path,'Count audits')[0]==[[len(rows)]]
    assert answer(path,'Count distinct inspectors from audits')[0]==[[distinct]]
    assert answer(path,'Count distinct reviewers from audits')[0]==[[len({r[2] for r in rows if r[2] is not None})]]
    assert answer(path,'Count audits where fee is zero')[0]==[[sum(r[3]==0 for r in rows)]]
    with closing(sqlite3.connect(path)) as db:
        db.execute('INSERT INTO audits VALUES(?,?,?,?,?)',(100,*rows[0][1:]))
        db.execute('INSERT INTO people VALUES(999)')
        db.commit()
    assert answer(path,'Count audits')[0]==[[len(rows)+1]]
    assert answer(path,'Count people')[0]==[[9]]
    assert answer(path,'Count distinct inspectors from audits')[0]==[[distinct]]
    assert answer(path,'Count audits where fee is zero')[0]==[[sum(r[3]==0 for r in rows)+1]]
    with closing(sqlite3.connect(path)) as db:
        db.executescript('ALTER TABLE audits RENAME TO verifications; ALTER TABLE verifications RENAME COLUMN inspector_id TO checker_id; ALTER TABLE verifications RENAME COLUMN fee TO cost;')
        db.commit()
    assert answer(path,'Count distinct checkers from verifications')[0]==[[distinct]]
    assert answer(path,'Count verifications where cost is zero')[0]==[[sum(r[3]==0 for r in rows)+1]]


@pytest.mark.parametrize('mode',['empty','null'])
def test_empty_facts_and_all_null_identities(tmp_path,mode):
    path=tmp_path/'empty-or-null.db'
    rows=create_roles(path,23,mode)
    assert answer(path,'Count audits')[0]==[[len(rows)]]
    assert answer(path,'Count distinct inspectors from audits')[0]==[[0]]
    assert answer(path,'Count distinct reviewers from audits')[0]==[[0]]
    if mode=='empty':
        assert answer(path,'Count audits by status')[0]==[]


@pytest.mark.parametrize('value',['zero.','clear.'])
def test_quoted_punctuation_is_a_literal_not_sentence_termination(tmp_path,value):
    path=tmp_path/'quoted-punctuation.db'
    create_roles(path,23)
    rows,planned=answer(path,f'Count audits where status is "{value}"')
    assert rows==[[0]]
    assert planned.plan.composition.filters[0].value==value
    assert answer(path,f'Count audits where status is "{value[:-1]}"')[0][0][0]>0


@pytest.mark.parametrize('phrase',['with fee of zero','fee of zero','with zero fee'])
def test_numeric_field_binding_cannot_be_replaced_by_sample_category(tmp_path,phrase):
    path=tmp_path/'binding.db'
    rows=create_roles(path,23)
    actual,planned=answer(path,f'Count audits {phrase}')
    assert actual==[[sum(r[3]==0 for r in rows)]]
    filters=planned.plan.composition.filters
    assert len(filters)==1 and filters[0].field.column=='fee' and filters[0].value==0
    with pytest.raises(CoverageError):
        validate_coverage(planned.plan.composition,planned.sql.replace('"fee"','"status"'))


@pytest.mark.parametrize('value',['zero','clear'])
def test_unquoted_sentence_period_does_not_change_text_filter(tmp_path,value):
    path=tmp_path/'sentence.db'
    create_roles(path,23)
    assert answer(path,f'Count audits where status is {value}.')[0]==answer(path,f'Count audits where status is "{value}"')[0]


def test_of_in_measure_description_is_not_an_equality(tmp_path):
    path=tmp_path/'measure-description.db'
    with closing(sqlite3.connect(path)) as db:
        db.executescript('CREATE TABLE lesson_viewing(id INTEGER PRIMARY KEY,minutes INTEGER); INSERT INTO lesson_viewing VALUES(1,3),(2,7);')
        db.commit()
    rows,planned=answer(path,'Total minutes of lesson viewing')
    assert rows==[[10]]
    assert not planned.plan.composition.filters


@pytest.mark.parametrize('phrase',['with fee of high','with fee of zero or ten','with zero fee and fee is one'])
def test_unresolved_or_conflicting_binding_is_withheld(tmp_path,phrase):
    path=tmp_path/'unsupported-binding.db'
    create_roles(path,23)
    adapter=SQLiteAdapter(path)
    catalog=SchemaCatalog(adapter.discover_schema(),adapter.profile_values())
    result=plan_compositional(f'Count audits {phrase}',catalog)
    assert result.sql is None and result.clarification


@pytest.mark.parametrize('seed',[11,37,59])
@pytest.mark.parametrize('aliases',[('crm','product'),('core','usage'),('left1','right2')])
def test_join_snapshots_preserve_grain_and_earlier_versions(tmp_path,seed,aliases):
    rng=random.Random(seed)
    left,right=aliases
    crm=tmp_path/'crm.db'
    product=tmp_path/'product.db'
    rows=[(i,None if i%9==0 else rng.randint(1,3),100+rng.randint(1,5)) for i in range(1,31)]
    with closing(sqlite3.connect(crm)) as db:
        db.executescript('''CREATE TABLE accounts(account_id INTEGER PRIMARY KEY,plan TEXT);
            CREATE TABLE users(user_id INTEGER PRIMARY KEY);
            CREATE TABLE memberships(user_id INTEGER REFERENCES users,account_id INTEGER REFERENCES accounts,
              PRIMARY KEY(user_id,account_id));
            INSERT INTO accounts VALUES(1,'free'),(2,'pro'),(3,'pro');''')
        db.executemany('INSERT INTO users VALUES(?)',[(i,) for i in range(101,106)])
        db.executemany('INSERT INTO memberships VALUES(?,?)',[(i,a) for i in range(101,106) for a in range(1,4)])
        db.commit()
    with closing(sqlite3.connect(product)) as db:
        db.execute('CREATE TABLE activity(event_id INTEGER PRIMARY KEY,workspace_id INTEGER,user_id INTEGER)')
        db.executemany('INSERT INTO activity VALUES(?,?,?)',rows)
        db.commit()
    request=CombineDatabases(name='metamorphic',sources=[dict(name='crm.db',alias=left),dict(name='product.db',alias=right)],relationships=[
        dict(child_source=right,child_table='activity',child_columns=['workspace_id'],parent_source=left,parent_table='accounts',parent_columns=['account_id']),
        dict(child_source=right,child_table='activity',child_columns=['user_id'],parent_source=left,parent_table='users',parent_columns=['user_id'])])
    registry=DatabaseRegistry(crm)
    before=(digest(crm),digest(product))
    result=DatabaseCombiner(registry).create(request)
    assert (digest(crm),digest(product))==before
    first=registry.resolve_source(result['database']['name'])
    first_hash=digest(first)
    def reference(data):
        return [[plan,sum(r[1] is not None and ('free' if r[1]==1 else 'pro')==plan for r in data)] for plan in ('free','pro')]
    actual,planned=answer(first,'Count activity by account plan')
    assert sorted(actual)==reference(rows)
    join=planned.plan.composition.joins[0]
    assert join.equalities[0][0].column=='workspace_id'
    wrong=planned.sql.replace('"workspace_id"','"user_id"')
    with pytest.raises(CoverageError):
        validate_coverage(planned.plan.composition,wrong)
    with closing(sqlite3.connect(product)) as db:
        db.execute('INSERT INTO activity VALUES(100,1,101)')
        db.commit()
    updated=DatabaseCombiner(registry).create(request)
    assert updated['database']['name']!=result['database']['name']
    assert digest(first)==first_hash
    assert sorted(answer(first,'Count activity by account plan')[0])==reference(rows)
    assert sorted(answer(registry.resolve_source(updated['database']['name']),'Count activity by account plan')[0])==reference([*rows,(100,1,101)])
    assert registry.active_path()==crm
