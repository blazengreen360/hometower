"""Dispatch for forward canvas actions routed through undo/redo API bridge (HT-032)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import httpx

from src.ui.components.canvas_undo_handler_utils import (
    apply_undoable_device_field_patch,
    as_dict,
    fetch_current_device_version,
    graph_edge_payload,
    node_set_from_snapshot,
    response_detail,
    to_int,
    to_uuid,
)

ResolveSuccess = Callable[[str, str, dict[str, object]], Awaitable[None]]
ResolveFailure = Callable[[str, str, str], Awaitable[None]]
CallApi = Callable[[str, str, dict[str, object] | None], Awaitable[httpx.Response]]


async def handle_canvas_action_request(
    *,
    args: dict[str, object],
    can_write: bool,
    token: str,
    resolve_success: ResolveSuccess,
    resolve_failure: ResolveFailure,
    call_api: CallApi,
) -> None:
    entry_id = str(args.get("entry_id", ""))
    action = as_dict(args.get("action"))
    action_type = str(action.get("type", ""))
    payload = as_dict(action.get("payload"))

    if not can_write:
        await resolve_failure("forward", entry_id, "Forbidden")
        return

    if action_type == "create_edge":
        create_payload = {
            "source_id": payload.get("source_id"),
            "target_id": payload.get("target_id"),
            "type": payload.get("connection_type", "Ethernet"),
            "label": payload.get("label"),
        }
        response = await call_api("POST", "/api/connections/", create_payload)
        if response.status_code != 201:
            await resolve_failure("forward", entry_id, response_detail(response))
            return

        created = as_dict(response.json())
        edge_payload = graph_edge_payload(created)
        entry = {
            "entry_id": entry_id,
            "type": "create_edge",
            "label": "Create edge",
            "execution": "api",
            "forward": {"op": "create_published_edge", "payload": edge_payload},
            "reverse": {"op": "delete_published_edge", "payload": edge_payload},
        }
        await resolve_success(
            "forward",
            entry_id,
            {
                "entry": entry,
                "graph_patch": {"op": "add_edge", "edge": edge_payload},
            },
        )
        return

    if action_type == "delete_edge":
        connection_id = str(payload.get("connection_id", ""))
        response = await call_api("DELETE", f"/api/connections/{connection_id}", None)
        if response.status_code not in {204, 404}:
            await resolve_failure("forward", entry_id, response_detail(response))
            return

        edge_payload = {
            "connection_id": connection_id,
            "source_id": payload.get("source_id"),
            "target_id": payload.get("target_id"),
            "connection_type": payload.get("connection_type", "Ethernet"),
            "label": payload.get("label"),
        }
        entry = {
            "entry_id": entry_id,
            "type": "delete_edge",
            "label": "Delete edge",
            "execution": "api",
            "forward": {"op": "delete_published_edge", "payload": edge_payload},
            "reverse": {"op": "create_published_edge", "payload": edge_payload},
        }
        await resolve_success(
            "forward",
            entry_id,
            {
                "entry": entry,
                "graph_patch": {
                    "op": "remove_edge",
                    "connection_id": connection_id,
                },
            },
        )
        return

    if action_type == "delete_published_node":
        device_id = str(payload.get("device_id", ""))
        active_diagram_id = payload.get("active_diagram_id")
        response = await call_api("POST", f"/api/devices/{device_id}/canvas-delete", None)
        if response.status_code != 200:
            await resolve_failure("forward", entry_id, response_detail(response))
            return

        body = as_dict(response.json())
        snapshot = as_dict(body.get("snapshot"))
        active_node = as_dict(payload.get("active_node"))
        node_set = node_set_from_snapshot(snapshot, active_node, active_diagram_id)
        entry = {
            "entry_id": entry_id,
            "type": "delete_published_node",
            "label": "Delete device",
            "execution": "api",
            "forward": {
                "op": "delete_published_device",
                "payload": {
                    "device_id": device_id,
                    "active_diagram_id": active_diagram_id,
                },
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
        }
        await resolve_success(
            "forward",
            entry_id,
            {
                "entry": entry,
                "graph_patch": {"op": "remove_node_set", "snapshot": node_set},
                "modified_diagrams": body.get("modified_diagrams", []),
            },
        )
        return

    if action_type == "update_device_field":
        device_uuid = to_uuid(payload.get("device_id"))
        field = str(payload.get("field", ""))
        if device_uuid is None or not field:
            await resolve_failure("forward", entry_id, "Invalid device field action payload")
            return

        before = payload.get("before")
        after = payload.get("after")
        version_cursor = to_int(payload.get("version_cursor", 1), 1)
        version_cursor = await fetch_current_device_version(
            token,
            device_id=device_uuid,
            fallback=version_cursor,
        )

        ok, next_version = await apply_undoable_device_field_patch(
            token,
            device_id=device_uuid,
            field=field,
            after=after,
            version_cursor=version_cursor,
        )
        if not ok:
            await resolve_failure("forward", entry_id, f"Failed to update {field}")
            return

        node_patch = as_dict(payload.get("node_patch")) or {field: after}
        node_patch["version"] = next_version
        action_payload = {
            "device_id": str(device_uuid),
            "field": field,
            "before": before,
            "after": after,
            "version_cursor": next_version,
            "version_strategy": "current_device",
            "node_patch": node_patch,
        }
        entry = {
            "entry_id": entry_id,
            "type": "update_device_field",
            "label": f"Update {field}",
            "execution": "api",
            "forward": {"op": "update_device_field", "payload": action_payload},
            "reverse": {"op": "update_device_field", "payload": action_payload},
        }
        await resolve_success(
            "forward",
            entry_id,
            {
                "entry": entry,
                "graph_patch": {
                    "op": "patch_node",
                    "node_id": str(device_uuid),
                    "patch": node_patch,
                },
            },
        )
        return

    await resolve_failure("forward", entry_id, f"Unsupported action: {action_type}")
