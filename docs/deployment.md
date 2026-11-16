# DeepBNK — Deployment & Operations Runbook

Status: v0.9 (post-Wave 0 hardening). Staging-grade. **Production deployment requires explicit owner approval** and is not authorized as of this writing. The release label remains **Prototype v0.9** — do not enter real station data until a staging host, operator UAT, and owner sign-off are complete.

Scope: one station, single host, PostgreSQL — a real but modest cloud footprint.

## 1. What is ready vs what is not

| Component                                                                           | Status                                                              |
| ----------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| Dockerized frontend (unprivileged nginx) + API (python slim, non-root) + PostgreSQL | Written; CI builds and health-checks the stack on every push        |
| Dedicated one-shot `migrate` service (advisory lock)                                | Written; CI verifies migrations run once before the API starts      |
| Staging steps (this document)                                                       | Documented; rehearsed in CI end-to-end                              |
| HTTPS/TLS (Caddy)                                                                   | Documented below; NOT verified — requires a real host + domain      |
| Managed/secured self-hosted PostgreSQL                                              | Documented; not provisioned anywhere                                |
| Native backup (`pg_dump -Fc`) + verified restore                                    | Automated roundtrip test green on SQLite locally and Postgres in CI |
| Monitoring & log retention                                                          | Documented; not provisioned                                         |
| Production deployment                                                               | **Not done — needs explicit owner approval + a host + domain**      |

## 2. Target architecture (single host, minimal exposure)

```
            443/80 ┌──────────────┐
Internet ─────────►│ Caddy (TLS)  │  (automatic HTTPS, Let's Encrypt)
                    └──────┬───────┘
                           │ proxy (localhost only)
                    ┌──────┴───────┐
                    │ web (nginx)  │  serves SPA, /api/* proxied to api
                    │              │  bound to 127.0.0.1:8080 (not LAN-exposed)
                    └──────┬───────┘
                           │ internal Docker network only
                    ┌──────┴───────┐       ┌──────────────┐
                    │ api (uvicorn)│──────►│ db Postgres16│  no public port
                    └──────────────┘       └──────────────┘
                           ▲
                    ┌──────┴───────┐
                    │ migrate      │  one-shot: alembic upgrade head under advisory lock
                    └──────────────┘
```

- Database never published; only `web` (via Caddy on 443) is internet-facing.
- `web` container binds `127.0.0.1:8080` only — Caddy proxies to it over localhost.
- Secrets via environment file/secret store, never in images.
- Containers run as non-root (API user `app`, nginx-unprivileged uid 101 on port 8080); images pinned by minor tag (`python:3.14-slim`, `nginxinc/nginx-unprivileged:1.27-alpine`, `postgres:16-alpine`) — pin to digests for strict production use.

## 3. Prerequisites (production)

- A small cloud VM (e.g. 1–2 vCPU, 2 GB RAM, 20 GB disk) with Docker + compose plugin.
- A domain (e.g. `station.example.com`) with an A/AAAA record pointing at the VM.
- Outbound HTTPS access for Let's Encrypt (port 80 for HTTP-01 challenge, or DNS challenge).
- A password manager entry for `POSTGRES_PASSWORD` (12+ random characters).
- A backup destination: object storage or an encrypted off-host volume.

## 4. Caddy (TLS termination)

Create `Caddyfile` at the repo root (never committed with secrets — it contains no secrets, so it is safe to commit):

```
station.example.com {
    encode gzip zstd

    reverse_proxy localhost:8080 {
        header_up Host {upstream_hostport}
        header_up X-Forwarded-Proto https
        header_up X-Forwarded-For {remote}
        header_up X-Request-Id {http.request.header.X-Request-Id}
    }

    @health path /healthz
    respond @health 200 "ok"
}
```

Caddy obtains and renews a Let's Encrypt certificate automatically. Ports 80 and 443 must be reachable from the internet at provision time.

## 5. Production environment file

Create `.env` (never commit):

```env
# Frontend (Vite) — browser origin served by Caddy/TLS
VITE_API_URL=https://station.example.com

# Backend — required
DATABASE_URL=postgresql+psycopg://openbunk:<strong-password>@db:5432/openbunk

# CORS — production requires https origins, no wildcards
CORS_ORIGINS=https://station.example.com

# REQUIRED: production disables /api/docs and /api/openapi.json, enables HSTS
ENVIRONMENT=production

# Rate limit for /api/v1/session (per client IP, per minute)
RATE_LIMIT_PER_MINUTE=20

# Seed PIN — EMPTY in production. Set a 6+ digit value only for the first
# boot to create the initial owner, then unset and restart.
OPENBUNK_SEED_PIN=

# docker-compose stack only
PUBLIC_ORIGIN=https://station.example.com

# Postgres container password — 12+ random characters, from a password manager
POSTGRES_PASSWORD=<strong-random>
```

Production guards (enforced by `backend/app/config.py` when `ENVIRONMENT=production`):

- Rejects SQLite `DATABASE_URL`
- Rejects wildcard (`*`) or non-https CORS origins
- Rejects database passwords shorter than 12 chars or common defaults
- Rejects weak/default `OPENBUNK_SEED_PIN` (must be 6+ digits, not a known default)

## 6. Provision the host

```bash
# 1. Install Docker + compose
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER && newgrp docker

# 2. Install Caddy (TLS termination)
sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt-get update
sudo apt-get install -y caddy

# 3. Clone the repo
git clone git@github.com:Dilipkumarkv/OpenBunk.git && cd OpenBunk

# 4. Write Caddyfile (replace station.example.com)
cat > Caddyfile <<'EOF'
station.example.com {
    encode gzip zstd
    reverse_proxy localhost:8080 {
        header_up Host {upstream_hostport}
        header_up X-Forwarded-Proto https
        header_up X-Forwarded-For {remote}
        header_up X-Request-Id {http.request.header.X-Request-Id}
    }
    @health path /healthz
    respond @health 200 "ok"
}
EOF
sudo cp Caddyfile /etc/caddy/Caddyfile
sudo systemctl enable --now caddy

# 5. Write .env (replace placeholders; never commit)
cat > .env <<'EOF'
VITE_API_URL=https://station.example.com
DATABASE_URL=postgresql+psycopg://openbunk:<strong-password>@db:5432/openbunk
CORS_ORIGINS=https://station.example.com
ENVIRONMENT=production
RATE_LIMIT_PER_MINUTE=20
OPENBUNK_SEED_PIN=
PUBLIC_ORIGIN=https://station.example.com
POSTGRES_PASSWORD=<strong-random>
EOF
chmod 600 .env

# 6. Firewall: only SSH, HTTP, HTTPS
sudo ufw default deny incoming
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

## 7. Run the stack

```bash
docker compose --env-file .env build
docker compose --env-file .env up -d

# Confirm migrations ran (migrate service exited 0)
docker compose --env-file .env ps -a --format '{{.Service}} {{.ExitCode}}'
# expect: migrate 0

# Confirm api and web are healthy
docker compose --env-file .env ps
```

Caddy now terminates TLS and proxies to `web` on `localhost:8080`. Verify:

```bash
curl -I https://station.example.com/healthz        # 200
curl https://station.example.com/api/v1/readiness   # {"status":"ready","database":"ok"}
```

## 8. Create the first owner (production, no seeded users)

`OPENBUNK_SEED_PIN` is empty by production default, so no seeded employees exist.

Option A — seed once with a strong PIN, then create a real owner and disable seeding:

```bash
# Set a strong 6+ digit PIN, seed, then immediately unset it
OPENBUNK_SEED_PIN=246813 docker compose --env-file .env exec -T api python -m app.seed
# Sign in as EMP-00 / 246813, create your own owner user via /api/v1/employees
# Then unset OPENBUNK_SEED_PIN in .env and restart: docker compose --env-file .env up -d
```

Option B — create the owner directly via the API without seeding at all.

Never leave `EMP-00`…`EMP-04` seeded employees on a real deployment.

## 9. Release procedure

1. **Owner approval** — written approval for this specific release/ref.
2. `git fetch && git checkout <release-ref>`
3. **Backup before any change:** `docker compose run --rm migrate python -m app.backup create /data/pre-.dump` (native `pg_dump -Fc` + SHA-256 manifest; see §11)
4. `docker compose --env-file .env build`
5. `docker compose --env-file .env up -d`
6. Confirm `migrate` exited 0 in `docker compose ps -a`
7. Verify: `curl https://<host>/api/v1/readiness` = ready; spot-check reports.
8. Rollback: `git checkout <previous-ref> && docker compose --env-file .env build && docker compose --env-file .env up -d` (confirm `migrate` exits 0). App rollback is safe because released schema is additive-only; for destructive migrations, restore from §11 instead.

## 10. Migrations

- Migrations run **once** in the dedicated `migrate` service (`python -m app.migrate`) before the API starts. It takes a Postgres advisory lock, so multiple replicas cannot race; the API container itself never migrates.
- For a planned schema change: back up first, then `docker compose run --rm migrate python -m app.migrate`.
- Verify models and revisions agree with `python -m alembic check` (CI runs it on every push).
- **Backup before any schema change** (mandatory; use a maintenance window).
- Rollback strategy: `alembic downgrade <revision>` for shipped revisions; for anything destructive, restore from backup instead. Never downgrade a production database with live writes without a maintenance window and a fresh backup.

## 11. Backup & restore (native, verified)

Backup: `python -m app.backup create backups/backup-<timestamp>.dump` — on Postgres runs `pg_dump -Fc`; on SQLite uses the native backup API. Each dump gets `<name>.dump.manifest.json` with SHA-256, Alembic revision, row counts, timestamp. Dumps contain PIN hashes — treat as secrets, store encrypted off-host.

Restore: `python -m app.backup restore backups/backup-<timestamp>.dump --force`. Restores refuse without `--force`, take a pre-restore snapshot, verify row counts afterward, and reject dumps from a different Alembic revision unless `--allow-revision-mismatch` is passed.

Automated drill: `backend/tests/test_backup_restore.py` runs in CI against PostgreSQL (client `pg_dump`/`pg_restore` 16, matching the server major).

Host-level drill before every production migration:

1. `docker compose run --rm migrate python -m app.backup create /data/drill.dump`
2. Restore into a scratch database with `restore --force`; compare printed row counts.
3. Keep the manifest with the release ticket; delete the scratch DB.

Schedule: daily `backup` cron (keep 14 dailies + 4 weeklies); store off-host with encryption at rest; test restores quarterly.

Example daily cron (root crontab):

```cron
0 2 * * * cd /home/<user>/OpenBunk && docker compose --env-file .env run --rm migrate python -m app.backup create /data/backups/backup-$(date +\%Y\%m\%d).dump >> /var/log/openbunk-backup.log 2>&1
```

## 12. Logs, monitoring & retention

- Structured stdout logs with request IDs (`X-Request-Id`); no secrets logged.
- Verify no secrets: `docker compose logs api | grep -iE 'argon2|pin_hash|password|secret'` (expect no output).
- Rotate container logs with Docker's `log-driver` (add to `docker-compose.yml` service definitions if needed):
  ```yaml
  logging:
    driver: 'json-file'
    options:
      max-size: '10m'
      max-file: '5'
  ```
- Monitoring is not provisioned — set up uptime checks on `/api/v1/readiness` and disk/alerting on the backup volume.

## 13. Roll back application; database rollback strategy

- App rollback: redeploy previous image/tag (§9). Stateless containers make this trivial.
- Database rollback: prefer forward-fix. If unavoidable: restore the §11 backup with `python -m app.backup restore --force` into an empty maintenance window. This is destructive — it discards all writes since the backup. Announce, get approval, and back up the current state first.

## 14. Rotate secrets / revoke compromised credentials

- Session tokens: revoke per employee via `DELETE /api/v1/employees/{id}`, or wipe all sessions: `docker compose exec db psql -U openbunk -c "UPDATE session_tokens SET revoked_at = now()"`.
- DB password: rotate in Postgres (`ALTER USER openbunk PASSWORD …`), update `.env`, recreate api/web containers; the password lives only in env vars.
- PIN reset: no self-service flow yet — owner re-creates the employee or resets via a re-seed run (planned: owner-side PIN reset endpoint).

## 15. Incident response

1. Identify: `docker compose logs --tail 200 api web`, `docker compose ps`.
2. Isolate: `docker compose stop web` to take the station offline (API stays internal).
3. Preserve: copy logs + backup to offline storage before any fix attempt.
4. Recover: restore from latest known-good backup (§11) after fixing root cause.
5. Communicate: repo owner (`Dilipkumarkv`, GitHub) is the single point of accountability; post-mortem in `docs/` within 7 days.

## 16. Offboarding / vendor-independent exit

- `GET /api/v1/export` (owner PIN) downloads a complete JSON export of the station — schema independent of any vendor. Native database dumps (`app.backup`) are equally portable.
- Decommission: export → stop stack → delete volumes (`docker compose down -v`) → archive encrypted backups per retention policy.

## 17. Logs do not contain secrets — verification

Request logging records method/path/status/request_id/elapsed only — never bodies, headers, or query strings with credentials. Verify with: `docker compose logs api | grep -iE 'pin|password|token|secret'` (expect no output). Error responses include only `code/message/details/requestId`.

## 18. Pre-production checklist (owner gate)

Do not mark any item complete without the corresponding evidence.

- [ ] Explicit written owner approval for production deployment
- [ ] Staging host provisioned with domain + TLS (Caddy/Let's Encrypt)
- [ ] `ENVIRONMENT=production` confirmed; production guards pass at startup (no SQLite, no wildcard CORS, strong DB password, no weak seed PIN)
- [ ] Staging backup/restore drill executed and documented (§11)
- [ ] `OPENBUNK_SEED_PIN` empty; no seeded employees (`EMP-00`…`EMP-04`) present
- [ ] Firewall allows only 22/80/443; database port not published
- [ ] CI green on the release ref (all three jobs: checks, compose, backend)
- [ ] Operator UAT with dummy data completed and feedback recorded
- [ ] Android device, screen-reader, and printed-shift-sheet checks completed
- [ ] Backup schedule + off-host storage configured and tested
- [ ] On-call / incident contact assigned

## 19. Netlify (frontend-only)

Netlify hosts the static React SPA only. It cannot run the FastAPI backend (Functions supports
JS/TS/Go, not Python/FastAPI + PostgreSQL + Alembic), so a functional deployment needs the API on a
separate container host and `VITE_API_URL` pointing at it. Without an API the UI still loads and
runs with offline empty states (no bundled sample figures).

Config in the repo:

- `netlify.toml` — build command `npm run build`, publish `dist`, Node 24.
- `public/_headers` — CSP, HSTS, nosniff, frame denial, asset caching. Copied to `dist/` so it also
  applies to manual and CLI deploys.
- `public/_redirects` — SPA fallback (`/*` → `/index.html`, status 200). Routing is hash-based
  today, so this is only a safety net.

### Deploy

```bash
npm ci
npm run build                       # tsc -b && vite build → dist/

# Option A — drag and drop: upload the dist/ folder at https://app.netlify.com/drop
# Option B — CLI (use the publish dir so _headers/_redirects ship with it)
npx netlify-cli deploy --dir=dist          # draft URL first
npx netlify-cli deploy --dir=dist --prod   # promote to production
```

### Connect the API

`VITE_API_URL` is baked into the bundle at build time; changing it requires a rebuild/redeploy.

```bash
npx netlify-cli env:set VITE_API_URL https://api.example.com
npx netlify-cli build && npx netlify-cli deploy --dir=dist --prod
```

Then on the API host:

- Add the Netlify origin to `CORS_ORIGINS` (exact origin, https in production), e.g.
  `https://<site>.netlify.app`. Deploy previews and branch deploys use different hostnames — add
  those too if they need API access.
- Keep `ENVIRONMENT=production` guards satisfied (https origins, non-SQLite database, strong DB
  password, empty seed PIN).

Notes:

- Never put secrets in `VITE_*` variables — they are inlined into the public bundle.
- The CSP in `public/_headers` allows `connect-src https:` so any HTTPS API works out of the box;
  tighten it to the API origin once it is fixed.
- The site is HTTPS-only, so an `http://` API URL is blocked as mixed content and the UI stays
  offline (empty states, sign-in unavailable).
