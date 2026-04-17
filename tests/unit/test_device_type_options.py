"""Unit tests for UI device type option helpers."""

from src.models.types import DeviceType
from src.ui.components.device_type_options import (
    get_creatable_device_types,
    get_editable_device_type_values,
)


class TestDeviceTypeOptions:
    def test_creatable_types_exclude_deprecated_vlan_and_subnet(self) -> None:
        creatable = get_creatable_device_types()
        assert DeviceType.Server in creatable
        assert DeviceType.VLAN not in creatable
        assert DeviceType.Subnet not in creatable

    def test_editable_values_default_exclude_deprecated_types(self) -> None:
        options = get_editable_device_type_values()
        assert DeviceType.Server.value in options
        assert DeviceType.VLAN.value not in options
        assert DeviceType.Subnet.value not in options

    def test_editable_values_include_legacy_type_when_current_is_deprecated(self) -> None:
        vlan_options = get_editable_device_type_values(DeviceType.VLAN)
        subnet_options = get_editable_device_type_values(DeviceType.Subnet.value)
        assert DeviceType.VLAN.value in vlan_options
        assert DeviceType.Subnet.value in subnet_options
