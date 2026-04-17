"""Unit tests for HT-052 device deletion with cascade and orphan detection."""
import uuid
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session

from src.domain.devices import (
    device_in_cytoscape_json,
    filter_device_from_cytoscape_json,
    validate_device_no_children,
)
from src.models.device import DevicePlacement


class TestFilterDeviceFromCytoscapeJsonExtended:
    """Extended edge-case coverage beyond test_domain_devices.py."""

    def test_non_dict_elements_skipped(self) -> None:
        cj: dict[str, object] = {"elements": ["bad", 42, None]}
        result, changed = filter_device_from_cytoscape_json(cj, "x")
        assert changed is False

    def test_uuid_string_match(self) -> None:
        uid = str(uuid.uuid4())
        cj: dict[str, object] = {"elements": [
            {"data": {"id": uid}},
            {"data": {"id": "other"}},
        ]}
        result, changed = filter_device_from_cytoscape_json(cj, uid)
        assert changed is True
        assert len(result["elements"]) == 1  # type: ignore[arg-type]

    def test_preserves_other_keys(self) -> None:
        cj: dict[str, object] = {
            "elements": [{"data": {"id": "x"}}],
            "style": [{"selector": "node"}],
        }
        result, changed = filter_device_from_cytoscape_json(cj, "x")
        assert changed is True
        assert "style" in result


class TestDeviceInCytoscapeJsonExtended:
    """Extended edge-case coverage."""

    def test_edge_not_counted_as_node(self) -> None:
        cj: dict[str, object] = {"elements": [
            {"data": {"id": "edge-1", "source": "dev-1", "target": "dev-2"}},
        ]}
        # edge-1 data.id == "edge-1", not "dev-1"
        assert device_in_cytoscape_json(cj, "dev-1") is False

    def test_non_list_elements_returns_false(self) -> None:
        cj: dict[str, object] = {"elements": "bad"}
        assert device_in_cytoscape_json(cj, "x") is False


class TestValidateDeviceNoChildrenRegression:
    """Regression guard: children still block deletion (HT-021)."""

    def test_children_block_deletion(self) -> None:
        with pytest.raises(ValueError, match="child devices"):
            validate_device_no_children(2)

    def test_zero_children_passes(self) -> None:
        validate_device_no_children(0)


class TestDevicePlacementModel:
    def test_placement_fields(self) -> None:
        p = DevicePlacement(
            view_id=uuid.uuid4(),
            view_name="My View",
            topology_name="Topo A",
        )
        assert p.view_name == "My View"
        assert p.topology_name == "Topo A"

    def test_placement_topology_name_optional(self) -> None:
        p = DevicePlacement(
            view_id=uuid.uuid4(),
            view_name="Orphaned View",
        )
        assert p.topology_name is None
