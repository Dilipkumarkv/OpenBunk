"""Owner-only data export. Contains NO secrets (no PIN/token hashes)."""

import json

from fastapi import APIRouter, Depends, Response
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from ..deps import audit, get_db_dep, require_reauth, require_roles
from ..models import (
    AuditEvent,
    CreditCustomer,
    CreditLedgerEntry,
    Employee,
    FuelPrice,
    FuelProduct,
    FuelReceipt,
    MeterReading,
    Nozzle,
    Payment,
    Sale,
    Shift,
    Station,
    StockMovement,
    Tank,
)

router = APIRouter(tags=["export"])

_EXCLUDE = {"pin_hash"}  # never export credentials


def _dump(entity):
    return {
        column.key: getattr(entity, column.key)
        for column in inspect(entity.__class__).mapper.column_attrs
        if column.key not in _EXCLUDE
    }


@router.get("/export")
def export_station_data(
    employee: Employee = Depends(require_roles("owner")),
    _: Employee = Depends(require_reauth),
    db: Session = Depends(get_db_dep),
):
    sid = employee.station_id
    sections = {
        "station": Station,
        "employees": Employee,
        "fuel_products": FuelProduct,
        "fuel_prices": FuelPrice,
        "tanks": Tank,
        "nozzles": Nozzle,
        "shifts": Shift,
        "meter_readings": MeterReading,
        "fuel_receipts": FuelReceipt,
        "stock_movements": StockMovement,
        "credit_customers": CreditCustomer,
        "credit_ledger_entries": CreditLedgerEntry,
        "sales": Sale,
        "payments": Payment,
        "audit_events": AuditEvent,
    }
    dump = {}
    for name, model in sections.items():
        query = db.query(model)
        query = query.filter(model.id == sid) if model is Station else query.filter(model.station_id == sid)
        dump[name] = [_dump(r) for r in query.all()]
    counts = {key: len(value) for key, value in dump.items()}
    audit(db, station_id=sid, action="data.exported", entity_type="station", entity_id=sid, payload=counts, actor=employee.id)
    db.commit()

    payload = json.dumps(dump, default=str, indent=2)
    return Response(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="deepbnk-export.json"'},
    )
