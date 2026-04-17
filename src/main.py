"""Application entry point.

Imports the FastAPI app, registers NiceGUI pages, and mounts NiceGUI as middleware.
The actual server is started by uvicorn via the Dockerfile CMD.
"""
from nicegui import ui

from src.api.app import app  # noqa: F401 — triggers app creation
from src.ui.pages import login  # noqa: F401 — registers /login page
from src.ui.pages import dashboard  # noqa: F401 — registers / page
from src.ui.pages import topology  # noqa: F401 — registers /topology page
from src.ui.pages import inventory  # noqa: F401 — registers /inventory page
from src.ui.pages import ipam  # noqa: F401 — registers /ipam page
from src.ui.pages import map  # noqa: F401 — registers /map page
from src.ui.pages import device_edit  # noqa: F401 — registers /inventory/edit/{device_id} page
from src.ui.pages import settings_locations  # noqa: F401 — registers /settings/locations page
from src.ui.pages import settings_networks  # noqa: F401 — registers /settings/networks page
from src.ui.pages import settings_power  # noqa: F401 — registers /settings/power page
from src.ui.pages import access_denied  # noqa: F401 — registers /403 page
from src.ui.pages import settings_users  # noqa: F401 — registers /settings/users page
from src.ui.pages import settings_data  # noqa: F401 — registers /settings/data page
from src.ui.pages import settings_profile  # noqa: F401 — registers /settings/profile page
from src.ui.pages import settings_about  # noqa: F401 — registers /settings/about page
from src.ui.pages import workspaces  # noqa: F401 — registers /workspaces page
from src.ui.pages import workspace_detail  # noqa: F401 — registers /workspaces/{id} page
from src.utils.settings import settings

# Mount NiceGUI as ASGI middleware onto the FastAPI app.
# Use a dedicated storage secret to avoid key reuse between JWTs and UI storage.
# If `STORAGE_SECRET` is not provided, derive a distinct value from `SECRET_KEY`.
_storage_secret = settings.storage_secret or (settings.secret_key + "_nicegui_storage")
ui.run_with(app, storage_secret=_storage_secret)
