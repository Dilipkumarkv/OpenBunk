# OpenBunk — Deployment & Operations Runbook

Status: v0.8. Staging-grade. Production deployment requires explicit owner approval (Phase 08 policy).
Scope: one station, single host, PostgreSQL — a real but modest cloud footprint.

## 1. What is ready vs what is not

| Component                                                              | Status                                                                   |
| ---------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| Dockerized frontend (nginx) + API (python slim, non-root) + PostgreSQL | Written; CI builds and health-checks the stack on every push             |
| Staging steps (this document)                                          | Documented; rehearsed in CI end-to-end                                   |
| HTTPS/TLS                                                              | Documented (Caddy example); NOT verified — requires a real host + domain |
| Managed/secured self-hosted PostgreSQL                                 | Documented; not provisioned anywhere                                     |
| Backup + restore drill                                                 | Executed and verified (see §6)                                           |
| Monitoring & log retention                                             | Documented; not provisioned                                              |
| Production deployment                                                  | **Not done — needs explicit owner approval + a host + domain**           |

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
```

- Database never published; only `web` published via Caddy on 80/443.
- Secrets via environment file/secret store, never in images.
- Containers run as non-root; images pinned by minor tag (`python:3.14-slim`, `nginx:1.27-alpine`,
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
docker compose --env-file .env up -d --wait
docker compose --env-file .env ps         # all healthy
caddy reverse-proxy --from staging.example.com --to localhost:8080   # or a Caddyfile / traefik
```

Verify:

```bash
curl -I https://staging.example.com/healthz        # 200 (web container)
curl https://staging.example.com/api/readiness     # {"status":"ready","database":"ok"}
curl -X POST https://staging.example.com/api/v1/session -H 'Content-Type: application/json' \
     -d '{"station_code":"OB-001","employee_code":"OWNER-1","pin":"<set at provision-time>"}'  # 201 (only if seeded)
```

Create the first owner WITHOUT demo access: set `OPENBUNK_SEED_PIN=<strong pin>` **only for the first
boot**, sign in once as owner, create your own owner user (`/api/v1/employees`), then unset
`OPENBUNK_SEED_PIN` (restart) or offboard EMP-00…04. Never leave demo accounts on a real deployment.

## 4. Deploy + verify health (release procedure)

1. `git fetch && git checkout <release-ref>`
2. **`python -m app.backup create backups/pre-<ref>.json`** (or `docker compose exec api python -m app.backup create /data/pre.json`)
3. `docker compose build && docker compose up -d --wait`
4. Verify: `curl https://<host>/api/readiness` = ready; spot-check `/api/v1/reports/daily-sales?date=<today>`.
5. Rollback: `git checkout <previous-ref> && docker compose build && docker compose up -d --wait`.
   App rollback is safe because released schema is additive-only; if a destructive migration was ever
   applied, restore from the §4.2 backup instead (see §7).

## 5. Apply migrations safely

- Migrations run automatically on container start (`alembic upgrade head`); for planned schema
  changes apply them explicitly first: `docker compose exec api python -m alembic upgrade head`.
- **Backup before any schema change** (mandatory; the compose entrypoint assumes maintenance windows).
- Rollback strategy: `alembic downgrade <revision>` works for the three shipped migrations; for
  anything destructive, restore from backup instead. Never downgrade a production database with live
  writes without an explicit maintenance window and a fresh backup.

## 6. Backup & restore drill (EXECUTED 2026-11-16 against a scratch database)

- Backup: `python -m app.backup create backups/backup-<timestamp>.json` — JSON dump of all tables
  (17 tables / 15 rows on the seeded demo set; contains PIN hashes — treat as a secret).
- Restore: `python -m app.backup restore backups/backup-<timestamp>.json` — wipes + restores.
- Drill result (executed): dump → restore into empty database → station `OB-001`, 5 employees,
  3 nozzles, 2 tanks, 2 products, 2 stock movements, **EMP-01 PIN verifies against restored hash**
  — roundtrip lossless. Repeat this drill on staging before every production migration:
  1. `docker compose exec api python -m app.backup create /data/drill.json`
  2. `docker compose exec db psql -U openbunk -c 'CREATE DATABASE drill OWNER openbunk'` (or a scratch instance)
  3. restore into drill DB, run `pytest` against it or compare row counts (`app.backup` restore prints them)
  4. drop drill DB. Document the output in STATUS.md.
- Schedule: daily `backup` cron (keep 14 dailies + 4 weeklies); store off-host (object storage with
  encryption at rest or an encrypted volume); test restores **quarterly**.

## 7. Roll back application; database rollback strategy

- App rollback: redeploy previous image/tag (§4.5). Stateless containers make this trivial.
- Database rollback: prefer forward-fix. If unavoidable: restore the §4.2 backup with
  `python -m app.backup restore` into an empty maintenance window. This is destructive — it discards
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
  independent of any vendor. Database dumps (`app.backup`) are igualmente portable.
- Decommission: export → stop stack → delete volumes (`docker compose down -v`) → archive encrypted
  backups per retention policy.

## 11. Logs do not contain secrets — verification

Request logging records method/path/status/request_id/elapsed only — never bodies, headers, or query
strings with credentials. Verify with: `docker compose logs api | grep -iE 'pin|password|token|secret'`
(expect no output). Error responses include only `code/message/details/requestId`.
