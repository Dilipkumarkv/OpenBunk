"""Migration safety: a populated pre-Wave-0 database must upgrade without data loss."""

import os
import sqlite3
import uuid
from pathlib import Path

from alembic import command
from alembic.config import Config

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


def test_populated_database_upgrades_and_downgrades(tmp_path, monkeypatch):
    db_path = tmp_path / "populated.db"
    url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", url)
    cfg = _config()

    command.upgrade(cfg, "a9969610a625")

    station_id = str(uuid.uuid4())
    employee_id = str(uuid.uuid4())
    shift_id = str(uuid.uuid4())
    token_id = str(uuid.uuid4())
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO stations (id, code, name, timezone, currency, business_day_start, active, created_at, updated_at) "
            "VALUES (?, 'OB-001', 'Existing Station', 'Asia/Kolkata', 'INR', '06:00', 1, '2026-01-01', '2026-01-01')",
            (station_id,),
        )
        conn.execute(
            "INSERT INTO employees (id, station_id, code, name, role, pin_hash, active, created_at) "
            "VALUES (?, ?, 'EMP-00', 'Owner', 'owner', '$argon2id$placeholder', 1, '2026-01-01')",
            (employee_id, station_id),
        )
        conn.execute(
            "INSERT INTO session_tokens (id, station_id, employee_id, token_hash, created_at, expires_at, revoked_at) "
            "VALUES (?, ?, ?, 'existing-token-hash', '2026-01-01', '2026-12-31', NULL)",
            (token_id, station_id, employee_id),
        )
        conn.execute(
            "INSERT INTO shifts (id, station_id, employee_id, kind, business_date, status, opened_at, closed_at, closed_by, revenue_total) "
            "VALUES (?, ?, ?, 'morning', '2026-01-01', 'closed', '2026-01-01', '2026-01-01', ?, 100.00)",
            (shift_id, station_id, employee_id, employee_id),
        )
        conn.commit()

    # Existing the exact failure the audit reproduced: NOT NULL column without default.
    command.upgrade(cfg, "head")

    with sqlite3.connect(db_path) as conn:
        kind = conn.execute("SELECT kind FROM session_tokens WHERE id = ?", (token_id,)).fetchone()[0]
        version = conn.execute("SELECT version FROM shifts WHERE id = ?", (shift_id,)).fetchone()[0]
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        request_hash = conn.execute("PRAGMA table_info(idempotency_keys)").fetchall()
    assert kind == "access"
    assert version == 1
    assert {"fuel_prices", "reauth_attempts"} <= tables
    assert any(row[1] == "request_hash" for row in request_hash)

    # Round-trip one revision down and back up.
    command.downgrade(cfg, "c8c8a8abb21c")
    command.upgrade(cfg, "head")
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM shifts").fetchone()[0] == 1
