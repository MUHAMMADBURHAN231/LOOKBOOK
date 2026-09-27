"""LOOKBOOK API gateway."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import health
from app.api.v1 import account, auth, catalog, live, looks, media, stylist, tryon
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.middleware import CsrfMiddleware, HttpsAndHeadersMiddleware, RequestContextMiddleware

log = logging.getLogger("lookbook")


@asynccontextmanager
async def lifespan(_: FastAPI):
    s = get_settings()
    log.info("LOOKBOOK API starting (env=%s, storage=%s, mock=%s)", s.environment, s.storage_backend, s.use_mock)
    yield


def create_app() -> FastAPI:
    s = get_settings()
    configure_logging(s.log_level, s.json_logs)
    app = FastAPI(
        title="LOOKBOOK API",
        version="1.0.0",
        lifespan=lifespan,
        # Interactive docs only outside production (they'd expose the full attack surface).
        docs_url=None if s.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if s.is_production else "/openapi.json",
    )

    # Order: last added runs first. Request context wraps everything so every log line has an ID.
    app.add_middleware(CsrfMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token", "X-Lookbook-Key", "X-Lookbook-Host", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Retry-After"],
        max_age=600,
    )
    app.add_middleware(HttpsAndHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        # Echo field locations and messages only, never the submitted values (could be passwords).
        errors = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
        first = errors[0]["message"].removeprefix("Value error, ") if errors else "Invalid request."
        return JSONResponse({"detail": first, "errors": errors}, status_code=422)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("Unhandled error: %s", type(exc).__name__)
        return JSONResponse({"detail": "Something went wrong on our side."}, status_code=500)

    app.include_router(health.router)
    for module in (auth, media, tryon, stylist, catalog, looks, live, account):
        app.include_router(module.router, prefix="/api/v1")
    return app


app = create_app()
