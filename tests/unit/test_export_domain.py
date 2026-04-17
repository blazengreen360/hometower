"""Unit tests for src/domain/export.py — pure mapping logic."""
import uuid
from datetime import datetime, timezone

import pytest

from src.domain.export import (
    EXPORT_VERSION,
    SUPPORTED_VERSIONS,
    validate_export_version,
)
from src.models.export_schema import (
    ExportedConnection,
    ExportedCustomField,
    ExportedDevice,
    ExportedDeviceTag,
    ExportedDiagramLayout,
    ExportedLocation,
    ExportedTag,
    ExportedUser,
)
from src.models.types import ConnectionType, DeviceType, LocationType, Role
from src.services.export_service import build_export_envelope


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dt(year: int = 2024, month: int = 1, day: int = 1) -> datetime:
    return datetime(year, month, day, tzinfo=timezone.utc)


def _device(name: str = "dev", created_at: datetime | None = None) -> ExportedDevice:
    return ExportedDevice(
        id=uuid.uuid4(),
        name=name,
        type=DeviceType.Server,
        ip=None,
        mac=None,
        os=None,
        notes=None,
        location_id=None,
        created_at=created_at or _dt(),
        updated_at=_dt(),
    )


def _user(
    username: str = "user", created_at: datetime | None = None
) -> ExportedUser:
    return ExportedUser(
        id=uuid.uuid4(),
        username=username,
        email=f"{username}@test.local",
        role=Role.Contributor,
        is_active=True,
        created_at=created_at or _dt(),
        updated_at=_dt(),
    )


def _tag(name: str = "tag", created_at: datetime | None = None) -> ExportedTag:
    return ExportedTag(
        id=uuid.uuid4(),
        name=name,
        color="#ff0000",
        created_at=created_at or _dt(),
    )


def _location() -> ExportedLocation:
    return ExportedLocation(
        id=uuid.uuid4(),
        name="rack-1",
        type=LocationType.rack,
        lat=None,
        lng=None,
        rack=None,
        row=None,
        parent_id=None,
        created_at=_dt(),
        updated_at=_dt(),
    )


def _custom_field(device_id: uuid.UUID) -> ExportedCustomField:
    return ExportedCustomField(
        id=uuid.uuid4(),
        device_id=device_id,
        key="cpu",
        value="8-core",
        created_at=_dt(),
        updated_at=_dt(),
    )


def _empty_envelope():
    return build_export_envelope([], [], [], [], [], [], [], [])


# ---------------------------------------------------------------------------
# build_export_envelope — envelope properties
# ---------------------------------------------------------------------------

class TestEnvelopeProperties:
    def test_version_matches_export_version_constant(self) -> None:
        result = _empty_envelope()
        assert result.version == EXPORT_VERSION

    def test_version_is_1_0(self) -> None:
        result = _empty_envelope()
        assert result.version == "1.0"

    def test_exported_at_is_populated(self) -> None:
        result = _empty_envelope()
        assert result.exported_at is not None

    def test_exported_at_is_timezone_aware(self) -> None:
        result = _empty_envelope()
        assert result.exported_at.tzinfo is not None

    def test_empty_inputs_produce_empty_lists(self) -> None:
        result = _empty_envelope()
        assert result.devices == []
        assert result.connections == []
        assert result.locations == []
        assert result.tags == []
        assert result.device_tags == []
        assert result.custom_fields == []
        assert result.diagram_layouts == []
        assert result.users == []


# ---------------------------------------------------------------------------
# build_export_envelope — sorting
# ---------------------------------------------------------------------------

class TestSorting:
    def test_devices_sorted_by_created_at_ascending(self) -> None:
        d_late = _device("late", created_at=_dt(2024, 6, 1))
        d_early = _device("early", created_at=_dt(2024, 1, 1))
        result = build_export_envelope([d_late, d_early], [], [], [], [], [], [], [])
        assert result.devices[0].name == "early"
        assert result.devices[1].name == "late"

    def test_users_sorted_by_created_at_ascending(self) -> None:
        u_late = _user("late", created_at=_dt(2024, 6, 1))
        u_early = _user("early", created_at=_dt(2024, 1, 1))
        result = build_export_envelope([], [], [], [], [], [], [], [u_late, u_early])
        assert result.users[0].username == "early"
        assert result.users[1].username == "late"

    def test_tags_sorted_by_created_at_ascending(self) -> None:
        t_late = _tag("zzz", created_at=_dt(2024, 12, 1))
        t_early = _tag("aaa", created_at=_dt(2024, 1, 1))
        result = build_export_envelope([], [], [], [t_late, t_early], [], [], [], [])
        assert result.tags[0].name == "aaa"
        assert result.tags[1].name == "zzz"


# ---------------------------------------------------------------------------
# ExportedUser — password_hash exclusion
# ---------------------------------------------------------------------------

class TestExportedUser:
    def test_exported_user_type_has_no_password_hash_field(self) -> None:
        assert "password_hash" not in ExportedUser.model_fields

    def test_build_envelope_user_has_no_password_hash_attr(self) -> None:
        u = _user("alice")
        result = build_export_envelope([], [], [], [], [], [], [], [u])
        exported = result.users[0]
        assert not hasattr(exported, "password_hash")

    def test_build_envelope_maps_user_fields_correctly(self) -> None:
        u = _user("bob")
        result = build_export_envelope([], [], [], [], [], [], [], [u])
        exp = result.users[0]
        assert exp.username == "bob"
        assert exp.email == "bob@test.local"
        assert exp.role == Role.Contributor
        assert exp.is_active is True
        assert exp.id == u.id


# ---------------------------------------------------------------------------
# Field mapping correctness
# ---------------------------------------------------------------------------

class TestFieldMapping:
    def test_maps_device_fields(self) -> None:
        d = _device("my-server")
        d.ip = "10.0.0.1"
        d.mac = "AA:BB:CC:DD:EE:FF"
        result = build_export_envelope([d], [], [], [], [], [], [], [])
        exp = result.devices[0]
        assert exp.name == "my-server"
        assert exp.ip == "10.0.0.1"
        assert exp.mac == "AA:BB:CC:DD:EE:FF"
        assert exp.id == d.id
        assert exp.type == DeviceType.Server

    def test_maps_location_fields(self) -> None:
        loc = _location()
        result = build_export_envelope([], [], [loc], [], [], [], [], [])
        exp = result.locations[0]
        assert exp.name == "rack-1"
        assert exp.type == LocationType.rack
        assert exp.id == loc.id

    def test_maps_device_tag_fields(self) -> None:
        device_id = uuid.uuid4()
        tag_id = uuid.uuid4()
        dt = ExportedDeviceTag(device_id=device_id, tag_id=tag_id)
        result = build_export_envelope([], [], [], [], [dt], [], [], [])
        exp = result.device_tags[0]
        assert exp.device_id == device_id
        assert exp.tag_id == tag_id

    def test_maps_custom_field_fields(self) -> None:
        device_id = uuid.uuid4()
        cf = _custom_field(device_id)
        result = build_export_envelope([], [], [], [], [], [cf], [], [])
        exp = result.custom_fields[0]
        assert exp.key == "cpu"
        assert exp.value == "8-core"
        assert exp.device_id == device_id

    def test_maps_diagram_layout_fields(self) -> None:
        dl = ExportedDiagramLayout(
            id=uuid.uuid4(),
            name="main",
            cytoscape_json={"elements": []},
            created_at=_dt(),
            updated_at=_dt(),
        )
        result = build_export_envelope([], [], [], [], [], [], [dl], [])
        exp = result.diagram_layouts[0]
        assert exp.name == "main"
        assert exp.cytoscape_json == {"elements": []}


# ---------------------------------------------------------------------------
# validate_export_version
# ---------------------------------------------------------------------------

class TestValidateExportVersion:
    def test_accepts_version_1_0(self) -> None:
        validate_export_version("1.0")  # must not raise

    def test_raises_value_error_for_unknown_version(self) -> None:
        with pytest.raises(ValueError):
            validate_export_version("2.0")

    def test_raises_value_error_for_empty_string(self) -> None:
        with pytest.raises(ValueError):
            validate_export_version("")

    def test_raises_value_error_for_old_version(self) -> None:
        with pytest.raises(ValueError):
            validate_export_version("0.9")

    def test_supported_versions_contains_1_0(self) -> None:
        assert "1.0" in SUPPORTED_VERSIONS
