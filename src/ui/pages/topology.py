"""Topology page — NiceGUI page at /topology."""
import json

from nicegui import app as nicegui_app
from nicegui import ui

from src.models.types import Role
from src.ui.components.app_shell import app_shell
from src.ui.components.auth_guard import get_ui_role, redirect_if_unauthenticated
from src.ui.components.breadcrumb import render_breadcrumb
from src.ui.components.canvas import render_canvas
from src.ui.components.canvas_context_menu import CONTEXT_MENU_JS
from src.ui.components.canvas_mode import EDIT_MODE_JS, VIEW_MODE_JS
from src.ui.components.canvas_network_overlay import inject_network_overlay
from src.ui.components.canvas_shortcuts import inject_canvas_shortcuts
from src.ui.components.canvas_undo_handlers import register_canvas_undo_handlers
from src.ui.components.canvas_zoom import inject_zoom_controls
from src.ui.components.connection_detail_panel import render_connection_detail_panel
from src.ui.components.device_detail_panel import render_detail_panel
from src.ui.components.device_palette import render_palette
from src.ui.components.ghost_detail_panel import render_ghost_detail_panel
from src.ui.components.stencils_panel import compute_placed_ids, render_stencils_panel
from src.ui.components.topology_network_panel import render_network_filter_panel
from src.ui.components.topology_restore_summary import render_restore_summary_banner
from src.ui.components.topology_leave_guard import inject_topology_leave_guard
from src.ui.pages.topology_page_support import (
    _FOCUS_DEVICE_JS_TEMPLATE,
    _fetch_stencil_devices,
    _render_header_actions,
    _resolve_topology_id_from_layout,
)
from src.ui.services.topology_data import load_canvas_data, load_network_summaries
from src.ui.services.topology_layout import fetch_breadcrumb_names

@ui.page("/topology")
async def topology_page(
    device_id: str = "",
    layout_id: str = "",
    topology_id: str = "",
    workspace_id: str = "",
) -> None:
    """Topology page — requires auth, renders the full canvas view."""
    if redirect_if_unauthenticated(current_path="/topology"):
        return

    role = get_ui_role()
    user_role: str = role.value if role else Role.Reader.value
    token: str = nicegui_app.storage.user.get("access_token", "")

    if not topology_id and layout_id:
        topology_id = await _resolve_topology_id_from_layout(token, layout_id)

    ws_name = ""
    topo_name = ""
    if workspace_id and topology_id:
        headers = {"Authorization": f"Bearer {token}"}
        ws_name, topo_name = await fetch_breadcrumb_names(
            workspace_id, topology_id, headers,
        )

    ui.add_body_html(f"<script>{CONTEXT_MENU_JS}</script>")

    elements, saved_layout = await load_canvas_data(
        token,
        layout_id=layout_id,
        topology_id=topology_id,
    )

    current_diagram_id = ""
    current_diagram_version: int | None = None
    draft_version: int | None = None
    has_unsaved_changes = False
    restore_summary: dict[str, object] | None = None
    if isinstance(saved_layout, dict):
        raw_diagram_id = saved_layout.get("_current_diagram_id")
        if raw_diagram_id:
            current_diagram_id = str(raw_diagram_id)
        raw_diagram_version = saved_layout.get("_current_diagram_version")
        if isinstance(raw_diagram_version, int):
            current_diagram_version = raw_diagram_version
        elif isinstance(raw_diagram_version, float):
            current_diagram_version = int(raw_diagram_version)
        raw_draft_version = saved_layout.get("_draft_version")
        if isinstance(raw_draft_version, int):
            draft_version = raw_draft_version
        elif isinstance(raw_draft_version, float):
            draft_version = int(raw_draft_version)
        raw_unsaved_changes = saved_layout.get("_has_unsaved_changes")
        has_unsaved_changes = bool(raw_unsaved_changes)
        raw_restore_summary = saved_layout.get("restore_summary")
        if isinstance(raw_restore_summary, dict):
            restore_summary = raw_restore_summary

    network_summaries = await load_network_summaries(token)

    placed_ids = compute_placed_ids(elements)
    stencil_devices: list[dict[str, str | int]] = []
    if role != Role.Reader:
        stencil_devices = await _fetch_stencil_devices(token)

    can_patch_diagrams = role in (Role.Admin, Role.Contributor)
    register_canvas_undo_handlers(token, user_role)
    ui.add_body_html(
        "<script>"
        f"window.HT_CAN_PATCH_DIAGRAMS = {str(can_patch_diagrams).lower()};"
        "window.HT_READONLY = true;"
        f"window._htUserRole = {json.dumps(user_role)};"
        f"window._htTopologyId = {json.dumps(topology_id or None)};"
        f"window._htDiagramId = {json.dumps(current_diagram_id or None)};"
        f"window._htCurrentDiagramId = {json.dumps(current_diagram_id or None)};"
        f"window._htDiagramVersion = {json.dumps(current_diagram_version)};"
        f"window._htDraftVersion = {json.dumps(draft_version)};"
        f"window._htHasUnsavedChanges = {json.dumps(has_unsaved_changes)};"
        "</script>"
    )
    inject_topology_leave_guard(user_role)
    ui.add_body_html(f"<script>{VIEW_MODE_JS}</script>")
    ui.add_body_html(f"<script>{EDIT_MODE_JS}</script>")
    ui.add_body_html("<script>(function(){window._htEventsWired=false;if(window._htTopologyTeardownInit)return;window._htTopologyTeardownInit=true;window.addEventListener('pagehide',function(){window._htEventsWired=false;if(window._htResetUndoState)window._htResetUndoState();});})();</script>")

    _refs: dict[str, object] = {}

    with app_shell(
        "Topology",
        "/topology",
        breadcrumb=["Topology"],
        header_actions=lambda: _render_header_actions(
            token,
            user_role,
            _refs,
            topology_id,
            current_diagram_id,
            current_diagram_version,
            draft_version,
            has_unsaved_changes,
        ),
    ):
        if ws_name and topo_name:
            render_breadcrumb([
                ("Workspaces", "/workspaces"),
                (ws_name, f"/workspaces/{workspace_id}"),
                (topo_name, ""),
            ], use_leave_guard=True)
        render_restore_summary_banner(restore_summary)
        with ui.row().style(
            "flex: 1; width: 100%; min-height: 0; gap: 0;"
            " flex-wrap: nowrap; align-items: stretch;"
        ):
            palette_container = ui.element("div").style(
                "flex-shrink: 0; overflow-y: auto; display: flex;"
                " flex-direction: row; max-height: 100%;"
            )
            palette_container.set_visibility(False)
            _refs["palette"] = palette_container
            if role != Role.Reader:
                with palette_container:
                    render_palette()
                    render_stencils_panel(stencil_devices, placed_ids)

            with ui.element("div").style(
                "flex: 1; min-width: 0; min-height: 0; position: relative;"
            ):
                render_canvas(elements, saved_layout)
                inject_canvas_shortcuts()
                inject_zoom_controls()
                inject_network_overlay()

            render_network_filter_panel(network_summaries)

            render_detail_panel(token, user_role)
            render_ghost_detail_panel(token, user_role, topology_id)
            render_connection_detail_panel(token, user_role)

            if device_id:
                focus_js = _FOCUS_DEVICE_JS_TEMPLATE.replace(
                    "__HT_DEVICE_ID__", json.dumps(device_id)
                )
                ui.add_body_html(f"<script>{focus_js}</script>")
