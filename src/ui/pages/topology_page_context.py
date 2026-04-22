"""Helper functions for topology page orchestration."""

import json
from dataclasses import dataclass

from fastapi import Request
from nicegui import ui

from src.models.types import Role
from src.ui.components.breadcrumb import render_breadcrumb
from src.ui.pages.topology_page_support import (
    _FOCUS_DEVICE_JS_TEMPLATE,
    _fetch_stencil_devices,
    _resolve_topology_id_from_layout,
)
from src.ui.services.topology_layout import fetch_breadcrumb_names


@dataclass(frozen=True)
class TopologyPageRouteContext:
    topology_id: str
    workspace_name: str
    topology_name: str


@dataclass(frozen=True)
class TopologySavedLayoutContext:
    current_diagram_id: str = ""
    current_diagram_version: int | None = None
    draft_version: int | None = None
    has_unsaved_changes: bool = False
    restore_summary: dict[str, object] | None = None


def build_topology_current_path(request: Request) -> str:
    """Rebuild the current topology URL path including its query string."""
    current_path = getattr(request.url, "path", "") or "/topology"
    current_query = str(getattr(request.url, "query", "") or "")
    if current_query:
        return f"{current_path}?{current_query}"
    return current_path


def _coerce_optional_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


async def resolve_topology_page_route_context(
    token: str,
    layout_id: str,
    topology_id: str,
    workspace_id: str,
) -> TopologyPageRouteContext:
    """Resolve the topology id and breadcrumb labels for page entry."""
    resolved_topology_id = topology_id
    if not resolved_topology_id and layout_id:
        resolved_topology_id = await _resolve_topology_id_from_layout(token, layout_id)

    workspace_name = ""
    topology_name = ""
    if workspace_id and resolved_topology_id:
        headers = {"Authorization": f"Bearer {token}"}
        workspace_name, topology_name = await fetch_breadcrumb_names(
            workspace_id,
            resolved_topology_id,
            headers,
        )

    return TopologyPageRouteContext(
        topology_id=resolved_topology_id,
        workspace_name=workspace_name,
        topology_name=topology_name,
    )


def parse_saved_layout_context(saved_layout: object) -> TopologySavedLayoutContext:
    """Normalize saved layout metadata used by topology page bootstrapping."""
    if not isinstance(saved_layout, dict):
        return TopologySavedLayoutContext()

    raw_diagram_id = saved_layout.get("_current_diagram_id")
    raw_restore_summary = saved_layout.get("restore_summary")
    return TopologySavedLayoutContext(
        current_diagram_id=str(raw_diagram_id) if raw_diagram_id else "",
        current_diagram_version=_coerce_optional_int(saved_layout.get("_current_diagram_version")),
        draft_version=_coerce_optional_int(saved_layout.get("_draft_version")),
        has_unsaved_changes=bool(saved_layout.get("_has_unsaved_changes")),
        restore_summary=raw_restore_summary if isinstance(raw_restore_summary, dict) else None,
    )


async def load_stencil_devices_for_role(
    token: str,
    role: Role | None,
) -> list[dict[str, str | int]]:
    """Fetch stencil inventory only for editing roles."""
    if role == Role.Reader:
        return []
    return await _fetch_stencil_devices(token)


def render_topology_breadcrumb(
    workspace_name: str,
    topology_name: str,
    workspace_id: str,
) -> None:
    """Render breadcrumb only when both workspace and topology names are known."""
    if workspace_name and topology_name:
        render_breadcrumb([
            ("Workspaces", "/workspaces"),
            (workspace_name, f"/workspaces/{workspace_id}"),
            (topology_name, ""),
        ], use_leave_guard=True)


def inject_focus_device_script(device_id: str) -> None:
    """Queue the deep-link focus script when a device id is provided."""
    if not device_id:
        return
    focus_js = _FOCUS_DEVICE_JS_TEMPLATE.replace(
        "__HT_DEVICE_ID__",
        json.dumps(device_id),
    )
    ui.add_body_html(f"<script>{focus_js}</script>")