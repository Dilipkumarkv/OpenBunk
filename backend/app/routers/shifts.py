from datetime import date
from uuid import UUID
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.orm import Session

from ..deps import audit, get_current_employee, get_db_dep, paginate
from ..domain import compute_volume, round2
from ..errors import ApiError
from ..idempotency import replay_if_present, store
from ..models import Employee, FuelProduct, MeterReading, Nozzle, Shift, StockMovement, utcnow
from ..schemas import (
    MeterReadingOut,
    ReadingsUpsert,
    ShiftClose,
    ShiftDetailOut,
    ShiftOpen,
    ShiftOut,
    ShiftPage,
    ValidationIssue,
    ValidationOut,
)
from sqlalchemy import asc, desc

router = APIRouter(tags=["shifts"])

_SORTABLE = {"business_date": Shift.business_date, "kind": Shift.kind, "status": Shift.status}


@router.post("/shifts", response_model=ShiftOut, status_code=status.HTTP_201_CREATED)
def open_shift(payload: ShiftOpen, employee: Employee = Depends(get_current_employee), db: Session = Depends(get_db_dep)):
    business_date = payload.business_date or date.today()
    operator = employee
    if payload.employee_id is not None and payload.employee_id != employee.id:
        candidate = db.get(Employee, payload.employee_id)
        if candidate is None or candidate.station_id != employee.station_id:
            raise ApiError(404, "Employee not found")
        operator = candidate

    shift = Shift(
        station_id=employee.station_id,
        employee_id=operator.id,
        kind=payload.kind,
        business_date=business_date,
        status="draft",
    )
    db.add(shift)
    db.flush()
    audit(db, station_id=employee.station_id, action="shift.opened", entity_type="shift", entity_id=shift.id, actor=employee.id)
    db.commit()
    db.refresh(shift)
    return shift


@router.get("/shifts", response_model=ShiftPage)
def list_shifts(
    status_filter: str | None = Query(default=None, alias="status"),
    kind: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort: str = "business_date",
    order: str = "desc",
    limit: int = 50,
    offset: int = 0,
    employee: Employee = Depends(get_current_employee),
    db: Session = Depends(get_db_dep),
):
    limit, offset = paginate(limit, offset)
    query = db.query(Shift).filter(Shift.station_id == employee.station_id)
    if status_filter:
        query = query.filter(Shift.status == status_filter)
    if kind:
        query = query.filter(Shift.kind == kind)
    if date_from:
        query = query.filter(Shift.business_date >= date_from)
    if date_to:
        query = query.filter(Shift.business_date <= date_to)
    column = _SORTABLE.get(sort)
    if column is None:
        raise ApiError(422, f"sort must be one of {sorted(_SORTABLE)}")
    query = query.order_by(desc(column) if order == "desc" else asc(column))
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return ShiftPage(total=total, items=items)


def _get_shift(db: Session, shift_id, station_id) -> Shift:
    shift = db.get(Shift, shift_id)
    if shift is None or shift.station_id != station_id:
        raise ApiError(404, "Shift not found")
    return shift


@router.get("/shifts/{shift_id}", response_model=ShiftDetailOut)
def get_shift(shift_id: UUID, employee: Employee = Depends(get_current_employee), db: Session = Depends(get_db_dep)):
    shift = _get_shift(db, shift_id, employee.station_id)
    return shift


@router.put("/shifts/{shift_id}/readings", response_model=ShiftDetailOut)
def upsert_readings(shift_id: UUID, payload: ReadingsUpsert, employee: Employee = Depends(get_current_employee), db: Session = Depends(get_db_dep)):
    shift = _get_shift(db, shift_id, employee.station_id)
    if shift.status != "draft":
        raise ApiError(409, "Shift is closed; readings are immutable")

    nozzle_ids = {r.nozzle_id for r in payload.readings}
    nozzles = {n.id: n for n in db.query(Nozzle).filter(Nozzle.station_id == employee.station_id, Nozzle.id.in_(nozzle_ids)).all()}
    missing = nozzle_ids - set(nozzles)
    if missing:
        raise ApiError(422, "Unknown nozzle(s)", details=[{"nozzle_id": str(m)} for m in missing])

    for reading in payload.readings:
        existing = (
            db.query(MeterReading)
            .filter(MeterReading.shift_id == shift.id, MeterReading.nozzle_id == reading.nozzle_id)
            .first()
        )
        if existing is not None:
            existing.opening_litres = reading.opening_litres
            existing.closing_litres = reading.closing_litres
            existing.unit_price = reading.unit_price
            existing.recorded_by = employee.id
        else:
            db.add(
                MeterReading(
                    station_id=employee.station_id,
                    shift_id=shift.id,
                    nozzle_id=reading.nozzle_id,
                    opening_litres=reading.opening_litres,
                    closing_litres=reading.closing_litres,
                    unit_price=reading.unit_price,
                    recorded_by=employee.id,
                )
            )
    audit(
        db,
        station_id=employee.station_id,
        action="shift.readings_recorded",
        entity_type="shift",
        entity_id=shift.id,
        payload={"count": len(payload.readings)},
        actor=employee.id,
    )
    db.commit()
    db.refresh(shift)
    return shift


def _product_code(db: Session, nozzle: Nozzle) -> str:
    product = db.get(FuelProduct, nozzle.product_id)
    return (product.code if product else "").lower()


def _validate_readings(db: Session, shift: Shift, rollover) -> tuple[bool, list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    nozzles = {n.id: n for n in db.query(Nozzle).filter(Nozzle.station_id == shift.station_id).all()}
    readings = db.query(MeterReading).filter(MeterReading.shift_id == shift.id).all()
    if not readings:
        issues.append(ValidationIssue(field="readings", message="No readings recorded for this shift."))
        return False, issues

    for reading in readings:
        nozzle = nozzles.get(reading.nozzle_id)
        code = _product_code(db, nozzle) if nozzle else ""
        rollover_value = None
        authorized = False
        if code == "petrol" and rollover.petrol:
            rollover_value, authorized = rollover.petrol_rollover_value, True
        elif code == "diesel" and rollover.diesel:
            rollover_value, authorized = rollover.diesel_rollover_value, True

        if reading.closing_litres < reading.opening_litres:
            if authorized:
                if rollover_value is None or rollover_value <= reading.opening_litres:
                    issues.append(ValidationIssue(
                        field=f"nozzle {nozzle.label if nozzle else reading.nozzle_id}",
                        message="Authorized rollover needs a rollover value greater than the opening reading.",
                    ))
            else:
                issues.append(ValidationIssue(
                    field=f"nozzle {nozzle.label if nozzle else reading.nozzle_id}",
                    message="Closing is below opening — check the meter readings (or authorize a rollover).",
                ))
        if reading.unit_price <= 0:
            issues.append(ValidationIssue(
                field=f"nozzle {nozzle.label if nozzle else reading.nozzle_id} price",
                message="Price must be greater than zero.",
            ))
    return len(issues) == 0, issues


@router.post("/shifts/{shift_id}/validate", response_model=ValidationOut)
def validate_shift(shift_id: UUID, payload: ShiftClose, employee: Employee = Depends(get_current_employee), db: Session = Depends(get_db_dep)):
    shift = _get_shift(db, shift_id, employee.station_id)
    valid, issues = _validate_readings(db, shift, payload.rollover)
    return ValidationOut(valid=valid, issues=issues)


@router.post("/shifts/{shift_id}/close", status_code=status.HTTP_200_OK)
def close_shift(
    shift_id: UUID,
    payload: ShiftClose,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    employee: Employee = Depends(get_current_employee),
    db: Session = Depends(get_db_dep),
):
    if not idempotency_key:
        raise ApiError(400, "Idempotency-Key header is required for shift close")

    replayed, stored = replay_if_present(db, employee.station_id, "shifts.close", idempotency_key)
    if replayed:
        status_code, body = stored
        body = dict(body)
        body["idempotent_replay"] = True
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=status_code, content=body, headers={"X-Idempotent-Replay": "true"})

    try:
        shift = (
            db.query(Shift)
            .filter(Shift.id == shift_id, Shift.station_id == employee.station_id)
            .with_for_update()
            .first()
        )
        if shift is None:
            raise ApiError(404, "Shift not found")
        if shift.status != "draft":
            raise ApiError(409, "Shift already closed")

        valid, issues = _validate_readings(db, shift, payload.rollover)
        if not valid:
            raise ApiError(422, "Shift readings are invalid", details=[{"field": i.field, "message": i.message} for i in issues])

        readings = db.query(MeterReading).filter(MeterReading.shift_id == shift.id).all()
        nozzles = {n.id: n for n in db.query(Nozzle).filter(Nozzle.station_id == employee.station_id).all()}

        total_revenue = Decimal("0")
        total_litres = Decimal("0")
        for reading in readings:
            nozzle = nozzles[reading.nozzle_id]
            product = db.get(FuelProduct, nozzle.product_id)
            code = (product.code if product else "").lower()
            rollover_value = (
                payload.rollover.petrol_rollover_value
                if code == "petrol" and payload.rollover.petrol
                else payload.rollover.diesel_rollover_value
                if code == "diesel" and payload.rollover.diesel
                else None
            )
            volume = compute_volume(reading.opening_litres, reading.closing_litres, rollover_value)
            value = round2(volume * reading.unit_price)
            total_revenue += value
            total_litres += volume
            # dispensed fuel deducts from book stock via append-only movements
            if volume != 0:
                db.add(
                    StockMovement(
                        station_id=employee.station_id,
                        tank_id=nozzle.tank_id,
                        kind="sale",
                        delta_litres=-volume,
                        source_type="shift_close",
                        source_id=str(shift.id),
                    )
                )

        shift.status = "closed"
        shift.closed_at = utcnow()
        shift.closed_by = employee.id
        shift.revenue_total = round2(total_revenue)
        audit(
            db,
            station_id=employee.station_id,
            action="shift.closed",
            entity_type="shift",
            entity_id=shift.id,
            payload={"revenue_total": str(shift.revenue_total), "litres": str(total_litres), "nozzle_count": len(readings)},
            actor=employee.id,
        )
        body = {
            "shift_id": str(shift.id),
            "status": shift.status,
            "revenue_total": str(shift.revenue_total),
            "total_litres": str(total_litres),
            "readings_processed": len(readings),
        }
        store(db, employee.station_id, "shifts.close", idempotency_key, 200, body)
        db.commit()
        return body
    except ApiError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise ApiError(500, "Shift close failed") from e


@router.get("/shifts/{shift_id}/readings", response_model=list[MeterReadingOut])
def list_readings(shift_id: UUID, employee: Employee = Depends(get_current_employee), db: Session = Depends(get_db_dep)):
    shift = _get_shift(db, shift_id, employee.station_id)
    return db.query(MeterReading).filter(MeterReading.shift_id == shift.id).all()
