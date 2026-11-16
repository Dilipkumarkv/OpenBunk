from datetime import timedelta

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from ..config import get_settings
from ..deps import audit, enforce_rate_limit, get_current_employee, get_db_dep, _aware
from ..errors import ApiError
from ..models import Employee, LoginAttempt, SessionToken, Station, utcnow
from ..schemas import MeResponse, RefreshRequest, SessionRequest, SessionTokensOut
from ..security import hash_token, new_session_token, verify_pin

router = APIRouter(tags=["auth"])

settings = get_settings()

ACCESS_TTL = timedelta(minutes=15)
REFRESH_TTL = timedelta(hours=12)
MAX_FAILURES = 5
LOCKOUT_MINUTES = 15


def _issue_pair(db: Session, station: Station, employee: Employee) -> dict:
    access, refresh = new_session_token(), new_session_token()
    db.add(
        SessionToken(station_id=station.id, employee_id=employee.id, token_hash=hash_token(access), kind="access", expires_at=utcnow() + ACCESS_TTL)
    )
    db.add(
        SessionToken(station_id=station.id, employee_id=employee.id, token_hash=hash_token(refresh), kind="refresh", expires_at=utcnow() + REFRESH_TTL)
    )
    return {
        "access_token": access,
        "refresh_token": refresh,
        "access_expires_at": utcnow() + ACCESS_TTL,
        "refresh_expires_at": utcnow() + REFRESH_TTL,
        "employee": employee,
        "station": station,
    }


def _check_lockout(db: Session, station_id, employee_code: str) -> None:
    attempt = db.query(LoginAttempt).filter(
        LoginAttempt.station_id == station_id, LoginAttempt.employee_code == employee_code
    ).first()
    if attempt is not None and _aware(attempt.locked_until) is not None and _aware(attempt.locked_until) > utcnow():
        minutes = int((_aware(attempt.locked_until) - utcnow()).total_seconds() // 60) + 1
        raise ApiError(429, f"Account locked — too many failed attempts. Try again in ~{minutes} min.")


def _record_failure(db: Session, station_id, employee_code: str) -> None:
    attempt = db.query(LoginAttempt).filter(
        LoginAttempt.station_id == station_id, LoginAttempt.employee_code == employee_code
    ).first()
    if attempt is None:
        attempt = LoginAttempt(station_id=station_id, employee_code=employee_code, failures=0)
        db.add(attempt)
    attempt.failures += 1
    if attempt.failures >= MAX_FAILURES:
        attempt.locked_until = utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
        audit(db, station_id=station_id, action="account.locked", entity_type="employee", entity_id=employee_code, actor=None)


def _clear_failures(db: Session, station_id, employee_code: str) -> None:
    db.query(LoginAttempt).filter(
        LoginAttempt.station_id == station_id, LoginAttempt.employee_code == employee_code
    ).delete()


@router.post("/session", response_model=SessionTokensOut, status_code=status.HTTP_201_CREATED)
def create_session(payload: SessionRequest, request: Request, db: Session = Depends(get_db_dep)):
    enforce_rate_limit(f"session:{request.client.host if request.client else 'unknown'}", settings.RATE_LIMIT_PER_MINUTE)

    station = db.query(Station).filter(Station.code == payload.station_code, Station.active.is_(True)).first()
    if station is None:
        raise ApiError(401, "Invalid credentials")

    _check_lockout(db, station.id, payload.employee_code)

    employee = (
        db.query(Employee)
        .filter(
            Employee.station_id == station.id,
            Employee.code == payload.employee_code,
            Employee.active.is_(True),
        )
        .first()
    )
    if employee is None or not verify_pin(payload.pin, employee.pin_hash):
        _record_failure(db, station.id, payload.employee_code)
        audit(db, station_id=station.id, action="session.login_failed", entity_type="employee", entity_id=payload.employee_code)
        db.commit()
        raise ApiError(401, "Invalid credentials")

    _clear_failures(db, station.id, payload.employee_code)
    tokens = _issue_pair(db, station, employee)
    audit(db, station_id=station.id, action="session.created", entity_type="employee", entity_id=employee.id, actor=employee.id)
    db.commit()
    return tokens


@router.post("/session/refresh", response_model=SessionTokensOut)
def refresh_session(payload: RefreshRequest, request: Request, db: Session = Depends(get_db_dep)):
    enforce_rate_limit(f"refresh:{request.client.host if request.client else 'unknown'}", settings.RATE_LIMIT_PER_MINUTE)
    row = db.query(SessionToken).filter(SessionToken.token_hash == hash_token(payload.refresh_token), SessionToken.kind == "refresh").first()
    if row is None:
        raise ApiError(401, "Invalid refresh token")
    if _aware(row.revoked_at) is not None:
        # token reuse — burn the whole credential family for this employee
        db.query(SessionToken).filter(SessionToken.employee_id == row.employee_id, SessionToken.revoked_at.is_(None)).update({"revoked_at": utcnow()})
        audit(db, station_id=row.station_id, action="refresh.reuse_detected", entity_type="employee", entity_id=row.employee_id, actor=row.employee_id)
        db.commit()
        raise ApiError(401, "Refresh token already used — all sessions revoked")
    if _aware(row.expires_at) < utcnow():
        raise ApiError(401, "Refresh token expired")

    employee = db.get(Employee, row.employee_id)
    station = db.get(Station, row.station_id)
    if employee is None or not employee.active or station is None:
        raise ApiError(401, "Invalid session")

    row.revoked_at = utcnow()  # single-use rotation
    tokens = _issue_pair(db, station, employee)
    db.commit()
    return tokens


@router.delete("/session", status_code=status.HTTP_204_NO_CONTENT)
def destroy_session(request: Request, payload: RefreshRequest | None = None, db: Session = Depends(get_db_dep)):
    auth = request.headers.get("authorization", "")
    token = auth.removeprefix("Bearer ")
    if token:
        row = db.query(SessionToken).filter(SessionToken.token_hash == hash_token(token)).first()
        if row is not None and row.revoked_at is None:
            row.revoked_at = utcnow()
    if payload is not None and payload.refresh_token:
        row = db.query(SessionToken).filter(SessionToken.token_hash == hash_token(payload.refresh_token), SessionToken.kind == "refresh").first()
        if row is not None and row.revoked_at is None:
            row.revoked_at = utcnow()
    if token or (payload and payload.refresh_token):
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=MeResponse)
def me(employee: Employee = Depends(get_current_employee), db: Session = Depends(get_db_dep)):
    station = db.get(Station, employee.station_id)
    return MeResponse(employee=employee, station=station)
