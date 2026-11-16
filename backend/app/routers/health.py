from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import Depends, status

from ..db import get_db
from ..errors import ApiError

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/readiness")
def readiness(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:  # noqa: BLE001 - map any driver failure to 503 without leaking details
        raise ApiError(status.HTTP_503_SERVICE_UNAVAILABLE, "database not reachable") from e
    return {"status": "ready", "database": "ok"}
