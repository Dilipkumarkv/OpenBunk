"""Shared dependencies: DB session, pagination, auth, rate limiting."""

import time
from collections import defaultdict, deque
from collections.abc import Generator
from datetime import timedelta, timezone

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from .db import get_db
from .errors import ApiError
from .logging_config import request_id_ctx
from .models import Employee, SessionToken, utcnow
from .security import hash_token


def get_db_dep() -> Generator[Session, None, None]:
    yield from get_db()


def paginate(limit: int, offset: int) -> tuple[int, int]:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    return limit, offset


def _aware(dt):
    """SQLite drops tz info; normalize naive datetimes to UTC for comparisons."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def get_current_employee(request: Request, db: Session = Depends(get_db)) -> Employee:
    auth = request.headers.get("authorization", "")
    prefix = "Bearer "
    if not auth.startswith(prefix):
        raise ApiError(401, "Missing bearer token")
    token_hash = hash_token(auth[len(prefix):])
    session = db.query(SessionToken).filter(SessionToken.token_hash == token_hash).first()
    if session is None or _aware(session.revoked_at) is not None or _aware(session.expires_at) < utcnow():
        raise ApiError(401, "Session expired or revoked")
    employee = db.get(Employee, session.employee_id)
    if employee is None or not employee.active:
        raise ApiError(401, "Employee not found or inactive")
    return employee


# --- Simple in-memory rate limit (single instance). Redis-backed limiter lands in Phase 05. ---
_hits: dict[str, deque[float]] = defaultdict(deque)


def enforce_rate_limit(key: str, limit_per_minute: int) -> None:
    now = time.monotonic()
    window = _hits[key]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= limit_per_minute:
        raise ApiError(429, "Too many requests")
    window.append(now)


def audit(db: Session, *, station_id, action: str, entity_type: str, entity_id=None, reason=None, payload=None, actor=None):
    from .models import AuditEvent

    db.add(
        AuditEvent(
            station_id=station_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            reason=reason,
            payload=payload,
            actor=str(actor) if actor is not None else None,
        )
    )


SESSION_TTL_HOURS = 12


def session_ttl() -> timedelta:
    return timedelta(hours=SESSION_TTL_HOURS)


__all__ = [
    "audit",
    "enforce_rate_limit",
    "get_current_employee",
    "get_db_dep",
    "paginate",
    "request_id_ctx",
    "session_ttl",
]
