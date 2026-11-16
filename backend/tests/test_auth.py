from conftest import auth

from app.deps import enforce_rate_limit
from app.errors import ApiError


def test_session_requires_valid_pin(client):
    response = client.post(
        "/api/v1/session",
        json={"station_code": "OB-001", "employee_code": "EMP-01", "pin": "0000"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert "requestId" in response.json()["error"]


def test_session_lifecycle(client):
    response = client.post(
        "/api/v1/session",
        json={"station_code": "OB-001", "employee_code": "EMP-01", "pin": "1234"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["token"]
    assert body["station"]["code"] == "OB-001"

    token = body["token"]
    me = client.get("/api/v1/me", headers=auth(token))
    assert me.status_code == 200
    assert me.json()["employee"]["code"] == "EMP-01"

    logout = client.delete("/api/v1/session", headers=auth(token))
    assert logout.status_code == 204

    me_after = client.get("/api/v1/me", headers=auth(token))
    assert me_after.status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/v1/me").status_code == 401


def test_rate_limit_enforced():
    key = "unit-test-bucket"
    enforce_rate_limit(key, 2)
    enforce_rate_limit(key, 2)
    try:
        enforce_rate_limit(key, 2)
        assert False, "expected rate limit"
    except ApiError as e:
        assert e.status_code == 429
