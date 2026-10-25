from app.query_engine.planner import deterministic_sql, plan_question


def test_specific_table_month_query():
    sql = deterministic_sql("Show all events from March 2026")
    assert sql is not None
    assert "FROM events" in sql
    assert "2026-03-01" in sql
    assert "2026-04-01" in sql


def test_all_data_month_query_is_cross_table_summary():
    sql = deterministic_sql("Give me all the data from March 2026")
    assert sql is not None
    assert "WITH days AS" in sql
    assert "AS signups" in sql
    assert "AS revenue" in sql
    assert plan_question("Give me all the data from March 2026").time_range == "march_2026"


def test_natural_language_event_action_resolves_to_event_type():
    question = "I want all instances where the action was to open the app in March 2026"
    sql = deterministic_sql(question)
    assert sql is not None
    assert "event_type = 'app_open'" in sql
    assert "2026-03-01" in sql
    plan = plan_question(question)
    assert plan.relevant_tables == ["events"]
    assert plan.intent == "lookup"
    assert plan.filters == {"event_type": "app_open"}
