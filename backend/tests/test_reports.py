from datetime import date

from conftest import auth


def _close_prototype_shift(client, token):
    nozzles = {n["label"]: n for n in client.get("/api/v1/nozzles", headers=auth(token)).json()}
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
    response = client.post(
        f"/api/v1/shifts/{shift['id']}/close",
        headers={**auth(token), "Idempotency-Key": "reports-close-1", "X-Reauth-Pin": "123456"},
        json={"collections": {"cash": "79615.00"}},
    )
    assert response.status_code == 200
    return shift


def test_daily_sales_report(client, manager_token):
    _close_prototype_shift(client, manager_token)
    today = date.today().isoformat()
    response = client.get(f"/api/v1/reports/daily-sales?date={today}", headers=auth(manager_token))
    assert response.status_code == 200
    body = response.json()
    by_product = {t["product"]: t for t in body["totals"]}
    # petrol: (330 + 80) L across P1/P2, diesel 420 L
    assert by_product["Petrol"]["volume_litres"] == "410.0"
    assert by_product["Petrol"]["amount"] == "42025.00"
    assert by_product["Diesel"]["amount"] == "37590.00"
    assert body["grand_total_litres"] == "830.0"


def test_collections_report_excludes_credit(client, manager_token):
    nozzles = {n["label"]: n for n in client.get("/api/v1/nozzles", headers=auth(manager_token)).json()}
    p1 = nozzles["P1"]
    for mode, volume in [("cash", "10"), ("upi", "20"), ("card", "5")]:
        response = client.post(
            "/api/v1/sales",
            headers={**auth(manager_token), "Idempotency-Key": f"sale-{mode}"},
            json={"nozzle_id": p1["id"], "volume_litres": volume, "tender": mode},
        )
        assert response.status_code == 201, response.text

    customer = client.post(
        "/api/v1/credit/customers",
        headers=auth(manager_token),
        json={"account_code": "AC-REPORT", "name": "Fleet", "credit_limit": "100000"},
    ).json()
    credit = client.post(
        "/api/v1/sales",
        headers={**auth(manager_token), "Idempotency-Key": "sale-credit"},
        json={"nozzle_id": p1["id"], "volume_litres": "40", "tender": "credit", "credit_customer_id": customer["id"]},
    )
    assert credit.status_code == 201, credit.text

    today = date.today().isoformat()
    response = client.get(f"/api/v1/reports/collections?date={today}", headers=auth(manager_token))
    assert response.status_code == 200
    body = response.json()
    by_mode = {s["mode"]: s["amount"] for s in body["slices"]}
    assert by_mode["cash"] == "1025.00"
    assert by_mode["upi"] == "2050.00"
    assert by_mode["card"] == "512.50"
    assert "credit" not in by_mode
    assert body["total"] == "3587.50"
