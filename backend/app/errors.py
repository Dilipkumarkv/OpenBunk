"""Consistent structured error responses.

Every error body has the shape:
  {"error": {"code": str, "message": str, "details": [...], "requestId": str}}
"""

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .logging_config import get_logger, request_id_ctx

logger = get_logger("openbunk.errors")

_STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "validation_failed",
    429: "rate_limited",
}


class ApiError(Exception):
    def __init__(self, status_code: int, message: str, details: Any = None, code: str | None = None):
        self.status_code = status_code
        self.message = message
        self.details = details
        self.code = code or _STATUS_CODES.get(status_code, "error")


def _body(code: str, message: str, details: Any) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details if details is not None else [],
            "requestId": request_id_ctx.get(),
        }
    }


async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=_body(exc.code, exc.message, exc.details))


async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = [{"loc": list(e.get("loc", [])), "msg": e.get("msg", "")} for e in exc.errors()]
    return JSONResponse(status_code=422, content=_body("validation_failed", "Request validation failed", details))


async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error: %s", exc.__class__.__name__)
    return JSONResponse(status_code=500, content=_body("internal_error", "Internal server error", []))
