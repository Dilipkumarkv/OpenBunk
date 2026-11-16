"""Idempotency-Key support for transaction-posting endpoints (spec Phase 04)."""

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from .models import IdempotencyKey


def replay_if_present(db: Session, station_id: UUID, endpoint: str, key: str | None) -> tuple[bool, Any]:
    """Returns (True, stored_body) if this key was already processed, else (False, None)."""
    if not key:
        return False, None
    row = (
        db.query(IdempotencyKey)
        .filter(
            IdempotencyKey.station_id == station_id,
            IdempotencyKey.endpoint == endpoint,
            IdempotencyKey.key == key,
        )
        .first()
    )
    if row is None:
        return False, None
    return True, (row.response_status, row.response_body)


def store(db: Session, station_id: UUID, endpoint: str, key: str | None, status: int, body: Any) -> None:
    if not key:
        return
    db.add(
        IdempotencyKey(
            station_id=station_id,
            endpoint=endpoint,
            key=key,
            response_status=status,
            response_body=body,
        )
    )
