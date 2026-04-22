"""Dispatch for undo/redo operations routed through API bridge (HT-032)."""

from __future__ import annotations

from src.ui.components.canvas_undo_handler_utils import as_dict
from src.ui.components.canvas_undo_operation_support import OPERATION_HANDLERS, CallApi
from src.ui.components.canvas_undo_operation_support import ResolveFailure, ResolveSuccess


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

    handler = OPERATION_HANDLERS.get(op)
    if handler is None:
        await resolve_failure(direction, entry_id, f"Unsupported operation: {op}")
        return

    await handler(direction, entry, payload, token, resolve_success, resolve_failure, call_api)
