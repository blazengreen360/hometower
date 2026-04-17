"""Export domain logic — pure functions, no I/O."""

from collections import deque
from collections.abc import Mapping
from typing import Protocol, TypeVar, cast
from uuid import UUID

EXPORT_VERSION = "1.0"
SUPPORTED_VERSIONS = {"1.0"}


class LocationWithParent(Protocol):
    """Duck-typed location object used for topology ordering."""

    id: UUID
    parent_id: UUID | None


LocationLike = LocationWithParent | Mapping[str, UUID | None]
LocationT = TypeVar("LocationT", bound=LocationLike)


def _location_id(location: LocationLike) -> UUID:
    if isinstance(location, Mapping):
        return cast(UUID, location["id"])
    return location.id


def _location_parent_id(location: LocationLike) -> UUID | None:
    if isinstance(location, Mapping):
        return cast(UUID | None, location.get("parent_id"))
    return location.parent_id


def topological_sort_locations(locations: list[LocationT]) -> list[LocationT]:
    """Return locations sorted so every parent appears before its children.

    Uses Kahn's algorithm (BFS topological sort). Locations whose parent_id
    is not present in the input list are treated as roots.

    Raises:
        ValueError("circular_location_reference"): if a cycle is detected.
    """
    by_id: dict[UUID, LocationT] = {}
    children: dict[UUID, list[UUID]] = {}
    in_degree: dict[UUID, int] = {}

    for loc in locations:
        loc_id = _location_id(loc)
        by_id[loc_id] = loc
        children[loc_id] = []
        in_degree[loc_id] = 0

    for loc in locations:
        loc_id = _location_id(loc)
        parent_id = _location_parent_id(loc)
        if parent_id is not None and parent_id in by_id:
            children[parent_id].append(loc_id)
            in_degree[loc_id] += 1

    queue: deque[UUID] = deque(
        lid for lid, deg in in_degree.items() if deg == 0
    )
    result: list[LocationT] = []

    while queue:
        lid = queue.popleft()
        result.append(by_id[lid])
        for child_id in children[lid]:
            in_degree[child_id] -= 1
            if in_degree[child_id] == 0:
                queue.append(child_id)

    if len(result) != len(locations):
        raise ValueError("circular_location_reference")

    return result


class DeviceWithParent(Protocol):
    """Duck-typed device object used for topology ordering."""

    id: UUID
    parent_id: UUID | None


DeviceLike = DeviceWithParent | Mapping[str, UUID | None]
DeviceT = TypeVar("DeviceT", bound=DeviceLike)


def _device_id(device: DeviceLike) -> UUID:
    if isinstance(device, Mapping):
        return cast(UUID, device["id"])
    return device.id


def _device_parent_id(device: DeviceLike) -> UUID | None:
    if isinstance(device, Mapping):
        return cast(UUID | None, device.get("parent_id"))
    return device.parent_id


def topological_sort_devices(devices: list[DeviceT]) -> list[DeviceT]:
    """Return devices sorted so every parent appears before its children.

    Uses Kahn's algorithm. Raises ValueError("circular_device_reference") on cycles.
    """
    by_id: dict[UUID, DeviceT] = {}
    children: dict[UUID, list[UUID]] = {}
    in_degree: dict[UUID, int] = {}

    for dev in devices:
        dev_id = _device_id(dev)
        by_id[dev_id] = dev
        children[dev_id] = []
        in_degree[dev_id] = 0

    for dev in devices:
        dev_id = _device_id(dev)
        parent_id = _device_parent_id(dev)
        if parent_id is not None and parent_id in by_id:
            children[parent_id].append(dev_id)
            in_degree[dev_id] += 1

    queue: deque[UUID] = deque(did for did, deg in in_degree.items() if deg == 0)
    result: list[DeviceT] = []

    while queue:
        did = queue.popleft()
        result.append(by_id[did])
        for child_id in children[did]:
            in_degree[child_id] -= 1
            if in_degree[child_id] == 0:
                queue.append(child_id)

    if len(result) != len(devices):
        raise ValueError("circular_device_reference")

    return result


def validate_export_version(version: str) -> None:
    """Raise ValueError if version is not in SUPPORTED_VERSIONS."""
    if version not in SUPPORTED_VERSIONS:
        raise ValueError(f"unsupported_version: {version!r}")


