from conftest import auth


def test_station_requires_auth(client):
    assert client.get("/api/v1/station").status_code == 401


def test_get_and_update_station(client, manager_token):
    response = client.get("/api/v1/station", headers=auth(manager_token))
    assert response.status_code == 200
    assert response.json()["code"] == "OB-001"

    update = client.put(
        "/api/v1/station",
        headers=auth(manager_token),
        json={"name": "OpenBunk Test Station", "business_day_start": "06:00"},
    )
    assert update.status_code == 200
    assert update.json()["name"] == "OpenBunk Test Station"


def test_audit_requires_privileged_role(client, attendant_token, manager_token):
    # attendant cannot read audit log
    assert client.get("/api/v1/audit", headers=auth(attendant_token)).status_code == 403
    # manager can
    response = client.get("/api/v1/audit", headers=auth(manager_token))
    assert response.status_code == 200
    assert isinstance(response.json(), list)
