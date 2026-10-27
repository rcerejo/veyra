"""Bounded, explicit-key multi-source snapshots. Never enables ATTACH in query execution."""
from contextlib import closing, ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time
import uuid

from app.database.registry import DatabaseRegistry, DatabaseRegistryError, MAX_DATABASE_BYTES
from app.database.sqlite import SQLiteAdapter
from app.schemas.database import CombineDatabases

MAX_TABLES=60
MAX_ROWS=500_000
MAX_SECONDS=30


def quote(value):
    return '"'+value.replace('"','""')+'"'


def digest(path):
    result=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            result.update(block)
    return result.hexdigest()


def check_time(deadline):
    if time.monotonic()>deadline:
        raise DatabaseRegistryError('Combining exceeded its 30-second budget; use smaller source snapshots')


def publish_snapshot(stage,published,deadline):
    """Retry only Windows sharing/access-denied races, never overwrite a destination."""
    for attempt in range(10):
        check_time(deadline)
        if published.exists():
            raise DatabaseRegistryError('Snapshot destination already exists; retry with a new name')
        try:
            os.rename(stage,published)
            return
        except PermissionError as exc:
            if getattr(exc,'winerror',None) not in (5,32,33):
                raise
            if attempt==9:
                raise DatabaseRegistryError('Windows kept the completed snapshot directory locked. Retry after file synchronization/scanning finishes; sources and the active dataset were not changed.') from exc
            time.sleep(min(.05*(attempt+1),.2))


def read_connection(path, deadline):
    connection=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=2)
    connection.execute('PRAGMA trusted_schema=OFF')
    connection.execute('PRAGMA query_only=ON')
    connection.enable_load_extension(False)
    connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH,2*1024*1024)
    connection.set_progress_handler(lambda:int(time.monotonic()>deadline),1000)
    return connection


def describe(path, deadline):
    """Rebuild only understood schema semantics, never execute uploaded DDL/triggers."""
    adapter=SQLiteAdapter(path)
    tables=adapter.discover_schema()
    if not tables or len(tables)>MAX_TABLES:
        raise DatabaseRegistryError('Choose a source with 1–60 ordinary tables')
    result=[]
    with closing(read_connection(path,deadline)) as db:
        definitions=dict(db.execute("SELECT name,sql FROM sqlite_master WHERE type='table'"))
        ignored=[row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type IN ('view','trigger')")]
        if len(ignored)>100 or any(len(name)>128 for name in ignored):
            raise DatabaseRegistryError('The source has too many views/triggers or oversized identifiers for a bounded schema preview')
        for table in tables:
            check_time(deadline)
            ddl=definitions.get(table.name) or ''
            if re.search(r'\bVIRTUAL\s+TABLE\b|\bCOLLATE\b|\bSTRICT\s*$',ddl,re.I):
                raise DatabaseRegistryError('Virtual tables, strict tables and custom collation schemas are not supported for combining')
            if len(table.name)>128 or not table.columns or len(table.columns)>100:
                raise DatabaseRegistryError('Source table names/column counts exceed the supported snapshot limits')
            raw_columns=db.execute(f'PRAGMA table_xinfo({quote(table.name)})').fetchall()
            if any(row[6] for row in raw_columns):
                raise DatabaseRegistryError('Generated/hidden columns require an explicit projection and cannot be combined yet')
            columns=[]
            for column in table.columns:
                declared=next(r[2] for r in raw_columns if r[1]==column.name)
                if len(column.name)>128 or not re.fullmatch(r'[a-zA-Z ]*(?:\(\s*\d+\s*(?:,\s*\d+\s*)?\))?',declared):
                    raise DatabaseRegistryError('A source column has an unsupported name length or declared type')
                columns.append(dict(column.__dict__,data_type=declared))
            primary=[c.name for c in sorted(table.columns,key=lambda c:c.primary_key_position) if c.primary_key]
            unique=[primary] if primary else []
            for index in db.execute(f'PRAGMA index_list({quote(table.name)})').fetchall():
                if not index[2]:
                    continue
                info=db.execute(f'PRAGMA index_xinfo({quote(index[1])})').fetchall()
                keys=[row for row in info if row[5]]
                if index[4] or any(row[1]<0 or row[4]!='BINARY' for row in keys):
                    raise DatabaseRegistryError('Partial/expression/collated unique indexes are not supported for combining')
                names=[row[2] for row in keys]
                if names not in unique:
                    unique.append(names)
            result.append(dict(name=table.name,columns=columns,unique_keys=unique,
                foreign_keys=[k.__dict__ for k in table.foreign_keys]))
    return result,ignored


class DatabaseCombiner:
    def __init__(self,registry: DatabaseRegistry):
        self.registry=registry

    def schema(self,name):
        try:
            path=self.registry.resolve_source(name)
            tables,ignored=describe(path,time.monotonic()+8)
            return dict(name=name,tables=tables,ignored_objects=ignored,
                note='Schema preview does not switch databases. Views/triggers/defaults/checks are not copied or executed.')
        except (sqlite3.Error,OSError) as exc:
            raise DatabaseRegistryError('Unable to inspect this source safely; use a supported ordinary SQLite snapshot') from exc

    def provenance(self,name):
        path=self.registry.resolve_source(name)
        if not path.is_relative_to(self.registry.root/'combined') or path.name!='dataset.db':
            raise DatabaseRegistryError('This database is not a generated combined snapshot')
        metadata=path.with_suffix('.provenance.json')
        if metadata.is_symlink() or metadata.resolve().parent!=path.parent:
            raise DatabaseRegistryError('Snapshot provenance must remain beside its dataset inside the workspace')
        if not metadata.is_file() or metadata.stat().st_size>512*1024:
            raise DatabaseRegistryError('Snapshot provenance is missing or invalid')
        try:
            data=json.loads(metadata.read_text(encoding='utf-8'))
            if data.get('dataset_sha256')!=digest(path):
                raise DatabaseRegistryError('Snapshot content no longer matches its creation fingerprint')
            return dict(provenance=data,provenance_sha256=digest(metadata))
        except DatabaseRegistryError:
            raise
        except (OSError,ValueError) as exc:
            raise DatabaseRegistryError('Unable to verify snapshot provenance') from exc

    def create(self,request: CombineDatabases):
        deadline=time.monotonic()+MAX_SECONDS
        self.registry.root.mkdir(parents=True,exist_ok=True)
        try:
            with tempfile.TemporaryDirectory(prefix='.veyra-combine-',dir=self.registry.root) as temporary:
                stage=Path(temporary)
                snapshots={}
                resolved=set()
                captured_bytes=0
                # Backup captures committed WAL contents as well as the main database.
                # Each source is consistent independently, not a distributed transaction.
                for source in request.sources:
                    check_time(deadline)
                    path=self.registry.resolve_source(source.name)
                    if path in resolved:
                        raise DatabaseRegistryError('Two source names resolve to the same database')
                    resolved.add(path)
                    snapshot=stage/f'{source.alias}.snapshot'
                    def backup_progress(*_):
                        check_time(deadline)
                        if snapshot.exists() and (snapshot.stat().st_size>MAX_DATABASE_BYTES or captured_bytes+snapshot.stat().st_size>2*MAX_DATABASE_BYTES):
                            raise DatabaseRegistryError('Source snapshots exceed the 100 MB per-source or 200 MB total staging limit')
                    with closing(read_connection(path,deadline)) as db, closing(sqlite3.connect(snapshot)) as destination:
                        db.backup(destination,pages=128,progress=backup_progress,sleep=.01)
                        # Normalize only our private copy: no lingering WAL/SHM
                        # sidecars or reader locks when staging is published.
                        destination.execute('PRAGMA journal_mode=DELETE')
                    if snapshot.stat().st_size>MAX_DATABASE_BYTES:
                        raise DatabaseRegistryError('A source snapshot exceeds the 100 MB limit')
                    captured_bytes+=snapshot.stat().st_size
                    tables,ignored=describe(snapshot,deadline)
                    snapshots[source.alias]=dict(path=snapshot,name=source.name,tables=tables,ignored=ignored,
                        snapshot_sha256=digest(snapshot),captured_utc=datetime.now(timezone.utc).isoformat())
                return self._materialize(request,snapshots,stage,deadline)
        except DatabaseRegistryError:
            raise
        except (sqlite3.Error,OSError,ValueError) as exc:
            raise DatabaseRegistryError('Snapshot creation failed safely. Check source integrity, key types, unique parent keys, orphan references and resource limits; no source or active dataset was changed.') from exc

    def _materialize(self,request,snapshots,stage,deadline):
        tables={(alias,t['name']):t for alias,s in snapshots.items() for t in s['tables']}
        if len(tables)>MAX_TABLES:
            raise DatabaseRegistryError('The combined snapshot supports at most 60 tables')
        names={key:key[0]+'__'+key[1] for key in tables}
        if len({n.casefold() for n in names.values()})!=len(names):
            raise DatabaseRegistryError('Namespaced table names collide; choose different aliases')
        edges={key:[] for key in tables}
        for (alias,name),table in tables.items():
            groups={}
            for key in table['foreign_keys']:
                groups.setdefault((key['constraint_id'],key['target_table']),[]).append(key)
            for (_,target),keys in groups.items():
                keys.sort(key=lambda k:k['sequence'])
                parent=(alias,target)
                columns=[k['column'] for k in keys]
                target_columns=[k['target_column'] for k in keys]
                self._validate_edge(tables,(alias,name),columns,parent,target_columns)
                edges[(alias,name)].append((columns,parent,target_columns))
        connected={a:set() for a in snapshots}
        for link in request.relationships:
            child=(link.child_source,link.child_table)
            parent=(link.parent_source,link.parent_table)
            if link.child_source==link.parent_source:
                raise DatabaseRegistryError('New relationships must connect different sources; existing internal FKs are preserved')
            self._validate_edge(tables,child,link.child_columns,parent,link.parent_columns)
            edge=(link.child_columns,parent,link.parent_columns)
            if edge in edges[child]:
                raise DatabaseRegistryError('Duplicate cross-source relationship')
            edges[child].append(edge)
            connected[child[0]].add(parent[0])
            connected[parent[0]].add(child[0])
        seen=set()
        todo=[next(iter(snapshots))]
        while todo:
            source=todo.pop()
            if source not in seen:
                seen.add(source)
                todo.extend(connected[source]-seen)
        if seen!=set(snapshots):
            raise DatabaseRegistryError('Every selected source must be connected by your explicit cross-source relationships')
        target=stage/'dataset.db'
        counts={}
        total=0
        with closing(sqlite3.connect(target)) as db, ExitStack() as stack:
            db.execute('PRAGMA trusted_schema=OFF')
            db.execute('PRAGMA page_size=4096')
            db.execute(f'PRAGMA max_page_count={MAX_DATABASE_BYTES//4096}')
            db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH,2*1024*1024)
            db.set_progress_handler(lambda:int(time.monotonic()>deadline),1000)
            # FKs may be cyclic; validate all constraints only after all rows are copied.
            db.execute('PRAGMA foreign_keys=OFF')
            readers={alias:stack.enter_context(closing(read_connection(s['path'],deadline))) for alias,s in snapshots.items()}
            for key,table in tables.items():
                parts=[]
                for column in table['columns']:
                    declared=column['data_type']
                    parts.append(quote(column['name'])+' '+declared+(' NOT NULL' if not column['nullable'] else ''))
                primary=[c['name'] for c in sorted(table['columns'],key=lambda c:c['primary_key_position']) if c['primary_key']]
                if primary:
                    parts.append('PRIMARY KEY ('+', '.join(map(quote,primary))+')')
                for unique in table['unique_keys']:
                    if unique!=primary:
                        parts.append('UNIQUE ('+', '.join(map(quote,unique))+')')
                for columns,parent,parent_columns in edges[key]:
                    parts.append('FOREIGN KEY ('+', '.join(map(quote,columns))+') REFERENCES '+quote(names[parent])+' ('+', '.join(map(quote,parent_columns))+')')
                db.execute('CREATE TABLE '+quote(names[key])+' ('+', '.join(parts)+')')
            for key,table in tables.items():
                check_time(deadline)
                columns=', '.join(quote(c['name']) for c in table['columns'])
                cursor=readers[key[0]].execute('SELECT '+columns+' FROM '+quote(key[1]))
                count=0
                for batch in iter(lambda:cursor.fetchmany(256),[]):
                    total+=len(batch)
                    count+=len(batch)
                    if total>MAX_ROWS:
                        raise DatabaseRegistryError('Combined snapshot exceeds the 500,000-row limit')
                    check_time(deadline)
                    db.executemany('INSERT INTO '+quote(names[key])+' VALUES ('+', '.join('?' for _ in table['columns'])+')',batch)
                cursor.close()
                counts[names[key]]=count
            violation=db.execute('PRAGMA foreign_key_check').fetchone()
            if violation:
                raise DatabaseRegistryError(f'Relationship validation failed in {violation[0]}; some non-NULL keys have no matching parent. Fix the mapping or source records; no rows were dropped.')
            if db.execute('PRAGMA integrity_check(1)').fetchone()[0]!='ok':
                raise DatabaseRegistryError('Combined snapshot integrity check failed')
            db.commit()
        check_time(deadline)
        provenance=dict(version=1,mode='combined_snapshot',created_utc=datetime.now(timezone.utc).isoformat(),
            name=request.name,sources=[dict(alias=a,name=s['name'],snapshot_sha256=s['snapshot_sha256'],captured_utc=s['captured_utc'],ignored_objects=s['ignored']) for a,s in snapshots.items()],
            table_mapping=[dict(source=k[0],table=k[1],combined_table=v) for k,v in names.items()],
            relationships=[link.model_dump() for link in request.relationships],row_counts=counts,
            dataset_sha256=digest(target),
            limitations=['Static copy; source updates require a new snapshot.',
                'Source captures are individually consistent, not a distributed transaction.',
                'No views/triggers/default/check constraints, non-unique indexes, generated columns, custom collations or semantic metric definitions are copied.',
                'No automatic business-context ingestion; cross-source keys are explicit user-provided technical mappings.'])
        metadata=stage/'dataset.provenance.json'
        metadata.write_text(json.dumps(provenance,indent=2),encoding='utf-8')
        # Remove only our exact temporary backup files before publishing the completed directory.
        for source in snapshots.values():
            source['path'].unlink()
        directory=self.registry.root/'combined'
        directory.mkdir(exist_ok=True)
        if directory.resolve()!=directory:
            raise DatabaseRegistryError('Snapshot output directory escapes the workspace')
        published=directory/(request.name+'-'+uuid.uuid4().hex)
        publish_snapshot(stage,published,deadline)
        final=published/'dataset.db'
        return dict(database=dict(name=final.relative_to(self.registry.root).as_posix(),size_bytes=final.stat().st_size,active=False),
            provenance=provenance,provenance_sha256=digest(published/'dataset.provenance.json'))

    @staticmethod
    def _validate_edge(tables,child,columns,parent,parent_columns):
        if child not in tables or parent not in tables:
            raise DatabaseRegistryError('Relationship references an unknown source or table')
        child_names={c['name']:c for c in tables[child]['columns']}
        parent_names={c['name']:c for c in tables[parent]['columns']}
        if not columns or len(columns)!=len(parent_columns) or any(c not in child_names for c in columns) or any(c not in parent_names for c in parent_columns):
            raise DatabaseRegistryError('Relationship columns are missing or unresolved')
        if parent_columns not in tables[parent]['unique_keys']:
            raise DatabaseRegistryError('Parent columns must be an exact declared primary or unique key; a many-to-many join is not a foreign key')
        for left,right in zip(columns,parent_columns):
            # Require the same declared type family, avoiding implicit ID coercions.
            def affinity(value):
                value=value.upper()
                return 'integer' if 'INT' in value else 'text' if any(t in value for t in ('CHAR','CLOB','TEXT')) else 'real' if any(t in value for t in ('REAL','FLOA','DOUB')) else 'blob' if value in ('','BLOB') else 'numeric'
            if affinity(child_names[left]['data_type'])!=affinity(parent_names[right]['data_type']):
                raise DatabaseRegistryError('Join key type affinities differ; normalize IDs explicitly before combining')
