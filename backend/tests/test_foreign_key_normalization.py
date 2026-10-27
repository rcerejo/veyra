import sqlite3

from app.database.sqlite import SQLiteAdapter
from app.database.schema import SchemaCatalog
from app.query_engine.semantic import _join_sql


def test_implicit_composite_keys_preserve_order_and_constraint_identity(tmp_path):
    path=tmp_path/'keys.db'
    with sqlite3.connect(path) as db:
        db.executescript('''CREATE TABLE parent(a INTEGER,b INTEGER,PRIMARY KEY(b,a));
        CREATE TABLE child(x INTEGER,y INTEGER,FOREIGN KEY(x,y) REFERENCES parent);
        CREATE TABLE single(id INTEGER PRIMARY KEY);
        CREATE TABLE roles(origin INTEGER REFERENCES single,destination INTEGER REFERENCES single);''')
    adapter=SQLiteAdapter(path)
    catalog=SchemaCatalog(adapter.discover_schema())
    keys=sorted(catalog.tables['child'].foreign_keys,key=lambda k:k.sequence)
    assert [(k.column,k.target_column) for k in keys]==[('x','b'),('y','a')]
    assert len({k.constraint_id for k in keys})==1
    assert ' AND ' in _join_sql(catalog,['child','parent'])
    assert {k.target_column for k in catalog.tables['roles'].foreign_keys}=={'id'}
    assert len({k.constraint_id for k in catalog.tables['roles'].foreign_keys})==2


def test_unresolvable_target_is_not_guessed(tmp_path):
    path=tmp_path/'invalid.db'
    with sqlite3.connect(path) as db:
        db.executescript('CREATE TABLE parent(a INTEGER); CREATE TABLE child(x INTEGER REFERENCES parent);')
    catalog=SchemaCatalog(SQLiteAdapter(path).discover_schema())
    assert catalog.tables['child'].foreign_keys[0].target_column is None
    import pytest
    with pytest.raises(ValueError,match='cannot be resolved'):
        _join_sql(catalog,['child','parent'])
