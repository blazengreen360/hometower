"""Unit tests for src/domain/locations.py — pure function coverage."""
import uuid
from typing import Optional

import pytest

from src.domain.locations import (
    detect_cycle,
    validate_location_deletable,
    validate_location_fields,
)
from src.models.types import LocationType


# ---------------------------------------------------------------------------
# validate_location_fields
# ---------------------------------------------------------------------------


class TestValidateLocationFieldsGeo:
    def test_valid_geo(self) -> None:
        validate_location_fields(LocationType.geo, 51.5, -0.1, None, None)

    def test_missing_lat_raises(self) -> None:
        with pytest.raises(ValueError, match="Geographic locations require lat and lng"):
            validate_location_fields(LocationType.geo, None, -0.1, None, None)

    def test_missing_lng_raises(self) -> None:
        with pytest.raises(ValueError, match="Geographic locations require lat and lng"):
            validate_location_fields(LocationType.geo, 51.5, None, None, None)

    def test_both_missing_raises(self) -> None:
        with pytest.raises(ValueError, match="Geographic locations require lat and lng"):
            validate_location_fields(LocationType.geo, None, None, None, None)

    def test_geo_with_rack_raises(self) -> None:
        with pytest.raises(ValueError, match="Geographic locations must not have rack or row"):
            validate_location_fields(LocationType.geo, 51.5, -0.1, "A1", None)

    def test_geo_with_row_raises(self) -> None:
        with pytest.raises(ValueError, match="Geographic locations must not have rack or row"):
            validate_location_fields(LocationType.geo, 51.5, -0.1, None, "R1")

    def test_lat_too_low_raises(self) -> None:
        with pytest.raises(ValueError, match="lat must be between -90 and 90"):
            validate_location_fields(LocationType.geo, -90.1, 0.0, None, None)

    def test_lat_too_high_raises(self) -> None:
        with pytest.raises(ValueError, match="lat must be between -90 and 90"):
            validate_location_fields(LocationType.geo, 90.1, 0.0, None, None)

    def test_lng_too_low_raises(self) -> None:
        with pytest.raises(ValueError, match="lng must be between -180 and 180"):
            validate_location_fields(LocationType.geo, 0.0, -180.1, None, None)

    def test_lng_too_high_raises(self) -> None:
        with pytest.raises(ValueError, match="lng must be between -180 and 180"):
            validate_location_fields(LocationType.geo, 0.0, 180.1, None, None)

    def test_boundary_lat_90_valid(self) -> None:
        validate_location_fields(LocationType.geo, 90.0, 0.0, None, None)

    def test_boundary_lat_minus90_valid(self) -> None:
        validate_location_fields(LocationType.geo, -90.0, 0.0, None, None)

    def test_boundary_lng_180_valid(self) -> None:
        validate_location_fields(LocationType.geo, 0.0, 180.0, None, None)


class TestValidateLocationFieldsRack:
    def test_valid_rack_no_optionals(self) -> None:
        validate_location_fields(LocationType.rack, None, None, None, None)

    def test_valid_rack_with_rack_row(self) -> None:
        validate_location_fields(LocationType.rack, None, None, "A1", "Row-1")

    def test_rack_with_lat_raises(self) -> None:
        with pytest.raises(ValueError, match="Rack locations must not have coordinates"):
            validate_location_fields(LocationType.rack, 51.5, None, None, None)

    def test_rack_with_lng_raises(self) -> None:
        with pytest.raises(ValueError, match="Rack locations must not have coordinates"):
            validate_location_fields(LocationType.rack, None, -0.1, None, None)

    def test_rack_with_both_coords_raises(self) -> None:
        with pytest.raises(ValueError, match="Rack locations must not have coordinates"):
            validate_location_fields(LocationType.rack, 51.5, -0.1, None, None)


# ---------------------------------------------------------------------------
# detect_cycle
# ---------------------------------------------------------------------------


class TestDetectCycle:
    def _uid(self) -> uuid.UUID:
        return uuid.uuid4()

    def test_direct_self_loop(self) -> None:
        loc_id = self._uid()
        assert detect_cycle(loc_id, loc_id, {}) is True

    def test_direct_parent_is_self(self) -> None:
        loc_id = self._uid()
        parent_map: dict[uuid.UUID, Optional[uuid.UUID]] = {loc_id: None}
        assert detect_cycle(loc_id, loc_id, parent_map) is True

    def test_no_cycle_single_level(self) -> None:
        loc_id = self._uid()
        proposed_parent = self._uid()
        parent_map: dict[uuid.UUID, Optional[uuid.UUID]] = {proposed_parent: None}
        assert detect_cycle(loc_id, proposed_parent, parent_map) is False

    def test_indirect_cycle(self) -> None:
        # A → B → C and we try to set C's parent to A (creating A→B→C→A)
        a = self._uid()
        b = self._uid()
        c = self._uid()
        parent_map: dict[uuid.UUID, Optional[uuid.UUID]] = {a: None, b: a, c: b}
        # Setting A's parent to C would create a cycle
        assert detect_cycle(a, c, parent_map) is True

    def test_no_cycle_deep_chain(self) -> None:
        # A → B → C → D; setting D's parent to a new node is fine
        a = self._uid()
        b = self._uid()
        c = self._uid()
        d = self._uid()
        new_node = self._uid()
        parent_map: dict[uuid.UUID, Optional[uuid.UUID]] = {
            a: None, b: a, c: b, d: c, new_node: None
        }
        assert detect_cycle(new_node, d, parent_map) is False

    def test_pre_existing_corrupt_cycle_returns_true(self) -> None:
        # Corrupt tree: A → B → A (already cycled in DB)
        a = self._uid()
        b = self._uid()
        c = self._uid()
        parent_map: dict[uuid.UUID, Optional[uuid.UUID]] = {a: b, b: a}
        # Walking from c's proposed parent b will immediately revisit
        assert detect_cycle(c, b, parent_map) is True

    def test_missing_parent_in_map_stops_walk(self) -> None:
        loc_id = self._uid()
        parent_id = self._uid()
        # parent_id not in map → parent_map.get returns None → stops
        parent_map: dict[uuid.UUID, Optional[uuid.UUID]] = {}
        assert detect_cycle(loc_id, parent_id, parent_map) is False


# ---------------------------------------------------------------------------
# validate_location_deletable
# ---------------------------------------------------------------------------


class TestValidateLocationDeletable:
    def test_no_devices_passes(self) -> None:
        validate_location_deletable([])  # should not raise

    def test_single_device_raises(self) -> None:
        with pytest.raises(ValueError, match="Location has 1 device\\(s\\) assigned: server-1"):
            validate_location_deletable(["server-1"])

    def test_multiple_devices_raises(self) -> None:
        names = ["dev-1", "dev-2", "dev-3"]
        with pytest.raises(ValueError, match="Location has 3 device\\(s\\) assigned"):
            validate_location_deletable(names)

    def test_exactly_five_devices_no_suffix(self) -> None:
        names = [f"dev-{i}" for i in range(5)]
        with pytest.raises(ValueError) as exc_info:
            validate_location_deletable(names)
        msg = str(exc_info.value)
        assert "and" not in msg

    def test_six_devices_adds_more_suffix(self) -> None:
        names = [f"dev-{i}" for i in range(6)]
        with pytest.raises(ValueError, match="and 1 more"):
            validate_location_deletable(names)

    def test_ten_devices_truncates_to_five(self) -> None:
        names = [f"dev-{i}" for i in range(10)]
        with pytest.raises(ValueError, match="Location has 10 device\\(s\\) assigned") as exc_info:
            validate_location_deletable(names)
        msg = str(exc_info.value)
        assert "and 5 more" in msg
