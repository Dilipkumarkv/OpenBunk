from conftest import auth


def _nozzles_by_label(client, token):
    response = client.get("/api/v1/nozzles", headers=auth(token))
    assert response.status_code == 200
    return {n["label"]: n for n in response.json()}


def _tanks_by_label(client, token):
    response = client.get("/api/v1/tanks", headers=auth(token))
    assert response.status_code == 200
    return {t["label"]: t for t in response.json()}


def _open_shift(client, token, kind="afternoon"):
    response = client.post("/api/v1/shifts", headers=auth(token), json={"kind": kind})
    assert response.status_code == 201
    return response.json()


def _put_prototype_readings(client, token, shift_id, nozzles):
    response = client.put(
        f"/api/v1/shifts/{shift_id}/readings",
        headers=auth(token),
        json={
            "readings": [
                {
                    "nozzle_id": nozzles["P1"]["id"],
                    "opening_litres": "12450",
                    "closing_litres": "12780",
                    "unit_price": "102.50",
                },
                {
                    "nozzle_id": nozzles["D1"]["id"],
                    "opening_litres": "22500",
                    "closing_litres": "22920",
                    "unit_price": "89.50",
                },
            ]
        },
    )
    assert response.status_code == 200


def test_shift_open_validate_close_happy_path(client, manager_token):
    nozzles = _nozzles_by_label(client, manager_token)
    shift = _open_shift(client, manager_token)
    _put_prototype_readings(client, manager_token, shift["id"], nozzles)

    validation = client.post(
        f"/api/v1/shifts/{shift['id']}/validate",
        headers=auth(manager_token),
        json={},
    )
    assert validation.status_code == 200
    assert validation.json()["valid"] is True

    closed = client.post(
        f"/api/v1/shifts/{shift['id']}/close",
        headers={**auth(manager_token), "X-Reauth-Pin": "1234", "Idempotency-Key": "test-close-1"},
        json={},
    )
    assert closed.status_code == 200
    body = closed.json()
    assert body["status"] == "closed"
    assert body["revenue_total"] == "71415.00"
    assert body["readings_processed"] == 2


def test_close_requires_idempotency_key(client, manager_token):
    nozzles = _nozzles_by_label(client, manager_token)
    shift = _open_shift(client, manager_token)
    _put_prototype_readings(client, manager_token, shift["id"], nozzles)
    response = client.post(
        f"/api/v1/shifts/{shift['id']}/close",
        headers={**auth(manager_token), "X-Reauth-Pin": "1234"},
        json={},
    )
    assert response.status_code == 400


def test_close_is_idempotent(client, manager_token):
    nozzles = _nozzles_by_label(client, manager_token)
    shift = _open_shift(client, manager_token)
    _put_prototype_readings(client, manager_token, shift["id"], nozzles)

    first = client.post(
        f"/api/v1/shifts/{shift['id']}/close",
        headers={**auth(manager_token), "X-Reauth-Pin": "1234", "Idempotency-Key": "idem-key-42"},
        json={},
    )
    assert first.status_code == 200

    replay = client.post(
        f"/api/v1/shifts/{shift['id']}/close",
        headers={**auth(manager_token), "X-Reauth-Pin": "1234", "Idempotency-Key": "idem-key-42"},
        json={},
    )
    assert replay.status_code == 200
    assert replay.headers.get("X-Idempotent-Replay") == "true"
    assert replay.json()["revenue_total"] == first.json()["revenue_total"]

    # a fresh key after close conflicts instead of double-counting
    second = client.post(
        f"/api/v1/shifts/{shift['id']}/close",
        headers={**auth(manager_token), "X-Reauth-Pin": "1234", "Idempotency-Key": "idem-key-43"},
        json={},
    )
    assert second.status_code == 409


def test_close_deducts_tank_stock(client, manager_token):
    nozzles = _nozzles_by_label(client, manager_token)
    tanks = _tanks_by_label(client, manager_token)
    shift = _open_shift(client, manager_token)
    _put_prototype_readings(client, manager_token, shift["id"], nozzles)
    response = client.post(
        f"/api/v1/shifts/{shift['id']}/close",
        headers={**auth(manager_token), "X-Reauth-Pin": "1234", "Idempotency-Key": "stock-close-1"},
        json={},
    )
    assert response.status_code == 200

    stock = client.get(f"/api/v1/tanks/{tanks['T-01']['id']}/stock", headers=auth(manager_token))
    assert stock.status_code == 200
    assert stock.json()["book_stock_litres"] == "8090.0"  # 8420 - 330


def test_closing_below_opening_blocks_close(client, manager_token):
    nozzles = _nozzles_by_label(client, manager_token)
    shift = _open_shift(client, manager_token)
    client.put(
        f"/api/v1/shifts/{shift['id']}/readings",
        headers=auth(manager_token),
        json={
            "readings": [
                {
                    "nozzle_id": nozzles["P1"]["id"],
                    "opening_litres": "12450",
                    "closing_litres": "12000",
                    "unit_price": "102.50",
                },
                {
                    "nozzle_id": nozzles["D1"]["id"],
                    "opening_litres": "22500",
                    "closing_litres": "22920",
                    "unit_price": "89.50",
                },
            ]
        },
    )

    validation = client.post(
        f"/api/v1/shifts/{shift['id']}/validate", headers=auth(manager_token), json={}
    )
    assert validation.json()["valid"] is False
    assert any("below opening" in i["message"] for i in validation.json()["issues"])

    closed = client.post(
        f"/api/v1/shifts/{shift['id']}/close",
        headers={**auth(manager_token), "X-Reauth-Pin": "1234", "Idempotency-Key": "bad-readings-close"},
        json={},
    )
    assert closed.status_code == 422


def test_rollover_authorized_allows_wrap(client, manager_token):
    nozzles = _nozzles_by_label(client, manager_token)
    shift = _open_shift(client, manager_token)
    client.put(
        f"/api/v1/shifts/{shift['id']}/readings",
        headers=auth(manager_token),
        json={
            "readings": [
                {
                    "nozzle_id": nozzles["P1"]["id"],
                    "opening_litres": "99990",
                    "closing_litres": "20",
                    "unit_price": "100.00",
                },
                {
                    "nozzle_id": nozzles["D1"]["id"],
                    "opening_litres": "500",
                    "closing_litres": "800",
                    "unit_price": "90.00",
                },
            ]
        },
    )
    close = client.post(
        f"/api/v1/shifts/{shift['id']}/close",
        headers={**auth(manager_token), "X-Reauth-Pin": "1234", "Idempotency-Key": "rollover-close-1"},
        json={
            "rollover": {
                "petrol": True,
                "diesel": False,
                "petrol_rollover_value": "100000",
            }
        },
    )
    assert close.status_code == 200
    # petrol 30 L * 100.00 + diesel 300 L * 90.00 = 3000 + 27000
    assert close.json()["revenue_total"] == "30000.00"


def test_close_with_no_readings_is_422(client, manager_token):
    shift = _open_shift(client, manager_token)
    response = client.post(
        f"/api/v1/shifts/{shift['id']}/close",
        headers={**auth(manager_token), "X-Reauth-Pin": "1234", "Idempotency-Key": "empty-close-1"},
        json={},
    )
    assert response.status_code == 422


def test_readings_cannot_change_after_close(client, manager_token):
    nozzles = _nozzles_by_label(client, manager_token)
    shift = _open_shift(client, manager_token)
    _put_prototype_readings(client, manager_token, shift["id"], nozzles)
    client.post(
        f"/api/v1/shifts/{shift['id']}/close",
        headers={**auth(manager_token), "X-Reauth-Pin": "1234", "Idempotency-Key": "immutability-close"},
        json={},
    )
    response = client.put(
        f"/api/v1/shifts/{shift['id']}/readings",
        headers=auth(manager_token),
        json={
            "readings": [
                {
                    "nozzle_id": nozzles["P1"]["id"],
                    "opening_litres": "1",
                    "closing_litres": "2",
                    "unit_price": "1.00",
                }
            ]
        },
    )
    assert response.status_code == 409
