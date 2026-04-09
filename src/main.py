"""Application entry point.

Imports the FastAPI app (which configures routes and middleware) then mounts
NiceGUI and starts the uvicorn server via ui.run_with().
"""
from nicegui import ui

from src.api.app import app  # noqa: F401 — triggers app creation
from src.ui.pages import login  # noqa: F401 — registers /login page
from src.utils.settings import settings

ui.run_with(  # type: ignore[call-arg]
    app,
    host="0.0.0.0",
    port=8080,
    storage_secret=settings.secret_key,
)
