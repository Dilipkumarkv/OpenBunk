# OpenBunk

OpenBunk is a prototype for **assisted meter entry** for building operators. It is being built in
phases; this repository currently contains the **repository foundation only** — an empty,
installable, fully checked React + TypeScript + Vite app. Business features land in later phases
(see `STATUS.md`).

## Stack

- **Frontend:** React 19 + TypeScript + Vite
- **Styling:** plain CSS (`src/index.css`) — one styling system, no framework yet
- **Linting:** oxlint (React + TypeScript rules)
- **Formatting:** Prettier
- **Tests:** Vitest + Testing Library (jsdom)
- **Backend (later phases):** Python + FastAPI + PostgreSQL
- **Deployment (later phases):** Docker Compose

## Prerequisites

- Node.js **>= 20** (developed and CI-tested on Node 24)
- npm **11** (ships with Node 24). `packageManager` in `package.json` pins npm; with Corepack
  enabled, `corepack install` will fetch the exact version.
- Git

## Getting started

```bash
git clone <repo-url>
cd OpenBunk
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

## Project structure

```
.github/workflows/ci.yml   # CI: lint, type-check, test, format check, build
public/                    # static assets served as-is
src/
  test/setup.ts            # Vitest setup (jest-dom matchers)
  App.tsx                  # placeholder — features arrive in later phases
  App.test.tsx             # smoke test
  main.tsx                 # entry point
.env.example               # documented env vars; copy to .env (never commit .env)
STATUS.md                  # phase tracking — updated after every phase
```

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
