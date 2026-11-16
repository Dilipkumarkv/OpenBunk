from conftest import auth

CLOSE_COLLECTIONS = {"collections": {"cash": "79615.00"}}


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
                {"nozzle_id": nozzles["P1"]["id"], "opening_litres": "12450", "closing_litres": "12780"},
                {"nozzle_id": nozzles["P2"]["id"], "opening_litres": "9000", "closing_litres": "9080"},
                {"nozzle_id": nozzles["D1"]["id"], "opening_litres": "22500", "closing_litres": "22920"},
            ]
        },
    )
    assert response.status_code == 200


def _close(client, token, shift_id, key, body):
    return client.post(
        f"/api/v1/shifts/{shift_id}/close",
        headers={**auth(token), "X-Reauth-Pin": "123456", "Idempotency-Key": key},
        json=body,
    )


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

    closed = _close(client, manager_token, shift["id"], "test-close-1", CLOSE_COLLECTIONS)
    assert closed.status_code == 200
    body = closed.json()
    assert body["status"] == "closed"
    assert body["revenue_total"] == "79615.00"
    assert body["readings_processed"] == 3
    assert body["variance"] == "0.00"
    assert body["reconciliation_status"] == "balanced"


def test_close_requires_idempotency_key(client, manager_token):
    nozzles = _nozzles_by_label(client, manager_token)
    shift = _open_shift(client, manager_token)
    _put_prototype_readings(client, manager_token, shift["id"], nozzles)
    response = client.post(
        f"/api/v1/shifts/{shift['id']}/close",
        headers={**auth(manager_token), "X-Reauth-Pin": "123456"},
        json=CLOSE_COLLECTIONS,
    )
    assert response.status_code == 400


def test_close_requires_collections(client, manager_token):
    nozzles = _nozzles_by_label(client, manager_token)
    shift = _open_shift(client, manager_token)
    _put_prototype_readings(client, manager_token, shift["id"], nozzles)
    response = _close(client, manager_token, shift["id"], "no-collections", {})
    assert response.status_code == 422


def test_close_is_idempotent(client, manager_token):
    nozzles = _nozzles_by_label(client, manager_token)
    shift = _open_shift(client, manager_token)
    _put_prototype_readings(client, manager_token, shift["id"], nozzles)

    first = _close(client, manager_token, shift["id"], "idem-key-42", CLOSE_COLLECTIONS)
    assert first.status_code == 200

    replay = _close(client, manager_token, shift["id"], "idem-key-42", CLOSE_COLLECTIONS)
    assert replay.status_code == 200
    assert replay.headers.get("X-Idempotent-Replay") == "true"
    assert replay.json()["revenue_total"] == first.json()["revenue_total"]

    # reusing the key with a different request is rejected
    changed = _close(client, manager_token, shift["id"], "idem-key-42", {"collections": {"cash": "1.00"}})
    assert changed.status_code == 409

    # a fresh key after close conflicts instead of double-counting
    second = _close(client, manager_token, shift["id"], "idem-key-43", CLOSE_COLLECTIONS)
    assert second.status_code == 409


def test_close_deducts_tank_stock(client, manager_token):
    nozzles = _nozzles_by_label(client, manager_token)
    tanks = _tanks_by_label(client, manager_token)
    shift = _open_shift(client, manager_token)
    _put_prototype_readings(client, manager_token, shift["id"], nozzles)
    response = _close(client, manager_token, shift["id"], "stock-close-1", CLOSE_COLLECTIONS)
    assert response.status_code == 200

    stock = client.get(f"/api/v1/tanks/{tanks['T-01']['id']}/stock", headers=auth(manager_token))
    assert stock.status_code == 200
    assert stock.json()["book_stock_litres"] == "8010.0"  # 8420 - (330 + 80)


def test_closing_below_opening_blocks_close(client, manager_token):
    nozzles = _nozzles_by_label(client, manager_token)
    shift = _open_shift(client, manager_token)
    client.put(
        f"/api/v1/shifts/{shift['id']}/readings",
        headers=auth(manager_token),
        json={
            "readings": [
                {"nozzle_id": nozzles["P1"]["id"], "opening_litres": "12450", "closing_litres": "12000"},
                {"nozzle_id": nozzles["P2"]["id"], "opening_litres": "9000", "closing_litres": "9080"},
                {"nozzle_id": nozzles["D1"]["id"], "opening_litres": "22500", "closing_litres": "22920"},
            ]
        },
    )

    validation = client.post(
        f"/api/v1/shifts/{shift['id']}/validate", headers=auth(manager_token), json={}
    )
    assert validation.json()["valid"] is False
    assert any("below opening" in i["message"] for i in validation.json()["issues"])

    closed = _close(client, manager_token, shift["id"], "bad-readings-close", CLOSE_COLLECTIONS)
    assert closed.status_code == 422


def test_missing_active_nozzle_blocks_close(client, manager_token):
    nozzles = _nozzles_by_label(client, manager_token)
    shift = _open_shift(client, manager_token)
    client.put(
        f"/api/v1/shifts/{shift['id']}/readings",
        headers=auth(manager_token),
        json={
            "readings": [
                {"nozzle_id": nozzles["P1"]["id"], "opening_litres": "12450", "closing_litres": "12780"},
                {"nozzle_id": nozzles["D1"]["id"], "opening_litres": "22500", "closing_litres": "22920"},
            ]
        },
    )
    validation = client.post(
        f"/api/v1/shifts/{shift['id']}/validate", headers=auth(manager_token), json={}
    )
    assert validation.json()["valid"] is False
    assert any(i["field"] == "nozzle P2" for i in validation.json()["issues"])


def test_rollover_authorized_allows_wrap(client, manager_token):
    nozzles = _nozzles_by_label(client, manager_token)
    shift = _open_shift(client, manager_token)
    client.put(
        f"/api/v1/shifts/{shift['id']}/readings",
        headers=auth(manager_token),
        json={
            "readings": [
                {"nozzle_id": nozzles["P1"]["id"], "opening_litres": "99990", "closing_litres": "20"},
                {"nozzle_id": nozzles["P2"]["id"], "opening_litres": "9000", "closing_litres": "9080"},
                {"nozzle_id": nozzles["D1"]["id"], "opening_litres": "500", "closing_litres": "800"},
            ]
        },
    )
    close = _close(
        client,
        manager_token,
        shift["id"],
        "rollover-close-1",
        {
            "rollover": {"petrol": True, "diesel": False, "petrol_rollover_value": "100000"},
            "collections": {"cash": "38125.00"},
        },
    )
    assert close.status_code == 200
    # petrol 30 L * 102.50 + P2 80 L * 102.50 + diesel 300 L * 89.50 = 38125
    assert close.json()["revenue_total"] == "38125.00"


def test_close_with_no_readings_is_422(client, manager_token):
    shift = _open_shift(client, manager_token)
    response = _close(client, manager_token, shift["id"], "empty-close-1", {"collections": {"cash": "0"}})
    assert response.status_code == 422


def test_readings_cannot_change_after_close(client, manager_token):
    nozzles = _nozzles_by_label(client, manager_token)
    shift = _open_shift(client, manager_token)
    _put_prototype_readings(client, manager_token, shift["id"], nozzles)
    closed = _close(client, manager_token, shift["id"], "immutability-close", CLOSE_COLLECTIONS)
    assert closed.status_code == 200

    response = client.put(
        f"/api/v1/shifts/{shift['id']}/readings",
        headers=auth(manager_token),
        json={
            "readings": [
                {"nozzle_id": nozzles["P1"]["id"], "opening_litres": "1", "closing_litres": "2"},
            ]
        },
    )
    assert response.status_code == 409
