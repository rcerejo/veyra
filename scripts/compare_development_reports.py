"""Compare the unchanged v1 development denominator and export actual plan examples."""
import argparse
import asyncio
import json
from pathlib import Path

from run_independent_evaluation import ROOT,sha
from app.core.config import Settings
from app.database.sqlite import SQLiteAdapter
from app.query_engine.service import QueryService
from app.schemas.query import QueryRequest,QueryResponse


async def compare(before_path,after_path,pack,example_ids=None):
    before=json.loads(before_path.read_text(encoding='utf-8'))
    after=json.loads(after_path.read_text(encoding='utf-8'))
    manifest=pack/'manifest.json'
    if before['manifest_sha256']!=after['manifest_sha256'] or sha(manifest)!=before['manifest_sha256']:
        raise ValueError('Different suite snapshots cannot be presented as a baseline improvement')
    b=next(s for s in before['systems'] if s['system']=='deterministic')
    a=next(s for s in after['systems'] if s['system']=='deterministic')
    old={c['id']:c for c in b['cases']}
    new={c['id']:c for c in a['cases']}
    if set(old)!=set(new) or len(old)!=108:
        raise ValueError('Both reports must cover the same complete 108 cases')
    fixed=[key for key in old if not old[key]['correct'] and new[key]['correct']]
    regressed=[key for key in old if old[key]['correct'] and not new[key]['correct']]
    examples=[]
    example_ids=example_ids or ('education-29','logistics-18','collaboration-09')
    if not set(example_ids)<=set(new):
        raise ValueError('Example IDs must exist in the development suite')
    for key in example_ids:
        case=new[key]
        adapter=SQLiteAdapter(pack/f'{case["dataset"]}.db')
        service=QueryService(Settings(database_path=adapter.path,prefer_model_sql=False,sql_examples_path=None))
        service.adapter=adapter
        async def offline():
            return False
        service.ollama.available=offline
        answer=await service.ask(QueryRequest(question=case['question']))
        if not isinstance(answer,QueryResponse):
            raise ValueError('Expected a verified development plan example')
        examples.append(dict(id=key,question=case['question'],before_sql=old[key].get('sql'),
            before_error=old[key].get('error'),after_plan=answer.plan.model_dump(),after_sql=answer.sql))
    return dict(role='development-exposed',held_out=False,baseline_sha256=sha(before_path),
        current_report_sha256=sha(after_path),manifest_sha256=sha(manifest),before=b['summary'],after=a['summary'],
        previous_failures_fixed=len(fixed),previous_passes_regressed=len(regressed),fixed_ids=fixed,regressed_ids=regressed,
        unchanged_passes=sum(old[k]['correct'] and new[k]['correct'] for k in old),
        unchanged_failures=sum(not old[k]['correct'] and not new[k]['correct'] for k in old),plan_examples=examples)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before',type=Path,default=ROOT/'logs/independent-v1-deterministic.json')
    parser.add_argument('--after',type=Path,required=True)
    parser.add_argument('--pack',type=Path,default=ROOT/'datasets/evaluation/independent-v1')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--example-ids',nargs='+')
    args=parser.parse_args()
    if args.output.exists():
        parser.error('Choose a new report filename')
    report=asyncio.run(compare(args.before,args.after,args.pack,args.example_ids))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as handle:
        json.dump(report,handle,indent=2)
    print(json.dumps({k:report[k] for k in ('previous_failures_fixed','previous_passes_regressed','unchanged_passes','unchanged_failures')},indent=2))
