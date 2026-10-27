"""Manual capability labels for the 42 v1 development withholdings; no final artifacts."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FAMILIES={
    'bounded_fk_existence':['education-05','education-20','education-21','logistics-05','logistics-21','logistics-22','collaboration-05','collaboration-21','collaboration-22'],
    'advanced_existence':['education-26','education-30','logistics-25','logistics-26','collaboration-25'],
    'ordered_funnels_ratios':['education-27','education-28','logistics-27','logistics-28','collaboration-26','collaboration-27','collaboration-28'],
    'distinct_activity_identity':['education-17','logistics-16','collaboration-15','collaboration-16','collaboration-19','collaboration-29'],
    'event_catalog_fact_grounding':['collaboration-11','collaboration-12','collaboration-13','collaboration-17','collaboration-30'],
    'ranking':['education-24','logistics-24','collaboration-24'],
    'grouped_relationship_having':['education-25','logistics-23','collaboration-23'],
    'parallel_join_aliases':['logistics-19'],
    'related_timestamp_role':['logistics-29'],
    'measure_word_grounding':['logistics-09'],
    'grain_qualifier_interpretation':['collaboration-20'],
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize(before_path,after_path):
    b=json.loads(before_path.read_text(encoding='utf-8'))
    a=json.loads(after_path.read_text(encoding='utf-8'))
    if b['manifest_sha256']!=a['manifest_sha256'] or b['partial'] or a['partial']:
        raise ValueError('Complete reports must use the same frozen development manifest')
    before=next(s for s in b['systems'] if s['system']=='deterministic')
    after=next(s for s in a['systems'] if s['system']=='deterministic')
    old={c['id']:c for c in before['cases']}
    new={c['id']:c for c in after['cases']}
    assigned=[key for keys in FAMILIES.values() for key in keys]
    failed={key for key,c in old.items() if not c['correct']}
    if set(old)!=set(new) or len(old)!=108 or len(assigned)!=len(set(assigned)) or set(assigned)!=failed:
        raise ValueError('Capability labels must exactly partition this 42-case development baseline')
    families=[]
    for name,keys in FAMILIES.items():
        families.append(dict(name=name,before=len(keys),fixed=[key for key in keys if new[key]['correct']],
            remaining=[key for key in keys if not new[key]['correct']]))
    def metrics(system):
        summary=dict(system['summary'])
        summary['wrong_executed_answers']=sum(c['outcome']=='query' and not c['correct'] for c in system['cases'])
        return summary
    return dict(role='development-exposed',held_out=False,baseline_sha256=digest(before_path),
        current_sha256=digest(after_path),manifest_sha256=b['manifest_sha256'],before=metrics(before),after=metrics(after),
        families=families,previous_pass_regressions=[key for key in old if old[key]['correct'] and not new[key]['correct']],
        notes=['Primary capability labels are manual, mutually exclusive, and not guaranteed single-cause fixes.',
               'Advanced existence comprises three temporal cases, one compound existence case, and one composite non-direct-FK correlation case.',
               'No reserved final artifact or its construction code is read or executed by this analysis.'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before',type=Path,default=ROOT/'logs/compositional-v1-development-verified.json')
    parser.add_argument('--after',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        parser.error('Choose a new report filename')
    report=summarize(args.before,args.after)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as handle:
        json.dump(report,handle,indent=2)
    print(json.dumps([dict(name=f['name'],before=f['before'],fixed=len(f['fixed']),remaining=len(f['remaining'])) for f in report['families']],indent=2))
