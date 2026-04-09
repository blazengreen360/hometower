"""FastAPI application factory.

Configures the app with middleware, routers, and a lifespan handler that
runs Alembic migrations and creates the first admin on startup.

NiceGUI is mounted in src/main.py via ui.run_with() — NOT here — so that
the FastAPI app can be imported cleanly by tests without starting a server.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from sqlmodel import Session

from src.api.middleware.auth import AuthMiddleware
from src.api.routers.auth import router as auth_router
from src.api.routers.connections import router as connections_router
from src.api.routers.devices import router as devices_router
from src.api.routers.diagrams import router as diagrams_router
from src.services.auth_service import create_first_admin_if_needed
from src.utils.db import engine
from src.utils.logger import logger


def run_migrations() -> None:
    """Apply any pending Alembic migrations against the live database."""
    from alembic import command as alembic_command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    alembic_command.upgrade(cfg, "head")
    logger.info("Database migrations complete")


def _startup() -> None:
    """Synchronous startup routine called by the lifespan handler."""
    run_migrations()
    with Session(engine) as session:
        create_first_admin_if_needed(session)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Hometower starting up")
    _startup()
    yield
    logger.info("Hometower shut down")


app = FastAPI(
    title="Hometower API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(AuthMiddleware)
app.include_router(auth_router, prefix="/api")
app.include_router(devices_router, prefix="/api")
app.include_router(diagrams_router, prefix="/api")
app.include_router(connections_router, prefix="/api")


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check — excluded from JWT middleware."""
    return {"status": "ok"}
