from app.metrics.experiments import compare
from app.metrics.experiments import assignment_balance


def test_balance_respects_configured_allocation():
    assert assignment_balance(100, 100, .5)['status'] == 'passed'
    assert assignment_balance(100, 900, .5)['status'] == 'mismatch'
    assert assignment_balance(100, 900, .9)['status'] == 'passed'
    assert assignment_balance(100, 900, None)['status'] == 'not_configured'
    assert assignment_balance(1, 1, .5)['status'] == 'insufficient_data'


def test_equal_rates_are_inconclusive():
    result = compare(100, 50, 100, 50)
    assert result['p_value'] == 1
    assert result['interval'][0] < 0 < result['interval'][1]


def test_large_effect_is_detected():
    result = compare(1000, 100, 1000, 200)
    assert result['status'] == 'difference_detected'
    assert abs(result['effect'] - .1) < 1e-10
    assert result['interval'][0] > 0


def test_sparse_or_empty_data_withholds_inference():
    assert compare(10, 0, 10, 1)['p_value'] is None
    assert compare(0, 0, 10, 1)['effect'] is None


def test_assignment_window_excludes_preassignment_events(client, database):
    import sqlite3
    with sqlite3.connect(database) as db:
        db.executescript("""
        CREATE TABLE experiments (experiment_id INTEGER, experiment_name TEXT);
        CREATE TABLE experiment_assignments (experiment_id INTEGER, user_id INTEGER, variant TEXT, assigned_at TEXT);
        INSERT INTO experiments VALUES (1, 'Test');
        INSERT INTO experiment_assignments VALUES (1, 1, 'control', '2026-01-05'), (1, 2, 'treatment', '2026-01-05');
        INSERT INTO events VALUES (10, 1, 'purchase', '2026-01-04', 1), (11, 2, 'purchase', '2026-01-06', 2), (12, 1, 'app_open', '2026-01-20', 1);
        """)
    response = client.get('/api/experiments')
    assert response.status_code == 200
    result = response.json()[0]
    assert result['groups']['control']['conversions'] == 0
    assert result['groups']['treatment']['conversions'] == 1
    short = client.get('/api/experiments?conversion_event=purchase&window_days=1').json()[0]
    assert short['groups']['treatment']['conversions'] == 0
    assert short['window_days'] == 1
    assert client.get('/api/experiments?window_days=0').status_code == 422
    assert client.get('/api/experiments?conversion_event=missing').status_code == 422
    assert client.get("/api/experiments?conversion_event=quote%27event").status_code == 422
    with sqlite3.connect(database) as db:
        db.execute("INSERT INTO experiment_assignments VALUES (1, 1, 'treatment', '2026-01-05')")
    rejected = client.get('/api/experiments')
    assert rejected.status_code == 422
    assert 'Conflicting' in rejected.json()['detail']
