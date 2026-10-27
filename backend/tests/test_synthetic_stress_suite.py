"""Test development fixture integrity, not planner performance thresholds."""
import importlib.util
import json
from pathlib import Path
import sqlite3
from contextlib import closing

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT/'scripts'/filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = load('synthetic_stress_builder', 'build_synthetic_stress_suite.py')
evaluation = load('synthetic_stress_evaluation', 'run_independent_evaluation.py')


@pytest.mark.parametrize('seed', [11,29])
def test_all_python_oracles_agree_with_validated_reference_sql(tmp_path, seed):
    pack = tmp_path/f'pack-{seed}'
    builder.build(pack,seed)
    manifest = evaluation.verify_suite(pack)
    cases = [c for d in manifest['datasets'] for c in d['cases']]
    assert len(cases) == 90
    assert sum(c['expected_outcome']=='query' for c in cases) == 78
    assert sum(c['expected_outcome']=='clarification' for c in cases) == 6
    assert sum(c['expected_outcome']=='refusal' for c in cases) == 6
    assert manifest['exposure'].startswith('development-exposed')
    assert not manifest['external_blind']


def test_deterministic_seed_and_no_overwrite(tmp_path):
    first = builder.build(tmp_path/'a',11)
    second = builder.build(tmp_path/'b',11)
    assert first == second
    with pytest.raises(FileExistsError):
        builder.build(tmp_path/'a',11)
    third = builder.build(tmp_path/'c',29)
    for a,b in zip(first['datasets'],third['datasets']):
        assert a['sha256'] != b['sha256']
        assert [c['question'] for c in a['cases']] == [c['question'] for c in b['cases']]
        assert any(x['expected_rows'] != y['expected_rows'] for x,y in zip(a['cases'],b['cases']))


def test_nonvacuous_relationship_and_order_counterexamples(tmp_path):
    manifest = builder.build(tmp_path/'pack',11)
    for dataset in manifest['datasets']:
        cases = {c['id']:c for c in dataset['cases']}
        name = dataset['name']
        assert cases[f'{name}-14']['expected_rows']  # observed entities
        assert cases[f'{name}-15']['expected_rows']  # absent entities
        assert cases[f'{name}-20']['expected_rows'][0][0] > 0  # NULL relationship
    billing = manifest['datasets'][2]['cases']
    assert billing[27]['expected_rows'] == [[2]]  # reversed export->open does not convert
    assert billing[28]['expected_rows'] == [[2/12]]
    with closing(sqlite3.connect(tmp_path/'pack'/'support.db')) as db:
        correct = db.execute('SELECT COUNT(*) FROM ticket_tags x JOIN tags t ON t.namespace=x.namespace AND t.code=x.code').fetchone()[0]
        wrong = db.execute('SELECT COUNT(*) FROM ticket_tags x JOIN tags t ON t.code=x.code').fetchone()[0]
        assert correct == 4 and wrong > correct


def test_boundary_offsets_are_utc_not_lexical_dates():
    assert builder.utc_day('2026-03-31T23:30:00-02:00') == '2026-04-01'
    assert builder.utc_day('2026-04-01T00:30:00+02:00') == '2026-03-31'
    assert builder.utc_day('2026-03-10') == '2026-03-10'


def test_reference_or_data_corruption_is_detected(tmp_path):
    pack = tmp_path/'pack'
    builder.build(pack)
    path = pack/'manifest.json'
    manifest = json.loads(path.read_text())
    manifest['datasets'][0]['cases'][0]['expected_rows'] = [[99999]]
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='oracle disagreement'):
        evaluation.verify_suite(pack)
