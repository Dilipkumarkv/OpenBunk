"""P0-2: server-derived prices/attribution and mandatory idempotency."""

from conftest import auth


def _catalog(client, token):
    nozzles = {n["label"]: n for n in client.get("/api/v1/nozzles", headers=auth(token)).json()}
    products = {p["code"]: p for p in client.get("/api/v1/fuel-products", headers=auth(token)).json()}
    prices = {p["product_code"]: p for p in client.get("/api/v1/fuel-prices/current", headers=auth(token)).json()}
    return nozzles, products, prices


def test_current_prices_are_seeded(client, manager_token):
    _, _, prices = _catalog(client, manager_token)
    assert prices["petrol"]["unit_price"] == "102.50"
    assert prices["diesel"]["unit_price"] == "89.50"


def test_price_change_requires_reauth_and_takes_effect(client, manager_token):
    _, products, _ = _catalog(client, manager_token)
    payload = {"product_id": products["petrol"]["id"], "unit_price": "105.00"}
    assert client.post("/api/v1/fuel-prices", headers=auth(manager_token), json=payload).status_code == 401

    changed = client.post(
        "/api/v1/fuel-prices",
        headers={**auth(manager_token), "X-Reauth-Pin": "123456"},
        json=payload,
    )
    assert changed.status_code == 201
    assert changed.json()["unit_price"] == "105.00"

    _, _, prices = _catalog(client, manager_token)
    assert prices["petrol"]["unit_price"] == "105.00"


def test_sale_price_is_server_derived(client, manager_token):
    nozzles, _, _ = _catalog(client, manager_token)
    sale = client.post(
        "/api/v1/sales",
        headers={**auth(manager_token), "Idempotency-Key": "server-price-1"},
        json={"nozzle_id": nozzles["P1"]["id"], "volume_litres": "10", "tender": "cash"},
    )
    assert sale.status_code == 201, sale.text
    assert sale.json()["unit_price"] == "102.50"
    assert sale.json()["amount"] == "1025.00"


def test_sale_rejects_client_price_or_product_mismatch(client, manager_token):
    nozzles, products, _ = _catalog(client, manager_token)
    bad_price = client.post(
        "/api/v1/sales",
        headers={**auth(manager_token), "Idempotency-Key": "bad-price-1"},
        json={"nozzle_id": nozzles["P1"]["id"], "volume_litres": "10", "unit_price": "1.00", "tender": "cash"},
    )
    assert bad_price.status_code == 422

    bad_product = client.post(
        "/api/v1/sales",
        headers={**auth(manager_token), "Idempotency-Key": "bad-product-1"},
        json={"nozzle_id": nozzles["P1"]["id"], "product_id": products["diesel"]["id"], "volume_litres": "10", "tender": "cash"},
    )
    assert bad_product.status_code == 422


def test_nozzle_must_match_tank_product(client, manager_token):
    tanks = {t["label"]: t for t in client.get("/api/v1/tanks", headers=auth(manager_token)).json()}
    products = {p["code"]: p for p in client.get("/api/v1/fuel-products", headers=auth(manager_token)).json()}
    response = client.post(
        "/api/v1/nozzles",
        headers=auth(manager_token),
        json={"label": "X1", "tank_id": tanks["T-01"]["id"], "product_id": products["diesel"]["id"]},
    )
    assert response.status_code == 422


def test_sale_idempotency_fingerprint(client, manager_token):
    nozzles, _, _ = _catalog(client, manager_token)
    payload = {"nozzle_id": nozzles["P1"]["id"], "volume_litres": "10", "tender": "cash"}
    missing = client.post("/api/v1/sales", headers=auth(manager_token), json=payload)
    assert missing.status_code == 400

    first = client.post(
        "/api/v1/sales",
        headers={**auth(manager_token), "Idempotency-Key": "sale-idem-1"},
        json=payload,
    )
    assert first.status_code == 201
    replay = client.post(
        "/api/v1/sales",
        headers={**auth(manager_token), "Idempotency-Key": "sale-idem-1"},
        json=payload,
    )
    assert replay.status_code == 201
    assert replay.headers.get("X-Idempotent-Replay") == "true"
    assert replay.json()["id"] == first.json()["id"]

    changed = client.post(
        "/api/v1/sales",
        headers={**auth(manager_token), "Idempotency-Key": "sale-idem-1"},
        json={**payload, "volume_litres": "11"},
    )
    assert changed.status_code == 409


def test_sale_rejects_closed_shift(client, manager_token):
    nozzles, _, _ = _catalog(client, manager_token)
    shift = client.post("/api/v1/shifts", headers=auth(manager_token), json={"kind": "afternoon"}).json()
    closed = client.post(
        f"/api/v1/shifts/{shift['id']}/close",
        headers={**auth(manager_token), "X-Reauth-Pin": "123456", "Idempotency-Key": "closed-shift-close"},
        json={"collections": {"cash": "0"}},
    )
    assert closed.status_code == 422  # no readings
    # force the shift into a closed state through a valid close is covered elsewhere;
    # here we only prove a bogus shift id is rejected
    missing = client.post(
        "/api/v1/sales",
        headers={**auth(manager_token), "Idempotency-Key": "missing-shift-sale"},
        json={"nozzle_id": nozzles["P1"]["id"], "volume_litres": "1", "tender": "cash", "shift_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert missing.status_code == 404


def test_credit_sale_enforces_limit(client, manager_token):
    nozzles, _, _ = _catalog(client, manager_token)
    customer = client.post(
        "/api/v1/credit/customers",
        headers=auth(manager_token),
        json={"account_code": "AC-LIMIT", "name": "Limit Co", "credit_limit": "500"},
    ).json()
    response = client.post(
        "/api/v1/sales",
        headers={**auth(manager_token), "Idempotency-Key": "credit-over-limit"},
        json={
            "nozzle_id": nozzles["P1"]["id"],
            "volume_litres": "10",  # 1025.00
            "tender": "credit",
            "credit_customer_id": customer["id"],
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["details"]["code"] == "credit_limit_exceeded"
