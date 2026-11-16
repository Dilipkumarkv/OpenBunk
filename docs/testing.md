# DeepBNK — Testing & Quality Gates

## Test pyramid (as implemented)

### Unit — frontend (`src/domain/`, `src/lib/`, `npm run test`)

- money/round2 half-up edge cases (1.005 → 1.01, −1.005 → −1.01, float artifacts)
- shift meter math: volumes incl. authorized rollover, negative-volume-not-silent rule
- strict draft validation: required/non-negative/price>0/closing≥opening + rollover-authorized paths
- collections reconciliation statuses + ₹1 tolerance boundary
- stock projection (book = opening + receipts − dispensed ± adjustments) incl. the E2E-verified
  tank deltas (8420−330=8090, 11280−420=10860)
- credit limit status (near/over/active + 80% threshold + non-finite coercion)
- offline shift-draft persistence (save/load/clear + corrupt-data tolerance)
- format & App smoke

### Unit — backend (`backend/tests/test_domain.py`)

- round2 ties, compute_volume (rollover + negative-not-silent), credit_balance (charge/receipt/
  signed adjustments), reconcile (balanced/over/short + inclusive tolerance boundary)

### API (backend/tests/, 57 tests)

- auth lifecycle, rate limiting, argon2 hashes, refresh rotation + reuse family-burn
- permission matrix enforcement (owner/manager/cashier/accountant/auditor), station scoping
  (cross-station isolation → 404/empty), 403 with no data leakage
- optimistic locking (`expected_version`): stale version → 409 with `current_version`; increments per write
- reconciliation at close: matching collections pass without override; variance → 422 with
  `override_required`; `override_reason` → allowed + audited as `shift.close_variance_override`
- idempotent close (Idempotency-Key replay), close deducts tank stock, readings immutable after close
- pagination, CSV import/export (dry-run/commit/duplicates/bad rows), sales + payments +
  collection/daily-sales reports, fuel receipts ledger, audit role protection, lockout/recovery

### Backup/restore integration (`backend/tests/test_backup_restore.py`)

- dump → JSON boundary → wipe → restore → row-level counts identical; PIN hashes survive the
  roundtrip. `app/backup.py` also runnable as CLI (`python -m app.backup create|restore`).

### UI (`src/*.ui.test.tsx` — 4 tests, Testing Library, jsdom)

- navigation across all screens with accessible names; labeled controls; `<main>` landmark
- station profile strip renders name, code and address under the top bar
- signed-out empty states: the Shift page asks for sign-in, no nozzle inputs render, and Save
  draft / Close shift are disabled
- brand and **● Offline** status render with no session

Inline validation wiring (closing < opening → `aria-invalid` + message) is covered by the domain
validation tests; the UI path needs a live catalog, so it is verified manually against the API.

### End-to-end (API-level + manual browser verification)

- API-level: full shift lifecycle open → readings → validate → close (atomic, stock deducted) → reports
  (`test_shifts.py`, `test_reports.py`).
- **Automated browser E2E is NOT in CI** (no headless browser harness on `ubuntu-latest` here);
  UI E2E was verified manually against live backend+preview (login → PIN re-auth close → live
  dashboard/reports/fuel figures) and is recorded in STATUS.md. Playwright can be added later if the
  project accepts the dependency cost.

## Critical scenarios → coverage map (spec Phase 07)

| Scenario                                                       | Covered by                                                            |
| -------------------------------------------------------------- | --------------------------------------------------------------------- |
| Closing < opening rejected / authorized rollover               | validation.test.ts, shift.test.ts, test_shifts.py                     |
| Duplicate close → idempotent replay, no double posting         | test_shifts.py (`test_close_is_idempotent`)                           |
| Cash/UPI/card/credit mismatch → variance + authorized override | test_phase07_scenarios.py (3 tests)                                   |
| Concurrent shift edits → optimistic locking                    | test_phase07_scenarios.py (`expected_version` 1→2→3, stale → 409)     |
| Network interruption → draft preserved + unsynced state shown  | src/lib/draft.ts + src/lib/draft.test.ts + Shifts page restore banner |
| Unauthorized user → 403, no leakage                            | test_security.py, test_station_catalog.py                             |
| Tank receipt + sale → expected book stock                      | test_receipts.py, test_shifts.py (8090.0 / 10860.0)                   |
| Credit receipt reduces outstanding exactly once                | test_phase07_scenarios.py                                             |
| Backup restore recovers verified dataset                       | test_backup_restore.py                                                |

## CI gates (must all pass to merge)

frontend: format:check → lint → type-check → test → **npm audit --audit-level=high** → build
backend: **pip-audit --strict** → migration check (empty DB → `alembic upgrade head`)
→ full pytest suite (with the from-empty-DB migration as the suite's entry point)

## Exclusions / not covered (explicit)

- Automated browser/visual regression (manual verification only; sub-700px viewports covered by
  CSS breakpoints but 360 px width itself not tool-verified).
- Load/stress testing, hardware/dispenser integration (no hardware), penetration testing.
- No skipped/xfailed tests; no TODO mocks in production paths.
