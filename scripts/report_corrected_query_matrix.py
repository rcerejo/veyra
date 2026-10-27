"""Audit the explicit development matrix; no planner changes, generation or final labels."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from run_independent_evaluation import SQLiteAdapter, SchemaCatalog, sha, summarize, validate_sql, verify_suite

GROUPS=('corrected_control','nearby_wording','contrastive_probe')


def metrics(cases):
    return dict(summarize(cases),wrong_executed_answers=sum(c['outcome']=='query' and not c['correct'] for c in cases))


def report(packs,paths):
    if not packs or len(packs)!=len(paths):
        raise ValueError('Supply paired development packs/reports')
    variants=[]
    signatures=[]
    fingerprints=None
    for pack,path in zip(packs,paths):
        manifest=verify_suite(pack)
        if manifest.get('suite_name') not in ('corrected-query-matrix-v1','literal-collision-probes-v1'):
            raise ValueError('Only the explicit development corrected-query matrix is supported')
        measured=json.loads(path.read_text(encoding='utf-8'))
        if measured['manifest_sha256']!=sha(pack/'manifest.json') or measured['partial'] or measured['system_order']!=['deterministic']:
            raise ValueError('Use complete deterministic runs matching their fixture snapshots')
        production={k:v for k,v in measured['code']['files'].items() if k.replace('\\','/').startswith('backend/app/')}
        if fingerprints is not None and fingerprints!=production:
            raise ValueError('Variants use different production code')
        fingerprints=production
        references={c['id']:(d,c) for d in manifest['datasets'] for c in d['cases']}
        cases=measured['systems'][0]['cases']
        if len(cases)!=len(references) or {c['id'] for c in cases}!=set(references):
            raise ValueError('Case denominator mismatch')
        details=[]
        signatures.append({c['id']:(c['correct'],c['outcome']) for c in cases})
        for case in cases:
            dataset,reference=references[case['id']]
            if reference['question']!=case['question'] or reference['expected_outcome']!=case['expected_outcome']:
                raise ValueError('Question or reference label mismatch')
            detail=dict(case,reference_sql=reference['reference_sql'],expected_rows=reference['expected_rows'])
            if case['outcome']=='query':
                adapter=SQLiteAdapter(pack/dataset['file'])
                catalog=SchemaCatalog(adapter.discover_schema())
                sql=validate_sql(case['sql'],catalog)
                _,rows,truncated=adapter.execute_readonly(sql,5000,8)
                detail.update(actual_rows=[list(r.values()) for r in rows],truncated=truncated)
            details.append(detail)
        variants.append(dict(seed=manifest['seed'],manifest_sha256=sha(pack/'manifest.json'),report_sha256=sha(path),
            database_sha256={d['name']:d['sha256'] for d in manifest['datasets']},
            summary=metrics(cases),by_schema=measured['systems'][0]['by_schema'],
            groups={tag:metrics([c for c in cases if tag in c['tags']]) for tag in GROUPS},
            by_complexity=measured['systems'][0]['by_complexity'],failures=[c for c in details if not c['correct']],
            cases=details))
    if any(set(s)!=set(signatures[0]) for s in signatures):
        raise ValueError('Paired variants have different case IDs')
    changed=[key for key in signatures[0] if any(s[key]!=signatures[0][key] for s in signatures[1:])]
    all_cases=[c for v in variants for c in v['cases']]
    failures=Counter(c['id'].split('-')[-1] for c in all_cases if not c['correct'])
    return dict(role='development-exposed',held_out=False,external_blind=False,variants=variants,
        production_sha256=hashlib.sha256(json.dumps(fingerprints,sort_keys=True).encode()).hexdigest(),
        aggregate=metrics(all_cases),groups={tag:metrics([c for c in all_cases if tag in c['tags']]) for tag in GROUPS},
        failed_template_counts=dict(sorted(failures.items())),data_variant_outcome_changes=changed,
        notes=['Four renamed role/type families repeat operation templates; paired seeds change data, not language diversity. Contrastive probes deliberately reuse matrix database contents.',
               'Python source-tuple oracles were checked against SQL before scoring; no independent human reference review claimed.',
               'Unsupported but fully specified operations are labeled query and count as withheld failures, not correct clarifications.',
               'Corrected controls and nearby phrasings are different case groups, not a before/after accuracy improvement.',
               'No model-only/hybrid measurements, training or held-out generalization claims.'])


def combine_audits(paths):
    if not paths:
        raise ValueError('Choose development audit reports')
    audits=[json.loads(p.read_text(encoding='utf-8')) for p in paths]
    if any(a.get('role')!='development-exposed' or a.get('held_out') is not False or not a.get('production_sha256') for a in audits):
        raise ValueError('Only fingerprinted development audit reports are supported')
    if len({a['production_sha256'] for a in audits})!=1:
        raise ValueError('Production code differs between audit groups')
    seen=set()
    cases=[]
    databases=set()
    for audit in audits:
        for variant in audit['variants']:
            databases.update(variant['database_sha256'].values())
            for case in variant['cases']:
                identity=(variant['seed'],case['id'])
                if identity in seen:
                    raise ValueError('Overlapping case executions would double-count evidence')
                seen.add(identity)
                cases.append(case)
    return dict(role='development-exposed',held_out=False,external_blind=False,
        production_sha256=audits[0]['production_sha256'],source_audits={str(p):sha(p) for p in paths},
        question_formulations=len({c['question'] for c in cases}),distinct_database_contents=len(databases),
        aggregate=metrics(cases),groups={tag:metrics([c for c in cases if tag in c['tags']]) for tag in GROUPS},
        wrong_answer_groups=dict(Counter('field_value_binding' if 'field_value_binding' in c['tags'] else 'text_punctuation' if 'text_punctuation' in c['tags'] else 'other'
            for c in cases if c['outcome']=='query' and not c['correct'])),
        notes=['Counts combine complementary case groups from the same production version, not before/after accuracy.',
               'Templates and data are reused; case executions are not independent language examples.',
               'See source audits for generated/reference SQL, expected/actual rows and every withheld request.'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packs',type=Path,nargs='+')
    parser.add_argument('--reports',type=Path,nargs='+')
    parser.add_argument('--combine-audits',type=Path,nargs='+')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        parser.error('Choose a new output filename')
    if args.combine_audits:
        if args.packs or args.reports:
            parser.error('Choose audit combination or pack/report analysis, not both')
        result=combine_audits(args.combine_audits)
    else:
        if not args.packs or not args.reports:
            parser.error('Supply paired --packs and --reports')
        result=report(args.packs,args.reports)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2)
    print(json.dumps(dict(aggregate=result['aggregate'],groups=result['groups'],
                         data_variant_outcome_changes=result.get('data_variant_outcome_changes')),indent=2))
