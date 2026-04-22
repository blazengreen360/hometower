"""Device-oriented forward handlers for the canvas undo bridge."""

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


async def handle_delete_published_node_action(
    entry_id: str,
    payload: dict[str, object],
    _token: str,
    resolve_success: ResolveSuccess,
    resolve_failure: ResolveFailure,
    call_api: CallApi,
) -> None:
    device_id = str(payload.get("device_id", ""))
    active_diagram_id = payload.get("active_diagram_id")
    response = await call_api("POST", f"/api/devices/{device_id}/canvas-delete", None)
    if response.status_code != 200:
        await resolve_failure("forward", entry_id, response_detail(response))
        return

    body = as_dict(response.json())
    snapshot = as_dict(body.get("snapshot"))
    node_set = node_set_from_snapshot(snapshot, as_dict(payload.get("active_node")), active_diagram_id)
    await resolve_success(
        "forward",
        entry_id,
        {
            "entry": {
                "entry_id": entry_id,
                "type": "delete_published_node",
                "label": "Delete device",
                "execution": "api",
                "forward": {
                    "op": "delete_published_device",
                    "payload": {"device_id": device_id, "active_diagram_id": active_diagram_id},
                },
                "reverse": {
                    "op": "restore_published_device",
                    "payload": {
                        "device_id": device_id,
                        "snapshot": snapshot,
                        "active_node": node_set,
                        "active_diagram_id": active_diagram_id,
                    },
                },
            },
            "graph_patch": {"op": "remove_node_set", "snapshot": node_set},
            "stencil_patch": {"op": "remove_published_device", "device_id": device_id},
            "modified_diagrams": body.get("modified_diagrams", []),
        },
    )


async def handle_update_device_field_action(
    entry_id: str,
    payload: dict[str, object],
    token: str,
    resolve_success: ResolveSuccess,
    resolve_failure: ResolveFailure,
    _call_api: CallApi,
) -> None:
    device_uuid = to_uuid(payload.get("device_id"))
    field = str(payload.get("field", ""))
    if device_uuid is None or not field:
        await resolve_failure("forward", entry_id, "Invalid device field action payload")
        return

    version_cursor = await fetch_current_device_version(
        token,
        device_id=device_uuid,
        fallback=to_int(payload.get("version_cursor", 1), 1),
    )
    ok, next_version = await apply_undoable_device_field_patch(
        token,
        device_id=device_uuid,
        field=field,
        after=payload.get("after"),
        version_cursor=version_cursor,
    )
    if not ok:
        await resolve_failure("forward", entry_id, f"Failed to update {field}")
        return

    node_patch = as_dict(payload.get("node_patch")) or {field: payload.get("after")}
    node_patch["version"] = next_version
    action_payload = {
        "device_id": str(device_uuid),
        "field": field,
        "before": payload.get("before"),
        "after": payload.get("after"),
        "version_cursor": next_version,
        "version_strategy": "current_device",
        "node_patch": node_patch,
    }
    await resolve_success(
        "forward",
        entry_id,
        {
            "entry": {
                "entry_id": entry_id,
                "type": "update_device_field",
                "label": f"Update {field}",
                "execution": "api",
                "forward": {"op": "update_device_field", "payload": action_payload},
                "reverse": {"op": "update_device_field", "payload": action_payload},
            },
            "graph_patch": {"op": "patch_node", "node_id": str(device_uuid), "patch": node_patch},
        },
    )


async def handle_reparent_device_action(
    entry_id: str,
    payload: dict[str, object],
    token: str,
    resolve_success: ResolveSuccess,
    resolve_failure: ResolveFailure,
    call_api: CallApi,
) -> None:
    device_uuid = to_uuid(payload.get("device_id"))
    if device_uuid is None:
        await resolve_failure("forward", entry_id, "Invalid reparent action payload")
        return

    version_cursor = to_int(payload.get("version_cursor", 1), 1)
    ok, next_version, error_message = await apply_reparent_with_conflict_recovery(
        call_api=call_api,
        device_id=device_uuid,
        target_parent=payload.get("to_parent_id"),
        version_cursor=version_cursor,
    )
    if not ok:
        await resolve_failure("forward", entry_id, error_message or "Conflict")
        return

    device_id = str(device_uuid)
    reparent_payload = updated_reparent_payload(payload, device_id=device_id, version_cursor=next_version)
    await resolve_success(
        "forward",
        entry_id,
        {
            "entry": {
                "entry_id": entry_id,
                "type": "reparent_device",
                "label": str(payload.get("label", "Move device")),
                "execution": "api",
                "forward": {"op": "reparent_device", "payload": reparent_payload},
                "reverse": {"op": "reparent_device", "payload": reparent_payload},
            },
            "graph_patch": reparent_graph_patch(
                device_id=device_id,
                parent_id=payload.get("to_parent_id"),
                rendered_position=payload.get("to_rendered_position"),
                version_cursor=next_version,
            ),
        },
    )