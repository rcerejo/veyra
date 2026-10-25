def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["database"]["connected"] is True


def test_schema_discovers_foreign_keys(client):
    response = client.get("/api/schema")
    events = next(table for table in response.json()["tables"] if table["name"] == "events")
    assert events["foreign_keys"][0]["target_table"] == "users"


def test_deterministic_query_returns_real_rows(client):
    response = client.post("/api/query", json={"question": "How many users are there?"})
    assert response.status_code == 200
    body = response.json()
    assert body["rows"] == [{"user_count": 2}]
    assert body["metadata"]["source"] == "deterministic"

