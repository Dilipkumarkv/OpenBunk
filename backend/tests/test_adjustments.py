from conftest import auth


def _setup(client, token):
    tanks = {t["label"]: t for t in client.get("/api/v1/tanks", headers=auth(token)).json()}
    return tanks


def test_tank_adjustment_requires_owner_or_manager_and_reason(client, cashier_token, manager_token):
    tanks = _setup(client, manager_token)
    t01 = tanks["T-01"]
    before = client.get(f"/api/v1/tanks/{t01['id']}/stock", headers=auth(manager_token)).json()[
        "book_stock_litres"
    ]

    # cashier forbidden
    response = client.post(
        f"/api/v1/tanks/{t01['id']}/adjustments",
        headers={**auth(cashier_token), "X-Reauth-Pin": "123456"},
        json={"delta_litres": "50", "reason": "count correction"},
    )
    assert response.status_code == 403

    # reason is mandatory
    response = client.post(
        f"/api/v1/tanks/{t01['id']}/adjustments",
        headers={**auth(manager_token), "X-Reauth-Pin": "123456"},
        json={"delta_litres": "50"},
    )
    assert response.status_code == 422

    # re-auth PIN is mandatory
    response = client.post(
        f"/api/v1/tanks/{t01['id']}/adjustments",
        headers=auth(manager_token),
        json={"delta_litres": "50", "reason": "count correction"},
    )
    assert response.status_code == 401


def test_tank_adjustment_applies_and_audits(client, manager_token):
    tanks = _setup(client, manager_token)
    t01 = tanks["T-01"]
    before = float(
        client.get(f"/api/v1/tanks/{t01['id']}/stock", headers=auth(manager_token)).json()["book_stock_litres"]
    )

    response = client.post(
        f"/api/v1/tanks/{t01['id']}/adjustments",
        headers={**auth(manager_token), "X-Reauth-Pin": "123456"},
        json={"delta_litres": "-18", "reason": "dip shortage confirmed by owner"},
    )
    assert response.status_code == 201
    assert response.json()["delta_litres"] == "-18"

    after = float(
        client.get(f"/api/v1/tanks/{t01['id']}/stock", headers=auth(manager_token)).json()["book_stock_litres"]
    )
    assert after - before == -18.0

    audit = client.get("/api/v1/audit", headers=auth(manager_token))
    assert audit.status_code == 403  # audit is owner/auditor-only — adjustment still happened


def test_tank_adjustment_is_audited_visible_to_owner(client, owner_token):
    tanks = _setup(client, owner_token)
    t01 = tanks["T-01"]
    client.post(
        f"/api/v1/tanks/{t01['id']}/adjustments",
        headers={**auth(owner_token), "X-Reauth-Pin": "123456"},
        json={"delta_litres": "25", "reason": "recount after delivery"},
    )
    audit = client.get("/api/v1/audit", headers=auth(owner_token)).json()
    entries = [e for e in audit if e["action"] == "stock.adjustment"]
    assert entries, "stock.adjustment audit event missing"
    assert entries[0]["reason"] == "recount after delivery"
