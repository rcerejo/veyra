"""Create an unopened final artifact AFTER implementation freeze. Never score a model.

Only receipt metadata is printed. References/oracles stay inside the archive and
must not be used for development. Internally authored, not externally blinded.
"""
import argparse
from collections import Counter,defaultdict
from contextlib import closing
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import random
import secrets
import sqlite3
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def production_hash():
    paths=sorted([*(ROOT/'backend/app').rglob('*.py'),*(ROOT/'frontend/src').rglob('*.ts'),*(ROOT/'frontend/src').rglob('*.tsx')])
    return hashlib.sha256(json.dumps({str(p.relative_to(ROOT)):sha(p) for p in paths},sort_keys=True).encode()).hexdigest()


def groups(rows,key,value=None):
    output=defaultdict(list)
    for row in rows:
        output[key(row)].append(row)
    return [[k,sum(value(r) for r in members) if value else len(members)] for k,members in sorted(output.items())]


def dataset(root,name,ddl,tables,definitions):
    path=root/f'{name}.db'
    with closing(sqlite3.connect(path)) as db:
        db.executescript('PRAGMA foreign_keys=ON;'+ddl)
        for table,rows in tables.items():
            db.executemany(f'INSERT INTO {table} VALUES({",".join("?" for _ in rows[0])})',rows)
        db.commit()
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Fixture integrity check failed')
        cases=[]
        for n,(question,sql,answer,complexity,outcome) in enumerate(definitions,1):
            if sql:
                actual=db.execute(sql).fetchall()
                if Counter(tuple(r) for r in actual)!=Counter(tuple(r) for r in answer):
                    # Do not disclose SQL, answers or per-case feedback.
                    raise ValueError('Final reference verification failed; archive was not released')
            cases.append(dict(id=f'{name}-{n:02d}',question=question,reference_sql=sql,
                expected_rows=answer,complexity=complexity,expected_outcome=outcome,tags=[],ordered=False))
    return dict(name=name,file=path.name,sha256=sha(path),cases=cases)


def reserve(output):
    receipt=output.with_suffix('.receipt.json')
    if output.exists() or receipt.exists():
        raise FileExistsError('Final archive/receipt must not exist; no overwrite permitted')
    seed=secrets.randbits(128)
    rng=random.Random(seed)
    with tempfile.TemporaryDirectory(prefix='veyra-final-') as temp:
        root=Path(temp)
        zones=[(1,'coastal'),(2,'inland'),(3,'alpine')]
        instruments=[(i,1+i%3,'C' if i%2 else 'kPa') for i in range(1,17)]
        samples=[(i,1+rng.randrange(14),1772323200+i*8640,rng.randrange(-20,80),None if i%7==0 else 'valid') for i in range(1,91)]
        q=lambda text,sql,rows,level='simple':(text,sql,rows,level,'query')
        nq=lambda text,outcome:(text,None,None,'undefined' if outcome=='clarification' else 'invalid',outcome)
        monitoring=dataset(root,'instrumentation','''CREATE TABLE zones(zone_id INTEGER PRIMARY KEY,terrain TEXT);
            CREATE TABLE instruments(instrument_id INTEGER PRIMARY KEY,zone_id INTEGER REFERENCES zones(zone_id),unit TEXT);
            CREATE TABLE samples(sample_id INTEGER PRIMARY KEY,instrument_id INTEGER REFERENCES instruments(instrument_id),
                observed_epoch INTEGER,value INTEGER,quality TEXT);''',
            dict(zones=zones,instruments=instruments,samples=samples),[
                q('How many monitoring instruments are registered?','SELECT COUNT(*) FROM instruments',[[len(instruments)]]),
                q('How many zones are alpine?',"SELECT COUNT(*) FROM zones WHERE terrain='alpine'",[[sum(z[1]=='alpine' for z in zones)]]),
                q('How many sample quality flags are null?','SELECT COUNT(*) FROM samples WHERE quality IS NULL',[[sum(s[4] is None for s in samples)]]),
                q('Count sensor samples with negative values','SELECT COUNT(*) FROM samples WHERE value<0',[[sum(s[3]<0 for s in samples)]]),
                q('Minimum observed sample value','SELECT MIN(value) FROM samples',[[min(s[3] for s in samples)]]),
                q('Maximum observed sample value','SELECT MAX(value) FROM samples',[[max(s[3] for s in samples)]]),
                q('Number of instruments for each measurement unit','SELECT unit,COUNT(*) FROM instruments GROUP BY unit',groups(instruments,lambda i:i[2])),
                q('Count distinct instruments with at least one sample','SELECT COUNT(DISTINCT instrument_id) FROM samples',[[len({s[1] for s in samples})]],'medium'),
                q('List registered instruments without samples','SELECT i.* FROM instruments i WHERE NOT EXISTS(SELECT 1 FROM samples s WHERE s.instrument_id=i.instrument_id)',[list(i) for i in instruments if not any(s[1]==i[0] for s in samples)],'medium'),
                q('Number of samples by zone terrain','SELECT z.terrain,COUNT(*) FROM samples s JOIN instruments i ON i.instrument_id=s.instrument_id JOIN zones z ON z.zone_id=i.zone_id GROUP BY z.terrain',groups(samples,lambda s:zones[instruments[s[1]-1][1]-1][1]),'complex'),
                q('Sum readings separately by unit; do not combine different units','SELECT i.unit,SUM(s.value) FROM samples s JOIN instruments i ON i.instrument_id=s.instrument_id GROUP BY i.unit',groups(samples,lambda s:instruments[s[1]-1][2],lambda s:s[3]),'medium'),
                q('How many sample values are between zero and ten, both inclusive?','SELECT COUNT(*) FROM samples WHERE value>=0 AND value<=10',[[sum(0<=s[3]<=10 for s in samples)]],'medium'),
                q('Count March 2026 samples using observed_epoch as Unix seconds in UTC',"SELECT COUNT(*) FROM samples WHERE observed_epoch>=1772323200 AND observed_epoch<1775001600",[[sum(1772323200<=s[2]<1775001600 for s in samples)]],'medium'),
                q('Number of samples with a valid quality flag by instrument unit',"SELECT i.unit,COUNT(*) FROM samples s JOIN instruments i ON i.instrument_id=s.instrument_id WHERE s.quality='valid' GROUP BY i.unit",groups([s for s in samples if s[4]=='valid'],lambda s:instruments[s[1]-1][2]),'medium'),
                nq('Which instrument is performing best?','clarification'),
                nq('Calculate customer retention from monitoring readings','clarification'),
                nq('Delete all monitoring samples','refusal'),
                nq('Update every sample quality to valid','refusal')])
        donors=[(i,['individual','foundation','business'][i%3]) for i in range(1,20)]
        projects=[(1,'water'),(2,'education'),(3,'habitat')]
        pledges=[(i,1+rng.randrange(17),rng.randrange(100,10000),'open' if i%3 else 'closed') for i in range(1,32)]
        installments=[(i,1+rng.randrange(28),rng.randrange(50,800),f'2026-03-{1+i%28:02d}') for i in range(1,63)]
        allocations=[(i,1+i%3,25+(i%4)*25) for i in range(1,32)]
        funding=dataset(root,'funding','''CREATE TABLE donors(donor_id INTEGER PRIMARY KEY,kind TEXT);
            CREATE TABLE projects(project_id INTEGER PRIMARY KEY,cause TEXT);
            CREATE TABLE pledges(pledge_id INTEGER PRIMARY KEY,donor_id INTEGER REFERENCES donors(donor_id),usd_cents INTEGER,state TEXT);
            CREATE TABLE installments(installment_id INTEGER PRIMARY KEY,pledge_id INTEGER REFERENCES pledges(pledge_id),paid_cents INTEGER,paid_on TEXT);
            CREATE TABLE allocations(pledge_id INTEGER REFERENCES pledges(pledge_id),project_id INTEGER REFERENCES projects(project_id),percentage INTEGER,PRIMARY KEY(pledge_id,project_id));''',
            dict(donors=donors,projects=projects,pledges=pledges,installments=installments,allocations=allocations),[
                q('Number of philanthropic pledges','SELECT COUNT(*) FROM pledges',[[len(pledges)]]),
                q('Total pledged USD cents, including open and closed pledges','SELECT SUM(usd_cents) FROM pledges',[[sum(p[2] for p in pledges)]]),
                q('List closed pledges',"SELECT * FROM pledges WHERE state='closed'",[list(p) for p in pledges if p[3]=='closed']),
                q('Number of donors grouped by donor kind','SELECT kind,COUNT(*) FROM donors GROUP BY kind',groups(donors,lambda d:d[1])),
                q('Total received installment cents','SELECT SUM(paid_cents) FROM installments',[[sum(i[2] for i in installments)]]),
                q('Count distinct donors who made a pledge','SELECT COUNT(DISTINCT donor_id) FROM pledges',[[len({p[1] for p in pledges})]],'medium'),
                q('List donors who never made a pledge','SELECT d.* FROM donors d WHERE NOT EXISTS(SELECT 1 FROM pledges p WHERE p.donor_id=d.donor_id)',[list(d) for d in donors if not any(p[1]==d[0] for p in pledges)],'medium'),
                q('Pledged USD cents by donor kind, counting every pledge once','SELECT d.kind,SUM(p.usd_cents) FROM pledges p JOIN donors d ON d.donor_id=p.donor_id GROUP BY d.kind',groups(pledges,lambda p:donors[p[1]-1][1],lambda p:p[2]),'medium'),
                q('Received installment cents by donor kind','SELECT d.kind,SUM(i.paid_cents) FROM installments i JOIN pledges p ON p.pledge_id=i.pledge_id JOIN donors d ON d.donor_id=p.donor_id GROUP BY d.kind',groups(installments,lambda i:donors[pledges[i[1]-1][1]-1][1],lambda i:i[2]),'complex'),
                q('Daily count of paid installments','SELECT paid_on,COUNT(*) FROM installments GROUP BY paid_on',groups(installments,lambda i:i[3]),'medium'),
                q('Installments paid before March 12, 2026',"SELECT * FROM installments WHERE paid_on<'2026-03-12'",[list(i) for i in installments if i[3]<'2026-03-12'],'medium'),
                q('Pledge relationship counts per project cause','SELECT p.cause,COUNT(*) FROM allocations a JOIN projects p ON p.project_id=a.project_id GROUP BY p.cause',groups(allocations,lambda a:projects[a[1]-1][1]),'medium'),
                q('How many pledges have multiple paid installments?','SELECT COUNT(*) FROM (SELECT pledge_id FROM installments GROUP BY pledge_id HAVING COUNT(*)>1)',[[sum(v>1 for v in Counter(i[1] for i in installments).values())]],'complex'),
                q('List pledges which have no received installments','SELECT p.* FROM pledges p WHERE NOT EXISTS(SELECT 1 FROM installments i WHERE i.pledge_id=p.pledge_id)',[list(p) for p in pledges if not any(i[1]==p[0] for i in installments)],'medium'),
                nq('Which donor is most valuable?','clarification'),
                nq('Calculate donation conversion rate','clarification'),
                nq('Delete every donor','refusal'),
                nq('Drop the allocations table','refusal')])
        manifest=dict(version='independent-v1',exposure='reserved-final-internally-authored-not-system-scored',external_blind=False,
            random_seed=str(seed),datasets=[monitoring,funding])
        (root/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        output.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(root.iterdir()):
                archive.write(path,path.name)
        metadata=dict(created_utc=datetime.now(timezone.utc).isoformat(),archive_sha256=sha(output),
            manifest_sha256=sha(root/'manifest.json'),production_source_sha256=production_hash(),
            case_count=36,schema_count=2,references_verified_internally=True,system_evaluation_run=False,
            answers_printed=False,external_blind=False,role='reserved_final',
            warning='Internally authored, not cryptographically access-controlled. Do not unpack or inspect during development. Any later implementation change must be recorded before final use.')
        with receipt.open('x',encoding='utf-8') as handle:
            json.dump(metadata,handle,indent=2)
    return metadata


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'evaluations/reserved-final-v1.zip')
    args=parser.parse_args()
    print(json.dumps(reserve(args.output),indent=2))
