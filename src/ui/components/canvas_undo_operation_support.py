"""Helper handlers for undo/redo canvas undo-bridge operations."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from src.ui.components.canvas_undo_dispatch_types import CallApi, ResolveFailure
from src.ui.components.canvas_undo_dispatch_types import ResolveSuccess
from src.ui.components.canvas_undo_handler_utils import (
    as_dict,
    graph_edge_payload,
    response_detail,
)
from src.ui.components.canvas_undo_operation_device_support import (
    handle_delete_published_device_operation,
    handle_reparent_device_operation,
    handle_restore_published_device_operation,
    handle_update_device_field_operation,
)

UndoHandler = Callable[
    [str, dict[str, object], dict[str, object], str, ResolveSuccess, ResolveFailure, CallApi],
    Awaitable[None],
]


def recreated_edge_entry_patch(
    entry: dict[str, object],
    edge_payload: dict[str, object],
) -> dict[str, object]:
    forward = as_dict(entry.get("forward"))
    reverse = as_dict(entry.get("reverse"))
    return {
        "forward": {"op": str(forward.get("op", "")) or "delete_published_edge", "payload": edge_payload},
        "reverse": {"op": str(reverse.get("op", "")) or "create_published_edge", "payload": edge_payload},
    }


async def handle_create_published_edge_operation(
    direction: str,
    entry: dict[str, object],
    payload: dict[str, object],
    _token: str,
    resolve_success: ResolveSuccess,
    resolve_failure: ResolveFailure,
    call_api: CallApi,
) -> None:
    entry_id = str(entry.get("entry_id", ""))
    response = await call_api(
        "POST",
        "/api/connections/",
        {
            "source_id": payload.get("source_id"),
            "target_id": payload.get("target_id"),
            "type": payload.get("connection_type", "Ethernet"),
            "label": payload.get("label"),
        },
    )
    if response.status_code != 201:
        await resolve_failure(direction, entry_id, response_detail(response))
        return

    edge_payload = graph_edge_payload(as_dict(response.json()))
    await resolve_success(
        direction,
        entry_id,
        {
            "entry_patch": recreated_edge_entry_patch(entry, edge_payload),
            "graph_patch": {"op": "add_edge", "edge": edge_payload},
        },
    )


async def handle_delete_published_edge_operation(
    direction: str,
    entry: dict[str, object],
    payload: dict[str, object],
    _token: str,
    resolve_success: ResolveSuccess,
    resolve_failure: ResolveFailure,
    call_api: CallApi,
) -> None:
    entry_id = str(entry.get("entry_id", ""))
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


OPERATION_HANDLERS: dict[str, UndoHandler] = {
    "create_published_edge": handle_create_published_edge_operation,
    "delete_published_edge": handle_delete_published_edge_operation,
    "delete_published_device": handle_delete_published_device_operation,
    "restore_published_device": handle_restore_published_device_operation,
    "update_device_field": handle_update_device_field_operation,
    "reparent_device": handle_reparent_device_operation,
}