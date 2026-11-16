"""JSON backup/restore of every table.

Backup files contain credential hashes (employee pin_hash, session tokens).
Treat them as confidential secrets. Restore replaces ALL data in the target DB.

CLI:
  python -m app.backup create  backup.json
  python -m app.backup restore backup.json
Reads DATABASE_URL from the environment (or .env).
"""

import datetime
import json
import sys
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, JSON, Numeric, Uuid, create_engine, inspect
from sqlalchemy.orm import Session

from .config import get_settings
from .models import Base

FORMAT = "openbunk-backup@1"


def _jsonable(value):
    if value is None:
        return None
    if isinstance(value, (datetime.datetime, datetime.date, Decimal, UUID)):
        return str(value)
    return value


def dump_database(engine) -> dict:
    tables: dict[str, list[dict]] = {}
    with engine.connect() as conn:
        for table in Base.metadata.sorted_tables:
            rows = conn.execute(table.select()).mappings().all()
            tables[table.name] = [
                {column.name: _jsonable(row[column.name]) for column in table.columns} for row in rows
            ]
    return {"format": FORMAT, "tables": tables}


def _parse_value(column, value):
    if value is None:
        return None
    col_type = column.type
    if isinstance(col_type, DateTime):
        return datetime.datetime.fromisoformat(value) if isinstance(value, str) else value
    if isinstance(col_type, Date):
        return datetime.date.fromisoformat(value) if isinstance(value, str) else value
    if isinstance(col_type, Numeric):
        return Decimal(str(value))
    if isinstance(col_type, Boolean):
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes")
        return bool(value)
    if isinstance(col_type, Uuid):
        return UUID(str(value))
    if isinstance(col_type, JSON):
        return value
    return value


def restore_database(engine, data: dict) -> dict:
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ValueError(f"unsupported backup format (expected {FORMAT})")
    counts: dict[str, int] = {}
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
        for table in Base.metadata.sorted_tables:
            rows = data.get("tables", {}).get(table.name, [])
            for row in rows:
                values = {
                    column.name: _parse_value(column, row[column.name])
                    for column in table.columns
                    if column.name in row
                }
                if values:
                    conn.execute(table.insert().values(**values))
            counts[table.name] = len(rows)
    return counts


def _engine():
    settings = get_settings()
    kwargs = {"connect_args": {"check_same_thread": False}} if settings.DATABASE_URL.startswith("sqlite") else {}
    return create_engine(settings.DATABASE_URL, **kwargs)


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] not in ("create", "restore"):
        print(__doc__)
        return 2
    command, path = argv
    engine = _engine()
    if command == "create":
        dump = dump_database(engine)
        Path(path).write_text(json.dumps(dump, indent=2, default=str), encoding="utf-8")
        total = sum(len(v) for v in dump["tables"].values())
        print(f"Backup written to {path}: {len(dump['tables'])} tables, {total} rows.")
        return 0
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    counts = restore_database(engine, data)
    print(f"Restored {sum(counts.values())} rows across {len(counts)} tables from {path}.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
