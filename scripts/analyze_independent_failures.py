"""Evidence-based manual audit of the frozen v1 offline baseline; no generation changes."""
import argparse
from collections import Counter
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from run_independent_evaluation import ROOT, sha, verify_suite

CATEGORIES={
    1:'Incorrect schema or column identification',
    2:'Incorrect joins or table relationships',
    3:'Incorrect filtering or aggregation',
    4:'Incorrect date and time logic',
    5:'Incorrect interpretation of business metrics',
    6:'Ambiguous questions that should trigger clarification',
    7:'SQL generation or execution errors',
    8:'Evaluation or reference-answer issues',
}

# Primary labels partition failures. Secondary labels describe overlapping symptoms;
# neither these annotations nor this script are imported by application code.
ANNOTATIONS={}


def annotate(family, numbers, primary, evidence, secondary=(), certainty='observed'):
    for number in numbers:
        key=f'{family}-{number:02d}'
        if key in ANNOTATIONS:
            raise ValueError(f'Duplicate annotation: {key}')
        ANNOTATIONS[key]=dict(primary=primary,secondary=list(secondary),evidence=evidence,certainty=certainty)


annotate('education',[7],3,'Requested each-region grouping is absent; generated SQL returns one count.')
annotate('education',[9],3,'Generated AVG is rounded to two decimals although the reference/oracle retains precision.',[8])
annotate('education',[10],3,'Generated count omits the requested IS NULL predicate.')
annotate('education',[11,12,13],3,'Generated lookup omits the explicit state predicate. State is absent from categorical profiles.',[1])
annotate('education',[14,15,16,30],4,'Clarification says there is no date column although joined_on/viewed_on exists. Date recognizer excludes *_on.',[1])
annotate('education',[17],2,'Counts all learners without joining viewing/enrollment records, distinct users or daily grouping.',[1,3,4])
annotate('education',[18,22],7,'Implicit REFERENCES target produces target_column=None; join SQL calls identifier.replace on None.',[2])
annotate('education',[19],1,'Selects learners as measure table and asks which field to sum; minutes belongs to lesson_views.',[2])
annotate('education',[20],2,'Generated lookup omits the requested NOT EXISTS enrollment relationship.')
annotate('education',[21],2,'Clarifies a lexical table tie instead of planning the explicitly requested anti-join.')
annotate('education',[23],4,'Sums minutes across the entire table instead of grouping by day.',[3])
annotate('education',[24],3,'Returns enrollment rows without requested SUM, ranking, top-three limit or tie rule.',[1,2])
annotate('education',[25],2,'Lexical table tie prevents relationship query with distinct-course HAVING.',[3])
annotate('education',[26],4,'Counts every enrollment without checking view date >= enrollment date.',[2])
annotate('education',[27,28],5,'Explicit ordered funnel/denominator is not represented; output is a count or raw enrollment rows.',[2,3,4])
annotate('education',[29],3,'Generated lookup omits the score >= 50 predicate.')
annotate('education',[33],6,'Undefined best learner criterion is answered with raw learners rather than clarification.',[5])

annotate('logistics',[5],2,'Lexical table tie blocks distinct parcels participating in the checkpoint relationship.',[3])
annotate('logistics',[9],3,'Net charged cents is compiled as COUNT(*) instead of SUM(amount_cents).')
annotate('logistics',[10],3,'Generated count omits amount_cents < 0.')
annotate('logistics',[11,12,13],3,'Generated lookup omits the explicit stage predicate. Stage is absent from profiles.',[1])
annotate('logistics',[14,29],4,'Clarification rejects shipped_on as unrecognizable despite an explicit date request.',[1])
annotate('logistics',[15],4,'Daily grouping is omitted; generated SQL returns one parcel count.',[3])
annotate('logistics',[16],4,'Per-day grouping, delivered filter, distinctness and checkpoint table are absent.',[1,3])
annotate('logistics',[17,18,19,20],7,'Implicit REFERENCES target produces target_column=None; join SQL calls identifier.replace on None.',[2])
annotate('logistics',[21],2,'Generated lookup omits the NOT EXISTS delivered-checkpoint condition.',[3])
annotate('logistics',[22],2,'Lexical table tie prevents the requested no-charges anti-join.')
annotate('logistics',[23],2,'Counts all parcels instead of grouping related charges and applying HAVING COUNT(*) > 1.',[3])
annotate('logistics',[24],3,'Returns parcel rows without the requested weight projection, descending rank or top-three limit.')
annotate('logistics',[25],2,'Counts all parcels without the two required related-ledger EXISTS predicates.',[3])
annotate('logistics',[26],4,'Counts every parcel without checking delivery date >= shipping date.',[2])
annotate('logistics',[27,28],5,'Explicit ordered shipping/acceptance/delivery funnel is replaced by a count or raw rows.',[2,3,4])
annotate('logistics',[30],3,'Generated lookup omits weight_grams > 400.')
annotate('logistics',[31],7,'Ambiguous origin/destination zone request reaches the same implicit-FK None exception instead of clarification.',[2,6])
annotate('logistics',[34],6,'Undefined best depot criterion is answered with raw depots rather than clarification.',[5])

annotate('collaboration',[9],3,'AVG includes void invoices because the paid-state predicate is absent.',[1])
annotate('collaboration',[10],3,'Generated lookup omits the void-state predicate; state is absent from profiles.',[1])
annotate('collaboration',[11,12,13],2,'Normalized action labels require a catalog join, but generated SQL returns the entire audit log.',[1,3])
annotate('collaboration',[14],4,'Issued_on is not recognized as a date field.',[1])
annotate('collaboration',[15],1,'Lexical audit_log/people tie blocks an explicit audit-log activity request.',[3,4])
annotate('collaboration',[16],1,'Selects people rather than audit_log; distinct actors and workspace grouping are absent.',[3])
annotate('collaboration',[17],1,'Counts catalog entries instead of fact-table occurrences joined to catalog labels.',[2,3])
annotate('collaboration',[18,20],7,'Implicit REFERENCES target produces target_column=None; join SQL calls identifier.replace on None.',[2])
annotate('collaboration',[19],2,'Counts organizations by plan instead of distinct people across membership relationships.',[1,3])
annotate('collaboration',[21,22],2,'Lexical table tie prevents the requested anti-join; no additional business definition is needed.')
annotate('collaboration',[23],2,'Returns all people rather than applying a grouped membership HAVING condition.',[3])
annotate('collaboration',[24],3,'Returns one audit count without actor grouping, ranking or top-three limit.',[1])
annotate('collaboration',[25],2,'Lexical tie prevents the explicit person/workspace composite anti-join.',[1])
annotate('collaboration',[26,27,28],5,'Explicit ordered person-level funnel across workspaces is replaced by people count/raw rows.',[1,2,3,4])
annotate('collaboration',[29],1,'Cannot identify audit_log from actors; lexical matching does not resolve actor to actor_id.',[3,4])
annotate('collaboration',[30],2,'Counts organizations by one dimension instead of audit events joined to both plan and action label.',[1,3])


def accidental_pass(pack,family,table,insert_sql,reference,generated):
    """Modify only an in-memory copy; never change the frozen database or official score."""
    source=pack/f'{family}.db'
    before=sha(source)
    with closing(sqlite3.connect(f'{source.resolve().as_uri()}?mode=ro',uri=True)) as db, closing(sqlite3.connect(':memory:')) as memory:
        db.backup(memory)
        original=dict(generated=memory.execute(generated).fetchall(),reference=memory.execute(reference).fetchall())
        memory.execute(insert_sql)
        altered=dict(generated=memory.execute(generated).fetchall(),reference=memory.execute(reference).fetchall())
    if sha(source)!=before:
        raise ValueError('Frozen database changed')
    return dict(table=table,original=original,in_memory_counterexample=altered,source_unchanged=True)


def analyze(pack,baseline):
    manifest=verify_suite(pack)
    report=json.loads(baseline.read_text(encoding='utf-8'))
    if report['manifest_sha256']!=sha(pack/'manifest.json'):
        raise ValueError('Baseline and manifest do not match')
    systems=[s for s in report['systems'] if s['system']=='deterministic']
    if len(systems)!=1:
        raise ValueError('Expected one deterministic baseline')
    cases=systems[0]['cases']
    targets={c['id']:c for d in manifest['datasets'] for c in d['cases']}
    if len(cases)!=108 or {c['id'] for c in cases}!=set(targets):
        raise ValueError('Audit requires the complete 108-case baseline')
    failed={c['id'] for c in cases if not c['correct']}
    if failed!=set(ANNOTATIONS):
        raise ValueError(f'Annotation coverage mismatch: missing {failed-set(ANNOTATIONS)}, extra {set(ANNOTATIONS)-failed}')
    reviewed=[]
    flags={'education-05':'Accidental pass: total learners equals distinct enrolled learners.',
           'collaboration-05':'Accidental pass: total people equals distinct organization members.'}
    weak_clarifications={'education-32','education-34','logistics-32','collaboration-32','collaboration-34'}
    for case in cases:
        target=targets[case['id']]
        entry=dict(case,reference_sql=target['reference_sql'],expected_rows=target['expected_rows'],review_status='reviewed')
        if case['id'] in ANNOTATIONS:
            entry.update(ANNOTATIONS[case['id']])
        if case['id'] in flags:
            entry['evaluation_warning']=flags[case['id']]
        if case['id'] in weak_clarifications:
            entry['clarification_warning']='Category is correct, but message asks which table rather than the missing business definition/field.'
        reviewed.append(entry)
    counts=Counter(a['primary'] for a in ANNOTATIONS.values())
    overlapping=Counter(category for a in ANNOTATIONS.values() for category in {a['primary'],*a['secondary']})
    counterexamples={}
    for key,table,insert in [('education-05','learners',"INSERT INTO learners VALUES(999,'new-region','2026-01-01')"),
                             ('collaboration-05','people',"INSERT INTO people VALUES(999,'2026-01-01')")]:
        case=next(c for c in cases if c['id']==key)
        counterexamples[key]=accidental_pass(pack,case['dataset'],table,insert,targets[key]['reference_sql'],case['sql'])
    return dict(scope='Full 108-case offline baseline only; not a full LLM failure analysis',
                suite_role='development',baseline_sha256=sha(baseline),manifest_sha256=sha(pack/'manifest.json'),
                baseline_summary=systems[0]['summary'],reviewed=len(reviewed),failed=len(failed),
                primary_counts={str(k):dict(category=name,count=counts[k]) for k,name in CATEGORIES.items()},
                overlapping_counts={str(k):dict(category=name,count=overlapping[k]) for k,name in CATEGORIES.items()},
                classification_policy='One primary observed failure per failed case; secondary labels overlap. Dominant observed mismatch, not proven counterfactual causal attribution.',
                evaluation_warnings=dict(accidental_passes=2,precision_contract_cases=['education-09'],
                    weak_correct_clarifications=len(weak_clarifications),confirmed_reference_sql_oracle_disagreements=0),
                in_memory_checks=counterexamples,cases=reviewed)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack',type=Path,default=ROOT/'datasets/evaluation/independent-v1')
    parser.add_argument('--baseline',type=Path,default=ROOT/'logs/independent-v1-deterministic.json')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--markdown-output',type=Path)
    args=parser.parse_args()
    if args.output.exists():
        parser.error('Choose a new report filename')
    if args.markdown_output and args.markdown_output.exists():
        parser.error('Choose a new Markdown report filename')
    result=analyze(args.pack,args.baseline)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as handle:
        json.dump(result,handle,indent=2)
    if args.markdown_output:
        lines=['# V1 development audit: all 108 cases','',
               'Manual evidence annotations, not automated causal attribution. Primary categories partition the 71 failures; secondary categories overlap. Historical scores and references are unchanged.','',
               f"Baseline SHA-256: `{result['baseline_sha256']}`.",'',
               f"Manifest SHA-256: `{result['manifest_sha256']}`.",'']
        for case in result['cases']:
            lines += [f"## {case['id']}: {'PASS' if case['correct'] else 'FAIL'}",'',case['question'],'',
                      f"Expected: {case['expected_outcome']}. Observed: {case['outcome']}.",'']
            if 'primary' in case:
                lines += [f"Primary category {case['primary']}: {CATEGORIES[case['primary']]}. {case['evidence']}",'',
                          f"Secondary categories: {', '.join(str(c) for c in case['secondary']) or 'none'}.",'']
            for key in ('evaluation_warning','clarification_warning','message','error'):
                if case.get(key):
                    lines += [f"{key.replace('_',' ').title()}: {case[key]}",'']
            if case.get('sql'):
                lines += ['Generated SQL:','', '```sql',case['sql'],'```','']
            if case.get('reference_sql'):
                lines += ['Reference SQL:','', '```sql',case['reference_sql'],'```','']
        args.markdown_output.parent.mkdir(parents=True,exist_ok=True)
        with args.markdown_output.open('x',encoding='utf-8') as handle:
            handle.write('\n'.join(lines))
    print(json.dumps({k:result[k] for k in ('reviewed','failed','primary_counts','evaluation_warnings')},indent=2))


if __name__=='__main__':
    main()
