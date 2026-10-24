"""Сборка приложения. Вынесена в функцию, чтобы тесты могли подставлять свои настройки и базу."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.engine import Engine

from app import __version__
from app import models  # noqa: F401  (регистрирует таблицы)
from app.api import admin, cars, health, sources
from app.config import Settings, get_settings
from app.database import Base, make_engine, make_session_factory
from app.importers.registry import build_importers
from app.importers.runner import sync_sources
from app.logging_config import setup_logging

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    engine: Engine | None = None,
    configure_logging: bool = True,
) -> FastAPI:
    settings = settings or get_settings()
    if configure_logging:
        setup_logging(settings.log_level)

    engine = engine or make_engine(settings.sqlalchemy_url)
    session_factory = make_session_factory(engine)
    importers = build_importers(settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        Base.metadata.create_all(engine)
        with session_factory() as db:
            sync_sources(db, importers)
        logger.info("Сервер запущен: %s v%s", settings.app_name, __version__)
        yield
        engine.dispose()
        logger.info("Сервер остановлен")

    app = FastAPI(title=settings.app_name, version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.importers = importers

    if settings.cors_origins_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins_list,
            allow_methods=["GET"],
            allow_headers=["*"],
        )

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "Необработанная ошибка: %s %s", request.method, request.url.path, exc_info=exc
        )
        return JSONResponse(status_code=500, content={"detail": "Внутренняя ошибка сервера."})

    @app.get("/", include_in_schema=False)
    def root() -> dict:
        return {
            "name": settings.app_name,
            "version": __version__,
            "docs": "/docs",
            "health": "/health",
        }

    app.include_router(health.router)
    app.include_router(cars.router)
    app.include_router(sources.router)
    app.include_router(admin.router)
    return app