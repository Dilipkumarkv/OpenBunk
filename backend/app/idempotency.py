"""Idempotency-Key support for transaction-posting endpoints.

A key is bound to a request fingerprint. Replaying the same key with a different
body is rejected (409) instead of silently returning another request's result.
The key row is claimed before the business transaction commits; concurrent
duplicates hit the unique constraint and are rejected while the first is in flight.
"""

import hashlib
import json
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .errors import ApiError
from .models import IdempotencyKey


def fingerprint(payload: Any) -> str:
    """Stable SHA-256 of the request body (Decimal/dict/list safe)."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def lookup(
    db: Session, station_id: UUID, endpoint: str, key: str | None, request_hash: str
) -> tuple[bool, Any]:
    """Return (True, (status, body)) for a completed replay, else claim the key."""
    if not key or not key.strip():
        raise ApiError(400, "Idempotency-Key header is required for this endpoint")
    key = key.strip()[:128]
    row = (
        db.query(IdempotencyKey)
        .filter(
            IdempotencyKey.station_id == station_id,
            IdempotencyKey.endpoint == endpoint,
            IdempotencyKey.key == key,
        )
        .first()
    )
    if row is not None:
        if row.request_hash and row.request_hash != request_hash:
            raise ApiError(409, "Idempotency-Key was already used for a different request")
        if row.response_status == 0:
            raise ApiError(409, "A request with this Idempotency-Key is still in progress")
        return True, (row.response_status, row.response_body)

    db.add(
        IdempotencyKey(
            station_id=station_id,
            endpoint=endpoint,
            key=key,
            request_hash=request_hash,
            response_status=0,
            response_body={},
        )
    )
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "A request with this Idempotency-Key is still in progress")
    return False, None


def store(
    db: Session,
    station_id: UUID,
    endpoint: str,
    key: str | None,
    status: int,
    body: Any,
    request_hash: str | None = None,
) -> None:
    if not key:
        return
    row = (
        db.query(IdempotencyKey)
        .filter(
            IdempotencyKey.station_id == station_id,
            IdempotencyKey.endpoint == endpoint,
            IdempotencyKey.key == key.strip()[:128],
        )
        .first()
    )
    if row is None:
        row = IdempotencyKey(
            station_id=station_id,
            endpoint=endpoint,
            key=key.strip()[:128],
            request_hash=request_hash,
            response_status=status,
            response_body=body,
        )
        db.add(row)
        return
    row.response_status = status
    row.response_body = body
    if request_hash:
        row.request_hash = request_hash
