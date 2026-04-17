"""Inventory domain — pure filter logic for the inventory list view."""
from dataclasses import dataclass
import re as _re
import uuid
from typing import Protocol, Sequence, TypeVar

from src.models.types import DeviceType

_HEX_COLOR_RE = _re.compile(r'^#[0-9a-fA-F]{6}$')


def normalize_tag_name(name: str) -> str:
    """Return the canonical form of a tag name: stripped and lowercased.

    Used before DB insert to prevent case-duplicate tags.
    """
    return name.strip().lower()


def normalize_custom_field_key(key: str) -> str:
    """Return the canonical form of a custom field key: stripped and lowercased."""
    return key.strip().lower()


def validate_hex_color(color: str) -> str:
    """Raise ValueError if color is not a 6-digit hex string.

    Returns the color unchanged on success.
    """
    if not _HEX_COLOR_RE.match(color):
        raise ValueError(f"Invalid hex color: {color!r}. Expected #RRGGBB format.")
    return color


class HasId(Protocol):
    """Structural protocol for objects that have a UUID id field."""

    @property
    def id(self) -> uuid.UUID: ...


@dataclass(frozen=True)
class CommonTagOption:
    """Tag option derived from intersection across selected devices."""

    id: uuid.UUID
    name: str
    color: str


class TagRenderable(Protocol):
    """Structural protocol for tag-like objects usable in inventory helpers."""

    @property
    def id(self) -> uuid.UUID: ...

    @property
    def name(self) -> str: ...

    @property
    def color(self) -> str: ...


class TaggableInventoryDevice(Protocol):
    """Structural protocol for devices that expose a tags collection."""

    @property
    def tags(self) -> Sequence[TagRenderable]: ...


class FilterableDevice(Protocol):
    """Structural contract for inventory filtering inputs."""

    @property
    def name(self) -> str: ...

    @property
    def ip(self) -> str | None: ...

    @property
    def notes(self) -> str | None: ...

    @property
    def type(self) -> DeviceType: ...

    @property
    def tags(self) -> Sequence[HasId]: ...


TFilterableDevice = TypeVar("TFilterableDevice", bound=FilterableDevice)


def get_common_tags(
    devices: Sequence[TaggableInventoryDevice],
) -> list[CommonTagOption]:
    """Return sorted tag intersection across selected devices.

    Rules:
      - empty selection -> []
      - single selected device -> all tags on that device
      - many devices -> only tags present on every selected device
      - sorted by lowercase name then UUID string for stability
    """
    if not devices:
        return []

    first_device_tags = list(devices[0].tags)
    common_ids = {tag.id for tag in first_device_tags}
    if not common_ids:
        return []

    for device in devices[1:]:
        device_tag_ids = {tag.id for tag in device.tags}
        common_ids.intersection_update(device_tag_ids)
        if not common_ids:
            return []

    first_tag_lookup = {tag.id: tag for tag in first_device_tags}
    common_tags = [
        CommonTagOption(id=tag_id, name=first_tag_lookup[tag_id].name, color=first_tag_lookup[tag_id].color)
        for tag_id in common_ids
        if tag_id in first_tag_lookup
    ]
    common_tags.sort(key=lambda tag: (tag.name.lower(), str(tag.id)))
    return common_tags


def filter_devices(
    devices: list[TFilterableDevice],
    search: str,
    types: set[DeviceType],
    tag_ids: set[uuid.UUID],
) -> list[TFilterableDevice]:
    """Filter inventory devices by search text, type chips, and tag chips.

    Filter semantics (AND across categories, OR within each set):
      - search:   case-insensitive substring match on name, ip, or notes;
                  None fields are treated as empty strings.
      - types:    device.type must be in types; no filter when types is empty.
      - tag_ids:  reserved for HT-006; silently ignored until tags are implemented.

    Returns a new list preserving input order without mutating the input.
    """
    search_lower = search.strip().lower()
    result: list[TFilterableDevice] = []

    for device in devices:
        # Search filter (applied only when non-empty after strip)
        if search_lower:
            hit = (
                search_lower in (device.name or "").lower()
                or search_lower in (device.ip or "").lower()
                or search_lower in (device.notes or "").lower()
            )
            if not hit:
                continue

        # Type filter (OR within set; no-op when set is empty)
        if types and device.type not in types:
            continue

        # Tag filter (OR within set — device must have at least one matching tag)
        if tag_ids:
            device_tag_ids = {t.id for t in device.tags}
            if not device_tag_ids.intersection(tag_ids):
                continue

        result.append(device)

    return result
