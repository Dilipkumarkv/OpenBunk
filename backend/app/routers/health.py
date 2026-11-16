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


# Proxied copies under /api/v1 so the frontend/reverse-proxy sees every endpoint under one prefix
@router.get("/api/v1/health")
def health_v1():
    return {"status": "ok"}


@router.get("/api/v1/readiness")
def readiness_v1(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:  # noqa: BLE001
        raise ApiError(status.HTTP_503_SERVICE_UNAVAILABLE, "database not reachable") from e
    return {"status": "ready", "database": "ok"}
