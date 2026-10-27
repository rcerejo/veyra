"""Compare frozen, development-exposed matrix audits by seed and case ID."""
import argparse
import json
from pathlib import Path


def compare(before_paths,after_paths):
    def collect(paths):
        cases={}
        manifests={}
        for path in paths:
            audit=json.loads(path.read_text(encoding='utf-8'))
            if audit.get('role')!='development-exposed' or audit.get('held_out') is not False:
                raise ValueError('Only development audits are accepted')
            for variant in audit['variants']:
                for case in variant['cases']:
                    key=(variant['seed'],case['id'])
                    if key in cases:
                        raise ValueError('Duplicate execution')
                    cases[key]=case
                    manifests[key]=variant['manifest_sha256']
        return cases,manifests
    before,bm=collect(before_paths)
    after,am=collect(after_paths)
    if bm!=am or not before:
        raise ValueError('Frozen denominators/fingerprints differ')
    fixed=[]
    regressed=[]
    for key,old in before.items():
        new=after[key]
        if any(old[k]!=new[k] for k in ('question','expected_outcome','reference_sql','expected_rows')):
            raise ValueError('Question or oracle changed')
        if not old['correct'] and new['correct']:
            fixed.append(dict(seed=key[0],id=key[1],previous_outcome=old['outcome']))
        if old['correct'] and not new['correct']:
            regressed.append(dict(seed=key[0],id=key[1]))
    return dict(role='development-exposed',held_out=False,total=len(before),fixed=fixed,regressed=regressed,
                fixed_count=len(fixed),regressed_count=len(regressed),
                previously_wrong_fixed=sum(c['previous_outcome']=='query' for c in fixed),
                previously_withheld_fixed=sum(c['previous_outcome']=='clarification' for c in fixed))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before',type=Path,nargs='+',required=True)
    parser.add_argument('--after',type=Path,nargs='+',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=compare(args.before,args.after)
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k not in ('fixed','regressed')},indent=2))
