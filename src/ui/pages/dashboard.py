"""Dashboard page at / with stats, power summary, recent activity, and quick actions."""
import asyncio
from datetime import datetime, timezone

import httpx
from nicegui import app as nicegui_app
from nicegui import ui

from src.ui.components.app_shell import app_shell
from src.ui.components.auth_guard import redirect_if_unauthenticated
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


def _stat_card(label: str, value: str) -> None:
    """Render a single stat card with hover lift animation."""
    with ui.card().classes("p-4 ht-stat-card").style(
        "background:var(--ht-bg-surface-raised); min-width:140px; text-align:center;"
        " border:1px solid var(--ht-border); border-radius:var(--ht-radius-card);"
        " box-shadow:var(--ht-shadow-sm); transition:all var(--ht-transition-norm);"
    ):
        ui.label(value).style(
            "font-size:2rem; font-weight:700; color:var(--ht-text-primary);"
        )
        ui.label(label).style(
            "font-size:0.8rem; color:var(--ht-text-secondary); text-transform:uppercase;"
        )


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
        ui.add_head_html("""
<style>
.ht-stat-card:hover {
    transform: translateY(-1px);
    box-shadow: var(--ht-shadow-md) !important;
}
</style>
""")
        with ui.column().classes("w-full max-w-4xl mx-auto p-6 gap-6"):
            ui.label("Dashboard").style(
                "font-size:1.25rem; font-weight:600; color:var(--ht-text-primary);"
            )

            with ui.row().classes("flex-wrap gap-4"):
                _stat_card("Devices", str(device_count))
                _stat_card("Connections", str(conn_count))
                _stat_card("Locations", str(loc_count))
                _stat_card("Tags", str(tag_count))

            with ui.card().classes("w-full").style(
                "background:var(--ht-bg-surface-raised); border:1px solid var(--ht-border);"
                " border-radius:var(--ht-radius-card); box-shadow:var(--ht-shadow-sm);"
            ):
                with ui.column().classes("p-4 gap-3 w-full"):
                    ui.label("Power Usage").style(
                        "font-size:0.875rem; font-weight:600; color:var(--ht-text-secondary);"
                        " text-transform:uppercase; letter-spacing:0.5px;"
                    )

                    total_watts = _as_int(power_summary.get("total_watts"), 0)
                    ui.label(f"{total_watts}W").style(
                        "font-size:2rem; font-weight:700; color:var(--ht-text-primary);"
                    )

                    monthly_cost = _as_float(power_summary.get("estimated_monthly_cost"))
                    currency = power_summary.get("currency")
                    if monthly_cost is not None and isinstance(currency, str) and currency:
                        ui.label(f"{monthly_cost:.2f} {currency} / month").style(
                            "font-size:0.9rem; color:var(--ht-text-secondary);"
                        )
                    else:
                        ui.label("Rate not configured").style(
                            "font-size:0.9rem; color:var(--ht-text-secondary);"
                        )

                    top_locations = _power_top_locations(power_summary.get("by_location"))
                    if not top_locations:
                        ui.label("No location power data yet").style(
                            "font-size:0.85rem; color:var(--ht-text-secondary);"
                        )
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
                                    ui.label(name).style(
                                        "font-size:0.8rem; color:var(--ht-text-primary);"
                                    )
                                    ui.label(f"{watts}W").style(
                                        "font-size:0.75rem; color:var(--ht-text-secondary);"
                                    )
                                with ui.element("div").style(
                                    "width:100%; height:6px; border-radius:999px;"
                                    " background:var(--ht-bg-surface); overflow:hidden;"
                                ):
                                    ui.element("div").style(
                                        f"height:100%; width:{width}%; background:var(--ht-accent);"
                                    )

            with ui.card().classes("w-full").style(
                "background:var(--ht-bg-surface-raised); border:1px solid var(--ht-border);"
                " border-radius:var(--ht-radius-card); box-shadow:var(--ht-shadow-sm);"
            ):
                with ui.column().classes("p-4 gap-3 w-full"):
                    ui.label("Recent Activity").style(
                        "font-size:0.875rem; font-weight:600; color:var(--ht-text-secondary);"
                        " text-transform:uppercase; letter-spacing:0.5px;"
                    )
                    if not recent_devices:
                        ui.label(
                            "No devices yet — add one from Topology"
                        ).style("color:var(--ht-text-secondary); font-size:0.875rem;")
                    else:
                        for dev in recent_devices:
                            with ui.row().classes("items-center justify-between w-full"):
                                with ui.row().classes("items-center gap-2"):
                                    ui.icon("dns").style(
                                        "color:var(--ht-accent); font-size:1.1rem;"
                                    )
                                    ui.label(dev.get("name", "\u2014")).style(
                                        "color:var(--ht-text-primary); font-size:0.875rem;"
                                    )
                                    ui.label(dev.get("type", "")).style(
                                        "color:var(--ht-text-secondary); font-size:0.75rem;"
                                    )
                                ui.label(
                                    _relative_time(dev.get("updated_at", ""))
                                ).style(
                                    "color:var(--ht-text-secondary); font-size:0.75rem;"
                                )

            with ui.row().classes("gap-3 flex-wrap"):
                ui.button(
                    "Add Device",
                    icon="add",
                    on_click=lambda: ui.navigate.to("/topology"),
                ).style("background:var(--ht-accent); color:var(--ht-text-on-accent);")
                ui.button(
                    "View Inventory",
                    icon="list",
                    on_click=lambda: ui.navigate.to("/inventory"),
                ).props("outlined")
                ui.button(
                    "Manage Locations",
                    icon="location_on",
                    on_click=lambda: ui.navigate.to("/settings/locations"),
                ).props("outlined")
