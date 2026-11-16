"""Shared credit-limit enforcement.

Every path that posts a credit charge must go through `post_charge`: the customer
row is locked, the balance is recomputed inside the same transaction, and a hard
limit rejection is raised unless an owner supplies an audited override.
"""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from .deps import audit
from .domain import round2
from .errors import ApiError
from .models import CreditCustomer, CreditLedgerEntry, Employee


def balance_for(db: Session, customer_id: UUID) -> Decimal:
    charges = (
        db.query(func.coalesce(func.sum(CreditLedgerEntry.amount), Decimal("0")))
        .filter(CreditLedgerEntry.customer_id == customer_id, CreditLedgerEntry.type == "charge")
        .scalar()
    )
    receipts = (
        db.query(func.coalesce(func.sum(CreditLedgerEntry.amount), Decimal("0")))
        .filter(CreditLedgerEntry.customer_id == customer_id, CreditLedgerEntry.type == "receipt")
        .scalar()
    )
    adjustments = (
        db.query(func.coalesce(func.sum(CreditLedgerEntry.amount), Decimal("0")))
        .filter(CreditLedgerEntry.customer_id == customer_id, CreditLedgerEntry.type == "adjustment")
        .scalar()
    )
    return round2(charges - receipts + adjustments)


def lock_customer(db: Session, station_id: UUID, customer_id: UUID) -> CreditCustomer:
    customer = (
        db.query(CreditCustomer)
        .filter(CreditCustomer.id == customer_id, CreditCustomer.station_id == station_id)
        .with_for_update()
        .first()
    )
    if customer is None:
        raise ApiError(404, "Credit customer not found")
    if not customer.active:
        raise ApiError(422, "Credit customer is inactive — charge rejected")
    return customer


def post_charge(
    db: Session,
    *,
    station_id: UUID,
    customer_id: UUID,
    amount: Decimal,
    reason: str | None,
    actor: Employee,
    reference_sale_id: UUID | None = None,
    override_reason: str | None = None,
) -> CreditLedgerEntry:
    customer = lock_customer(db, station_id, customer_id)
    amount = round2(amount)
    if amount <= 0:
        raise ApiError(422, "Credit charge amount must be greater than zero")

    balance = balance_for(db, customer.id)
    projected = round2(balance + amount)
    if projected > customer.credit_limit:
        override = (override_reason or "").strip()
        if actor.role != "owner" or len(override) < 10:
            raise ApiError(
                422,
                "Credit limit exceeded — charge rejected (owner override requires a reason)",
                details={
                    "code": "credit_limit_exceeded",
                    "balance": str(balance),
                    "credit_limit": str(customer.credit_limit),
                    "projected": str(projected),
                    "override_allowed": actor.role == "owner",
                },
            )
        audit(
            db,
            station_id=station_id,
            action="credit.limit_override",
            entity_type="credit_customer",
            entity_id=customer.id,
            reason=override,
            payload={
                "balance": str(balance),
                "amount": str(amount),
                "credit_limit": str(customer.credit_limit),
                "projected": str(projected),
            },
            actor=actor.id,
        )

    entry = CreditLedgerEntry(
        station_id=station_id,
        customer_id=customer.id,
        type="charge",
        amount=amount,
        reason=reason,
        reference_sale_id=reference_sale_id,
    )
    db.add(entry)
    db.flush()
    return entry
