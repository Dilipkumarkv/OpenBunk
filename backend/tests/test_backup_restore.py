"""Native backup → mutate → verified restore roundtrip (SQLite; CI also uses Postgres)."""

import pytest
from sqlalchemy import inspect, text

from app.backup import create_backup, restore_backup
from app.db import engine


def _counts():
    with engine.connect() as conn:
        return {
            table: conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar()
            for table in inspect(engine).get_table_names()
        }


def test_backup_restore_roundtrip(tmp_path):
    before = _counts()
    assert before["stations"] == 1
    assert before["employees"] == 5

    path = tmp_path / "openbunk.dump"
    manifest = create_backup(engine, path)
    assert manifest["sha256"]
    assert manifest["row_counts"] == before
    assert (tmp_path / "openbunk.dump.manifest.json").exists()

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM audit_events"))

    result = restore_backup(engine, path, force=True)
    assert _counts() == before
    assert result["row_counts"] == before


def test_restore_requires_force(tmp_path):
    path = tmp_path / "forced.dump"
    create_backup(engine, path)
    with pytest.raises(ValueError, match="--force"):
        restore_backup(engine, path)


def test_restore_rejects_corrupted_backup(tmp_path):
    path = tmp_path / "corrupt.dump"
    create_backup(engine, path)
    with path.open("ab") as handle:
        handle.write(b"tampered")
    with pytest.raises(ValueError, match="checksum"):
        restore_backup(engine, path, force=True)
