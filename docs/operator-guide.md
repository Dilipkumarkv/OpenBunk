# OpenBunk — Operator Quick Reference (v0.9)

For station staff. One station, one terminal or Android phone, assisted meter entry.
**Prototype environment:** unless you are told otherwise, figures you see are illustrative.

## Sign in

1. Open OpenBunk in your browser.
2. Enter **Station code** (e.g. `OB-001`), **Employee code** (e.g. `EMP-02`), **PIN**.
3. Forgot your PIN? Contact the owner — there is no self-service reset yet.
4. Sign out on shared machines, always: sidebar → **Sign out** (top-left of screen).

## Dashboard — what you will see

- Top bar: **● Connected** (green) when live, or **● Offline demo** (amber) when not.
- Cards: today's sales, litres dispensed, cash collected, credit outstanding.
- **Demo data** labels mean figures are illustrative, not real.

## Close a shift (the normal daily task)

1. Go to **Shift & readings**.
2. Enter opening and closing totalizers for **Petrol P1** and **Diesel D1** and the litres price.
3. Enter cash and UPI/card collected.
4. **Validate readings** — fix any red field shown (closing below opening, price zero, empty).
5. Click **Close shift**, enter your PIN (this re-checks it is you), and confirm.
6. If sales ≠ collections, you must either fix the collections or enter an **override reason**
   (e.g. "Manager approved short collection"). Variance is never ignored silently.
7. The shift cannot be edited afterwards. Mistakes after closing need the owner
   (adjustment entries + audit trail).

## Fuel & stock

- Tanks show **book stock** (ledger-derived). Physical dip confirmed by manager on request.
- "Dip variance" shows when physical differs from book — flagged, never silently corrected.

## Credit customers

- Search a customer, check status: **Active / Near limit / Over limit**.
- New customer: ask the manager to add (or import a CSV: `account_code,name,credit_limit`).

## Printing

- On any screen press the browser print button (or `Ctrl+P`) — menus, buttons and notices
  are hidden; the shift sheet prints cleanly. Save as PDF instead of paper if you prefer.

## If something looks wrong

1. **Offline demo** banner → you can keep working; entries are saved on this device and sync
   when the backend is reachable again (draft restores automatically).
2. **Backend not reachable** message → tell the owner; do NOT keep closing real shifts in offline
   mode. The screen shows sample data instead of live figures — do not trust it.
3. **Validation rejected** (closing below opening) → re-read the meter. If the meter genuinely
   rolled over, tick "rollover authorized" and enter the wrap value, or call the owner.
4. **"Another session updated this shift"** → your page reloads automatically; re-enter changes.
5. Anything else: note the time, what you clicked, and call the owner. Evidence is better than guesses.
