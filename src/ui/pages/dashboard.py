"""Dashboard page at / backed by the HT-082 aggregate summary endpoint."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
from nicegui import app as nicegui_app
from nicegui import ui

from src.models.types import Role
from src.ui.components.app_shell import app_shell
from src.ui.components.auth_guard import get_ui_role, redirect_if_unauthenticated
from src.ui.components.dashboard_sections import render_dashboard_breakdown_card
from src.ui.components.dashboard_sections import render_dashboard_power_card
from src.ui.components.dashboard_sections import render_dashboard_primary_actions
from src.ui.components.dashboard_sections import render_dashboard_recent_activity_card
from src.ui.components.dashboard_sections import render_dashboard_summary_cards
from src.ui.design.primitives import page_container
from src.ui.design.primitives import render_page_intro
from src.utils.logger import logger
from src.utils.settings import settings


def _default_summary() -> dict[str, object]:
    return {
        "devices": 0,
        "workspaces": 0,
        "topologies": 0,
        "offline_devices": 0,
        "recent_edits": 0,
        "power": {
            "workspace_options": [{"id": None, "name": "All Workspaces"}],
            "selected_workspace_id": None,
            "selected_workspace_name": "All Workspaces",
            "total_watts": 0,
            "estimated_monthly_cost": None,
            "currency": None,
        },
        "inventory_breakdown": {"status_counts": [], "type_counts": []},
        "recent_activity": [],
    }


def _relative_time(value: object) -> str:
    raw = str(value or "")
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return raw
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


async def _load_dashboard_summary(
    headers: dict[str, str],
    workspace_id: str | None = None,
) -> dict[str, object]:
    params = {"workspace_id": workspace_id} if workspace_id else None
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.api_base_url}/api/dashboard/summary",
                headers=headers,
                params=params,
            )
    except Exception as exc:
        logger.error("Dashboard summary fetch failed: {}", str(exc))
        return _default_summary()

    if response.status_code != 200:
        logger.error("Dashboard summary request failed: status={}", response.status_code)
        return _default_summary()

    payload = response.json()
    return payload if isinstance(payload, dict) else _default_summary()


def _scope_value(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _selected_workspace_id(summary: dict[str, object], fallback: str | None = None) -> str | None:
    power = summary.get("power", {})
    if not isinstance(power, dict):
        return fallback
    return _scope_value(str(power.get("selected_workspace_id") or "")) or fallback


def _inventory_route(workspace_id: str | None) -> str:
    return f"/inventory?workspace_id={workspace_id}" if workspace_id else "/inventory"


def _dashboard_history_js(workspace_id: str | None) -> str:
    return f"""
    (() => {{
        const current = new URL(window.location.href);
        const nextValue = {json.dumps(workspace_id or "")};
        if (nextValue) {{
            current.searchParams.set('workspace_id', nextValue);
        }} else {{
            current.searchParams.delete('workspace_id');
        }}
        window.history.replaceState(
            window.history.state ?? null,
            '',
            `${{current.pathname}}${{current.search}}${{current.hash}}`,
        );
    }})()
    """.strip()


@ui.page("/")
async def dashboard_page(workspace_id: str | None = None) -> None:
    """Dashboard — auth-gated control room backed by /api/dashboard/summary."""
    if redirect_if_unauthenticated(current_path="/"):
        return

    token = str(nicegui_app.storage.user.get("access_token", ""))
    role = get_ui_role()
    can_write = role in {Role.Admin, Role.Contributor}
    headers = {"Authorization": f"Bearer {token}"}
    selected_workspace_id = _scope_value(workspace_id)
    summary = await _load_dashboard_summary(headers, selected_workspace_id)

    def _render_scoped_content(content_summary: dict[str, object]) -> None:
        power = content_summary.get("power", {})
        power = power if isinstance(power, dict) else {}
        breakdown = content_summary.get("inventory_breakdown", {})
        breakdown = breakdown if isinstance(breakdown, dict) else {}
        recent_activity = content_summary.get("recent_activity", [])
        recent_activity = recent_activity if isinstance(recent_activity, list) else []
        scoped_workspace_id = _selected_workspace_id(content_summary, selected_workspace_id)
        inventory_route = _inventory_route(scoped_workspace_id)

        render_dashboard_summary_cards(ui, content_summary)
        with ui.row().classes("w-full gap-4 flex-wrap items-stretch"):
            render_dashboard_power_card(ui, power, _refresh_dashboard)
            render_dashboard_breakdown_card(ui, breakdown, scoped_workspace_id)
        render_dashboard_recent_activity_card(ui, recent_activity, _relative_time, scoped_workspace_id)
        render_dashboard_primary_actions(ui, can_write=can_write, inventory_route=inventory_route)

    with app_shell("Dashboard", "/", breadcrumb=["Dashboard"]):
        with page_container(ui.column()):
            render_page_intro(
                ui,
                "Dashboard",
                "One pass across inventory, power, and recent topology changes for the current workspace scope.",
                "Operations",
            )
            content = ui.column().classes("w-full gap-4")

            async def _refresh_dashboard(workspace_id: str | None) -> None:
                refreshed_summary = await _load_dashboard_summary(headers, workspace_id)
                await ui.run_javascript(
                    _dashboard_history_js(_selected_workspace_id(refreshed_summary, workspace_id))
                )
                content.clear()
                with content:
                    _render_scoped_content(refreshed_summary)

            with content:
                _render_scoped_content(summary)
