"""Settings — About / system info page at /settings/about (HT-035)."""
import platform
import sys
from typing import Optional

import httpx
from nicegui import app as nicegui_app
from nicegui import ui

from src.__version__ import __version__
from src.ui.components.app_shell import app_shell
from src.ui.components.auth_guard import redirect_if_unauthenticated
from src.utils.logger import logger
from src.utils.settings import settings

_API = settings.api_base_url


def _row(label: str, value: str) -> None:
    with ui.row().classes("justify-between w-full").style("gap: 8px;"):
        ui.label(label).style("color: var(--ht-text-secondary); font-size: 0.875rem;")
        ui.label(value).style("color: var(--ht-text-primary); font-size: 0.875rem;")


def _section(title: str) -> None:
    ui.separator()
    ui.label(title).style(
        "font-size: 0.875rem; font-weight: 600; color: var(--ht-text-secondary); "
        "text-transform: uppercase; letter-spacing: 0.05em;"
    )


@ui.page("/settings/about")
async def settings_about_page() -> None:
    """System info settings page — any authenticated role."""
    if redirect_if_unauthenticated(current_path="/settings/about"):
        return

    token = nicegui_app.storage.user.get("access_token", "")
    headers = {"Authorization": f"Bearer {token}"}

    health: dict = {}
    stats: dict = {}

    try:
        async with httpx.AsyncClient() as c:
            h = await c.get(f"{_API}/api/health", timeout=5.0)
            s = await c.get(
                f"{_API}/api/system/stats", headers=headers, timeout=5.0
            )
        health = h.json() if h.status_code == 200 else {}
        stats = s.json() if s.status_code == 200 else {}
    except httpx.HTTPError as exc:
        logger.error("About page data fetch failed: {}", str(exc))

    with app_shell("About", "/settings/about", breadcrumb=["Settings", "About"]):
        ui.label("About Hometower").style(
            "font-size: 1.5rem; font-weight: 700; color: var(--ht-text-primary);"
        )

        with ui.card().style("background: var(--ht-bg-surface-raised); width: 100%;"):
            with ui.column().classes("w-full").style("gap: 8px;"):
                _section("Application")
                _row("Name", "Hometower")
                _row("Version", __version__)
                _row("Python", f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")

                _section("Runtime")
                uptime = health.get("uptime_seconds")
                _row(
                    "Server Uptime",
                    f"{uptime:.0f}s" if uptime is not None else "—",
                )
                import datetime
                _row("Server Time (UTC)", datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

                _section("Database")
                _row("PostgreSQL Version", stats.get("db_version") or "—")
                size = stats.get("db_size_bytes")
                _row(
                    "Database Size",
                    f"{size / 1024 / 1024:.1f} MB" if size else "—",
                )

                _section("Inventory Summary")
                _row("Devices", str(stats.get("devices", "—")))
                _row("Connections", str(stats.get("connections", "—")))
                _row("Locations", str(stats.get("locations", "—")))
                _row("Tags", str(stats.get("tags", "—")))
                _row("Custom Fields", str(stats.get("custom_fields", "—")))
                _row("Saved Diagrams", str(stats.get("diagrams", "—")))
                users_val = stats.get("users")
                _row("Users", str(users_val) if users_val is not None else "N/A (Admin only)")
