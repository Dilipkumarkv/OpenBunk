"""Phase 05 security: lockout, cross-station isolation, role matrix, export/offboard."""

from conftest import auth

from app.db import SessionLocal
from app.models import Employee, Station
from app.security import hash_pin


def test_lockout_after_five_failures_and_recovery(client, owner_token):
    for _ in range(5):
        response = client.post(
            "/api/v1/session",
            json={"station_code": "OB-001", "employee_code": "EMP-02", "pin": "999999"},
        )
        assert response.status_code == 401

    # sixth attempt, even with the correct PIN, is locked out
    locked = client.post(
        "/api/v1/session",
        json={"station_code": "OB-001", "employee_code": "EMP-02", "pin": "123456"},
    )
    assert locked.status_code == 429

    # a different employee at the same station is unaffected
    other = client.post(
        "/api/v1/session",
        json={"station_code": "OB-001", "employee_code": "EMP-01", "pin": "123456"},
    )
    assert other.status_code == 201


def _create_second_station():
    with SessionLocal() as db:
        station = Station(code="OB-002", name="Second Station")
        db.add(station)
        db.flush()
        emp = Employee(
            station_id=station.id,
            code="S2-01",
            name="Second Owner",
            role="owner",
            pin_hash=hash_pin("999999"),
        )
        db.add(emp)
        db.commit()


def test_cross_station_isolation(client, owner_token):
    _create_second_station()

    customer = client.post(
        "/api/v1/credit/customers",
        headers=auth(owner_token),
        json={"account_code": "AC-777", "name": "Station One Customer", "credit_limit": "10000"},
    )
    assert customer.status_code == 201
    customer_id = customer.json()["id"]

    login = client.post(
        "/api/v1/session",
        json={"station_code": "OB-002", "employee_code": "S2-01", "pin": "999999"},
    )
    assert login.status_code == 201
    token2 = login.json()["access_token"]

    # second station sees no first-station customers
    listed = client.get("/api/v1/credit/customers", headers=auth(token2))
    assert listed.status_code == 200
    assert listed.json() == []

    # and cannot read a first-station customer by direct id
    direct = client.get(f"/api/v1/credit/customers/{customer_id}/ledger", headers=auth(token2))
    assert direct.status_code == 404


def test_auditor_is_read_only(client, auditor_token):
    assert client.get("/api/v1/reports/daily-sales?date=2026-11-16", headers=auth(auditor_token)).status_code == 200
    assert client.get("/api/v1/audit", headers=auth(auditor_token)).status_code == 200

    # forbidden everywhere else
    assert client.put("/api/v1/station", headers=auth(auditor_token), json={"name": "X"}).status_code == 403
    assert client.get("/api/v1/credit/customers", headers=auth(auditor_token)).status_code == 403
    assert client.post("/api/v1/sales", headers=auth(auditor_token), json={}).status_code == 403
    assert client.post("/api/v1/shifts", headers=auth(auditor_token), json={"kind": "morning"}).status_code == 403


def test_cashier_cannot_close_shift(client, cashier_token):
    nozzles = client.get("/api/v1/nozzles", headers=auth(cashier_token)).json()
    shift = client.post("/api/v1/shifts", headers=auth(cashier_token), json={"kind": "morning"})
    assert shift.status_code == 201
    shift_id = shift.json()["id"]
    p1 = next(n for n in nozzles if n["label"] == "P1")
    d1 = next(n for n in nozzles if n["label"] == "D1")
    client.put(
        f"/api/v1/shifts/{shift_id}/readings",
        headers=auth(cashier_token),
        json={
            "readings": [
                {"nozzle_id": p1["id"], "opening_litres": "100", "closing_litres": "200", "unit_price": "100.00"},
                {"nozzle_id": d1["id"], "opening_litres": "100", "closing_litres": "200", "unit_price": "90.00"},
            ]
        },
    )
    closed = client.post(
        f"/api/v1/shifts/{shift_id}/close",
        headers={**auth(cashier_token), "Idempotency-Key": "cashier-close", "X-Reauth-Pin": "123456"},
        json={},
    )
    assert closed.status_code == 403


def test_export_requires_owner_and_reauth(client, manager_token, owner_token):
    forbidden = client.get("/api/v1/export", headers={**auth(manager_token), "X-Reauth-Pin": "123456"})
    assert forbidden.status_code == 403

    no_reauth = client.get("/api/v1/export", headers=auth(owner_token))
    assert no_reauth.status_code == 401

    exported = client.get("/api/v1/export", headers={**auth(owner_token), "X-Reauth-Pin": "123456"})
    assert exported.status_code == 200
    assert "deepbnk-export.json" in exported.headers.get("content-disposition", "")
    body = exported.json()
    assert "pin_hash" not in str(body)
    assert body["station"][0]["code"] == "OB-001"


def test_role_change_is_audited_and_takes_effect(client, owner_token):
    target = client.get("/api/v1/employees", headers=auth(owner_token)).json()
    kumar = next(e for e in target if e["code"] == "EMP-02")
    updated = client.put(
        f"/api/v1/employees/{kumar['id']}/role",
        headers={**auth(owner_token), "X-Reauth-Pin": "123456"},
        json={"role": "manager"},
    )
    assert updated.status_code == 200
    assert updated.json()["role"] == "manager"

    audit_events = client.get("/api/v1/audit", headers=auth(owner_token)).json()
    assert any(e["action"] == "employee.role_changed" and e["entity_id"] == kumar["id"] for e in audit_events)


def test_offboard_revokes_access(client, owner_token):
    create = client.post(
        "/api/v1/employees",
        headers={**auth(owner_token), "X-Reauth-Pin": "123456"},
        json={"code": "EMP-99", "name": "Temp Staff", "role": "cashier", "pin": "432100"},
    )
    assert create.status_code == 201
    staff_id = create.json()["id"]

    login = client.post(
        "/api/v1/session",
        json={"station_code": "OB-001", "employee_code": "EMP-99", "pin": "432100"},
    )
    staff_token = login.json()["access_token"]
    assert client.get("/api/v1/me", headers=auth(staff_token)).status_code == 200

    offboard = client.delete(
        f"/api/v1/employees/{staff_id}",
        headers={**auth(owner_token), "X-Reauth-Pin": "123456"},
    )
    assert offboard.status_code == 204
    assert client.get("/api/v1/me", headers=auth(staff_token)).status_code == 401


def test_short_pin_is_rejected(client, owner_token):
    response = client.post(
        "/api/v1/employees",
        headers={**auth(owner_token), "X-Reauth-Pin": "123456"},
        json={"code": "EMP-98", "name": "Short PIN", "role": "cashier", "pin": "1234"},
    )
    assert response.status_code == 422


def test_reauth_lockout_audits_and_revokes_sessions(client, owner_token):
    employees = client.get("/api/v1/employees", headers=auth(owner_token)).json()
    cashier = next(e for e in employees if e["code"] == "EMP-02")

    for _ in range(5):
        response = client.put(
            f"/api/v1/employees/{cashier['id']}/role",
            headers={**auth(owner_token), "X-Reauth-Pin": "000000"},
            json={"role": "manager"},
        )
        assert response.status_code == 401

    # lockout revokes the owner's sessions, so the old token is dead
    assert client.get("/api/v1/me", headers=auth(owner_token)).status_code == 401

    relogin = client.post(
        "/api/v1/session",
        json={"station_code": "OB-001", "employee_code": "EMP-00", "pin": "123456"},
    )
    assert relogin.status_code == 201
    audit = client.get("/api/v1/audit", headers=auth(relogin.json()["access_token"])).json()
    assert any(e["action"] == "reauth.failed" for e in audit)
    assert any(e["action"] == "reauth.locked" for e in audit)
