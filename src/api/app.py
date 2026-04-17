"""FastAPI application factory.

Configures the app with middleware, routers, and a lifespan handler that
runs Alembic migrations and creates the first admin on startup.

NiceGUI is mounted in src/main.py via ui.run_with() — NOT here — so that
the FastAPI app can be imported cleanly by tests without starting a server.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlmodel import Session
from starlette.middleware.cors import CORSMiddleware

from src.api.middleware.auth import AuthMiddleware
from src.api.middleware.rate_limit import limiter
from src.api.middleware.security_headers import SecurityHeadersMiddleware
from src.utils.settings import settings
from src.api.routers.auth import router as auth_router
from src.api.routers.connections import router as connections_router
from src.api.routers.devices import router as devices_router
from src.api.routers.device_attachments import router as device_attachments_router
from src.api.routers.device_sub_routes import router as device_sub_routes_router
from src.api.routers.diagrams import router as diagrams_router
from src.api.routers.health import router as health_router
from src.api.routers.ipam import router as ipam_router
from src.api.routers.locations import router as locations_router
from src.api.routers.networks import router as networks_router
from src.api.routers.power import router as power_router
from src.api.routers.system import router as system_router
from src.api.routers.tags import router as tags_router
from src.api.routers.users import router as users_router
from src.api.routers.data_transfer import router as data_transfer_router
from src.api.routers.services import router as services_router
from src.api.routers.workspaces import router as workspaces_router
from src.api.routers.topologies import (
    nested_router as topologies_nested_router,
    standalone_router as topologies_standalone_router,
)
from src.api.routers.topology_editor import router as topology_editor_router
from src.api.routers.views import router as views_router
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

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_middleware(AuthMiddleware)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.api_base_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)
app.include_router(auth_router, prefix="/api")
app.include_router(devices_router, prefix="/api")
app.include_router(device_attachments_router, prefix="/api")
app.include_router(device_sub_routes_router, prefix="/api")
app.include_router(diagrams_router, prefix="/api")
app.include_router(connections_router, prefix="/api")
app.include_router(health_router, prefix="/api")
app.include_router(ipam_router, prefix="/api")
app.include_router(locations_router, prefix="/api")
app.include_router(networks_router, prefix="/api")
app.include_router(power_router, prefix="/api")
app.include_router(system_router, prefix="/api")
app.include_router(tags_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(data_transfer_router, prefix="/api")
app.include_router(services_router, prefix="/api")
app.include_router(workspaces_router, prefix="/api")
app.include_router(topologies_nested_router, prefix="/api")
app.include_router(topologies_standalone_router, prefix="/api")
app.include_router(topology_editor_router, prefix="/api")
app.include_router(views_router, prefix="/api")



