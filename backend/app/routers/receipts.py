from datetime import datetime

from fastapi import APIRouter, Depends, Header, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..deps import audit, get_current_employee, get_db_dep, paginate, require_roles
from ..errors import ApiError
from ..idempotency import fingerprint, lookup, store
from ..models import Employee, FuelProduct, FuelReceipt, StockMovement, Tank
from ..schemas import FuelReceiptCreate, FuelReceiptOut

router = APIRouter(tags=["fuel-receipts"])


@router.post("/fuel-receipts", response_model=FuelReceiptOut, status_code=status.HTTP_201_CREATED)
def create_receipt(
    payload: FuelReceiptCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    employee: Employee = Depends(require_roles("owner", "manager")),
    db: Session = Depends(get_db_dep),
):
    request_hash = fingerprint(payload.model_dump(mode="json"))
    replayed, stored = lookup(db, employee.station_id, "fuel_receipts.create", idempotency_key, request_hash)
    if replayed:
        status_code, body = stored
        body = dict(body)
        body["idempotent_replay"] = True
        return JSONResponse(status_code=status_code, content=body, headers={"X-Idempotent-Replay": "true"})

    tank = db.get(Tank, payload.tank_id)
    if tank is None or tank.station_id != employee.station_id:
        raise ApiError(404, "Tank not found")
    product = db.get(FuelProduct, payload.product_id)
    if product is None or product.station_id != employee.station_id:
        raise ApiError(404, "Fuel product not found")
    if tank.product_id != product.id:
        raise ApiError(422, "Tank and product do not match")

    receipt = FuelReceipt(station_id=employee.station_id, created_by=employee.id, **payload.model_dump())
    db.add(receipt)
    db.flush()
    db.add(
        StockMovement(
            station_id=employee.station_id,
            tank_id=tank.id,
            kind="receipt",
            delta_litres=payload.quantity_litres,
            source_type="fuel_receipt",
            source_id=str(receipt.id),
        )
    )
    audit(
        db,
        station_id=employee.station_id,
        action="stock.receipt_posted",
        entity_type="fuel_receipt",
        entity_id=receipt.id,
        payload={"quantity_litres": str(payload.quantity_litres), "tank": tank.label},
        actor=employee.id,
    )
    body = {
        "id": str(receipt.id),
        "tank_id": str(receipt.tank_id),
        "product_id": str(receipt.product_id),
        "quantity_litres": str(receipt.quantity_litres),
        "supplier": receipt.supplier,
        "invoice_no": receipt.invoice_no,
        "received_at": receipt.received_at.isoformat(),
    }
    store(db, employee.station_id, "fuel_receipts.create", idempotency_key, 201, body, request_hash)
    db.commit()
    db.refresh(receipt)
    return receipt


@router.get("/fuel-receipts", response_model=list[FuelReceiptOut])
def list_receipts(
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    employee: Employee = Depends(require_roles("owner", "manager", "accountant", "auditor")),
    db: Session = Depends(get_db_dep),
):
    limit, offset = paginate(limit, offset)
    return (
        db.query(FuelReceipt)
        .filter(FuelReceipt.station_id == employee.station_id)
        .order_by(FuelReceipt.received_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
