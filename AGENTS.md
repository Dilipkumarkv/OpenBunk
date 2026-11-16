# DeepBNK — Agent Instructions (project-local)

Conventions for any coding agent (human-piloted or harness-driven) working in this repo.
This file complements `STATUS.md` and the phase docs; it does not override user instructions.

## Phase protocol

- Work is organized by phase files (`NN_*.md`). Read the target spec **and** `STATUS.md` before editing.
- One coherent scope per phase. Verify with real commands before claiming completion; record results
  in `STATUS.md` (completed work, exact commands + outcomes, known issues, next phase).
- Never mark a phase complete on the strength of "it compiles" alone — run lint, type-check, tests,
  format, build, and (where relevant) live end-to-end checks.

## Non-negotiables

- **No bundled sample/test data.** The UI ships empty states (`—`, "no data yet", sign-in
  guidance) until the API returns data; never add placeholder figures. No button may claim a
  server write that did not happen — unavailable actions say so.
- **Financial correctness:** Decimal/NUMERIC money; rounding half-up to 2 dp at boundaries;
  posted records immutable; corrections = reversal/adjustment + audit event.
- **Authorization everywhere:** UI hiding is not authorization. The matrix in `docs/permissions.md`
  is enforced server-side on every endpoint; respect it when adding endpoints.
- **Station scoping** on every query — no cross-station reads/writes, ever.
- **No secrets in source, logs, or frontend bundles.** `.env.example` documents keys only.
- **Domain layer** (`src/domain/` frontend, `backend/app/domain.py` backend) holds pure logic;
  keep it free of framework/DOM/FastAPI dependencies; mirror rules in both places + tests.
- **Append-only tables** (stock_movements, credit_ledger_entries, audit_events): no UPDATE/DELETE paths.

## Verification commands

Frontend: `npm run lint && npm run type-check && npm run test && npm run format:check && npm run build`
Backend (from `backend/`): `python -m pytest` (SQLite locally; CI runs Postgres)
Migrations: `alembic upgrade head` / `downgrade base` — verify round-trip when revising models.

## E2E before signing off a phase

Serve the built frontend (`vite preview`) + backend (`uvicorn`) and drive the critical path in a
browser: sign in, perform one real business write, verify the effect in the UI **and** the API.
Record what was actually verified; do not claim visual checks you did not see.

## Commit conventions

- Phase-scoped commits on `main` (e.g. `Phase 06: integrations …`); follow-up fixes reference the
  defect they fix. Push after committing; CI must be green before closing a phase.
- Never force-push; never delete user data; no production hard resets/migrations without approval.
