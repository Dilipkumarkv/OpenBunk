from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Auth ----------
class SessionRequest(BaseModel):
    station_code: str = Field(min_length=1, max_length=32)
    employee_code: str = Field(min_length=1, max_length=32)
    pin: str = Field(min_length=4, max_length=64)


class SessionTokensOut(BaseModel):
    access_token: str
    refresh_token: str
    access_expires_at: datetime
    refresh_expires_at: datetime
    employee: "EmployeeOut"
    station: "StationOut"


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class LoginAttemptOut(BaseModel):
    employee_code: str
    failures: int
    locked_until: datetime | None


# ---------- Tank adjustment ----------
class TankAdjustmentCreate(BaseModel):
    delta_litres: Decimal  # signed: + in, − out
    reason: str = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def non_zero(self):
        if self.delta_litres == 0:
            raise ValueError("delta_litres must be non-zero (signed)")
        return self


# ---------- Staff / roles ----------
class EmployeeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=200)
    role: Literal["owner", "manager", "cashier", "accountant", "auditor"]
    pin: str = Field(min_length=4, max_length=64)


class EmployeeRoleUpdate(BaseModel):
    role: Literal["owner", "manager", "cashier", "accountant", "auditor"]


# ---------- Station ----------
class StationOut(ORMModel):
    id: UUID
    code: str
    name: str
    address: str | None
    timezone: str
    currency: str
    business_day_start: str


class StationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    address: str | None = Field(default=None, max_length=500)
    timezone: str | None = Field(default=None, max_length=64)
    currency: str | None = Field(default=None, min_length=3, max_length=8)
    business_day_start: str | None = Field(default=None, max_length=16)


# ---------- Employee ----------
class EmployeeOut(ORMModel):
    id: UUID
    code: str
    name: str
    role: str


# ---------- Catalog ----------
class FuelProductOut(ORMModel):
    id: UUID
    code: str
    name: str
    unit: str


class FuelProductCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=64)
    unit: str = Field(default="litre", max_length=8)


class TankOut(ORMModel):
    id: UUID
    label: str
    product_id: UUID
    capacity_litres: Decimal
    opening_book_litres: Decimal


class TankCreate(BaseModel):
    label: str = Field(min_length=1, max_length=32)
    product_id: UUID
    capacity_litres: Decimal = Field(ge=0)
    opening_book_litres: Decimal = Field(default=Decimal("0"), ge=0)


class NozzleOut(ORMModel):
    id: UUID
    label: str
    tank_id: UUID
    product_id: UUID


class NozzleCreate(BaseModel):
    label: str = Field(min_length=1, max_length=16)
    tank_id: UUID
    product_id: UUID


class TankStockOut(BaseModel):
    tank_id: UUID
    label: str
    book_stock_litres: Decimal


# ---------- Shifts ----------
ShiftKind = Literal["morning", "afternoon", "night"]


class ShiftOpen(BaseModel):
    kind: ShiftKind
    business_date: date | None = None
    employee_id: UUID | None = None  # defaults to caller


class MeterReadingIn(BaseModel):
    nozzle_id: UUID
    opening_litres: Decimal = Field(ge=0)
    closing_litres: Decimal = Field(ge=0)
    unit_price: Decimal = Field(ge=0)

    @field_validator("opening_litres", "closing_litres", "unit_price", mode="before")
    @classmethod
    def coerce_number(cls, v):
        try:
            return Decimal(str(v))
        except (InvalidOperation, ValueError, TypeError) as e:
            raise ValueError("must be a number") from e


class ReadingsUpsert(BaseModel):
    readings: list[MeterReadingIn]


class MeterReadingOut(ORMModel):
    id: UUID
    nozzle_id: UUID
    opening_litres: Decimal
    closing_litres: Decimal
    unit_price: Decimal


class ShiftOut(ORMModel):
    id: UUID
    station_id: UUID
    employee_id: UUID
    kind: str
    business_date: date
    status: str
    opened_at: datetime
    closed_at: datetime | None
    revenue_total: Decimal | None


class ShiftDetailOut(ShiftOut):
    readings: list[MeterReadingOut] = []


class RolloverAuthorization(BaseModel):
    petrol: bool = False
    diesel: bool = False
    petrol_rollover_value: Decimal | None = Field(default=None, ge=0)
    diesel_rollover_value: Decimal | None = Field(default=None, ge=0)


class ShiftClose(BaseModel):
    rollover: RolloverAuthorization = RolloverAuthorization()


class ValidationIssue(BaseModel):
    field: str
    message: str


class ValidationOut(BaseModel):
    valid: bool
    issues: list[ValidationIssue]


class Page(BaseModel):
    total: int
    items: list


class ShiftPage(BaseModel):
    total: int
    items: list[ShiftOut]


# ---------- Credit ----------
class CreditCustomerOut(ORMModel):
    id: UUID
    account_code: str
    name: str
    credit_limit: Decimal
    active: bool
    balance: Decimal | None = None


class CreditCustomerCreate(BaseModel):
    account_code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=200)
    credit_limit: Decimal = Field(ge=0)


class CreditEntryCreate(BaseModel):
    type: Literal["charge", "receipt", "adjustment"]
    # charge/receipt: positive. adjustment: signed (positive adds to balance, negative subtracts).
    amount: Decimal
    reason: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def check_amount(self):
        if self.type in ("charge", "receipt") and self.amount <= 0:
            raise ValueError("amount must be greater than zero for charge/receipt")
        if self.type == "adjustment" and self.amount == 0:
            raise ValueError("adjustment amount must be non-zero (signed)")
        return self


class CreditEntryOut(ORMModel):
    id: UUID
    type: str
    amount: Decimal
    reason: str | None
    created_at: datetime


class CreditLedgerOut(BaseModel):
    customer: CreditCustomerOut
    balance: Decimal
    entries: list[CreditEntryOut]


# ---------- Fuel receipts ----------
class FuelReceiptCreate(BaseModel):
    tank_id: UUID
    product_id: UUID
    quantity_litres: Decimal = Field(gt=0)
    supplier: str | None = Field(default=None, max_length=200)
    invoice_no: str | None = Field(default=None, max_length=64)


class FuelReceiptOut(ORMModel):
    id: UUID
    tank_id: UUID
    product_id: UUID
    quantity_litres: Decimal
    supplier: str | None
    invoice_no: str | None
    received_at: datetime


# ---------- Reports ----------
class ProductTotal(BaseModel):
    product: str
    volume_litres: Decimal
    amount: Decimal


class DailySalesOut(BaseModel):
    date: date
    totals: list[ProductTotal]
    grand_total_amount: Decimal
    grand_total_litres: Decimal


class CollectionSlice(BaseModel):
    mode: str
    amount: Decimal


class CollectionsOut(BaseModel):
    date: date
    slices: list[CollectionSlice]
    total: Decimal


# ---------- Audit ----------
class AuditEventOut(ORMModel):
    id: UUID
    action: str
    entity_type: str
    entity_id: str | None
    reason: str | None
    actor: str | None
    created_at: datetime


class MeResponse(BaseModel):
    employee: "EmployeeOut"
    station: "StationOut"


SessionTokensOut.model_rebuild()
MeResponse.model_rebuild()
