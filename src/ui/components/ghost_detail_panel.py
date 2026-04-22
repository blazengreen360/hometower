"""Ghost placeholder detail panel for topology history reconciliation (HT-075)."""

import json

import httpx
from nicegui import ui

from src.ui.components.device_detail_panel_shell import (
    build_panel_visibility_js,
    build_right_rail_panel,
)
from src.ui.components.toast import show_toast
from src.ui.components.topology_layout_bar_support import apply_history_response, build_state_sync_js
from src.ui.design.primitives import primary_button
from src.ui.design.primitives import secondary_button
from src.utils.logger import logger
from src.utils.settings import settings

_RECONCILE_ROLES = {"Admin", "Contributor"}
_PAGE_LIMIT = 100


async def _read_window_diagram_version() -> int | None:
    raw_version = await ui.run_javascript("window._htDiagramVersion")
    if isinstance(raw_version, int):
        return raw_version
    if isinstance(raw_version, float):
        return int(raw_version)
    return None


def _format_live_device_option(item: dict[str, object]) -> tuple[str, str] | None:
    raw_id = item.get("id")
    if raw_id is None:
        return None
    device_id = str(raw_id)
    name = str(item.get("name", "Unnamed device")).strip() or "Unnamed device"
    device_type = str(item.get("type", "Unknown")).strip() or "Unknown"
    return device_id, f"{name} ({device_type})"


async def _fetch_live_device_options(token: str) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    options: dict[str, str] = {}
    try:
        async with httpx.AsyncClient() as client:
            page = 1
            while True:
                response = await client.get(
                    f"{settings.api_base_url}/api/devices/",
                    params={"page": page, "limit": _PAGE_LIMIT},
                    headers=headers,
                    timeout=5.0,
                )
                if response.status_code != 200:
                    break
                raw_items = response.json().get("items", [])
                items = [item for item in raw_items if isinstance(item, dict)]
                for item in items:
                    option = _format_live_device_option(item)
                    if option is None:
                        continue
                    device_id, label = option
                    options[device_id] = label
                if len(items) < _PAGE_LIMIT:
                    break
                page += 1
    except httpx.HTTPError as exc:
        logger.warning("Ghost panel device options fetch failed: {}", str(exc))
    return options


async def _apply_editor_response(response_data: dict[str, object]) -> None:
    state: dict[str, object] = {
        "current_diagram_id": None,
        "current_diagram_version": None,
        "draft_version": None,
        "has_unsaved_changes": False,
    }
    apply_history_response(state, response_data)
    await ui.run_javascript(build_state_sync_js(state))
    layout = response_data.get("cytoscape_json")
    if not isinstance(layout, dict):
        return
    layout_json = json.dumps(layout)
    await ui.run_javascript(
        "if(window.applyTopologySnapshot){"
        f"window.applyTopologySnapshot({layout_json});"
        "}else if(window.applyLayoutPositions){"
        f"window.applyLayoutPositions({layout_json});"
        "}"
    )


def render_ghost_detail_panel(token: str, user_role: str, topology_id: str) -> None:
    """Render a dedicated panel for ghost placeholders and reconciliation actions."""
    can_reconcile = user_role in _RECONCILE_ROLES
    state: dict[str, object] = {
        "ghost_id": None,
        "ghost_original_name": "",
        "ghost_original_type": "",
        "ghost_status": "Deleted from inventory",
    }
    panel = build_right_rail_panel(
        "ghost-detail-panel", "Deleted device details", element_builder=ui.element
    )
    name_label_ref: list[ui.label] = []
    type_label_ref: list[ui.label] = []
    status_label_ref: list[ui.label] = []
    map_select_ref: list[ui.select] = []

    async def _close_panel() -> None:
        await ui.run_javascript(build_panel_visibility_js("ghost-detail-panel", False))
        state["ghost_id"] = None

    async def _refresh_map_options() -> None:
        if not can_reconcile or not map_select_ref:
            return
        options = await _fetch_live_device_options(token)
        ghost_id = state.get("ghost_id")
        if isinstance(ghost_id, str):
            options.pop(ghost_id, None)
        map_select_ref[0].set_options(options, value=None)

    async def _post_reconcile_action(endpoint: str, payload: dict[str, object], success_title: str) -> None:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.api_base_url}{endpoint}",
                    json=payload,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10.0,
                )
        except httpx.HTTPError as exc:
            logger.error("Ghost reconciliation request failed: {}", str(exc))
            show_toast(type="error", title="Connection error")
            return
        if response.status_code == 200:
            body = response.json()
            if not isinstance(body, dict):
                show_toast(type="error", title="Unexpected reconcile response")
                return
            await _apply_editor_response(body)
            show_toast(type="success", title=success_title)
            await _close_panel()
            return
        if response.status_code == 404:
            show_toast(type="error", title="Ghost placeholder not found")
            return
        if response.status_code == 409:
            show_toast(type="warning", title="Conflict detected. Reload to sync.")
            return
        if response.status_code == 422:
            show_toast(type="warning", title="Reconcile validation failed")
            return
        show_toast(type="error", title=f"Reconcile failed ({response.status_code})")

    async def _recreate_as_new_device() -> None:
        ghost_id = state.get("ghost_id")
        if not isinstance(ghost_id, str) or not ghost_id or not topology_id:
            show_toast(type="error", title="Ghost context is missing")
            return
        base_diagram_version = await _read_window_diagram_version()
        await _post_reconcile_action(
            endpoint=f"/api/topologies/{topology_id}/ghosts/{ghost_id}/recreate",
            payload={"base_diagram_version": base_diagram_version},
            success_title="Ghost recreated as new device",
        )

    async def _map_to_existing_device() -> None:
        ghost_id = state.get("ghost_id")
        if not isinstance(ghost_id, str) or not ghost_id or not topology_id:
            show_toast(type="error", title="Ghost context is missing")
            return
        if not map_select_ref:
            show_toast(type="error", title="Mapping selector is unavailable")
            return
        selected_live_device = map_select_ref[0].value
        if not isinstance(selected_live_device, str) or not selected_live_device:
            show_toast(type="warning", title="Select a live device to map")
            return
        base_diagram_version = await _read_window_diagram_version()
        await _post_reconcile_action(
            endpoint=f"/api/topologies/{topology_id}/ghosts/{ghost_id}/map",
            payload={"live_device_id": selected_live_device, "base_diagram_version": base_diagram_version},
            success_title="Ghost mapped to existing device",
        )

    with panel:
        with ui.row().classes("justify-between items-center w-full"):
            ui.label("Deleted Device").style("color:var(--ht-text-primary); font-size:1.25rem; font-weight:600;")
            ui.button(icon="close", on_click=_close_panel).props("flat dense aria-label='Close panel'").style(
                "color:var(--ht-text-secondary);"
            )
        status_label_ref.append(ui.label("Deleted from inventory").style("font-size:0.875rem; color:var(--ht-warning); font-weight:600;"))
        name_label_ref.append(ui.label("").style("font-size:1rem; color:var(--ht-text-primary); font-weight:600;"))
        type_label_ref.append(ui.label("").style("font-size:0.875rem; color:var(--ht-text-secondary);"))
        ui.label("This historical node remains visible in the topology and is not editable.").style(
            "font-size:0.825rem; color:var(--ht-text-secondary);"
        )
        if can_reconcile:
            ui.separator()
            ui.label("Reconcile this ghost").style("font-size:0.875rem; color:var(--ht-text-primary); font-weight:600;")
            secondary_button(
                ui.button("Recreate as New Device", on_click=_recreate_as_new_device)
            ).classes("w-full")
            map_select = ui.select(options={}, label="Map to Existing Device", value=None).classes("w-full")
            map_select_ref.append(map_select)
            primary_button(
                ui.button("Map Selected Device", on_click=_map_to_existing_device)
            ).classes("w-full")
        else:
            ui.label("Your role can view ghosts but cannot reconcile them.").style(
                "font-size:0.825rem; color:var(--ht-text-secondary);"
            )

    async def _on_ghost_panel_select(event: object) -> None:
        args = getattr(event, "args", None)
        if not isinstance(args, dict):
            return
        ghost_id = args.get("ghost_id")
        if not isinstance(ghost_id, str) or not ghost_id:
            return
        state["ghost_id"] = ghost_id
        state["ghost_original_name"] = str(args.get("ghost_original_name", "Deleted device"))
        state["ghost_original_type"] = str(args.get("ghost_original_type", "Unknown"))
        state["ghost_status"] = str(args.get("ghost_status", "Deleted from inventory"))
        name_label_ref[0].set_text(str(state["ghost_original_name"]))
        type_label_ref[0].set_text(f"Type: {state['ghost_original_type']}")
        status_label_ref[0].set_text(str(state["ghost_status"]))
        await ui.run_javascript(build_panel_visibility_js("ghost-detail-panel", True))
        if can_reconcile:
            await _refresh_map_options()

    ui.on("ghost_panel_select", _on_ghost_panel_select)
