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
                {"nozzle_id": nozzles["P1"]["id"], "opening_litres": "12450", "closing_litres": "12780", "unit_price": "102.50"},
                {"nozzle_id": nozzles["P2"]["id"], "opening_litres": "9000", "closing_litres": "9080", "unit_price": "102.50"},
                {"nozzle_id": nozzles["D1"]["id"], "opening_litres": "22500", "closing_litres": "22920", "unit_price": "89.50"},
            ]
        },
    )
    response = client.post(
        f"/api/v1/shifts/{shift['id']}/close",
        headers={**auth(token), "Idempotency-Key": "reports-close-1"},
        json={},
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


def test_collections_report_sums_payments(client, manager_token):
    products = client.get("/api/v1/fuel-products", headers=auth(manager_token)).json()
    petrol = next(p for p in products if p["code"] == "petrol")

    for mode, amount in [("cash", "1000.00"), ("upi", "2500.00"), ("card", "500.00")]:
        response = client.post(
            "/api/v1/sales",
            headers={**auth(manager_token), "Idempotency-Key": f"sale-{mode}"},
            json={"product_id": petrol["id"], "volume_litres": "10", "unit_price": str(float(amount) / 10), "tender": mode},
        )
        assert response.status_code == 201, response.text

    today = date.today().isoformat()
    response = client.get(f"/api/v1/reports/collections?date={today}", headers=auth(manager_token))
    assert response.status_code == 200
    body = response.json()
    by_mode = {s["mode"]: s["amount"] for s in body["slices"]}
    assert by_mode["cash"] == "1000.00"
    assert by_mode["upi"] == "2500.00"
    assert by_mode["card"] == "500.00"
    assert body["total"] == "4000.00"
