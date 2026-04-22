"""Topology page — NiceGUI page at /topology."""
import json

from fastapi import Request
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
from src.ui.components.ghost_detail_panel import render_ghost_detail_panel
from src.ui.components.stencils_panel import compute_placed_ids
from src.ui.components.topology_layout_runtime import (
    arm_topology_layout_runtime,
    inject_topology_layout_runtime,
)
from src.ui.components.topology_layout_shell import (
    inject_topology_layout_shell_css,
    render_topology_left_rail,
)
from src.ui.components.topology_restore_summary import render_restore_summary_banner
from src.ui.components.topology_leave_guard import inject_topology_leave_guard
from src.ui.pages.topology_page_context import build_topology_current_path
from src.ui.pages.topology_page_context import inject_focus_device_script
from src.ui.pages.topology_page_context import load_stencil_devices_for_role
from src.ui.pages.topology_page_context import parse_saved_layout_context
from src.ui.pages.topology_page_context import render_topology_breadcrumb
from src.ui.pages.topology_page_context import resolve_topology_page_route_context
from src.ui.pages.topology_page_support import (
    _FOCUS_DEVICE_JS_TEMPLATE,
    _render_header_actions,
)
from src.ui.services.topology_data import load_canvas_data

@ui.page("/topology")
async def topology_page(
    request: Request,
    device_id: str = "",
    layout_id: str = "",
    topology_id: str = "",
    workspace_id: str = "",
) -> None:
    """Topology page — requires auth, renders the full canvas view."""
    current_path = build_topology_current_path(request)

    if redirect_if_unauthenticated(current_path=current_path):
        return

    role = get_ui_role()
    user_role: str = role.value if role else Role.Reader.value
    token: str = nicegui_app.storage.user.get("access_token", "")

    route_context = await resolve_topology_page_route_context(
        token,
        layout_id,
        topology_id,
        workspace_id,
    )
    topology_id = route_context.topology_id

    ui.add_body_html(f"<script>{CONTEXT_MENU_JS}</script>")

    elements, saved_layout = await load_canvas_data(
        token,
        layout_id=layout_id,
        topology_id=topology_id,
    )

    layout_context = parse_saved_layout_context(saved_layout)

    placed_ids = compute_placed_ids(elements)
    stencil_devices = await load_stencil_devices_for_role(token, role)
    restore_summary = layout_context.restore_summary

    can_patch_diagrams = role in (Role.Admin, Role.Contributor)
    register_canvas_undo_handlers(token, user_role)
    ui.add_body_html(
        "<script>"
        f"window.HT_CAN_PATCH_DIAGRAMS = {str(can_patch_diagrams).lower()};"
        "window.HT_READONLY = true;"
        f"window._htUserRole = {json.dumps(user_role)};"
        f"window._htTopologyId = {json.dumps(topology_id or None)};"
        f"window._htDiagramId = {json.dumps(layout_context.current_diagram_id or None)};"
        f"window._htCurrentDiagramId = {json.dumps(layout_context.current_diagram_id or None)};"
        f"window._htDiagramVersion = {json.dumps(layout_context.current_diagram_version)};"
        f"window._htDraftVersion = {json.dumps(layout_context.draft_version)};"
        f"window._htHasUnsavedChanges = {json.dumps(layout_context.has_unsaved_changes)};"
        "</script>"
    )
    inject_topology_leave_guard(user_role)
    ui.add_body_html(f"<script>{VIEW_MODE_JS}</script>")
    ui.add_body_html(f"<script>{EDIT_MODE_JS}</script>")
    inject_topology_layout_runtime()
    inject_topology_layout_shell_css()
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
                layout_context.current_diagram_id,
                layout_context.current_diagram_version,
                layout_context.draft_version,
                layout_context.has_unsaved_changes,
        ),
    ):
        with ui.column().props('id="ht-topology-page"').classes("w-full flex-1").style(
            "min-height:0; height:100%;"
        ):
            render_topology_breadcrumb(
                route_context.workspace_name,
                route_context.topology_name,
                workspace_id,
            )
            render_restore_summary_banner(restore_summary)
            # The shell still honors the old "flex-wrap: nowrap;" and
            # "align-items: stretch;" canvas contract, but the row is now
            # expressed through explicit shell ids.
            with ui.element("section").props('id="ht-topology-shell"'):
                if role != Role.Reader:
                    # render_palette() now lives inside the consolidated left rail helper.
                    _refs["palette"] = render_topology_left_rail(stencil_devices, placed_ids)

                with ui.element("div").props('id="ht-topology-workspace"'):
                    with ui.element("div").props('id="ht-topology-canvas-stage"'):
                        render_canvas(elements, saved_layout)
                        inject_canvas_shortcuts()
                        inject_zoom_controls()
                        inject_network_overlay()

                    with ui.element("aside").props(
                        'id="ht-topology-right-rail" role="complementary" aria-label="Topology side panels"'
                    ):
                        render_detail_panel(token, user_role)
                        render_ghost_detail_panel(token, user_role, topology_id)
                        render_connection_detail_panel(token, user_role)

        arm_topology_layout_runtime()
        if device_id:
            inject_focus_device_script(device_id)
