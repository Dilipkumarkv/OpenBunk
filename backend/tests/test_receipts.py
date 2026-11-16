from conftest import auth


def _fuel_setup(client, token):
    tanks = {t["label"]: t for t in client.get("/api/v1/tanks", headers=auth(token)).json()}
    products = {p["code"]: p for p in client.get("/api/v1/fuel-products", headers=auth(token)).json()}
    return tanks, products


def test_fuel_receipt_increases_book_stock(client, manager_token):
    tanks, products = _fuel_setup(client, manager_token)
    t01 = tanks["T-01"]
    before = client.get(f"/api/v1/tanks/{t01['id']}/stock", headers=auth(manager_token)).json()["book_stock_litres"]

    response = client.post(
        "/api/v1/fuel-receipts",
        headers={**auth(manager_token), "Idempotency-Key": "receipt-stock"},
        json={
            "tank_id": t01["id"],
            "product_id": products["petrol"]["id"],
            "quantity_litres": "6000",
            "supplier": "Oil Company Depot",
            "invoice_no": "INV-24091",
        },
    )
    assert response.status_code == 201

    after = client.get(f"/api/v1/tanks/{t01['id']}/stock", headers=auth(manager_token)).json()["book_stock_litres"]
    assert float(after) - float(before) == 6000.0


def test_fuel_receipt_rejects_tank_product_mismatch(client, manager_token):
    tanks, products = _fuel_setup(client, manager_token)
    response = client.post(
        "/api/v1/fuel-receipts",
        headers={**auth(manager_token), "Idempotency-Key": "receipt-mismatch"},
        json={
            "tank_id": tanks["T-02"]["id"],
            "product_id": products["petrol"]["id"],
            "quantity_litres": "1000",
        },
    )
    assert response.status_code == 422


def test_fuel_receipt_quantity_must_be_positive(client, manager_token):
    tanks, products = _fuel_setup(client, manager_token)
    response = client.post(
        "/api/v1/fuel-receipts",
        headers={**auth(manager_token), "Idempotency-Key": "receipt-zero"},
        json={
            "tank_id": tanks["T-01"]["id"],
            "product_id": products["petrol"]["id"],
            "quantity_litres": "0",
        },
    )
    assert response.status_code == 422
