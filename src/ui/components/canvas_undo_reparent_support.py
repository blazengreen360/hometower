"""Shared helpers for canvas undo reparent payload updates."""

from __future__ import annotations

import uuid

from src.ui.components.canvas_undo_dispatch_types import CallApi
from src.ui.components.canvas_undo_handler_utils import as_dict
from src.ui.components.canvas_undo_handler_utils import response_detail
from src.ui.components.canvas_undo_handler_utils import to_int


def reparent_graph_patch(
    *,
    device_id: str,
    parent_id: object,
    rendered_position: object,
    version_cursor: int,
) -> dict[str, object]:
    return {
        "op": "reparent_node",
        "node_id": device_id,
        "parent_id": parent_id,
        "rendered_position": rendered_position,
        "version": version_cursor,
    }


def updated_reparent_payload(
    payload: dict[str, object],
    *,
    device_id: str,
    version_cursor: object,
) -> dict[str, object]:
    updated_payload = dict(payload)
    updated_payload["device_id"] = device_id
    updated_payload["version_cursor"] = to_int(version_cursor, to_int(payload.get("version_cursor", 1), 1))
    return updated_payload


def _normalize_parent_id(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


async def _fetch_current_reparent_state(
    call_api: CallApi,
    *,
    device_id: uuid.UUID,
    fallback_version: int,
) -> tuple[str | None, int] | None:
    response = await call_api("GET", f"/api/devices/{device_id}", None)
    if response.status_code != 200:
        return None

    body = as_dict(response.json())
    return (
        _normalize_parent_id(body.get("parent_id")),
        to_int(body.get("version", fallback_version), fallback_version),
    )


async def apply_reparent_with_conflict_recovery(
    *,
    call_api: CallApi,
    device_id: uuid.UUID,
    target_parent: object,
    version_cursor: int,
) -> tuple[bool, int, str | None]:
    target_parent_id = _normalize_parent_id(target_parent)
    response = await call_api(
        "PATCH",
        f"/api/devices/{device_id}",
        {"parent_id": target_parent, "version": version_cursor},
    )
    if response.status_code == 200:
        body = as_dict(response.json())
        return True, to_int(body.get("version", version_cursor), version_cursor), None
    if response.status_code != 409:
        return False, version_cursor, response_detail(response)

    current_state = await _fetch_current_reparent_state(
        call_api,
        device_id=device_id,
        fallback_version=version_cursor,
    )
    if current_state is None:
        return False, version_cursor, response_detail(response)

    current_parent_id, current_version = current_state
    if current_parent_id == target_parent_id:
        return True, current_version, None

    retry_response = await call_api(
        "PATCH",
        f"/api/devices/{device_id}",
        {"parent_id": target_parent, "version": current_version},
    )
    if retry_response.status_code == 200:
        body = as_dict(retry_response.json())
        return True, to_int(body.get("version", current_version), current_version), None

    if retry_response.status_code == 409:
        retry_state = await _fetch_current_reparent_state(
            call_api,
            device_id=device_id,
            fallback_version=current_version,
        )
        if retry_state is not None:
            retry_parent_id, retry_version = retry_state
            if retry_parent_id == target_parent_id:
                return True, retry_version, None
            current_version = retry_version

    return False, current_version, response_detail(retry_response)