"""CSV import/export (spec Phase 06 integration #1).

Export: read-only, owner/accountant/auditor, audited (`data.exported`).
Import: create-only credit customers, owner/manager/accountant.
`validate_only=true` (default) performs a dry run and persists nothing.
"""

import csv
import io
from decimal import Decimal, InvalidOperation
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..deps import audit, get_db_dep, require_reauth, require_roles
from ..domain import round2
from ..errors import ApiError
from ..models import CreditCustomer, CreditLedgerEntry, Employee, MeterReading, Payment, Sale, Shift

router = APIRouter(tags=["csv"])

MAX_IMPORT_BYTES = 1_000_000  # 1 MB
MAX_IMPORT_ROWS = 500

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _safe_cell(value):
    """Prevent spreadsheet formula injection from customer-entered text."""
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return f"'{value}"
    return value


def _csv_response(filename: str, rows: list[list]) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    for row in rows:
        writer.writerow([_safe_cell(cell) for cell in row])
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export.csv")
def export_csv(
    type: str = Query(pattern="^(sales|collections|credit-ledger|shifts)$"),
    employee: Employee = Depends(require_roles("owner", "accountant", "auditor", "manager")),
    _: Employee = Depends(require_reauth),
    db: Session = Depends(get_db_dep),
):
    sid = employee.station_id
    audit(db, station_id=sid, action="data.exported", entity_type="export_csv", entity_id=type, actor=employee.id)

    if type == "sales":
        rows = [["id", "created_at", "tender", "volume_litres", "unit_price", "amount"]]
        for s in db.query(Sale).filter(Sale.station_id == sid).order_by(Sale.created_at).all():
            rows.append([s.id, s.created_at.isoformat(timespec="seconds"), s.tender, s.volume_litres, s.unit_price, s.amount])
        db.commit()
        return _csv_response("openbunk-sales.csv", rows)

    if type == "collections":
        rows = [["date", "mode", "amount"]]
        grouped = (
            db.query(func.date(Payment.created_at), Payment.mode, func.sum(Payment.amount))
            .filter(Payment.station_id == sid, Payment.mode != "credit")
            .group_by(func.date(Payment.created_at), Payment.mode)
            .order_by(func.date(Payment.created_at))
            .all()
        )
        for day, mode, amount in grouped:
            rows.append([day, mode, round2(amount or Decimal("0"))])
        db.commit()
        return _csv_response("openbunk-collections.csv", rows)

    if type == "credit-ledger":
        rows = [["created_at", "account_code", "customer", "type", "amount", "reason"]]
        query = (
            db.query(CreditLedgerEntry, CreditCustomer)
            .join(CreditCustomer, CreditLedgerEntry.customer_id == CreditCustomer.id)
            .filter(CreditLedgerEntry.station_id == sid)
            .order_by(CreditLedgerEntry.created_at)
        )
        for entry, customer in query.all():
            rows.append([entry.created_at.isoformat(timespec="seconds"), customer.account_code, customer.name, entry.type, entry.amount, entry.reason or ""])
        db.commit()
        return _csv_response("openbunk-credit-ledger.csv", rows)

    # shifts (with readings)
    rows = [["business_date", "kind", "status", "revenue_total", "readings"]]
    shifts = db.query(Shift).filter(Shift.station_id == sid).order_by(Shift.business_date).all()
    readings = db.query(MeterReading).filter(MeterReading.station_id == sid).all()
    by_shift: dict[UUID, int] = {}
    for r in readings:
        by_shift[r.shift_id] = by_shift.get(r.shift_id, 0) + 1
    for s in shifts:
        rows.append([s.business_date, s.kind, s.status, s.revenue_total, by_shift.get(s.id, 0)])
    db.commit()
    return _csv_response("openbunk-shifts.csv", rows)


def _parse_customer_row(row: dict) -> tuple[dict | None, str | None]:
    code = (row.get("account_code") or "").strip()
    name = (row.get("name") or "").strip()
    limit_raw = (row.get("credit_limit") or "").strip()
    if not code or not name or not limit_raw:
        return None, "account_code, name and credit_limit are required"
    try:
        limit = Decimal(limit_raw)
    except (InvalidOperation, ValueError):
        return None, f"credit_limit is not a number: {limit_raw!r}"
    if limit < 0:
        return None, "credit_limit must be >= 0"
    if len(code) > 32 or len(name) > 200:
        return None, "field too long"
    return {"account_code": code, "name": name, "credit_limit": limit}, None


@router.post("/credit/customers/import.csv")
async def import_credit_customers(
    file: UploadFile = File(...),
    validate_only: bool = Query(default=True),
    employee: Employee = Depends(require_roles("owner", "manager", "accountant")),
    db: Session = Depends(get_db_dep),
):
    if file.content_type not in ("text/csv", "application/vnd.ms-excel", "application/octet-stream", "text/plain"):
        raise ApiError(415, "Expected a CSV file")
    content = await file.read()
    if len(content) > MAX_IMPORT_BYTES:
        raise ApiError(413, "CSV larger than 1 MB")

    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    required = {"account_code", "name", "credit_limit"}
    if not reader.fieldnames or not required.issubset({f.strip() if f else f for f in reader.fieldnames}):
        raise ApiError(422, f"CSV must contain columns: {sorted(required)}")

    results = []
    parsed_rows = []
    for index, raw in enumerate(reader, start=2):  # line 2 = first data row
        if index - 2 >= MAX_IMPORT_ROWS:
            results.append({"line": index, "ok": False, "error": f"row cap {MAX_IMPORT_ROWS} reached — import truncated"})
            break
        row = {k.strip() if k else k: v for k, v in raw.items()}
        parsed, error = _parse_customer_row(row)
        if parsed is None:
            results.append({"line": index, "ok": False, "error": error})
            continue
        exists = db.query(CreditCustomer).filter(
            CreditCustomer.station_id == employee.station_id,
            CreditCustomer.account_code == parsed["account_code"],
        ).first()
        if exists is not None:
            results.append({"line": index, "ok": False, "error": f"duplicate account_code {parsed['account_code']}"})
            continue
        results.append({"line": index, "ok": True, "account_code": parsed["account_code"]})
        parsed_rows.append(parsed)

    created = 0
    if not validate_only:
        for parsed in parsed_rows:
            db.add(CreditCustomer(station_id=employee.station_id, **parsed))
            created += 1
        audit(
            db,
            station_id=employee.station_id,
            action="credit.import",
            entity_type="credit_customer",
            reason="csv import",
            payload={"created": created, "failed": sum(1 for r in results if not r["ok"])},
            actor=employee.id,
        )
        db.commit()

    return {
        "validate_only": validate_only,
        "created": 0 if validate_only else created,
        "rows": results,
        "summary": {
            "total": len(results),
            "valid": sum(1 for r in results if r["ok"]),
            "invalid": sum(1 for r in results if not r["ok"]),
        },
    }
