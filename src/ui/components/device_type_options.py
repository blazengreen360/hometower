"""Shared device-type option helpers for UI creation/edit flows."""

from src.models.types import DeviceType

_DEPRECATED_CREATION_TYPES = {DeviceType.VLAN, DeviceType.Subnet}


def get_creatable_device_types() -> list[DeviceType]:
    """Return device types allowed in creation affordances."""
    return [device_type for device_type in DeviceType if device_type not in _DEPRECATED_CREATION_TYPES]


def get_editable_device_type_values(current_type: DeviceType | str | None = None) -> list[str]:
    """Return type values for edit forms, preserving legacy types when already set."""
    options = [device_type.value for device_type in get_creatable_device_types()]
    normalized_current: DeviceType | None
    if isinstance(current_type, str):
        try:
            normalized_current = DeviceType(current_type)
        except ValueError:
            normalized_current = None
    else:
        normalized_current = current_type

    if normalized_current in _DEPRECATED_CREATION_TYPES and normalized_current.value not in options:
        options.append(normalized_current.value)
    return options
