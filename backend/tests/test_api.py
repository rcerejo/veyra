def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["database"]["connected"] is True


def test_schema_discovers_foreign_keys(client):
    response = client.get("/api/schema")
    events = next(table for table in response.json()["tables"] if table["name"] == "events")
    assert events["foreign_keys"][0]["target_table"] == "users"
    assert events["sample_values"]["event_type"] == ["app_open"]


def test_deterministic_query_returns_real_rows(client):
    response = client.post("/api/query", json={"question": "How many users are there?"})
    assert response.status_code == 200
    body = response.json()
    assert body["rows"] == [{"user_count": 2}]
    assert body["metadata"]["source"] == "deterministic"


def test_database_list_and_upload(client, database):
    initial = client.get("/api/databases")
    assert initial.status_code == 200
    assert initial.json()["databases"][0]["active"] is True

    uploaded = client.post(
        "/api/databases/upload?filename=customer-analytics.sqlite",
        content=database.read_bytes(),
        headers={"content-type": "application/octet-stream"},
    )
    assert uploaded.status_code == 201
    assert uploaded.json()["name"] == "uploads/customer-analytics.sqlite"
    assert uploaded.json()["active"] is True
    assert client.get("/api/health").json()["database"]["name"] == "customer-analytics.sqlite"


def test_database_upload_rejects_non_sqlite(client):
    response = client.post(
        "/api/databases/upload?filename=not-a-database.db",
        content=b"definitely not sqlite",
        headers={"content-type": "application/octet-stream"},
    )
    assert response.status_code == 422
    assert "not a valid SQLite" in response.json()["detail"]


def test_database_activation_rejects_path_escape(client):
    response = client.post("/api/databases/activate", json={"name": "../outside.db"})
    assert response.status_code == 422
    assert "escapes" in response.json()["detail"]

