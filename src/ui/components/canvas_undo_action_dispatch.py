"""Dispatch for forward canvas actions routed through undo/redo API bridge (HT-032)."""

from __future__ import annotations

from src.ui.components.canvas_undo_action_support import ACTION_HANDLERS, CallApi
from src.ui.components.canvas_undo_action_support import ResolveFailure, ResolveSuccess
from src.ui.components.canvas_undo_handler_utils import as_dict


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

    handler = ACTION_HANDLERS.get(action_type)
    if handler is None:
        await resolve_failure("forward", entry_id, f"Unsupported action: {action_type}")
        return

    await handler(entry_id, payload, token, resolve_success, resolve_failure, call_api)
