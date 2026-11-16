# OpenBunk — Calculation Specification

Status: v0.1. Formulas with worked examples and edge cases. Prototype implementation lives in
`src/domain/` (framework-free, unit-tested). The backend (Phase 04) mirrors these rules;
deviations are defects, not choices.

Units: litres (L), INR (₹), integer minutes. Money: see Rounding policy below.

## 1. Meter volume (per nozzle, per shift)

```
volume = closing_totalizer − opening_totalizer          (normal case)
```

With an **explicitly authorized** rollover/reset (never inferred):

```
volume = (rollover_value − opening_totalizer) + closing_totalizer
```

- `rollover_value` = wrap point of the totalizer (meter returns to 0 above it),
  e.g. `100000` for a 5-digit totalizer. Must be > opening reading.
- Unauthorized closing < opening → **error**, not a "negative volume fix-up".
- Formula reference: `computeVolume` in `src/domain/shift.ts`.

Example (rollover): opening 99,990 L, closing 20 L, rollover_value 100,000 L
→ volume = (100,000 − 99,990) + 20 = **30 L**.
Example (normal): opening 12,450 L, closing 12,780 L → **330 L**.
Edge (unauthorized): opening 99,990, closing 20 → closing − opening = −99,970 L → validation error.

## 2. Shift sales value

```
petrol_value = petrol_volume × petrol_price
diesel_value = diesel_volume × diesel_price
total_value  = petrol_value + diesel_value
```

- Prices are snapshots taken at shift close; never recomputed from today's price.
- Example: 330 L × ₹102.50 = ₹33,825.00; 420 L × ₹89.50 = ₹37,590.00; total ₹71,415.00.
- Zero price → validation error (a shift closing with fuel sold at ₹0 is a configuration defect; it must never pass silently). A legitimately idle shift shows volume 0 and value ₹0.00.
- Negative volume → negative value (surfaces as validation error / visible variance, never silently clamped).

## 3. Collections reconciliation (per shift)

```
collected = Σ(collections)                      (cash + UPI + card + credit + other)
variance  = collected − expected_sales_value
status    = 'balanced'  if |variance| ≤ tolerance
            'over'      if  variance >  tolerance
            'short'     if  variance < −tolerance
```

- Default `tolerance = ₹1` (absolute), configurable per station.
- Formula reference: `reconcileCollections` in `src/domain/reconcile.ts`.
- Example: expected ₹71,415.00, collections ₹57,000 cash + ₹14,415 UPI = ₹71,415.00 → variance ₹0.00 → **balanced**.
- Example: collections ₹57,400 vs expected ₹57,000 → variance +₹400 → **over**.

## 4. Tank book stock (authoritative = movement ledger)

```
book_stock = opening_book + Σ receipts − Σ dispensed ± Σ approved adjustments
```

- Never mutated directly; every change is a `StockMovement` (receipt / sale / adjustment).
- Example: opening 8,000 L + receipt 6,000 L − sales 5,580 L → book 8,420 L.

## 5. Physical (dip) variance

```
variance = physical_measured − book_stock
```

- Recorded as a reconciliation record (`DipReading`), **not** a silent stock update.
- Example: measured 8,402 L vs book 8,420 L → variance −18 L → flagged for reconciliation.
- Out-of-tolerance variance blocks shift close only if station policy requires it.

## 6. Credit balance (per customer)

```
balance = Σ posted charges − Σ posted receipts − Σ adjustments
```

- `balance > limit` → over limit; `balance ≥ 80% of limit` (configurable ratio) → near limit; else active.
- Amounts are posted entries; reversing an entry posts a reversal, never an edit.
- Ageing buckets for reporting: 0–30, 31–60, 60+ days since charge date (unpaid portion, FIFO).

## 7. Rounding policy

- Persisted money: integer paise (minor units) or `numeric(12,2)`. Never IEEE float at rest.
- UI prototype: floats allowed for display math only; **all persisted/committed boundaries round half-up to 2 dp** (`round2` in `src/domain/money.ts`).
- Half-up means ties (x.xx5) round away from zero in magnitude: 1.005 → 1.01, −1.005 → −1.01.
- Display: `en-IN` grouping, 2 dp maximum, symbol `₹` (e.g. `₹ 1,42,800`).
- Variance comparisons (reconciliation) use rounded values + absolute tolerance, never raw float equality.

## 8. Units

- Volume: litres, 1 dp display (values may carry 3 dp internally).
- Currency: ₹, 2 dp.
- Timestamps: timezone-aware; station default Asia/Kolkata; displayed `dd MMM yyyy, HH:mm`.
- Totalizers: whole litres typical; decimals allowed in capture.

## 9. Edge cases checklist (must be covered by tests)

| Case                                                    | Rule                                                        |
| ------------------------------------------------------- | ----------------------------------------------------------- |
| closing == opening                                      | volume 0; value ₹0.00; not an error                         |
| closing < opening, no rollover authorized               | validation error                                            |
| closing < opening, rollover authorized, value ≤ opening | validation error                                            |
| closing < opening, rollover authorized, value > opening | wrap formula above                                          |
| empty / non-numeric / negative inputs                   | parse → null → validation error                             |
| non-finite (Infinity/NaN) inputs                        | treated as 0 in lenient math; strict validation rejects     |
| price = 0                                               | validation error (prevents silent under-reporting of sales) |
| price < 0 / missing                                     | validation error                                            |
| half-paise ties                                         | round half-up (1.005 → 1.01)                                |
| float artifact inputs (102.555 × 1 L)                   | value rounded to 102.56                                     |
| collections with non-finite entries                     | ignored in sum, flagged in validation                       |
| tolerance boundary                                      | `                                                           | variance | == tolerance` → balanced |

Tests: `src/domain/*.test.ts` (`npm run test`) — must cover every row above.
