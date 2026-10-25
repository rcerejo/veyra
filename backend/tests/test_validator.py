import pytest

from app.database.adapter import ColumnInfo, TableInfo
from app.database.schema import SchemaCatalog
from app.query_engine.validator import UnsafeQueryError, validate_sql


CATALOG = SchemaCatalog((TableInfo("users", (ColumnInfo("user_id", "INTEGER", False, True),)),))


def test_accepts_select():
    assert validate_sql("SELECT user_id FROM users", CATALOG) == "SELECT user_id FROM users"


@pytest.mark.parametrize("sql", ["DELETE FROM users", "PRAGMA table_info(users)", "SELECT 1; SELECT 2", "SELECT * FROM missing", "SELECT missing_column FROM users"])
def test_rejects_unsafe_or_unknown_sql(sql):
    with pytest.raises(UnsafeQueryError):
        validate_sql(sql, CATALOG)

