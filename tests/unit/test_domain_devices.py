"""Unit tests for src/domain/devices.py pure functions."""
import uuid
from typing import Optional

import pytest

from src.domain.devices import (
    detect_parent_cycle,
    device_in_cytoscape_json,
    extract_device_view_snapshot,
    filter_device_from_cytoscape_json,
    restore_device_to_cytoscape_json,
    validate_device_no_children,
    validate_ip,
    validate_mac,
)


class TestValidateMac:
    def test_validate_mac_valid(self) -> None:
        assert validate_mac("AA:BB:CC:DD:EE:FF") == "AA:BB:CC:DD:EE:FF"

    def test_validate_mac_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_mac("not-a-mac")

    def test_validate_mac_none_returns_none(self) -> None:
        assert validate_mac(None) is None

    def test_validate_mac_normalizes_to_uppercase(self) -> None:
        assert validate_mac("aa:bb:cc:dd:ee:ff") == "AA:BB:CC:DD:EE:FF"

    def test_validate_mac_mixed_case_normalizes(self) -> None:
        assert validate_mac("aA:bB:cC:dD:eE:fF") == "AA:BB:CC:DD:EE:FF"

    def test_validate_mac_invalid_separator_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_mac("AA-BB-CC-DD-EE-FF")

    def test_validate_mac_short_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_mac("AA:BB:CC:DD:EE")

    def test_validate_mac_strips_whitespace(self) -> None:
        assert validate_mac(" aa:bb:cc:dd:ee:ff ") == "AA:BB:CC:DD:EE:FF"


class TestValidateIp:
    def test_validate_ip_valid(self) -> None:
        assert validate_ip("192.168.1.1") == "192.168.1.1"

    def test_validate_ip_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_ip("not-an-ip")

    def test_validate_ip_none_returns_none(self) -> None:
        assert validate_ip(None) is None

    def test_validate_ip_octet_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_ip("192.168.1.256")

    def test_validate_ip_loopback(self) -> None:
        assert validate_ip("127.0.0.1") == "127.0.0.1"

    def test_validate_ip_broadcast(self) -> None:
        assert validate_ip("255.255.255.255") == "255.255.255.255"

    def test_validate_ip_all_octets_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_ip("999.999.999.999")

    def test_validate_ip_ipv6_loopback(self) -> None:
        assert validate_ip("::1") == "::1"

    def test_validate_ip_ipv6_link_local(self) -> None:
        assert validate_ip("fe80::1") == "fe80::1"

    def test_validate_ip_strips_whitespace(self) -> None:
        assert validate_ip(" 192.168.1.1 ") == "192.168.1.1"


class TestFilterDeviceFromCytoscapeJson:
    def test_no_elements_key_returns_unchanged(self) -> None:
        cj: dict[str, object] = {"style": []}
        result, changed = filter_device_from_cytoscape_json(cj, "abc")
        assert changed is False
        assert result is cj

    def test_removes_matching_node(self) -> None:
        cj: dict[str, object] = {"elements": [
            {"data": {"id": "dev-1"}},
            {"data": {"id": "dev-2"}},
        ]}
        result, changed = filter_device_from_cytoscape_json(cj, "dev-1")
        assert changed is True
        els = result["elements"]
        assert isinstance(els, list)
        assert len(els) == 1
        assert els[0]["data"]["id"] == "dev-2"  # type: ignore[index]

    def test_removes_edges_referencing_device(self) -> None:
        cj: dict[str, object] = {"elements": [
            {"data": {"id": "dev-1"}},
            {"data": {"id": "dev-2"}},
            {"data": {"id": "edge-1", "source": "dev-1", "target": "dev-2"}},
            {"data": {"id": "edge-2", "source": "dev-2", "target": "dev-1"}},
        ]}
        result, changed = filter_device_from_cytoscape_json(cj, "dev-1")
        assert changed is True
        els = result["elements"]
        assert isinstance(els, list)
        assert len(els) == 1  # only dev-2 node survives

    def test_no_match_returns_unchanged(self) -> None:
        cj: dict[str, object] = {"elements": [{"data": {"id": "dev-1"}}]}
        result, changed = filter_device_from_cytoscape_json(cj, "other")
        assert changed is False

    def test_empty_elements_list(self) -> None:
        cj: dict[str, object] = {"elements": []}
        result, changed = filter_device_from_cytoscape_json(cj, "x")
        assert changed is False

    def test_dict_elements_shape_preserved_and_collapsed_nodes_cleaned(self) -> None:
        cj: dict[str, object] = {
            "elements": {
                "nodes": [
                    {"group": "nodes", "data": {"id": "dev-1"}},
                    {"group": "nodes", "data": {"id": "dev-2"}},
                ],
                "edges": [
                    {
                        "group": "edges",
                        "data": {"id": "edge-1", "source": "dev-1", "target": "dev-2"},
                    }
                ],
            },
            "collapsedNodes": ["dev-1", "other"],
        }

        result, changed = filter_device_from_cytoscape_json(cj, "dev-1")

        assert changed is True
        elements = result["elements"]
        assert isinstance(elements, dict)
        nodes = elements["nodes"]
        assert isinstance(nodes, list)
        assert len(nodes) == 1
        assert nodes[0]["data"]["id"] == "dev-2"  # type: ignore[index]
        edges = elements["edges"]
        assert isinstance(edges, list)
        assert edges == []
        assert result["collapsedNodes"] == ["other"]

    def test_removes_device_id_node_edges_and_collapsed_node_alias(self) -> None:
        cj: dict[str, object] = {
            "elements": {
                "nodes": [
                    {"group": "nodes", "data": {"id": "node-1", "device_id": "dev-1"}},
                    {"group": "nodes", "data": {"id": "node-2", "device_id": "dev-2"}},
                ],
                "edges": [
                    {
                        "group": "edges",
                        "data": {"id": "edge-1", "source": "node-1", "target": "node-2"},
                    }
                ],
            },
            "collapsedNodes": ["node-1", "other"],
        }

        result, changed = filter_device_from_cytoscape_json(cj, "dev-1")

        assert changed is True
        elements = result["elements"]
        assert isinstance(elements, dict)
        nodes = elements["nodes"]
        assert isinstance(nodes, list)
        assert len(nodes) == 1
        assert nodes[0]["data"]["device_id"] == "dev-2"  # type: ignore[index]
        edges = elements["edges"]
        assert isinstance(edges, list)
        assert edges == []
        assert result["collapsedNodes"] == ["other"]


class TestDeviceViewSnapshots:
    def test_extract_device_snapshot_from_list_elements(self) -> None:
        cj: dict[str, object] = {
            "elements": [
                {
                    "group": "nodes",
                    "data": {"id": "dev-1", "label": "Node 1"},
                    "position": {"x": 10, "y": 20},
                }
            ],
            "collapsedNodes": ["dev-1"],
        }

        snapshot, was_collapsed = extract_device_view_snapshot(cj, "dev-1")

        assert snapshot is not None
        assert snapshot["data"]["id"] == "dev-1"  # type: ignore[index]
        assert was_collapsed is True

    def test_extract_device_snapshot_from_dict_elements(self) -> None:
        cj: dict[str, object] = {
            "elements": {
                "nodes": [
                    {
                        "group": "nodes",
                        "data": {"id": "dev-1", "label": "Node 1"},
                        "position": {"x": 10, "y": 20},
                    }
                ],
                "edges": [],
            },
            "collapsedNodes": [],
        }

        snapshot, was_collapsed = extract_device_view_snapshot(cj, "dev-1")

        assert snapshot is not None
        assert snapshot["data"]["id"] == "dev-1"  # type: ignore[index]
        assert was_collapsed is False

    def test_restore_snapshot_is_idempotent_when_node_exists(self) -> None:
        node_snapshot: dict[str, object] = {
            "group": "nodes",
            "data": {"id": "dev-1", "label": "Node 1"},
            "position": {"x": 10, "y": 20},
        }
        cj: dict[str, object] = {
            "elements": {
                "nodes": [node_snapshot],
                "edges": [],
            },
            "collapsedNodes": ["dev-1"],
        }

        result, changed = restore_device_to_cytoscape_json(cj, node_snapshot, True)

        assert changed is False
        assert result is cj

    def test_restore_adds_node_and_does_not_duplicate_collapsed_entry(self) -> None:
        node_snapshot: dict[str, object] = {
            "group": "nodes",
            "data": {"id": "dev-1", "label": "Node 1"},
            "position": {"x": 10, "y": 20},
        }
        cj: dict[str, object] = {
            "elements": {
                "nodes": [{"group": "nodes", "data": {"id": "dev-2"}}],
                "edges": [],
            },
            "collapsedNodes": ["dev-1", "dev-2"],
        }

        result, changed = restore_device_to_cytoscape_json(cj, node_snapshot, True)

        assert changed is True
        elements = result["elements"]
        assert isinstance(elements, dict)
        nodes = elements["nodes"]
        assert isinstance(nodes, list)
        assert len(nodes) == 2
        collapsed = result["collapsedNodes"]
        assert isinstance(collapsed, list)
        assert collapsed.count("dev-1") == 1

    def test_extract_and_restore_support_device_id_nodes(self) -> None:
        node_snapshot: dict[str, object] = {
            "group": "nodes",
            "data": {"id": "node-1", "device_id": "dev-1", "label": "Node 1"},
            "position": {"x": 10, "y": 20},
        }
        cj: dict[str, object] = {
            "elements": {
                "nodes": [node_snapshot],
                "edges": [],
            },
            "collapsedNodes": ["node-1"],
        }

        snapshot, was_collapsed = extract_device_view_snapshot(cj, "dev-1")

        assert snapshot is not None
        assert snapshot["data"]["id"] == "node-1"  # type: ignore[index]
        assert was_collapsed is True

        restored, changed = restore_device_to_cytoscape_json(
            {"elements": {"nodes": [], "edges": []}, "collapsedNodes": []},
            snapshot,
            was_collapsed,
        )

        assert changed is True
        elements = restored["elements"]
        assert isinstance(elements, dict)
        nodes = elements["nodes"]
        assert isinstance(nodes, list)
        assert len(nodes) == 1
        assert nodes[0]["data"]["device_id"] == "dev-1"  # type: ignore[index]
        assert restored["collapsedNodes"] == ["node-1"]


class TestDeviceInCytoscapeJson:
    def test_device_present(self) -> None:
        cj: dict[str, object] = {"elements": [{"data": {"id": "dev-1"}}]}
        assert device_in_cytoscape_json(cj, "dev-1") is True

    def test_device_absent(self) -> None:
        cj: dict[str, object] = {"elements": [{"data": {"id": "dev-1"}}]}
        assert device_in_cytoscape_json(cj, "dev-2") is False

    def test_no_elements_key(self) -> None:
        cj: dict[str, object] = {"style": []}
        assert device_in_cytoscape_json(cj, "dev-1") is False

    def test_empty_elements(self) -> None:
        cj: dict[str, object] = {"elements": []}
        assert device_in_cytoscape_json(cj, "dev-1") is False

    def test_device_present_via_device_id_field(self) -> None:
        cj: dict[str, object] = {
            "elements": [
                {"group": "nodes", "data": {"id": "node-1", "device_id": "dev-1"}}
            ]
        }
        assert device_in_cytoscape_json(cj, "dev-1") is True


class TestDetectParentCycle:
    """HT-021: cycle detection mirrors src/domain/locations.py::detect_cycle."""

    def _uid(self) -> uuid.UUID:
        return uuid.uuid4()

    def test_direct_self_loop_returns_true(self) -> None:
        device_id = self._uid()
        assert detect_parent_cycle(device_id, device_id, {}) is True

    def test_no_cycle_single_level(self) -> None:
        device_id = self._uid()
        parent_id = self._uid()
        parent_map: dict[uuid.UUID, Optional[uuid.UUID]] = {parent_id: None}
        assert detect_parent_cycle(device_id, parent_id, parent_map) is False

    def test_two_cycle_detected(self) -> None:
        # A → B, attempt to set A.parent = B's descendant (which is A itself)
        a = self._uid()
        b = self._uid()
        parent_map: dict[uuid.UUID, Optional[uuid.UUID]] = {a: None, b: a}
        # Setting A's parent to B would create A→B→A
        assert detect_parent_cycle(a, b, parent_map) is True

    def test_three_cycle_detected(self) -> None:
        # A → B → C; attempt to set A.parent = C creates A→B→C→A
        a = self._uid()
        b = self._uid()
        c = self._uid()
        parent_map: dict[uuid.UUID, Optional[uuid.UUID]] = {a: None, b: a, c: b}
        assert detect_parent_cycle(a, c, parent_map) is True

    def test_valid_deep_chain_no_cycle(self) -> None:
        # A → B → C → D; new_node being reparented under D is fine
        a = self._uid()
        b = self._uid()
        c = self._uid()
        d = self._uid()
        new_node = self._uid()
        parent_map: dict[uuid.UUID, Optional[uuid.UUID]] = {
            a: None, b: a, c: b, d: c, new_node: None,
        }
        assert detect_parent_cycle(new_node, d, parent_map) is False

    def test_root_parent_terminates_walk(self) -> None:
        device_id = self._uid()
        parent_id = self._uid()
        parent_map: dict[uuid.UUID, Optional[uuid.UUID]] = {parent_id: None}
        assert detect_parent_cycle(device_id, parent_id, parent_map) is False

    def test_missing_parent_in_map_stops_walk(self) -> None:
        device_id = self._uid()
        parent_id = self._uid()
        parent_map: dict[uuid.UUID, Optional[uuid.UUID]] = {}
        assert detect_parent_cycle(device_id, parent_id, parent_map) is False

    def test_pre_existing_corrupt_cycle_guarded(self) -> None:
        # Parent map already contains A→B→A corruption; walking from a third
        # device's proposed parent B must not loop forever.
        a = self._uid()
        b = self._uid()
        third = self._uid()
        parent_map: dict[uuid.UUID, Optional[uuid.UUID]] = {a: b, b: a}
        assert detect_parent_cycle(third, b, parent_map) is True


class TestValidateDeviceNoChildren:
    def test_zero_children_passes(self) -> None:
        validate_device_no_children(0)  # must not raise

    def test_one_child_raises(self) -> None:
        with pytest.raises(
            ValueError,
            match="Device has child devices — remove or reassign them first",
        ):
            validate_device_no_children(1)

    def test_many_children_raises(self) -> None:
        with pytest.raises(ValueError, match="child devices"):
            validate_device_no_children(7)


class TestDeviceLocationId:
    """HT-005: DeviceCreate and DeviceUpdate must expose location_id now that
    the Location entity is implemented (supersedes CRITICAL-002 guard).
    """

    def test_device_create_has_location_id_field(self) -> None:
        from src.models.device import DeviceCreate
        assert "location_id" in DeviceCreate.model_fields

    def test_device_update_has_location_id_field(self) -> None:
        from src.models.device import DeviceUpdate
        assert "location_id" in DeviceUpdate.model_fields

    def test_device_create_location_id_defaults_to_none(self) -> None:
        import uuid
        from src.models.device import DeviceCreate
        from src.models.types import DeviceType
        device = DeviceCreate(name="x", type=DeviceType.Server)
        assert device.location_id is None

    def test_device_create_accepts_location_id(self) -> None:
        import uuid
        from src.models.device import DeviceCreate
        from src.models.types import DeviceType
        loc_id = uuid.uuid4()
        device = DeviceCreate(name="x", type=DeviceType.Server, location_id=loc_id)
        assert device.location_id == loc_id
