"""Support helpers for the topology history toolbar."""

from __future__ import annotations

import html
import json as _json
from collections.abc import Awaitable, Callable

import httpx

from src.utils.logger import logger
from src.utils.settings import settings

HistoryItem = dict[str, object]
HistoryMap = dict[str, HistoryItem]
LayoutBarState = dict[str, object]
AsyncClientFactory = Callable[..., httpx.AsyncClient]
GetLayoutsFn = Callable[..., Awaitable[list[HistoryItem]]]


def to_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def history_label(item: HistoryItem) -> str:
    name = str(item.get("snapshot_name", "Unnamed Version"))
    action = str(item.get("action", "save_version"))
    marker = ""
    if item.get("is_current") is True:
        marker = " (Current)"
    if action == "restore":
        return html.escape(f"{name} [restore]{marker}")
    if action == "backfill":
        return html.escape(f"{name} [legacy]{marker}")
    return html.escape(f"{name}{marker}")


def build_history_map(items: list[HistoryItem]) -> HistoryMap:
    return {
        str(item["id"]): item
        for item in items
        if isinstance(item, dict) and item.get("id") is not None
    }


def normalize_history_selection(raw_value: object, history_items: HistoryMap) -> str | None:
    if not history_items:
        return None

    def _match_candidate(candidate: str) -> str | None:
        trimmed = candidate.strip()
        if not trimmed:
            return None
        if trimmed in history_items:
            return trimmed
        for item_id, item in history_items.items():
            snapshot_name = str(item.get("snapshot_name", "")).strip()
            if trimmed == snapshot_name:
                return item_id
            if trimmed == history_label(item):
                return item_id
        return None

    if isinstance(raw_value, str):
        return _match_candidate(raw_value)

    if isinstance(raw_value, int):
        ordered_ids = list(history_items.keys())
        if 0 <= raw_value < len(ordered_ids):
            return ordered_ids[raw_value]
        return None

    if isinstance(raw_value, dict):
        maybe_id = raw_value.get("id")
        if isinstance(maybe_id, str):
            matched = _match_candidate(maybe_id)
            if matched is not None:
                return matched

        maybe_label = raw_value.get("label")
        if isinstance(maybe_label, str):
            matched = _match_candidate(maybe_label)
            if matched is not None:
                return matched

        maybe_index = raw_value.get("value")
        if isinstance(maybe_index, int):
            return normalize_history_selection(maybe_index, history_items)

    return None


def apply_history_response(state: LayoutBarState, data: HistoryItem) -> None:
    state["current_diagram_id"] = data.get("current_diagram_id")
    state["current_diagram_version"] = to_int(data.get("current_diagram_version"))
    state["draft_version"] = to_int(data.get("draft_version"))
    state["has_unsaved_changes"] = bool(data.get("has_unsaved_changes", False))
    state["selected_history_id"] = str(data.get("history_entry_id", "")) or None


def build_state_sync_js(state: LayoutBarState) -> str:
    has_unsaved_changes = bool(state.get("has_unsaved_changes"))
    return (
        "window._htCurrentDiagramId="
        f"{_json.dumps(state.get('current_diagram_id'))};"
        "window._htDiagramId="
        f"{_json.dumps(state.get('current_diagram_id'))};"
        "window._htDiagramVersion="
        f"{_json.dumps(state.get('current_diagram_version'))};"
        "window._htDraftVersion="
        f"{_json.dumps(state.get('draft_version'))};"
        "window._htHasUnsavedChanges="
        f"{_json.dumps(has_unsaved_changes)};"
        "if(window._htSetDraftStatus) window._htSetDraftStatus("
        f"{_json.dumps(has_unsaved_changes)}"
        ");"
        "else if(window._htUpdateDraftBadge) window._htUpdateDraftBadge();"
    )


def history_items_from_state(state: LayoutBarState) -> HistoryMap:
    history_items = state.get("history_items")
    if not isinstance(history_items, dict):
        return {}
    return {
        str(item_id): item
        for item_id, item in history_items.items()
        if isinstance(item_id, str) and isinstance(item, dict)
    }


async def fetch_history_map(
    token: str,
    topology_id: str,
    get_layouts_fn: GetLayoutsFn,
    async_client_factory: AsyncClientFactory,
) -> HistoryMap:
    if not topology_id:
        return {}
    items = await get_layouts_fn(token, async_client_factory, topology_id=topology_id)
    return build_history_map(items)


def _read_json_dict(response: httpx.Response) -> HistoryItem | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    if isinstance(payload, dict):
        return payload
    return None


async def request_save_version(
    token: str,
    topology_id: str,
    state: LayoutBarState,
    canvas_json: HistoryItem,
    async_client_factory: AsyncClientFactory,
) -> tuple[int, HistoryItem | None]:
    payload: HistoryItem = {
        "cytoscape_json": canvas_json,
        "base_diagram_version": state.get("current_diagram_version"),
    }
    try:
        async with async_client_factory() as client:
            response = await client.post(
                f"{settings.api_base_url}/api/topologies/{topology_id}/save-version",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
    except httpx.HTTPError as exc:
        logger.error("Save version failed: {}", str(exc))
        return 0, None
    if response.status_code != 200:
        return response.status_code, None
    return response.status_code, _read_json_dict(response)


async def request_restore_version(
    token: str,
    topology_id: str,
    history_entry_id: str,
    state: LayoutBarState,
    async_client_factory: AsyncClientFactory,
) -> tuple[int, HistoryItem | None]:
    payload: HistoryItem = {
        "base_diagram_version": state.get("current_diagram_version"),
    }
    try:
        async with async_client_factory() as client:
            response = await client.post(
                f"{settings.api_base_url}/api/topologies/{topology_id}/history/{history_entry_id}/restore",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
    except httpx.HTTPError as exc:
        logger.error("Restore history failed: {}", str(exc))
        return 0, None
    if response.status_code != 200:
        return response.status_code, None
    return response.status_code, _read_json_dict(response)