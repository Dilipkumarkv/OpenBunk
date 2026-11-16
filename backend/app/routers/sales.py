from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..credit_service import lock_customer, post_charge
from ..deps import audit, get_db_dep, paginate, require_roles
from ..domain import round2
from ..errors import ApiError
from ..idempotency import fingerprint, lookup, store
from ..models import CreditCustomer, Employee, Payment, Sale, Shift
from ..pricing import require_price, resolve_nozzle
from ..schemas import ORMModel

router = APIRouter(tags=["sales"])


class SaleCreate(BaseModel):
    nozzle_id: UUID
    # Deprecated client hints. The server derives both from the nozzle and price table.
    product_id: UUID | None = None
    unit_price: Decimal | None = Field(default=None, gt=0)
    volume_litres: Decimal = Field(gt=0)
    tender: Literal["cash", "upi", "card", "credit", "other"]
    credit_customer_id: UUID | None = None
    shift_id: UUID | None = None


class SaleOut(ORMModel):
    id: UUID
    shift_id: UUID | None
    nozzle_id: UUID | None
    product_id: UUID
    volume_litres: Decimal
    unit_price: Decimal
    amount: Decimal
    tender: str
    created_at: datetime


@router.post("/sales", response_model=SaleOut, status_code=status.HTTP_201_CREATED)
def create_sale(
    payload: SaleCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    employee: Employee = Depends(require_roles("owner", "manager", "cashier")),
    db: Session = Depends(get_db_dep),
):
    request_hash = fingerprint(payload.model_dump(mode="json"))
    replayed, stored = lookup(db, employee.station_id, "sales.create", idempotency_key, request_hash)
    if replayed:
        status_code, body = stored
        body = dict(body)
        body["idempotent_replay"] = True
        return JSONResponse(status_code=status_code, content=body, headers={"X-Idempotent-Replay": "true"})

    nozzle, product, _tank = resolve_nozzle(db, employee.station_id, payload.nozzle_id)
    if payload.product_id is not None and payload.product_id != product.id:
        raise ApiError(422, "Client product does not match the nozzle's product")
    server_price = require_price(db, employee.station_id, product.id)
    if payload.unit_price is not None and round2(payload.unit_price) != round2(server_price):
        raise ApiError(
            422,
            "Client price does not match the configured selling price",
            details={"configured_unit_price": str(server_price)},
        )

    if payload.shift_id is not None:
        shift = db.get(Shift, payload.shift_id)
        if shift is None or shift.station_id != employee.station_id:
            raise ApiError(404, "Shift not found")
        if shift.status != "draft":
            raise ApiError(409, "Cannot post a sale to a closed shift")

    customer = None
    if payload.tender == "credit":
        if payload.credit_customer_id is None:
            raise ApiError(422, "credit_customer_id is required for credit tender")
        customer = lock_customer(db, employee.station_id, payload.credit_customer_id)
    elif payload.credit_customer_id is not None:
        raise ApiError(422, "credit_customer_id is only valid for credit tender")

    amount = round2(payload.volume_litres * server_price)
    sale = Sale(
        station_id=employee.station_id,
        shift_id=payload.shift_id,
        nozzle_id=nozzle.id,
        product_id=product.id,
        volume_litres=payload.volume_litres,
        unit_price=server_price,
        amount=amount,
        tender=payload.tender,
        credit_customer_id=payload.credit_customer_id,
    )
    db.add(sale)
    db.flush()
    db.add(Payment(station_id=employee.station_id, sale_id=sale.id, mode=payload.tender, amount=amount))
    if customer is not None:
        post_charge(
            db,
            station_id=employee.station_id,
            customer_id=customer.id,
            amount=amount,
            reason=f"sale {sale.id}",
            actor=employee,
            reference_sale_id=sale.id,
        )
    audit(
        db,
        station_id=employee.station_id,
        action="sale.posted",
        entity_type="sale",
        entity_id=sale.id,
        payload={
            "amount": str(amount),
            "tender": payload.tender,
            "volume_litres": str(payload.volume_litres),
            "unit_price": str(server_price),
            "nozzle": nozzle.label,
        },
        actor=employee.id,
    )
    body = {
        "id": str(sale.id),
        "shift_id": str(sale.shift_id) if sale.shift_id else None,
        "nozzle_id": str(sale.nozzle_id) if sale.nozzle_id else None,
        "product_id": str(sale.product_id),
        "volume_litres": str(sale.volume_litres),
        "unit_price": str(server_price),
        "amount": str(amount),
        "tender": sale.tender,
        "created_at": sale.created_at.isoformat() if sale.created_at else None,
    }
    store(db, employee.station_id, "sales.create", idempotency_key, 201, body, request_hash)
    db.commit()
    db.refresh(sale)
    return sale


@router.get("/sales", response_model=list[SaleOut])
def list_sales(
    date_from: str | None = None,
    date_to: str | None = None,
    tender: str | None = None,
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    employee: Employee = Depends(require_roles("owner", "manager", "accountant", "auditor")),
    db: Session = Depends(get_db_dep),
):
    limit, offset = paginate(limit, offset)
    query = db.query(Sale).filter(Sale.station_id == employee.station_id)
    if tender:
        query = query.filter(Sale.tender == tender)
    if date_from:
        query = query.filter(Sale.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        query = query.filter(Sale.created_at < datetime.fromisoformat(date_to))
    return query.order_by(Sale.created_at.desc()).offset(offset).limit(limit).all()
