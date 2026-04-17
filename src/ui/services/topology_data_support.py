"""Internal fetch and transform helpers for topology canvas data loading."""

import httpx

from src.ui.services.topology_data_helpers import _topological_sort_elements
from src.utils.logger import logger
from src.utils.settings import settings


def _elements_from_saved_layout(saved_layout: dict[str, object]) -> list[dict[str, object]]:
    """Extract Cytoscape elements from saved-layout JSON in list or dict format."""
    raw_elements = saved_layout.get("elements")
    nodes: list[dict[str, object]] = []
    edges: list[dict[str, object]] = []

    if isinstance(raw_elements, list):
        for entry in raw_elements:
            if not isinstance(entry, dict):
                continue
            entry_data = entry.get("data")
            if not isinstance(entry_data, dict):
                continue
            entry_group = entry.get("group")
            if entry_group == "edges" or (
                entry_data.get("source") is not None and entry_data.get("target") is not None
            ):
                edge_entry = dict(entry)
                edge_entry.setdefault("group", "edges")
                edges.append(edge_entry)
                continue
            node_entry = dict(entry)
            node_entry.pop("group", None)
            nodes.append(node_entry)
    elif isinstance(raw_elements, dict):
        raw_nodes = raw_elements.get("nodes", [])
        raw_edges = raw_elements.get("edges", [])
        if isinstance(raw_nodes, list):
            for entry in raw_nodes:
                if isinstance(entry, dict):
                    node_entry = dict(entry)
                    node_entry.pop("group", None)
                    nodes.append(node_entry)
        if isinstance(raw_edges, list):
            for entry in raw_edges:
                if not isinstance(entry, dict):
                    continue
                edge_entry = dict(entry)
                edge_entry.setdefault("group", "edges")
                edges.append(edge_entry)

    return _topological_sort_elements(nodes + edges)


def _decorate_editor_state_layout(editor_state: dict[str, object]) -> dict[str, object] | None:
    """Attach editor-state metadata to the returned layout for JS bridge usage."""
    raw_layout = editor_state.get("cytoscape_json")
    if not isinstance(raw_layout, dict):
        return None
    saved_layout = dict(raw_layout)
    saved_layout["_editor_state_source"] = str(editor_state.get("source", ""))
    saved_layout["_has_unsaved_changes"] = bool(editor_state.get("has_unsaved_changes", False))
    saved_layout["_current_diagram_id"] = editor_state.get("current_diagram_id")
    saved_layout["_current_diagram_version"] = editor_state.get("current_diagram_version")
    saved_layout["_draft_version"] = editor_state.get("draft_version")
    return saved_layout


async def _fetch_saved_layout(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    layout_id: str,
    topology_id: str,
) -> dict[str, object] | None:
    """Fetch the saved diagram layout from the API."""
    if layout_id:
        detail_resp = await client.get(
            f"{settings.api_base_url}/api/diagrams/{layout_id}",
            headers=headers,
            timeout=5.0,
        )
        if detail_resp.status_code == 200:
            return detail_resp.json().get("cytoscape_json")  # type: ignore[no-any-return]
        logger.warning(
            "Canvas data load failed: diagram detail request returned status={status}",
            status=detail_resp.status_code,
        )
        return None

    params: dict[str, str | int] = {"limit": 1}
    if topology_id:
        params["topology_id"] = topology_id

    diagrams_resp = await client.get(
        f"{settings.api_base_url}/api/diagrams/",
        params=params,
        headers=headers,
        timeout=5.0,
    )
    if diagrams_resp.status_code != 200:
        logger.warning(
            "Canvas data load failed: diagrams request returned status={status}",
            status=diagrams_resp.status_code,
        )
        return None

    items = diagrams_resp.json().get("items", [])
    if topology_id and isinstance(items, list):
        items = [
            item for item in items if isinstance(item, dict) and str(item.get("topology_id", "")) == topology_id
        ]
    if not items:
        return None

    latest_id = items[0]["id"]
    detail_resp = await client.get(
        f"{settings.api_base_url}/api/diagrams/{latest_id}",
        headers=headers,
        timeout=5.0,
    )
    if detail_resp.status_code != 200:
        logger.warning(
            "Canvas data load failed: diagram detail request returned status={status}",
            status=detail_resp.status_code,
        )
        return None
    return detail_resp.json().get("cytoscape_json")  # type: ignore[no-any-return]


async def _fetch_editor_state(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    topology_id: str,
) -> dict[str, object] | None:
    """Fetch topology-centric editor state for HT-072 history/draft workflows."""
    response = await client.get(
        f"{settings.api_base_url}/api/topologies/{topology_id}/editor-state",
        headers=headers,
        timeout=5.0,
    )
    if response.status_code != 200:
        logger.warning(
            "Canvas data load failed: editor-state request returned status={status}",
            status=response.status_code,
        )
        return None
    payload = response.json()
    if isinstance(payload, dict):
        return payload
    return None