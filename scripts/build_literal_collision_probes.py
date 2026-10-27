"""Contrastive development probes reusing frozen source-tuple fixtures, never planner SQL."""
import argparse
import json
from pathlib import Path

from build_corrected_query_matrix import FAMILIES, fixture


def build(output,seed=23):
    if output.exists():
        raise FileExistsError('Choose a new output directory; existing diagnostics are never overwritten')
    output.mkdir(parents=True)
    datasets=[]
    for family in FAMILIES:
        dataset=fixture(output,family,seed)
        name,table,_,_,_,_,_,_,_,amount,_=family
        original=dataset['cases']
        zero=original[0]
        status_zero=original[10]
        status_pass=original[11]
        if zero['expected_rows']==status_zero['expected_rows'] or status_zero['expected_rows'][0][0]==0 or status_pass['expected_rows'][0][0]==0:
            raise ValueError('Choose a seed with nonempty, distinct numeric-zero and text-zero reference results')
        probes=[
            (f'Count {table} with {amount} of zero',zero,'field_value_binding'),
            (f'Count {table} {amount} of zero',zero,'field_value_binding'),
            (f'Count {table} with zero {amount}',zero,'field_value_binding'),
            (f'Count {table} where status is zero.',status_zero,'text_punctuation'),
            (f'Count {table} where status is PASS.',status_pass,'text_punctuation'),
            (f'Count {table} where status is "PASS".',status_pass,'quoted_text_control'),
            (f'Count {table} where {amount} is zero?',zero,'numeric_punctuation_control'),
            (f'Count {table} where {amount} equals zero!',zero,'numeric_punctuation_control'),
        ]
        dataset['cases']=[dict(id=f'{name}-probe-{i:02d}',question=question,expected_outcome='query',
            reference_sql=reference['reference_sql'],expected_rows=reference['expected_rows'],
            ordered=False,complexity='simple',tags=['contrastive_probe',tag]) for i,(question,reference,tag) in enumerate(probes,1)]
        datasets.append(dataset)
    manifest=dict(version='independent-v1',suite_name='literal-collision-probes-v1',seed=seed,
        exposure='development-exposed-neighboring-query-diagnostics',external_blind=False,
        oracle='Reuses independently computed Python source-tuple targets from the corrected-query builder for equivalent phrasings; SQL cross-check required before scoring.',
        design='Eight contrastive templates per renamed family. Database contents intentionally match the corresponding matrix seed, not new independent data.',datasets=datasets)
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--seed',type=int,default=23)
    args=parser.parse_args()
    result=build(args.output,args.seed)
    print(f"Created {sum(len(d['cases']) for d in result['datasets'])} contrastive cases, seed {args.seed}")
