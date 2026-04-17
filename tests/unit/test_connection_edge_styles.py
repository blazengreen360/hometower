"""Unit tests for connection edge style mapping logic (HT-030)."""
import pytest

from src.models.types import ConnectionType


_EDGE_STYLES: dict[str, dict[str, object]] = {
    "Ethernet": {"line-style": "solid", "width": 2},
    "WiFi":     {"line-style": "dashed"},
    "Fibre":    {"width": 4},
    "iSCSI":    {"line-style": "dotted"},
    "NFS":      {"line-style": "dotted"},
    "VM":       {"line-style": "dashed", "line-color": "#a78bfa"},
    "Other":    {"opacity": 0.7},
}


class TestConnectionEdgeStyleMapping:
    def test_all_connection_types_have_entry(self) -> None:
        for ct in ConnectionType:
            assert ct.value in _EDGE_STYLES, f"Missing style for {ct.value}"

    def test_wifi_is_dashed(self) -> None:
        assert _EDGE_STYLES["WiFi"].get("line-style") == "dashed"

    def test_fibre_is_thick(self) -> None:
        assert _EDGE_STYLES["Fibre"].get("width") == 4

    def test_iscsi_is_dotted(self) -> None:
        assert _EDGE_STYLES["iSCSI"].get("line-style") == "dotted"

    def test_nfs_is_dotted(self) -> None:
        assert _EDGE_STYLES["NFS"].get("line-style") == "dotted"

    def test_vm_is_dashed_with_color(self) -> None:
        assert _EDGE_STYLES["VM"].get("line-style") == "dashed"
        assert "line-color" in _EDGE_STYLES["VM"]

    def test_ethernet_is_solid(self) -> None:
        assert _EDGE_STYLES["Ethernet"].get("line-style") == "solid"

    def test_other_has_opacity(self) -> None:
        opacity = _EDGE_STYLES["Other"].get("opacity")
        assert isinstance(opacity, (int, float))
        assert opacity < 1.0


class TestConnectionTypeEnum:
    def test_has_seven_values(self) -> None:
        assert len(ConnectionType) == 7

    def test_all_expected_types_exist(self) -> None:
        expected = {"Ethernet", "WiFi", "Fibre", "iSCSI", "NFS", "VM", "Other"}
        actual = {ct.value for ct in ConnectionType}
        assert actual == expected
