"""Pure Cytoscape helpers for device placement snapshots and filtering."""
import copy


def _element_data(element: object) -> dict[str, object]:
    if not isinstance(element, dict):
        return {}
    data = element.get("data")
    if not isinstance(data, dict):
        return {}
    return data


def _element_node_id(element: object) -> str | None:
    node_id = _element_data(element).get("id")
    if node_id is None:
        return None
    return str(node_id)


def _element_device_id(element: object) -> str | None:
    data = _element_data(element)
    candidate = data.get("device_id", data.get("id"))
    if candidate is None:
        return None
    return str(candidate)


def _element_is_device_node(element: object, device_id_str: str) -> bool:
    data = _element_data(element)
    if _element_device_id(element) != device_id_str:
        return False
    return "source" not in data and "target" not in data


def _matching_device_node_ids(elements: object, device_id_str: str) -> set[str]:
    candidates = elements.get("nodes") if isinstance(elements, dict) else elements
    if not isinstance(candidates, list):
        return set()
    return {
        node_id
        for element in candidates
        if _element_is_device_node(element, device_id_str)
        for node_id in [_element_node_id(element)]
        if node_id is not None
    }


def _element_references_node_ids(element: object, node_ids: set[str]) -> bool:
    data = _element_data(element)
    if str(data.get("source", "")) in node_ids:
        return True
    if str(data.get("target", "")) in node_ids:
        return True
    return False


def _collapsed_without_device(
    collapsed_nodes: object,
    node_ids: set[str],
) -> tuple[list[object] | None, bool]:
    if not isinstance(collapsed_nodes, list):
        return None, False
    filtered = [cid for cid in collapsed_nodes if str(cid) not in node_ids]
    return filtered, len(filtered) != len(collapsed_nodes)


def _collapsed_contains(collapsed_nodes: object, node_ids: set[str]) -> bool:
    return isinstance(collapsed_nodes, list) and any(
        str(collapsed_id) in node_ids for collapsed_id in collapsed_nodes
    )


def filter_device_from_cytoscape_json(
    cytoscape_json: dict[str, object],
    device_id_str: str,
) -> tuple[dict[str, object], bool]:
    """Remove node/edge elements and collapsed-state references for *device_id_str*."""
    elements = cytoscape_json.get("elements")
    result = dict(cytoscape_json)
    changed = False
    removed_node_ids = _matching_device_node_ids(elements, device_id_str)
    reference_ids = {device_id_str, *removed_node_ids}

    if isinstance(elements, list):
        filtered = [
            el
            for el in elements
            if not _element_is_device_node(el, device_id_str)
            and not _element_references_node_ids(el, reference_ids)
        ]
        if len(filtered) != len(elements):
            result["elements"] = filtered
            changed = True
    elif isinstance(elements, dict):
        nodes = elements.get("nodes")
        edges = elements.get("edges")
        if isinstance(nodes, list) and isinstance(edges, list):
            filtered_nodes = [
                node for node in nodes if not _element_is_device_node(node, device_id_str)
            ]
            filtered_edges = [
                edge for edge in edges if not _element_references_node_ids(edge, reference_ids)
            ]
            if len(filtered_nodes) != len(nodes) or len(filtered_edges) != len(edges):
                rebuilt = dict(elements)
                rebuilt["nodes"] = filtered_nodes
                rebuilt["edges"] = filtered_edges
                result["elements"] = rebuilt
                changed = True

    collapsed_nodes, collapsed_changed = _collapsed_without_device(
        cytoscape_json.get("collapsedNodes"),
        reference_ids,
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
    fallback_collapsed = _collapsed_contains(collapsed_nodes, {device_id_str})

    elements = cytoscape_json.get("elements")
    if isinstance(elements, list):
        for element in elements:
            if _element_is_device_node(element, device_id_str):
                node_ids = {device_id_str}
                node_id = _element_node_id(element)
                if node_id is not None:
                    node_ids.add(node_id)
                return copy.deepcopy(element), _collapsed_contains(collapsed_nodes, node_ids)
        return None, fallback_collapsed

    if isinstance(elements, dict):
        nodes = elements.get("nodes")
        if not isinstance(nodes, list):
            return None, fallback_collapsed
        for node in nodes:
            if _element_is_device_node(node, device_id_str):
                node_ids = {device_id_str}
                node_id = _element_node_id(node)
                if node_id is not None:
                    node_ids.add(node_id)
                return copy.deepcopy(node), _collapsed_contains(collapsed_nodes, node_ids)
        return None, fallback_collapsed

    return None, fallback_collapsed


def restore_device_to_cytoscape_json(
    cytoscape_json: dict[str, object],
    node_snapshot: dict[str, object],
    was_collapsed: bool,
) -> tuple[dict[str, object], bool]:
    """Reinsert a node element and collapsed-state marker if missing."""
    node_id = _element_node_id(node_snapshot)
    device_id = _element_device_id(node_snapshot)
    if node_id is None or device_id is None:
        return cytoscape_json, False

    if device_in_cytoscape_json(cytoscape_json, device_id):
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
        collapsed_ids = {node_id, device_id}
        if isinstance(collapsed_nodes, list):
            if not any(str(collapsed_id) in collapsed_ids for collapsed_id in collapsed_nodes):
                restored_collapsed = list(collapsed_nodes)
                restored_collapsed.append(node_id)
                result["collapsedNodes"] = restored_collapsed
        else:
            result["collapsedNodes"] = [node_id]

    return result, True