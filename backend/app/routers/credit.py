from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..deps import audit, get_db_dep, paginate, require_roles
from ..domain import round2
from ..errors import ApiError
from ..models import CreditCustomer, CreditLedgerEntry, Employee
from ..schemas import (
    CreditCustomerCreate,
    CreditCustomerOut,
    CreditEntryCreate,
    CreditEntryOut,
    CreditLedgerOut,
)

router = APIRouter(tags=["credit"])


def _balance(db: Session, customer_id: UUID) -> Decimal:
    charges = db.query(func.coalesce(func.sum(CreditLedgerEntry.amount), Decimal("0"))).filter(
        CreditLedgerEntry.customer_id == customer_id, CreditLedgerEntry.type == "charge"
    ).scalar()
    receipts = db.query(func.coalesce(func.sum(CreditLedgerEntry.amount), Decimal("0"))).filter(
        CreditLedgerEntry.customer_id == customer_id, CreditLedgerEntry.type == "receipt"
    ).scalar()
    adjustments = db.query(func.coalesce(func.sum(CreditLedgerEntry.amount), Decimal("0"))).filter(
        CreditLedgerEntry.customer_id == customer_id, CreditLedgerEntry.type == "adjustment"
    ).scalar()
    return round2(charges - receipts + adjustments)


@router.post("/credit/customers", response_model=CreditCustomerOut, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CreditCustomerCreate,
    employee: Employee = Depends(require_roles("owner", "manager", "accountant")),
    db: Session = Depends(get_db_dep),
):
    existing = db.query(CreditCustomer).filter(
        CreditCustomer.station_id == employee.station_id, CreditCustomer.account_code == payload.account_code
    ).first()
    if existing is not None:
        raise ApiError(409, "Account code already exists")
    customer = CreditCustomer(station_id=employee.station_id, **payload.model_dump())
    db.add(customer)
    audit(db, station_id=employee.station_id, action="credit.customer_created", entity_type="credit_customer", entity_id=customer.id, actor=employee.id)
    db.commit()
    db.refresh(customer)
    return CreditCustomerOut.model_validate(customer).model_copy(update={"balance": Decimal("0")})


@router.get("/credit/customers", response_model=list[CreditCustomerOut])
def list_customers(
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    employee: Employee = Depends(require_roles("owner", "manager", "accountant")),
    db: Session = Depends(get_db_dep),
):

    limit, offset = paginate(limit, offset)
    query = db.query(CreditCustomer).filter(CreditCustomer.station_id == employee.station_id)
    if q:
        pattern = f"%{q}%"
        query = query.filter((CreditCustomer.name.ilike(pattern)) | (CreditCustomer.account_code.ilike(pattern)))
    customers = query.order_by(CreditCustomer.account_code).offset(offset).limit(limit).all()
    return [CreditCustomerOut.model_validate(c).model_copy(update={"balance": _balance(db, c.id)}) for c in customers]


@router.get("/credit/customers/{customer_id}/ledger", response_model=CreditLedgerOut)
def get_ledger(customer_id: UUID, employee: Employee = Depends(require_roles("owner", "manager", "accountant")), db: Session = Depends(get_db_dep)):
    customer = db.get(CreditCustomer, customer_id)
    if customer is None or customer.station_id != employee.station_id:
        raise ApiError(404, "Credit customer not found")
    entries = (
        db.query(CreditLedgerEntry)
        .filter(CreditLedgerEntry.customer_id == customer.id)
        .order_by(CreditLedgerEntry.created_at.desc())
        .limit(100)
        .all()
    )
    return CreditLedgerOut(
        customer=CreditCustomerOut.model_validate(customer).model_copy(update={"balance": _balance(db, customer.id)}),
        balance=_balance(db, customer.id),
        entries=[CreditEntryOut.model_validate(e) for e in entries],
    )


@router.post("/credit/customers/{customer_id}/entries", status_code=status.HTTP_201_CREATED)
def post_entry(
    customer_id: UUID,
    payload: CreditEntryCreate,
    employee: Employee = Depends(require_roles("owner", "manager", "accountant")),
    db: Session = Depends(get_db_dep),
):
    customer = db.get(CreditCustomer, customer_id)
    if customer is None or customer.station_id != employee.station_id:
        raise ApiError(404, "Credit customer not found")
    entry = CreditLedgerEntry(
        station_id=employee.station_id,
        customer_id=customer.id,
        type=payload.type,
        amount=payload.amount,
        reason=payload.reason,
    )
    db.add(entry)
    audit(
        db,
        station_id=employee.station_id,
        action=f"credit.{payload.type}_posted",
        entity_type="credit_ledger_entry",
        entity_id=entry.id,
        reason=payload.reason,
        actor=employee.id,
    )
    db.commit()
    db.refresh(entry)
    balance = _balance(db, customer.id)
    return {
        "entry": CreditEntryOut.model_validate(entry),
        "balance": str(balance),
        "credit_limit": str(customer.credit_limit),
        "limit_status": "over_limit" if balance > customer.credit_limit else ("near_limit" if balance >= customer.credit_limit * Decimal("0.8") else "active"),
    }
