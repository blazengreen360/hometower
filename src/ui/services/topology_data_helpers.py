"""Pure helper functions for topology canvas data loading."""
from collections import deque

from src.utils.logger import logger

def _is_draft_data(data: dict[str, object]) -> bool:
    nid = str(data.get("id", ""))
    return nid.startswith("draft-") or bool(data.get("draft") or data.get("draft_edge"))


def _extract_published_ids(saved_layout: dict[str, object] | None) -> set[str]:
    """Extract published (non-draft) device IDs from cytoscape_json elements."""
    if not saved_layout:
        return set()
    raw = saved_layout.get("elements", {})
    nodes: list[dict[str, object]] = []
    if isinstance(raw, dict):
        nodes = raw.get("nodes", [])  # type: ignore[assignment]
    elif isinstance(raw, list):
        nodes = [n for n in raw if isinstance(n, dict) and n.get("group") != "edges"]

    ids: set[str] = set()
    for node in nodes:
        if not isinstance(node, dict):
            continue
        data = node.get("data")
        if not isinstance(data, dict):
            continue
        if _is_draft_data(data):
            continue
        nid = str(data.get("id", ""))
        if nid:
            ids.add(nid)
    return ids
def _extract_draft_elements(saved_layout: dict[str, object] | None) -> list[dict[str, object]]:
    """Extract draft device elements from cytoscape_json for direct rendering."""
    if not saved_layout:
        return []
    raw = saved_layout.get("elements", {})
    all_elems: list[dict[str, object]] = []
    if isinstance(raw, dict):
        for group_list in raw.values():
            if isinstance(group_list, list):
                all_elems.extend(
                    item for item in group_list if isinstance(item, dict)
                )
    elif isinstance(raw, list):
        all_elems = [n for n in raw if isinstance(n, dict)]

    drafts: list[dict[str, object]] = []
    for elem in all_elems:
        data = elem.get("data")
        if not isinstance(data, dict):
            continue
        if _is_draft_data(data):
            drafts.append(elem)
    return drafts
def prune_orphaned_draft_layout(saved_layout: dict[str, object] | None) -> int:
    """Remove draft nodes/edges from a saved layout and record cleanup metadata."""
    if not saved_layout:
        return 0

    raw = saved_layout.get("elements")
    pruned_nodes = 0
    pruned_any = False

    def _keep(elem: object) -> bool:
        nonlocal pruned_nodes, pruned_any
        if not isinstance(elem, dict):
            return False
        data = elem.get("data")
        if not isinstance(data, dict):
            return True
        if not _is_draft_data(data):
            return True
        pruned_any = True
        if not data.get("draft_edge") and str(data.get("id", "")).startswith("draft-"):
            pruned_nodes += 1
        return False

    if isinstance(raw, dict):
        nodes = raw.get("nodes", [])
        edges = raw.get("edges", [])
        if isinstance(nodes, list):
            raw["nodes"] = [node for node in nodes if _keep(node)]
        if isinstance(edges, list):
            raw["edges"] = [edge for edge in edges if _keep(edge)]
    elif isinstance(raw, list):
        saved_layout["elements"] = [elem for elem in raw if _keep(elem)]

    if pruned_any:
        saved_layout["_draft_cleanup_required"] = True
        saved_layout["_draft_pruned_count"] = pruned_nodes
    return pruned_nodes
def _safe_text(value: object) -> str:
    return "" if value is None else str(value)


def _elem_has_parent(elem: dict[str, object]) -> bool:
    data = elem.get("data")
    return isinstance(data, dict) and "parent" in data


def _topological_sort_elements(
    elements: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Sort elements so parent nodes appear before children and edges stay last."""
    nodes: list[dict[str, object]] = []
    others: list[dict[str, object]] = []
    for elem in elements:
        if elem.get("group") == "edges":
            others.append(elem)
        else:
            nodes.append(elem)

    by_id: dict[str, dict[str, object]] = {}
    children_map: dict[str, list[str]] = {}
    in_degree: dict[str, int] = {}

    for node in nodes:
        node_data = node.get("data", {})
        if isinstance(node_data, dict):
            nid = str(node_data.get("id", ""))
            by_id[nid] = node
            children_map[nid] = []
            in_degree[nid] = 0

    for node in nodes:
        node_data = node.get("data", {})
        if isinstance(node_data, dict):
            nid = str(node_data.get("id", ""))
            parent = node_data.get("parent")
            if parent is not None and str(parent) in by_id:
                children_map[str(parent)].append(nid)
                in_degree[nid] += 1

    queue: deque[str] = deque(nid for nid, deg in in_degree.items() if deg == 0)
    sorted_nodes: list[dict[str, object]] = []
    while queue:
        nid = queue.popleft()
        sorted_nodes.append(by_id[nid])
        for child_id in children_map[nid]:
            in_degree[child_id] -= 1
            if in_degree[child_id] == 0:
                queue.append(child_id)

    if len(sorted_nodes) < len(nodes):
        sorted_ids: set[str] = set()
        for n in sorted_nodes:
            n_data = n.get("data")
            if isinstance(n_data, dict):
                sorted_ids.add(str(n_data.get("id", "")))
        for nid, node in by_id.items():
            if nid not in sorted_ids:
                sorted_nodes.append(node)

    return sorted_nodes + others


def merge_saved_layout(
    elements: list[dict[str, object]],
    saved_layout: dict[str, object] | None,
    device_ids: set[str],
) -> None:
    if not (saved_layout and isinstance(saved_layout, dict) and "elements" in saved_layout):
        return

    filtered_saved_nodes: list[dict[str, object]] = []
    stale_nodes_filtered = 0

    raw = saved_layout["elements"]
    if isinstance(raw, dict):
        saved_nodes = raw.get("nodes", [])
        if isinstance(saved_nodes, list):
            for node in saved_nodes:
                if not isinstance(node, dict):
                    continue
                node_data = node.get("data")
                node_id = node_data.get("id") if isinstance(node_data, dict) else None
                if node_id is None:
                    continue
                if str(node_id) in device_ids:
                    filtered_saved_nodes.append(node)
                else:
                    stale_nodes_filtered += 1
        raw["nodes"] = filtered_saved_nodes
    elif isinstance(raw, list):
        retained_elements: list[object] = []
        for elem in raw:
            if not isinstance(elem, dict):
                retained_elements.append(elem)
                continue

            elem_group = elem.get("group")
            # Legacy list format treats missing group as node entries.
            if elem_group not in (None, "nodes"):
                retained_elements.append(elem)
                continue

            node_data = elem.get("data")
            node_id = node_data.get("id") if isinstance(node_data, dict) else None
            if node_id is None:
                retained_elements.append(elem)
                continue

            if str(node_id) in device_ids:
                filtered_saved_nodes.append(elem)
                retained_elements.append(elem)
            else:
                stale_nodes_filtered += 1

        saved_layout["elements"] = retained_elements

    if stale_nodes_filtered > 0:
        logger.debug("Filtered stale nodes from saved layout: count={count}", count=stale_nodes_filtered)

    position_map: dict[str, dict[str, object]] = {}
    classes_map: dict[str, str] = {}
    for node in filtered_saved_nodes:
        if isinstance(node, dict) and "data" in node:
            node_data = node["data"]
            if isinstance(node_data, dict):
                node_id = node_data.get("id")
                if node_id:
                    node_pos = node.get("position")
                    if isinstance(node_pos, dict):
                        position_map[str(node_id)] = node_pos
                    node_classes = node.get("classes")
                    if node_classes and isinstance(node_classes, str):
                        classes_map[str(node_id)] = node_classes

    for elem in elements:
        elem_data = elem.get("data")
        if isinstance(elem_data, dict):
            elem_id = elem_data.get("id")
            if elem_id:
                str_id = str(elem_id)
                if str_id in position_map:
                    elem["position"] = position_map[str_id]
                    elem_data["_positioned"] = True
                if str_id in classes_map:
                    elem["classes"] = classes_map[str_id]


def apply_collapsed_state(
    elements: list[dict[str, object]],
    saved_layout: dict[str, object] | None,
) -> None:
    if not (saved_layout and isinstance(saved_layout, dict)):
        return
    collapsed_ids = saved_layout.get("collapsedNodes", [])
    if isinstance(collapsed_ids, list) and collapsed_ids:
        collapsed_set = {str(cid) for cid in collapsed_ids if cid}
        for elem in elements:
            elem_data = elem.get("data")
            if isinstance(elem_data, dict):
                elem_id = elem_data.get("id")
                if elem_id and str(elem_id) in collapsed_set:
                    elem_data["_collapsed"] = True
