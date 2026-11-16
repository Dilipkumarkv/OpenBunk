# DeepBNK

DeepBNK is a station operations app for fuel bunks: assisted meter entry and shift closing, fuel
stock, credit ledger and daily reports. It ships as an installable, offline-capable PWA and talks
to the FastAPI backend in `backend/`.

## Features

- Dashboard with today's sales, cash collections and recent transactions, loaded from the API
- Shift closing: meter readings, server-configured prices, collections reconciliation, PIN
  re-authentication and authorized rollover
- Fuel stock: tank register (book stock) and fuel receipts
- Credit ledger with CSV import (validate-only dry run, then commit)
- Daily sales and collections reports with PIN-protected CSV export
- Station profile strip (name, code, address) under the top bar on every screen; data requires
  sign-in
- Installable PWA (manifest + service worker) that opens offline with the app shell

The UI never bundles sample or test figures: until the API returns data you see empty states
(`—`, "no data yet", and sign-in guidance).

## Stack

- **Frontend:** React 19 + TypeScript + Vite
- **Styling:** plain CSS design system (`src/index.css`) with self-hosted Plus Jakarta Sans
- **Linting:** oxlint (React + TypeScript rules)
- **Formatting:** Prettier
- **Tests:** Vitest + Testing Library (jsdom)
- **Backend:** Python + FastAPI + PostgreSQL
- **Deployment:** Docker Compose (full stack) or Netlify (frontend only)

## Prerequisites

- Node.js **>= 20** (developed and CI-tested on Node 24)
- npm **11** (ships with Node 24). `packageManager` in `package.json` pins npm; with Corepack
  enabled, `corepack install` will fetch the exact version.
- Git

## Getting started

```bash
git clone <repo-url>
cd <repo-folder>
npm ci          # deterministic install from package-lock.json
npm run dev     # start the dev server (http://localhost:5173)
```

Verify everything works:

```bash
npm run lint          # oxlint
npm run type-check    # tsc -b (noEmit)
npm run test          # vitest run
npm run format:check  # prettier --check .
npm run build         # tsc -b && vite build -> dist/
```

## Scripts

| Script                 | What it does                             |
| ---------------------- | ---------------------------------------- |
| `npm run dev`          | Vite dev server with HMR                 |
| `npm run build`        | Type-check + production build to `dist/` |
| `npm run preview`      | Serve the production build locally       |
| `npm run lint`         | oxlint over the project                  |
| `npm run type-check`   | TypeScript project references, no emit   |
| `npm run test`         | Vitest, single run                       |
| `npm run test:watch`   | Vitest in watch mode                     |
| `npm run format`       | Prettier write                           |
| `npm run format:check` | Prettier check (used in CI)              |

Dependencies are pinned to exact versions in `package.json`; `package-lock.json` is committed and
`npm ci` is used everywhere (local and CI) so builds are reproducible.

## Quick start (Docker stack)

```bash
docker compose up -d                   # db → one-shot migrate → api → web
docker compose ps -a --format '{{.Service}} {{.ExitCode}}'   # migrate should show "0"
docker compose exec api python -m app.seed   # development seed station OB-001 (skip in production)
# open http://localhost:8080  → sign in with EMP-00 / the PIN in OPENBUNK_SEED_PIN (dev only)
```

`OPENBUNK_SEED_PIN` is now empty by default — set a 6+ digit value (e.g. `246813`) before running
the seed, or no seeded employees are created. The web container binds `127.0.0.1:8080` only.

## Backend (Phase 04)

FastAPI + SQLAlchemy 2 + Alembic + Pydantic under `backend/`. The SPA calls it through
`VITE_API_URL` (default `http://localhost:8000`); the backend stands alone under `backend/`.

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Windows; use bin/ on macOS/Linux
# default DATABASE_URL is SQLite (./openbunk.db) — no server needed for local dev
python -m alembic upgrade head                   # create/migrate schema (reversible)
python -m app.seed                               # development seed station OB-001 (set seed PIN first)
python -m uvicorn app.main:app --reload          # http://127.0.0.1:8000  (docs at /api/docs)
```

Against PostgreSQL (production):

```bash
$env:DATABASE_URL = "postgresql+psycopg://openbunk:openbunk@localhost:5432/openbunk"
python -m alembic upgrade head   # from-empty-DB migration is CI-tested against postgres:16
python -m uvicorn app.main:app
```

Tests:

```bash
cd backend
python -m pytest        # uses a throwaway SQLite DB locally; CI runs the same suite
                        # against a postgres:16 service container
```

Auth model: POST `/api/v1/session` → `access_token` (15 min) + `refresh_token` (12 h, rotating).
Refresh via POST `/api/v1/session/refresh`; logout via DELETE `/api/v1/session`. Sensitive actions
need `X-Reauth-Pin: <your PIN>` — see `docs/permissions.md` and `docs/security-checklist.md`.

API conventions (see `/api/docs` for the full OpenAPI schema):

- All endpoints under `/api/v1` (health/readiness at `/health`, `/readiness`, no secrets).
- Bearer-token auth (Phase 05): 15-min access tokens + rotating single-use refresh tokens
  (12 h); argon2id PIN hashes; tokens stored as sha256; lockout after 5 failures (15 min);
  reuse of a refresh token burns the whole credential family. Permissions enforced server-side
  for 5 roles — see `docs/permissions.md`; sensitive actions require `X-Reauth-Pin`.
  **Development seed PIN (6+ digits) comes from `OPENBUNK_SEED_PIN` and is empty by default;
  production refuses weak/default PINs. Never leave seeded employees on a real station.**
- Structured error bodies: `{ "error": { "code", "message", "details", "requestId" } }`.
- `X-Request-Id` on every response (echoed or generated); structured stdout logs.
- List endpoints paginate (`limit`/`offset`, max 100) with totals.
- `Idempotency-Key` is required for `POST /api/v1/shifts/{id}/close` and for sales/receipts; the key
  is bound to a hash of the request body, so a different payload with the same key is rejected.
- Money is NUMERIC(12,2) with half-up rounding; volumes NUMERIC(14,1).
- Posted records are immutable; fuel stock moves only through append-only `stock_movements`;
  audit events are append-only (`/api/v1/audit`, owner/manager only).

## Project structure

```
.github/workflows/ci.yml   # CI: lint, type-check, test, format check, build
public/                    # static assets (favicon)
src/
  components/              # Layout (sidebar/topbar/station strip), icons, auth + toast contexts
  config/station.ts        # station profile shown in the strip (name, code, address)
  domain/                  # tested domain rules — no React/DOM: shift math & parsing,
                           #   strict draft validation, collections reconciliation, credit/stock
  lib/                     # API client, offline shift drafts, format helpers
  pages/                   # Dashboard, Shifts, Fuel, Credit, Reports, Settings, Login
  test/setup.ts            # Vitest setup (jest-dom matchers)
  App.tsx                  # routes (HashRouter)
  main.tsx                 # entry point (fonts + styles)
.env.example               # documented env vars; copy to .env (never commit .env)
docs/domain-model.md       # entities, invariants, immutability rules
docs/calculations.md       # formulas, examples, edge cases, rounding/rollover policy
STATUS.md                  # phase tracking — updated after every phase
```

Routing uses `HashRouter` so the static build works on any file host (e.g. GitHub Pages)
without SPA rewrite rules; switch to `BrowserRouter` if/when a rewrite-capable server exists.

## Netlify (frontend only)

`netlify.toml` plus `public/_headers` / `public/_redirects` are ready for a static deploy:
`npm ci && npm run build`, then drag `dist/` to Netlify Drop or run
`npx netlify-cli deploy --dir=dist --prod`. Netlify cannot host the FastAPI backend — set
`VITE_API_URL` to an externally hosted API, or the UI runs with offline empty states. Full notes:
[`docs/deployment.md` §19](./docs/deployment.md#19-netlify-frontend-only).

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs on pushes to `main` and on pull requests:
`npm ci` → lint → type-check → test → format check → build. Any failing step fails the job.

## Troubleshooting

- **`npm ci` fails with a lock mismatch** — do not hand-edit `package.json` versions; run
  `npm install` locally, commit the updated `package-lock.json`, and retry.
- **Port 5173 already in use** — `npm run dev -- --port 5174` or stop the other process.
- **PowerShell: `npm.ps1 cannot be loaded`** — the repo scripts call `npm`/`npx` via the standard
  CLI. If your execution policy blocks the shim, use `npm.cmd` (what this repo's maintainer env
  uses) or fix policy with `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
- **`tsc -b` reports stale build info** — delete `node_modules/.tmp/*.tsbuildinfo` and re-run.
- **Vitest cannot find jsdom** — reinstall dev dependencies (`npm ci`); `jsdom` must be present.

## License

MIT — see [LICENSE](./LICENSE).
