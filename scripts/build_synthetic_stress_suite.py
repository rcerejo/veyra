"""Development-only synthetic stress fixtures. Never imports the planner or final-set tooling."""
import argparse
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import sqlite3

ROOT = Path(__file__).resolve().parents[1]


def groups(rows, key, value=None):
    result = defaultdict(list)
    for row in rows:
        result[key(row)].append(row)
    return [[k, sum(value(r) for r in v) if value else len(v)] for k, v in sorted(result.items())]


def utc_day(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).date().isoformat()


class Fixture:
    def __init__(self, path, name, ddl, tables):
        self.path, self.name, self.cases = path, name, []
        with closing(sqlite3.connect(path)) as db:
            db.executescript('PRAGMA foreign_keys=ON;' + ddl)
            for table, rows in tables.items():
                db.executemany(f'INSERT INTO {table} VALUES ({",".join("?" for _ in rows[0])})', rows)
            db.commit()
            assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            assert not db.execute('PRAGMA foreign_key_check').fetchall()

    def add(self, question, sql=None, rows=None, complexity='simple', tags=(), outcome='query', ordered=False):
        self.cases.append(dict(id=f'{self.name}-{len(self.cases)+1:02d}', question=question,
            reference_sql=sql, expected_rows=rows, expected_outcome=outcome,
            complexity=complexity, tags=list(tags), ordered=ordered))

    def finish(self):
        assert len(self.cases) == 30
        return dict(name=self.name, file=self.path.name,
            sha256=hashlib.sha256(self.path.read_bytes()).hexdigest(), cases=self.cases)


def common(f, entities, facts, dimensions, names):
    """Shared operation controls, not 60 independently diverse linguistic constructions."""
    entity, eid, region, fact, fid, fk, dim, did, dfk, label, stamp, amount, state = names
    # Source dictionaries keep Python expected results independent of SQL evaluation.
    a = f.add
    a(f'How many {entity} are there?', f'SELECT COUNT(*) FROM {entity}', [[len(entities)]], tags=['count'])
    a(f'How many {fact} are there?', f'SELECT COUNT(*) FROM {fact}', [[len(facts)]], tags=['count'])
    a(f'How many {dim} are there?', f'SELECT COUNT(*) FROM {dim}', [[len(dimensions)]], tags=['count'])
    values = [r[amount] for r in facts if r[amount] is not None]
    a(f'Total {amount} from {fact}', f'SELECT SUM({amount}) FROM {fact}', [[sum(values)]], tags=['sum'])
    a(f'Average nonmissing {amount} from {fact}', f'SELECT AVG({amount}) FROM {fact}', [[sum(values)/len(values)]], tags=['average','nulls'])
    a(f'Count {fact} where {amount} is missing', f'SELECT COUNT(*) FROM {fact} WHERE {amount} IS NULL', [[sum(r[amount] is None for r in facts)]], tags=['nulls'])
    for choice in ('complete', 'cancelled'):
        a(f'List {fact} whose {state} is {choice}', f"SELECT * FROM {fact} WHERE {state}='{choice}'", [list(r.values()) for r in facts if r[state] == choice], tags=['filter'])
    a(f'Count {fact} by {state}', f'SELECT {state},COUNT(*) FROM {fact} GROUP BY {state}', groups(facts, lambda r:r[state]), tags=['grouping'])
    a(f'Count distinct {fk} from {fact}', f'SELECT COUNT(DISTINCT {fk}) FROM {fact}', [[len({r[fk] for r in facts if r[fk] is not None})]], tags=['distinct','nulls'])
    march = [r for r in facts if r[stamp] and '2026-03-01' <= utc_day(r[stamp]) < '2026-04-01']
    a(f'Count {fact} during March 2026', f"SELECT COUNT(*) FROM {fact} WHERE julianday({stamp})>=julianday('2026-03-01') AND julianday({stamp})<julianday('2026-04-01')", [[len(march)]], 'medium', ['date_window','utc'])
    window = [r for r in facts if r[stamp] and '2026-03-10' <= utc_day(r[stamp]) < '2026-03-20']
    a(f'Count {fact} on or after March 10 and before March 20, 2026', f"SELECT COUNT(*) FROM {fact} WHERE julianday({stamp})>=julianday('2026-03-10') AND julianday({stamp})<julianday('2026-03-20')", [[len(window)]], 'medium', ['date_window','boundaries'])
    dated = [r for r in facts if r[stamp]]
    a(f'Daily count of {fact}, excluding missing {stamp}, using UTC dates', f'SELECT DATE({stamp}),COUNT(*) FROM {fact} WHERE {stamp} IS NOT NULL GROUP BY DATE({stamp})', groups(dated, lambda r:utc_day(r[stamp])), 'medium', ['daily','utc','nulls'])
    observed = {r[fk] for r in facts}
    a(f'List {entity} with at least one {fact}', f'SELECT e.* FROM {entity} e WHERE EXISTS(SELECT 1 FROM {fact} f WHERE f.{fk}=e.{eid})', [list(r.values()) for r in entities if r[eid] in observed], 'medium', ['existence','duplicates'])
    a(f'List {entity} without any {fact}', f'SELECT e.* FROM {entity} e WHERE NOT EXISTS(SELECT 1 FROM {fact} f WHERE f.{fk}=e.{eid})', [list(r.values()) for r in entities if r[eid] not in observed], 'medium', ['anti_join','nulls'])
    byid = {r[eid]:r for r in entities}
    joined = [r for r in facts if r[fk] in byid]
    a(f'Count {fact} by {entity} {region}, excluding rows without a {entity} relationship', f'SELECT e.{region},COUNT(*) FROM {fact} f JOIN {entity} e ON e.{eid}=f.{fk} GROUP BY e.{region}', groups(joined, lambda r:byid[r[fk]][region]), 'medium', ['join','grouping'])
    ranked = sorted(facts, key=lambda r:(-(r[amount] if r[amount] is not None else float('-inf')), r[fid]))[:3]
    a(f'Show the three {fact} with highest {amount}, breaking ties by {fid} ascending; put missing amounts last', f'SELECT * FROM {fact} ORDER BY {amount} DESC,{fid} ASC LIMIT 3', [list(r.values()) for r in ranked], 'medium', ['ranking','ties','nulls'], ordered=True)
    counts = Counter(r[fk] for r in facts if r[fk] is not None)
    a(f'Which {fk} have at least four {fact}? Exclude missing IDs', f'SELECT {fk} FROM {fact} WHERE {fk} IS NOT NULL GROUP BY {fk} HAVING COUNT(*)>=4', [[k] for k,v in sorted(counts.items()) if v>=4], 'medium', ['having','distinct'])
    a(f'Count {fact} where {amount} is zero', f'SELECT COUNT(*) FROM {fact} WHERE {amount}=0', [[sum(r[amount] == 0 for r in facts)]], tags=['zero'])
    a(f'Count {fact} with missing {fk}', f'SELECT COUNT(*) FROM {fact} WHERE {fk} IS NULL', [[sum(r[fk] is None for r in facts)]], tags=['null_relationship'])
    a(f'Show activation for {entity}', complexity='ambiguous', tags=['undefined_metric'], outcome='clarification')
    a(f'Predict next month revenue from {fact} with a guaranteed confidence interval', complexity='ambiguous', tags=['unsupported_inference'], outcome='clarification')
    a(f'Delete all {fact}', complexity='invalid', tags=['write'], outcome='refusal')
    a(f'Update {fact} set {amount} to zero', complexity='invalid', tags=['write'], outcome='refusal')


def records(seed, names):
    rng = random.Random(seed)
    entity, eid, region, fact, fid, fk, dim, did, dfk, label, stamp, amount, state = names
    entities = [{eid:i, region:('east','west','central')[i%3], 'registered_on':f'2026-02-{i:02d}'} for i in range(1,13)]
    dimensions = [{did:i, label:v} for i,v in enumerate(('standard','premium','unused'),1)]
    dates = ['2026-02-28','2026-03-01','2026-03-09','2026-03-10','2026-03-19','2026-03-20',
             '2026-03-29','2026-03-30','2026-03-31T23:30:00-02:00','2026-04-01T00:30:00+02:00',None]
    facts = [{fid:i, fk:None if i%11==0 else rng.randint(1,9), dfk:1+i%2,
        stamp:dates[(i-1)%len(dates)], amount:None if i%7==0 else (0 if i%5==0 else rng.choice([10,20,20,50])),
        state:('complete','pending','cancelled')[i%3]} for i in range(1,37+seed%7)]
    return entities, facts, dimensions


def build_domain(output, domain, seed):
    configs = {
        'rentals': ('renters','renter_id','district','bookings','booking_id','renter_id','equipment','equipment_id','equipment_id','tier','booked_at','fee','status'),
        'support': ('requesters','requester_id','territory','tickets','ticket_id','requester_id','queues','queue_id','queue_id','category','opened_at','effort','state'),
        'billing': ('subscribers','subscriber_id','market','charges','charge_id','subscriber_id','plans','plan_id','plan_id','level','charged_at','amount','status'),
    }
    names = configs[domain]
    entity,eid,region,fact,fid,fk,dim,did,dfk,label,stamp,amount,state = names
    entities,facts,dimensions = records(seed,names)
    ddl = f'''CREATE TABLE {entity}({eid} INTEGER PRIMARY KEY,{region} TEXT,registered_on TEXT);
        CREATE TABLE {dim}({did} INTEGER PRIMARY KEY,{label} TEXT);
        CREATE TABLE {fact}({fid} INTEGER PRIMARY KEY,{fk} INTEGER REFERENCES {entity},
          {dfk} INTEGER REFERENCES {dim},{stamp} TEXT,{amount} INTEGER,{state} TEXT);'''
    tables = {entity:[tuple(r.values()) for r in entities],dim:[tuple(r.values()) for r in dimensions],fact:[tuple(r.values()) for r in facts]}
    if domain == 'rentals':
        ddl += '''CREATE TABLE inspections(inspection_id INTEGER PRIMARY KEY,booking_id INTEGER REFERENCES bookings,
            inspector_id INTEGER REFERENCES renters,reviewer_id INTEGER REFERENCES renters,inspected_at TEXT,score INTEGER);'''
        inspections = [(1,1,1,2,'2026-03-01',80),(2,1,1,3,'2026-03-02',90),
                       (3,2,3,1,'2026-03-01',None),(4,3,None,2,None,0),(5,4,2,2,'2026-04-01',80)]
        tables['inspections'] = inspections
    elif domain == 'support':
        ddl += '''CREATE TABLE tags(namespace TEXT,code TEXT,label TEXT,PRIMARY KEY(namespace,code));
            CREATE TABLE ticket_tags(ticket_id INTEGER REFERENCES tickets,namespace TEXT,code TEXT,
              PRIMARY KEY(ticket_id,namespace,code),FOREIGN KEY(namespace,code) REFERENCES tags(namespace,code));
            CREATE TABLE responses(response_id INTEGER PRIMARY KEY,ticket_id INTEGER REFERENCES tickets,sent_at TEXT);'''
        tags = [('priority','p1','urgent'),('product','p1','payments'),('priority','p2','normal')]
        links = [(1,'priority','p1'),(1,'product','p1'),(2,'priority','p2'),(3,'priority','p1')]
        responses = [(1,1,'2026-03-02'),(2,1,'2026-03-03'),(3,2,'2026-02-20'),(4,4,None)]
        tables.update(tags=tags,ticket_tags=links,responses=responses)
    else:
        ddl += '''CREATE TABLE event_kinds(kind_id INTEGER PRIMARY KEY,label TEXT);
            CREATE TABLE usage_events(event_id INTEGER PRIMARY KEY,subscriber_id INTEGER REFERENCES subscribers,
              kind_id INTEGER REFERENCES event_kinds,occurred_at TEXT);'''
        kinds = [(1,'app_open'),(2,'export'),(3,'unused_kind')]
        events = [(1,1,1,'2026-03-01'),(2,1,1,'2026-03-01'),(3,1,2,'2026-03-02'),
            (4,2,2,'2026-02-28'),(5,2,1,'2026-03-02'),(6,3,1,'2026-03-29'),
            (7,3,2,'2026-03-30'),(8,None,1,None),(9,4,1,'2026-03-31T23:30:00-02:00')]
        tables.update(event_kinds=kinds,usage_events=events)
    f = Fixture(output/f'{domain}.db',domain,ddl,tables)
    common(f,entities,facts,dimensions,names)
    a = f.add
    if domain == 'rentals':
        a('Count distinct inspectors from inspections', 'SELECT COUNT(DISTINCT inspector_id) FROM inspections', [[len({r[2] for r in inspections if r[2] is not None})]], 'medium', ['role','distinct'])
        a('Count distinct reviewers from inspections', 'SELECT COUNT(DISTINCT reviewer_id) FROM inspections', [[len({r[3] for r in inspections})]], 'medium', ['role','distinct'])
        a('Count inspections where inspector and reviewer are the same renter', 'SELECT COUNT(*) FROM inspections WHERE inspector_id=reviewer_id', [[sum(r[2] is not None and r[2]==r[3] for r in inspections)]], 'complex', ['parallel_roles','column_comparison'])
        a('List bookings without inspections', 'SELECT b.* FROM bookings b WHERE NOT EXISTS(SELECT 1 FROM inspections i WHERE i.booking_id=b.booking_id)', [list(r.values()) for r in facts if not any(i[1]==r[fid] for i in inspections)], 'medium', ['anti_join','duplicates'])
        a('Count bookings with an inspection score of at least 80', 'SELECT COUNT(*) FROM bookings b WHERE EXISTS(SELECT 1 FROM inspections i WHERE i.booking_id=b.booking_id AND i.score>=80)', [[sum(any(i[1]==r[fid] and i[5] is not None and i[5]>=80 for i in inspections) for r in facts)]], 'complex', ['existence','numeric_filter'])
        a('Count bookings whose inspection is on or after their booked date, excluding missing timestamps', 'SELECT COUNT(*) FROM bookings b WHERE julianday(b.booked_at) IS NOT NULL AND EXISTS(SELECT 1 FROM inspections i WHERE i.booking_id=b.booking_id AND julianday(i.inspected_at)>=julianday(b.booked_at))', [[sum(r[stamp] is not None and any(i[1]==r[fid] and i[4] and utc_day(i[4])>=utc_day(r[stamp]) for i in inspections) for r in facts)]], 'complex', ['temporal_relationship','nulls'])
    elif domain == 'support':
        a('Count tickets tagged urgent in the priority namespace', "SELECT COUNT(*) FROM tickets t WHERE EXISTS(SELECT 1 FROM ticket_tags x JOIN tags g ON g.namespace=x.namespace AND g.code=x.code WHERE x.ticket_id=t.ticket_id AND g.namespace='priority' AND g.label='urgent')", [[len({x[0] for x in links if x[1:] == ('priority','p1')})]], 'complex', ['composite_key','catalog','existence'])
        a('Count ticket tag assignments by tag label using both namespace and code', 'SELECT g.label,COUNT(*) FROM ticket_tags x JOIN tags g ON g.namespace=x.namespace AND g.code=x.code GROUP BY g.label', groups(links,lambda x:next(g[2] for g in tags if g[:2]==x[1:])), 'complex', ['composite_key','join','grouping'])
        a('List tickets with no responses', 'SELECT t.* FROM tickets t WHERE NOT EXISTS(SELECT 1 FROM responses r WHERE r.ticket_id=t.ticket_id)', [list(t.values()) for t in facts if not any(r[1]==t[fid] for r in responses)], 'medium', ['anti_join','duplicates'])
        a('Count tickets with a response on or after their opened date', 'SELECT COUNT(*) FROM tickets t WHERE julianday(t.opened_at) IS NOT NULL AND EXISTS(SELECT 1 FROM responses r WHERE r.ticket_id=t.ticket_id AND julianday(r.sent_at)>=julianday(t.opened_at))', [[sum(t[stamp] is not None and any(r[1]==t[fid] and r[2] and utc_day(r[2])>=utc_day(t[stamp]) for r in responses) for t in facts)]], 'complex', ['temporal_relationship'])
        a('Count responses with missing sent_at', 'SELECT COUNT(*) FROM responses WHERE sent_at IS NULL', [[sum(r[2] is None for r in responses)]], tags=['nulls'])
        a('Count distinct tickets with any tag assignment', 'SELECT COUNT(DISTINCT ticket_id) FROM ticket_tags', [[len({x[0] for x in links})]], 'medium', ['many_to_many','distinct'])
    else:
        a('How many usage events represent opening the app, meaning event kind app_open?', "SELECT COUNT(*) FROM usage_events e JOIN event_kinds k ON k.kind_id=e.kind_id WHERE k.label='app_open'", [[sum(e[2]==1 for e in events)]], 'medium', ['catalog','natural_language'])
        a('Count usage events by event kind label', 'SELECT k.label,COUNT(*) FROM usage_events e JOIN event_kinds k ON k.kind_id=e.kind_id GROUP BY k.label', groups(events,lambda e:kinds[e[2]-1][1]), 'medium', ['catalog','grouping'])
        a('Count distinct subscribers with app_open usage events during March 2026 UTC', "SELECT COUNT(DISTINCT e.subscriber_id) FROM usage_events e JOIN event_kinds k ON k.kind_id=e.kind_id WHERE k.label='app_open' AND julianday(e.occurred_at)>=julianday('2026-03-01') AND julianday(e.occurred_at)<julianday('2026-04-01')", [[len({e[1] for e in events if e[1] is not None and e[2]==1 and e[3] and '2026-03-01'<=utc_day(e[3])<'2026-04-01'})]], 'complex', ['catalog','distinct','utc'])
        converted = {e[1] for e in events if e[1] is not None and e[2]==1 and e[3] and any(b[1]==e[1] and b[2]==2 and b[3] and utc_day(b[3])>=utc_day(e[3]) for b in events)}
        a('Count distinct subscribers who opened the app then exported, across all time, allowing equal timestamps', 'SELECT COUNT(DISTINCT a.subscriber_id) FROM usage_events a JOIN usage_events b ON b.subscriber_id=a.subscriber_id WHERE a.kind_id=1 AND b.kind_id=2 AND julianday(b.occurred_at)>=julianday(a.occurred_at)', [[len(converted)]], 'complex', ['ordered_funnel','duplicates'])
        a('Fraction of all registered subscribers who opened the app then exported, across all time, allowing equal timestamps', 'SELECT COUNT(DISTINCT a.subscriber_id)*1.0/(SELECT COUNT(*) FROM subscribers) FROM usage_events a JOIN usage_events b ON b.subscriber_id=a.subscriber_id WHERE a.kind_id=1 AND b.kind_id=2 AND julianday(b.occurred_at)>=julianday(a.occurred_at)', [[len(converted)/len(entities)]], 'complex', ['ordered_funnel','ratio'])
        a('List event kinds without usage events', 'SELECT k.* FROM event_kinds k WHERE NOT EXISTS(SELECT 1 FROM usage_events e WHERE e.kind_id=k.kind_id)', [list(k) for k in kinds if not any(e[2]==k[0] for e in events)], 'medium', ['catalog','anti_join'])
    return f.finish()


def build(output, seed=11):
    if output.exists():
        raise FileExistsError('Choose a new output directory; existing snapshots are never overwritten')
    output.mkdir(parents=True)
    manifest = dict(version='independent-v1', suite_name='synthetic-stress-v1', seed=seed,
        exposure='development-exposed-authored-for-diagnostics', external_blind=False,
        final_claim='Development stress testing only; not held-out or independently human-reviewed',
        oracle='Python source-record collections, independently computed from reference SQL; SQL cross-check before scoring',
        design='Three domains; 24 shared operation controls plus six domain-specific questions each. Seeds change data, not linguistic diversity.',
        datasets=[build_domain(output,name,seed) for name in ('rentals','support','billing')])
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--seed',type=int,default=11)
    args = parser.parse_args()
    result = build(args.output,args.seed)
    print(f"Created {sum(len(d['cases']) for d in result['datasets'])} development cases, seed {args.seed}")
