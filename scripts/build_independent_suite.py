"""Freeze internal evaluation fixtures; never import the query planner or learning exporter."""
import argparse
from collections import Counter, defaultdict
from contextlib import closing
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'independent-v1'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def grouped(rows, key, value=None):
    groups = defaultdict(list)
    for row in rows:
        groups[key(row)].append(row)
    return [[label, sum(value(r) for r in members) if value else len(members)]
            for label, members in sorted(groups.items())]


class Fixture:
    def __init__(self, name, path, ddl, tables):
        self.name, self.path, self.cases = name, path, []
        with closing(sqlite3.connect(path)) as db:
            db.executescript('PRAGMA foreign_keys=ON;' + ddl)
            for table, rows in tables.items():
                db.executemany(f'INSERT INTO {table} VALUES ({",".join("?" for _ in rows[0])})', rows)
            db.commit()
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError(f'Invalid fixture: {name}')

    def add(self, question, sql=None, expected=None, complexity='simple', tags=(), outcome='query', ordered=False):
        self.cases.append(dict(id=f'{self.name}-{len(self.cases)+1:02d}', question=question,
                               reference_sql=sql, expected_rows=expected, complexity=complexity,
                               tags=list(tags), expected_outcome=outcome, ordered=ordered))

    def finish(self):
        if len(self.cases) != 36:
            raise ValueError(f'{self.name} must contain 36 cases, got {len(self.cases)}')
        return dict(name=self.name, file=self.path.name, sha256=digest(self.path), cases=self.cases)


def education(path):
    learners = [(i, ['north', 'south', 'west'][i % 3], f'2026-01-{i:02d}') for i in range(1, 25)]
    courses = [(1, 'design'), (2, 'science'), (3, 'science'), (4, 'history')]
    enrollments = [(i, 1+(i*7)%24, 1+(i//5)%4, f'2026-0{2+i%2}-{1+i%27:02d}',
                    ['active', 'cancelled', 'complete'][i%3]) for i in range(1, 49)]
    views = [(i, 1+i%48, f'2026-03-{1+i%27:02d}', 10+i%20) for i in range(1, 121)]
    # Some completions precede views/enrollment: ordered funnels must exclude them.
    completions = [(i, i*3, f'2026-03-{1+i%27:02d}', None if i%5 == 0 else 40+i%61) for i in range(1, 17)]
    f = Fixture('education', path, '''
        CREATE TABLE learners(learner_id INTEGER PRIMARY KEY,region TEXT,registered_on TEXT);
        CREATE TABLE courses(course_id INTEGER PRIMARY KEY,subject TEXT);
        CREATE TABLE enrollments(enrollment_id INTEGER PRIMARY KEY,learner_id INTEGER REFERENCES learners,
          course_id INTEGER REFERENCES courses,joined_on TEXT,state TEXT);
        CREATE TABLE lesson_views(view_id INTEGER PRIMARY KEY,enrollment_id INTEGER REFERENCES enrollments,
          viewed_on TEXT,minutes INTEGER);
        CREATE TABLE completions(completion_id INTEGER PRIMARY KEY,enrollment_id INTEGER REFERENCES enrollments,
          completed_on TEXT,score INTEGER);''',
        dict(learners=learners, courses=courses, enrollments=enrollments, lesson_views=views, completions=completions))
    add = f.add
    for table, rows in [('learners', learners), ('courses', courses), ('enrollments', enrollments), ('lesson_views', views)]:
        add(f'How many {table.replace("_", " ")} are there?', f'SELECT COUNT(*) FROM {table}', [[len(rows)]], tags=['count'])
    add('How many different learners have enrolled?', 'SELECT COUNT(DISTINCT learner_id) FROM enrollments', [[len({e[1] for e in enrollments})]], tags=['distinct_users'])
    add('Count enrollments by state', 'SELECT state,COUNT(*) FROM enrollments GROUP BY state', grouped(enrollments, lambda e:e[4]), tags=['aggregation'])
    add('How many learners are in each region?', 'SELECT region,COUNT(*) FROM learners GROUP BY region', grouped(learners, lambda r:r[1]), tags=['aggregation'])
    add('Total minutes of lesson viewing', 'SELECT SUM(minutes) FROM lesson_views', [[sum(v[3] for v in views)]], tags=['aggregation'])
    add('Average nonmissing completion score', 'SELECT AVG(score) FROM completions', [[sum(c[3] for c in completions if c[3] is not None)/sum(c[3] is not None for c in completions)]], tags=['nulls'])
    add('How many completion scores are missing?', 'SELECT COUNT(*) FROM completions WHERE score IS NULL', [[sum(c[3] is None for c in completions)]], tags=['nulls'])
    for state in ('active', 'cancelled', 'complete'):
        add(f'List enrollments whose state is {state}', f"SELECT * FROM enrollments WHERE state='{state}'", [list(e) for e in enrollments if e[4]==state], tags=['filter'])
    add('Show enrollments joined in February 2026', "SELECT * FROM enrollments WHERE joined_on>='2026-02-01' AND joined_on<'2026-03-01'", [list(e) for e in enrollments if e[3]<'2026-03-01'], 'medium', ['date_window'])
    add('Show enrollments joined in March 2026', "SELECT * FROM enrollments WHERE joined_on>='2026-03-01' AND joined_on<'2026-04-01'", [list(e) for e in enrollments if e[3]>='2026-03-01'], 'medium', ['date_window'])
    add('Count lesson views on or after March 10 and before March 20, 2026', "SELECT COUNT(*) FROM lesson_views WHERE viewed_on>='2026-03-10' AND viewed_on<'2026-03-20'", [[sum('2026-03-10'<=v[2]<'2026-03-20' for v in views)]], 'medium', ['date_window'])
    add('Number of distinct viewing learners each day', 'SELECT v.viewed_on,COUNT(DISTINCT e.learner_id) FROM lesson_views v JOIN enrollments e ON e.enrollment_id=v.enrollment_id GROUP BY v.viewed_on', [[day, len({enrollments[v[1]-1][1] for v in views if v[2]==day})] for day in sorted({v[2] for v in views})], 'medium', ['join','distinct_users','date'])
    add('Enrollment counts by course subject', 'SELECT c.subject,COUNT(*) FROM enrollments e JOIN courses c ON c.course_id=e.course_id GROUP BY c.subject', grouped(enrollments, lambda e:courses[e[2]-1][1]), 'medium', ['join','aggregation'])
    add('Total viewing minutes by learner region', 'SELECT l.region,SUM(v.minutes) FROM lesson_views v JOIN enrollments e ON e.enrollment_id=v.enrollment_id JOIN learners l ON l.learner_id=e.learner_id GROUP BY l.region', grouped(views, lambda v:learners[enrollments[v[1]-1][1]-1][1], lambda v:v[3]), 'complex', ['join','aggregation'])
    inactive = [list(l) for l in learners if not any(e[1]==l[0] for e in enrollments)]
    add('List learners without an enrollment', 'SELECT l.* FROM learners l WHERE NOT EXISTS(SELECT 1 FROM enrollments e WHERE e.learner_id=l.learner_id)', inactive, 'medium', ['anti_join'])
    add('List courses without completions', 'SELECT c.* FROM courses c WHERE NOT EXISTS(SELECT 1 FROM enrollments e JOIN completions x ON x.enrollment_id=e.enrollment_id WHERE e.course_id=c.course_id)', [list(c) for c in courses if not any(enrollments[x[1]-1][2]==c[0] for x in completions)], 'complex', ['anti_join'])
    add('Enrollment counts by registration region and course subject', 'SELECT l.region,c.subject,COUNT(*) FROM enrollments e JOIN learners l ON l.learner_id=e.learner_id JOIN courses c ON c.course_id=e.course_id GROUP BY l.region,c.subject', [[region, subject, n] for (region,subject),n in Counter((learners[e[1]-1][1],courses[e[2]-1][1]) for e in enrollments).items()], 'complex', ['join','aggregation'])
    add('Daily total viewing minutes', 'SELECT viewed_on,SUM(minutes) FROM lesson_views GROUP BY viewed_on', grouped(views, lambda v:v[2], lambda v:v[3]), 'medium', ['date','aggregation'])
    add('Which three enrollments have the most viewing minutes? Break ties by enrollment ID ascending.', 'SELECT enrollment_id,SUM(minutes) AS total FROM lesson_views GROUP BY enrollment_id ORDER BY total DESC,enrollment_id ASC LIMIT 3', sorted(grouped(views, lambda v:v[1], lambda v:v[3]), key=lambda r:(-r[1],r[0]))[:3], 'medium', ['ranking'], ordered=True)
    add('Learners enrolled in at least two distinct courses', 'SELECT learner_id FROM enrollments GROUP BY learner_id HAVING COUNT(DISTINCT course_id)>=2', [[i] for i in sorted({e[1] for e in enrollments}) if len({e[2] for e in enrollments if e[1]==i})>=2], 'medium', ['having','distinct'])
    eligible = [e for e in enrollments if any(v[1]==e[0] and v[2]>=e[3] for v in views)]
    completed = [e for e in eligible if any(x[1]==e[0] and any(v[1]==e[0] and e[3]<=v[2]<=x[2] for v in views) for x in completions)]
    add('Count enrollments with a lesson view on or after their join date', 'SELECT COUNT(*) FROM enrollments e WHERE EXISTS(SELECT 1 FROM lesson_views v WHERE v.enrollment_id=e.enrollment_id AND v.viewed_on>=e.joined_on)', [[len(eligible)]], 'complex', ['funnel','date'])
    add('Count enrollments that joined, then viewed a lesson, then completed, allowing same-day steps', 'SELECT COUNT(*) FROM enrollments e WHERE EXISTS(SELECT 1 FROM lesson_views v JOIN completions c ON c.enrollment_id=v.enrollment_id WHERE v.enrollment_id=e.enrollment_id AND v.viewed_on>=e.joined_on AND c.completed_on>=v.viewed_on)', [[len(completed)]], 'complex', ['funnel','join'])
    add('What fraction of all enrollments joined then viewed then completed, allowing same-day steps?', 'SELECT COUNT(*)*1.0/(SELECT COUNT(*) FROM enrollments) FROM enrollments e WHERE EXISTS(SELECT 1 FROM lesson_views v JOIN completions c ON c.enrollment_id=v.enrollment_id WHERE v.enrollment_id=e.enrollment_id AND v.viewed_on>=e.joined_on AND c.completed_on>=v.viewed_on)', [[len(completed)/len(enrollments)]], 'complex', ['funnel','ratio'])
    add('List completions with scores at least 50', 'SELECT * FROM completions WHERE score>=50', [list(c) for c in completions if c[3] is not None and c[3]>=50], tags=['filter','nulls'])
    add('How many enrollments joined before March 1, 2026 but completed during March?', "SELECT COUNT(*) FROM enrollments e WHERE e.joined_on<'2026-03-01' AND EXISTS(SELECT 1 FROM completions c WHERE c.enrollment_id=e.enrollment_id AND c.completed_on>='2026-03-01' AND c.completed_on<'2026-04-01')", [[sum(e[3]<'2026-03-01' and any(c[1]==e[0] and '2026-03-01'<=c[2]<'2026-04-01' for c in completions) for e in enrollments)]], 'complex', ['join','date_window'])
    for q, tag in [('Show retention', 'ambiguous'), ('Show course revenue', 'missing_field'), ('Who are our best learners?', 'ambiguous'), ('Show conversion rate', 'ambiguous')]:
        add(q, complexity='undefined', tags=[tag], outcome='clarification')
    for q in ('Delete all learners', 'Drop the courses table'):
        add(q, complexity='invalid', tags=['write_request'], outcome='refusal')
    return f.finish()


def logistics(path):
    depots = [(1,'east'), (2,'west'), (3,'north'), (4,'south')]
    parcels = [(i, 1+i%4, 1+(i+1)%4, f'2026-03-{1+i%28:02d}', 100+i*11) for i in range(1, 41)]
    # Composite-key event stream and one-to-many ledger: careless joins multiply charges.
    stops = [(i, j, ['accepted','in_transit','delivered'][j], f'2026-03-{1+(i+j)%28:02d}') for i in range(1,41) for j in range(3) if not (j==2 and i%4==0)]
    charges = [(i, 1+i%40, ['USD','EUR'][i%2], (-100 if i%9==0 else 100+i*3), 'refund' if i%9==0 else 'shipping') for i in range(1,71)]
    f = Fixture('logistics',path, '''
        CREATE TABLE depots(depot_id INTEGER PRIMARY KEY,zone TEXT);
        CREATE TABLE parcels(parcel_id INTEGER PRIMARY KEY,origin_depot INTEGER REFERENCES depots,
          destination_depot INTEGER REFERENCES depots,shipped_on TEXT,weight_grams INTEGER);
        CREATE TABLE checkpoints(parcel_id INTEGER REFERENCES parcels,sequence_no INTEGER,stage TEXT,
          occurred_on TEXT,PRIMARY KEY(parcel_id,sequence_no));
        CREATE TABLE charges(charge_id INTEGER PRIMARY KEY,parcel_id INTEGER REFERENCES parcels,
          currency TEXT,amount_cents INTEGER,kind TEXT);''', dict(depots=depots,parcels=parcels,checkpoints=stops,charges=charges))
    add=f.add
    for table, rows in [('depots',depots),('parcels',parcels),('checkpoints',stops),('charges',charges)]:
        add(f'Count all {table}', f'SELECT COUNT(*) FROM {table}', [[len(rows)]], tags=['count'])
    add('How many distinct parcels have checkpoints?', 'SELECT COUNT(DISTINCT parcel_id) FROM checkpoints', [[len({s[0] for s in stops})]], tags=['distinct'])
    add('Count checkpoints by stage', 'SELECT stage,COUNT(*) FROM checkpoints GROUP BY stage', grouped(stops,lambda s:s[2]), tags=['aggregation'])
    add('Total parcel weight in grams', 'SELECT SUM(weight_grams) FROM parcels', [[sum(p[4] for p in parcels)]], tags=['aggregation','units'])
    add('Average parcel weight in grams', 'SELECT AVG(weight_grams) FROM parcels', [[sum(p[4] for p in parcels)/len(parcels)]], tags=['aggregation'])
    add('Net charged cents grouped by currency, including refunds', 'SELECT currency,SUM(amount_cents) FROM charges GROUP BY currency', grouped(charges,lambda c:c[2],lambda c:c[3]), tags=['aggregation','currency'])
    add('How many negative ledger charges exist?', 'SELECT COUNT(*) FROM charges WHERE amount_cents<0', [[sum(c[3]<0 for c in charges)]], tags=['filter'])
    for stage in ('accepted','in_transit','delivered'):
        add(f'List checkpoints at stage {stage}',f"SELECT * FROM checkpoints WHERE stage='{stage}'",[list(s) for s in stops if s[2]==stage],tags=['filter'])
    add('List parcels shipped from March 10 through March 19, 2026 inclusive', "SELECT * FROM parcels WHERE shipped_on>='2026-03-10' AND shipped_on<'2026-03-20'",[list(p) for p in parcels if '2026-03-10'<=p[3]<'2026-03-20'],'medium',['date_window'])
    add('Daily count of parcels shipped', 'SELECT shipped_on,COUNT(*) FROM parcels GROUP BY shipped_on',grouped(parcels,lambda p:p[3]),'medium',['date','aggregation'])
    add('Count distinct delivered parcels per day', "SELECT occurred_on,COUNT(DISTINCT parcel_id) FROM checkpoints WHERE stage='delivered' GROUP BY occurred_on",[[day,len({s[0] for s in stops if s[2]=='delivered' and s[3]==day})] for day in sorted({s[3] for s in stops if s[2]=='delivered'})],'medium',['distinct','date'])
    add('Parcel counts by origin zone', 'SELECT d.zone,COUNT(*) FROM parcels p JOIN depots d ON d.depot_id=p.origin_depot GROUP BY d.zone',grouped(parcels,lambda p:depots[p[1]-1][1]),'medium',['join'])
    add('Parcel counts by destination zone', 'SELECT d.zone,COUNT(*) FROM parcels p JOIN depots d ON d.depot_id=p.destination_depot GROUP BY d.zone',grouped(parcels,lambda p:depots[p[2]-1][1]),'medium',['join','ambiguous_join_resolved'])
    add('Parcel counts by origin zone and destination zone', 'SELECT o.zone AS origin_zone,d.zone AS destination_zone,COUNT(*) FROM parcels p JOIN depots o ON o.depot_id=p.origin_depot JOIN depots d ON d.depot_id=p.destination_depot GROUP BY o.zone,d.zone',[[o,d,n] for (o,d),n in Counter((depots[p[1]-1][1],depots[p[2]-1][1]) for p in parcels).items()],'complex',['self_join_roles'])
    add('Net cents by origin zone and currency, counting each ledger charge once', 'SELECT d.zone,c.currency,SUM(c.amount_cents) FROM charges c JOIN parcels p ON p.parcel_id=c.parcel_id JOIN depots d ON d.depot_id=p.origin_depot GROUP BY d.zone,c.currency',[[z,cc,sum(c[3] for c in charges if depots[parcels[c[1]-1][1]-1][1]==z and c[2]==cc)] for z,cc in sorted({(depots[parcels[c[1]-1][1]-1][1],c[2]) for c in charges})],'complex',['join','currency','fanout'])
    add('List parcels without a delivered checkpoint', "SELECT p.* FROM parcels p WHERE NOT EXISTS(SELECT 1 FROM checkpoints s WHERE s.parcel_id=p.parcel_id AND s.stage='delivered')",[list(p) for p in parcels if not any(s[0]==p[0] and s[2]=='delivered' for s in stops)],'medium',['anti_join'])
    add('List parcels with no ledger charges', 'SELECT p.* FROM parcels p WHERE NOT EXISTS(SELECT 1 FROM charges c WHERE c.parcel_id=p.parcel_id)',[list(p) for p in parcels if not any(c[1]==p[0] for c in charges)],'medium',['anti_join','empty_result'])
    add('How many parcels have more than one ledger charge?', 'SELECT COUNT(*) FROM (SELECT parcel_id FROM charges GROUP BY parcel_id HAVING COUNT(*)>1)',[[sum(n>1 for n in Counter(c[1] for c in charges).values())]],'medium',['having'])
    add('Three heaviest parcels, weight descending then parcel ID ascending', 'SELECT parcel_id,weight_grams FROM parcels ORDER BY weight_grams DESC,parcel_id ASC LIMIT 3',[[p[0],p[4]] for p in sorted(parcels,key=lambda p:(-p[4],p[0]))[:3]],'medium',['ranking'],ordered=True)
    add('How many parcels have both a shipping charge and a refund?', "SELECT COUNT(*) FROM parcels p WHERE EXISTS(SELECT 1 FROM charges c WHERE c.parcel_id=p.parcel_id AND c.kind='shipping') AND EXISTS(SELECT 1 FROM charges c WHERE c.parcel_id=p.parcel_id AND c.kind='refund')",[[sum(any(c[1]==p[0] and c[4]=='shipping' for c in charges) and any(c[1]==p[0] and c[4]=='refund' for c in charges) for p in parcels)]],'complex',['exists'])
    delivered=[p for p in parcels if any(s[0]==p[0] and s[2]=='delivered' and s[3]>=p[3] for s in stops)]
    ordered=[p for p in parcels if any(a[0]==p[0] and a[2]=='accepted' and p[3]<=a[3] and any(b[0]==p[0] and b[2]=='delivered' and b[3]>=a[3] for b in stops) for a in stops)]
    add('Count parcels delivered on or after their shipping date', "SELECT COUNT(*) FROM parcels p WHERE EXISTS(SELECT 1 FROM checkpoints s WHERE s.parcel_id=p.parcel_id AND s.stage='delivered' AND s.occurred_on>=p.shipped_on)",[[len(delivered)]],'complex',['funnel'])
    add('Count parcels shipped then accepted then delivered, allowing same-day steps', "SELECT COUNT(*) FROM parcels p WHERE EXISTS(SELECT 1 FROM checkpoints a JOIN checkpoints b ON a.parcel_id=b.parcel_id WHERE a.parcel_id=p.parcel_id AND a.stage='accepted' AND b.stage='delivered' AND a.occurred_on>=p.shipped_on AND b.occurred_on>=a.occurred_on)",[[len(ordered)]],'complex',['funnel','join'])
    add('Fraction of all parcels shipped then accepted then delivered, allowing same-day steps', "SELECT COUNT(*)*1.0/(SELECT COUNT(*) FROM parcels) FROM parcels p WHERE EXISTS(SELECT 1 FROM checkpoints a JOIN checkpoints b ON a.parcel_id=b.parcel_id WHERE a.parcel_id=p.parcel_id AND a.stage='accepted' AND b.stage='delivered' AND a.occurred_on>=p.shipped_on AND b.occurred_on>=a.occurred_on)",[[len(ordered)/len(parcels)]],'complex',['funnel','ratio'])
    add('Net USD cents for parcels shipped before March 15, 2026', "SELECT SUM(c.amount_cents) FROM charges c JOIN parcels p ON p.parcel_id=c.parcel_id WHERE c.currency='USD' AND p.shipped_on<'2026-03-15'",[[sum(c[3] for c in charges if c[2]=='USD' and parcels[c[1]-1][3]<'2026-03-15')]],'medium',['join','date_window','currency'])
    add('List parcels heavier than 400 grams', 'SELECT * FROM parcels WHERE weight_grams>400',[list(p) for p in parcels if p[4]>400],tags=['filter'])
    for q,tag in [('Show parcel counts by zone','ambiguous'),('What is total revenue in dollars?','currency_undefined'),('Show customer churn','missing_field'),('Which depot is best?','ambiguous')]:
        add(q,complexity='undefined',tags=[tag],outcome='clarification')
    for q in ('Update every parcel weight to zero','Delete all charges'):
        add(q,complexity='invalid',tags=['write_request'],outcome='refusal')
    return f.finish()


def collaboration(path):
    orgs=[(1,'free'),(2,'team'),(3,'team'),(4,'enterprise'),(5,'free')]
    people=[(i,f'2026-01-{i:02d}') for i in range(1,19)]
    membership=[(i,o,'owner' if i%5==0 else 'member') for i in range(1,19) for o in range(1,6) if (i+o)%3==0]
    actions=[(1,'sign_in'),(2,'document_create'),(3,'share_link')]
    logs=[(i,1+i%18,1+(i//3)%5,1+(i//7)%3,f'2026-03-{1+i%28:02d}') for i in range(1,101)]
    invoices=[(i,1+i%5,1000+i*100,f'2026-03-{1+i%28:02d}', 'paid' if i%3 else 'void') for i in range(1,16)]
    f=Fixture('collaboration',path, '''
        CREATE TABLE organizations(org_id INTEGER PRIMARY KEY,plan TEXT);
        CREATE TABLE people(person_id INTEGER PRIMARY KEY,registered_on TEXT);
        CREATE TABLE memberships(person_id INTEGER REFERENCES people,org_id INTEGER REFERENCES organizations,
          role TEXT,PRIMARY KEY(person_id,org_id));
        CREATE TABLE action_catalog(action_id INTEGER PRIMARY KEY,label TEXT);
        CREATE TABLE audit_log(log_id INTEGER PRIMARY KEY,actor_id INTEGER REFERENCES people,
          workspace_id INTEGER REFERENCES organizations,action_id INTEGER REFERENCES action_catalog,occurred_on TEXT);
        CREATE TABLE invoices(invoice_id INTEGER PRIMARY KEY,org_id INTEGER REFERENCES organizations,
          usd_cents INTEGER,issued_on TEXT,state TEXT);''',dict(organizations=orgs,people=people,memberships=membership,action_catalog=actions,audit_log=logs,invoices=invoices))
    add=f.add
    for table,rows in [('organizations',orgs),('people',people),('memberships',membership),('audit_log',logs)]:
        add(f'How many {table.replace("_"," ")} records exist?',f'SELECT COUNT(*) FROM {table}',[[len(rows)]],tags=['count'])
    add('How many distinct people belong to an organization?', 'SELECT COUNT(DISTINCT person_id) FROM memberships',[[len({m[0] for m in membership})]],tags=['distinct_users'])
    add('Count organizations by plan', 'SELECT plan,COUNT(*) FROM organizations GROUP BY plan',grouped(orgs,lambda o:o[1]),tags=['aggregation'])
    add('Count memberships by role', 'SELECT role,COUNT(*) FROM memberships GROUP BY role',grouped(membership,lambda m:m[2]),tags=['aggregation'])
    add('Sum invoice amounts in USD cents including all states', 'SELECT SUM(usd_cents) FROM invoices',[[sum(i[2] for i in invoices)]],tags=['aggregation','units'])
    add('Average paid invoice amount in USD cents', "SELECT AVG(usd_cents) FROM invoices WHERE state='paid'",[[sum(i[2] for i in invoices if i[4]=='paid')/sum(i[4]=='paid' for i in invoices)]],tags=['aggregation'])
    add('List void invoices', "SELECT * FROM invoices WHERE state='void'",[list(i) for i in invoices if i[4]=='void'],tags=['filter'])
    for label in ('sign_in','document_create','share_link'):
        add(f'List audit log records for {label}',f"SELECT l.* FROM audit_log l JOIN action_catalog a ON a.action_id=l.action_id WHERE a.label='{label}'",[list(l) for l in logs if actions[l[3]-1][1]==label],'medium',['join','event_catalog'])
    add('List invoices issued March 1 through March 9, 2026 inclusive', "SELECT * FROM invoices WHERE issued_on>='2026-03-01' AND issued_on<'2026-03-10'",[list(i) for i in invoices if '2026-03-01'<=i[3]<'2026-03-10'],'medium',['date_window'])
    add('Daily distinct active people from the audit log', 'SELECT occurred_on,COUNT(DISTINCT actor_id) FROM audit_log GROUP BY occurred_on',[[day,len({l[1] for l in logs if l[4]==day})] for day in sorted({l[4] for l in logs})],'medium',['distinct_users','date'])
    add('Distinct active people per workspace, not membership counts', 'SELECT workspace_id,COUNT(DISTINCT actor_id) FROM audit_log GROUP BY workspace_id',[[o[0],len({l[1] for l in logs if l[2]==o[0]})] for o in orgs],'medium',['distinct_users'])
    add('Count audit actions by their catalog label', 'SELECT a.label,COUNT(*) FROM audit_log l JOIN action_catalog a ON a.action_id=l.action_id GROUP BY a.label',grouped(logs,lambda l:actions[l[3]-1][1]),'medium',['join','event_catalog'])
    add('Count membership relationships by organization plan', 'SELECT o.plan,COUNT(*) FROM memberships m JOIN organizations o ON o.org_id=m.org_id GROUP BY o.plan',grouped(membership,lambda m:orgs[m[1]-1][1]),'medium',['join','many_to_many'])
    add('Distinct members by organization plan, deduplicating people across organizations of the same plan', 'SELECT o.plan,COUNT(DISTINCT m.person_id) FROM memberships m JOIN organizations o ON o.org_id=m.org_id GROUP BY o.plan',[[plan,len({m[0] for m in membership if orgs[m[1]-1][1]==plan})] for plan in sorted({o[1] for o in orgs})],'complex',['join','distinct_users','many_to_many'])
    add('Paid invoice USD cents by organization plan without membership fanout', "SELECT o.plan,SUM(i.usd_cents) FROM invoices i JOIN organizations o ON o.org_id=i.org_id WHERE i.state='paid' GROUP BY o.plan",grouped([i for i in invoices if i[4]=='paid'],lambda i:orgs[i[1]-1][1],lambda i:i[2]),'medium',['join','fanout'])
    add('List people with no memberships', 'SELECT p.* FROM people p WHERE NOT EXISTS(SELECT 1 FROM memberships m WHERE m.person_id=p.person_id)',[list(p) for p in people if not any(m[0]==p[0] for m in membership)],'medium',['anti_join','empty_result'])
    add('List organizations with no paid invoices', "SELECT o.* FROM organizations o WHERE NOT EXISTS(SELECT 1 FROM invoices i WHERE i.org_id=o.org_id AND i.state='paid')",[list(o) for o in orgs if not any(i[1]==o[0] and i[4]=='paid' for i in invoices)],'medium',['anti_join'])
    add('People who belong to more than one organization', 'SELECT person_id FROM memberships GROUP BY person_id HAVING COUNT(*)>1',[[p[0]] for p in people if sum(m[0]==p[0] for m in membership)>1],'medium',['having','many_to_many'])
    add('Top three actors by audit record count, breaking ties by actor ID ascending', 'SELECT actor_id,COUNT(*) AS n FROM audit_log GROUP BY actor_id ORDER BY n DESC,actor_id ASC LIMIT 3',sorted(grouped(logs,lambda l:l[1]),key=lambda r:(-r[1],r[0]))[:3],'medium',['ranking'],ordered=True)
    add('Count audit log records from people who are not members of that workspace', 'SELECT COUNT(*) FROM audit_log l WHERE NOT EXISTS(SELECT 1 FROM memberships m WHERE m.person_id=l.actor_id AND m.org_id=l.workspace_id)',[[sum(not any(m[0]==l[1] and m[1]==l[2] for m in membership) for l in logs)]],'complex',['anti_join','composite_relationship'])
    # Funnel is per person across workspaces; explicit question avoids an implicit scope definition.
    signed={l[1] for l in logs if l[3]==1}
    creators={p for p in signed if any(a[1]==p and a[3]==1 and any(b[1]==p and b[3]==2 and b[4]>=a[4] for b in logs) for a in logs)}
    sharers={p for p in creators if any(a[1]==p and a[3]==1 and any(b[1]==p and b[3]==2 and b[4]>=a[4] and any(c[1]==p and c[3]==3 and c[4]>=b[4] for c in logs) for b in logs) for a in logs)}
    add('Count distinct people who signed in then created a document across any workspaces, allowing same-day steps', 'SELECT COUNT(DISTINCT a.actor_id) FROM audit_log a JOIN audit_log b ON b.actor_id=a.actor_id JOIN action_catalog x ON x.action_id=a.action_id JOIN action_catalog y ON y.action_id=b.action_id WHERE x.label=\'sign_in\' AND y.label=\'document_create\' AND b.occurred_on>=a.occurred_on',[[len(creators)]],'complex',['funnel','event_catalog','join'])
    add('Count distinct people who signed in, then created a document, then shared a link across any workspaces, allowing same-day steps', "SELECT COUNT(DISTINCT a.actor_id) FROM audit_log a JOIN audit_log b ON b.actor_id=a.actor_id JOIN audit_log c ON c.actor_id=a.actor_id WHERE a.action_id=(SELECT action_id FROM action_catalog WHERE label='sign_in') AND b.action_id=(SELECT action_id FROM action_catalog WHERE label='document_create') AND c.action_id=(SELECT action_id FROM action_catalog WHERE label='share_link') AND b.occurred_on>=a.occurred_on AND c.occurred_on>=b.occurred_on",[[len(sharers)]],'complex',['funnel','event_catalog'])
    add('Fraction of all registered people who signed in then created then shared across any workspaces, allowing same-day steps', "SELECT COUNT(DISTINCT a.actor_id)*1.0/(SELECT COUNT(*) FROM people) FROM audit_log a JOIN audit_log b ON b.actor_id=a.actor_id JOIN audit_log c ON c.actor_id=a.actor_id WHERE a.action_id=1 AND b.action_id=2 AND c.action_id=3 AND b.occurred_on>=a.occurred_on AND c.occurred_on>=b.occurred_on",[[len(sharers)/len(people)]],'complex',['funnel','ratio'])
    add('Count distinct actors active March 10 through March 19, 2026 inclusive', "SELECT COUNT(DISTINCT actor_id) FROM audit_log WHERE occurred_on>='2026-03-10' AND occurred_on<'2026-03-20'",[[len({l[1] for l in logs if '2026-03-10'<=l[4]<'2026-03-20'})]],'medium',['date_window','distinct_users'])
    add('Count audit actions by organization plan and action label', 'SELECT o.plan,a.label,COUNT(*) FROM audit_log l JOIN organizations o ON o.org_id=l.workspace_id JOIN action_catalog a ON a.action_id=l.action_id GROUP BY o.plan,a.label',[[p,a,n] for (p,a),n in Counter((orgs[l[2]-1][1],actions[l[3]-1][1]) for l in logs).items()],'complex',['join','aggregation'])
    for q,tag in [('Show user activation','ambiguous'),('Calculate session duration','missing_field'),('Show retention by plan','ambiguous'),('Show revenue per user','ambiguous')]:
        add(q,complexity='undefined',tags=[tag],outcome='clarification')
    for q in ('Delete all people','Drop the memberships table'):
        add(q,complexity='invalid',tags=['write_request'],outcome='refusal')
    return f.finish()


def build(output):
    if output.exists():
        raise FileExistsError('Choose a new suite directory; frozen fixtures are never overwritten')
    output.mkdir(parents=True)
    datasets=[builder(output/f'{name}.db') for name,builder in
              [('education',education),('logistics',logistics),('collaboration',collaboration)]]
    manifest=dict(version=VERSION, exposure='authored-not-used-for-planner-tuning',
                  external_blind=False, final_claim='Internal author-separated synthetic baseline, not external blind accuracy',
                  oracle='Python collection operations on source tuples, separate from SQLite reference execution',
                  datasets=datasets)
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'datasets/evaluation/independent-v1')
    args=parser.parse_args()
    result=build(args.output)
    print(f"Frozen {sum(len(d['cases']) for d in result['datasets'])} cases across {len(result['datasets'])} schemas")
