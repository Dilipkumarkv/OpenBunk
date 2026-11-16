"""SQLAlchemy 2 models. Mirror docs/domain-model.md.

Money is NUMERIC(12,2); volumes NUMERIC(14,1). Posted business records are never
hard-deleted; corrections are reversal/adjustment entries + audit events.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


MONEY = Numeric(12, 2)
LITRES = Numeric(14, 1)
TOTALIZER = Numeric(14, 1)


class Station(Base):
    __tablename__ = "stations"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500))
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata", nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="INR", nullable=False)
    business_day_start: Mapped[str] = mapped_column(String(16), default="06:00", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (UniqueConstraint("station_id", "code", name="uq_employee_station_code"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    station_id: Mapped[UUID] = mapped_column(ForeignKey("stations.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="attendant", nullable=False)  # owner|manager|attendant
    pin_hash: Mapped[str | None] = mapped_column(String(300))  # pbkdf2 salt$hash; demo only in prototype
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class FuelProduct(Base):
    __tablename__ = "fuel_products"
    __table_args__ = (UniqueConstraint("station_id", "code", name="uq_product_station_code"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    station_id: Mapped[UUID] = mapped_column(ForeignKey("stations.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    unit: Mapped[str] = mapped_column(String(8), default="litre", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class FuelPrice(Base):
    """Server-authoritative selling price. Sales and readings never use a client price."""

    __tablename__ = "fuel_prices"
    __table_args__ = (
        Index("ix_fuel_prices_station_product_effective", "station_id", "product_id", "effective_from"),
        CheckConstraint("unit_price > 0", name="ck_fuel_price_positive"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    station_id: Mapped[UUID] = mapped_column(ForeignKey("stations.id"), nullable=False, index=True)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("fuel_products.id"), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("employees.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Tank(Base):
    __tablename__ = "tanks"
    __table_args__ = (
        UniqueConstraint("station_id", "label", name="uq_tank_station_label"),
        CheckConstraint("capacity_litres >= 0", name="ck_tank_capacity_nonneg"),
        CheckConstraint("opening_book_litres >= 0", name="ck_tank_opening_nonneg"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    station_id: Mapped[UUID] = mapped_column(ForeignKey("stations.id"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(32), nullable=False)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("fuel_products.id"), nullable=False)
    capacity_litres: Mapped[Decimal] = mapped_column(LITRES, nullable=False)
    opening_book_litres: Mapped[Decimal] = mapped_column(LITRES, default=Decimal("0"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Nozzle(Base):
    __tablename__ = "nozzles"
    __table_args__ = (UniqueConstraint("station_id", "label", name="uq_nozzle_station_label"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    station_id: Mapped[UUID] = mapped_column(ForeignKey("stations.id"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(16), nullable=False)  # P1, D1…
    tank_id: Mapped[UUID] = mapped_column(ForeignKey("tanks.id"), nullable=False)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("fuel_products.id"), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Shift(Base):
    __tablename__ = "shifts"
    __table_args__ = (
        CheckConstraint("kind IN ('morning','afternoon','night')", name="ck_shift_kind"),
        CheckConstraint("status IN ('draft','closed')", name="ck_shift_status"),
        Index("ix_shifts_station_date", "station_id", "business_date"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    station_id: Mapped[UUID] = mapped_column(ForeignKey("stations.id"), nullable=False, index=True)
    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by: Mapped[UUID | None] = mapped_column(ForeignKey("employees.id"))
    revenue_total: Mapped[Decimal | None] = mapped_column(MONEY)
    collections: Mapped[dict | None] = mapped_column(JSON)
    variance_amount: Mapped[Decimal | None] = mapped_column(MONEY)
    variance_reason: Mapped[str | None] = mapped_column(String(300))
    rollover_values: Mapped[dict | None] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    readings: Mapped[list["MeterReading"]] = relationship(back_populates="shift")


class MeterReading(Base):
    __tablename__ = "meter_readings"
    __table_args__ = (
        UniqueConstraint("shift_id", "nozzle_id", name="uq_reading_shift_nozzle"),
        CheckConstraint("opening_litres >= 0 AND closing_litres >= 0", name="ck_reading_nonneg"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    station_id: Mapped[UUID] = mapped_column(ForeignKey("stations.id"), nullable=False, index=True)
    shift_id: Mapped[UUID] = mapped_column(ForeignKey("shifts.id"), nullable=False, index=True)
    nozzle_id: Mapped[UUID] = mapped_column(ForeignKey("nozzles.id"), nullable=False)
    opening_litres: Mapped[Decimal] = mapped_column(TOTALIZER, nullable=False)
    closing_litres: Mapped[Decimal] = mapped_column(TOTALIZER, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    recorded_by: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), nullable=False)

    shift: Mapped[Shift] = relationship(back_populates="readings")


class FuelReceipt(Base):
    __tablename__ = "fuel_receipts"
    __table_args__ = (CheckConstraint("quantity_litres > 0", name="ck_receipt_qty_positive"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    station_id: Mapped[UUID] = mapped_column(ForeignKey("stations.id"), nullable=False, index=True)
    tank_id: Mapped[UUID] = mapped_column(ForeignKey("tanks.id"), nullable=False)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("fuel_products.id"), nullable=False)
    quantity_litres: Mapped[Decimal] = mapped_column(LITRES, nullable=False)
    supplier: Mapped[str | None] = mapped_column(String(200))
    invoice_no: Mapped[str | None] = mapped_column(String(64))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("employees.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class StockMovement(Base):
    """Append-only stock ledger. Current stock derives from this table."""

    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint("kind IN ('opening','receipt','sale','adjustment')", name="ck_movement_kind"),
        Index("ix_stock_movements_tank_created", "tank_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    station_id: Mapped[UUID] = mapped_column(ForeignKey("stations.id"), nullable=False, index=True)
    tank_id: Mapped[UUID] = mapped_column(ForeignKey("tanks.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    delta_litres: Mapped[Decimal] = mapped_column(LITRES, nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(32))
    source_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class CreditCustomer(Base):
    __tablename__ = "credit_customers"
    __table_args__ = (
        UniqueConstraint("station_id", "account_code", name="uq_credit_account_station"),
        CheckConstraint("credit_limit >= 0", name="ck_credit_limit_nonneg"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    station_id: Mapped[UUID] = mapped_column(ForeignKey("stations.id"), nullable=False, index=True)
    account_code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    credit_limit: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CreditLedgerEntry(Base):
    """Append-only. balance = Σ charge − Σ receipt ± Σ signed adjustment."""

    __tablename__ = "credit_ledger_entries"
    __table_args__ = (
        CheckConstraint("type IN ('charge','receipt','adjustment')", name="ck_credit_entry_type"),
        Index("ix_credit_ledger_customer_created", "customer_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    station_id: Mapped[UUID] = mapped_column(ForeignKey("stations.id"), nullable=False, index=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("credit_customers.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)  # receipts negative is NOT used; sign via type
    reason: Mapped[str | None] = mapped_column(String(300))
    reference_sale_id: Mapped[UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Sale(Base):
    __tablename__ = "sales"
    __table_args__ = (
        CheckConstraint("tender IN ('cash','upi','card','credit','other')", name="ck_sale_tender"),
        CheckConstraint("volume_litres >= 0 AND amount >= 0", name="ck_sale_nonneg"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    station_id: Mapped[UUID] = mapped_column(ForeignKey("stations.id"), nullable=False, index=True)
    shift_id: Mapped[UUID | None] = mapped_column(ForeignKey("shifts.id"))
    nozzle_id: Mapped[UUID | None] = mapped_column(ForeignKey("nozzles.id"))
    product_id: Mapped[UUID] = mapped_column(ForeignKey("fuel_products.id"), nullable=False)
    volume_litres: Mapped[Decimal] = mapped_column(LITRES, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    tender: Mapped[str] = mapped_column(String(16), nullable=False)
    credit_customer_id: Mapped[UUID | None] = mapped_column(ForeignKey("credit_customers.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (CheckConstraint("mode IN ('cash','upi','card','credit','other')", name="ck_payment_mode"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    station_id: Mapped[UUID] = mapped_column(ForeignKey("stations.id"), nullable=False, index=True)
    sale_id: Mapped[UUID] = mapped_column(ForeignKey("sales.id"), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AuditEvent(Base):
    """Append-only: no update/delete paths exist in this codebase."""

    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_station_created", "station_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    station_id: Mapped[UUID] = mapped_column(ForeignKey("stations.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(64))
    reason: Mapped[str | None] = mapped_column(String(300))
    payload: Mapped[dict | None] = mapped_column(JSON)
    actor: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class SessionToken(Base):
    __tablename__ = "session_tokens"
    __table_args__ = (CheckConstraint("kind IN ('access','refresh')", name="ck_session_token_kind"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    station_id: Mapped[UUID] = mapped_column(ForeignKey("stations.id"), nullable=False, index=True)
    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), default="access", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LoginAttempt(Base):
    """Consecutive-failure tracking + lockout, keyed by (station, employee_code)."""

    __tablename__ = "login_attempts"
    __table_args__ = (UniqueConstraint("station_id", "employee_code", name="uq_login_attempt_key"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    station_id: Mapped[UUID] = mapped_column(ForeignKey("stations.id"), nullable=False)
    employee_code: Mapped[str] = mapped_column(String(32), nullable=False)
    failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("station_id", "endpoint", "key", name="uq_idempotency"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    station_id: Mapped[UUID] = mapped_column(ForeignKey("stations.id"), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(64), nullable=False)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str | None] = mapped_column(String(64))
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ReauthAttempt(Base):
    """Consecutive failed re-authentication attempts, keyed by employee."""

    __tablename__ = "reauth_attempts"
    __table_args__ = (UniqueConstraint("employee_id", name="uq_reauth_attempt_employee"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    station_id: Mapped[UUID] = mapped_column(ForeignKey("stations.id"), nullable=False)
    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), nullable=False)
    failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
