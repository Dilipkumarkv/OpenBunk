def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness(client):
    response = client.get("/readiness")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"


def test_request_id_echoed(client):
    response = client.get("/health", headers={"X-Request-Id": "test-req-1"})
    assert response.headers["X-Request-Id"] == "test-req-1"
