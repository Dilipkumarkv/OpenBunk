# OpenBunk — Domain Model

Status: v0.1 (prototype; documents intended production semantics. Persistence arrives in Phase 04+.)
Scope: one station initially; design for future multi-station support without implementing it.
Timezone: Asia/Kolkata (station timezone; all timestamps stored timezone-aware, UTC at rest recommended in production).

## Entities

| Entity            | Purpose                       | Key fields                                                                                                                            |
| ----------------- | ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Station           | Single pump identity          | id, code, name, address, timezone, currency, businessDayStart                                                                         |
| User              | Login identity                | id, email/phone, displayName, credentialHash, active                                                                                  |
| Role              | Authorization group           | id, name (owner / manager / attendant), permissions                                                                                   |
| Employee          | Staff on site (may ≠ User)    | id, stationId, employeeCode, name, role, active                                                                                       |
| Shift             | Worked interval per station   | id, stationId, employeeId, kind (morning/afternoon/night), startsAt, endsAt, status (draft/posted/closed)                             |
| FuelProduct       | Sellable fuel                 | id, name (petrol/diesel), unit (litre), density?                                                                                      |
| Nozzle            | Dispenser point               | id, stationId, tankId, productId, label (P1/D1…), priceUnitId?                                                                        |
| Tank              | Storage                       | id, stationId, name/label (T-01), productId, capacityLitres, bookStockLitres (derived; see below)                                     |
| MeterReading      | Totalizer capture             | id, stationId, nozzleId, shiftId, timestamp, totalizerLitres, operatorId, unit, rolloverEventId?                                      |
| FuelReceipt       | Tanker delivery               | id, stationId, tankId, supplierId?, quantityLitres, invoiceNo, receivedAt, postedBy                                                   |
| Sale              | One retail transaction        | id, stationId, shiftId, nozzleId?, productId, volumeLitres, unitPrice, amount, tender (cash/upi/card/credit/other), creditCustomerId? |
| Payment           | Settlement split of a sale    | id, stationId, saleId, mode (cash/upi/card/credit/other), amount                                                                      |
| CreditCustomer    | Account customer (fleet/agro) | id, stationId, accountCode (AC-###), name, creditLimit, active                                                                        |
| CreditLedgerEntry | Posted charge or receipt      | id, stationId, creditCustomerId, type (charge/receipt/adjustment), amount, referenceSaleId?, reason?, postedAt                        |
| Expense           | Petty cash out                | id, stationId, category, amount, spentAt, approvedBy?                                                                                 |
| DipReading        | Physical stock measurement    | id, stationId, tankId, timestamp, measuredLitres, measuredBy                                                                          |
| StockMovement     | Authoritative stock change    | id, stationId, tankId, kind (receipt/sale/adjustment), deltaLitres, sourceId (receipt/sale/adjustment), createdAt                     |
| AuditEvent        | Privileged action log         | id, stationId, actorId, action, entityType, entityId, reason?, at, payloadJson?                                                       |
| PriceSnapshot     | Price history                 | id, stationId, productId, unitPrice, effectiveFrom (shift close captures price onto the shift — history is never rewritten)           |

Optional later: Lubricant, Supplier, TankerDelivery, attachments.

## Core invariants

1. Every transaction belongs to exactly one station (`stationId` mandatory).
2. Every meter reading identifies nozzle, shift, timestamp, operator, unit (`litre`).
3. Meter readings cannot decrease unless an authorized rollover/reset event is recorded
   (explicitly authorized; never inferred from the numbers).
4. Opening reading for a shift must reconcile with the prior accepted closing reading,
   or carry a documented exception (e.g. physical reset verified and signed off).
5. Volume = closing totalizer − opening totalizer; rollover handled explicitly
   (see calculations.md).
6. Money uses decimal precision — never binary float for persisted currency.
   The prototype UI computes in floats but rounds half-up to 2 dp at value boundaries (`src/domain/money.ts`);
   persisted values will be integer minor units (paise) or SQL `numeric`.
7. Price is snapshotted on shift close / sale; later price changes do not rewrite history.
8. Posted/closed records are immutable; corrections are reversal/adjustment entries
   with reason + audit event (`AuditEvent`), never updates in place.
9. Cash + UPI + card + credit + other must reconcile to sale total, subject to explicitly
   recorded rounding/variance.
10. Stock movement ledger (`StockMovement`) is authoritative; current stock is derived
    (opening + receipts − sales ± approved adjustments), or safely cached from movements.
11. Physical dip (`DipReading`) variance is a reconciliation record, not a silent stock mutation.
12. Timezone-aware timestamps; station timezone defaults to Asia/Kolkata.
13. Every privileged action records actor, timestamp, reason, affected entity.

## Relationships (summary)

- Station 1—n Employee, Shift, Nozzle, Tank, CreditCustomer, DipReading, Expense, Sale, AuditEvent.
- Tank 1—n StockMovement, DipReading; Nozzle n—1 Tank (today), Nozzle n—1 FuelProduct.
- Shift 1—n Sale, MeterReading, Payment (via Sale).
- CreditCustomer 1—n CreditLedgerEntry; CreditLedgerEntry n—0..1 Sale (charge origin).
- Every mutation of above writes an AuditEvent for privileged operations.

## Identity & immutability notes

- IDs: UUID everywhere (no sequential public IDs); account codes (`AC-###`) are display codes, unique per station.
- Shift `status`: `draft` → `posted`/`closed` (terminal). Corrections after close = reversal entries + new reconciliation.
- Soft-delete only (`active` flag) for masters; transactions never deleted.
