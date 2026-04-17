"""Pure topology history helpers for HT-075 ghost placeholder semantics."""
import copy
import uuid

from src.models.types import Role

_GHOST_LABEL_SUFFIX = " (Deleted from inventory)"


def _is_uuid_string(value: object) -> bool:
    try:
        uuid.UUID(str(value))
    except (TypeError, ValueError):
        return False
    return True


def _iter_data_entries(
    cytoscape_json: dict[str, object],
    *,
    want_edges: bool,
) -> list[tuple[dict[str, object], dict[str, object]]]:
    elements = cytoscape_json.get("elements")
    entries: list[tuple[dict[str, object], dict[str, object]]] = []
    key = "edges" if want_edges else "nodes"

    if isinstance(elements, dict):
        raw_items = elements.get(key)
        if not isinstance(raw_items, list):
            return entries
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            data = item.get("data")
            if not isinstance(data, dict):
                continue
            is_edge = data.get("source") is not None or data.get("target") is not None
            if is_edge != want_edges:
                continue
            entries.append((item, data))
        return entries

    if not isinstance(elements, list):
        return entries
    for item in elements:
        if not isinstance(item, dict):
            continue
        data = item.get("data")
        if not isinstance(data, dict):
            continue
        is_edge = data.get("source") is not None or data.get("target") is not None
        if is_edge != want_edges:
            continue
        entries.append((item, data))
    return entries


def _iter_node_entries(cytoscape_json: dict[str, object]) -> list[tuple[dict[str, object], dict[str, object]]]:
    return _iter_data_entries(cytoscape_json, want_edges=False)


def _iter_edge_data(cytoscape_json: dict[str, object]) -> list[dict[str, object]]:
    return [data for _, data in _iter_data_entries(cytoscape_json, want_edges=True)]


def _with_ghost_class(node_entry: dict[str, object]) -> None:
    classes = node_entry.get("classes")
    if isinstance(classes, str):
        parts = [part for part in classes.split(" ") if part]
        if "ghost" not in parts:
            parts.append("ghost")
        node_entry["classes"] = " ".join(parts)
        return
    if isinstance(classes, list):
        parts = [str(part) for part in classes]
        if "ghost" not in parts:
            parts.append("ghost")
        node_entry["classes"] = parts
        return
    node_entry["classes"] = "ghost"


def _without_ghost_class(node_entry: dict[str, object]) -> None:
    classes = node_entry.get("classes")
    if isinstance(classes, str):
        parts = [part for part in classes.split(" ") if part and part != "ghost"]
        if parts:
            node_entry["classes"] = " ".join(parts)
        else:
            node_entry.pop("classes", None)
        return
    if isinstance(classes, list):
        parts = [str(part) for part in classes if str(part) != "ghost"]
        if parts:
            node_entry["classes"] = parts
        else:
            node_entry.pop("classes", None)


def _base_name(data: dict[str, object], fallback_id: str) -> str:
    preferred = data.get("ghost_original_name") or data.get("raw_name") or data.get("label")
    value = str(preferred or "").strip()
    if value.endswith(_GHOST_LABEL_SUFFIX):
        value = value[: -len(_GHOST_LABEL_SUFFIX)]
    return value or f"Deleted device {fallback_id[:8]}"


def _base_type(data: dict[str, object]) -> str:
    preferred = data.get("ghost_original_type") or data.get("raw_device_type") or data.get("device_type")
    value = str(preferred or "").strip()
    return value or "Server"


def extract_missing_device_refs(
    cytoscape_json: dict[str, object],
    live_device_ids: set[str],
) -> list[dict[str, str]]:
    missing: list[dict[str, str]] = []
    for _, data in _iter_node_entries(cytoscape_json):
        raw_id = data.get("id")
        if not _is_uuid_string(raw_id):
            continue
        device_id = str(raw_id)
        if device_id in live_device_ids:
            continue
        missing.append({
            "device_id": device_id,
            "name": _base_name(data, device_id),
            "device_type": _base_type(data),
        })
    return missing


def synthesize_ghost_placeholders(
    cytoscape_json: dict[str, object],
    live_device_ids: set[str],
) -> tuple[dict[str, object], list[dict[str, str]]]:
    result = copy.deepcopy(cytoscape_json)
    missing = extract_missing_device_refs(result, live_device_ids)
    missing_map = {item["device_id"]: item for item in missing}

    for node_entry, data in _iter_node_entries(result):
        raw_id = data.get("id")
        if not _is_uuid_string(raw_id):
            continue
        device_id = str(raw_id)
        details = missing_map.get(device_id)
        if details is None:
            continue

        display_name = details["name"]
        display_type = details["device_type"]
        data["ghost"] = True
        data["ghost_reason"] = "deleted_from_inventory"
        data["ghost_status"] = "Deleted from inventory"
        data["ghost_device_id"] = device_id
        data["ghost_original_name"] = display_name
        data["ghost_original_type"] = display_type
        data["raw_name"] = display_name
        data["raw_device_type"] = display_type
        data["device_type"] = display_type
        data["label"] = f"{display_name}{_GHOST_LABEL_SUFFIX}"
        data["editable"] = False
        _with_ghost_class(node_entry)

    return result, missing


def build_ghost_restore_summary(missing_devices: list[dict[str, str]], role: Role) -> dict[str, object]:
    can_reconcile = role in {Role.Admin, Role.Contributor}
    allowed_actions = ["recreate_as_new_device", "map_to_existing_device"] if can_reconcile else []
    return {
        "ghost_count": len(missing_devices),
        "ghost_device_ids": [device["device_id"] for device in missing_devices],
        "message": "Deleted devices were preserved as ghost placeholders instead of recreated into inventory.",
        "ghost_recovery": {"can_reconcile": can_reconcile, "allowed_actions": allowed_actions},
    }


def get_missing_device_metadata(cytoscape_json: dict[str, object], ghost_device_id: str) -> dict[str, str] | None:
    if not _is_uuid_string(ghost_device_id):
        return None
    for _, data in _iter_node_entries(cytoscape_json):
        if str(data.get("id")) != ghost_device_id:
            continue
        return {
            "device_id": ghost_device_id,
            "name": _base_name(data, ghost_device_id),
            "device_type": _base_type(data),
        }
    return None


def replace_ghost_with_live_device(
    cytoscape_json: dict[str, object],
    ghost_id: str,
    live_device_id: str,
) -> tuple[dict[str, object], bool]:
    result = copy.deepcopy(cytoscape_json)
    changed = False

    for node_entry, data in _iter_node_entries(result):
        if str(data.get("id")) != ghost_id:
            continue

        base_name = _base_name(data, ghost_id)
        data["id"] = live_device_id
        data["label"] = base_name
        data["raw_name"] = base_name
        data.pop("ghost", None)
        data.pop("ghost_reason", None)
        data.pop("ghost_status", None)
        data.pop("ghost_device_id", None)
        data.pop("ghost_original_name", None)
        data.pop("ghost_original_type", None)
        data.pop("editable", None)
        _without_ghost_class(node_entry)
        changed = True

    for edge_data in _iter_edge_data(result):
        if str(edge_data.get("source")) == ghost_id:
            edge_data["source"] = live_device_id
            changed = True
        if str(edge_data.get("target")) == ghost_id:
            edge_data["target"] = live_device_id
            changed = True

    collapsed_nodes = result.get("collapsedNodes")
    if isinstance(collapsed_nodes, list):
        replaced = [live_device_id if str(node_id) == ghost_id else node_id for node_id in collapsed_nodes]
        deduped: list[object] = []
        seen: set[str] = set()
        for node_id in replaced:
            key = str(node_id)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(node_id)
        if deduped != collapsed_nodes:
            result["collapsedNodes"] = deduped
            changed = True

    if not changed:
        return cytoscape_json, False
    return result, True
