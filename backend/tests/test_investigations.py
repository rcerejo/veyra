import pytest
from app.metrics.investigations import decompose


def test_decomposition_reconciles_with_population_shift():
    before = {'a': (80,40), 'b': (20,2)}
    after = {'a': (20,10), 'b': (80,8)}
    rows = decompose(before,after)
    assert sum(r['total_contribution'] for r in rows) == pytest.approx(.18-.42)
    assert sum(r['within_contribution'] for r in rows) == 0


def test_entering_and_exiting_segments_reconcile():
    rows = decompose({'a': (10,5)}, {'b': (20,4)})
    assert sum(r['total_contribution'] for r in rows) == pytest.approx(-.3)


def test_investigation_validates_periods_and_returns_evidence(client, database):
    import sqlite3
    with sqlite3.connect(database) as db:
        db.execute("INSERT INTO events VALUES (99,1,'purchase','2026-01-04T12:00:00',3)")
    payload = {'baseline_start':'2026-01-03','baseline_end':'2026-01-03','current_start':'2026-01-04','current_end':'2026-01-04'}
    response = client.post('/api/investigations',json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body['absolute_change'] == 1
    for breakdown in body['breakdowns']:
        assert sum(s['total_contribution'] for s in breakdown['segments']) == pytest.approx(1)
    payload['current_start'] = '2026-01-03'
    assert client.post('/api/investigations',json=payload).status_code == 422
