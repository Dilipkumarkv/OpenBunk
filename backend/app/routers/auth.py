from fastapi import APIRouter, Depends, Request, Response, status

from ..config import get_settings
from ..deps import audit, enforce_rate_limit, get_current_employee, get_db_dep, session_ttl
from ..db import get_db
from ..errors import ApiError
from ..models import Employee, SessionToken, Station, utcnow
from ..schemas import MeResponse, SessionRequest, SessionResponse
from ..security import hash_token, new_session_token, verify_pin
from sqlalchemy.orm import Session

router = APIRouter(tags=["auth"])

settings = get_settings()


@router.post("/session", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(payload: SessionRequest, request: Request, response: Response, db: Session = Depends(get_db_dep)):
    enforce_rate_limit(f"session:{request.client.host if request.client else 'unknown'}", settings.RATE_LIMIT_PER_MINUTE)

    station = db.query(Station).filter(Station.code == payload.station_code, Station.active.is_(True)).first()
    if station is None:
        raise ApiError(401, "Invalid credentials")
    employee = (
        db.query(Employee)
        .filter(
            Employee.station_id == station.id,
            Employee.code == payload.employee_code,
            Employee.active.is_(True),
        )
        .first()
    )
    if employee is None or not employee.pin_hash or not verify_pin(payload.pin, employee.pin_hash):
        raise ApiError(401, "Invalid credentials")

    token = new_session_token()
    expires_at = utcnow() + session_ttl()
    db.add(
        SessionToken(
            station_id=station.id,
            employee_id=employee.id,
            token_hash=hash_token(token),
            expires_at=expires_at,
        )
    )
    audit(db, station_id=station.id, action="session.created", entity_type="employee", entity_id=employee.id, actor=employee.id)
    db.commit()
    db.refresh(employee)
    db.refresh(station)
    return SessionResponse(token=token, expires_at=expires_at, employee=employee, station=station)


@router.delete("/session", status_code=status.HTTP_204_NO_CONTENT)
def destroy_session(request: Request, db: Session = Depends(get_db_dep)):
    auth = request.headers.get("authorization", "")
    token = auth.removeprefix("Bearer ")
    if token:
        row = db.query(SessionToken).filter(SessionToken.token_hash == hash_token(token)).first()
        if row is not None and row.revoked_at is None:
            row.revoked_at = utcnow()
            audit(db, station_id=row.station_id, action="session.revoked", entity_type="employee", entity_id=row.employee_id, actor=row.employee_id)
            db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=MeResponse)
def me(employee: Employee = Depends(get_current_employee), db: Session = Depends(get_db_dep)):
    station = db.get(Station, employee.station_id)
    return MeResponse(employee=employee, station=station)
