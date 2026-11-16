# OpenBunk — Integrations

Status: v0.6 (Phase 06, 2026-11-16). Integration policy: **only what the product and environment
actually support**, in the spec's order. Mocks/demo data are always labeled; no integration may
bypass authorization or audit events.

## 1. CSV import/export — SUPPORTED (owner/manager/accountant)

**Owner:** station owner/manager (import); owner/accountant/auditor (export).
**Data flow:** browser → `POST /api/v1/credit/customers/import.csv` (multipart, 1 MB / 500 row cap)
→ per-row validation (`account_code`, `name`, `credit_limit ≥ 0`, duplicate check) → dry-run by
default (`validate_only=true`, persists nothing) → commit with `validate_only=false` → rows created

- audit event `credit.import` with counts. Export: `GET /api/v1/export.csv?type=sales|collections|credit-ledger|shifts` → CSV download + audit event `data.exported`.
  **Permissions:** server-side `require_roles(...)` on every CSV endpoint; station scoping on all queries.
  **Failure behavior:** 415 wrong media type · 413 too large · 422 bad columns · per-row errors reported
  (never partially hidden) · duplicate account codes reported, skipped.
  **Test strategy:** `backend/tests/test_csv.py` — dry-run persists nothing; commit creates valid rows;
  bad rows reported; wrong columns → 422; duplicates → skipped (5 tests).
  **UI:** Credit page has an Import CSV card (visible when signed in): file picker → dry run →
  "Commit N valid row(s)" button → customer list refreshes.

## 2. PDF/printable shift sheets — SUPPORTED as print CSS (not true PDF)

**Owner:** anyone using the shift page.
**Data flow:** browser → `⎙ Print` → `@media print` stylesheet hides sidebar/topbar/actions/notices
→ printable shift sheet (shift closing form + reconciliation + computed values).
**Limitations:** print-to-PDF via the OS print dialog only; server-generated PDF pending a generator
(e.g. WeasyPrint) when a real PDF customer requirement appears. No external service is used.

## 3. Email / notification provider — NOT SUPPORTED (not configured)

No provider credentials are configured; per policy it is **not implemented**. Integration point
when needed: `notifications/` module behind a provider interface (SES/SMTP), triggered only after
shift close / credit-follow-up thresholds, with explicit owner opt-in. Mocking it would violate
"no fake integrations".

## 4. Tally integration — NOT SUPPORTED

Requires an agreed Tally schema mapping (vouchers, ledgers) + reconciliation design + a test
instance. No mapping document exists; not started. When picked up: read-only verification export
first, one-way write with idempotency keys second, reconciliation report before go-live.

## 5. Dispenser protocol / hardware — NOT SUPPORTED

No make/model/protocol is known; hardware absent. Integration requires a specific dispenser spec
(e.g. Gilbarco/Tokheim serial protocols or OPC-UA gateway) + isolated network segment + dry-run
read-only mode for weeks. The meter-entry flow (manual totalizers) is the supported path today.

## 6. Payment gateway — NOT SUPPORTED (not needed yet)

Sales recording supports cash/UPI/card/credit tenders as records; no gateway is wired. If required:
gateway SDK tokenizes card data (never stored by us, PCI SAQ-A), webhook signature verification,
idempotency keys on all postings, reconciliation report per settlement cycle.

---

## MCP (Model Context Protocol) operating rules — as applied in this repo

OpenBunk's MCP surface is the **development/operator** harness, not the product:

- **Discovered servers this session:** browser (read-only inspection + navigation for verification).
  No OpenBunk business API is exposed as an MCP server; the app's secure API enforces auth itself.
- **Used read-only:** page navigation, DOM reads, console error checks — never mutating business data.
  All business writes in this phase happened through the app's own UI → API → DB with full authz/audit.
- **Never exposed:** database credentials, seed PINs, or tokens in model context or prompts.
  (Session tokens used during manual E2E lived in the browser's sessionStorage; logs show no secrets.)
- **Validation:** every API response consumed by the harness was sanity-checked (status, row counts,
  invariant values like ₹ 71,415) before being recorded as verified.
- **External writes through MCP:** none performed. Any future MCP write (deploy, issue creation,
  customer notification, financial action) requires explicit owner confirmation first.
- **No MCP server shortcut for auth:** MCP cannot and must not bypass the app's authorization or audit —
  the permission matrix (docs/permissions.md) applies to every actor, human or agent.
- **Skills used this phase:** `browser` (verification only). No skill overrode project policy;
  all changes were reviewed against the spec before commit.
- **If MCP is unavailable:** continue with local tools and record the limitation here (none hit this phase).

## Frontend ↔ API integration map (as wired in v0.6)

| Page      | Live path                                                                                                                                         | Fallback                       |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------ |
| Dashboard | `/reports/daily-sales`, `/reports/collections`, `/sales?limit=4`                                                                                  | sample data + "Demo" label     |
| Shifts    | `PUT /shifts/{id}/readings`, `POST …/validate` (server authoritative), `POST …/close` (Idempotency-Key + X-Reauth-Pin), stock deducted atomically | local-only, "Demo only" toasts |
| Fuel      | `/tanks`, `/tanks/{id}/stock`, `/fuel-receipts`                                                                                                   | sample tanks/receipts          |
| Credit    | `/credit/customers` (balances), `/credit/customers/import.csv` (dry-run → commit)                                                                 | sample accounts                |
| Reports   | `/reports/daily-sales`, `/reports/collections`, `/export.csv?type=sales                                                                           | collections`                   | sample tables |
| Settings  | `/api/v1/me`, `/health`, `DELETE /session`, `/api/v1/export` (owner, PIN)                                                                         | demo info                      |
| Login     | `POST /session` (+ refresh/rotation via sessionStorage)                                                                                           | demo mode entry                |

**Known wiring gaps:** credit "add customer" button still a prototype toast; sales entry UI does not
exist yet (recorded via backend/seed/API only); alerts & sales-trend chart are illustrative; dip
readings not captured (stock variance shows —); CSV import UI shows dry-run summary but not full
row-level error table.
