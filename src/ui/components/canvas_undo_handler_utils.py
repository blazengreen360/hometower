"""Shared helper utilities for canvas undo/redo API dispatch (HT-032)."""

from __future__ import annotations

import uuid

import httpx

from src.utils.settings import settings


def as_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def response_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"HTTP {response.status_code}"
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str) and detail:
            return detail
    return f"HTTP {response.status_code}"


def graph_edge_payload(connection: dict[str, object]) -> dict[str, object]:
    return {
        "connection_id": connection.get("id"),
        "source_id": connection.get("source_id"),
        "target_id": connection.get("target_id"),
        "connection_type": connection.get("type", "Ethernet"),
        "label": connection.get("label"),
    }


def _placement_node_for_diagram(
    placements: object,
    active_diagram_id: object | None,
) -> dict[str, object] | None:
    if not isinstance(placements, list):
        return None

    active_id_str = str(active_diagram_id or "")
    if active_id_str:
        for row in placements:
            placement = as_dict(row)
            if str(placement.get("diagram_id", "")) != active_id_str:
                continue
            node = placement.get("node")
            if isinstance(node, dict):
                return node

    for row in placements:
        placement = as_dict(row)
        node = placement.get("node")
        if isinstance(node, dict):
            return node

    return None


def node_set_from_snapshot(
    snapshot: dict[str, object],
    fallback: dict[str, object] | None,
    active_diagram_id: object | None,
) -> dict[str, object]:
    if isinstance(fallback, dict) and isinstance(fallback.get("nodes"), list):
        return fallback

    first_node = _placement_node_for_diagram(
        snapshot.get("placements"),
        active_diagram_id,
    )

    edges: list[dict[str, object]] = []
    connections = snapshot.get("connections")
    if isinstance(connections, list):
        for row in connections:
            connection = as_dict(row)
            edges.append(
                {
                    "group": "edges",
                    "data": {
                        "id": connection.get("id"),
                        "source": connection.get("source_id"),
                        "target": connection.get("target_id"),
                        "connection_type": connection.get("type", "Ethernet"),
                        "raw_label": connection.get("label"),
                        "label": connection.get("label") or "",
                    },
                }
            )

    return {
        "nodes": [first_node] if isinstance(first_node, dict) else [],
        "edges": edges,
    }


def to_uuid(value: object) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def to_int(value: object, default: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


async def fetch_current_device_version(
    token: str,
    *,
    device_id: uuid.UUID,
    fallback: int,
) -> int:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.api_base_url}/api/devices/{device_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
        )
    if response.status_code != 200:
        return fallback

    body = as_dict(response.json())
    return to_int(body.get("version", fallback), fallback)


async def apply_undoable_device_field_patch(
    token: str,
    *,
    device_id: uuid.UUID,
    field: str,
    after: object,
    version_cursor: int,
) -> tuple[bool, int]:
    """Apply a PATCH-backed device-field change and return (ok, new_version)."""
    payload: dict[str, object] = {field: after, "version": version_cursor}
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"{settings.api_base_url}/api/devices/{device_id}",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
        )
    if response.status_code != 200:
        return False, version_cursor

    body = as_dict(response.json())
    new_version_raw = body.get("version", version_cursor)
    new_version = to_int(new_version_raw, version_cursor)
    return True, new_version
