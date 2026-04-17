"""Unit tests for import-related domain functions (HT-013)."""
import uuid
from datetime import datetime, timezone

import pytest

from src.domain.export import topological_sort_locations, validate_export_version
from src.models.export_schema import ExportedLocation
from src.models.types import LocationType


def _loc(loc_id: uuid.UUID, parent_id: uuid.UUID | None = None) -> ExportedLocation:
    now = datetime.now(timezone.utc)
    return ExportedLocation(
        id=loc_id,
        name="loc",
        type=LocationType.rack,
        parent_id=parent_id,
        created_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# validate_export_version
# ---------------------------------------------------------------------------


class TestValidateExportVersion:
    def test_version_1_0_is_accepted(self) -> None:
        validate_export_version("1.0")  # must not raise

    def test_version_2_0_raises(self) -> None:
        with pytest.raises(ValueError, match="unsupported_version"):
            validate_export_version("2.0")

    def test_arbitrary_string_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_export_version("bogus")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_export_version("")


# ---------------------------------------------------------------------------
# topological_sort_locations
# ---------------------------------------------------------------------------


class TestTopologicalSortLocations:
    def test_empty_input_returns_empty(self) -> None:
        assert topological_sort_locations([]) == []

    def test_single_root_location(self) -> None:
        loc = _loc(uuid.uuid4())
        assert topological_sort_locations([loc]) == [loc]

    def test_child_appears_after_parent(self) -> None:
        parent_id = uuid.uuid4()
        child_id = uuid.uuid4()
        parent = _loc(parent_id)
        child = _loc(child_id, parent_id=parent_id)
        # Supply child first to force reordering
        result = topological_sort_locations([child, parent])
        ids = [loc.id for loc in result]
        assert ids.index(parent_id) < ids.index(child_id)

    def test_three_level_hierarchy_ordered_correctly(self) -> None:
        a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        result = topological_sort_locations(
            [_loc(c, b), _loc(b, a), _loc(a)]
        )
        ids = [loc.id for loc in result]
        assert ids.index(a) < ids.index(b)
        assert ids.index(b) < ids.index(c)

    def test_cycle_raises_value_error(self) -> None:
        a, b = uuid.uuid4(), uuid.uuid4()
        with pytest.raises(ValueError, match="circular_location_reference"):
            topological_sort_locations([_loc(a, b), _loc(b, a)])

    def test_external_parent_id_treated_as_root(self) -> None:
        """A location whose parent_id is not in the list is treated as a root."""
        external = uuid.uuid4()
        loc = _loc(uuid.uuid4(), parent_id=external)
        result = topological_sort_locations([loc])
        assert len(result) == 1

    def test_multiple_roots_all_returned(self) -> None:
        locs = [_loc(uuid.uuid4()) for _ in range(4)]
        assert len(topological_sort_locations(locs)) == 4

    def test_mixed_roots_and_children(self) -> None:
        root1, root2 = uuid.uuid4(), uuid.uuid4()
        child1 = uuid.uuid4()
        child2 = uuid.uuid4()
        result = topological_sort_locations(
            [
                _loc(child2, root2),
                _loc(child1, root1),
                _loc(root2),
                _loc(root1),
            ]
        )
        ids = [loc.id for loc in result]
        assert ids.index(root1) < ids.index(child1)
        assert ids.index(root2) < ids.index(child2)
