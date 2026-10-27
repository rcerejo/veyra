"""Synthetic two-source preparation and context-delivery honesty; no final fixtures."""
from contextlib import closing
import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest

ROOT=Path(__file__).resolve().parents[2]


def load(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/file)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder=load('joined_demo_builder','build_joined_context_demo.py')
evaluation=load('joined_demo_evaluator','run_independent_evaluation.py')


def test_sources_combined_snapshot_and_python_oracles(tmp_path):
    pack=tmp_path/'demo'
    builder.build(pack)
    manifest=evaluation.verify_suite(pack)
    cases=manifest['datasets'][0]['cases']
    assert len(cases)==26
    assert sum(c['expected_outcome']=='query' for c in cases)==15
    assert sum(c['expected_outcome']=='clarification' for c in cases)==9
    assert sum(c['expected_outcome']=='refusal' for c in cases)==2
    provenance=json.loads((pack/'provenance.json').read_text())
    assert provenance['source_files_unchanged']
    assert not provenance['federation'] and not provenance['context_automatically_loaded']
    for name,digest in provenance['source_hashes'].items():
        assert builder.digest(pack/name)==digest
    combined=builder.read_tables(pack/'joined.db',provenance['row_counts'])
    sources={**builder.read_tables(pack/'crm.db',('accounts','people','memberships')),
             **builder.read_tables(pack/'product.db',('activity_log','invoices'))}
    assert combined==sources


def test_cross_source_keys_exist_only_in_validated_combined_snapshot(tmp_path):
    pack=tmp_path/'demo'
    builder.build(pack)
    with closing(sqlite3.connect(pack/'product.db')) as db:
        assert not db.execute('PRAGMA foreign_key_list(activity_log)').fetchall()
    with closing(sqlite3.connect(pack/'joined.db')) as db:
        assert len(db.execute('PRAGMA foreign_key_list(activity_log)').fetchall())==2
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'


def test_snapshots_are_reproducible_and_never_overwritten(tmp_path):
    first=builder.build(tmp_path/'first')
    assert builder.build(tmp_path/'second')==first
    assert (tmp_path/'first'/'dataset-context.md').read_bytes()==(tmp_path/'second'/'dataset-context.md').read_bytes()
    with pytest.raises(FileExistsError):
        builder.build(tmp_path/'first')


def test_counterexamples_make_wrong_time_and_identity_joins_detectable(tmp_path):
    pack=tmp_path/'demo'
    builder.build(pack)
    with closing(sqlite3.connect(pack/'joined.db')) as db:
        utc=db.execute("SELECT COUNT(*) FROM activity_log WHERE action='app_open' AND julianday(occurred_at)>=julianday('2026-03-01') AND julianday(occurred_at)<julianday('2026-04-01')").fetchone()[0]
        lexical=db.execute("SELECT COUNT(*) FROM activity_log WHERE action='app_open' AND occurred_at>='2026-03-01' AND occurred_at<'2026-04-01'").fetchone()[0]
        assert utc!=lexical
        source_plan=db.execute('SELECT a.plan,COUNT(*) FROM activity_log e JOIN accounts a ON a.account_id=e.workspace_id GROUP BY a.plan').fetchall()
        membership_plan=db.execute('SELECT a.plan,COUNT(*) FROM activity_log e JOIN memberships m ON m.person_id=e.actor_id JOIN accounts a ON a.account_id=m.account_id GROUP BY a.plan').fetchall()
        assert source_plan!=membership_plan
        assert db.execute('SELECT COUNT(*) FROM accounts a WHERE NOT EXISTS(SELECT 1 FROM activity_log e WHERE e.workspace_id=a.account_id)').fetchone()[0]>0


def test_context_is_complete_but_never_advertised_as_automatic():
    context=builder.context_markdown()
    for section in ('## 1.','## 2.','## 3.','## 4.','## 5.','## 6.'):
        assert section in context
    assert 'not automatically loaded' in context
    assert 'Retention: undefined' in context
    assert 'workspace_id' in context and 'actor_id' in context
