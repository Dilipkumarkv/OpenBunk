from conftest import auth


def _create_customer(client, token, code="AC-014", name="Sri Lakshmi Transport", limit="50000"):
    response = client.post(
        "/api/v1/credit/customers",
        headers=auth(token),
        json={"account_code": code, "name": name, "credit_limit": limit},
    )
    assert response.status_code == 201
    return response.json()


def test_credit_customer_lifecycle_and_limit_status(client, manager_token):
    customer = _create_customer(client, manager_token)

    charge = client.post(
        f"/api/v1/credit/customers/{customer['id']}/entries",
        headers=auth(manager_token),
        json={"type": "charge", "amount": "48000", "reason": "fleet fuel"},
    )
    assert charge.status_code == 201
    assert charge.json()["limit_status"] == "near_limit"

    receipt = client.post(
        f"/api/v1/credit/customers/{customer['id']}/entries",
        headers=auth(manager_token),
        json={"type": "receipt", "amount": "20000"},
    )
    assert receipt.status_code == 201
    assert receipt.json()["balance"] == "28000.00"

    ledger = client.get(f"/api/v1/credit/customers/{customer['id']}/ledger", headers=auth(manager_token))
    assert ledger.status_code == 200
    assert ledger.json()["balance"] == "28000.00"
    assert len(ledger.json()["entries"]) == 2


def test_credit_over_limit_is_rejected_and_owner_can_override(client, manager_token, owner_token):
    customer = _create_customer(client, manager_token, code="AC-021", name="Ravi Enterprises", limit="25000")
    response = client.post(
        f"/api/v1/credit/customers/{customer['id']}/entries",
        headers=auth(manager_token),
        json={"type": "charge", "amount": "28400"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["details"]["code"] == "credit_limit_exceeded"

    # manager cannot override, even with a reason
    manager_override = client.post(
        f"/api/v1/credit/customers/{customer['id']}/entries",
        headers=auth(manager_token),
        json={"type": "charge", "amount": "28400", "override_limit_reason": "customer promises to pay"},
    )
    assert manager_override.status_code == 422

    override = client.post(
        f"/api/v1/credit/customers/{customer['id']}/entries",
        headers=auth(owner_token),
        json={"type": "charge", "amount": "28400", "override_limit_reason": "owner approved temporary excess"},
    )
    assert override.status_code == 201
    assert override.json()["limit_status"] == "over_limit"

    audit = client.get("/api/v1/audit", headers=auth(owner_token)).json()
    assert any(e["action"] == "credit.limit_override" for e in audit)


def test_duplicate_account_code_conflicts(client, manager_token):
    _create_customer(client, manager_token)
    response = client.post(
        "/api/v1/credit/customers",
        headers=auth(manager_token),
        json={"account_code": "AC-014", "name": "Duplicate", "credit_limit": "10000"},
    )
    assert response.status_code == 409


def test_adjustment_entry_signed(client, manager_token):
    customer = _create_customer(client, manager_token)
    client.post(
        f"/api/v1/credit/customers/{customer['id']}/entries",
        headers=auth(manager_token),
        json={"type": "charge", "amount": "10000"},
    )
    adjust = client.post(
        f"/api/v1/credit/customers/{customer['id']}/entries",
        headers=auth(manager_token),
        json={"type": "adjustment", "amount": "-2500", "reason": "goodwill"},
    )
    assert adjust.status_code == 201
    assert adjust.json()["balance"] == "7500.00"
