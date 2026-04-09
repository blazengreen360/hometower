"""Application entry point.

Imports the FastAPI app, registers NiceGUI pages, and mounts NiceGUI as middleware.
The actual server is started by uvicorn via the Dockerfile CMD.
"""
from nicegui import ui

from src.api.app import app  # noqa: F401 — triggers app creation
from src.ui.pages import login  # noqa: F401 — registers /login page
from src.ui.pages import topology  # noqa: F401 — registers /topology page
from src.utils.settings import settings

# Mount NiceGUI as ASGI middleware onto the FastAPI app.
# The server itself is started by uvicorn via Dockerfile CMD.
ui.run_with(app, storage_secret=settings.secret_key)
