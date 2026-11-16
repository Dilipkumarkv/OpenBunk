from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..deps import audit, get_db_dep, require_reauth, require_roles
from ..errors import ApiError
from ..models import Employee
from ..schemas import EmployeeCreate, EmployeeOut, EmployeeRoleUpdate
from ..security import hash_pin

router = APIRouter(tags=["staff"])


def _active_owners(db: Session, station_id, exclude_id=None) -> int:
    query = db.query(Employee).filter(
        Employee.station_id == station_id,
        Employee.role == "owner",
        Employee.active.is_(True),
    )
    if exclude_id is not None:
        query = query.filter(Employee.id != exclude_id)
    return query.count()


@router.get("/employees", response_model=list[EmployeeOut])
def list_employees(
    employee: Employee = Depends(require_roles("owner")),
    db: Session = Depends(get_db_dep),
):
    return (
        db.query(Employee)
        .filter(Employee.station_id == employee.station_id)
        .order_by(Employee.code)
        .all()
    )


@router.post("/employees", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
def create_employee(
    payload: EmployeeCreate,
    employee: Employee = Depends(require_roles("owner")),
    _: Employee = Depends(require_reauth),
    db: Session = Depends(get_db_dep),
):
    existing = db.query(Employee).filter(
        Employee.station_id == employee.station_id, Employee.code == payload.code
    ).first()
    if existing is not None:
        raise ApiError(409, "Employee code already exists")
    staff = Employee(
        station_id=employee.station_id,
        code=payload.code,
        name=payload.name,
        role=payload.role,
        pin_hash=hash_pin(payload.pin),
    )
    db.add(staff)
    audit(db, station_id=employee.station_id, action="employee.created", entity_type="employee", entity_id=payload.code, payload={"role": payload.role}, actor=employee.id)
    db.commit()
    db.refresh(staff)
    return staff


@router.put("/employees/{employee_id}/role", response_model=EmployeeOut)
def update_role(
    employee_id: UUID,
    payload: EmployeeRoleUpdate,
    employee: Employee = Depends(require_roles("owner")),
    _: Employee = Depends(require_reauth),
    db: Session = Depends(get_db_dep),
):
    target = db.get(Employee, employee_id)
    if target is None or target.station_id != employee.station_id:
        raise ApiError(404, "Employee not found")
    if target.role == "owner" and payload.role != "owner" and _active_owners(db, employee.station_id, exclude_id=target.id) == 0:
        raise ApiError(409, "Cannot remove the last active owner — assign another owner first")
    old_role = target.role
    target.role = payload.role
    audit(
        db,
        station_id=employee.station_id,
        action="employee.role_changed",
        entity_type="employee",
        entity_id=target.id,
        payload={"from": old_role, "to": payload.role},
        actor=employee.id,
    )
    db.commit()
    db.refresh(target)
    return target


@router.delete("/employees/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def offboard(
    employee_id: UUID,
    employee: Employee = Depends(require_roles("owner")),
    _: Employee = Depends(require_reauth),
    db: Session = Depends(get_db_dep),
):
    """Soft offboard: no hard delete; credentials revoked via active=false."""
    target = db.get(Employee, employee_id)
    if target is None or target.station_id != employee.station_id:
        raise ApiError(404, "Employee not found")
    if target.id == employee.id:
        raise ApiError(400, "Owner cannot offboard themselves")
    if target.role == "owner" and _active_owners(db, employee.station_id, exclude_id=target.id) == 0:
        raise ApiError(409, "Cannot offboard the last active owner — assign another owner first")
    target.active = False
    # kill existing sessions immediately
    from ..models import SessionToken, utcnow

    db.query(SessionToken).filter(SessionToken.employee_id == target.id, SessionToken.revoked_at.is_(None)).update({"revoked_at": utcnow()})
    audit(db, station_id=employee.station_id, action="employee.offboarded", entity_type="employee", entity_id=target.id, actor=employee.id)
    db.commit()
    return
