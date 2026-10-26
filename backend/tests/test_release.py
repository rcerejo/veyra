from app.metrics.evaluation import benchmark_cases


def test_benchmark_has_fifty_distinct_questions():
    cases=benchmark_cases()
    assert len(cases)>=50
    assert len({case['question'] for case in cases})==len(cases)


def test_modification_request_is_refused(client):
    response=client.post('/api/query',json={'question':'Delete all users'})
    assert response.status_code==200
    assert response.json()['status']=='clarification_required'
    assert client.post('/api/query',json={'question':'How many users are there?'}).json()['rows'][0]['user_count']==2


def test_country_is_not_misread_as_count(client):
    result=client.post('/api/query',json={'question':'Show users by country'}).json()
    assert {row['country'] for row in result['rows']}=={'US','CA'}


def test_growth_counts_revenue_without_join_duplication(client,database):
    import sqlite3
    with sqlite3.connect(database) as db:
        db.executescript("""CREATE TABLE orders(order_id INTEGER,user_id INTEGER,order_timestamp TEXT,revenue REAL);
        INSERT INTO orders VALUES(1,1,'2026-01-03',10),(2,1,'2026-01-03',20);""")
    response=client.get('/api/metrics/growth?start=2026-01-01&end=2026-01-04')
    assert response.status_code==200
    result=response.json()
    assert result['summary']['revenue']==30
    assert result['summary']['revenue_per_registered_user']==15
    assert sum(row['revenue'] for row in result['channels'])==30


def test_prediction_rejects_insufficient_history(client):
    assert client.post('/api/prediction').status_code==422
