"""Unit tests for device container features (HT-021).

Covers topological_sort_devices and import parent-ref validation.
"""
import uuid
from datetime import datetime, timezone

import pytest

from src.domain.export import topological_sort_devices
from src.models.export_schema import ExportedDevice, ExportSchema
from src.models.types import DeviceType
from src.services.import_validation import (
    ImportPayloadValidationError,
    validate_device_parent_refs,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _dev(
    dev_id: uuid.UUID | None = None,
    parent_id: uuid.UUID | None = None,
    name: str = "dev",
) -> ExportedDevice:
    return ExportedDevice(
        id=dev_id or uuid.uuid4(),
        name=name,
        type=DeviceType.Server,
        ip=None,
        mac=None,
        os=None,
        notes=None,
        location_id=None,
        parent_id=parent_id,
        created_at=_now(),
        updated_at=_now(),
    )


def _payload(devices: list[ExportedDevice]) -> ExportSchema:
    return ExportSchema(
        version="1.0",
        exported_at=_now(),
        devices=devices,
        connections=[],
        locations=[],
        tags=[],
        device_tags=[],
        custom_fields=[],
        diagram_layouts=[],
        services=[],
        service_dependencies=[],
        users=[],
    )


# ---------------------------------------------------------------------------
# topological_sort_devices
# ---------------------------------------------------------------------------


class TestTopologicalSortDevices:
    def test_empty_list_returns_empty(self) -> None:
        assert topological_sort_devices([]) == []

    def test_single_root_device(self) -> None:
        dev = _dev()
        assert topological_sort_devices([dev]) == [dev]

    def test_all_roots_pass_through(self) -> None:
        devs = [_dev() for _ in range(4)]
        result = topological_sort_devices(devs)
        assert len(result) == 4

    def test_child_appears_after_parent(self) -> None:
        parent_id = uuid.uuid4()
        child_id = uuid.uuid4()
        parent = _dev(parent_id, name="parent")
        child = _dev(child_id, parent_id=parent_id, name="child")
        # Supply child first to force reordering
        result = topological_sort_devices([child, parent])
        ids = [d.id for d in result]
        assert ids.index(parent_id) < ids.index(child_id)

    def test_three_level_hierarchy(self) -> None:
        a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        result = topological_sort_devices(
            [_dev(c, parent_id=b), _dev(b, parent_id=a), _dev(a)]
        )
        ids = [d.id for d in result]
        assert ids.index(a) < ids.index(b)
        assert ids.index(b) < ids.index(c)

    def test_cycle_raises_value_error(self) -> None:
        a, b = uuid.uuid4(), uuid.uuid4()
        with pytest.raises(ValueError, match="circular_device_reference"):
            topological_sort_devices([_dev(a, parent_id=b), _dev(b, parent_id=a)])

    def test_external_parent_id_treated_as_root(self) -> None:
        """A device whose parent_id is not in the list is treated as a root."""
        external = uuid.uuid4()
        dev = _dev(parent_id=external)
        result = topological_sort_devices([dev])
        assert len(result) == 1


# ---------------------------------------------------------------------------
# validate_device_parent_refs
# ---------------------------------------------------------------------------


class TestValidateDeviceParentRefs:
    def test_none_parent_ids_pass(self) -> None:
        payload = _payload([_dev(), _dev()])
        validate_device_parent_refs(payload)  # must not raise

    def test_valid_parent_ref_passes(self) -> None:
        parent_id = uuid.uuid4()
        child_id = uuid.uuid4()
        parent = _dev(parent_id)
        child = _dev(child_id, parent_id=parent_id)
        payload = _payload([parent, child])
        validate_device_parent_refs(payload)  # must not raise

    def test_dangling_parent_id_raises(self) -> None:
        dangling_parent = uuid.uuid4()
        child = _dev(parent_id=dangling_parent)
        payload = _payload([child])
        with pytest.raises(ImportPayloadValidationError, match="parent_id"):
            validate_device_parent_refs(payload)

    def test_empty_devices_passes(self) -> None:
        payload = _payload([])
        validate_device_parent_refs(payload)  # must not raise
