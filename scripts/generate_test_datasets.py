"""Generate unfamiliar SQLite schemas and independently calculated reference answers."""
import argparse
from contextlib import closing
from datetime import date, timedelta
import json
from pathlib import Path
import random
import sqlite3

ROOT=Path(__file__).resolve().parents[1]


def case(question,sql,rows=None,clarify=False):
    return {'question':question,'reference_sql':sql,'expected_rows':rows,'expect_clarification':clarify}


def commerce(path):
    rng=random.Random(101)
    customers=[(i,'retail' if i%3 else 'business',['US','GB','CA'][i%3]) for i in range(1,81)]
    purchases=[(i,rng.randint(1,80),f'2026-03-{1+i%28:02d}T10:00:00',['completed','pending','cancelled'][i%3],rng.randint(500,20000)) for i in range(1,241)]
    refunds=[(i,i*3,'approved' if i%2 else 'requested',purchases[i*3-1][4]//2) for i in range(1,41)]
    with closing(sqlite3.connect(path)) as db:
        db.executescript('''CREATE TABLE customers(customer_key INTEGER PRIMARY KEY,segment TEXT,market TEXT);
            CREATE TABLE purchases(purchase_key INTEGER PRIMARY KEY,buyer_key INTEGER REFERENCES customers(customer_key),ordered_at TEXT,status TEXT,total_cents INTEGER);
            CREATE TABLE refunds(refund_key INTEGER PRIMARY KEY,purchase_key INTEGER REFERENCES purchases(purchase_key),status TEXT,refund_cents INTEGER);''')
        db.executemany('INSERT INTO customers VALUES(?,?,?)',customers)
        db.executemany('INSERT INTO purchases VALUES(?,?,?,?,?)',purchases)
        db.executemany('INSERT INTO refunds VALUES(?,?,?,?)',refunds)
        db.commit()
    return [case('How many customers are there?','SELECT COUNT(*) FROM customers',[[80]]),
            case('How many purchases are there?','SELECT COUNT(*) FROM purchases',[[240]]),
            case('Show cancelled purchases in March 2026',"SELECT * FROM purchases WHERE status='cancelled' AND ordered_at>='2026-03-01' AND ordered_at<'2026-04-01'",[list(r) for r in purchases if r[3]=='cancelled']),
            case('Show total total_cents for purchases','SELECT SUM(total_cents) FROM purchases',[[sum(r[4] for r in purchases)]]),
            case('Break down purchases by customer segment','SELECT c.segment,COUNT(*) FROM purchases p JOIN customers c ON p.buyer_key=c.customer_key GROUP BY c.segment',[[segment,sum(customers[r[1]-1][1]==segment for r in purchases)] for segment in ('retail','business')]),
            case('Show approved refunds',"SELECT * FROM refunds WHERE status='approved'",[list(r) for r in refunds if r[2]=='approved']),
            case('Show customer retention',None,clarify=True)]


def subscriptions(path):
    accounts=[(i,['starter','pro','enterprise'][i%3],f'2026-01-{1+i%28:02d}') for i in range(1,61)]
    memberships=[(i,i,'active' if i%4 else 'cancelled',10+(i%3)*20,'2026-02-01') for i in range(1,61)]
    activity=[(i,1+i%60,['launch','invite_sent','report_export'][i%3],f'2026-03-{1+i%28:02d}T12:00:00') for i in range(1,301)]
    with closing(sqlite3.connect(path)) as db:
        db.executescript('''CREATE TABLE accounts(account_key INTEGER PRIMARY KEY,plan_tier TEXT,created_at TEXT);
            CREATE TABLE memberships(membership_key INTEGER PRIMARY KEY,account_key INTEGER REFERENCES accounts(account_key),status TEXT,monthly_price INTEGER,started_at TEXT);
            CREATE TABLE activity(activity_key INTEGER PRIMARY KEY,account_key INTEGER REFERENCES accounts(account_key),action_name TEXT,occurred_at TEXT);''')
        db.executemany('INSERT INTO accounts VALUES(?,?,?)',accounts)
        db.executemany('INSERT INTO memberships VALUES(?,?,?,?,?)',memberships)
        db.executemany('INSERT INTO activity VALUES(?,?,?,?)',activity)
        db.commit()
    return [case('How many accounts are there?','SELECT COUNT(*) FROM accounts',[[60]]),
            case('Show cancelled memberships',"SELECT * FROM memberships WHERE status='cancelled'",[list(r) for r in memberships if r[2]=='cancelled']),
            case('Show launch activity in March 2026',"SELECT * FROM activity WHERE action_name='launch' AND occurred_at>='2026-03-01' AND occurred_at<'2026-04-01'",[list(r) for r in activity if r[2]=='launch']),
            case('Break down memberships by account plan tier','SELECT a.plan_tier,COUNT(*) FROM memberships m JOIN accounts a ON m.account_key=a.account_key GROUP BY a.plan_tier',[[tier,20] for tier in ('starter','pro','enterprise')]),
            case('Show total monthly_price for memberships','SELECT SUM(monthly_price) FROM memberships',[[sum(r[3] for r in memberships)]]),
            case('Show account churn',None,clarify=True)]


def support(path):
    agents=[(i,['billing','technical','general'][i%3]) for i in range(1,13)]
    tickets=[(i,1+i%12,['open','resolved','pending'][i%3],['low','high'][i%2],f'2026-03-{1+i%28:02d}',None if i%3 else i%48+1) for i in range(1,181)]
    messages=[(i,1+i%180,'customer' if i%2 else 'agent') for i in range(1,541)]
    with closing(sqlite3.connect(path)) as db:
        db.executescript('''CREATE TABLE agents(agent_key INTEGER PRIMARY KEY,team TEXT);
            CREATE TABLE tickets(ticket_key INTEGER PRIMARY KEY,assigned_agent INTEGER REFERENCES agents(agent_key),status TEXT,priority TEXT,created_at TEXT,resolution_hours REAL);
            CREATE TABLE messages(message_key INTEGER PRIMARY KEY,ticket_key INTEGER REFERENCES tickets(ticket_key),sender_type TEXT);''')
        db.executemany('INSERT INTO agents VALUES(?,?)',agents)
        db.executemany('INSERT INTO tickets VALUES(?,?,?,?,?,?)',tickets)
        db.executemany('INSERT INTO messages VALUES(?,?,?)',messages)
        db.commit()
    return [case('How many tickets are there?','SELECT COUNT(*) FROM tickets',[[180]]),
            case('Show resolved tickets in March 2026',"SELECT * FROM tickets WHERE status='resolved' AND created_at>='2026-03-01' AND created_at<'2026-04-01'",[list(r) for r in tickets if r[2]=='resolved']),
            case('Break down tickets by agent team','SELECT a.team,COUNT(*) FROM tickets t JOIN agents a ON t.assigned_agent=a.agent_key GROUP BY a.team',[[team,60] for team in ('billing','technical','general')]),
            case('Show average resolution_hours for tickets','SELECT AVG(resolution_hours) FROM tickets',[[sum(r[5] for r in tickets if r[5] is not None)/sum(r[5] is not None for r in tickets)]]),
            case('Show customer messages',"SELECT * FROM messages WHERE sender_type='customer'",[list(r) for r in messages if r[2]=='customer']),
            case('Which customers churned?',None,clarify=True)]


def messy(path):
    records=[(1,'launch','2026-03-04',10),(2,' LAUNCH ','03/05/2026',None),(3,'Launch','05/03/2026',20),(4,None,'not-a-date',-5),(5,'report_export',None,0),(6,'launch','2026-04-01',10)]
    with closing(sqlite3.connect(path)) as db:
        db.executescript('''CREATE TABLE records(record_key INTEGER PRIMARY KEY,action_name TEXT,happened_at TEXT,value REAL);
            CREATE TABLE customer_accounts(customer_key INTEGER PRIMARY KEY,status TEXT);
            CREATE TABLE customer_profiles(customer_key INTEGER PRIMARY KEY,status TEXT);''')
        db.executemany('INSERT INTO records VALUES(?,?,?,?)',records)
        db.execute("INSERT INTO customer_accounts VALUES(1,'active')")
        db.execute("INSERT INTO customer_profiles VALUES(1,'active')")
        db.commit()
    return [case('How many records are there?','SELECT COUNT(*) FROM records',[[6]]),
            case('Show total value for records','SELECT SUM(value) FROM records',[[35]]),
            case('Show customer records',None,clarify=True),
            case('Show records from March 2026',None,clarify=True),
            case('Show customer accounts by record action',None,clarify=True)]


def rename_demo(source,target):
    mappings={
        'users':('members',{'user_id':'member_key','signup_date':'joined_on','acquisition_channel':'source_channel','country':'region_code','device_type':'client_kind'}),
        'events':('activity_log',{'event_id':'activity_key','user_id':'member_key','event_type':'action_name','event_timestamp':'occurred_at','session_id':'visit_key'}),
        'sessions':('visits',{'session_id':'visit_key','user_id':'member_key','session_start':'began_at','session_end':'finished_at'}),
        'orders':('transactions',{'order_id':'transaction_key','user_id':'member_key','order_timestamp':'recorded_at','revenue':'gross_amount'}),
        'experiments':('trials',{'experiment_id':'trial_key','experiment_name':'trial_label','start_date':'begins_on','end_date':'ends_on'}),
        'experiment_assignments':('trial_enrolments',{'experiment_id':'trial_key','user_id':'member_key','variant':'arm','assigned_at':'enrolled_at'}),
    }
    with closing(sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True)) as original, closing(sqlite3.connect(target)) as db:
        original.backup(db)
        counts={table:db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in mappings}
        revenue=db.execute('SELECT SUM(revenue) FROM orders').fetchone()[0]
        for old,(new,columns) in mappings.items():
            db.execute(f'ALTER TABLE "{old}" RENAME TO "{new}"')
            for before,after in columns.items():
                db.execute(f'ALTER TABLE "{new}" RENAME COLUMN "{before}" TO "{after}"')
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Renaming invalidated foreign keys')
        db.commit()
    cases=[case(f'How many {new} are there?',f'SELECT COUNT(*) FROM "{new}"',[[counts[old]]]) for old,(new,_) in mappings.items()]
    cases.append(case('Show total gross_amount for transactions','SELECT SUM(gross_amount) FROM transactions',[[revenue]]))
    cases.append(case('Show daily active users',None,clarify=True))
    return cases,mappings


def build_pack(output,source):
    if output.exists():
        raise ValueError('Output directory already exists. Choose a new path; packs are never overwritten.')
    if not source.is_file():
        raise ValueError('Generate the canonical demo first, or pass --source to an existing demo database')
    output.mkdir(parents=True)
    manifest={'version':1,'synthetic':True,'datasets':[]}
    for name,builder in [('commerce',commerce),('subscriptions',subscriptions),('support',support),('messy',messy)]:
        cases=builder(output/f'{name}.db')
        manifest['datasets'].append({'name':name,'file':f'{name}.db','cases':cases})
    cases,mappings=rename_demo(source,output/'renamed-demo.db')
    manifest['datasets'].append({'name':'renamed-demo','file':'renamed-demo.db','cases':cases,'rename_map':mappings})
    for dataset in manifest['datasets']:
        with closing(sqlite3.connect(output/dataset['file'])) as db:
            assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'datasets/test-packs/v1')
    parser.add_argument('--source',type=Path,default=ROOT/'datasets/veyra.db')
    args=parser.parse_args()
    try:
        manifest=build_pack(args.output,args.source)
    except (ValueError,sqlite3.Error) as exc:
        parser.error(str(exc))
    print(f"Created {len(manifest['datasets'])} databases and {sum(len(d['cases']) for d in manifest['datasets'])} reference/clarification cases in {args.output}")


if __name__=='__main__':
    main()
