"""Canvas data-loading helpers for the topology page.

Extracted from topology.py to keep that file under the 250-line limit.
"""
import httpx

from src.ui.design.tokens import DEVICE_SHAPE_BY_VALUE
from src.utils.logger import logger
from src.utils.settings import settings


async def load_canvas_data(
    token: str,
) -> tuple[list[dict[str, object]], dict[str, object] | None]:
    """Fetch devices and latest diagram layout, return Cytoscape elements + saved layout."""
    headers = {"Authorization": f"Bearer {token}"}
    elements: list[dict[str, object]] = []
    saved_layout: dict[str, object] | None = None

    try:
        async with httpx.AsyncClient() as client:
            devices_resp = await client.get(
                f"{settings.api_base_url}/api/devices/",
                params={"page": 1, "limit": 100},
                headers=headers,
                timeout=5.0,
            )
            if devices_resp.status_code == 200:
                devices = devices_resp.json().get("items", [])
                for device in devices:
                    shape = DEVICE_SHAPE_BY_VALUE.get(device["type"], "rectangle")
                    elements.append({
                        "data": {
                            "id": device["id"],
                            "label": device["name"],
                            "shape": shape,
                            "device_type": device["type"],
                            "ip": device.get("ip", ""),
                            "mac": device.get("mac", ""),
                            "os": device.get("os", ""),
                            "notes": device.get("notes", ""),
                        }
                    })

            connections_resp = await client.get(
                f"{settings.api_base_url}/api/connections/",
                params={"page": 1, "limit": 100},
                headers=headers,
                timeout=5.0,
            )
            if connections_resp.status_code == 200:
                connections = connections_resp.json().get("items", [])
                for conn in connections:
                    elements.append({
                        "group": "edges",
                        "data": {
                            "id": conn["id"],
                            "source": conn["source_id"],
                            "target": conn["target_id"],
                            "label": conn.get("label") or "",
                            "connection_type": conn["type"],
                        }
                    })

            diagrams_resp = await client.get(
                f"{settings.api_base_url}/api/diagrams/",
                headers=headers,
                timeout=5.0,
            )
            if diagrams_resp.status_code == 200:
                items = diagrams_resp.json().get("items", [])
                if items:
                    latest_id = items[0]["id"]
                    detail_resp = await client.get(
                        f"{settings.api_base_url}/api/diagrams/{latest_id}",
                        headers=headers,
                        timeout=5.0,
                    )
                    if detail_resp.status_code == 200:
                        saved_layout = detail_resp.json().get("cytoscape_json")
    except httpx.HTTPError as exc:
        logger.error("Canvas data load failed: {error}", error=str(exc))

    # Merge saved positions into device-derived elements so the preset layout
    # has coordinates for each node.
    if saved_layout and isinstance(saved_layout, dict) and "elements" in saved_layout:
        raw = saved_layout["elements"]
        if isinstance(raw, dict):
            saved_nodes = raw.get("nodes", [])
        elif isinstance(raw, list):
            saved_nodes = raw
        else:
            saved_nodes = []
        position_map: dict[str, dict[str, object]] = {}
        for node in saved_nodes:
            if isinstance(node, dict) and "data" in node and "position" in node:
                node_data = node["data"]
                node_pos = node["position"]
                if isinstance(node_data, dict) and isinstance(node_pos, dict):
                    node_id = node_data.get("id")
                    if node_id:
                        position_map[str(node_id)] = node_pos
        for elem in elements:
            elem_data = elem.get("data")
            if isinstance(elem_data, dict):
                elem_id = elem_data.get("id")
                if elem_id and str(elem_id) in position_map:
                    elem["position"] = position_map[str(elem_id)]

    return elements, saved_layout
