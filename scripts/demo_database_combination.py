"""Exercise upload -> inspect -> combine -> review -> activate -> NL join via real API handlers.

Runs an isolated in-process development app, never the user's running server/workspace.
Uses only the previously authored synthetic Beacon sources; no final evaluation artifacts.
"""
import argparse
from collections import Counter, defaultdict
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))


def run(output):
    if output.exists():
        raise FileExistsError('Choose a new demo directory')
    output=output.resolve()
    output.mkdir(parents=True)
    os.environ.update(VEYRA_DATABASE_PATH=str(output/'default.db'),VEYRA_ENVIRONMENT='development',
                      VEYRA_GATEWAY_API_KEY='',VEYRA_ALLOWED_HOSTS='["testserver","localhost"]',VEYRA_PREFER_MODEL_SQL='false')
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.config import get_settings
    from app.database.combine import digest
    from run_independent_evaluation import rows_equal
    from build_joined_context_demo import ACCOUNTS, ACTIVITY, INVOICES
    get_settings.cache_clear()
    source_pack=ROOT/'datasets/test-packs/joined-context-v1-reviewed'
    before={name:digest(source_pack/name) for name in ('crm.db','product.db')}
    with TestClient(app) as client:
        sources=[]
        for alias in ('crm','product'):
            response=client.post('/api/databases/upload',params={'filename':alias+'.db'},
                                 content=(source_pack/(alias+'.db')).read_bytes(),headers={'Content-Type':'application/octet-stream'})
            response.raise_for_status()
            sources.append(dict(alias=alias,name=response.json()['name']))
            client.get('/api/databases/schema',params={'name':response.json()['name']}).raise_for_status()
        previous=client.get('/api/databases').json()['databases']
        active_before=next(d['name'] for d in previous if d['active'])
        relationship=lambda table,col,parent,key:dict(child_source='product',child_table=table,child_columns=[col],parent_source='crm',parent_table=parent,parent_columns=[key])
        configuration=dict(name='beacon-demo',sources=sources,relationships=[
            relationship('activity_log','actor_id','people','person_id'),
            relationship('activity_log','workspace_id','accounts','account_id'),
            relationship('invoices','workspace_id','accounts','account_id')])
        created=client.post('/api/databases/combine',json=configuration)
        created.raise_for_status()
        result=created.json()
        assert not result['database']['active']
        assert next(d['name'] for d in client.get('/api/databases').json()['databases'] if d['active'])==active_before
        client.get('/api/databases/provenance',params={'name':result['database']['name']}).raise_for_status()
        client.post('/api/databases/activate',json={'name':result['database']['name']}).raise_for_status()
        plans={a[0]:a[1] for a in ACCOUNTS}
        activity=Counter(plans[e[2]] for e in ACTIVITY if e[2] in plans)
        revenue=defaultdict(int)
        for i in INVOICES:
            if i[1] in plans and i[3]=='paid' and i[2] is not None:
                revenue[plans[i[1]]]+=i[2]
        questions=[
            ('Count product__activity_log by crm__accounts plan',[[k,v] for k,v in sorted(activity.items())]),
            ('Total paid product__invoices usd cents by crm__accounts plan',[[k,v] for k,v in sorted(revenue.items())]),
            ('List crm__accounts without product__activity_log',[list(a) for a in ACCOUNTS if not any(e[2]==a[0] for e in ACTIVITY)]),
            ('List crm__accounts with no paid product__invoices',[list(a) for a in ACCOUNTS if not any(i[1]==a[0] and i[3]=='paid' for i in INVOICES)]),
        ]
        answers=[]
        for question,expected in questions:
            response=client.post('/api/query',json={'question':question})
            response.raise_for_status()
            answer=response.json()
            correct='rows' in answer and rows_equal([list(r.values()) for r in answer['rows']],expected)
            answers.append(dict(question=question,expected_rows=expected,correct=correct,response=answer))
    assert before=={name:digest(source_pack/name) for name in before}
    report=dict(role='development',held_out=False,isolated_in_process_api=True,running_workspace_unchanged=True,
        original_source_files_unchanged=True,source_sha256=before,configuration=configuration,created=result,queries=answers,
        correct=sum(a['correct'] for a in answers),total=len(answers),
        note='Four selected cross-source development queries, not an NL accuracy benchmark or browser interaction test.')
    (output/'api-walkthrough.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(dict(correct=report['correct'],total=report['total'],dataset=result['database']['name']),indent=2))
    if not all(a['correct'] for a in answers):
        raise AssertionError('A walkthrough result differed from its Python source-record reference; see api-walkthrough.json')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    run(args.output)
