from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy import asc, desc, func
from sqlalchemy.orm import Session

from ..deps import audit, get_current_employee, get_db_dep, paginate, require_reauth, require_roles
from ..domain import compute_volume, reconcile, round2
from ..errors import ApiError
from ..idempotency import fingerprint, lookup, store
from ..models import (
    Employee,
    FuelProduct,
    MeterReading,
    Nozzle,
    Sale,
    Shift,
    StockMovement,
    utcnow,
)
from ..pricing import require_price, resolve_nozzle
from ..schemas import (
    MeterReadingOut,
    ReadingsUpsert,
    ShiftClose,
    ShiftDetailOut,
    ShiftOpen,
    ShiftOut,
    ShiftPage,
    ShiftValidate,
    ValidationIssue,
    ValidationOut,
)

router = APIRouter(tags=["shifts"])

_SORTABLE = {"business_date": Shift.business_date, "kind": Shift.kind, "status": Shift.status}
TOLERANCE = Decimal("1.00")
APPROVER_ROLES = ("owner", "manager", "accountant")


@router.post("/shifts", response_model=ShiftOut, status_code=status.HTTP_201_CREATED)
def open_shift(payload: ShiftOpen, employee: Employee = Depends(require_roles("owner", "manager", "cashier")), db: Session = Depends(get_db_dep)):
    business_date = payload.business_date or date.today()
    operator = employee
    if payload.employee_id is not None and payload.employee_id != employee.id:
        candidate = db.get(Employee, payload.employee_id)
        if candidate is None or candidate.station_id != employee.station_id or not candidate.active:
            raise ApiError(404, "Employee not found")
        if candidate.role not in ("owner", "manager", "cashier"):
            raise ApiError(422, "Selected employee cannot operate a shift")
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
def upsert_readings(shift_id: UUID, payload: ReadingsUpsert, employee: Employee = Depends(require_roles("owner", "manager", "cashier")), db: Session = Depends(get_db_dep)):
    shift = _get_shift(db, shift_id, employee.station_id)
    if shift.status != "draft":
        raise ApiError(409, "Shift is closed; readings are immutable")
    if payload.expected_version is not None and payload.expected_version != shift.version:
        raise ApiError(
            409,
            "Shift was modified by another session — refresh before saving",
            details={"current_version": shift.version, "expected_version": payload.expected_version},
        )
    if not payload.readings:
        raise ApiError(422, "At least one reading is required")

    nozzle_ids = [r.nozzle_id for r in payload.readings]
    if len(set(nozzle_ids)) != len(nozzle_ids):
        raise ApiError(422, "Duplicate nozzle in readings")

    resolved = {}
    for reading in payload.readings:
        nozzle, product, _tank = resolve_nozzle(db, employee.station_id, reading.nozzle_id)
        resolved[reading.nozzle_id] = (nozzle, product)

    for reading in payload.readings:
        nozzle, product = resolved[reading.nozzle_id]
        server_price = require_price(db, employee.station_id, product.id)
        existing = (
            db.query(MeterReading)
            .filter(MeterReading.shift_id == shift.id, MeterReading.nozzle_id == nozzle.id)
            .first()
        )
        if existing is not None:
            existing.opening_litres = reading.opening_litres
            existing.closing_litres = reading.closing_litres
            existing.unit_price = server_price
            existing.recorded_by = employee.id
        else:
            db.add(
                MeterReading(
                    station_id=employee.station_id,
                    shift_id=shift.id,
                    nozzle_id=nozzle.id,
                    opening_litres=reading.opening_litres,
                    closing_litres=reading.closing_litres,
                    unit_price=server_price,
                    recorded_by=employee.id,
                )
            )
    shift.version += 1
    audit(
        db,
        station_id=employee.station_id,
        action="shift.readings_recorded",
        entity_type="shift",
        entity_id=shift.id,
        payload={"count": len(payload.readings), "version": shift.version},
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
    nozzles = {
        n.id: n
        for n in db.query(Nozzle).filter(
            Nozzle.station_id == shift.station_id, Nozzle.active.is_(True)
        ).all()
    }
    readings = db.query(MeterReading).filter(MeterReading.shift_id == shift.id).all()
    if not readings:
        issues.append(ValidationIssue(field="readings", message="No readings recorded for this shift."))
        return False, issues

    recorded = {r.nozzle_id for r in readings}
    for nozzle in nozzles.values():
        if nozzle.id not in recorded:
            issues.append(
                ValidationIssue(
                    field=f"nozzle {nozzle.label}",
                    message=f"No reading recorded for active nozzle {nozzle.label}.",
                )
            )

    for reading in readings:
        nozzle = nozzles.get(reading.nozzle_id)
        if nozzle is None:
            issues.append(ValidationIssue(field="readings", message="Reading references an inactive or unknown nozzle."))
            continue
        code = _product_code(db, nozzle)
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
                        field=f"nozzle {nozzle.label}",
                        message="Authorized rollover needs a rollover value greater than the opening reading.",
                    ))
            else:
                issues.append(ValidationIssue(
                    field=f"nozzle {nozzle.label}",
                    message="Closing is below opening — check the meter readings (or authorize a rollover).",
                ))
        if reading.unit_price <= 0:
            issues.append(ValidationIssue(
                field=f"nozzle {nozzle.label} price",
                message="The configured selling price must be greater than zero.",
            ))
    return len(issues) == 0, issues


@router.post("/shifts/{shift_id}/validate", response_model=ValidationOut)
def validate_shift(shift_id: UUID, payload: ShiftValidate, employee: Employee = Depends(get_current_employee), db: Session = Depends(get_db_dep)):
    shift = _get_shift(db, shift_id, employee.station_id)
    valid, issues = _validate_readings(db, shift, payload.rollover)
    return ValidationOut(valid=valid, issues=issues)


def _verify_approver(
    db: Session,
    actor: Employee,
    code: str | None,
    pin: str | None,
    *,
    action: str,
    shift_id: UUID,
) -> Employee:
    from ..security import verify_pin

    if not code or not pin:
        raise ApiError(
            422,
            "A second approver is required for a variance over ₹1.00 "
            "(X-Approval-Code and X-Approval-Pin)",
            details={"approval_required": True},
        )
    approver = (
        db.query(Employee)
        .filter(
            Employee.station_id == actor.station_id,
            Employee.code == code,
            Employee.active.is_(True),
        )
        .first()
    )
    if (
        approver is None
        or approver.id == actor.id
        or approver.role not in APPROVER_ROLES
        or not verify_pin(pin, approver.pin_hash)
    ):
        raise ApiError(403, "Second approver rejected — check code, role and PIN")
    audit(
        db,
        station_id=actor.station_id,
        action="shift.variance_approved",
        entity_type="shift",
        entity_id=shift_id,
        payload={"approver_code": approver.code, "approver_role": approver.role},
        actor=approver.id,
    )
    return approver


@router.post("/shifts/{shift_id}/close", status_code=status.HTTP_200_OK)
def close_shift(
    shift_id: UUID,
    payload: ShiftClose,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_approval_code: str | None = Header(default=None, alias="X-Approval-Code"),
    x_approval_pin: str | None = Header(default=None, alias="X-Approval-Pin"),
    employee: Employee = Depends(require_roles("owner", "manager")),
    _: Employee = Depends(require_reauth),
    db: Session = Depends(get_db_dep),
):
    request_hash = fingerprint({"shift_id": str(shift_id), "body": payload.model_dump(mode="json")})
    replayed, stored = lookup(db, employee.station_id, "shifts.close", idempotency_key, request_hash)
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
        rollover_values: dict[str, str] = {}
        for reading in readings:
            nozzle = nozzles[reading.nozzle_id]
            product = db.get(FuelProduct, nozzle.product_id)
            code = (product.code if product else "").lower()
            rollover_value = None
            if code == "petrol" and payload.rollover.petrol:
                rollover_value = payload.rollover.petrol_rollover_value
                if rollover_value is not None:
                    rollover_values["petrol"] = str(rollover_value)
            elif code == "diesel" and payload.rollover.diesel:
                rollover_value = payload.rollover.diesel_rollover_value
                if rollover_value is not None:
                    rollover_values["diesel"] = str(rollover_value)
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

        # Credit sales are not cash collected: exclude them from the expected drawer.
        credit_sales = (
            db.query(func.coalesce(func.sum(Sale.amount), Decimal("0")))
            .filter(Sale.station_id == employee.station_id, Sale.shift_id == shift.id, Sale.tender == "credit")
            .scalar()
        )
        expected_collected = round2(total_revenue - Decimal(credit_sales or 0))

        recon = reconcile(expected_collected, list(payload.collections.values()), tolerance=TOLERANCE)
        variance = Decimal(recon["variance"])
        override = (payload.override_reason or "").strip()
        if abs(variance) > TOLERANCE:
            if not override:
                raise ApiError(
                    422,
                    "Collections do not reconcile with expected collections — resolve or provide override_reason",
                    details={**recon, "credit_excluded": str(round2(Decimal(credit_sales or 0))), "override_required": True},
                )
            _verify_approver(db, employee, x_approval_code, x_approval_pin, action="shift.close_variance_override", shift_id=shift.id)
            audit(
                db,
                station_id=employee.station_id,
                action="shift.close_variance_override",
                entity_type="shift",
                entity_id=shift.id,
                reason=override,
                payload=recon,
                actor=employee.id,
            )

        shift.status = "closed"
        shift.closed_at = utcnow()
        shift.closed_by = employee.id
        shift.revenue_total = round2(total_revenue)
        shift.collections = {key: str(round2(value)) for key, value in payload.collections.items()}
        shift.variance_amount = variance
        shift.variance_reason = override or None
        shift.rollover_values = rollover_values or None
        shift.version += 1
        audit(
            db,
            station_id=employee.station_id,
            action="shift.closed",
            entity_type="shift",
            entity_id=shift.id,
            payload={
                "revenue_total": str(shift.revenue_total),
                "litres": str(total_litres),
                "nozzle_count": len(readings),
                "collections": shift.collections,
                "variance": str(variance),
                "credit_sales_excluded": str(round2(Decimal(credit_sales or 0))),
            },
            actor=employee.id,
        )
        body = {
            "shift_id": str(shift.id),
            "status": shift.status,
            "revenue_total": str(shift.revenue_total),
            "total_litres": str(total_litres),
            "readings_processed": len(readings),
            "collections": shift.collections,
            "variance": str(variance),
            "reconciliation_status": recon["status"],
        }
        store(db, employee.station_id, "shifts.close", idempotency_key, 200, body, request_hash)
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
