# OpenBunk — External Audit

**Date:** 2026-11-16
**Commit reviewed:** `ce09e4b` (branch `main`, working tree clean)
**Scope:** frontend, backend, database schema/migrations, tests, CI, containers, nginx, and all docs
**Method:** full source read + independent execution of the quality gates and selected failure scenarios
**Auditor stance:** external reviewer; no code changes made; prior `STATUS.md` claims treated as unverified until checked

---

## Verdict

> **Prototype only. Do not enter real station, cash, credit, or stock data into this build.**

> **Wave 0 update (2026-11-16):** the seven P0 blockers below were remediated in the working tree after
> this audit; see `STATUS.md` → “Wave 0 — P0 remediation” for the exact changes and verification
> commands. The verdict above still applies until CI, staging and operator UAT re-verify the build.

The engineering foundation is better than the average prototype: clean domain modules, real money types,
server-enforced station scoping, hashed tokens, a sensible CI pipeline, and unusually honest documentation
intent. But the **financial control plane is not sound**. Credit limits are advisory, sale prices are
client-controlled, re-authentication can be brute-forced, shift reconciliation can be skipped or
self-approved, and the documented upgrade/backup procedures do not survive contact with a populated
database. Several UI paths can also present demo figures as live data.

This is a good prototype to **harden**, not a system to pilot in its current state. The release label
`Prototype v0.9` is accurate; the phrase "pilot-ready internal build" in `docs/release-readiness.md`
is not.

**Scorecard**

| Area                               | Grade  | Comment                                                                    |
| ---------------------------------- | ------ | -------------------------------------------------------------------------- |
| Build, lint, type-check, tests, CI | A-     | Reproducible and green; coverage is concentrated in pure functions         |
| Authn / session cryptography       | A-     | Argon2id, hashed tokens, rotation, reuse detection are genuinely good      |
| Authorization / tenant scoping     | B+     | Strong per-endpoint checks; a few privileged gaps                          |
| Financial controls                 | **D**  | Limits, pricing, reconciliation and segregation of duties are not enforced |
| Data integrity / concurrency       | **D+** | Missing constraints, non-atomic locking, unsafe restore                    |
| Frontend correctness / operator UX | **C-** | Demo values can reach real writes; false "Connected"/"saved" states        |
| Deployment / operations            | **C-** | Good artifacts; unsafe upgrade path, backup model and edge security        |
| Documentation accuracy             | B-     | Honest in tone, but numerous claims are contradicted by the code           |
| Test coverage                      | C      | Excellent domain tests; almost no tests on money-writing UI or concurrency |

---

## 1. The seven release blockers (P0)

These must be closed before any real data. Each is verified in the cited code; the migration failure was
reproduced.

### P0-1 — Credit limits are never enforced

**Evidence:** `backend/app/routers/credit.py:92-126`, `backend/app/routers/sales.py:64-96`,
`backend/tests/test_credit.py:39-46`.

A charge is inserted unconditionally; the limit is evaluated **after** commit only to return a label
(`active` / `near_limit` / `over_limit`). The test suite codifies this: a INR 28,400 charge against a
INR 25,000 limit is expected to succeed. Credit-tender sales take the same path. There is no row lock and
no `active` check on the customer.

**Failure:** One cashier can post an unbounded receivable (INR 10,00,000 against a INR 10,000 limit);
two concurrent charges both pass. The primary credit control does not exist.

**Fix:** A single `post_charge` service that locks the customer row, checks `active`, computes the
ledger balance, and rejects `balance + amount > credit_limit` unless an owner override with a reason is
supplied and audited.

---

### P0-2 — Sales trust the client for price, product, nozzle, and shift

**Evidence:** `backend/app/routers/sales.py:21-28,57-85`; `backend/app/routers/catalog.py:84-100`.

`unit_price` is accepted from the caller; there is no price table. The product and nozzle are checked
for station membership but **not against each other**. `shift_id` is persisted without checking that it
belongs to the same station or is still a draft. Sale posting does not require an idempotency key.

**Failure:** Post a petrol product against a diesel nozzle at INR 0.01/L: revenue is fabricated while
the diesel tank is debited at shift close. Retry a timed-out credit sale: the customer is charged twice.
Attribute a sale to another station's or a closed shift.

**Fix:** Effective-dated server-side price book; assert `nozzle.product_id == product_id` and
`tank.product_id == product_id`; load the shift with station + `status='draft'` filters; require and
enforce `Idempotency-Key` on sales and receipts.

---

### P0-3 — Re-authentication is an unthrottled 4-digit PIN oracle

**Evidence:** `backend/app/deps.py:74-79`, `backend/app/schemas.py:17,56`,
`backend/app/routers/staff.py:28-50`.

`require_reauth` calls `verify_pin` directly: no rate limit, no failure counter, no lockout, no failure
audit. PINs may be four characters. The header gates the highest-risk actions: shift close, station
update, role change, offboarding, station export, tank adjustment. `POST /employees` — which can create
another owner — requires **no** re-auth at all.

**Failure:** A stolen access token (15-minute TTL, `sessionStorage`) plus a few minutes of guessing at
Argon2 speed yields a permanent owner account via `POST /employees`, or a full station export, or a
shift close. Login has lockout; re-auth does not, which is an asymmetric hole.

**Fix:** Apply the same per-employee failure counter and lockout to re-auth; audit `reauth.failed`;
invalidate the session after repeated failures; require 6+ digit PINs; require re-auth (ideally a
second owner) to create an owner.

---

### P0-4 — Reconciliation can be skipped or self-approved

**Evidence:** `backend/app/routers/shifts.py:277-299`; `backend/tests/test_phase07_scenarios.py:79-103`.

The entire reconciliation block is guarded by `if payload.collections:`. Omit the field and a shift
closes with no comparison at all. Supply collections and the same caller supplies `override_reason`; no
second approver exists. Declared collections are caller JSON, never tied to `Payment` rows. Separately,
`Payment(mode='credit')` is counted as a collection in `reports.py:53-57` and the CSV export.

**Failure:** A manager closes short, writes "counted twice" as the override, and is both the beneficiary
and the approver. Or closes with `{}` to bypass the rule. Credit sales inflate "collections" although no
cash arrived.

**Fix:** Make collections mandatory; derive collected amounts from payment rows (or a cash-count
record); require a different privileged actor for non-zero variance; persist declared collections and
rollover authorization; exclude credit from collected totals.

---

### P0-5 — Migrations cannot upgrade a populated database, yet run on every container start

**Evidence:** `backend/alembic/versions/a9969610a625_*.py:35`,
`backend/alembic/versions/c8c8a8abb21c_*.py:24`, `backend/Dockerfile:23`,
`.github/workflows/ci.yml:115-117`.

Both revisions add `NOT NULL` columns with no `server_default` and no SQLite batch mode. CI only
upgrades an **empty** database.

**Reproduced [actual run]:**

```text
$ alembic upgrade 8fba104538ba          # seed 1 station, 1 employee, 1 shift, 1 token
$ alembic upgrade head
sqlalchemy.exc.OperationalError: Cannot add a NOT NULL column with default value NULL
[SQL: ALTER TABLE session_tokens ADD COLUMN kind VARCHAR(16) NOT NULL]
```

A fresh SQLite upgrade succeeds (verified), which is why local testing and CI miss it. PostgreSQL behaves
the same way when the table contains rows. Because the API container runs `alembic upgrade head` before
serving, upgrading any existing deployment crash-loops the service; scaling to two replicas also races
on DDL with no advisory lock.

**Fix:** `server_default` + backfill, `batch_alter_table` for SQLite, a populated-upgrade test
(previous revision -> head), `alembic check`, and a one-shot migration job with an advisory lock and a
pre-migration backup.

---

### P0-6 — The backup/restore mechanism is not safe disaster recovery

**Evidence:** `backend/app/backup.py:36-44,68-86,103`; `docs/deployment.md:93-104`.

- The dump issues one `SELECT` per table on a connection using the database default isolation
  (READ COMMITTED on PostgreSQL): each statement sees a new snapshot, so a shift close committed mid-dump
  can leave stock/credit inconsistent with shifts.
- Restore **deletes every table**, including `audit_events`, with no confirmation, no pre-restore
  snapshot, no revision check, no checksum, and no record that the audit trail was destroyed.
- The output file is written non-atomically with `Path.write_text`.
- The documented "verified drill" was executed on SQLite only, and the documented backup paths are not
  ignored by Git (`backups/` is absent from `.gitignore`) and `/data` is not a mounted volume.

**Failure:** A "successful" restore silently misstates money and erases the evidence of what happened.
This is the documented rollback of record.

**Fix:** Use `pg_dump -Fc` / `pg_restore` (or PITR), write a manifest (alembic revision + row counts +
SHA-256), snapshot before restore, archive rather than delete audit events, write atomically, and run
the drill against PostgreSQL on staging.

---

### P0-7 — Demo figures and false liveness can be written as real data

**Evidence:** `src/pages/Shifts.tsx:21-30,167-173,205-215,278-292,294-347`;
`src/lib/api.ts:221-227`; `deploy/nginx.conf:29-31`; `src/components/Layout.tsx:104-106`.

- Every session starts with realistic readings (petrol 12,450 -> 12,780; diesel 22,500 -> 22,920;
  prices; INR 57,000 collected) and these are synced to the API on save/validate/close. A signed-in
  manager can close them (with an override reason).
- `healthCheck()` calls `/health`. Through the shipped nginx, `/health` is not proxied; the SPA
  fallback returns `index.html` with HTTP 200, so the UI reports online even when the API is down.
- The sidebar/topbar shows "Connected" whenever a session object exists, regardless of health.
- "Draft saved to the OpenBunk API." is shown even when `syncToApi()` returns `null` and wrote nothing.
- The UI reads only nozzles `P1` and `D1` and always closes the `afternoon` shift; the seeded station
  also has `P2`, so P2 volume is invisible.

**Failure:** An operator can persist a fabricated shift and see a green "Connected" badge while the
backend is unreachable. This violates the repo's own non-negotiable that demo data must never look real.

**Fix:** Empty initial state for signed-in users (hydrate server openings); render one row per nozzle;
bind shift kind, date and attendant to the payload; make health check an actual API readiness call; show
a blocking offline banner; only claim a write after a confirmed response.

---

## 2. High-severity findings (P1)

| #    | Finding                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | Evidence                                                                                                                                                  | Fix                                                                                                                                 |
| ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| H-1  | **401 handling never refreshes.** `request()` calls `clearTokens()` before `ensureAccessToken()`, so the refresh token is already gone; a wrong re-auth PIN logs the operator out and is reported as "Backend not reachable — no data written".                                                                                                                                                                                                                                         | `src/lib/api.ts:128-141`; `src/pages/Shifts.tsx:334-343`                                                                                                  | Refresh first; clear only on refresh failure; distinguish re-auth 401 from token 401                                                |
| H-2  | **False "Connected".** Health check hits a path served by the SPA fallback (always 200); UI uses session presence as proof of connectivity.                                                                                                                                                                                                                                                                                                                                             | `src/lib/api.ts:221-227`; `deploy/nginx.conf:29-31`; `Layout.tsx:104`                                                                                     | Call `/api/v1/readiness`; surface `online`/`session` separately                                                                     |
| H-3  | **Close skips local validation and coerces blanks to zero.** `inputs.petrolOpening \|\| '0'`; only the server's 422 stands between a typo and a bad close. A 5 s timeout is applied to writes and the failure copy says "No data was written" even if the commit succeeded.                                                                                                                                                                                                             | `src/pages/Shifts.tsx:175-203,294-347`; `src/lib/api.ts:83`                                                                                               | Run strict validation before close; use an "outcome unknown" state; reuse the idempotency key                                       |
| H-4  | **Optimistic locking is TOCTOU.** Version is read in Python, compared, then incremented; no conditional `UPDATE ... WHERE version`. The first write after draft creation sends `expected_version: null`. `SELECT FOR UPDATE` is a no-op on SQLite, and the readings PUT does not lock at all, so it can race a close.                                                                                                                                                                   | `backend/app/routers/shifts.py:101-154,229-234`; `src/pages/Shifts.tsx:175-203`                                                                           | Atomic conditional update or row lock; return the new version synchronously; hydrate the winner's readings on 409                   |
| H-5  | **Nozzle/tank/product inconsistency allowed.** Nozzle creation checks station membership only; a diesel nozzle can point at the petrol tank. Receipts do check tank/product consistency, so the omission is isolated to nozzles/sales.                                                                                                                                                                                                                                                  | `backend/app/routers/catalog.py:84-100`; `shifts.py:250-275`                                                                                              | Enforce `nozzle.product_id == tank.product_id` in code and DB                                                                       |
| H-6  | **Rollover is not persisted, so reports are wrong.** Shift stores only totals; `daily-sales` sums `closing - opening` with no rollover term. A valid wrap produces a large negative volume in reports and cannot be recomputed later.                                                                                                                                                                                                                                                   | `backend/app/models.py:113-133`; `reports.py:23-36`                                                                                                       | Persist rollover value/reason per reading/shift; use `compute_volume` in reports                                                    |
| H-7  | **Stock can go negative or exceed capacity.** Sales, receipts and adjustments apply signed deltas with no floor/cap and no row lock. Receipts have no idempotency key, so a retry doubles stock.                                                                                                                                                                                                                                                                                        | `backend/app/routers/catalog.py:103-136`; `receipts.py:15-50`; `shifts.py:264-275`; `models.py` tank capacity                                             | Lock the tank, enforce `0 <= stock+delta <= capacity`, require an audited override, add receipt idempotency and reversal            |
| H-8  | **CSV formula injection.** Customer names, account codes and ledger reasons are written raw. Excel/LibreOffice will execute a leading `=`, `+`, `-`, `@`, tab or CR.                                                                                                                                                                                                                                                                                                                    | `backend/app/routers/csv_io.py:70-81,96-110`                                                                                                              | Prefix dangerous cells with `'`; sanitize every free-text CSV field                                                                 |
| H-9  | **CSV export bypasses the data-export control.** JSON export is owner + re-auth; CSV export allows manager/accountant/auditor with no re-auth and no PIN. `docs/security-checklist.md` calls export "owner-only".                                                                                                                                                                                                                                                                       | `backend/app/routers/csv_io.py:40-47`; `export.py:40-45`; `docs/permissions.md:31`                                                                        | Apply the same role + re-auth gate, or document and test an explicit matrix                                                         |
| H-10 | **`POST /employees` has no re-auth and no last-owner guard.** A stolen owner token can mint a permanent owner. An owner can also demote the only owner, leaving the station unadministrable; there is no PIN reset.                                                                                                                                                                                                                                                                     | `backend/app/routers/staff.py:28-50,53-77,91-92`                                                                                                          | Require re-auth for privileged creation; block zero-owner transitions; add audited PIN reset                                        |
| H-11 | **Rate limiting is one global bucket behind nginx.** `request.client.host` is the nginx container because uvicorn is started without proxy headers. `RATE_LIMIT_PER_MINUTE=20` becomes 20/min for the whole station; the limiter is in-memory per process and its key map is never pruned.                                                                                                                                                                                              | `backend/app/routers/auth.py:71,103`; `deps.py:82-93`; `backend/Dockerfile:23`; `deploy/nginx.conf:23`                                                    | Trust the proxy, key on the real client + employee, move to Redis/nginx `limit_req` for scale                                       |
| H-12 | **Local images can contain credentials; the web container runs as root.** The API build context has no `.dockerignore`, so `COPY . ./` includes `.venv` (103 MB) and `verify.db`/`verify2.db` containing Argon2 PIN hashes and session-token hashes (CI builds from a clean checkout, so CI images are unaffected; developer builds are not). The nginx master runs as root; compose publishes `8080` on all interfaces, and HSTS is only emitted by the API, not on the HTML document. | `backend/Dockerfile:11`; `backend/.dockerignore` missing; `backend/verify*.db`; `Dockerfile.frontend:16`; `docker-compose.yml:52-53`; `deploy/nginx.conf` | Add `backend/.dockerignore`, delete scratch DBs, run nginx unprivileged, bind `127.0.0.1:8080:80`, terminate TLS + HSTS at the edge |
| H-13 | **Two DB sessions per authenticated request.** `get_current_employee` depends on `get_db`; endpoints depend on `get_db_dep`; FastAPI caches by callable, so each request opens two connections and leaves the auth transaction idle.                                                                                                                                                                                                                                                    | `backend/app/deps.py:45` vs endpoint signatures                                                                                                           | Depend on `get_db_dep` everywhere, or inject one session                                                                            |
| H-14 | **SQLite foreign keys are never enabled.** `db.py` sets only `check_same_thread`. Dev/test databases accept orphan rows that PostgreSQL would reject, so tests overstate integrity.                                                                                                                                                                                                                                                                                                     | `backend/app/db.py:10-15`; `backend/tests/conftest.py`                                                                                                    | `PRAGMA foreign_keys=ON` on connect; add an FK-violation test                                                                       |
| H-15 | **No upper bounds on money/volume.** `Decimal(ge=0)` accepts `1e13`, which can overflow `NUMERIC(12,2)`/`NUMERIC(14,1)` and return an opaque 500. `readings` and `collections` lists are unbounded.                                                                                                                                                                                                                                                                                     | `backend/app/schemas.py:242,248,278`; `sales.py:24-25`                                                                                                    | `max_digits`/`decimal_places` + explicit business bounds; cap row counts                                                            |
| H-16 | **Only two nozzles and one fixed shift in the UI.** P1/D1 are hard-coded, `kind` is always `afternoon`, the shift and salesman selects are decorative, and there is no shift date.                                                                                                                                                                                                                                                                                                      | `src/pages/Shifts.tsx:140-144,167-169,437-453`                                                                                                            | Render all nozzles; bind kind/date/attendant; make selects real                                                                     |
| H-17 | **Draft storage is global and survives sign-out.** The key is not scoped by station/employee/shift/date, failures are silent, and `logout()` does not clear it.                                                                                                                                                                                                                                                                                                                         | `src/lib/draft.ts:13`; `src/lib/api.ts:60-63`; `AuthProvider.tsx:53-56`                                                                                   | Scope keys, add expiry, clear on logout, warn on storage failure                                                                    |
| H-18 | **The money-writing frontend path is untested.** 43 of 49 tests are pure domain; there is no test for `api.ts` refresh/401/timeout, `AuthProvider`, close/409/sync failure, or any signed-in page.                                                                                                                                                                                                                                                                                      | `src/**/*.test.*`; `docs/testing.md:39`                                                                                                                   | Mocked-fetch tests for API client + close/conflict/failed-sync; live-mode page tests                                                |
| H-19 | **Business date and timezone are wrong.** Dashboard/Reports use UTC `toISOString()`; the station is Asia/Kolkata; the backend uses server-local midnight and ignores `station.timezone` / `business_day_start`.                                                                                                                                                                                                                                                                         | `src/pages/Dashboard.tsx:81`; `src/pages/Reports.tsx:36`; `backend/app/routers/reports.py:51-52`; `models.py:49-51`                                       | Compute the station business date everywhere; use it for reports                                                                    |
| H-20 | **Shift linkage and sales idempotency are optional.** `POST /sales` accepts any `shift_id`, including another station's or a closed one; retries duplicate sales/payments/credit charges.                                                                                                                                                                                                                                                                                               | `backend/app/routers/sales.py:28,74,117`                                                                                                                  | Validate shift station/status; require an idempotency key and store a payload hash                                                  |

---

## 3. Medium findings (P2)

| #    | Finding                                                                                                                                                                                                                                       | Evidence                                                                    |
| ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| M-1  | Idempotency keys are scoped only by `(station, endpoint, key)`, store no request fingerprint, are not atomic (read then insert), and the UI generates a new key on every close attempt.                                                       | `backend/app/idempotency.py:11-40`; `src/pages/Shifts.tsx:326`              |
| M-2  | The API sets `Content-Security-Policy: default-src 'none'` on every response, including Swagger UI, so `/api/docs` (linked from README) renders blank in development.                                                                         | `backend/app/main.py:38`; `README.md:81,104`                                |
| M-3  | `allow_credentials=True` on a bearer-only CORS API; becomes dangerous if origins are ever set to `*`.                                                                                                                                         | `backend/app/main.py:45-57`                                                 |
| M-4  | Credit ledger silently caps at 100 entries; balance covers all entries, so the list and total can disagree.                                                                                                                                   | `backend/app/routers/credit.py:78-89`                                       |
| M-5  | `POST /sales` does not check `customer.active`; an inactive credit customer can still accrue debt.                                                                                                                                            | `backend/app/routers/sales.py:64-69`                                        |
| M-6  | Check-then-insert create endpoints return 500 instead of 409 on a concurrent duplicate.                                                                                                                                                       | `credit.py:42-47`; `catalog.py:35-38,56-59,92-95`; `staff.py:34-38`         |
| M-7  | Missing DB constraints/indexes: no `(station_id, business_date, kind)` uniqueness for shifts; `ck_session_token_kind` exists in models but not in any migration; `reference_sale_id` has no FK; no `(station_id, created_at)` index on sales. | `models.py:221,276`; migrations; `sales.py:125-140`                         |
| M-8  | `GET /sales?date_from=garbage` raises `ValueError` -> 500; naive dates are compared to timezone-aware values.                                                                                                                                 | `backend/app/routers/sales.py:137-140`                                      |
| M-9  | Login has a timing oracle: unknown employee codes skip Argon2 entirely.                                                                                                                                                                       | `backend/app/routers/auth.py:88`                                            |
| M-10 | Every failed login for an arbitrary code writes a `LoginAttempt` and an `AuditEvent`; rows are never purged. A known employee can be locked out repeatedly by anyone.                                                                         | `auth.py:77-92`; `deps.py` limiter                                          |
| M-11 | Access tokens are not checked against `Station.active`; no station-deactivation path exists yet, so this is latent.                                                                                                                           | `deps.py:52-62`; `auth.py:116-119`                                          |
| M-12 | The export uses a denylist (`{"pin_hash"}`), so a future secret column leaks by default. Today's JSON export is clean (verified).                                                                                                             | `backend/app/routers/export.py:29-37`                                       |
| M-13 | Exports and list queries load everything into memory; a multi-year station export blocks the worker.                                                                                                                                          | `export.py:63-72`; `csv_io.py:50-93`                                        |
| M-14 | Append-only is enforced only by the absence of endpoints; the runtime DB role owns the schema and `restore` deletes audit events.                                                                                                             | `models.py:172-271`; `backup.py:73-74`; `docker-compose.yml:8`              |
| M-15 | Backup paths in the runbook are inside the repo (`backups/`) and Git does not ignore them; `/data` is not a volume, so container backups vanish on recreate.                                                                                  | `docs/deployment.md:75,99`; `.gitignore`; `docker-compose.yml:59-60`        |
| M-16 | The API container's health check hits liveness only (`/health`); compose reports healthy while PostgreSQL is unreachable.                                                                                                                     | `backend/Dockerfile:18-19`; `docker-compose.yml:35-43`; `health.py`         |
| M-17 | Docker Compose is not hardened: no `restart:`, log rotation, read-only root, capability drop, resource limits, or `internal: true` on the network.                                                                                            | `docker-compose.yml` (whole file)                                           |
| M-18 | No monitoring, alerting, log retention/shipping, or scheduled dependency audit; docs admit this but the runbook still reads as operational.                                                                                                   | `docs/deployment.md:15,103-104`; `ci.yml`                                   |
| M-19 | CI gaps: no production-environment startup test, no populated upgrade/downgrade test, no browser test, no image scan/SBOM, mutable action tags, no `permissions:`/`concurrency`/timeouts.                                                     | `.github/workflows/ci.yml` (whole file)                                     |
| M-20 | Python requirements mix runtime and test tooling, include unused packages (`opentelemetry-api`, `Pygments`), and are installed without hashes; `pip-audit` itself is unpinned in CI.                                                          | `backend/requirements.txt`; `ci.yml:110`                                    |
| M-21 | Version identity is inconsistent: `package.json` 0.1.0, API 0.4.0, Settings UI 0.6, deployment doc v0.8, STATUS v0.9; no tags or CHANGELOG.                                                                                                   | `package.json`; `backend/app/main.py:21`; docs                              |
| M-22 | Demo credentials are compiled into the production bundle and prefilled on the login form; `OPENBUNK_SEED_PIN=1234` is the documented demo path.                                                                                               | `src/pages/Login.tsx:9-10,108-110`; `seed.py`                               |
| M-23 | `AuthProvider` clears tokens on any `/me` error (including 500); a transient server error silently signs the operator out.                                                                                                                    | `src/components/AuthProvider.tsx:35-38`                                     |
| M-24 | Validation has no plausibility/continuity/capacity checks; an extra zero (127,800 L) passes; inputs have no `min`/`max`/`step`.                                                                                                               | `src/domain/validation.ts:47-130`; `Shifts.tsx:352-366`                     |
| M-25 | Print output hides station and notices but prints the decorative shift/salesman selects and no operator/date/signature.                                                                                                                       | `src/index.css:472-498`; `Shifts.tsx:437-453`                               |
| M-26 | Mobile: 14 px inputs trigger iOS zoom; the fixed toast sits under the keyboard; sign-out is hidden on small screens (`.sidebottom { display:none }`).                                                                                         | `src/index.css:22-28,616-626,660-663`                                       |
| M-27 | Accessibility: local validation errors are not announced/focused; table headers lack `scope`/`caption`; several status colours are 2.78-4.20:1 at 10-12 px.                                                                                   | `Shifts.tsx:366-370`; `index.css:275-283,331,349-371`                       |
| M-28 | No error boundary or protected routes; one malformed `/me` or render error blanks the terminal.                                                                                                                                               | `src/App.tsx:15-35`; `AuthProvider.tsx`                                     |
| M-29 | `crypto.randomUUID()` requires a secure context; on a LAN address (`http://192.168.x.x`) every close throws and is misreported as a backend outage.                                                                                           | `src/pages/Shifts.tsx:326`; `deploy/nginx.conf:1-2`                         |
| M-30 | Reports/collections are defined inconsistently with the close UI: server accepts any tenders, UI sends only cash + UPI; credit is counted as collected.                                                                                       | `reports.py:53-57`; `Shifts.tsx:319-322`; `docs/calculations.md:47`         |
| M-31 | `GET /health` and `/api/v1/readiness` are public and disclose DB state; acceptable for probes, but readiness is reachable through the public proxy.                                                                                           | `backend/app/routers/health.py`; `nginx.conf:18`                            |
| M-32 | Mid-request exceptions skip `request_id_ctx.reset()` and the security headers; 500 responses can lack CSP/nosniff.                                                                                                                            | `backend/app/main.py:26-43`                                                 |
| M-33 | Credit `adjustment` accepts any signed amount with an optional reason and no re-auth, delegated to a read-mostly accountant role.                                                                                                             | `credit.py:92-126`; `schemas.py:245-257`                                    |
| M-34 | `docs/calculations.md` says `charges - receipts - adjustments`; the code adds signed adjustments (`charges - receipts + adjustments`). Tests follow the code.                                                                                 | `docs/calculations.md:81`; `credit.py:33`                                   |
| M-35 | Seed prints credential hints and will create five shared-PIN demo employees in production if `OPENBUNK_SEED_PIN=1234`.                                                                                                                        | `backend/app/seed.py:21-29,94-108`                                          |
| M-36 | API `/readiness` returns 200 only if `SELECT 1` succeeds, but the shipped API health check never uses it; orchestration sees healthy with a dead DB.                                                                                          | `health.py:27-38`; `Dockerfile:18-19`                                       |
| M-37 | No native form semantics around the close panel (no Enter submit, no Escape, PIN remains in state after failure).                                                                                                                             | `Shifts.tsx:529-572`                                                        |
| M-38 | The 409 handler reloads the whole page after 1.5 s with no countdown and does not hydrate the server's readings.                                                                                                                              | `Shifts.tsx:217-221,421-428`                                                |
| M-39 | Credit CSV commit re-reads the file input instead of the validated payload; a changed file can be committed without re-validation.                                                                                                            | `src/pages/Credit.tsx:98-131,164-172`                                       |
| M-40 | Exports revoke the blob URL in the same tick and toast success before the browser confirms; downloads can fail silently.                                                                                                                      | `src/pages/Reports.tsx:100-107`; `Settings.tsx:35-41`                       |
| M-41 | Sample fixtures are internally inconsistent (rows do not sum to totals; "2 completed" with one closed shift).                                                                                                                                 | `src/data/sampleData.ts:144-149`; `Credit.tsx:195-200`; `Dashboard.tsx:301` |
| M-42 | Zero is conflated with missing (`Number(x) \|\| null`), so a real zero-cash day renders as "—".                                                                                                                                               | `Dashboard.tsx:111-114,155-164`                                             |
| M-43 | `tsconfig.app.json` lacks `strict`/`noUncheckedIndexedAccess`; casts (`as unknown as`) hide schema drift; `eslint-disable` comments are inert under oxlint.                                                                                   | `tsconfig.app.json`; `Shifts.tsx:83,92`                                     |
| M-44 | Static hosting has no CSP; tokens are in `sessionStorage` (XSS-readable) and the default API base is HTTP `localhost:8000`.                                                                                                                   | `index.html`; `src/lib/api.ts:11,48-63`                                     |
| M-45 | The frontend defaults to `http://localhost:8000` while the image builds with `http://localhost:8080` and the CSP expects same-origin; a host deploy not named localhost:8080 is blocked/mixed-content.                                        | `api.ts:11`; `Dockerfile.frontend:11`; `nginx.conf:37`                      |

---

## 4. Low-severity findings (P3)

- Seed/model comment says `pin_hash` is "pbkdf2 salt$hash"; it is Argon2id (`models.py:66` vs `security.py:11-14`).
- `Employee.role` model default is `"attendant"`, which is not an accepted role (`models.py:65`).
- `idempotency_keys.key` is `String(128)`; an oversized header produces a DB error rather than a 4xx.
- The in-memory rate-limit map grows without bound (`deps.py:83-93`).
- `/health` and `/api/v1/health` duplicate handlers and can drift.
- `package.json` has no `license` field; no `SECURITY.md`, `CODEOWNERS`, or third-party notices.
- Node engine `>=20` conflicts with Vite 8's `^20.19 || >=22.12` requirement.
- No `dist`/`backups` cleanup; the stale local `dist` points at `localhost:8000`.
- `allow_credentials=True` is unnecessary for bearer tokens.
- Uvicorn access logs include query strings while the app also logs requests; duplicate/oversharing logs.
- No `server_tokens off`, cache headers, or `limit_req` at the edge.
- No `@page`/`print-color-adjust` in the print stylesheet; wide tables can clip.
- `docs/integrations.md:86` and `docs/calculations.md:118` contain broken table pipes.
- Rounding can differ by one cent between row-level close totals and aggregate reports (`shifts.py:261-262` vs `reports.py:24-36`).
- Sales table lacks indexes on `shift_id`, `product_id`, and `created_at`.
- No lifecycle policy for `session_tokens` / `login_attempts` (unbounded growth).

---

## 5. What is genuinely good (preserve this)

1. **A real domain layer, not logic in JSX.** `src/domain/*` is framework-free, mirrored in
   `docs/calculations.md`, and the half-up rounding handles the classic 1.005/2.675/10.125 traps and
   negative ties. This is the best-tested part of the product.
2. **Rollover is explicit, never inferred.** `computeVolume` only wraps when an authorized rollover
   value is strictly above opening; otherwise it surfaces the negative difference for validation.
3. **Session security is solid.** 32-byte tokens, SHA-256 storage, access/refresh kinds, single-use
   rotation, reuse detection that burns the family, Argon2id PINs, and lockout on login.
4. **Object-level authorization is consistently applied.** Nearly every by-ID endpoint re-checks
   `station_id` and returns 404 for foreign resources; cross-station tests exist.
5. **No SQL injection or mass assignment.** ORM/parameterized access throughout; every write schema
   enumerates fields; computed amounts are not accepted from clients.
6. **Errors are sanitized.** Validation errors expose only `loc`/`msg`; 500s return a generic message
   with a request id; tokens/PINs are never logged.
7. **Shift close is validation-before-mutation and audited.** Within a single transaction, invalid
   readings roll back before any stock movement is written; close and variance overrides emit events.
8. **The JSON export genuinely excludes `pin_hash` and session tokens today**, and the CSV import is
   dry-run-first with size/row caps.
9. **CI is broad for a prototype:** lint, type-check, 49 frontend tests, format, build, `npm audit`,
   `pip-audit`, PostgreSQL-backed backend tests, and a compose rehearsal that logs in through nginx.
10. **Frontend hygiene:** no `dangerouslySetInnerHTML`, no `eval`, no third-party analytics, tokens not
    in URLs, labels tied to inputs, `aria-invalid`/`aria-describedby`, focus-visible styles, and a print
    stylesheet.
11. **Documentation intent is honest.** The repo repeatedly says "prototype, not cleared for real
    data". That is rare and valuable; the problem is specific over-claims, not a culture of deception.

---

## 6. Documentation claims vs reality

The docs are directionally honest but several statements are contradicted by the code. Correct these
before using them as operational evidence.

| Claim                                                                                        | Where                                                             | Reality                                                                 |
| -------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- | ----------------------------------------------------------------------- |
| "Repository currently contains the repository foundation only — an empty app; backend later" | `README.md:3-6,15-16`                                             | Phases 04-09 are complete; UI is API-wired                              |
| First-boot login uses employee code `OWNER-1`                                                | `docs/deployment.md:65`                                           | Only `EMP-00..04` are seeded; this login returns 401                    |
| "Secrets ... never in images"                                                                | `docs/deployment.md:35`                                           | The API image copies `.venv` and `verify*.db` with Argon2 hashes        |
| "Containers run as non-root"                                                                 | `docs/deployment.md:36`                                           | True for API; nginx master runs as root                                 |
| "Daily backup cron ... quarterly restores"                                                   | `docs/deployment.md:103-104`                                      | Nothing is implemented; backup path is not ignored/mounted              |
| "per client IP" rate limit                                                                   | `.env.example:13`; `docs/security-checklist.md:12`                | Behind nginx it is one global bucket                                    |
| "No secrets in ... frontend bundle"                                                          | `docs/security-checklist.md:29`                                   | Demo PIN 1234 and employee codes are compiled in                        |
| "Owner-only data export"                                                                     | `docs/permissions.md:31`                                          | CSV export allows manager/accountant/auditor without re-auth            |
| "Backup restore drill — pending" vs "drill executed and verified"                            | `docs/security-checklist.md:42` vs `docs/release-readiness.md:25` | Contradictory; the executed drill was SQLite-only                       |
| "Reconciliation-enforced" / "immutability by construction"                                   | `docs/release-readiness.md`                                       | Reconciliation is optional/self-approved; append-only is app-level only |
| "entries ... sync when the backend is reachable again"                                       | `docs/operator-guide.md:48-51`                                    | No background sync exists; only a sessionStorage draft                  |
| "Dip variance shows"                                                                         | `docs/operator-guide.md:33-34`                                    | Dip capture is not implemented; variance renders "—"                    |
| "tolerance ... configurable per station"                                                     | `docs/calculations.md:54`                                         | Hardcoded `Decimal("1.00")`; no station field                           |
| "57 tests" / "4 UI tests"                                                                    | `docs/testing.md:22,39`                                           | 60 backend / 49 frontend tests exist                                    |
| "CI builds and health-checks on every push"                                                  | `docs/deployment.md:10`                                           | Only pushes to `main` and PRs                                           |
| "must all pass to merge"                                                                     | `docs/testing.md:68`                                              | Branch protection is not enabled                                        |
| Five different version numbers                                                               | package/API/UI/docs/STATUS                                        | No single release identity, no tags or CHANGELOG                        |

---

## 7. Verification performed in this audit

**Executed [actual results]:**

| Command                                             | Result                                                                                    |
| --------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `npm run lint`                                      | pass (exit 0)                                                                             |
| `npm run type-check`                                | pass (exit 0)                                                                             |
| `npm run test`                                      | 9 files, **49 tests passed**                                                              |
| `npm audit --audit-level=high`                      | 0 vulnerabilities                                                                         |
| `python -m pip_audit`                               | no known vulnerabilities                                                                  |
| `python -m pytest -q` (backend)                     | **60 passed**                                                                             |
| `alembic upgrade head` on a **fresh** SQLite DB     | pass                                                                                      |
| `alembic upgrade head` on a **populated** SQLite DB | **FAIL** — `Cannot add a NOT NULL column with default value NULL` (`session_tokens.kind`) |
| `gh run list`                                       | latest `main` CI run **success** (43825154248)                                            |
| Pydantic `Decimal` with `Infinity`/`NaN`            | rejected (so this is _not_ a finding)                                                     |
| `1e13` through `Decimal(ge=0)`                      | accepted (no upper bound)                                                                 |

**Reviewed by inspection:** every file under `backend/app`, `src`, migrations, tests, CI, Docker,
nginx, and all docs.

**Not verified (no environment):** Docker image build/run locally (Docker absent), PostgreSQL locally
(CI only), browser/device E2E in this session, screen reader, physical printer, Android hardware,
load/concurrency tests. Claims depending on those are marked as such, not asserted.

**Claims rejected during verification** (checked and found inaccurate): sale `shift_id` _does_ have a
foreign key (`models.py:234`); Pydantic rejects `Infinity`/`NaN`; the JSON export is currently clean;
most object-level station scoping is correct.

---

## 8. Upgrade plan

Indicative effort assumes one experienced full-stack developer.

### Wave 0 — Blockers (must precede any real data; ~1 week)

1. **Fail-closed configuration.** Require an explicit `ENVIRONMENT`; in production refuse to start on
   SQLite, a default/short `POSTGRES_PASSWORD`, `CORS_ORIGINS=*`, or `OPENBUNK_SEED_PIN=1234`.
2. **Credit enforcement.** One charge service with row lock, `active` check, limit rejection, and an
   audited owner override.
3. **Server-side pricing and attribution.** Price book; `nozzle.product == tank.product == sale.product`;
   shift station/status validation; mandatory idempotency with payload hash for sales and receipts.
4. **Re-auth hardening.** Failure counter/lockout/audit; 6+ digit PIN policy; session invalidation;
   re-auth for employee creation; block zero-owner states.
5. **Reconciliation policy.** Mandatory collections derived from payment records; second-actor variance
   approval; persist declared collections and rollover value/reason; exclude credit from collected.
6. **Migration safety.** Add `server_default`/batch mode; test populated upgrade and downgrade; move
   migrations to a one-shot job with an advisory lock and pre-migration backup; add `alembic check`.
7. **Backup/restore.** `pg_dump -Fc` + manifest + atomic write; archive rather than delete audit data;
   tested restore on PostgreSQL; off-host, encrypted retention.
8. **Operator truthfulness.** Empty signed-in state; all nozzles and real shift/date/attendant; strict
   validation before close; real readiness health; honest "unknown outcome"; no demo PIN in production.
9. **Container hygiene.** `backend/.dockerignore`, delete `verify*.db`, unprivileged nginx, bind
   `127.0.0.1:8080`, TLS + HSTS at the edge, remove the compile-time demo credentials.

### Wave 1 — Pilot hardening (~2 weeks)

- Database constraints/indexes: shift-slot uniqueness, session-kind check, sale/payment indexes,
  `reference_sale_id` FK.
- Atomic optimistic locking (`UPDATE ... WHERE version`), row locks on stock, close-vs-edit tests.
- Persist and report rollover; fix collections semantics; fix station timezone/business date.
- CSV sanitization; unify export authorization; stream large exports; add pagination where needed.
- Proxy-aware, per-identity rate limiting (Redis if more than one replica); login timing equalization.
- PIN reset/break-glass; owner recovery; last-owner protection.
- Monitoring/alerts/log rotation; secret management; image scanning; CI production-mode and
  populated-migration tests; SHA-pinned actions.
- Frontend: mocked-fetch tests for `api.ts` and close; error boundary; draft scoping/expiry; 16 px
  inputs; accessible error summary; print header; mobile sign-out.
- Real-device Android testing and a short operator UAT with dummy data.

### Wave 2 — Pilot (needs a real host + owner approval)

Staging VPS + domain + HTTPS; PostgreSQL restore drill on staging; scheduled backups; operator training;
1-2 weeks of controlled UAT; incident runbook rehearsal; third-party review or focused pen test.

### Wave 3 — Production

Least-privilege DB roles and optional RLS; audit hash chain; SLOs and on-call; DR exercise; release
tagging/SBOM/provenance; multi-replica session/rate-limit design; support and SLA.

---

## 9. Improvements backlog (correctness, security, UX, ops)

**Correctness**

- Make all financial mutations go through one service layer with the same validation on every path.
- Add a price book with effective dates and per-station overrides; never accept a price from a client.
- Persist rollover and declared collections; make reports recomputable from stored facts.
- Use the station's timezone and `business_day_start` in every date boundary.
- Add reversal workflows for sales, receipts, credit entries and stock adjustments (no destructive edits).

**Security**

- Lockout + audit on re-auth; 6+ digit PINs; owner MFA/WebAuthn; per-device session list/revoke.
- Server-side authorization tests for every endpoint, including CSV export and employee creation.
- CSV/Excel sanitization; explicit export allowlists; sensitivity labels on downloads.
- Content Security Policy on the static build; consider HttpOnly refresh cookies; TLS everywhere.
- Least-privilege DB role; append-only triggers or hash-chained audit; protect backup files as secrets.

**UX / accessibility**

- One provenance model: live / stale / demo / error per card, with a blocking offline banner.
- Strict validation summary with focus to the first invalid field; persistent, dismissible errors.
- 16 px mobile inputs, larger touch targets, visible sign-out, responsive tables/sticky headers.
- Print a real shift sheet: station, business date, shift, operator, readings, collections, variance,
  closure, signature lines.
- Onboarding/empty states that never show invented money.

**Operations**

- Readiness-based health checks; structured logs with retention; metrics/Sentry/uptime alerts.
- Scheduled `pg_dump`/PITR with off-host retention and quarterly restore drills.
- One version source + tags + CHANGELOG; release checklist; SBOM and image scan.
- Compose hardening: restart policy, log rotation, read-only root, cap drop, resource limits.
- Secret manager/rotation procedure with a dual-credential window.

---

## 10. Enhancements (product roadmap)

1. **Pricing and promotions engine.** Effective-dated price book per product/station, server-derived
   amounts, price-change audit, and a "price override" permission for owners.
2. **Complete nozzle/tank/shift model.** One reading per nozzle (P1, P2, D1, ...), shift kind and date
   bound to the payload, attendant assignment, and continuity checks against the previous closing.
3. **Tender and cash-drawer workflow.** Separate cash/UPI/card/credit/wallet, denomination count,
   expected-vs-counted cash, dual control for variance, and an automatic Z-report.
4. **Offline-first PWA.** IndexedDB queue with explicit sync state, idempotent replay, conflict
   resolution, and an Android wrapper/TWA for reliable field use.
5. **Documents.** PDF/thermal receipts and shift Z-reports with station header, GST fields, operator,
   variance and signature; tested print/PDF workflow.
6. **Credit control.** Limit enforcement, ageing buckets, statements, promise-to-pay, owner override
   with reason, and a collections worklist.
7. **Stock control.** Dip capture, variance approval, capacity checks, delivery invoices, and a
   reconciliation report per tank/nozzle.
8. **Audit and compliance.** Hash-chained audit events, retention policy, export manifests, e-signature
   for variance overrides, and tamper-evident backups.
9. **Observability.** `/metrics`, Sentry, uptime checks, alert thresholds (failed logins, variance,
   stock negative, backup age), and log shipping.
10. **Identity.** PIN reset/break-glass, WebAuthn for owners, session management UI, and optional
    per-device binding for shared terminals.
11. **Multi-station/franchise.** Tenant model, optional PostgreSQL RLS, consolidated owner reporting,
    and per-station configuration.
12. **Integrations (only with a real contract).** Dispenser protocols, payment gateway, accounting
    export; keep the vendor-independent JSON/CSV export as the exit path.

---

## 11. Release gates

Do not move the label beyond **Prototype** until all of the following are true:

- [ ] Every P0 closed and covered by an automated test.
- [ ] Populated upgrade **and** downgrade tested on PostgreSQL in CI.
- [ ] PostgreSQL backup/restore drill executed on staging, with timing and row-count verification.
- [ ] Credit limit, pricing, reconciliation and re-auth abuse cases tested at the API level.
- [ ] A staging host with HTTPS, HSTS, restricted DB access, and monitoring.
- [ ] Android device test (360-420 px), keyboard/screen-reader pass, and printed shift sheet verified.
- [ ] Operator UAT with dummy data and written feedback.
- [ ] Security checklist corrected and all items genuinely verified.
- [ ] Written owner approval for pilot (and later, production).

---

## 12. Bottom line

OpenBunk is a **well-structured prototype with a strong domain core and weak financial enforcement**.
The fastest path to a credible pilot is not a rewrite: it is a focused hardening wave that makes the
server authoritative for prices, credit, stock, reconciliation and identity, fixes the migration and
backup paths, and removes the UI's ability to present demo data as live. Until then, treat every figure
in the app as illustrative, and do not enter real station money into it.

The repository is safe to keep as a prototype and to continue developing. It is **not** safe to operate.
