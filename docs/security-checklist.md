# OpenBunk — Security Checklist (pre-real-data gate)

Required before any real station data enters the system. Completed items are verified by tests
or CI; unchecked items block production use.

## Authentication & sessions

- [x] PINs hashed with argon2id (argon2-cffi); no plaintext or reversible storage
- [x] Tokens stored as sha256 hashes only; raw tokens never logged or persisted
- [x] Short-lived access token (15 min) + single-use rotating refresh token (12 h)
- [x] Refresh-token reuse burns the entire credential family (detected + audited)
- [x] Login throttling: per-IP rate limit on `/session` + `/session/refresh`
- [x] Account lockout: 5 consecutive failures → 15-minute lock (429), audited (`account.locked`)
- [x] No default production password: seed PIN only from `OPENBUNK_SEED_PIN`; in
      `ENVIRONMENT=production` seeding refuses to create employees without an explicit PIN

## Authorization

- [x] Permission matrix documented (`docs/permissions.md`) and enforced server-side on every endpoint
- [x] Station scoping on all queries; cross-station access tests return 404/empty (test_security.py)
- [x] Re-authentication (`X-Reauth-Pin`) for sensitive actions: shift close, station update,
      role change, offboard, export, tank adjustment
- [x] Cashier cannot close shifts; auditor cannot mutate anything; accountant cannot touch meters
- [x] Role changes and offboarding are audited (`employee.role_changed`, `employee.offboarded`)
- [x] Offboarded employees' sessions are revoked immediately

## Data protection

- [x] No secrets in repo, logs, or frontend bundle (tokens/PINs never logged; export excludes pin_hash)
- [x] Security headers: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`,
      `Content-Security-Policy`; HSTS in production
- [x] Money NUMERIC/Decimal; rounding half-up documented (docs/calculations.md)
- [x] Append-only tables for stock movements, credit ledger, audit events — no update/delete paths
- [x] Posted records immutable; corrections are adjustments + audit events

## Operations

- [x] Structured logs with request IDs (`X-Request-Id`); no secrets in logs
- [x] Owner-only data export (`/api/v1/export`) with audit (`data.exported`); CSRF N/A —
      bearer-token API, no cookies (if cookies are introduced, add CSRF protection)
- [ ] Account recovery / PIN reset flow — pending (document break-glass owner procedure)
- [ ] Backup restore drill — pending (Phase 08/09; migration rehearsal is CI-tested only)
- [ ] HTTPS termination + WAF — deployment concern (Phase 08); HSTS header present in production
- [ ] Rate limiter is single-instance in-memory — single replica only, or move to Redis (Phase 08)

**Gate status: NOT CLEARED for real data** (4 items pending). Security posture otherwise
implemented and covered by `backend/tests/test_security.py` (all passing).
