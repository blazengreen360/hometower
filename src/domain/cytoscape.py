"""Pure helpers for extracting placed device identifiers from Cytoscape payloads."""
import uuid
from collections.abc import Mapping


def extract_device_ids(cytoscape_json: object) -> set[uuid.UUID]:
    if not isinstance(cytoscape_json, Mapping):
        return set()

    elements = cytoscape_json.get("elements")
    if isinstance(elements, Mapping):
        candidates = elements.get("nodes")
    else:
        candidates = elements
    if not isinstance(candidates, list):
        return set()

    device_ids: set[uuid.UUID] = set()
    for element in candidates:
        if not isinstance(element, Mapping):
            continue
        group = element.get("group")
        if group is not None and group != "nodes":
            continue
        data = element.get("data")
        if not isinstance(data, Mapping):
            continue
        if "source" in data or "target" in data:
            continue
        candidate = data.get("device_id", data.get("id"))
        if candidate is None:
            continue
        try:
            device_ids.add(uuid.UUID(str(candidate)))
        except ValueError:
            continue
    return device_ids