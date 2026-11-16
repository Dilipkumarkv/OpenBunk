from conftest import auth

from app.deps import enforce_rate_limit
from app.errors import ApiError


def _login(client, code="EMP-01", pin="1234"):
    return client.post(
        "/api/v1/session",
        json={"station_code": "OB-001", "employee_code": code, "pin": pin},
    )


def test_session_requires_valid_pin(client):
    response = _login(client, pin="0000")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert "requestId" in response.json()["error"]


def test_session_lifecycle(client):
    response = _login(client)
    assert response.status_code == 201
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["station"]["code"] == "OB-001"

    token = body["access_token"]
    me = client.get("/api/v1/me", headers=auth(token))
    assert me.status_code == 200
    assert me.json()["employee"]["code"] == "EMP-01"

    logout = client.delete("/api/v1/session", headers=auth(token))
    assert logout.status_code == 204

    me_after = client.get("/api/v1/me", headers=auth(token))
    assert me_after.status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/v1/me").status_code == 401


def test_refresh_rotates_and_reuse_burns_family(client):
    response = _login(client)
    body = response.json()

    refreshed = client.post("/api/v1/session/refresh", json={"refresh_token": body["refresh_token"]})
    assert refreshed.status_code == 200
    pair = refreshed.json()
    assert pair["access_token"] != body["access_token"]
    assert pair["refresh_token"] != body["refresh_token"]

    # reusing the OLD refresh token revokes the whole family
    reuse = client.post("/api/v1/session/refresh", json={"refresh_token": body["refresh_token"]})
    assert reuse.status_code == 401

    # every token issued to this employee is now dead
    assert client.get("/api/v1/me", headers=auth(body["access_token"])).status_code == 401
    assert client.get("/api/v1/me", headers=auth(pair["access_token"])).status_code == 401


def test_refresh_rejects_access_token(client):
    body = _login(client).json()
    response = client.post("/api/v1/session/refresh", json={"refresh_token": body["access_token"]})
    assert response.status_code == 401


def test_logout_revokes_both_tokens(client):
    body = _login(client).json()
    response = client.request(
        "DELETE",
        "/api/v1/session",
        headers=auth(body["access_token"]),
        json={"refresh_token": body["refresh_token"]},
    )
    assert response.status_code == 204
    assert client.get("/api/v1/me", headers=auth(body["access_token"])).status_code == 401
    assert client.post("/api/v1/session/refresh", json={"refresh_token": body["refresh_token"]}).status_code == 401


def test_rate_limit_enforced():
    key = "unit-test-bucket"
    enforce_rate_limit(key, 2)
    enforce_rate_limit(key, 2)
    try:
        enforce_rate_limit(key, 2)
        assert False, "expected rate limit"
    except ApiError as e:
        assert e.status_code == 429
