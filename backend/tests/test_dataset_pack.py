import asyncio
import json
from pathlib import Path

import pytest

from app.ai.examples import retrieve_examples

ROOT=Path(__file__).resolve().parents[2]


@pytest.fixture
def generated_pack(tmp_path,monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))
    from scripts.generate_dataset import generate
    from scripts.generate_test_datasets import build_pack
    source=tmp_path/'source.db'
    generate(source,20)
    original=source.read_bytes()
    pack=tmp_path/'pack'
    manifest=build_pack(pack,source)
    assert source.read_bytes()==original
    return pack,source,manifest


def test_reference_answers_and_renamed_database_are_consistent(generated_pack):
    from scripts.evaluate_dataset_pack import verify_references
    from scripts.generate_test_datasets import build_pack
    pack,source,manifest=generated_pack
    assert len(manifest['datasets'])==5
    assert sum(len(d['cases']) for d in manifest['datasets'])==32
    verify_references(pack,manifest)
    with pytest.raises(ValueError,match='never overwritten'):
        build_pack(pack,source)


def test_unfamiliar_schema_regressions_and_clarification_guards(generated_pack):
    from scripts.evaluate_dataset_pack import evaluate_pack
    report=asyncio.run(evaluate_pack(generated_pack[0]))
    assert report['correct']==report['total']==32
    assert any(row['outcome']=='clarification' for row in report['cases'])


def test_learning_splits_exclude_evaluation_families(generated_pack):
    from scripts.prepare_sql_learning import prepare
    pack,_,_=generated_pack
    output=pack/'learning'
    report=prepare(pack,output)
    assert report['training_rows']==33
    assert report['unique_training_queries']==11
    assert set(report['train_families']).isdisjoint(report['heldout_families'])
    records=[json.loads(line) for line in (output/'fewshot.jsonl').read_text().splitlines()]
    assert {r['family'] for r in records}=={'commerce','support'}
    selected=retrieve_examples(output/'fewshot.jsonl','How many accounts are there?')
    assert len(selected.splitlines())<=2
    assert 'CREATE TABLE accounts' not in selected


def test_example_reader_ignores_malformed_records(tmp_path):
    path=tmp_path/'examples.jsonl'
    path.write_text('not json\n[]\n{"question":"broken"}\n')
    assert retrieve_examples(path,'Count records')==''
