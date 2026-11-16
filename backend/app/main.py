import uuid
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .errors import api_error_handler, unhandled_error_handler, validation_error_handler, ApiError
from .logging_config import configure_logging, request_id_ctx, get_logger
from .routers import audit, auth, catalog, credit, csv_io, export, health, receipts, reports, sales, shifts, staff, station

settings = get_settings()
configure_logging()
logger = get_logger("openbunk.main")


def create_app() -> FastAPI:
    app = FastAPI(
        title="DeepBNK API",
        version="0.9.1",
        docs_url="/api/docs" if not settings.is_production else None,
        openapi_url="/api/openapi.json" if not settings.is_production else None,
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_ctx.set(request_id)
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-Id"] = request_id
        # baseline security headers (HSTS only behind production TLS)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        if settings.is_production:
            response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
        logger.info("%s %s -> %s (%.2f ms)", request.method, request.url.path, response.status_code, elapsed_ms)
        request_id_ctx.reset(token)
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            "X-Request-Id",
            "X-Reauth-Pin",
            "X-Approval-Code",
            "X-Approval-Pin",
        ],
    )

    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
    from fastapi.exceptions import RequestValidationError

    app.add_exception_handler(RequestValidationError, validation_error_handler)

    app.include_router(health.router)
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(station.router, prefix="/api/v1")
    app.include_router(catalog.router, prefix="/api/v1")
    app.include_router(shifts.router, prefix="/api/v1")
    app.include_router(credit.router, prefix="/api/v1")
    app.include_router(receipts.router, prefix="/api/v1")
    app.include_router(sales.router, prefix="/api/v1")
    app.include_router(reports.router, prefix="/api/v1")
    app.include_router(audit.router, prefix="/api/v1")
    app.include_router(staff.router, prefix="/api/v1")
    app.include_router(export.router, prefix="/api/v1")
    app.include_router(csv_io.router, prefix="/api/v1")

    return app


app = create_app()
