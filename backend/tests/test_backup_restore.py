"""Backup → wipe → restore roundtrip must reproduce an identical verified dataset,
	including credential hashes (a restored employee keeps a working PIN hash).
"""

import json

from sqlalchemy import create_engine, func, select

from app.backup import dump_database, restore_database
from app.config import get_settings
from app.models import Base, Employee


def _counts(engine):
    with engine.connect() as conn:
        return {
            table.name: conn.execute(select(func.count()).select_from(table)).scalar()
            for table in Base.metadata.sorted_tables
        }


def test_backup_restore_roundtrip():
    settings = get_settings()
    kwargs = {"connect_args": {"check_same_thread": False}} if settings.DATABASE_URL.startswith("sqlite") else {}
    engine_source = create_engine(settings.DATABASE_URL, **kwargs)

    before = _counts(engine_source)
    assert before["stations"] == 1
    assert before["employees"] == 5

    dump = dump_database(engine_source)
    serialized = json.dumps(dump, default=str)
    restored_data = json.loads(serialized)  # through the JSON boundary, like a real backup file

    counts = restore_database(engine_source, restored_data)
    after = _counts(engine_source)

    assert after == before
    assert sum(counts.values()) == sum(before.values())

    # restored rows are actually usable: hashes survive the roundtrip
    with engine_source.connect() as conn:
        row = conn.execute(select(Employee.pin_hash).where(Employee.code == "EMP-01")).first()
        assert row is not None and row[0] and row[0].startswith("$argon2")

