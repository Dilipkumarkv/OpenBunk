# OpenBunk Development Status

## Current milestone

UI prototype in-app (Phase 02) — complete. Next: domain rules and tests (Phase 03).

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
- [ ] Domain rules and tests
- [ ] API/database
- [ ] Auth/security
- [ ] Integrations
- [ ] CI and quality gates
- [ ] Staging deployment
- [ ] Release readiness

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

## Known limitations

- Prototype uses illustrative sample data.
- No persistence, authentication, backend, cloud, or hardware integration.
- Buttons that say demo/preview do not perform real business writes.

## Update this file after every phase

Record actual commands and results, files changed, defects, and next phase.
