from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import audit, get_current_employee, get_db_dep, require_reauth, require_roles
from ..models import Employee, Station
from ..schemas import StationOut, StationUpdate

router = APIRouter(tags=["station"])


@router.get("/station", response_model=StationOut)
def get_station(employee: Employee = Depends(get_current_employee), db: Session = Depends(get_db_dep)):
    station = db.get(Station, employee.station_id)
    return station


@router.put("/station", response_model=StationOut)
def update_station(
    payload: StationUpdate,
    employee: Employee = Depends(require_roles("owner")),
    _: Employee = Depends(require_reauth),
    db: Session = Depends(get_db_dep),
):
    station = db.get(Station, employee.station_id)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(station, field, value)
    audit(
        db,
        station_id=station.id,
        action="station.updated",
        entity_type="station",
        entity_id=station.id,
        payload={"fields": list(changes)},
        actor=employee.id,
    )
    db.commit()
    db.refresh(station)
    return station
