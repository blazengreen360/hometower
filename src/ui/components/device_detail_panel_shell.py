"""Shell helpers for the device detail panel."""

from collections.abc import Awaitable, Callable, Sequence
import json
import uuid

from nicegui import ui

from src.models.connection import ConnectionResponse
from src.models.device import DeviceResponseEnriched


def build_detail_panel(
    is_editor: bool,
    on_duplicate: Callable[[], Awaitable[None]],
    on_close: Callable[[], Awaitable[None]],
) -> tuple[ui.label, ui.column]:
    panel = ui.element("div").props(
        'role="complementary" aria-label="Device details" id="device-detail-panel"'
    ).style(
        "display:none; flex-direction:column; gap:8px; width:280px; "
        "min-width:280px; padding:16px; background:var(--ht-bg-surface-raised); "
        "overflow-y:auto; flex-shrink:0;"
    )

    with panel:
        with ui.row().classes("justify-between items-center w-full"):
            ui.label("Device Info").style(
                "color:var(--ht-text-primary); font-size:1.25rem; font-weight:600;"
            )

            with ui.row().style("gap:4px; align-items:center;"):
                if is_editor:
                    ui.button(icon="content_copy", on_click=on_duplicate).props(
                        "flat dense aria-label='Duplicate device'"
                    ).style("color:var(--ht-text-secondary);")
                ui.button(icon="close", on_click=on_close).props(
                    "flat dense aria-label='Close panel'"
                ).style("color:var(--ht-text-secondary);")

        live_lbl = (
            ui.label("")
            .props("aria-live=polite")
            .style("position:absolute; width:1px; height:1px; overflow:hidden;")
        )
        content = ui.column().classes("w-full gap-2")
    return live_lbl, content


async def build_neighbor_names(
    device_id: uuid.UUID,
    connections: Sequence[ConnectionResponse],
    fetch_device: Callable[[uuid.UUID], Awaitable[DeviceResponseEnriched | None]],
) -> dict[uuid.UUID, str]:
    neighbor_names: dict[uuid.UUID, str] = {}
    for conn in connections:
        source_id = getattr(conn, "source_id", None)
        target_id = getattr(conn, "target_id", None)
        if not isinstance(source_id, uuid.UUID) or not isinstance(target_id, uuid.UUID):
            continue
        neighbor_id = target_id if source_id == device_id else source_id
        if neighbor_id in neighbor_names:
            continue
        neighbor = await fetch_device(neighbor_id)
        neighbor_names[neighbor_id] = neighbor.name if neighbor else f"{str(neighbor_id)[:8]}…"
    return neighbor_names


async def handle_panel_select(
    event: object,
    state: dict[str, object],
    content: ui.column,
    refresh: Callable[[], Awaitable[None]],
    show_draft: Callable[[str, ui.column], Awaitable[None]],
    on_invalid_uuid: Callable[[str], None],
) -> None:
    args = getattr(event, "args", None)
    if not isinstance(args, dict):
        return
    raw_id = args.get("device_id", "")
    if not isinstance(raw_id, str):
        return

    if raw_id.startswith("draft-"):
        state["device_id"] = None
        state["last_device"] = None
        await show_draft(raw_id, content)
        return

    try:
        state["device_id"] = uuid.UUID(raw_id)
    except ValueError:
        on_invalid_uuid(raw_id)
        return

    await refresh()


async def push_device_field_change(
    device_id: uuid.UUID,
    field: str,
    before_value: object,
    after_value: object,
    version: int,
    label: str,
    operation: str,
) -> None:
    node_patch = {field: after_value, "version": version}
    payload = {
        "device_id": str(device_id),
        "field": field,
        "before": before_value,
        "after": after_value,
        "version_cursor": version,
        "version_strategy": "current_device",
        "node_patch": node_patch,
    }
    undo_entry = {
        "entry_id": str(uuid.uuid4()),
        "type": operation,
        "label": f"Update {label}",
        "execution": "api",
        "forward": {"op": operation, "payload": payload},
        "reverse": {"op": operation, "payload": payload},
    }

    await ui.run_javascript(
        "if(window._htApplyUndoNodePatch) "
        f"window._htApplyUndoNodePatch({json.dumps(str(device_id))}, {json.dumps(node_patch)});"
    )
    await ui.run_javascript(
        "if(window._htPushCommittedUndoEntry) "
        f"window._htPushCommittedUndoEntry({json.dumps(undo_entry)});"
    )