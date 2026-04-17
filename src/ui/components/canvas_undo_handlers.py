"""Python-side API execution bridge for canvas undo/redo actions (HT-032)."""

from __future__ import annotations

import json

import httpx
from nicegui import ui

from src.ui.components.canvas_undo_action_dispatch import handle_canvas_action_request
from src.ui.components.canvas_undo_handler_utils import as_dict
from src.ui.components.canvas_undo_operation_dispatch import handle_canvas_undo_request
from src.utils.logger import logger
from src.utils.settings import settings


_EDITOR_ROLES = {"Admin", "Contributor"}


def register_canvas_undo_handlers(token: str, user_role: str) -> None:
    """Register ui.on handlers for canvas action requests and undo/redo requests."""
    can_write = user_role in _EDITOR_ROLES

    async def _resolve_success(direction: str, entry_id: str, payload: dict[str, object]) -> None:
        script = (
            "if(window._htResolveUndoApiSuccess)"
            f"window._htResolveUndoApiSuccess({json.dumps(direction)}, {json.dumps(entry_id)}, {json.dumps(payload)});"
        )
        await ui.run_javascript(script)

    async def _resolve_failure(direction: str, entry_id: str, message: str) -> None:
        script = (
            "if(window._htResolveUndoApiFailure)"
            f"window._htResolveUndoApiFailure({json.dumps(direction)}, {json.dumps(entry_id)}, {json.dumps(message)});"
        )
        await ui.run_javascript(script)

    async def _call_api(
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
    ) -> httpx.Response:
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                f"{settings.api_base_url}{path}",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0,
            )
        return response

    async def _on_canvas_action_request(event: object) -> None:
        args = as_dict(getattr(event, "args", None))
        await handle_canvas_action_request(
            args=args,
            can_write=can_write,
            token=token,
            resolve_success=_resolve_success,
            resolve_failure=_resolve_failure,
            call_api=_call_api,
        )

    async def _on_canvas_undo_request(event: object) -> None:
        args = as_dict(getattr(event, "args", None))
        await handle_canvas_undo_request(
            args=args,
            can_write=can_write,
            token=token,
            resolve_success=_resolve_success,
            resolve_failure=_resolve_failure,
            call_api=_call_api,
        )

    ui.on("ht_canvas_action_request", _on_canvas_action_request)
    ui.on("ht_canvas_undo_request", _on_canvas_undo_request)
    logger.debug("Registered canvas undo handlers for role={}", user_role)
