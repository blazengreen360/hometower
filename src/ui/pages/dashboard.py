"""Dashboard page at / with stats, power summary, recent activity, and quick actions."""
import asyncio
from datetime import datetime, timezone

import httpx
from nicegui import app as nicegui_app
from nicegui import ui

from src.models.types import Role
from src.ui.components.app_shell import app_shell
from src.ui.components.auth_guard import get_ui_role, redirect_if_unauthenticated
from src.ui.design.primitives import card_section
from src.ui.design.primitives import card_surface
from src.ui.design.primitives import page_container
from src.ui.design.primitives import primary_button
from src.ui.design.primitives import render_page_intro
from src.ui.design.primitives import render_stat_card
from src.ui.design.primitives import secondary_button
from src.utils.logger import logger
from src.utils.settings import settings


def _relative_time(iso: str) -> str:
    """Return a human-readable relative time string from an ISO timestamp."""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    diff = int((datetime.now(timezone.utc) - dt).total_seconds())
    if diff < 60:
        return "just now"
    if diff < 3600:
        return f"{diff // 60}m ago"
    if diff < 86400:
        return f"{diff // 3600}h ago"
    return f"{diff // 86400}d ago"


def _as_int(value: object, default: int = 0) -> int:
    return value if isinstance(value, int) else default


def _as_float(value: object) -> float | None:
    if isinstance(value, float):
        return value
    if isinstance(value, int):
        return float(value)
    return None


def _power_top_locations(by_location: object) -> list[dict[str, object]]:
    if not isinstance(by_location, list):
        return []
    normalized = [row for row in by_location if isinstance(row, dict)]
    root_rows = [row for row in normalized if row.get("parent_location_id") is None]
    source = root_rows if root_rows else normalized
    return source[:5]


@ui.page("/")
async def dashboard_page() -> None:
    """Dashboard — requires auth, shows summary stats and recent activity."""
    if redirect_if_unauthenticated(current_path="/"):
        return

    token: str = nicegui_app.storage.user.get("access_token", "")
    role = get_ui_role()
    can_write = role in {Role.Admin, Role.Contributor}
    headers = {"Authorization": f"Bearer {token}"}
    base = settings.api_base_url

    device_count = 0
    conn_count = 0
    loc_count = 0
    tag_count = 0
    recent_devices: list[dict] = []
    power_summary: dict[str, object] = {
        "total_watts": 0,
        "estimated_monthly_cost": None,
        "currency": None,
        "by_location": [],
    }

    try:
        async with httpx.AsyncClient() as client:
            results = await asyncio.gather(
                client.get(f"{base}/api/devices/", params={"limit": 1}, headers=headers),
                client.get(f"{base}/api/connections/", params={"limit": 1}, headers=headers),
                client.get(f"{base}/api/locations/", headers=headers),
                client.get(f"{base}/api/tags/", headers=headers),
                client.get(
                    f"{base}/api/devices/",
                    params={"sort": "-updated_at", "limit": 5},
                    headers=headers,
                ),
                client.get(f"{base}/api/power/summary", headers=headers),
                return_exceptions=True,
            )
        dev_resp, conn_resp, loc_resp, tag_resp, recent_resp, power_resp = results

        if isinstance(dev_resp, httpx.Response) and dev_resp.status_code == 200:
            device_count = dev_resp.json().get("total", 0)
        if isinstance(conn_resp, httpx.Response) and conn_resp.status_code == 200:
            conn_count = conn_resp.json().get("total", 0)
        if isinstance(loc_resp, httpx.Response) and loc_resp.status_code == 200:
            loc_count = len(loc_resp.json())
        if isinstance(tag_resp, httpx.Response) and tag_resp.status_code == 200:
            tag_count = len(tag_resp.json())
        if isinstance(recent_resp, httpx.Response) and recent_resp.status_code == 200:
            recent_devices = recent_resp.json().get("items", [])
        if isinstance(power_resp, httpx.Response) and power_resp.status_code == 200:
            payload = power_resp.json()
            if isinstance(payload, dict):
                power_summary = payload
    except Exception as exc:
        logger.error("Dashboard data fetch failed: {}", str(exc))

    with app_shell("Dashboard", "/", breadcrumb=["Dashboard"]):
        with page_container(ui.column()):
            render_page_intro(
                ui,
                "Dashboard",
                "A control-room view of your homelab: inventory scale, recent changes, and power load in one pass.",
                "Operations",
            )

            with ui.row().classes("flex-wrap gap-4"):
                render_stat_card(ui, "Devices", str(device_count))
                render_stat_card(ui, "Connections", str(conn_count))
                render_stat_card(ui, "Locations", str(loc_count))
                render_stat_card(ui, "Tags", str(tag_count))

            with card_surface(ui.card()):
                with card_section(ui.column()):
                    ui.label("Power Usage").classes("ht-section-caption")

                    total_watts = _as_int(power_summary.get("total_watts"), 0)
                    ui.label(f"{total_watts}W").classes("ht-page-title")

                    monthly_cost = _as_float(power_summary.get("estimated_monthly_cost"))
                    currency = power_summary.get("currency")
                    if monthly_cost is not None and isinstance(currency, str) and currency:
                        ui.label(f"{monthly_cost:.2f} {currency} / month").classes("ht-muted-copy")
                    else:
                        ui.label("Rate not configured").classes("ht-muted-copy")

                    top_locations = _power_top_locations(power_summary.get("by_location"))
                    if not top_locations:
                        ui.label("No location power data yet").classes("ht-small-copy")
                    else:
                        max_watts = max(
                            _as_int(row.get("total_watts"), 0)
                            for row in top_locations
                        )
                        for row in top_locations:
                            name_raw = row.get("location_name")
                            name = str(name_raw) if name_raw is not None else "Location"
                            watts = _as_int(row.get("total_watts"), 0)
                            width = 0 if max_watts <= 0 else max(4, int((watts / max_watts) * 100))

                            with ui.column().classes("w-full gap-1"):
                                with ui.row().classes("w-full items-center justify-between"):
                                    ui.label(name).classes("text-[var(--ht-text-primary)] text-[0.82rem]")
                                    ui.label(f"{watts}W").classes("ht-small-copy")
                                with ui.element("div").classes("ht-progress-track"):
                                    ui.element("div").classes("ht-progress-bar").style(
                                        f"width:{width}%;"
                                    )

            with card_surface(ui.card()):
                with card_section(ui.column()):
                    ui.label("Recent Activity").classes("ht-section-caption")
                    if not recent_devices:
                        ui.label("No devices yet — add one from Topology").classes("ht-muted-copy")
                    else:
                        for dev in recent_devices:
                            with ui.row().classes("items-center justify-between w-full"):
                                with ui.row().classes("items-center gap-2"):
                                    ui.icon("dns").classes("text-[var(--ht-accent)] text-[1.1rem]")
                                    ui.label(dev.get("name", "\u2014")).classes("text-[var(--ht-text-primary)]")
                                    ui.label(dev.get("type", "")).classes("ht-small-copy")
                                ui.label(_relative_time(dev.get("updated_at", ""))).classes("ht-small-copy")

            with ui.row().classes("gap-3 flex-wrap"):
                if can_write:
                    primary_button(ui.button(
                        "Add Device",
                        icon="add",
                        on_click=lambda: ui.navigate.to("/topology"),
                    ))
                secondary_button(ui.button(
                    "View Inventory",
                    icon="list",
                    on_click=lambda: ui.navigate.to("/inventory"),
                ))
                if can_write:
                    secondary_button(ui.button(
                        "Manage Locations",
                        icon="location_on",
                        on_click=lambda: ui.navigate.to("/settings/locations"),
                    ))
