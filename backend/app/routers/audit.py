from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..deps import get_current_employee, get_db_dep, paginate
from ..errors import ApiError
from ..models import AuditEvent, Employee
from ..schemas import AuditEventOut

router = APIRouter(tags=["audit"])

_PRIVILEGED_ROLES = {"owner", "auditor"}


@router.get("/audit", response_model=list[AuditEventOut])
def list_audit(
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    employee: Employee = Depends(get_current_employee),
    db: Session = Depends(get_db_dep),
):
    if employee.role not in _PRIVILEGED_ROLES:
        raise ApiError(403, "Audit log requires owner or auditor role")
    limit, offset = paginate(limit, offset)
    return (
        db.query(AuditEvent)
        .filter(AuditEvent.station_id == employee.station_id)
        .order_by(AuditEvent.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
