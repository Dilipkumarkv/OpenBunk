# OpenBunk — Deployment & Operations Runbook

Status: v0.9 (post-Wave 0 hardening). Staging-grade. Production deployment requires explicit owner approval (Phase 08 policy).
Scope: one station, single host, PostgreSQL — a real but modest cloud footprint.

## 1. What is ready vs what is not

| Component                                                                           | Status                                                                   |
| ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| Dockerized frontend (unprivileged nginx) + API (python slim, non-root) + PostgreSQL | Written; CI builds and health-checks the stack on every push             |
| Dedicated one-shot `migrate` service (advisory lock)                                | Written; CI verifies migrations run once before the API starts           |
| Staging steps (this document)                                                       | Documented; rehearsed in CI end-to-end                                   |
| HTTPS/TLS                                                                           | Documented (Caddy example); NOT verified — requires a real host + domain |
| Managed/secured self-hosted PostgreSQL                                              | Documented; not provisioned anywhere                                     |
| Native backup (`pg_dump -Fc`) + verified restore                                    | Automated roundtrip test green on SQLite locally and Postgres in CI      |
| Monitoring & log retention                                                          | Documented; not provisioned                                              |
| Production deployment                                                               | **Not done — needs explicit owner approval + a host + domain**           |

## 2. Target architecture (single host, minimal exposure)

```
            443/80 ┌──────────────┐
Internet ─────────►│ Caddy (TLS)  │  (automatic HTTPS)
                   └──────┬───────┘
                          │ proxy
                   ┌──────┴───────┐
                   │ web (nginx)  │  serves SPA, /api/* proxied
                   └──────┬───────┘
                          │ internal network only
                   ┌──────┴───────┐       ┌──────────────┐
                   │ api (uvicorn)│──────►│ db Postgres16│  no public port
                   └──────────────┘       └──────────────┘
                          ▲
                   ┌──────┴───────┐
                   │ migrate      │  one-shot: alembic upgrade head under advisory lock
                   └──────────────┘
```

- Database never published; only `web` published via Caddy on 80/443. The compose file binds the
  web container to `127.0.0.1:8080` so a local `docker compose up` is not exposed to the LAN.
- Secrets via environment file/secret store, never in images.
- Containers run as non-root (API user `app`, nginx-unprivileged uid 101 on port 8080); images
  pinned by minor tag (`python:3.14-slim`, `nginxinc/nginx-unprivileged:1.27-alpine`,
  `postgres:16-alpine`) — pin to digests for strict production use.

## 3. Provision staging (documented steps — needs a host)

Prereqs: a small VM (e.g. 1–2 vCPU, 2 GB) with Docker + compose; a domain A/AAAA record pointing at it.

```bash
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER && newgrp docker
git clone git@github.com:Dilipkumarkv/OpenBunk.git && cd OpenBunk
cat > .env <<'EOF'
POSTGRES_PASSWORD=<long-random>          # from a password manager, never committed
PUBLIC_ORIGIN=https://staging.example.com
ENVIRONMENT=production                     # disables /api/docs/openapi, enables HSTS
OPENBUNK_SEED_PIN=                        # EMPTY in real deployments — no demo users
EOF
docker compose --env-file .env build
docker compose --env-file .env up -d
docker compose --env-file .env wait migrate   # one-shot migrations; non-zero = failure
docker compose --env-file .env ps         # api/web healthy, migrate exited 0
caddy reverse-proxy --from staging.example.com --to localhost:8080   # or a Caddyfile / traefik
```

Verify:

```bash
curl -I https://staging.example.com/healthz        # 200 (web container)
curl https://staging.example.com/api/v1/readiness     # {"status":"ready","database":"ok"}
curl -X POST https://staging.example.com/api/v1/session -H 'Content-Type: application/json' \
     -d '{"station_code":"OB-001","employee_code":"OWNER-1","pin":"<set at provision-time>"}'  # 201 (only if seeded)
```

Create the first owner WITHOUT demo access: set `OPENBUNK_SEED_PIN=<strong pin>` **only for the first
boot**, sign in once as owner, create your own owner user (`/api/v1/employees`), then unset
`OPENBUNK_SEED_PIN` (restart) or offboard EMP-00…04. Never leave demo accounts on a real deployment.

## 4. Deploy + verify health (release procedure)

1. `git fetch && git checkout <release-ref>`
2. **`docker compose run --rm migrate python -m app.backup create /data/pre-<ref>.dump`**
   (native `pg_dump -Fc` dump + SHA-256 manifest; see §6)
3. `docker compose build && docker compose up -d && docker compose wait migrate`
   (runs `migrate`, then API, then web)
4. Verify: `curl https://<host>/api/v1/readiness` = ready; spot-check `/api/v1/reports/daily-sales?date=<today>`.
5. Rollback: `git checkout <previous-ref> && docker compose build && docker compose up -d && docker compose wait migrate`.
   App rollback is safe because released schema is additive-only; if a destructive migration was ever
   applied, restore from the §6 backup instead (see §7).

## 5. Apply migrations safely

- Migrations run **once** in the dedicated `migrate` service (`python -m app.migrate`) before the API
  starts. It takes a Postgres advisory lock, so multiple API/worker replicas cannot race; the API
  container itself never migrates.
- For a planned schema change: back up first, then
  `docker compose run --rm migrate python -m app.migrate`.
- Verify models and revisions agree with `python -m alembic check` (CI runs it on every push).
- **Backup before any schema change** (mandatory; use a maintenance window).
- Rollback strategy: `alembic downgrade <revision>` for the shipped revisions; for anything
  destructive, restore from backup instead. Never downgrade a production database with live writes
  without a maintenance window and a fresh backup.

## 6. Backup & restore (native, verified 2026-11-16)

- Backup: `python -m app.backup create backups/backup-<timestamp>.dump` — on Postgres this runs
  `pg_dump -Fc`; on SQLite it uses the native backup API. Each dump gets a
  `<name>.dump.manifest.json` with SHA-256, Alembic revision, row counts, and timestamp. Dumps contain
  PIN hashes — treat them as secrets and store them encrypted off-host.
- Restore: `python -m app.backup restore backups/backup-<timestamp>.dump --force`. Restores refuse to
  run without `--force`, take a pre-restore snapshot, and verify row counts afterward. A dump from a
  different Alembic revision is rejected unless `--allow-revision-mismatch` is passed.
- Automated drill: `backend/tests/test_backup_restore.py` backs up, mutates, restores, and compares
  row counts; CI runs it against PostgreSQL (requires `pg_dump`/`pg_restore` client tools).
- Host-level drill before every production migration:
  1. `docker compose run --rm migrate python -m app.backup create /data/drill.dump`
  2. restore into a scratch database with `restore --force` and compare the printed row counts
  3. keep the manifest with the release ticket and delete the scratch DB.
- Schedule: daily `backup` cron (keep 14 dailies + 4 weeklies); store off-host (object storage with
  encryption at rest or an encrypted volume); test restores **quarterly**.

## 7. Roll back application; database rollback strategy

- App rollback: redeploy previous image/tag (§4.5). Stateless containers make this trivial.
- Database rollback: prefer forward-fix. If unavoidable: restore the §4.2 backup with
  `python -m app.backup restore --force` into an empty maintenance window. This is destructive — it discards
  all writes since the backup. Announce + get approval + backup the current state first.

## 8. Rotate secrets / revoke compromised credentials

- Session tokens: revoke per employee via `DELETE /api/v1/employees/{id}` re-activation flow, or
  wipe `session_tokens` + force re-login for everyone: `docker compose exec db psql -U openbunk -c
'UPDATE session_tokens SET revoked_at = now()'`.
- DB password: rotate in Postgres (`ALTER USER openbunk PASSWORD …`), update `.env`, recreate api/web
  containers; the password lives only in env vars.
- PIN reset: no self-service flow yet — owner re-creates the employee or resets via a re-seed run
  (planned: owner-side PIN reset endpoint, Phase 09).

## 9. Incident response & owner contact

1. Identify: `docker compose logs --tail 200 api web`, `docker compose ps`.
2. Isolate: `docker compose stop web` to take the station offline (API stays internal).
3. Preserve: copy logs + backup JSON to offline storage before any fix attempt.
4. Recover: restore from latest known-good backup (§6) after fixing root cause.
5. Communicate: repo owner (`Dilipkumarkv`, GitHub) as single point of accountability; post-mortem
   in `docs/` within 7 days.

## 10. Offboarding / vendor-independent exit

- `GET /api/v1/export` (owner PIN) downloads a complete JSON export of the station — schema
  independent of any vendor. Native database dumps (`app.backup`) are equally portable.
- Decommission: export → stop stack → delete volumes (`docker compose down -v`) → archive encrypted
  backups per retention policy.

## 11. Logs do not contain secrets — verification

Request logging records method/path/status/request_id/elapsed only — never bodies, headers, or query
strings with credentials. Verify with: `docker compose logs api | grep -iE 'pin|password|token|secret'`
(expect no output). Error responses include only `code/message/details/requestId`.
