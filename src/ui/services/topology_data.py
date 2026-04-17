"""Canvas data-loading for the topology page.

Extracted from topology.py to keep that file under the 250-line limit.
Pure helpers live in topology_data_helpers.py.
"""
import html

import httpx

from src.ui.design.tokens import DEVICE_SHAPE_BY_VALUE
from src.ui.services.topology_data_helpers import (
    _elem_has_parent,  # noqa: F401 — re-exported for callers
    _extract_published_ids,
    _safe_text,
    _topological_sort_elements,
    apply_collapsed_state,
    merge_saved_layout,
    prune_orphaned_draft_layout,
)
from src.ui.services.topology_data_support import (
    _decorate_editor_state_layout,
    _elements_from_saved_layout,
    _fetch_editor_state,
    _fetch_saved_layout,
)
from src.ui.services.topology_network_summaries import load_network_summaries
from src.utils.logger import logger
from src.utils.settings import settings


async def load_canvas_data(
    token: str,
    layout_id: str = "",
    topology_id: str = "",
) -> tuple[list[dict[str, object]], dict[str, object] | None]:
    """Fetch devices and latest diagram layout, return Cytoscape elements + saved layout."""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        elements: list[dict[str, object]] = []
        saved_layout: dict[str, object] | None = None
        device_ids: set[str] = set()

        async with httpx.AsyncClient() as client:
            if topology_id:
                editor_state = await _fetch_editor_state(client, headers, topology_id)
                if editor_state is None:
                    return [], None
                saved_layout = _decorate_editor_state_layout(editor_state)
                if saved_layout is None:
                    logger.warning("Canvas data load failed: editor-state payload missing cytoscape_json")
                    return [], None
                elements = _elements_from_saved_layout(saved_layout)
                return elements, saved_layout

            page_limit = 100

            # 1. Fetch saved layout FIRST so we know which devices to include
            saved_layout = await _fetch_saved_layout(
                client,
                headers,
                layout_id,
                topology_id,
            )
            prune_orphaned_draft_layout(saved_layout)

            # If a specific layout was requested but not found, fail early
            if layout_id and saved_layout is None:
                return [], None

            # 2. Determine which published IDs are placed on this View
            has_layout = saved_layout is not None
            published_ids = _extract_published_ids(saved_layout)

            # 3. Fetch devices (paginated)
            devices: list[dict[str, object]] = []
            devices_page = 1
            while True:
                devices_resp = await client.get(
                    f"{settings.api_base_url}/api/devices/",
                    params={"page": devices_page, "limit": page_limit, "include": "networks"},
                    headers=headers,
                    timeout=5.0,
                )
                if devices_resp.status_code != 200:
                    logger.warning(
                        "Canvas data load failed: devices request returned status={status}",
                        status=devices_resp.status_code,
                    )
                    return [], None

                raw_device_items = devices_resp.json().get("items", [])
                device_page_items: list[dict[str, object]] = []
                if isinstance(raw_device_items, list):
                    for item in raw_device_items:
                        if isinstance(item, dict):
                            device_page_items.append(item)
                devices.extend(device_page_items)
                if len(device_page_items) < page_limit:
                    break
                devices_page += 1

            # 4. Build elements — only for placed devices when layout exists
            for device in devices:
                device_type = _safe_text(device.get("type", ""))
                device_name = _safe_text(device.get("name", ""))
                device_id = str(device["id"])
                # Skip devices not placed on this View (opt-in loading)
                if has_layout and device_id not in published_ids:
                    continue
                device_ids.add(device_id)
                shape = DEVICE_SHAPE_BY_VALUE.get(device_type, "rectangle")
                raw_version = device.get("version", 1)
                device_version = int(raw_version) if isinstance(raw_version, (int, str)) else 1
                device_elem_data: dict[str, object] = {
                    "id": device_id,
                    "label": html.escape(device_name),
                    "raw_name": device_name,
                    "shape": shape,
                    "device_type": html.escape(device_type),
                    "raw_device_type": device_type,
                    "version": device_version,
                    "status": html.escape(_safe_text(device.get("status", "Active"))),
                    "ip": html.escape(_safe_text(device.get("ip", ""))),
                    "mac": html.escape(_safe_text(device.get("mac", ""))),
                    "os": html.escape(_safe_text(device.get("os", ""))),
                    "notes": html.escape(_safe_text(device.get("notes", ""))),
                }
                raw_parent = device.get("parent_id")
                if raw_parent is not None:
                    device_elem_data["parent"] = str(raw_parent)

                memberships: list[dict[str, str]] = []
                raw_networks = device.get("networks", [])
                if isinstance(raw_networks, list):
                    for raw_net in raw_networks:
                        if not isinstance(raw_net, dict):
                            continue
                        network_id = str(raw_net.get("network_id", ""))
                        if not network_id:
                            continue
                        memberships.append(
                            {
                                "network_id": network_id,
                                "name": _safe_text(raw_net.get("name", "")),
                                "color": _safe_text(raw_net.get("color", "")),
                                "ip_address": _safe_text(raw_net.get("ip_address", "")),
                            }
                        )
                device_elem_data["network_memberships"] = memberships
                elements.append({"data": device_elem_data})

            elements = _topological_sort_elements(elements)

            # 5. Fetch connections and filter for placed devices
            connections: list[dict[str, object]] = []
            connections_page = 1
            while True:
                connections_resp = await client.get(
                    f"{settings.api_base_url}/api/connections/",
                    params={"page": connections_page, "limit": page_limit},
                    headers=headers,
                    timeout=5.0,
                )
                if connections_resp.status_code != 200:
                    logger.warning(
                        "Canvas data load failed: connections request returned status={status}",
                        status=connections_resp.status_code,
                    )
                    return [], None

                raw_connection_items = connections_resp.json().get("items", [])
                connection_page_items: list[dict[str, object]] = []
                if isinstance(raw_connection_items, list):
                    for item in raw_connection_items:
                        if isinstance(item, dict):
                            connection_page_items.append(item)
                connections.extend(connection_page_items)
                if len(connection_page_items) < page_limit:
                    break
                connections_page += 1

            for conn in connections:
                src_id = str(conn.get("source_id", ""))
                tgt_id = str(conn.get("target_id", ""))
                if has_layout and (src_id not in device_ids or tgt_id not in device_ids):
                    continue
                conn_label = _safe_text(conn.get("label") or "")
                elements.append({
                    "group": "edges",
                    "data": {
                        "id": conn["id"],
                        "source": src_id,
                        "target": tgt_id,
                        "label": html.escape(conn_label),
                        "raw_label": conn_label,
                        "connection_type": html.escape(_safe_text(conn.get("type", ""))),
                    }
                })
        merge_saved_layout(elements, saved_layout, device_ids)
        apply_collapsed_state(elements, saved_layout)
        return elements, saved_layout
    except (httpx.HTTPError, httpx.TimeoutException, KeyError, ValueError) as exc:
        logger.error("Canvas data load failed: {error}", error=str(exc))
        return [], None
