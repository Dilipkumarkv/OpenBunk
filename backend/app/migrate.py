"""Run Alembic migrations with a Postgres advisory lock.

Multiple API/worker containers may start at once. Every process waits on the
same advisory lock before running migrations, so only one migrates at a time.
SQLite (single-node dev) needs no lock.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from .config import get_settings

LOCK_ID = 727274  # arbitrary, stable application-wide migration lock


def run() -> None:
    settings = get_settings()
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    if settings.DATABASE_URL.startswith("sqlite"):
        command.upgrade(config, "head")
        return

    with engine.connect() as conn:
        conn.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": LOCK_ID})
        try:
            command.upgrade(config, "head")
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": LOCK_ID})


if __name__ == "__main__":
    run()
