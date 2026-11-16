from conftest import auth


def test_station_requires_auth(client):
    assert client.get("/api/v1/station").status_code == 401


def test_get_station(client, manager_token):
    response = client.get("/api/v1/station", headers=auth(manager_token))
    assert response.status_code == 200
    assert response.json()["code"] == "OB-001"


def test_update_station_requires_owner_and_reauth(client, manager_token, owner_token):
    # manager lacks owner role
    response = client.put(
        "/api/v1/station",
        headers={**auth(manager_token), "X-Reauth-Pin": "1234"},
        json={"name": "OpenBunk Test Station"},
    )
    assert response.status_code == 403

    # owner without re-auth
    response = client.put("/api/v1/station", headers=auth(owner_token), json={"name": "OpenBunk Test Station"})
    assert response.status_code == 401

    # owner with re-auth
    response = client.put(
        "/api/v1/station",
        headers={**auth(owner_token), "X-Reauth-Pin": "1234"},
        json={"name": "OpenBunk Test Station", "business_day_start": "06:00"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "OpenBunk Test Station"


def test_audit_requires_privileged_role(client, cashier_token, manager_token, auditor_token, owner_token):
    # cashier cannot read audit log
    assert client.get("/api/v1/audit", headers=auth(cashier_token)).status_code == 403
    # manager also cannot (owner + auditor only)
    assert client.get("/api/v1/audit", headers=auth(manager_token)).status_code == 403
    # auditor can
    response = client.get("/api/v1/audit", headers=auth(auditor_token))
    assert response.status_code == 200
    # owner can
    assert client.get("/api/v1/audit", headers=auth(owner_token)).status_code == 200
