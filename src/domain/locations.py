"""Location domain logic — pure functions, no I/O.

Only imports standard-library modules and src/models/types.py.
"""
import uuid
from typing import Optional

from src.models.types import LocationType


def validate_location_fields(
    type: LocationType,
    lat: Optional[float],
    lng: Optional[float],
    rack: Optional[str],
    row: Optional[str],
) -> None:
    """Validate that field values are consistent with the location type.

    Raises ValueError with a message matching the acceptance criteria verbatim.
    """
    if type == LocationType.geo:
        if lat is None or lng is None:
            raise ValueError("Geographic locations require lat and lng")
        if rack is not None or row is not None:
            raise ValueError("Geographic locations must not have rack or row")
        if not (-90.0 <= lat <= 90.0):
            raise ValueError("lat must be between -90 and 90")
        if not (-180.0 <= lng <= 180.0):
            raise ValueError("lng must be between -180 and 180")
    elif type == LocationType.rack:
        if lat is not None or lng is not None:
            raise ValueError("Rack locations must not have coordinates")


def detect_cycle(
    location_id: uuid.UUID,
    new_parent_id: uuid.UUID,
    parent_map: dict[uuid.UUID, Optional[uuid.UUID]],
) -> bool:
    """Return True if setting new_parent_id as parent of location_id creates a cycle.

    Walks the parent chain starting from new_parent_id. Returns True if
    location_id is encountered (direct self-loop or indirect cycle). Tracks
    visited nodes to guard against pre-existing corrupt cycles in the tree.
    """
    if new_parent_id == location_id:
        return True

    visited: set[uuid.UUID] = {location_id}
    current: Optional[uuid.UUID] = new_parent_id
    while current is not None:
        if current in visited:
            return True
        visited.add(current)
        current = parent_map.get(current)
    return False


def validate_location_deletable(device_names: list[str]) -> None:
    """Raise ValueError if any devices are assigned to this location.

    Includes the device names in the message, truncated to first 5 with a
    count suffix when there are more than 5.
    """
    n = len(device_names)
    if n == 0:
        return
    shown = device_names[:5]
    names_str = ", ".join(shown)
    if n > 5:
        names_str += f" (and {n - 5} more)"
    raise ValueError(f"Location has {n} device(s) assigned: {names_str}")
