"""Device domain logic — pure functions, no I/O.

Only imports standard-library modules. No SQLModel, FastAPI, or network calls.
"""
import ipaddress
import re
import uuid
from typing import Optional

from src.domain.device_cytoscape import device_in_cytoscape_json
from src.domain.device_cytoscape import extract_device_view_snapshot
from src.domain.device_cytoscape import filter_device_from_cytoscape_json
from src.domain.device_cytoscape import restore_device_to_cytoscape_json

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
