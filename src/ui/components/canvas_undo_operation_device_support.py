"""Device-oriented undo/redo handlers for the canvas undo bridge."""

from __future__ import annotations

from src.ui.components.canvas_undo_dispatch_types import CallApi, ResolveFailure
from src.ui.components.canvas_undo_dispatch_types import ResolveSuccess
from src.ui.components.canvas_undo_handler_utils import (
    apply_undoable_device_field_patch,
    as_dict,
    fetch_current_device_version,
    node_set_from_snapshot,
    response_detail,
    to_int,
    to_uuid,
)
from src.ui.components.canvas_undo_reparent_support import (
    apply_reparent_with_conflict_recovery,
    reparent_graph_patch,
    updated_reparent_payload,
)


async def handle_delete_published_device_operation(
    direction: str,
    entry: dict[str, object],
    payload: dict[str, object],
    _token: str,
    resolve_success: ResolveSuccess,
    resolve_failure: ResolveFailure,
    call_api: CallApi,
) -> None:
    entry_id = str(entry.get("entry_id", ""))
    device_id = str(payload.get("device_id", ""))
    active_diagram_id = payload.get("active_diagram_id")
    response = await call_api("POST", f"/api/devices/{device_id}/canvas-delete", None)
    if response.status_code != 200:
        await resolve_failure(direction, entry_id, response_detail(response))
        return

    body = as_dict(response.json())
    snapshot = as_dict(body.get("snapshot"))
    node_set = node_set_from_snapshot(snapshot, None, active_diagram_id)
    await resolve_success(
        direction,
        entry_id,
        {
            "entry_patch": {
                "reverse": {
                    "op": "restore_published_device",
                    "payload": {
                        "device_id": device_id,
                        "snapshot": snapshot,
                        "active_node": node_set,
                        "active_diagram_id": active_diagram_id,
                    },
                }
            },
            "graph_patch": {"op": "remove_node_set", "snapshot": node_set},
            "stencil_patch": {"op": "remove_published_device", "device_id": device_id},
            "modified_diagrams": body.get("modified_diagrams", []),
        },
    )


async def handle_restore_published_device_operation(
    direction: str,
    entry: dict[str, object],
    payload: dict[str, object],
    _token: str,
    resolve_success: ResolveSuccess,
    resolve_failure: ResolveFailure,
    call_api: CallApi,
) -> None:
    entry_id = str(entry.get("entry_id", ""))
    device_id = str(payload.get("device_id", ""))
    snapshot = as_dict(payload.get("snapshot"))
    response = await call_api("POST", f"/api/devices/{device_id}/restore", snapshot)
    if response.status_code != 200:
        await resolve_failure(direction, entry_id, response_detail(response))
        return

    await resolve_success(
        direction,
        entry_id,
        {
            "graph_patch": {
                "op": "restore_node_set",
                "snapshot": node_set_from_snapshot(
                    snapshot,
                    as_dict(payload.get("active_node")),
                    payload.get("active_diagram_id"),
                ),
            },
            "stencil_patch": {
                "op": "upsert_published_device",
                "device": as_dict(snapshot.get("device")),
            },
            "modified_diagrams": as_dict(response.json()).get("modified_diagrams", []),
        },
    )


async def handle_update_device_field_operation(
    direction: str,
    entry: dict[str, object],
    payload: dict[str, object],
    token: str,
    resolve_success: ResolveSuccess,
    resolve_failure: ResolveFailure,
    _call_api: CallApi,
) -> None:
    entry_id = str(entry.get("entry_id", ""))
    device_uuid = to_uuid(payload.get("device_id"))
    field = str(payload.get("field", ""))
    if device_uuid is None or not field:
        await resolve_failure(direction, entry_id, "Invalid device field payload")
        return

    target_value = payload.get("before") if direction == "undo" else payload.get("after")
    version_cursor = await fetch_current_device_version(
        token,
        device_id=device_uuid,
        fallback=to_int(payload.get("version_cursor", 1), 1),
    )
    ok, next_version = await apply_undoable_device_field_patch(
        token,
        device_id=device_uuid,
        field=field,
        after=target_value,
        version_cursor=version_cursor,
    )
    if not ok:
        await resolve_failure(direction, entry_id, f"Failed to update {field}")
        return

    node_patch = as_dict(payload.get("node_patch")) or {field: target_value}
    node_patch[field] = target_value
    node_patch["version"] = next_version
    updated_payload = {
        "device_id": str(device_uuid),
        "field": field,
        "before": payload.get("before"),
        "after": payload.get("after"),
        "version_cursor": next_version,
        "version_strategy": "current_device",
        "node_patch": node_patch,
    }
    await resolve_success(
        direction,
        entry_id,
        {
            "entry_patch": {
                "forward": {"op": "update_device_field", "payload": updated_payload},
                "reverse": {"op": "update_device_field", "payload": updated_payload},
            },
            "graph_patch": {"op": "patch_node", "node_id": str(device_uuid), "patch": node_patch},
        },
    )


async def handle_reparent_device_operation(
    direction: str,
    entry: dict[str, object],
    payload: dict[str, object],
    token: str,
    resolve_success: ResolveSuccess,
    resolve_failure: ResolveFailure,
    call_api: CallApi,
) -> None:
    entry_id = str(entry.get("entry_id", ""))
    device_uuid = to_uuid(payload.get("device_id"))
    if device_uuid is None:
        await resolve_failure(direction, entry_id, "Invalid reparent payload")
        return

    target_parent = payload.get("from_parent_id") if direction == "undo" else payload.get("to_parent_id")
    target_rendered = payload.get("from_rendered_position") if direction == "undo" else payload.get("to_rendered_position")
    version_cursor = to_int(payload.get("version_cursor", 1), 1)
    ok, next_version, error_message = await apply_reparent_with_conflict_recovery(
        call_api=call_api,
        device_id=device_uuid,
        target_parent=target_parent,
        version_cursor=version_cursor,
    )
    if not ok:
        await resolve_failure(direction, entry_id, error_message or "Conflict")
        return

    device_id = str(device_uuid)
    updated_payload = updated_reparent_payload(payload, device_id=device_id, version_cursor=next_version)
    await resolve_success(
        direction,
        entry_id,
        {
            "entry_patch": {
                "forward": {"op": "reparent_device", "payload": updated_payload},
                "reverse": {"op": "reparent_device", "payload": updated_payload},
            },
            "graph_patch": reparent_graph_patch(
                device_id=device_id,
                parent_id=target_parent,
                rendered_position=target_rendered,
                version_cursor=next_version,
            ),
        },
    )