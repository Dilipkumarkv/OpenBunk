# DeepBNK — Operator Quick Reference (v1.0)

For station staff. One station, one terminal or Android phone, assisted meter entry.

## Sign in

1. Open DeepBNK in your browser (or launch the installed app).
2. Enter **Station code** (e.g. `OB-001`), **Employee code** (e.g. `EMP-02`), **PIN**.
3. Forgot your PIN? Contact the owner — there is no self-service reset yet.
4. Sign out on shared machines, always: sidebar → **Sign out** (or **Station settings** on a phone).

## The screen frame

- The top bar shows the page and the connection badge: **● Connected** (green) when the API is
  reachable, **● Offline** (amber) when it is not.
- Just below the top bar a station strip always shows the **station name**, **station code** and
  **address**, so you can confirm you are on the right station before entering readings.
- On a phone the main screens live in the bottom tab bar: Home, Shifts, Fuel, Credit, Reports.

## Dashboard — what you will see

- Cards: today's sales, litres dispensed, cash collected, collection mix, recent transactions.
- Before sign-in or before the station saves data, the page shows **—** and "no data yet" with a
  sign-in prompt. DeepBNK does not display sample or placeholder figures.

## Close a shift (the normal daily task)

1. Go to **Shift & readings**. The nozzle list and selling prices come from the station server; if
   you are not signed in the page asks you to sign in first.
2. Enter opening and closing totalizers for every active nozzle.
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

1. **● Offline** badge → the app shell still opens, but live data and saves need the server.
   Do NOT keep closing real shifts offline; tell the owner and retry when reconnected.
2. **Backend not reachable** message → tell the owner. The screen shows empty states, never
   stand-in numbers.
3. **Validation rejected** (closing below opening) → re-read the meter. If the meter genuinely
   rolled over, tick "rollover authorized" and enter the wrap value, or call the owner.
4. **"Another session updated this shift"** → reload from the server and re-enter changes.
5. Anything else: note the time, what you clicked, and call the owner. Evidence is better than guesses.
