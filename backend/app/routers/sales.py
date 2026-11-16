from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status
from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..deps import audit, get_current_employee, get_db_dep, paginate
from ..domain import round2
from ..errors import ApiError
from ..idempotency import replay_if_present, store
from ..models import CreditCustomer, CreditLedgerEntry, Employee, FuelProduct, Nozzle, Payment, Sale
from ..schemas import ORMModel

router = APIRouter(tags=["sales"])


class SaleCreate(BaseModel):
    nozzle_id: UUID | None = None
    product_id: UUID
    volume_litres: Decimal = Field(gt=0)
    unit_price: Decimal = Field(gt=0)
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
    employee: Employee = Depends(get_current_employee),
    db: Session = Depends(get_db_dep),
):
    replayed, stored = replay_if_present(db, employee.station_id, "sales.create", idempotency_key)
    if replayed:
        status_code, body = stored
        body = dict(body)
        body["idempotent_replay"] = True
        return JSONResponse(status_code=status_code, content=body, headers={"X-Idempotent-Replay": "true"})

    product = db.get(FuelProduct, payload.product_id)
    if product is None or product.station_id != employee.station_id:
        raise ApiError(404, "Fuel product not found")
    if payload.nozzle_id is not None:
        nozzle = db.get(Nozzle, payload.nozzle_id)
        if nozzle is None or nozzle.station_id != employee.station_id:
            raise ApiError(404, "Nozzle not found")
    if payload.tender == "credit":
        if payload.credit_customer_id is None:
            raise ApiError(422, "credit_customer_id is required for credit tender")
        customer = db.get(CreditCustomer, payload.credit_customer_id)
        if customer is None or customer.station_id != employee.station_id:
            raise ApiError(404, "Credit customer not found")

    amount = round2(payload.volume_litres * payload.unit_price)
    sale = Sale(
        station_id=employee.station_id,
        shift_id=payload.shift_id,
        nozzle_id=payload.nozzle_id,
        product_id=payload.product_id,
        volume_litres=payload.volume_litres,
        unit_price=payload.unit_price,
        amount=amount,
        tender=payload.tender,
        credit_customer_id=payload.credit_customer_id,
    )
    db.add(sale)
    db.flush()
    db.add(Payment(station_id=employee.station_id, sale_id=sale.id, mode=payload.tender, amount=amount))
    if payload.tender == "credit":
        db.add(
            CreditLedgerEntry(
                station_id=employee.station_id,
                customer_id=payload.credit_customer_id,
                type="charge",
                amount=amount,
                reason=f"sale {sale.id}",
                reference_sale_id=sale.id,
            )
        )
    audit(
        db,
        station_id=employee.station_id,
        action="sale.posted",
        entity_type="sale",
        entity_id=sale.id,
        payload={"amount": str(amount), "tender": payload.tender, "volume_litres": str(payload.volume_litres)},
        actor=employee.id,
    )
    body = {
        "id": str(sale.id),
        "shift_id": str(sale.shift_id) if sale.shift_id else None,
        "nozzle_id": str(sale.nozzle_id) if sale.nozzle_id else None,
        "product_id": str(sale.product_id),
        "volume_litres": str(sale.volume_litres),
        "unit_price": str(sale.unit_price),
        "amount": str(amount),
        "tender": sale.tender,
        "created_at": sale.created_at.isoformat() if sale.created_at else None,
    }
    store(db, employee.station_id, "sales.create", idempotency_key, 201, body)
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
    employee: Employee = Depends(get_current_employee),
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
