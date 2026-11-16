"""Critical Phase 07 scenarios, updated for Wave 0 reconciliation controls:
- collections are mandatory; variance requires a reason AND a second approver
- duplicate close is idempotent (also covered in test_shifts)
- concurrent edits use optimistic locking via expected_version
"""

from conftest import auth


def _nozzles_by_label(client, token):
    response = client.get("/api/v1/nozzles", headers=auth(token))
    assert response.status_code == 200
    return {n["label"]: n for n in response.json()}


def _open_and_fill(client, token):
    nozzles = _nozzles_by_label(client, token)
    shift = client.post("/api/v1/shifts", headers=auth(token), json={"kind": "afternoon"}).json()
    client.put(
        f"/api/v1/shifts/{shift['id']}/readings",
        headers=auth(token),
        json={
            "readings": [
                {"nozzle_id": nozzles["P1"]["id"], "opening_litres": "12450", "closing_litres": "12780"},
                {"nozzle_id": nozzles["P2"]["id"], "opening_litres": "9000", "closing_litres": "9080"},
                {"nozzle_id": nozzles["D1"]["id"], "opening_litres": "22500", "closing_litres": "22920"},
            ]
        },
    )
    return shift


def _close(client, token, shift_id, key, body, approver=None):
    headers = {**auth(token), "Idempotency-Key": key, "X-Reauth-Pin": "123456"}
    if approver:
        headers["X-Approval-Code"], headers["X-Approval-Pin"] = approver
    return client.post(f"/api/v1/shifts/{shift_id}/close", headers=headers, json=body)


def test_close_with_matching_collections_succeeds_without_override(client, manager_token):
    shift = _open_and_fill(client, manager_token)
    # expected = 33825 + 8200 + 37590 = 79615
    response = _close(
        client,
        manager_token,
        shift["id"],
        "recon-ok",
        {"collections": {"cash": "40000.00", "upi": "39615.00"}},
    )
    assert response.status_code == 200
    assert response.json()["revenue_total"] == "79615.00"


def test_close_with_variance_is_rejected_without_approval(client, manager_token):
    shift = _open_and_fill(client, manager_token)
    response = _close(
        client,
        manager_token,
        shift["id"],
        "recon-bad",
        {"collections": {"cash": "25000.00", "upi": "32000.00"}},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["details"]["override_required"] is True
    assert body["error"]["details"]["status"] == "short"


def test_close_with_variance_requires_second_approver(client, manager_token):
    shift = _open_and_fill(client, manager_token)
    response = _close(
        client,
        manager_token,
        shift["id"],
        "recon-no-approver",
        {"collections": {"cash": "25000.00", "upi": "32000.00"}, "override_reason": "Cash shortfall under investigation"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["details"]["approval_required"] is True


def test_close_with_variance_and_second_approver_succeeds_and_audits(client, manager_token, owner_token):
    shift = _open_and_fill(client, manager_token)
    response = _close(
        client,
        manager_token,
        shift["id"],
        "recon-override",
        {"collections": {"cash": "25000.00", "upi": "32000.00"}, "override_reason": "Manager approved short collection in person"},
        approver=("EMP-00", "123456"),
    )
    assert response.status_code == 200

    audit = client.get("/api/v1/audit", headers=auth(owner_token)).json()
    assert any(e["action"] == "shift.close_variance_override" for e in audit)
    assert any(e["action"] == "shift.variance_approved" for e in audit)


def test_self_approval_is_rejected(client, owner_token):
    shift = _open_and_fill(client, owner_token)
    response = _close(
        client,
        owner_token,
        shift["id"],
        "recon-self",
        {"collections": {"cash": "25000.00"}, "override_reason": "Owner tries to self-approve variance"},
        approver=("EMP-00", "123456"),
    )
    assert response.status_code == 403


def test_close_over_collection_with_second_approver_succeeds(client, manager_token):
    shift = _open_and_fill(client, manager_token)
    response = _close(
        client,
        manager_token,
        shift["id"],
        "recon-over",
        {"collections": {"cash": "99999.00"}, "override_reason": "Excess cash from previous day drop"},
        approver=("EMP-00", "123456"),
    )
    assert response.status_code == 200


def test_optimistic_locking_rejects_stale_version(client, manager_token):
    nozzles = _nozzles_by_label(client, manager_token)
    shift = client.post("/api/v1/shifts", headers=auth(manager_token), json={"kind": "afternoon"}).json()
    assert shift["version"] == 1

    first = client.put(
        f"/api/v1/shifts/{shift['id']}/readings",
        headers=auth(manager_token),
        json={
            "expected_version": 1,
            "readings": [
                {"nozzle_id": nozzles["P1"]["id"], "opening_litres": "100", "closing_litres": "200"},
            ],
        },
    )
    assert first.status_code == 200
    assert first.json()["version"] == 2

    # a stale writer holding version 1 is rejected with 409
    stale = client.put(
        f"/api/v1/shifts/{shift['id']}/readings",
        headers=auth(manager_token),
        json={
            "expected_version": 1,
            "readings": [
                {"nozzle_id": nozzles["P1"]["id"], "opening_litres": "100", "closing_litres": "250"},
            ],
        },
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["details"]["current_version"] == 2

    # current version still succeeds
    fresh = client.put(
        f"/api/v1/shifts/{shift['id']}/readings",
        headers=auth(manager_token),
        json={
            "expected_version": 2,
            "readings": [
                {"nozzle_id": nozzles["P1"]["id"], "opening_litres": "100", "closing_litres": "250"},
            ],
        },
    )
    assert fresh.status_code == 200
    assert fresh.json()["version"] == 3


def test_credit_receipt_reduces_outstanding_exactly_once(client, manager_token):
    customer = client.post(
        "/api/v1/credit/customers",
        headers=auth(manager_token),
        json={"account_code": "AC-900", "name": "Ledger Test Co", "credit_limit": "100000"},
    ).json()

    for amount in ("10000", "5000"):
        client.post(
            f"/api/v1/credit/customers/{customer['id']}/entries",
            headers=auth(manager_token),
            json={"type": "charge", "amount": amount},
        )
    # two receipts, each applied exactly once
    client.post(
        f"/api/v1/credit/customers/{customer['id']}/entries",
        headers=auth(manager_token),
        json={"type": "receipt", "amount": "4000"},
    )
    client.post(
        f"/api/v1/credit/customers/{customer['id']}/entries",
        headers=auth(manager_token),
        json={"type": "receipt", "amount": "2000"},
    )
    ledger = client.get(f"/api/v1/credit/customers/{customer['id']}/ledger", headers=auth(manager_token)).json()
    assert ledger["balance"] == "9000.00"
    assert len(ledger["entries"]) == 4
