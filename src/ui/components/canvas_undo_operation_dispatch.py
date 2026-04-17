"""Dispatch for undo/redo operations routed through API bridge (HT-032)."""

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


def _entry_patch_for_recreated_edge(
    entry: dict[str, object],
    edge_payload: dict[str, object],
) -> dict[str, object]:
    forward = as_dict(entry.get("forward"))
    reverse = as_dict(entry.get("reverse"))
    forward_op = str(forward.get("op", "")) or "delete_published_edge"
    reverse_op = str(reverse.get("op", "")) or "create_published_edge"
    return {
        "forward": {"op": forward_op, "payload": edge_payload},
        "reverse": {"op": reverse_op, "payload": edge_payload},
    }


async def handle_canvas_undo_request(
    *,
    args: dict[str, object],
    can_write: bool,
    token: str,
    resolve_success: ResolveSuccess,
    resolve_failure: ResolveFailure,
    call_api: CallApi,
) -> None:
    direction = str(args.get("direction", ""))
    entry = as_dict(args.get("entry"))
    entry_id = str(entry.get("entry_id", ""))

    if not can_write:
        await resolve_failure(direction, entry_id, "Forbidden")
        return

    op_block = as_dict(entry.get("reverse" if direction == "undo" else "forward"))
    op = str(op_block.get("op", ""))
    payload = as_dict(op_block.get("payload"))

    if op == "create_published_edge":
        create_payload = {
            "source_id": payload.get("source_id"),
            "target_id": payload.get("target_id"),
            "type": payload.get("connection_type", "Ethernet"),
            "label": payload.get("label"),
        }
        response = await call_api("POST", "/api/connections/", create_payload)
        if response.status_code != 201:
            await resolve_failure(direction, entry_id, response_detail(response))
            return

        created = as_dict(response.json())
        edge_payload = graph_edge_payload(created)
        await resolve_success(
            direction,
            entry_id,
            {
                "entry_patch": _entry_patch_for_recreated_edge(entry, edge_payload),
                "graph_patch": {"op": "add_edge", "edge": edge_payload},
            },
        )
        return

    if op == "delete_published_edge":
        connection_id = str(payload.get("connection_id", ""))
        response = await call_api("DELETE", f"/api/connections/{connection_id}", None)
        if response.status_code not in {204, 404}:
            await resolve_failure(direction, entry_id, response_detail(response))
            return

        await resolve_success(
            direction,
            entry_id,
            {"graph_patch": {"op": "remove_edge", "connection_id": connection_id}},
        )
        return

    if op == "delete_published_device":
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
                "modified_diagrams": body.get("modified_diagrams", []),
            },
        )
        return

    if op == "restore_published_device":
        device_id = str(payload.get("device_id", ""))
        snapshot = as_dict(payload.get("snapshot"))
        active_diagram_id = payload.get("active_diagram_id")
        response = await call_api("POST", f"/api/devices/{device_id}/restore", snapshot)
        if response.status_code != 200:
            await resolve_failure(direction, entry_id, response_detail(response))
            return

        body = as_dict(response.json())
        node_set = node_set_from_snapshot(
            snapshot,
            as_dict(payload.get("active_node")),
            active_diagram_id,
        )
        await resolve_success(
            direction,
            entry_id,
            {
                "graph_patch": {"op": "restore_node_set", "snapshot": node_set},
                "modified_diagrams": body.get("modified_diagrams", []),
            },
        )
        return

    if op == "update_device_field":
        device_uuid = to_uuid(payload.get("device_id"))
        field = str(payload.get("field", ""))
        if device_uuid is None or not field:
            await resolve_failure(direction, entry_id, "Invalid device field payload")
            return

        before = payload.get("before")
        after = payload.get("after")
        target_value = before if direction == "undo" else after
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
            "before": before,
            "after": after,
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
                "graph_patch": {
                    "op": "patch_node",
                    "node_id": str(device_uuid),
                    "patch": node_patch,
                },
            },
        )
        return

    await resolve_failure(direction, entry_id, f"Unsupported operation: {op}")
