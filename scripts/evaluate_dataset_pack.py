"""Evaluate unfamiliar schemas without silently training on their reference answers."""
import argparse
import asyncio
from collections import Counter
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))

from app.core.config import Settings
from app.database.sqlite import SQLiteAdapter
from app.query_engine.service import QueryService
from app.schemas.query import QueryRequest, QueryResponse, ClarificationResponse


def normalized(rows):
    return Counter(tuple(round(value,7) if isinstance(value,float) else value for value in row) for row in rows)


def verify_references(pack,manifest):
    for dataset in manifest['datasets']:
        adapter=SQLiteAdapter(pack/dataset['file'])
        for item in dataset['cases']:
            if item['reference_sql']:
                _,rows,truncated=adapter.execute_readonly(item['reference_sql'],100000,8)
                if truncated or normalized([list(row.values()) for row in rows])!=normalized(item['expected_rows']):
                    raise ValueError(f"Reference disagrees with independent answer: {dataset['name']}: {item['question']}")


async def evaluate_pack(pack,with_model=False,model=None,family=None,limit=None,examples=None):
    manifest=json.loads((pack/'manifest.json').read_text(encoding='utf-8'))
    if family and family not in {d['name'] for d in manifest['datasets']}:
        raise ValueError('Unknown dataset family')
    if limit is not None and limit<1:
        raise ValueError('Limit must be positive')
    verify_references(pack,manifest)
    results=[]
    for dataset in manifest['datasets']:
        if family and dataset['name']!=family:
            continue
        settings=Settings(database_path=pack/dataset['file'],prefer_model_sql=with_model,sql_examples_path=examples,**({'ollama_model':model} if model else {}))
        service=QueryService(settings)
        service.adapter=SQLiteAdapter(pack/dataset['file'])
        if not with_model:
            async def offline():
                return False
            service.ollama.available=offline
        for item in dataset['cases']:
            if limit is not None and len(results)>=limit:
                break
            started=time.perf_counter()
            result={'dataset':dataset['name'],'question':item['question'],'correct':False,'expects_clarification':item['expect_clarification']}
            try:
                answer=await service.ask(QueryRequest(question=item['question']))
                if isinstance(answer,ClarificationResponse):
                    result.update(correct=item['expect_clarification'],outcome='clarification',message=answer.message)
                elif isinstance(answer,QueryResponse):
                    correct=not item['expect_clarification'] and not answer.metadata.truncated and normalized([list(row.values()) for row in answer.rows])==normalized(item['expected_rows'])
                    result.update(correct=correct,outcome='query',sql=answer.sql,source=answer.metadata.source,model=answer.metadata.model)
            except Exception as exc:
                result.update(outcome='error',error=str(exc))
            result['latency_ms']=round((time.perf_counter()-started)*1000,2)
            results.append(result)
    return {'mode':'model_preferred' if with_model else 'offline','model':model if with_model else None,'examples_enabled':examples is not None,'references_verified':True,'correct':sum(row['correct'] for row in results),'total':len(results),'datasets':[{'name':d['name'],'correct':sum(row['correct'] for row in results if row['dataset']==d['name']),'total':sum(row['dataset']==d['name'] for row in results)} for d in manifest['datasets'] if any(row['dataset']==d['name'] for row in results)],'cases':results,'notes':['This is a small synthetic diagnostic suite, not evidence of universal schema support.','Messy/ambiguous cases require clarification; successful SQL execution alone is not correctness.','Model-preferred runs retain mandatory clarification guards and fall back to offline SQL if the model is unavailable; inspect each source field.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack',type=Path,default=ROOT/'datasets/test-packs/v1')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--with-model',action='store_true')
    parser.add_argument('--model')
    parser.add_argument('--family')
    parser.add_argument('--limit',type=int)
    parser.add_argument('--examples',type=Path)
    args=parser.parse_args()
    if args.output.exists():
        parser.error('Choose a new report filename; existing reports are never overwritten')
    report=asyncio.run(evaluate_pack(args.pack,args.with_model,args.model,args.family,args.limit,args.examples))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({key:report[key] for key in ('mode','correct','total','datasets')},indent=2))


if __name__=='__main__':
    main()
