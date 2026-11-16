# DeepBNK Development Status

## Current milestone

All nine phases complete and Wave 0 P0 remediation implemented. Verdict: **Prototype v0.9 - CI-green; owner must approve any move beyond prototype** (see docs/release-readiness.md). The external audit (`AUDIT.md`, 2026-11-16) found seven P0 blockers; Wave 0 addresses them in code and tests (see the Wave 0 section), but the prototype label stands until CI, staging and operator UAT are re-verified.

## UI revision — DeepBNK branding, station strip, no sample data (2026-11-16)

- App name is **DeepBNK** everywhere user-visible (header, login, manifest, title, export/CSV filenames,
  backend API title, seed station name). Internal identifiers that would break existing clients or
  sessions were kept: `openbunk.*` sessionStorage keys, `OPENBUNK_SEED_PIN`, DB user/db names.
- Connection pill reads **● Offline / ● Connected** (no "demo" wording anywhere in the UI).
- All bundled sample/test data removed (`src/data/sampleData.ts` deleted). Every page now renders
  empty states (`—`, "no data yet", sign-in guidance) until the API returns data; signed-out Shifts
  no longer shows a fake catalog and close/save actions are disabled. Demo-mode login entry removed.
- Station profile strip (name, code, address) renders below the top bar on every screen from
  `src/config/station.ts` (signed-out) or the session station (signed-in).
- Reports summary cards render empty hints as text, not inside a min-width table (fixes a
  desktop horizontal-overflow artifact the empty states exposed).
- Docs rewritten to match: README, STATUS, AGENTS (no-sample-data rule), operator guide, testing,
  deployment, integrations, release-readiness, security-checklist.

**Verification (2026-11-16):**

- `npm run format:check` → exit 0 ("All matched files use Prettier code style")
- `npm run lint` (oxlint) → exit 0, 0 warnings / 0 errors, 36 files
- `npm run type-check` (`tsc -b`) → exit 0
- `npm run test` (vitest) → exit 0, 9 files / 57 tests passed
- `npm run build` → exit 0, `dist/` + PWA `sw.js` (precache 17 entries)
- Built bundle grep: `DeepBNK` present; only `openbunk` matches are the three sessionStorage keys
- Browser (Chrome, production build via `vite preview`): desktop 1365×950 and mobile 375×812
  emulation — Dashboard, Shifts (signed-out), Fuel, Credit, Reports, Settings, Login all render
  the DeepBNK brand, station strip under the top bar, ● Offline pill, and empty states with no
  sample numbers; reports overflow fixed and re-verified.
- Committed to `main` as `d70cba8`; follow-up `400841d` updates the compose-rehearsal brand
  assertion (`grep -i deepbnk`). CI run 43852060400: **success** — lint/type-check/test/build,
  backend PostgreSQL tests, and compose stack rehearsal all green.

## Requirements

- Cloud hosted
- PC + Android + remote owner
- Assisted meter entry
- English
- Optional cloud backup
- UI prototype first

## Completed

- [x] Single-file interactive HTML prototype created in conversation.
- [x] Phase-by-phase harness instructions drafted.
- [x] Repository foundation (2026-11-15) — see verification results below.
- [x] UI moved into project repository (2026-11-16) — see Phase 02 below.
- [x] Domain rules and tests (2026-11-16) — see Phase 03 below.
- [x] API/database (2026-11-16) — see Phase 04 below.
- [x] Auth/security (2026-11-16) — see Phase 05 below.
- [x] Integrations (2026-11-16) — see Phase 06 below (CSV import/export, print CSS, frontend↔API;
      other integrations deliberately not supported in this environment).
- [x] CI and quality gates (2026-11-16) — see Phase 07 below.
- [x] Staging deployment (2026-11-16) — see Phase 08 below (CI rehearsal green; real staging host pending owner provisioning).
- [x] Release readiness review (2026-11-16) — report at `docs/release-readiness.md`; verdict:
      Prototype, owner release approval pending. Not a production sign-off.

## Phase 01 — Repository Foundation (2026-11-15)

Repo created at `C:\Users\deep\OpenBunk` (did not previously exist; scaffolded fresh with
`create-vite` react-ts template, then customized).

**Stack:** React 19.3.1, TypeScript 7.0.2, Vite 8.3.8, oxlint (template default), Prettier 3.10.1,
Vitest 5.1.0 + Testing Library + jsdom, npm 11.17.0 (packageManager pinned), Node >= 20.
Backend/database intentionally not started (Phase 04+).

**Verification (all run locally on Windows, exit codes shown):**

- `npm run lint` → exit 0, no findings
- `npm run type-check` (`tsc -b`) → exit 0
- `npm run test` (`vitest run`) → exit 0, 1 file / 1 test passed
- `npm run format:check` (`prettier --check .`) → exit 0 (after `prettier --write` on 3 files)
- `npm run build` (`tsc -b && vite build`) → exit 0, `dist/` produced (index.html 0.55 kB,
  JS bundle 219.70 kB / 68.68 kB gzip)
- `npm ci --dry-run` → lockfile in sync with pinned exact versions
- `npm audit` → 0 vulnerabilities

**Dependencies:** all pinned to exact versions; `package-lock.json` committed; `.npmrc` sets
`save-exact=true`.

**CI (verified 2026-11-16):** `.github/workflows/ci.yml` (checkout → setup-node 24 → `npm ci` →
lint → type-check → test → format:check → build) on `github.com/Dilipkumarkv/OpenBunk`.
First run (`767627d`) FAILED at format:check — this STATUS.md was committed after the local
format pass. Fixed in `a3d3fee` (`prettier --write STATUS.md`); second run (`a3d3fee`, run 43805135692) PASSED all steps. Note: annotations warn that actions/checkout@v4 and
actions/setup-node@v4 target Node 20 (forced onto Node 24 on runners); consider bumping to
node24-based action versions when available.

**Files added:** README.md (rewritten: setup, scripts, structure, troubleshooting), LICENSE (MIT),
.gitignore (+ .env, db/sqlite/coverage/cache patterns), .env.example, .prettierrc.json, .prettierignore,
.npmrc, .github/workflows/ci.yml, src/test/setup.ts, src/App.test.tsx, favicon.svg.
Default Vite starter content replaced with a minimal placeholder app (hero/icons assets removed).

**Defects / notes:**

- `format:check` initially failed on 3 files; fixed with `prettier --write`, now passes.
- First CI run failed on `format:check` (STATUS.md not formatted before commit); fixed in
  `a3d3fee`, second CI run green.
- Repo made public on GitHub at user's request; pushed to `main`.
- No license headers on source files (MIT covers via LICENSE).

## Phase 02 — Prototype ported into the app (2026-11-16)

Single-file HTML prototype (`openbunk-prototype.html`, in Downloads) decomposed into the React app.

**What changed**

- `react-router-dom@7.18.5` added; routes via `HashRouter` (works on any static host without SPA
  rewrites): `/` Dashboard, `/shifts`, `/fuel`, `/credit`, `/reports`, `/settings`, `*` → `/`.
- Prototype CSS ported near-verbatim to `src/index.css` (one styling system; nav `<button>`s became
  `<NavLink>`s; `.section` show/hide removed — routing handles it).
- New files: `components/Layout.tsx` (sidebar/topbar shell), `components/Toast.tsx` +
  `components/toastContext.ts` (split so oxlint fast-refresh rule stays clean),
  `data/sampleData.ts` (all demo data), `lib/format.ts`, `lib/shiftCalc.ts`,
  pages: Dashboard, Shifts, Fuel, Credit, Reports, Settings.
- Shift & readings calculation (P1/D1 volumes × prices) extracted to `lib/shiftCalc.ts`,
  unit-tested (defaults + non-finite inputs + negative-zero guard).
- Prototype `oninput` handlers replaced by React state + `useMemo`; credit-ledger search filter
  is now controlled state; greeting computed from time of day; `👋` removed.
- index.html title/description updated; 0.1.0 sample data unchanged (illustrative only).

**Verification (local, 2026-11-16):**

- `npm run lint` → exit 0 (no findings after splitting toast context)
- `npm run type-check` → exit 0
- `npm run test` → exit 0, 2 files / 3 tests passed (shiftCalc ×2, App smoke ×1)
- `npm run format:check` → exit 0 (after `prettier --write .`, 5 files fixed)
- `npm run build` → exit 0 (dist: index.html 0.58 kB, JS 285.82 kB / 87.70 kB gzip)

**Notes / defects**

- First `shiftCalc` unit test failed on negative zero (`-500 × 0 = -0`); fixed in `lib/shiftCalc.ts`.
- First `format:check` after port failed on 5 new files; fixed with `prettier --write`.
- Number inputs snap to `0` when cleared (inherited from prototype `+v || 0` leniency); revisit in Phase 03.
- All figures remain illustrative sample data; no persistence/auth/backend. Buttons are demo/prototype actions.

## Phase 03 — Domain rules and tests (2026-11-16)

**Number-input decision (explicit):** operator inputs hold raw strings — clearing a field no longer
snaps to 0. Live calculation is lenient (invalid/empty → 0, never throws). "Validate readings" is
strict and reports issues inline per field: required non-negative numbers, price > 0, and
closing ≥ opening per fuel. Arithmetic error states (e.g. negative variance) are shown, not hidden.

**Domain layer** (`src/domain/`, framework-free, no React/DOM imports):

- `shift.ts` — `computeShiftTotals` (moved from `lib/shiftCalc.ts`, extended with `totalValue`),
  `parseMeterReading` (strict: empty/non-numeric/non-finite/negative → null),
  `parseMeterReadingOrZero` (lenient for live math).
- `validation.ts` — `validateShiftReadings(rawStrings)` → per-field issues
  (required, price > 0, closing ≥ opening for petrol and diesel).
- `reconcile.ts` — `reconcileCollections(expected, collections[], tolerance=₹1)` →
  expected/collected/variance + status `balanced` | `over` | `short`.

**Shifts page** now uses string state, inline field errors (`aria-invalid`/`aria-describedby`),
computes totals and a reconciliation preview (expected vs collected, variance, status pill) via the
domain layer.

**Verification (local, 2026-11-16):**

- `npm run lint` → exit 0
- `npm run type-check` → exit 0
- `npm run test` → exit 0, 4 files / 19 tests passed (shift 7, validation 5, reconcile 6, App smoke 1)
- `npm run format:check` → exit 0 (after `prettier --write .`, 1 file fixed)
- `npm run build` → exit 0 (dist: index.html 0.58 kB, JS 288.07 kB / 88.54 kB gzip)

**Notes**

- `lib/shiftCalc.ts` removed; logic superseded by `src/domain/shift.ts`.
- Reconciliation tolerance default ₹1 (absolute) — flag for product review when real POS/gateway data exists.
- Domain layer is intentionally UI-agnostic so the FastAPI backend (Phase 04) can mirror it.
- Credit-limit and dip-variance rules not extracted yet (Phase 05+); only meter/reading/reconciliation in scope.

## Spec re-verification against official phase files (2026-11-16)

Verified the repo against `02_UI_PROTOTYPE.md` and `03_DOMAIN_MODEL_AND_RULES.md`
(OpenBunk_Mobile_Harness_Phases.zip, Downloads). Gaps found and fixed in this pass:

- [fixed] Phase 02 — Dashboard was missing **alerts** and **collection mix** (added alerts card +
  collection-mix KPI row; alerts labeled demo data).
- [fixed] Phase 02 — no search/filter on transactions (added filter on Dashboard recent transactions;
  credit ledger already had one).
- [fixed] Phase 02 — mobile tables not adapted (`.tablewrap` overflow-x scroll; tables min 640 px).
- [fixed] Phase 02 — grid children could not shrink (`.grid > *` min-width: 0) — `/reports` had
  ~68 px horizontal overflow at narrow width; now none on any route.
- [fixed] Phase 02 — no visible-focus rule (`:focus-visible` outline added).
- [fixed] Phase 02 — credit table gained **ageing** column (0–30 / 60+ days).
- [fixed] Phase 02 — "saved" toast wording replaced with explicit "Demo only: … not persisted".
- [fixed] Phase 03 — missing deliverables created: `docs/domain-model.md` (entities, invariants,
  relationships, immutability) and `docs/calculations.md` (formulas, examples, edge cases,
  rounding + rollover policies).
- [fixed] Phase 03 — no rounding/rollover tests (added `round2` with float-safe half-up algorithm,
  `computeVolume` with explicit authorized wraparound, rollover-aware validation; money/reconcile
  now round half-up to 2 dp). Note: first epsilon-based `round2` failed tests for 1.005/2.675 —
  replaced with milli-scale algorithm; all pass.
- [noted] Sample data disclaimer visible on every screen (topbar "Demo mode" + sidebar + per-page
  demo/illustrative labels); buttons use prototype/demo language throughout.

**Re-verification (local, 2026-11-16):** lint 0; type-check 0; tests 5 files / **30 passed**
(shift 12, validation 7, reconcile 6, money 4, App smoke 1); format:check 0; build exit 0.
**Browser check (built app, `vite preview`, 616 px pane — within mobile breakpoint):** all 6 routes
render, no console errors, no document-level horizontal overflow; inline validation error confirmed
working live (set closing below opening → `aria-invalid=true`, error text shown). 360 px capture
not possible — harness pane fixed ≈616 px; CSS covers ≤700 px via existing breakpoints.
**Known gap:** `screenshot` tool requires a visible desktop window — unavailable from this session;
verification was DOM/console-based, not visual.

## Phase 04 — Backend & Database (2026-11-16)

FastAPI + SQLAlchemy 2 + Alembic + Pydantic under `backend/`; UI intentionally not wired yet
(Phase 06). PostgreSQL-ready; local tests on SQLite, CI tests on postgres:16 service.

**Built:** `/api/v1` — health/readiness (no secrets), session auth (pbkdf2 PIN hash, sha256 token
hash, expiry + revoke), station config (GET/PUT), fuel catalog (products/tanks/nozzles + derived
tank stock from append-only `stock_movements`), shifts (open/list/detail/readings upsert/validate/
**close — atomic, idempotent via `Idempotency-Key`, rollover-aware, book-stock deducted**), credit
(customers + append-only ledger, balance + limit status), sales/payments (credit tender posts a
ledger charge), reports (daily-sales by product from closed shifts; collections by tender from
payments), audit (owner/manager only), idempotency keys for posting endpoints.

**Cross-cutting:** request IDs (`X-Request-Id`), structured stdout logs (no secrets), structured
error bodies `{error:{code,message,details,requestId}}`, CORS from `CORS_ORIGINS`, in-memory
per-IP rate limit on `/api/v1/session`, pagination + allowlisted sort on lists, NUMERIC money
(half-up 2 dp), append-only audit/stock/credit-ledger tables, FK/unique/check constraints,
migrations reversible (upgrade→downgrade→upgrade verified on SQLite).

**Verification (all real):**

- `python -m pytest` local (SQLite tmp): **27 passed**
- Migration: `alembic upgrade head` from empty DB ✓; `downgrade base` → `upgrade head` ✓ (SQLite)
- CI run 43808165917 (commit `279d042`): backend job **FAILED — Post Setup Python cache step
  (no deps cached because install used `--no-cache-dir`); migrate ✓ and Postgres test suite ✓ ran.**
  Fixed in `a91cfcf` (dropped pip cache); CI run 43808304257: **backend (Postgres) ✓, frontend ✓.**
- Seed: `python -m app.seed` — station OB-001, P1/P2/D1, tanks T-01/T-02, demo employees (PIN 1234).

**Known gaps / not done**

- Auth is demo-grade (pbkdf2 + expiry + revoke); roles enforced only on `/audit`; Phase 05 hardens
  (role checks everywhere, refresh strategy, stronger PIN policy).
- Rate limiter is in-memory per instance; needs Redis for multi-instance (Phase 05/08).
- UUID path params rely on SQLAlchemy Uuid coercion (works on SQLite+PG); no raw SQL anywhere.
- Backups/restore procedure documented? Only via CI migration rehearsal — full backup restore
  drill pending (Phase 08/09).
- Frontend↔API integration pending (Phase 06). Demo PINs are 1234 — documented as demo-only.

## Phase 05 — Authentication, Authorization & Security (2026-11-16)

**Roles:** owner, manager, cashier, accountant, auditor — permission matrix documented in
`docs/permissions.md`, enforced server-side on every endpoint (UI hiding is not authorization).
Seed: EMP-00 owner · EMP-01 manager · EMP-02 cashier · EMP-03 accountant · EMP-04 auditor.

**Implemented**

- argon2id PIN hashing (argon2-cffi); PINs never stored/logged reversibly
- Sessions: 15-min opaque access tokens + 12h single-use rotating refresh tokens; only sha256
  hashes persisted; access token cannot call refresh endpoints; **refresh-token reuse burns the
  entire credential family** (audited as `refresh.reuse_detected`)
- Login lockout: 5 consecutive failures → 15-min lock (429), audited; cleared on success;
  per-IP rate limit retained on `/session` + `/session/refresh`
- Re-authentication (`X-Reauth-Pin`) for sensitive actions: shift close, station PUT, role change,
  offboard, export, tank adjustment
- Security headers middleware (nosniff, DENY frame, no-referrer, CSP default-src 'none'; HSTS in production)
- New: staff management (owner-only: list/create/role-change/soft-offboard with immediate session
  revocation), owner-only `/api/v1/export` (no pin_hash, `data.exported` audited), `POST /tanks/{id}/adjustments`
  (explicit signed adjustment + reason, audited), role-protected audit (owner + auditor only)
- Production seed guard: employee seeding skipped unless `OPENBUNK_SEED_PIN` set (verified both paths)
- `docs/security-checklist.md` — NOT cleared for real data (recovery flow, backup-restore drill,
  Redis rate limiter pending)

**Verification (all real, run today):**

- `python -m pytest` → **38 passed** (was 27; +test_security.py 7 tests: lockout, cross-station
  isolation, refresh rotation/reuse family burn, cashier-cannot-close, export re-auth, role-change
  audit, offboard session kill) — run on SQLite; CI runs same suite on postgres:16
- Migration round-trip: `upgrade head` (initial + phase05 revision) → `downgrade base` → `upgrade head` ✓
- Production seed guard verified: no employees seeded without PIN; 5 seeded with explicit `OPENBUNK_SEED_PIN=9999`

**Known gaps**

- No account recovery / PIN reset flow; no refresh-token cookie mode (bearer header only; CSRF N/A)
- Rate limiter is single-instance in-memory; needs Redis for multi-instance
- Cross-station isolation relies on pervasive station_id filtering (no RLS at DB level) — PG RLS could harden further
- Offboarding is soft-delete only (by design; posted records immutable)

## Phase 06 — Integrations, MCP & Skills (2026-11-16)

**UI ↔ API wiring (live-verified in browser, 2026-11-16):** login → dashboard (live daily-sales +
collections + recent sales), Shifts (draft/validate/close round-trip with Idempotency-Key +
X-Reauth-Pin → server closes atomically, tank stock deducted), Fuel (tanks + stock from movement
ledger), Credit (live balances + CSV import dry-run → commit), Reports (live tables + CSV download),
Settings (/me, sign out, owner JSON export). Signed-out/offline fallback = clearly labeled sample data.

**Defect found by E2E and fixed:** backend CORS `allow_headers` was missing `X-Reauth-Pin` →
preflight 400 on every re-auth call → shift close could never succeed from a browser. Fixed in
`backend/app/main.py`; CORS now allows it (+ `.env.example` preview origins).

**Integrations (spec order):**

1. CSV import/export — DONE (`/api/v1/export.csv?type=…`, `POST /credit/customers/import.csv`,
   1 MB/500-row caps, dry-run default, audited; 5 tests) — UI card on Credit page
2. Printable shift sheet — DONE as `@media print` CSS (hiding nav/actions) + ⎙ Print button;
   true server-side PDF deferred until a generator is chosen
3. Email/notification — NOT SUPPORTED (no provider configured) — not implemented, by policy
4. Tally — NOT SUPPORTED (no mapping/test instance) — not implemented
5. Dispenser hardware — NOT SUPPORTED (unknown make/model/protocol, no hardware) — not implemented
6. Payment gateway — NOT SUPPORTED (not needed yet; would require tokenized SAQ-A design)

**Frontend↔API map, MCP operating rules (read-only browser usage, no business-API MCP exposure,
no secrets to model context, no MCP writes without explicit owner approval) and integration gaps**
documented in `docs/integrations.md`. Project-local conventions captured in `AGENTS.md`.

**Verification (all real):** backend pytest **43 passed** (38 + 5 CSV tests); frontend lint/type-check/
test (30)/format/build exit 0; **browser E2E against live uvicorn+preview**: login → close shift
(PIN re-auth) → "Shift closed … Revenue ₹ 71,415 · total 750 L" → Dashboard shows ₹ 71,415/750 L →
Fuel shows 8,090 L / 10,860 L → Reports shows Diesel 420 L / Petrol 330 L / Total 750 L → Sign out →
sample-data mode. Zero console errors. CORS defect caught only by doing this.

**Known gaps:** sales entry UI missing; alerts/sales-trend illustrative; dip capture not implemented
(variance shows —); CSV import shows summary, not full row-level error table; email/Tally/dispenser/
gateway unimplemented by policy. Demo PINs remain 1234 until production seed policy is applied.

## Phase 07 — Testing, Quality Gates & Bounded Loops (2026-11-16)

**Spec tests → implemented (all critical scenarios covered):**

| Scenario                                                       | Result                                                                                                                                                                                                                                                                             |
| -------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| closing < opening rejected                                     | ✓ API 422 + inline UI error                                                                                                                                                                                                                                                        |
| duplicate close idempotent                                     | ✓ replay test + UI close                                                                                                                                                                                                                                                           |
| cash/UPI/card/credit mismatch → variance + authorized override | ✓ **new rule**: close with `collections` requires matching or `override_reason` (422 `override_required` otherwise; allowed with reason; audited as `shift.close_variance_override`); frontend now requires override reason before close confirmed and passes collections + reason |
| concurrent shift edits                                         | ✓ **new**: `shifts.version` optimistic lock (migration `c8c8a8abb21c`); stale `expected_version` → 409 with `current_version`; UI sends expected_version and auto-reloads on 409                                                                                                   |
| network interruption → draft preserved + unsynced state        | ✓ **new**: sessionStorage draft persistence + "Unsynced draft restored…" banner; clears on successful sync/close                                                                                                                                                                   |
| unauthorized role → 403, no leakage                            | ✓ existing + auditor read-only                                                                                                                                                                                                                                                     |
| tank receipt + sale ledger → expected book stock               | ✓ (8,090 / 10,860 L asserted)                                                                                                                                                                                                                                                      |
| credit receipt reduces outstanding exactly once                | ✓ test added                                                                                                                                                                                                                                                                       |
| backup restore recovers verified dataset                       | ✓ **new**: `app/backup.py` (CLI + library); JSON dump/restore roundtrip test incl. PIN-hash survival                                                                                                                                                                               |

**Quality gates added to CI:** `npm audit --audit-level=high` (frontend), `pip-audit --strict`
(backend, reported clean locally), migration check renamed and retained (empty-DB upgrade is the
CI pytest entry point). Branch protection on `main` NOT enabled — owner decision (see note).

**Verification (all real, run today):**

- frontend: lint 0 · type-check 0 · tests **49/49 (9 files)** (new: navigation, inline-error wiring,
  a11y landmark/labels, stock projection, credit status, draft persistence round-trip)
- backend: **57/57 pytest** (was 43; +test_domain 7, +test_phase07_scenarios 6, +test_backup_restore 1)
- migration round-trip ✓ (3 revisions: initial, auth+login_attempts, shifts.version)
- CI re-check needed after push; see run below

**CI:** run 43818858202 (`dac8c91`) FAILED — `test_backup_restore` passed `check_same_thread`
(SQLite-only) to psycopg/Postgres; 56/57 passed. Fixed in `a94f685`; run 43819137910:
**backend (Postgres) ✓ · frontend ✓.**

**Defects found & fixed during this phase (honest log):**

- `func.count().select_from` invalid SQLAlchemy call → fixed to `select(func.count()).select_from`
- jsdom tests accumulate DOM across files (no globals cleanup) → duplicate-element failures;
  fixed with RTL `cleanup()` in test setup
- Tightened RTL queries to accessible names; hash reset between UI tests
- **Stale build served during first E2E pass** — close succeeded without override because vite
  preview served the pre-Phase-07 bundle; rebuilt and re-verified (confirm disabled → enabled after
  reason → close 200 → variance override audited as `shift.close_variance_override`)
- Vitest "Cannot find module node:fs" assumption removed; debug scaffolding deleted (49 tests clean)

**Known exclusions (explicit, per spec):**

- Automated browser E2E not in CI (no headless browser on ubuntu-latest); API-level E2E + manual
  browser verification used instead; visual/360px regression not machine-verified
- Branch protection on `main` not enabled (would change how you can push — asked separately)
- Load/stress/hardware tests: none (no hardware, no multi-station data)

## Phase 08 — Cloud Deployment & Operations (2026-11-16)

**Scope honesty:** no staging/production host exists for this project yet — **nothing is deployed
anywhere.** Phase 08 delivered the complete deployable artifact and full operations runbook, plus a
CI rehearsal that builds and health-checks the stack on every push. A real staging deployment needs
a host + domain (ask owner) before it can be executed/approved.

**Delivered:**

- Dockerized stack: `Dockerfile.frontend` (node build → nginx:1.27-alpine, SPA fallback + `/api/*`
  reverse proxy + security headers + `/healthz`) and `backend/Dockerfile` (python:3.14-slim,
  **non-root**, HEALTHCHECK, migrations on start). `docker-compose.yml` (db internal-only, api, web;
  `pgdata` volume; `--wait` startup). `.dockerignore`.
- CI new job **Compose stack rehearsal**: builds both images, `up --wait`, seeds demo station,
  verifies `/healthz`, `/api/v1/readiness` (200 through nginx→API), HTML page, login `201`, and
  asserts API logs contain no secret patterns — **currently GREEN**.
- Backend: `/api/v1/health` + `/api/v1/readiness` aliases (proxied path) added; startup guard
  refuses `ENVIRONMENT=production` with SQLite (fail fast, verified message).
- `docs/deployment.md`: architecture, provisioning steps, health verification, migration + backup
  policy, rollback strategies (app redeploy / restore), secret rotation, incident response, vendor-
  independent exit (export works), log-secret audit procedure.
- Backup restore drill executed for real: dump → wipe → restore → row counts identical; EMP-01 PIN
  verifies against the restored hash. (`app/backup.py` CLI + `tests/test_backup_restore.py`.)

**Verification (all real):** CI run 43820547220 — **compose ✓ (build+up+seed+5 checks+log scan),
frontend ✓, backend(PostgreSQL) ✓**. Note: first compose run FAILED (404 on `/api/readiness` —
root-level endpoint not visible through `/api/*` proxy) and was fixed by adding `/api/v1/*` aliases;
recorded in STATUS per protocol.

**NOT verified (needs real host):** HTTPS/TLS end-to-end, security headers over the wire (headers
are set by nginx but unverified live), backup scheduling/monitoring/alerting, actual station cutover,
restore drill against Postgres (SQLite drill done; PG drill pending staging). **Production is
disabled/locked behind owner approval.**

## Phase 09 — Release Readiness (2026-11-16)

Verdict: **Prototype v0.9 — NOT cleared for pilot/production** (release-readiness report at
`docs/release-readiness.md`). Gates passed: roles tested, atomic/idempotent close, reconciliation
policy, backup/restore drill, CI audit gates, runbooks, operator guide. Failing/open gates: no
Android device test, no staging host (HTTPS unverified), no third-party pen test, no explicit owner
release approval (spec requires it). One endpoint (`/tanks/{id}/adjustments`) had no test — now
covered (`tests/test_adjustments.py`, 3 tests; 60 backend tests total).

**Owner must decide next:** remain prototype · provision pilot staging · production (requires all).

## Phase 09 outcome

**Owner decision (2026-11-16): remain prototype.** No pilot, no production. Repo stays a CI-green prototype with explicit verification records; revisit only with a real staging host + operator UAT.

## External audit (2026-11-16)

Independent review of commit `ce09e4b` is recorded in [`AUDIT.md`](AUDIT.md). Verdict: **prototype only,
not safe for real station data**. The review confirms the build/CI and session/authorization foundations
are sound, but identifies seven P0 blockers: credit limits are advisory; sale price/product/nozzle/shift
linkage is client-trusted; re-auth PINs have no throttle; reconciliation can be skipped or self-approved;
populated-database migrations fail (reproduced: `Cannot add a NOT NULL column with default value NULL`)
while running on container start; JSON backup/restore is not a safe DR mechanism; and demo readings plus
false "Connected" states can be written as real data. The report includes a four-wave upgrade plan, an
improvement backlog, product enhancements, and a claim-by-claim documentation correction table.

**No code was changed by the audit.** Wave 0 (the seven P0 blockers) is implemented — see the
Wave 0 section below for exact commands and remaining caveats.

## Wave 0 — P0 remediation (2026-11-16)

Scope authorised by the owner: fix the seven P0 blockers before any pilot discussion. No deployment
was performed; the release label remains **Prototype v0.9**.

**What changed (code):**

- **P0-1 credit enforcement** — `backend/app/credit_service.py`: locked customer row, hard limit
  rejection on credit sales/entries, owner-only override with reason + audit (`credit.override`).
- **P0-2 server pricing & attribution** — `fuel_prices` table with effective dates, `GET
/api/v1/fuel-prices/current`, `POST /api/v1/fuel-prices`; sales and shift readings derive prices
  server-side; nozzle→tank→product validated; sales/receipts require an `Idempotency-Key` bound to a
  request hash; shift station/status checked on every mutation.
- **P0-3 re-auth hardening** — `reauth_attempts` lockout (5 failures / 15 min), `reauth.failed` /
  `reauth.locked` audit, sessions revoked on lock, re-auth required for employee creation, last-owner
  guards, 6+ digit PIN policy everywhere.
- **P0-4 reconciliation policy** — close requires `collections`; credit sales excluded from expected
  cash; collections/variance/rollover persisted; variance over ₹1.00 needs a reason **and** a distinct
  second approver (`X-Approval-Code` + `X-Approval-Pin`); rollover-aware reports and CSVs.
- **P0-5 migration safety** — server defaults in historical revisions, SQLite batch mode, new
  `d1e2f3a4b5c6` revision, `app/migrate.py` advisory-lock runner, populated upgrade/downgrade test.
- **P0-6 backup/restore** — native `pg_dump -Fc` (Postgres) / backup API (SQLite), SHA-256 manifest,
  atomic writes, forced restores, pre-restore snapshot, audit archive, row-count verification.
- **P0-7 operator truthfulness** — signed-in shift form starts empty and hydrates from the server;
  signed-out mode is clearly labelled demo; demo PIN hint removed; connection banner distinguishes
  “Signed in · API unreachable”; dashboard/credit sample cards show “—” when live; CSV export requires
  a PIN and honest error handling.
- **Infra/config** — fail-closed `ENVIRONMENT` (required) with production guards, SQLite foreign keys,
  dedicated `migrate` compose service (advisory lock; API never migrates), unprivileged nginx on 8080,
  loopback-only web port, HSTS/CSP, `.dockerignore` files, CI Postgres client + `alembic check`.

**Verification run locally (Windows, real commands):**

- `npm run lint` → exit 0, no findings
- `npm run type-check` → exit 0
- `npm run test` → 9 files / 57 tests passed
- `npm run format:check` → “All matched files use Prettier code style!”
- `npm run build` → exit 0; `dist/` built (JS 330.25 kB / 100.30 kB gzip)
- `backend: .venv\Scripts\python.exe -m pytest -q` → **77 passed, 1 warning**
- Fresh SQLite database: `alembic upgrade head` → `d1e2f3a4b5c6`; `alembic check` → “No new upgrade
  operations detected.”; `alembic downgrade base` then `upgrade head` → all four revisions replayed;
  schema has 20 tables including `fuel_prices` and `reauth_attempts`

**Not verified in this environment:** Docker/Compose (no Docker installed locally), PostgreSQL
backup/restore outside CI, browser/print/screen-reader passes, Android device, host-level staging.

**CI (GitHub Actions, verified 2026-11-16):** run `43836542643` on commit `ce3dfc5` — **all three jobs
green**: lint/type-check/test/format/build; compose stack rehearsal (dedicated `migrate` service exits
0, seed + login with the new 6-digit PIN, readiness, no secrets in logs); backend on PostgreSQL 16
(77 tests, `alembic check`, advisory-lock migration runner, native `pg_dump`/`pg_restore` roundtrip).
Two CI-only defects found and fixed during the wave: `pg_dump` was given a password-masked URL
(now `render_as_string(hide_password=False)`), and the compose start check used `docker compose wait`
on an already-exited one-shot service (now reads `ps -a` exit codes). CI runners are pinned to
`ubuntu-24.04` so the client major matches `postgres:16`.

## Known limitations

- Sample data remains in signed-out/demo mode by design; in live mode pages read the API
  (closed shifts, recorded sales/receipts/ledger entries only).
- Buttons that say demo/preview do not perform real business writes.
- Security posture implemented but **not cleared for real data** — see docs/security-checklist.md
  (recovery flow, backup-restore drill, multi-instance rate limiting pending).

## Update this file after every phase

Record actual commands and results, files changed, defects, and next phase.
