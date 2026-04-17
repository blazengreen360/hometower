"""Unit tests for DeviceStatus enum and device model status field (HT-039)."""
import pytest

from src.models.types import DeviceStatus


class TestDeviceStatusEnum:
    def test_has_five_values(self) -> None:
        assert len(DeviceStatus) == 5

    def test_active_exists(self) -> None:
        assert DeviceStatus.Active == "Active"

    def test_offline_exists(self) -> None:
        assert DeviceStatus.Offline == "Offline"

    def test_maintenance_exists(self) -> None:
        assert DeviceStatus.Maintenance == "Maintenance"

    def test_planned_exists(self) -> None:
        assert DeviceStatus.Planned == "Planned"

    def test_decommissioned_exists(self) -> None:
        assert DeviceStatus.Decommissioned == "Decommissioned"

    def test_is_str_enum(self) -> None:
        assert isinstance(DeviceStatus.Active, str)


class TestDeviceModelStatus:
    def test_device_base_has_status_field(self) -> None:
        from src.models.device import DeviceBase
        from src.models.types import DeviceType

        device = DeviceBase(name="test", type=DeviceType.Server)
        assert hasattr(device, "status")

    def test_device_base_default_status_is_active(self) -> None:
        from src.models.device import DeviceBase
        from src.models.types import DeviceType

        device = DeviceBase(name="test", type=DeviceType.Server)
        assert device.status == DeviceStatus.Active

    def test_device_base_explicit_status_maintenance(self) -> None:
        from src.models.device import DeviceBase
        from src.models.types import DeviceType

        device = DeviceBase(
            name="test", type=DeviceType.Server, status=DeviceStatus.Maintenance
        )
        assert device.status == DeviceStatus.Maintenance

    def test_device_update_status_is_optional(self) -> None:
        from src.models.device import DeviceUpdate

        update = DeviceUpdate(version=1)
        assert update.status is None

    def test_device_update_accepts_status_change(self) -> None:
        from src.models.device import DeviceUpdate

        update = DeviceUpdate(status=DeviceStatus.Offline, version=1)
        assert update.status == DeviceStatus.Offline

    def test_device_response_includes_status(self) -> None:
        """DeviceResponse must inherit status from DeviceBase."""
        from src.models.device import DeviceResponse
        import uuid
        from datetime import datetime, timezone

        dr = DeviceResponse(
            id=uuid.uuid4(),
            name="test",
            type="Server",
            version=1,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        assert dr.status == DeviceStatus.Active
