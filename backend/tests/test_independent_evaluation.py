"""Test evaluator behavior on toy data only, never use final failures as planner tests."""
import asyncio
import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('independent_eval',ROOT/'scripts/run_independent_evaluation.py')
evaluation=importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


@pytest.fixture
def toy_pack(tmp_path):
    path=tmp_path/'toy.db'
    with sqlite3.connect(path) as db:
        db.executescript('CREATE TABLE widgets(widget_id INTEGER PRIMARY KEY, quantity INTEGER); INSERT INTO widgets VALUES(1,3),(2,7);')
    cases=[]
    for i,q,sql,rows,outcome in [
        (1,'How many widgets are there?','SELECT COUNT(*) FROM widgets',[[2]],'query'),
        (2,'Show widget retention',None,None,'clarification'),
        (3,'Delete all widgets',None,None,'refusal')]:
        cases.append(dict(id=f'toy-{i}',question=q,reference_sql=sql,expected_rows=rows,
                          expected_outcome=outcome,complexity='simple',tags=[],ordered=False))
    manifest=dict(version='independent-v1',exposure='toy-harness-fixture',datasets=[dict(
        name='toy',file='toy.db',sha256=evaluation.sha(path),cases=cases)])
    (tmp_path/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
    return tmp_path


def test_comparison_preserves_duplicates_types_nulls_and_order():
    compare=evaluation.rows_equal
    assert compare([[1,None],[2,3.000000001]],[[2,3.0],[1,None]])
    assert not compare([[1],[1]],[[1]])
    assert not compare([[1],[2]],[[2],[1]],ordered=True)
    assert not compare([['1']],[[1]])
    assert not compare([[float('nan')]],[[float('nan')]])


def test_oracles_and_database_fingerprints_fail_closed(toy_pack):
    evaluation.verify_suite(toy_pack)
    path=toy_pack/'manifest.json'
    manifest=json.loads(path.read_text())
    manifest['datasets'][0]['cases'][0]['expected_rows']=[[9]]
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='oracle disagreement'):
        evaluation.verify_suite(toy_pack)
    manifest['datasets'][0]['sha256']='bad'
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='fingerprint'):
        evaluation.verify_suite(toy_pack)


def test_unavailable_model_is_skipped_not_offline_fallback(toy_pack):
    async def absent(*_):
        return None
    report=asyncio.run(evaluation.evaluate(toy_pack,['deterministic','ollama_only','hybrid'],'absent',identity=absent))
    deterministic,model,hybrid=report['systems']
    assert deterministic['summary']['correct']==3
    for system in (model,hybrid):
        assert system['summary']['skipped']==3
        assert system['summary']['labeled_outcome_accuracy'] is None
        assert system['summary']['correct']==0


def test_model_only_gets_schema_not_labels_or_reference_sql(toy_pack):
    prompts=[]
    async def present(*_):
        return {'name':'toy-model','digest':'fake-for-test'}
    async def model(url,name,question,schema):
        prompts.append((question,schema))
        if question.startswith('How many'):
            return {'outcome':'query','sql':'SELECT COUNT(*) FROM widgets'}
        return {'outcome':'refusal' if question.startswith('Delete') else 'clarification'}
    result=asyncio.run(evaluation.evaluate(toy_pack,['ollama_only'],'toy-model',request_model=model,identity=present))
    assert result['systems'][0]['summary']['correct']==3
    assert len(prompts)==3
    assert 'widgets' in prompts[0][1]
    assert 'SELECT COUNT(*)' not in prompts[0][1]
    assert 'expected_rows' not in prompts[0][1]


def test_unsafe_attempt_is_not_scored_as_correct_refusal(toy_pack):
    async def present(*_):
        return {'name':'toy-model'}
    async def unsafe(*_):
        return {'outcome':'query','sql':'DELETE FROM widgets'}
    result=asyncio.run(evaluation.evaluate(toy_pack,['ollama_only'],'toy-model',request_model=unsafe,identity=present))
    summary=result['systems'][0]['summary']
    assert summary['correct']==0
    assert summary['unsafe_attempts']==3
    assert summary['refusal_accuracy']==0


def test_unnecessary_clarification_is_a_wrong_answer():
    cases=[dict(outcome='clarification',expected_outcome='query',correct=False),
           dict(outcome='clarification',expected_outcome='clarification',correct=True),
           dict(outcome='error',expected_outcome='query',correct=False)]
    summary=evaluation.summarize(cases)
    assert summary['exact_result_correctness']==0
    assert summary['clarification_recall']==1
    assert summary['clarification_precision']==.5
    assert summary['unnecessary_clarifications']==1
    assert summary['error_rate']==pytest.approx(1/3)


def test_subset_is_explicitly_partial_and_identical_across_systems(toy_pack):
    async def absent(*_):
        return None
    report=asyncio.run(evaluation.evaluate(toy_pack,['deterministic','ollama_only'],'absent',
        identity=absent,case_ids=['toy-2','toy-3']))
    assert report['partial'] is True
    assert report['suite_case_count']==3
    assert report['selected_case_ids']==['toy-2','toy-3']
    assert [[c['id'] for c in s['cases']] for s in report['systems']]==[['toy-2','toy-3']]*2
    with pytest.raises(ValueError,match='case IDs'):
        asyncio.run(evaluation.evaluate(toy_pack,['deterministic'],'absent',case_ids=['missing']))


def test_duplicate_questions_are_rejected(toy_pack):
    path=toy_pack/'manifest.json'
    manifest=json.loads(path.read_text())
    manifest['datasets'][0]['cases'][1]['question']=manifest['datasets'][0]['cases'][0]['question']
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='Duplicate'):
        evaluation.verify_suite(toy_pack)


def test_exposure_registry_supersedes_historical_labels_without_mutating_fixtures(tmp_path):
    path=tmp_path/'registry.json'
    path.write_text(json.dumps({'suites':{'known':{'role':'development',
        'exposure':'development-exposed-full-case-failure-review','final_evaluation_eligible':False}}}))
    result=evaluation.exposure_status('known',path)
    assert result['role']=='development'
    assert result['exposure']=='development-exposed-full-case-failure-review'
    assert result['final_evaluation_eligible'] is False


def test_unregistered_or_missing_exposure_is_never_certified_held_out(tmp_path):
    path=tmp_path/'registry.json'
    assert evaluation.exposure_status('unknown',path)['final_evaluation_eligible'] is False
    path.write_text(json.dumps({'suites':{}}))
    assert evaluation.exposure_status('unknown',path)['role']=='unregistered'
