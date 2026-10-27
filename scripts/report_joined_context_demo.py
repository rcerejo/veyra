"""Export context-delivery provenance and evidence from a joined synthetic diagnostic run."""
import argparse
import json
from pathlib import Path

from run_independent_evaluation import SQLiteAdapter, SchemaCatalog, sha, summarize, validate_sql, verify_suite


def report(pack, path):
    manifest=verify_suite(pack)
    if manifest.get('suite_name')!='joined-context-demo-v1':
        raise ValueError('Use the explicit development joined-context demo only')
    provenance=json.loads((pack/'provenance.json').read_text(encoding='utf-8'))
    if provenance['context_sha256']!=sha(pack/'dataset-context.md') or provenance['manifest_sha256']!=sha(pack/'manifest.json'):
        raise ValueError('Context or manifest fingerprint mismatch')
    if any(sha(pack/name)!=value for name,value in provenance['source_hashes'].items()):
        raise ValueError('Source snapshot fingerprint mismatch')
    measured=json.loads(path.read_text(encoding='utf-8'))
    if measured['manifest_sha256']!=sha(pack/'manifest.json') or measured['partial'] or measured['system_order']!=['deterministic']:
        raise ValueError('Use a complete deterministic report matching the demo pack')
    references={c['id']:c for c in manifest['datasets'][0]['cases']}
    actual=measured['systems'][0]['cases']
    if len(actual)!=len(references) or {c['id'] for c in actual}!=set(references):
        raise ValueError('Diagnostic case denominator mismatch')
    adapter=SQLiteAdapter(pack/'joined.db')
    catalog=SchemaCatalog(adapter.discover_schema())
    cases=[]
    for case in actual:
        reference=references[case['id']]
        if case['question']!=reference['question']:
            raise ValueError('Question mismatch')
        detail=dict(case,wording=reference['wording'],pair_id=reference.get('pair_id'),
            reference_sql=reference['reference_sql'],expected_rows=reference['expected_rows'])
        if case['outcome']=='query':
            sql=validate_sql(case['sql'],catalog)
            _,rows,truncated=adapter.execute_readonly(sql,5000,8)
            detail.update(actual_rows=[list(r.values()) for r in rows],truncated=truncated)
        cases.append(detail)
    def metrics(group):
        return dict(summarize(group),wrong_executed_answers=sum(c['outcome']=='query' and not c['correct'] for c in group))
    return dict(role='development',held_out=False,external_blind=False,provenance=provenance,
        report_sha256=sha(path),context_automatically_loaded=False,federated_execution=False,
        delivery='Only NL question and discovered schema/sample values enter QueryService. Explicit requests were manually authored from the recorded context; no reference SQL or expected rows supplied.',
        summary=metrics(cases),by_wording={mode:metrics([c for c in cases if c['wording']==mode]) for mode in ('raw','explicit','refusal')},
        cross_source=metrics([c for c in cases if 'cross_source_join' in c['tags']]),cases=cases,
        notes=['Raw and explicit questions provide different information and have different answerability labels. Do not present their scores as an automated context-ingestion improvement.',
               'References use independently computed Python collection/UTC results, computationally checked against SQL; no independent human review claimed.',
               'The combined database is a prepared snapshot. Two-file federation and automatic context mapping remain unimplemented.',
               'Current selected workspace and source snapshots are not changed by evaluation.'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        parser.error('Choose a new output filename')
    result=report(args.pack,args.report)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as handle:
        json.dump(result,handle,indent=2)
    print(json.dumps(result['by_wording'],indent=2))
