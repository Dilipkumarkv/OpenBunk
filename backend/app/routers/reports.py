from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..deps import get_db_dep, require_roles
from ..domain import compute_volume, round2
from ..models import Employee, FuelProduct, MeterReading, Nozzle, Payment, Shift
from ..schemas import CollectionSlice, CollectionsOut, DailySalesOut, ProductTotal

router = APIRouter(tags=["reports"])


@router.get("/reports/daily-sales", response_model=DailySalesOut)
def daily_sales(
    date_param: date = Query(alias="date"),
    employee: Employee = Depends(require_roles("owner", "manager", "accountant", "auditor")),
    db: Session = Depends(get_db_dep),
):
    """Metre-based daily sales, applying the rollover value stored at shift close."""
    rows = (
        db.query(MeterReading, Nozzle, FuelProduct, Shift)
        .join(Nozzle, Nozzle.id == MeterReading.nozzle_id)
        .join(FuelProduct, FuelProduct.id == Nozzle.product_id)
        .join(Shift, Shift.id == MeterReading.shift_id)
        .filter(
            Shift.station_id == employee.station_id,
            Shift.business_date == date_param,
            Shift.status == "closed",
        )
        .all()
    )

    totals: dict[str, list[Decimal]] = {}
    for reading, _nozzle, product, shift in rows:
        rollover = None
        if shift.rollover_values:
            code = (product.code or "").lower()
            raw = shift.rollover_values.get(code)
            if raw is not None:
                rollover = Decimal(str(raw))
        volume = compute_volume(reading.opening_litres, reading.closing_litres, rollover)
        bucket = totals.setdefault(product.name, [Decimal("0"), Decimal("0")])
        bucket[0] += volume
        bucket[1] += round2(volume * reading.unit_price)

    product_totals = [
        ProductTotal(product=name, volume_litres=volume, amount=round2(amount))
        for name, (volume, amount) in sorted(totals.items())
    ]
    return DailySalesOut(
        date=date_param,
        totals=product_totals,
        grand_total_amount=round2(sum((t.amount for t in product_totals), Decimal("0"))),
        grand_total_litres=sum((t.volume_litres for t in product_totals), Decimal("0")),
    )


@router.get("/reports/collections", response_model=CollectionsOut)
def collections(
    date_param: date = Query(alias="date"),
    employee: Employee = Depends(require_roles("owner", "manager", "accountant", "auditor")),
    db: Session = Depends(get_db_dep),
):
    start = datetime.combine(date_param, datetime.min.time())
    end = start + timedelta(days=1)
    rows = (
        db.query(Payment.mode, func.coalesce(func.sum(Payment.amount), Decimal("0")))
        .filter(
            Payment.station_id == employee.station_id,
            Payment.created_at >= start,
            Payment.created_at < end,
            Payment.mode != "credit",  # credit is receivable, not collected cash
        )
        .group_by(Payment.mode)
        .all()
    )
    slices = [CollectionSlice(mode=mode, amount=round2(amount)) for mode, amount in rows]
    return CollectionsOut(date=date_param, slices=slices, total=round2(sum((s.amount for s in slices), Decimal("0"))))
