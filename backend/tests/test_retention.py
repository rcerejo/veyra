def test_exact_day_retention_and_immature_cohorts(client):
    response = client.get('/api/metrics/retention')
    assert response.status_code == 200
    cohorts = response.json()['cohorts']
    assert cohorts[0]['cells'][0]['rate'] == 0
    assert cohorts[1]['cells'][0]['rate'] == 1
    assert cohorts[0]['cells'][1]['rate'] is None
    assert cohorts[0]['cells'][1]['eligible_users'] == 0
