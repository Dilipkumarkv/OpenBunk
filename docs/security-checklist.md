# DeepBNK — Security Checklist (pre-real-data gate)

Required before any real station data enters the system. Completed items are verified by tests
or CI; unchecked items block production use.

## Authentication & sessions

- [x] PINs are 6+ digits, hashed with argon2id (argon2-cffi); no plaintext or reversible storage
- [x] Tokens stored as sha256 hashes only; raw tokens never logged or persisted
- [x] Short-lived access token (15 min) + single-use rotating refresh token (12 h)
- [x] Refresh-token reuse burns the entire credential family (detected + audited)
- [x] Login throttling: per-IP rate limit on `/session` + `/session/refresh`
- [x] Account lockout: 5 consecutive failures → 15-minute lock (429), audited (`account.locked`)
- [x] Re-authentication lockout: 5 wrong `X-Reauth-Pin` attempts in 15 minutes → 429
      (`reauth.locked` audit) and all of that employee's sessions are revoked
- [x] No default production password: seed PIN only from `OPENBUNK_SEED_PIN`; in
      `ENVIRONMENT=production` seeding refuses to create employees without an explicit PIN, and
      rejects weak/default PINs of any length under 6 digits
- [x] Last-owner guards: the final active owner cannot be offboarded or demoted (audited refusals)

## Authorization

- [x] Permission matrix documented (`docs/permissions.md`) and enforced server-side on every endpoint
- [x] Station scoping on all queries; cross-station access tests return 404/empty (test_security.py)
- [x] Re-authentication (`X-Reauth-Pin`) for sensitive actions: shift close, station update,
      role change, offboard, export, tank adjustment, employee creation
- [x] Cashier cannot close shifts; auditor cannot mutate anything; accountant cannot touch meters
- [x] Role changes and offboarding are audited (`employee.role_changed`, `employee.offboarded`)
- [x] Offboarded employees' sessions are revoked immediately
- [x] Credit limits are server-enforced: locked customer row, sales over the limit are rejected,
      and only an owner may override with a reason (audited `credit.override`)
- [x] Sales are priced by the server (`fuel_prices`, effective-dated); client-supplied amounts and
      prices are rejected/ignored, and nozzle→tank→product is validated server-side
- [x] Sales and receipts require an `Idempotency-Key` bound to a request hash (mismatched payload
      reusing a key is rejected)

## Financial correctness & reconciliation

- [x] Shift close requires collections; credit sales are excluded from expected cash
- [x] Collections, variance and rollover are persisted and reports are rollover-aware
- [x] A variance over ₹1.00 requires a written reason **and** a different second approver
      (`X-Approval-Code` + `X-Approval-Pin`); self-approval is rejected
- [x] Money NUMERIC/Decimal; rounding half-up documented (docs/calculations.md)
- [x] Append-only tables for stock movements, credit ledger, audit events — no update/delete paths
- [x] Posted records immutable; corrections are adjustments + audit events

## Data protection & operations

- [x] No secrets in repo, logs, or frontend bundle (tokens/PINs never logged; export excludes pin_hash)
- [x] Security headers: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`,
      `Content-Security-Policy`; HSTS sent by the bundled nginx config (browser honours it over HTTPS)
- [x] Migrations are safe on populated databases: server defaults in historical revisions,
      SQLite batch mode, and an upgrade/downgrade test over a populated database in CI
- [x] Migrations run once in a dedicated container under a Postgres advisory lock; the API never
      migrates on boot
- [x] Backups are native (`pg_dump -Fc` / SQLite backup) with a SHA-256 manifest and row counts;
      writes are atomic; restores require `--force`, take a pre-restore snapshot, and verify counts
- [x] Native backup → mutate → verified restore roundtrip is an automated test (CI runs it on Postgres)
- [x] Containers: API runs as non-root, nginx image is unprivileged (uid 101, port 8080), the web
      port is bound to loopback, and images exclude `.env`, databases, and VCS data
- [x] Fail-closed configuration: `ENVIRONMENT` is required; production rejects SQLite, wildcard or
      non-HTTPS CORS origins, weak DB passwords, and weak seeded PINs

## Still pending (block real-data use)

- [ ] Account recovery / PIN reset flow — pending (document break-glass owner procedure)
- [ ] Backup restore drill on a real staging host — automated test passes; host-level drill pending
- [ ] HTTPS termination + WAF — deployment concern; HSTS header present but only honoured over TLS
- [ ] Rate limiter is single-instance in-memory — single replica only, or move to Redis
- [ ] Android device, screen-reader and printed-sheet verification — not executable in this environment
- [ ] Operator UAT with dummy data and written feedback

**Gate status: NOT CLEARED for real data** (6 items pending). Wave 0 closed the seven P0 audit
blockers at the code/test level; the open items are deployment and field verification.
