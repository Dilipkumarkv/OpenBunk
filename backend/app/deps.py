"""Shared dependencies: DB session, pagination, auth, roles, re-auth, rate limiting."""

import time
from collections import defaultdict, deque
from collections.abc import Generator
from datetime import timedelta, timezone

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from .db import get_db
from .errors import ApiError
from .models import Employee, SessionToken, utcnow
from .security import hash_token, verify_pin

ROLES = ("owner", "manager", "cashier", "accountant", "auditor")
# Permission matrix — see docs/permissions.md. Server-side enforced on every endpoint.
REPORTS_AUDIT = ("owner", "manager", "accountant", "auditor")
OPERATIONAL_WRITE = ("owner", "manager")
CASHIER_WRITE = ("owner", "manager", "cashier")
CREDIT_WRITE = ("owner", "manager", "accountant")
ADMIN_ONLY = ("owner",)

ACCESS_TTL = timedelta(minutes=15)
REFRESH_TTL = timedelta(hours=12)


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
    """Access tokens only; refresh tokens cannot call APIs."""
    auth = request.headers.get("authorization", "")
    prefix = "Bearer "
    if not auth.startswith(prefix):
        raise ApiError(401, "Missing bearer token")
    token_hash = hash_token(auth[len(prefix):])
    session = (
        db.query(SessionToken)
        .filter(SessionToken.token_hash == token_hash, SessionToken.kind == "access")
        .first()
    )
    if session is None or _aware(session.revoked_at) is not None or _aware(session.expires_at) < utcnow():
        raise ApiError(401, "Access token expired or revoked")
    employee = db.get(Employee, session.employee_id)
    if employee is None or not employee.active:
        raise ApiError(401, "Employee not found or inactive")
    return employee


def require_roles(*roles: str):
    def dependency(employee: Employee = Depends(get_current_employee)) -> Employee:
        if employee.role not in roles:
            raise ApiError(403, "Insufficient role for this action")
        return employee

    return dependency


def require_reauth(request: Request, employee: Employee = Depends(get_current_employee)) -> Employee:
    """Re-authentication for sensitive actions via X-Reauth-Pin (the caller's PIN)."""
    pin = request.headers.get("x-reauth-pin")
    if not pin or not verify_pin(pin, employee.pin_hash):
        raise ApiError(401, "Re-authentication required (X-Reauth-Pin)")
    return employee


# --- Simple in-memory rate limit (single instance). ---
_hits: dict[str, deque[float]] = defaultdict(deque)


def enforce_rate_limit(key: str, limit_per_minute: int) -> None:
    now = time.monotonic()
    window = _hits[key]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= limit_per_minute:
        raise ApiError(429, "Too many requests")
    window.append(now)


def audit(db, *, station_id, action: str, entity_type: str, entity_id=None, reason=None, payload=None, actor=None):
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


__all__ = [
    "ADMIN_ONLY",
    "CASHIER_WRITE",
    "CREDIT_WRITE",
    "OPERATIONAL_WRITE",
    "REPORTS_AUDIT",
    "ROLES",
    "audit",
    "enforce_rate_limit",
    "get_current_employee",
    "get_db_dep",
    "paginate",
    "require_reauth",
    "require_roles",
]
