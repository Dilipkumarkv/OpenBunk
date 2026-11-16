import os
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]

# Use a temp SQLite file unless TEST_DATABASE_URL is set (CI: Postgres service)
_tmpdir = tempfile.mkdtemp(prefix="openbunk-test-")
_default_url = f"sqlite:///{Path(_tmpdir) / 'test.db'}"
os.environ.setdefault("DATABASE_URL", _default_url)
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "1000")

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402


def _migrate() -> None:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")


_migrate()

import pytest  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import Base  # noqa: E402
from app.seed import seed  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    with SessionLocal() as db:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
    seed()
    yield


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


@pytest.fixture()
def manager_token(client):
    response = client.post(
        "/api/v1/session",
        json={"station_code": "OB-001", "employee_code": "EMP-01", "pin": "1234"},
    )
    assert response.status_code == 201, response.text
    return response.json()["token"]


@pytest.fixture()
def attendant_token(client):
    response = client.post(
        "/api/v1/session",
        json={"station_code": "OB-001", "employee_code": "EMP-02", "pin": "1234"},
    )
    assert response.status_code == 201, response.text
    return response.json()["token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}
