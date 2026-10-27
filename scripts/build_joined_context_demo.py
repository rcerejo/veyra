"""Create two synthetic sources, a combined demo snapshot and explicit context diagnostics.

This is fixture preparation, not a federated database adapter or semantic-layer feature.
Never reads customer files, the selected workspace or reserved final evaluation artifacts.
"""
import argparse
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3


ACCOUNTS = [(1,'free','east'),(2,'pro','west'),(3,'pro','east'),(4,'enterprise','north'),(5,'free','west')]
PEOPLE = [(i,f'2026-02-{i:02d}') for i in range(1,9)]
MEMBERSHIPS = [(1,1,'owner'),(1,2,'viewer'),(2,1,'viewer'),(3,2,'owner'),
    (3,3,'viewer'),(4,2,'viewer'),(5,3,'owner'),(6,3,'viewer'),(7,4,'owner'),(8,4,'viewer')]
ACTIVITY = [
    (1,1,1,'app_open','2026-03-01'),(2,1,1,'app_open','2026-03-01'),
    (3,1,1,'export','2026-03-02'),(4,2,1,'export','2026-02-28'),
    (5,2,1,'app_open','2026-03-03'),(6,3,2,'app_open','2026-03-10'),
    (7,3,2,'export','2026-03-11'),(8,4,2,'app_open','2026-03-31T23:30:00-02:00'),
    (9,5,3,'app_open','2026-04-01T00:30:00+02:00'),(10,5,3,'export','2026-04-02'),
    (11,6,3,'app_open',None),(12,None,1,'app_open','2026-03-12'),
    (13,7,1,'sign_in','2026-03-15'),(14,3,2,'sign_in','2026-03-10'),
    (15,8,4,'sign_in','2026-03-20'),(16,None,None,'app_open','2026-03-15'),
    (17,7,1,'app_open','2026-04-01T00:45:00+02:00')]
INVOICES = [(1,1,100,'paid','2026-03-01'),(2,1,0,'paid','2026-03-03'),
    (3,2,300,'paid','2026-03-10'),(4,2,-50,'paid','2026-03-11'),
    (5,3,500,'void','2026-03-12'),(6,3,400,'paid','2026-04-01'),
    (7,4,1000,'paid','2026-03-31T23:30:00-02:00'),(8,None,200,'paid','2026-03-15'),
    (9,2,None,'paid','2026-03-16')]

CRM_DDL = '''CREATE TABLE accounts(account_id INTEGER PRIMARY KEY,plan TEXT,region TEXT);
CREATE TABLE people(person_id INTEGER PRIMARY KEY,registered_on TEXT);
CREATE TABLE memberships(person_id INTEGER REFERENCES people,account_id INTEGER REFERENCES accounts,
 role TEXT,PRIMARY KEY(person_id,account_id));'''
PRODUCT_DDL = '''CREATE TABLE activity_log(event_id INTEGER PRIMARY KEY,actor_id INTEGER,workspace_id INTEGER,action TEXT,occurred_at TEXT);
CREATE TABLE invoices(invoice_id INTEGER PRIMARY KEY,workspace_id INTEGER,usd_cents INTEGER,status TEXT,issued_on TEXT);'''
JOINED_DDL = CRM_DDL + '''CREATE TABLE activity_log(event_id INTEGER PRIMARY KEY,
actor_id INTEGER REFERENCES people(person_id),workspace_id INTEGER REFERENCES accounts(account_id),action TEXT,occurred_at TEXT);
CREATE TABLE invoices(invoice_id INTEGER PRIMARY KEY,workspace_id INTEGER REFERENCES accounts(account_id),usd_cents INTEGER,status TEXT,issued_on TEXT);'''


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create(path, ddl, tables):
    if path.exists():
        raise FileExistsError('Never overwrite demo snapshots')
    with closing(sqlite3.connect(path)) as db:
        db.executescript('PRAGMA foreign_keys=ON;'+ddl)
        for name,rows in tables.items():
            db.executemany(f'INSERT INTO {name} VALUES ({",".join("?" for _ in rows[0])})',rows)
        db.commit()
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Invalid synthetic source or combined relationships')


def read_tables(path, names):
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as db:
        return {name:db.execute(f'SELECT * FROM {name} ORDER BY 1,2').fetchall() for name in names}


def instant(value):
    if value is None:
        return None
    parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    return (parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed).astimezone(timezone.utc)


def grouped(rows, key, amount=None):
    result=defaultdict(list)
    for row in rows:
        result[key(row)].append(row)
    return [[k,sum(amount(r) for r in values) if amount else len(values)] for k,values in sorted(result.items())]


def make_cases():
    cases=[]
    def pair(number, raw, explicit, sql, rows, raw_answerable=False, complexity='medium', tags=()):
        for mode,question in [('raw',raw),('explicit',explicit)]:
            answerable=sql is not None and (mode=='explicit' or raw_answerable)
            cases.append(dict(id=f'joined-{number:02d}-{mode}',pair_id=f'joined-{number:02d}',wording=mode,
                question=question,expected_outcome='query' if answerable else 'clarification',
                reference_sql=sql if answerable else None,expected_rows=rows if answerable else None,
                ordered=False,complexity=complexity,tags=[*tags,mode],
                context_delivery='No document/context supplied to service; explicit wording is manually authored from the recorded contract.' if mode=='explicit'
                    else 'No document/context supplied; unconfigured business metrics/aliases must clarify.'))
    pair(1,'How many accounts are there?','Count accounts','SELECT COUNT(*) FROM accounts',[[len(ACCOUNTS)]],True,'simple',['account_identity'])
    pair(2,'How many users do we have?','Count people','SELECT COUNT(*) FROM people',[[len(PEOPLE)]],tags=['user_mapping'])
    march=lambda x:x is not None and instant('2026-03-01')<=instant(x)<instant('2026-04-01')
    opens=[e for e in ACTIVITY if e[3]=='app_open' and march(e[4])]
    pair(3,'How often was the app opened in March 2026?',
        'Count activity_log whose action is app_open during March 2026',
        "SELECT COUNT(*) FROM activity_log WHERE action='app_open' AND julianday(occurred_at)>=julianday('2026-03-01') AND julianday(occurred_at)<julianday('2026-04-01')",[[len(opens)]],tags=['event_alias','utc','duplicate_events'])
    pair(4,'How many active users were there in March 2026?',
        'Count distinct actors active from activity_log app_open during March 2026',
        "SELECT COUNT(DISTINCT actor_id) FROM activity_log WHERE action='app_open' AND julianday(occurred_at)>=julianday('2026-03-01') AND julianday(occurred_at)<julianday('2026-04-01')",[[len({e[1] for e in opens if e[1] is not None})]],tags=['active_definition','distinct','utc'])
    plans={a[0]:a[1] for a in ACCOUNTS}
    paid=[r for r in INVOICES if r[3]=='paid' and r[1] in plans and r[2] is not None]
    pair(5,'Show revenue by customer plan',
        'Total paid invoices usd cents by account plan',
        "SELECT a.plan,SUM(i.usd_cents) FROM invoices i JOIN accounts a ON a.account_id=i.workspace_id WHERE i.status='paid' GROUP BY a.plan",
        grouped(paid,lambda r:plans[r[1]],lambda r:r[2]),tags=['cross_source_join','revenue_definition','null_amount','refund'])
    attributed=[e for e in ACTIVITY if e[2] in plans]
    pair(6,'Count activity_log by account plan','Activity_log counts by accounts plan',
        'SELECT a.plan,COUNT(*) FROM activity_log e JOIN accounts a ON a.account_id=e.workspace_id GROUP BY a.plan',
        grouped(attributed,lambda e:plans[e[2]]),True,tags=['cross_source_join','grain'])
    pair(7,'Which customers have no usage?','List accounts without activity_log',
        'SELECT a.* FROM accounts a WHERE NOT EXISTS(SELECT 1 FROM activity_log e WHERE e.workspace_id=a.account_id)',
        [list(a) for a in ACCOUNTS if not any(e[2]==a[0] for e in ACTIVITY)],tags=['cross_source_join','absence'])
    pair(8,'List accounts with no paid invoices','Show accounts without paid invoices',
        "SELECT a.* FROM accounts a WHERE NOT EXISTS(SELECT 1 FROM invoices i WHERE i.workspace_id=a.account_id AND i.status='paid')",
        [list(a) for a in ACCOUNTS if not any(i[1]==a[0] and i[3]=='paid' for i in INVOICES)],True,tags=['cross_source_join','filtered_absence'])
    known=[e for e in opens if e[1] is not None]
    days=sorted({instant(e[4]).date().isoformat() for e in known})
    daily=[[day,len({e[1] for e in known if instant(e[4]).date().isoformat()==day})] for day in days]
    pair(9,'Show daily active users in March 2026',
        'Daily distinct actors from activity_log app_open during March 2026 excluding missing actor IDs',
        "SELECT date(occurred_at),COUNT(DISTINCT actor_id) FROM activity_log WHERE action='app_open' AND actor_id IS NOT NULL AND julianday(occurred_at)>=julianday('2026-03-01') AND julianday(occurred_at)<julianday('2026-04-01') GROUP BY date(occurred_at)",daily,tags=['active_definition','daily','utc'])
    pair(10,'Count invoices whose usd cents is zero','Count invoices where usd cents equals zero',
        'SELECT COUNT(*) FROM invoices WHERE usd_cents=0',[[sum(i[2]==0 for i in INVOICES)]],True,'simple',['typed_zero'])
    converted={a[1] for a in ACTIVITY if a[1] is not None and a[3]=='app_open' and a[4] and
        any(b[1]==a[1] and b[3]=='export' and b[4] and instant(b[4])>=instant(a[4]) for b in ACTIVITY)}
    pair(11,'How many users converted?',
        'Count distinct people who opened the app then exported across any workspaces and all dates, allowing equal timestamps',
        "SELECT COUNT(DISTINCT a.actor_id) FROM activity_log a JOIN activity_log b ON b.actor_id=a.actor_id WHERE a.action='app_open' AND b.action='export' AND julianday(b.occurred_at)>=julianday(a.occurred_at)",[[len(converted)]],complexity='complex',tags=['conversion_definition','ordered_funnel'])
    pair(12,'Show user retention','Retention is undefined for this dataset; ask for the cohort anchor and return rule',None,None,tags=['undefined_metric'])
    for i,question in enumerate(('Delete all activity_log','Update invoices set usd_cents to zero'),25):
        cases.append(dict(id=f'joined-{i:02d}-refusal',question=question,expected_outcome='refusal',reference_sql=None,
            expected_rows=None,complexity='invalid',tags=['write'],ordered=False,wording='refusal'))
    return cases


def context_markdown():
    return '''# Completed dataset context: Beacon workspace demo

This is a filled copy of the dataset context brief, authored for a fully synthetic demo. No customer data or credentials are used. **This document is not automatically loaded by Veyra.** Definitions below are proposed demo-owner definitions, not approvals from a real business. Explicit diagnostic questions manually repeat these definitions.

## 1. Dataset and business meaning

- Domain: a fictional collaborative workspace product, Beacon.
- Snapshot/schema: joined-context-v1, context revision 2, fixed source tuples, data-complete-through 2026-04-30 UTC. File hashes and row counts are in provenance.json. Revision 2 explicitly states the daily sparse-bucket/anonymous policy after reviewing a revision-1 result mismatch; it is not an untouched evaluation.
- Two source files: crm.db (accounts, people, memberships), product.db (activity_log, invoices).
- Upload/query artifact: joined.db, a prepared combined snapshot with explicit cross-source foreign keys. Veyra queries one selected file, not two attached uploads. No federation feature is claimed.
- Intended questions: registered people/accounts, app-open activity, paid net recorded USD cents, workspace plan grouping, existence/absence and an explicitly defined ordered conversion.
- Outside scope: predictive/causal claims, realized cash, taxes, sessions, retention and activation without definitions, historical plan changes, arbitrary customer data.

## 2. Tables and grain

| Table | One row / key | Identity and relationships |
|---|---|---|
| accounts | Workspace account; account_id PK | plan is a current snapshot, not historical plan at event time; region is workspace region |
| people | Registered person; person_id PK | registered_on is signup date; a person can belong to several accounts |
| memberships | One person/account relationship; composite PK(person_id,account_id) | person_id -> people.person_id; account_id -> accounts.account_id; role describes membership, not event activity |
| activity_log | Recorded event; event_id PK | actor_id -> people.person_id, workspace_id -> accounts.account_id in joined.db; NULL actor is anonymous, NULL workspace is unattributed |
| invoices | Recorded invoice/credit; invoice_id PK | workspace_id -> accounts.account_id in joined.db; usd_cents is a signed amount, status is paid or void |

Cross-source references exist as plain IDs in product.db, because SQLite cannot declare foreign keys into crm.db. The preparation step reads the two sources read-only, checks referenced keys while constructing joined.db, declares the real FKs there, and checks integrity. Source hashes before/after must match.

Do not join events to accounts via memberships: this can duplicate activity for multi-account people and attribute it to the wrong workspace. Group events by their own workspace_id. A person may generate activity in a workspace where they are not a member; that is intentional, not an orphan. Event IDs are not user identities. Repeated opens are separate event rows, but count the person once in distinct-user measures. No soft deletion is modeled; NULL keys are unknown, not synthetic user/account IDs.

## 3. Column and event vocabulary

- “customer”, “organization”, “workspace” mean accounts, not people. “user”, “person”, “actor” mean people; activity uses activity_log.actor_id.
- “opened the app”, “launch”, “app open” mean activity_log.action = app_open.
- “exported”, “downloaded a report” mean action = export.
- “signed in” means action = sign_in. A sign-in is not an app-open under this demo's active-user rule.
- “paid” means invoices.status = paid. Void invoices do not contribute to recorded revenue. Negative paid amounts are credits/refunds and reduce net amounts. Zero is numeric 0, not the string zero.
- Account plan values: free, pro, enterprise. Plan is not payment status and does not prove that a payment occurred.

## 4. Time contract

- Event occurrence: activity_log.occurred_at; signup: people.registered_on; invoice record date: invoices.issued_on.
- ISO dates/timestamps; date-only values represent UTC midnight. Offset timestamps normalize to UTC. Reporting timezone UTC, weeks start Monday, no local-DST reporting.
- March 2026 means [2026-03-01T00:00:00Z,2026-04-01T00:00:00Z). A local March 31 event with -02:00 offset can fall in April UTC; an April 1 +02:00 event can fall in March UTC.
- Relative “last seven days”, if requested, means seven complete UTC calendar days excluding today; no relative windows are used in these frozen demo questions.
- Unknown dates cannot satisfy a dated metric. No late-arrival model is provided. The snapshot watermark is a synthetic contract, not a live data-quality guarantee.

## 5. Explicit metric definitions

- Registered customers: COUNT(*) of accounts. Registered users: COUNT(*) of people, including inactive people.
- App opens: number of app_open event rows in the requested window, including anonymous rows. Duplicate records are not deduplicated for this metric.
- Active users: distinct non-NULL actor_id with app_open in the requested UTC window. Daily active users: same definition independently per UTC date, excluding missing actor IDs before grouping. Sparse output: emit only dates with at least one known active actor, not zero-only anonymous dates or a complete calendar series. This is a chosen demo definition, not a universal meaning of active.
- Recorded revenue: sum paid invoices.usd_cents, including negative credits and numeric zero, ignoring NULL amounts. All amounts are USD cents. All-time unless a window is specified. This is net recorded invoice amount, not verified cash collection or accounting recognition.
- Revenue by customer plan: inner join invoices.workspace_id -> accounts.account_id, then sum by current accounts.plan. Exclude unattributed workspace rows from plan groups. NULL amount records remain separately reportable; do not coerce them to known zero. Convert cents to dollars only if explicitly requested.
- Activity by plan: count event rows grouped through event.workspace_id, including anonymous actors with a known workspace; exclude unknown workspace from plan groups. Current plan snapshot only.
- Accounts without paid invoices: accounts for which no related invoice has status paid; a zero paid invoice still counts as a paid invoice.
- Converted users: distinct non-NULL actor IDs with an app_open followed by an export at or after its timestamp, across all workspaces and all available dates; missing dates do not qualify, equal timestamps do. Export before open does not qualify. No conversion percentage is requested; its denominator is otherwise undefined.
- Activation: undefined, must clarify.
- Retention: undefined; cohort entry, return action, horizon and maturity rule must be supplied, must clarify.
- Sessions: unavailable; no session ID or approved inactivity rule, must clarify.

## 6. Reviewed examples and counterexamples

These are development examples authored from the context, not hidden answers supplied to the planner. Executable reference SQL and Python-oracle expected rows are recorded separately in manifest.json. A computational SQL/Python cross-check is required before scoring; no independent human review is claimed.

1. “How many users?” -> registered people, not membership rows. Explicit request: Count people.
2. “Active users in March 2026” -> distinct app_open actors, UTC-normalized timestamps, exclude NULL actor/date; not all registrations, sign-ins or event rows.
3. “Revenue by customer plan” -> signed paid USD cents grouped through invoice.workspace_id, not actor membership or account plan price.
4. “Activity by account plan” -> event workspace determines account. A multi-account actor must not duplicate an event into every membership.
5. “Accounts with no paid invoices” -> filtered NOT EXISTS, not invoices with status other than paid.
6. “Daily active users” -> one count per actor per UTC date; anonymous opens do not form a user.
7. “Free invoice” is ambiguous between a free-plan account and zero numeric amount. Ask which definition; tests instead explicitly request usd_cents equals zero.
8. “Converted users” -> ordered app_open then export. An export before the actor's first open must not qualify by itself.
9. “Retention” -> clarification; do not invent a cohort or denominator from this brief.

## Per-question checklist and test delivery

Diagnostic questions are paired: raw wording and manually explicit wording. The service receives only the question plus discovered schema/samples, **not this file**. Raw questions using undefined aliases/metrics are expected to clarify; four self-contained raw controls are answerable. Explicit wording repeats known contract definitions but may still be unsupported by the current planner. This is not a test of automatic context ingestion or a fair before/after feature comparison; definitions and wording differ. No SQL reference or expected result enters generation.

All fixtures, context and questions are development-exposed. Reserved final evaluation artifacts are not accessed. Context cannot guarantee correctness; unsupported requests must remain withheld.
'''


def build(output):
    if output.exists():
        raise FileExistsError('Choose a new output directory; demo snapshots are never overwritten')
    output.mkdir(parents=True)
    crm=dict(accounts=ACCOUNTS,people=PEOPLE,memberships=MEMBERSHIPS)
    product=dict(activity_log=ACTIVITY,invoices=INVOICES)
    create(output/'crm.db',CRM_DDL,crm)
    create(output/'product.db',PRODUCT_DDL,product)
    before={name:digest(output/name) for name in ('crm.db','product.db')}
    source_rows={**read_tables(output/'crm.db',crm),**read_tables(output/'product.db',product)}
    create(output/'joined.db',JOINED_DDL,source_rows)
    if before!={name:digest(output/name) for name in before}:
        raise ValueError('Source files changed during preparation')
    context=output/'dataset-context.md'
    context.write_text(context_markdown(),encoding='utf-8')
    manifest=dict(version='independent-v1',suite_name='joined-context-demo-v1',context_revision=2,exposure='development-exposed-context-diagnostics',
        external_blind=False,oracle='Python source tuples and UTC datetime operations; independently executed reference SQL cross-check required',
        datasets=[dict(name='joined',file='joined.db',sha256=digest(output/'joined.db'),cases=make_cases())])
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    provenance=dict(role='development',synthetic=True,federation=False,context_automatically_loaded=False,
        source_hashes=before,combined_sha256=digest(output/'joined.db'),context_sha256=digest(context),
        manifest_sha256=digest(output/'manifest.json'),source_files_unchanged=True,
        row_counts={name:len(rows) for name,rows in source_rows.items()},
        preparation='Read-only source connections; insert into newly created combined database with declared cross-source FKs and integrity checks. No ATTACH or customer database mutation.',
        context_source='Filled dataset-context-template.md sections by synthetic demo author; manually explicit questions only, no semantic-layer configuration or human approval claim.')
    (output/'provenance.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=build(args.output)
    print(f"Created two source databases, joined.db, completed context and {len(result['datasets'][0]['cases'])} diagnostic cases")
