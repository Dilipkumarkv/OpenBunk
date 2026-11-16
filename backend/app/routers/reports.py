from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..deps import get_db_dep, require_roles
from ..domain import round2
from ..models import Employee, FuelProduct, MeterReading, Nozzle, Payment, Sale, Shift
from ..schemas import CollectionSlice, CollectionsOut, DailySalesOut, ProductTotal

router = APIRouter(tags=["reports"])


@router.get("/reports/daily-sales", response_model=DailySalesOut)
def daily_sales(
    date_param: date = Query(alias="date"),
    employee: Employee = Depends(require_roles("owner", "manager", "accountant", "auditor")),
    db: Session = Depends(get_db_dep),
):
    """Metre-based daily sales: sums volumes/values of closed shifts' readings for the date."""
    rows = (
        db.query(FuelProduct.name, func.coalesce(func.sum(MeterReading.closing_litres - MeterReading.opening_litres), Decimal("0")), func.coalesce(func.sum((MeterReading.closing_litres - MeterReading.opening_litres) * MeterReading.unit_price), Decimal("0")))
        .join(Nozzle, Nozzle.product_id == FuelProduct.id)
        .join(MeterReading, MeterReading.nozzle_id == Nozzle.id)
        .join(Shift, Shift.id == MeterReading.shift_id)
        .filter(
            Shift.station_id == employee.station_id,
            Shift.business_date == date_param,
            Shift.status == "closed",
        )
        .group_by(FuelProduct.name)
        .all()
    )
    totals = [ProductTotal(product=name, volume_litres=vol, amount=round2(amt)) for name, vol, amt in rows]
    return DailySalesOut(
        date=date_param,
        totals=totals,
        grand_total_amount=round2(sum((t.amount for t in totals), Decimal("0"))),
        grand_total_litres=sum((t.volume_litres for t in totals), Decimal("0")),
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
        .filter(Payment.station_id == employee.station_id, Payment.created_at >= start, Payment.created_at < end)
        .group_by(Payment.mode)
        .all()
    )
    slices = [CollectionSlice(mode=mode, amount=round2(amount)) for mode, amount in rows]
    return CollectionsOut(date=date_param, slices=slices, total=round2(sum((s.amount for s in slices), Decimal("0"))))
