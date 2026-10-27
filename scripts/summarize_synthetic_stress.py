"""Summarize explicit development packs/reports; no generation or production mutations."""
import argparse
from collections import Counter
import json
from pathlib import Path

from run_independent_evaluation import (
    SQLiteAdapter, SchemaCatalog, sha, validate_sql, verify_suite,
)


def summarize(packs, reports):
    if len(packs) != len(reports) or not packs:
        raise ValueError('Supply paired development packs and reports')
    variants = []
    all_signatures = []
    production_hashes = None
    for pack, path in zip(packs,reports):
        manifest = verify_suite(pack)
        if manifest.get('suite_name') != 'synthetic-stress-v1':
            raise ValueError('Only explicit synthetic development stress packs are supported')
        report = json.loads(path.read_text(encoding='utf-8'))
        if report['manifest_sha256'] != sha(pack/'manifest.json'):
            raise ValueError('Report/pack fingerprint mismatch')
        if report['partial'] or report['system_order'] != ['deterministic']:
            raise ValueError('Use complete deterministic reports')
        hashes = {k:v for k,v in report['code']['files'].items() if k.replace('\\','/').startswith('backend/app/')}
        if production_hashes is not None and production_hashes != hashes:
            raise ValueError('Production code differs between variant evaluations')
        production_hashes = hashes
        system = report['systems'][0]
        references = {c['id']:(d,c) for d in manifest['datasets'] for c in d['cases']}
        if len(system['cases']) != len(references) or {c['id'] for c in system['cases']} != set(references):
            raise ValueError('Case denominator mismatch')
        counts = Counter()
        failures = []
        signatures = {}
        tags = {}
        for case in system['cases']:
            dataset,reference = references[case['id']]
            if case['question'] != reference['question'] or case['expected_outcome'] != reference['expected_outcome']:
                raise ValueError('Case question/label mismatch')
            signatures[case['id']] = (case['outcome'],case['correct'])
            status = ('correct' if case['correct'] else 'wrong_executed_answer' if case['outcome']=='query'
                      else 'unnecessary_clarification' if case['outcome']=='clarification' and case['expected_outcome']=='query'
                      else 'other_failure')
            counts[status] += 1
            for tag in case['tags']:
                tags.setdefault(tag,Counter())[status] += 1
            if case['correct']:
                continue
            detail = dict(id=case['id'],question=case['question'],status=status,tags=case['tags'],
                complexity=case['complexity'],message=case.get('message'),generated_sql=case.get('sql'),
                reference_sql=reference['reference_sql'],expected_rows=reference['expected_rows'])
            if case['outcome']=='query':
                adapter = SQLiteAdapter(pack/dataset['file'])
                catalog = SchemaCatalog(adapter.discover_schema())
                sql = validate_sql(case['sql'],catalog)
                _,rows,truncated = adapter.execute_readonly(sql,5000,8)
                detail.update(actual_rows=[list(r.values()) for r in rows],truncated=truncated)
            failures.append(detail)
        all_signatures.append(signatures)
        variants.append(dict(seed=manifest['seed'],pack=str(pack),report=str(path),
            manifest_sha256=sha(pack/'manifest.json'),report_sha256=sha(path),summary=system['summary'],
            outcome_counts=dict(counts),by_schema=system['by_schema'],by_complexity=system['by_complexity'],
            overlapping_tag_counts={k:dict(v) for k,v in sorted(tags.items())},failures=failures))
    first = all_signatures[0]
    if any(set(s)!=set(first) for s in all_signatures):
        raise ValueError('Paired variants have different case IDs')
    changed = [key for key in first if any(s[key]!=first[key] for s in all_signatures[1:])]
    return dict(role='development-exposed',held_out=False,external_blind=False,
        methodology='Python source-record oracles cross-checked against SQL before scoring; no independent human verification claimed.',
        variants=variants,data_variant_outcome_changes=changed,
        aggregate_counts=dict(sum((Counter(v['outcome_counts']) for v in variants),Counter())),
        production_code_identical_between_variants=True,
        notes=['Paired variants repeat questions; do not treat executions as independent linguistic cases.',
               'Tag categories overlap and are capability labels, not proven root causes.',
               'Only deterministic generation was measured; no Ollama or hybrid accuracy claim.',
               'Reserved final artifacts are not accessed by this script.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packs',type=Path,nargs='+',required=True)
    parser.add_argument('--reports',type=Path,nargs='+',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Choose a new output filename')
    result = summarize(args.packs,args.reports)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as handle:
        json.dump(result,handle,indent=2)
    print(json.dumps(dict(aggregate_counts=result['aggregate_counts'],
        data_variant_outcome_changes=result['data_variant_outcome_changes']),indent=2))
