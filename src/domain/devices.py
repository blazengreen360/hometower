"""Device domain logic — pure functions, no I/O.

Only imports standard-library modules. No SQLModel, FastAPI, or network calls.
"""
import copy
import ipaddress
import re
import uuid
from typing import Optional

_MAC_RE = re.compile(r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$')


def validate_mac(mac: Optional[str]) -> Optional[str]:
    """Return normalized (uppercase) MAC or None. Raise ValueError if invalid format."""
    if mac is None:
        return None
    mac = mac.strip()
    if not _MAC_RE.match(mac):
        raise ValueError("Invalid MAC address format")
    return mac.upper()


def validate_ip(ip: Optional[str]) -> Optional[str]:
    """Return ip or None. Raise ValueError if invalid format."""
    if ip is None:
        return None

    ip = ip.strip()
    try:
        ipaddress.ip_address(ip)
    except ValueError as exc:
        raise ValueError("Invalid IP address format") from exc

    return ip


def _element_data(element: object) -> dict[str, object]:
    if not isinstance(element, dict):
        return {}
    data = element.get("data")
    if not isinstance(data, dict):
        return {}
    return data


def _element_is_device_node(element: object, device_id_str: str) -> bool:
    data = _element_data(element)
    if str(data.get("id", "")) != device_id_str:
        return False
    return "source" not in data and "target" not in data


def _element_references_device(element: object, device_id_str: str) -> bool:
    data = _element_data(element)
    if _element_is_device_node(element, device_id_str):
        return True
    if str(data.get("source", "")) == device_id_str:
        return True
    if str(data.get("target", "")) == device_id_str:
        return True
    return False


def _collapsed_without_device(
    collapsed_nodes: object,
    device_id_str: str,
) -> tuple[list[object] | None, bool]:
    if not isinstance(collapsed_nodes, list):
        return None, False
    filtered = [cid for cid in collapsed_nodes if str(cid) != device_id_str]
    return filtered, len(filtered) != len(collapsed_nodes)


def filter_device_from_cytoscape_json(
    cytoscape_json: dict[str, object],
    device_id_str: str,
) -> tuple[dict[str, object], bool]:
    """Remove node/edge elements and collapsed-state references for *device_id_str*.

    Returns (updated_json, was_modified).  Pure function — no I/O.
    """
    elements = cytoscape_json.get("elements")
    result = dict(cytoscape_json)
    changed = False

    if isinstance(elements, list):
        filtered = [el for el in elements if not _element_references_device(el, device_id_str)]
        if len(filtered) != len(elements):
            result["elements"] = filtered
            changed = True
    elif isinstance(elements, dict):
        nodes = elements.get("nodes")
        edges = elements.get("edges")
        if isinstance(nodes, list) and isinstance(edges, list):
            filtered_nodes = [node for node in nodes if not _element_is_device_node(node, device_id_str)]
            filtered_edges = [edge for edge in edges if not _element_references_device(edge, device_id_str)]
            if len(filtered_nodes) != len(nodes) or len(filtered_edges) != len(edges):
                rebuilt = dict(elements)
                rebuilt["nodes"] = filtered_nodes
                rebuilt["edges"] = filtered_edges
                result["elements"] = rebuilt
                changed = True

    collapsed_nodes, collapsed_changed = _collapsed_without_device(
        cytoscape_json.get("collapsedNodes"),
        device_id_str,
    )
    if collapsed_changed and collapsed_nodes is not None:
        result["collapsedNodes"] = collapsed_nodes
        changed = True

    if not changed:
        return cytoscape_json, False
    return result, True


def device_in_cytoscape_json(
    cytoscape_json: dict[str, object],
    device_id_str: str,
) -> bool:
    """Return True if *device_id_str* appears as a node in the cytoscape JSON."""
    elements = cytoscape_json.get("elements")
    if isinstance(elements, list):
        for el in elements:
            if _element_is_device_node(el, device_id_str):
                return True
        return False
    if isinstance(elements, dict):
        nodes = elements.get("nodes")
        if not isinstance(nodes, list):
            return False
        for node in nodes:
            if _element_is_device_node(node, device_id_str):
                return True
    return False


def extract_device_view_snapshot(
    cytoscape_json: dict[str, object],
    device_id_str: str,
) -> tuple[dict[str, object] | None, bool]:
    """Return (node_snapshot, was_collapsed) for a placed device."""
    collapsed_nodes = cytoscape_json.get("collapsedNodes")
    was_collapsed = (
        isinstance(collapsed_nodes, list)
        and any(str(collapsed_id) == device_id_str for collapsed_id in collapsed_nodes)
    )

    elements = cytoscape_json.get("elements")
    if isinstance(elements, list):
        for element in elements:
            if _element_is_device_node(element, device_id_str):
                return copy.deepcopy(element), was_collapsed
        return None, was_collapsed

    if isinstance(elements, dict):
        nodes = elements.get("nodes")
        if not isinstance(nodes, list):
            return None, was_collapsed
        for node in nodes:
            if _element_is_device_node(node, device_id_str):
                return copy.deepcopy(node), was_collapsed
        return None, was_collapsed

    return None, was_collapsed


def restore_device_to_cytoscape_json(
    cytoscape_json: dict[str, object],
    node_snapshot: dict[str, object],
    was_collapsed: bool,
) -> tuple[dict[str, object], bool]:
    """Reinsert a node element and collapsed-state marker if missing."""
    node_data = node_snapshot.get("data")
    if not isinstance(node_data, dict):
        return cytoscape_json, False
    node_id_raw = node_data.get("id")
    if node_id_raw is None:
        return cytoscape_json, False
    node_id = str(node_id_raw)

    if device_in_cytoscape_json(cytoscape_json, node_id):
        return cytoscape_json, False

    result = dict(cytoscape_json)
    restored_node = copy.deepcopy(node_snapshot)
    elements = cytoscape_json.get("elements")

    if isinstance(elements, list):
        restored_elements = list(elements)
        restored_elements.append(restored_node)
        result["elements"] = restored_elements
    elif isinstance(elements, dict):
        nodes = elements.get("nodes")
        if not isinstance(nodes, list):
            return cytoscape_json, False
        restored_elements_dict = dict(elements)
        restored_nodes = list(nodes)
        restored_nodes.append(restored_node)
        restored_elements_dict["nodes"] = restored_nodes
        result["elements"] = restored_elements_dict
    else:
        result["elements"] = [restored_node]

    if was_collapsed:
        collapsed_nodes = cytoscape_json.get("collapsedNodes")
        if isinstance(collapsed_nodes, list):
            if not any(str(collapsed_id) == node_id for collapsed_id in collapsed_nodes):
                restored_collapsed = list(collapsed_nodes)
                restored_collapsed.append(node_id)
                result["collapsedNodes"] = restored_collapsed
        else:
            result["collapsedNodes"] = [node_id]

    return result, True


def validate_device_no_children(child_count: int) -> None:
    """Raise ValueError if device has child devices in a containment hierarchy.

    HT-021: a device acting as a container cannot be deleted until its
    children are removed or reassigned. The message text is taken verbatim
    from the acceptance criteria.
    """
    if child_count > 0:
        raise ValueError(
            "Device has child devices — remove or reassign them first"
        )


def detect_parent_cycle(
    device_id: uuid.UUID,
    new_parent_id: uuid.UUID,
    parent_map: dict[uuid.UUID, Optional[uuid.UUID]],
) -> bool:
    """Return True if setting new_parent_id as parent of device_id creates a cycle.

    HT-021: mirrors src/domain/locations.py::detect_cycle. Walks the parent
    chain from new_parent_id upward; returns True if device_id is encountered
    (direct self-loop or indirect cycle). Tracks visited nodes to guard against
    pre-existing corrupt cycles in the tree.
    """
    if new_parent_id == device_id:
        return True

    visited: set[uuid.UUID] = {device_id}
    current: Optional[uuid.UUID] = new_parent_id
    while current is not None:
        if current in visited:
            return True
        visited.add(current)
        current = parent_map.get(current)
    return False


def generate_copy_name(original_name: str, existing_names: list[str]) -> str:
    """Return a unique copy name for *original_name* that does not collide with *existing_names*.

    Returns ``"{name} (copy)"`` for the first copy, then ``"{name} (copy 2)"``,
    ``"{name} (copy 3)"``, etc.

    Args:
        original_name: The source device's name.
        existing_names: All current device names in the inventory.

    Returns:
        A name string guaranteed not to appear in *existing_names*.
    """
    existing_set = set(existing_names)
    candidate = f"{original_name} (copy)"
    if candidate not in existing_set:
        return candidate
    n = 2
    while True:
        candidate = f"{original_name} (copy {n})"
        if candidate not in existing_set:
            return candidate
        n += 1
