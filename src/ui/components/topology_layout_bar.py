"""Topology history toolbar component for the topology page (HT-072)."""
import asyncio
import html
import json as _json

import httpx
from nicegui import ui

from src.ui.components.topology_layout_api import get_layouts
from src.ui.components.topology_layout_bar_support import (
    apply_history_response,
    build_state_sync_js,
    fetch_history_map,
    history_label,
    history_items_from_state,
    normalize_history_selection,
    request_restore_version,
    request_save_version,
)
from src.ui.components.topology_layout_dialogs import build_restore_dialog
from src.ui.components.toast import show_toast

_ROLES_WITH_EDIT = {"Admin", "Contributor"}


def render_layout_bar(
    token: str,
    user_role: str,
    topology_id: str = "",
    initial_diagram_id: str = "",
    initial_diagram_version: int | None = None,
    initial_draft_version: int | None = None,
    initial_has_unsaved_changes: bool = False,
) -> None:
    """Render Save Version + History controls in the topology header."""
    is_editor: bool = user_role in _ROLES_WITH_EDIT
    state: dict[str, object] = {
        "selected_history_id": None,
        "history_items": {},
        "current_diagram_id": initial_diagram_id or None,
        "current_diagram_version": initial_diagram_version,
        "draft_version": initial_draft_version,
        "has_unsaved_changes": initial_has_unsaved_changes,
    }
    inputs: dict[str, object] = {}

    def _sync_js() -> None:
        ui.run_javascript(build_state_sync_js(state))

    async def _sync_state_from_window() -> None:
        payload = await ui.run_javascript(
            "({id:window._htDiagramId,v:window._htDiagramVersion,d:window._htDraftVersion,u:window._htHasUnsavedChanges})"
        )
        if not isinstance(payload, dict):
            return
        state["current_diagram_id"], state["current_diagram_version"], state["draft_version"], state["has_unsaved_changes"] = payload.get("id"), payload.get("v"), payload.get("d"), bool(payload.get("u"))

    async def _apply_canvas_state(cytoscape_json: dict[str, object]) -> None:
        await ui.run_javascript(
            f"if(window.applyLayoutPositions) window.applyLayoutPositions({_json.dumps(cytoscape_json)});"
        )

    def _history_items() -> dict[str, dict[str, object]]:
        return history_items_from_state(state)

    restore_dlg = ui.dialog()
    history_dlg = ui.dialog()

    def _resolve_selected_history_id() -> str | None:
        history_map = _history_items()
        select_obj = inputs.get("history_select")
        if select_obj is not None:
            select_input: ui.select = select_obj  # type: ignore[assignment]
            selected = normalize_history_selection(select_input.value, history_map)
            if selected is not None:
                state["selected_history_id"] = selected
                if select_input.value != selected:
                    select_input.set_value(selected)
                return selected

        selected_from_state = normalize_history_selection(
            state.get("selected_history_id"),
            history_map,
        )
        state["selected_history_id"] = selected_from_state
        return selected_from_state

    async def _refresh_history() -> None:
        history_map = await fetch_history_map(token, topology_id, get_layouts, httpx.AsyncClient)
        state["history_items"] = history_map

        options: dict[str, str] = {
            item_id: history_label(item)
            for item_id, item in history_map.items()
        }

        preferred = normalize_history_selection(state.get("selected_history_id"), history_map)
        if preferred is None:
            for item_id, item in history_map.items():
                if item.get("is_current") is True:
                    preferred = item_id
                    break

        select_input: ui.select = inputs["history_select"]  # type: ignore[assignment]
        select_input.set_options(options, value=preferred)
        state["selected_history_id"] = preferred
        history_empty_label = inputs.get("history_empty")
        if history_empty_label is not None:
            history_empty_label.set_visibility(not bool(options))  # type: ignore[attr-defined]

    async def _open_history() -> None:
        await _refresh_history()
        history_dlg.open()

    async def _on_history_select(event: object) -> None:
        selected = normalize_history_selection(getattr(event, "value", None), _history_items())
        state["selected_history_id"] = selected
        if selected is None:
            return
        select_obj = inputs.get("history_select")
        if select_obj is not None:
            select_input: ui.select = select_obj  # type: ignore[assignment]
            if select_input.value != selected:
                select_input.set_value(selected)

    async def _confirm_save() -> None:
        if not topology_id:
            show_toast(type="error", title="Topology context is missing")
            return
        await _sync_state_from_window()
        canvas_json = await ui.run_javascript("getCanvasJson()")
        if not isinstance(canvas_json, dict) or not canvas_json:
            show_toast(type="warning", title="Nothing to save")
            return

        status_code, data = await request_save_version(
            token=token,
            topology_id=topology_id,
            state=state,
            canvas_json=canvas_json,
            async_client_factory=httpx.AsyncClient,
        )
        if status_code == 200 and data is not None:
            apply_history_response(state, data)
            _sync_js()
            layout = data.get("cytoscape_json")
            if isinstance(layout, dict):
                await _apply_canvas_state(layout)
            await _refresh_history()
            show_toast(type="success", title="Version saved")
            return
        if status_code == 0:
            show_toast(type="error", title="Connection error")
            return
        if status_code == 409:
            show_toast(type="warning", title="Save conflict detected. Reload to sync.")
            return
        if status_code == 422:
            show_toast(type="warning", title="Save validation failed")
            return
        show_toast(type="error", title=f"Save failed ({status_code})")

    async def _on_restore() -> None:
        selected_id = _resolve_selected_history_id()
        if not selected_id:
            show_toast(type="info", title="Select a history version first")
            return
        item = _history_items().get(selected_id)
        if item and item.get("is_current") is True:
            show_toast(type="info", title="Selected version is already current")
            return

        label: ui.label = inputs["restore_label"]  # type: ignore[assignment]
        version_name = str(item.get("snapshot_name", "this version")) if item else "this version"
        label.set_text(f"Restore '{html.escape(version_name)}' as the latest version?")
        history_dlg.close()
        restore_dlg.open()

    async def _confirm_restore() -> None:
        if not topology_id:
            show_toast(type="error", title="Topology context is missing")
            return
        await _sync_state_from_window()
        selected_id = _resolve_selected_history_id()
        if not selected_id:
            show_toast(type="info", title="Select a history version first")
            return
        status_code, data = await request_restore_version(
            token=token,
            topology_id=topology_id,
            history_entry_id=selected_id,
            state=state,
            async_client_factory=httpx.AsyncClient,
        )
        if status_code == 200 and data is not None:
            apply_history_response(state, data)
            _sync_js()
            layout = data.get("cytoscape_json")
            if isinstance(layout, dict):
                await _apply_canvas_state(layout)
            await _refresh_history()
            show_toast(type="success", title="Version restored")
            restore_dlg.close()
            return
        if status_code == 0:
            show_toast(type="error", title="Connection error")
            return
        if status_code == 404:
            show_toast(type="error", title="Selected history version was not found")
            return
        if status_code == 409:
            show_toast(type="warning", title="Restore conflict detected. Reload to sync.")
            return
        show_toast(type="error", title=f"Restore failed ({status_code})")

    if is_editor:
        build_restore_dialog(restore_dlg, inputs, _confirm_restore)

    with history_dlg:
        with ui.card().style("min-width:340px; max-width:420px; width:100%;"):
            ui.label("History").style("font-weight:600;")
            history_empty = ui.label(
                "No saved versions yet. Use Save Version to create the first checkpoint."
            ).style("color:var(--ht-text-secondary); font-size:0.875rem;")
            history_empty.set_visibility(False)
            inputs["history_empty"] = history_empty

            history_select = (
                ui.select(options={}, label="Versions", clearable=True)
                .classes("w-full")
                .props('placeholder="Select a saved version…"')
            )
            inputs["history_select"] = history_select
            history_select.on_value_change(_on_history_select)

            with ui.row().classes("justify-end gap-2"):
                if is_editor:
                    ui.button("Restore Selected", on_click=_on_restore).props("outline")
                ui.button("Close", on_click=history_dlg.close).props("flat")

    with ui.row().style("gap:8px; align-items:center;"):
        if is_editor:
            ui.button("Save Version", on_click=_confirm_save).style(
                "background:var(--ht-accent); color:var(--ht-text-on-accent); font-size:0.875rem;"
            )
        ui.button("History", on_click=_open_history).props("outline").style(
            "font-size:0.875rem;"
        )

    _sync_js()
    ui.timer(0.05, lambda: asyncio.create_task(_refresh_history()), once=True)
