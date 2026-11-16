# DeepBNK — Release Readiness Report (Phase 09, 2026-11-16)

**Verdict: PROTOTYPE with pilot-grade internals — NOT cleared for pilot or production release.**
The owner must explicitly approve any non-prototype use (spec gate), and a staging host must be
provisioned first. Everything below is verified or explicitly excluded — no inflated claims.

## Release label: Prototype (v0.9)

Labels: **Prototype** = visual interactions on empty states (no bundled sample data) · **Pilot** =
controlled real data with backups/support/UAT · **Production** = full operational gates. DeepBNK is
not a pilot: it has no hosted environment, no trained users, no real data, no SLA/support, and the
operator-facing hardware/dispenser path is absent by design.

## Checklist, item by item (spec Phase 09)

| #   | Item                                              | Status                                                                                                                                                                         |
| --- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | Product scope & limitations documented            | ✓ (this file, `OPERATOR` guide, STATUS, README)                                                                                                                                |
| 2   | User roles & permissions tested                   | ✓ 5 roles enforced server-side; `test_security.py`, permission matrix `docs/permissions.md`                                                                                    |
| 3   | Financial calculations independently reviewed     | ⚠ Self-reviewed (worked examples in `docs/calculations.md`; rounding half-up unit-tested; totals cross-checked twice in E2E); **no second human accountant/engineer sign-off** |
| 4   | Meter reset/rollover & correction workflow tested | ✓ rollover domain tests + override-reason close; stock adjustment endpoint now tested (`tests/test_adjustments.py`)                                                            |
| 5   | Shift closing atomic & idempotent                 | ✓ single transaction + row lock; `Idempotency-Key` replay verified at API and in browser                                                                                       |
| 6   | Audit trail complete for sensitive actions        | ✓ see `audit_events` actions; owner/auditor read; immutability by construction (append-only)                                                                                   |
| 7   | Data export works & documented                    | ✓ JSON station export + 4 CSV types; tested                                                                                                                                    |
| 8   | Backup/restore drill                              | ✓ executed + automated test (`test_backup_restore.py`)                                                                                                                         |
| 9   | Security review & dependency scan                 | ✓ CI: `npm audit` + `pip-audit` clean; argon2id, lockout, re-auth, headers; **not** a third-party pen test                                                                     |
| 10  | Mobile usability on real Android                  | ✗ **NOT TESTED** — no device in loop; responsive CSS ≤700px layout exists                                                                                                      |
| 11  | Network interruption & reconnect                  | ✓ draft persistence (tested) + offline/live mode split; real N-failover not yet exercised                                                                                      |
| 12  | Printer/PDF workflow                              | ⚠ print CSS shipped; not verified on a physical printer                                                                                                                        |
| 13  | Operator training guide / quick reference         | ✓ `docs/operator-guide.md`                                                                                                                                                     |
| 14  | Support/incident & recovery runbook               | ✓ `docs/deployment.md` (backup/restore, rollback, secret rotation, offboarding)                                                                                                |
| 15  | Sample data separated from live data              | ✓ no sample data ships in the UI (empty states + sign-in guidance until the API returns data); production refuses to seed without explicit `OPENBUNK_SEED_PIN`                 |
| 16  | No unresolved critical/high defects               | ✓ CI green (frontend+backend+compose); **no defect tracker in use** — no formal triage process exists                                                                          |
| 17  | User explicitly approves pilot/production         | ✗ **NOT GIVEN** — release gate, owner only                                                                                                                                     |

## What DeepBNK can do today (honest)

- Record shifts with assisted meter math; closing is atomic, idempotent, reconciliation-enforced.
- Track tanks via movement ledger; fuel receipts update book stock; variance flagged via dip entry.
- Credit ledger with limit status; CSV import/export; station export JSON; reports (daily sales, collections).
- 5 roles server-enforced; re-auth for sensitive actions; full audit trail.
- Docker stack builds & passes CI rehearsal on every push.

## Known limitations (binding until closed)

- No staging/production host; HTTPS unverified; restore drill done on SQLite only (Postgres pending staging).
- Dispenser/hardware integration does not exist (irrelevant for current scope; meter is manual).
- No sales-entry screen (sales arrive via API/seed only); no payment gateway by design.
- No account recovery/PIN reset; no multi-instance rate limiting; no RLS at Postgres level.
- No bundled demo data; with no reachable backend the UI shows empty states and sign-in guidance.
- Not cleared for real data (`docs/security-checklist.md`).

## Outstanding risks

1. **Authorization regressions** as features grow — mitigated by permission matrix + mandatory tests per endpoint.
2. **Backup corruption discovered late** — mitigated by drill; still wants a Postgres drill on staging.
3. **Operator error under pressure** — partially mitigated by re-auth/override flows; training needed.
4. **Scope creep toward production without gates** — this document + the release label is the control.
5. **Single developer bus factor** — all knowledge must live in-repo (it does: AGENTS.md, docs/, STATUS.md).

## Release label decision & recommendation

**Recommended label: Prototype v0.9 (pilot-ready internal build, owner-gated).**
Do not market or use for live operations. The only sensible next step after this report is:

1. Owner decides: (a) remain prototype → stop here;
2. (b) pilot → provision a staging host (small VPS), seed a **test** station (no real finance),
   run the Postgres restore drill **on staging**, execute operator UAT with 1–2 staff for 1–2 weeks;
3. (c) production → all of (b) **plus** security checklist cleared, pen-test-level review,
   support/SLA, monitoring, and a signed release approval from the owner.

**Owner decision (2026-11-16): REMAIN PROTOTYPE.** No pilot, no production — the repository stays a
CI-green prototype with honest verification records. Revisit only when a real staging host +
operator UAT are planned.
