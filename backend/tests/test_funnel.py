import sqlite3


def test_order_window_and_maturity(client, database):
    with sqlite3.connect(database) as db:
        db.execute('DELETE FROM events')
        db.executemany('INSERT INTO events VALUES (?, ?, ?, ?, ?)', [
            (1, 1, 'purchase', '2026-01-01', 1),
            (2, 1, 'open', '2026-01-02', 1),
            (3, 1, 'purchase', '2026-01-03', 1),
            (4, 2, 'open', '2026-01-09', 2),
            (5, 2, 'purchase', '2026-01-10', 2),
        ])
    body = client.post('/api/metrics/funnel', json={'steps': ['open', 'purchase'], 'window_days': 7}).json()
    assert [s['users'] for s in body['steps']] == [1, 1]
    assert body['excluded_immature_users'] == 1


def test_empty_funnel_has_no_invented_rate(client):
    body = client.post('/api/metrics/funnel', json={'steps': ['absent', 'purchase']}).json()
    assert body['steps'][0]['conversion_rate'] is None
