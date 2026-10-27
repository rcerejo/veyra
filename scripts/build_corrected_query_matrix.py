"""Development-only neighboring-query stress matrix, with Python/SQL reference cross-checks.

No planner import, no model training, and no reserved final evaluation access.
"""
import argparse
from collections import Counter
from contextlib import closing
import hashlib
import json
from pathlib import Path
import random
import sqlite3


FAMILIES = [
    ('quality','reviews','review_id','staffers','staff_id','inspector_id','inspectors','reviewer_id','reviewers','fee','INTEGER'),
    ('dispatch','dispatches','dispatch_id','operators','operator_id','courier_id','couriers','checker_id','checkers','charge','REAL'),
    ('content','edits','edit_id','contributors','contributor_id','author_id','authors','approver_id','approvers','cost','NUMERIC(12,2)'),
    ('commerce','charges','charge_id','customers','customer_id','buyer_id','buyers','reviewer_id','reviewers','amount','INTEGER'),
]


def quote(value):
    return '"'+value.replace('"','""')+'"'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(output, family, seed):
    name,table,pk,parent,parent_pk,first,first_role,second,second_role,amount,declared=family
    rng=random.Random(seed)
    rows=[]
    for index in range(1,35+seed%5):
        value=[0,1.5,-2.5,10,None,0][index-1] if index<=6 else rng.choice([0,0,1,1.5,2,10,-2.5,None])
        rows.append((index,None if index%11==0 else rng.randint(1,3),
                     None if index%7==0 else rng.randint(4,5),value,
                     ['clear','PASS','on hold','zero',None][(index+seed)%5]))
    # Ensure text/numeric zero are different predicates with nonempty answers.
    rows[0]=(1,1,4,0,'clear')
    rows[1]=(2,1,4,0,'clear')
    rows[2]=(3,2,5,10,'zero')
    path=output/f'{name}.db'
    with closing(sqlite3.connect(path)) as db:
        db.executescript(f'''PRAGMA foreign_keys=ON;
          CREATE TABLE {quote(parent)}({quote(parent_pk)} INTEGER PRIMARY KEY);
          CREATE TABLE {quote(table)}({quote(pk)} INTEGER PRIMARY KEY,
            {quote(first)} INTEGER REFERENCES {quote(parent)}({quote(parent_pk)}),
            {quote(second)} INTEGER REFERENCES {quote(parent)}({quote(parent_pk)}),
            {quote(amount)} {declared},status TEXT);''')
        db.executemany(f'INSERT INTO {quote(parent)} VALUES(?)',[(i,) for i in range(1,9)])
        db.executemany(f'INSERT INTO {quote(table)} VALUES(?,?,?,?,?)',rows)
        db.commit()
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Invalid fixture')
    cases=[]
    def add(question,sql=None,expected=None,tags=(),outcome='query',complexity='simple'):
        cases.append(dict(id=f'{name}-{len(cases)+1:02d}',question=question,reference_sql=sql,
            expected_rows=expected,expected_outcome=outcome,complexity=complexity,tags=list(tags),ordered=False))
    def equal(question,column,index,value,wording='corrected_control'):
        literal=str(value) if isinstance(value,(int,float)) else "'"+value.replace("'","''")+"'"
        add(question,f'SELECT COUNT(*) FROM {quote(table)} WHERE {quote(column)}={literal}',
            [[sum(r[index]==value for r in rows)]],['scalar_equality',wording,'text' if isinstance(value,str) else 'numeric'])
    def distinct(question,column,index,wording='corrected_control',zero=False,group=False):
        eligible=[r for r in rows if not zero or r[3]==0]
        if group:
            categories={r[4] for r in eligible}
            expected=[[category,len({r[index] for r in eligible if r[4]==category and r[index] is not None})] for category in sorted(categories,key=str)]
        else:
            expected=[[len({r[index] for r in eligible if r[index] is not None})]]
        sql=f'SELECT '+('status,' if group else '')+f'COUNT(DISTINCT {quote(column)}) FROM {quote(table)}'
        if zero:
            sql+=f' WHERE {quote(amount)}=0'
        if group:
            sql+=' GROUP BY status'
        add(question,sql,expected,['distinct_identity',wording]+(['grouping'] if group else []),complexity='medium' if zero or group else 'simple')
    for raw,value in [('zero',0),('ZERO',0),('0',0),('"0"',0)]:
        equal(f'Count {table} where {amount} is {raw}',amount,3,value)
    equal(f'Count {table} where {amount} equals zero',amount,3,0)
    equal(f'Count {table} where {amount} is one',amount,3,1)
    equal(f'Count {table} where {amount} equals 10',amount,3,10)
    equal(f'Count {table} where {amount} is -2.5',amount,3,-2.5)
    equal(f'Count {table} where {amount} is 1.5',amount,3,1.5)
    equal(f'Count {table} where {amount} is 2E0',amount,3,2)
    equal(f'Count {table} where status is zero','status',4,'zero')
    equal(f'Count {table} where status is PASS','status',4,'PASS')
    equal(f'Count {table} where status is "on hold"','status',4,'on hold')
    distinct(f'Count distinct {first_role} from {table}',first,1)
    distinct(f'Count distinct {second_role} from {table}',second,2)
    distinct(f'Count unique {first} from {table}',first,1)
    distinct(f'Count distinct {table}.{second} from {table}',second,2)
    distinct(f'Count distinct {table} from {table}',pk,0)
    distinct(f'Count distinct status from {table}','status',4)
    distinct(f'Count distinct {first_role} from {table} where {amount} is zero',first,1,zero=True)
    for question in [f'Count {table} where {amount} is zero.',f'Count {table} where {amount} = zero',
                     f'How many {table} have a {amount} of zero?',f'Count {table} where {amount} is equal to zero']:
        equal(question,amount,3,0,'nearby_wording')
    distinct(f'Count unique {first_role} in {table}',first,1,'nearby_wording')
    distinct(f'How many different {first_role} are in {table}?',first,1,'nearby_wording')
    distinct(f'How many {first_role} performed {table}?',first,1,'nearby_wording')
    add(f'List distinct {first} from {table}, excluding missing IDs',
        f'SELECT DISTINCT {quote(first)} FROM {quote(table)} WHERE {quote(first)} IS NOT NULL',
        [[v] for v in sorted({r[1] for r in rows if r[1] is not None})],['distinct_identity','nearby_wording','projection'])
    eligible=[r for r in rows if r[3]==0 and r[4]=='PASS']
    add(f'Count {table} where {amount} is 0 and status is PASS',
        f"SELECT COUNT(*) FROM {quote(table)} WHERE {quote(amount)}=0 AND status='PASS'",[[len(eligible)]],['numeric','text','compound','corrected_control'])
    add(f'Count distinct {first} from {table} where {amount} is zero and status is PASS',
        f"SELECT COUNT(DISTINCT {quote(first)}) FROM {quote(table)} WHERE {quote(amount)}=0 AND status='PASS'",
        [[len({r[1] for r in eligible if r[1] is not None})]],['distinct_identity','compound','corrected_control'])
    distinct(f'Count distinct {second} from {table} by status',second,2,group=True)
    grouped=Counter(r[4] for r in rows)
    add(f'Count {table} by status',f'SELECT status,COUNT(*) FROM {quote(table)} GROUP BY status',
        [[k,v] for k,v in grouped.items()],['grouping','nulls','corrected_control'])
    add(f'Count {table} whose {amount} is null',f'SELECT COUNT(*) FROM {quote(table)} WHERE {quote(amount)} IS NULL',
        [[sum(r[3] is None for r in rows)]],['nulls','corrected_control'])
    add(f'Count {table} where {amount} is zero or {amount} is ten',
        f'SELECT COUNT(*) FROM {quote(table)} WHERE {quote(amount)}=0 OR {quote(amount)}=10',
        [[sum(r[3] in (0,10) for r in rows)]],['compound','nearby_wording'])
    add(f'Count {table} whose {amount} is not zero',f'SELECT COUNT(*) FROM {quote(table)} WHERE {quote(amount)}<>0',
        [[sum(r[3] is not None and r[3]!=0 for r in rows)]],['negation','nearby_wording'])
    distinct(f'Count distinct {first_role} from {table} where {amount} is zero and {amount} is zero',first,1,'nearby_wording',zero=True)
    for question,tag in [(f'Count {table} where {amount} is high','undefined_value'),
                         (f'Count distinct {parent} from {table}','ambiguous_role'),
                         (f'Show activation for {parent}','undefined_metric'),
                         (f'Which {first_role} are best?','undefined_metric')]:
        add(question,outcome='clarification',tags=[tag],complexity='ambiguous')
    for question in (f'Delete all {table}',f'Update {table} set {amount} to zero'):
        add(question,outcome='refusal',tags=['write'],complexity='invalid')
    if len(cases)!=42:
        raise ValueError(f'Expected 42 cases, got {len(cases)}')
    return dict(name=name,file=path.name,sha256=sha(path),cases=cases)


def build(output,seed=23):
    if output.exists():
        raise FileExistsError('Choose a new output directory; existing fixtures are never overwritten')
    output.mkdir(parents=True)
    manifest=dict(version='independent-v1',suite_name='corrected-query-matrix-v1',seed=seed,
        exposure='development-exposed-neighboring-query-diagnostics',external_blind=False,
        oracle='Python source-tuple collections; reference SQL checked separately before scoring',
        design='Four renamed role/type families with the same 42 operation templates each. Data variants repeat questions; no independent-language sample claim.',
        datasets=[fixture(output,family,seed) for family in FAMILIES])
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--seed',type=int,default=23)
    args=parser.parse_args()
    result=build(args.output,args.seed)
    print(f"Created {sum(len(d['cases']) for d in result['datasets'])} development cases, seed {args.seed}")
