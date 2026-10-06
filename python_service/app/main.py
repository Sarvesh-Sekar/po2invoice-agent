"""FastAPI application entrypoint.

Lifecycle: configure logging -> configure the async engine -> create tables
-> build the DI container -> compile both LangGraphs exactly once.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config.logging import configure_logging, get_logger
from app.config.settings import Settings, get_settings
from app.containers import AppContainer
from app.exceptions.base import BaseAppError
from app.repositories import database
from app.routers import agent_router, internal_router
from app.seed import seed_field_definitions

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    configure_logging(settings.log_level, settings.log_format)
    logger.info(
        "app_starting: name=%s | version=%s | environment=%s | log_level=%s | log_format=%s",
        settings.app_name,
        settings.app_version,
        settings.environment,
        settings.log_level.upper(),
        settings.log_format,
    )

    # Tests may inject a pre-built container (engine already configured).
    container = getattr(app.state, "container", None)
    if container is None:
        database.configure_engine(settings.database_url, echo=settings.db_echo)
        await database.create_all()
        await seed_field_definitions(database.get_session_factory())
        container = AppContainer(settings)
        app.state.container = container

    await container.startup()
    logger.info("app_started: graphs_compiled=po,invoice")
    yield

    await container.shutdown()
    await database.dispose()
    logger.info("app_stopped: name=%s", settings.app_name)


origins = [
    "http://localhost:5173",  # Popular React/Next.js local port
    "http://localhost:8080",  # Popular Vue/Vite local port
    "https://yourfrontend.com",  # Production domain
]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,  # Allows requests from these domains
        allow_credentials=True,  # Allows cookies and credentials (e.g. Authorization headers)
        allow_methods=["*"],  # Allows all standard HTTP methods (GET, POST, etc.)
        allow_headers=["*"],  # Allows all HTTP headers
    )

    app.include_router(agent_router.router, prefix=settings.api_prefix)
    app.include_router(internal_router.router, prefix=settings.api_prefix)

    @app.exception_handler(BaseAppError)
    async def _app_error_handler(request: Request, exc: BaseAppError) -> JSONResponse:
        log = logger.warning if exc.status_code < 500 else logger.error
        log(
            "request_failed: code=%s | category=%s | status=%s | method=%s | path=%s | message=%s",
            exc.code,
            exc.category.value,
            exc.status_code,
            request.method,
            request.url.path,
            exc.message,
        )
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = sorted({str(err.get("loc", [""])[-1]) for err in exc.errors()})
        logger.warning(
            "request_invalid: method=%s | path=%s | fields=%s",
            request.method,
            request.url.path,
            fields,
        )
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": exc.errors()[:10],
                },
            },
        )

    @app.exception_handler(Exception)
    async def _unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "request_crashed: method=%s | path=%s | error=%s: %s",
            request.method,
            request.url.path,
            type(exc).__name__,
            exc,
        )
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                },
            },
        )

    @app.get("/health", tags=["health"])
    async def health() -> dict:
        return {"status": "ok", "service": settings.app_name, "version": settings.app_version}

    return app


app = create_app()
