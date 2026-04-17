"""Unit tests for src/domain/inventory.py — filter_devices pure function."""
import uuid
from dataclasses import dataclass, field
from typing import Sequence

import pytest

from src.domain.inventory import (
    CommonTagOption,
    filter_devices,
    get_common_tags,
    normalize_tag_name,
    normalize_custom_field_key,
    validate_hex_color,
)
from src.models.types import DeviceType


@dataclass(frozen=True)
class FakeTag:
    id: uuid.UUID
    name: str = "tag"
    color: str = "#111111"


@dataclass(frozen=True)
class FakeFilterableDevice:
    name: str
    type: DeviceType
    ip: str | None = None
    notes: str | None = None
    tags: Sequence[FakeTag] = field(default_factory=tuple)


def _make_common_tag(name: str, color: str = "#111111") -> FakeTag:
    return FakeTag(id=uuid.uuid4(), name=name, color=color)


def _make_device(**kwargs) -> FakeFilterableDevice:
    """Return a minimal protocol-compatible device for testing."""
    defaults: dict = {
        "name": "test-device",
        "type": DeviceType.Server,
        "ip": None,
        "notes": None,
        "tags": (),
    }
    defaults.update(kwargs)
    return FakeFilterableDevice(**defaults)


# ---------------------------------------------------------------------------
# Search filter
# ---------------------------------------------------------------------------


class TestFilterDevicesSearch:
    def test_empty_search_returns_all(self) -> None:
        devices = [_make_device(name="alpha"), _make_device(name="beta")]
        result = filter_devices(devices, "", set(), set())
        assert result == devices

    def test_search_case_insensitive(self) -> None:
        devices = [_make_device(name="ProxMox"), _make_device(name="ubuntu")]
        result = filter_devices(devices, "proxmox", set(), set())
        assert len(result) == 1
        assert result[0].name == "ProxMox"

    def test_search_uppercase_query(self) -> None:
        devices = [_make_device(name="alpha-node"), _make_device(name="beta")]
        result = filter_devices(devices, "ALPHA", set(), set())
        assert len(result) == 1

    def test_search_by_ip(self) -> None:
        devices = [_make_device(ip="192.168.1.1"), _make_device(ip="10.0.0.1")]
        result = filter_devices(devices, "192.168", set(), set())
        assert len(result) == 1
        assert result[0].ip == "192.168.1.1"

    def test_search_by_notes(self) -> None:
        devices = [
            _make_device(notes="primary NAS storage"),
            _make_device(notes="dev workstation"),
        ]
        result = filter_devices(devices, "NAS", set(), set())
        assert len(result) == 1

    def test_search_none_fields_treated_as_empty(self) -> None:
        device = _make_device(name="server", ip=None, notes=None)
        result = filter_devices([device], "missing", set(), set())
        assert result == []

    def test_search_whitespace_only_no_filter(self) -> None:
        """Whitespace-only search string → no filter applied."""
        devices = [_make_device(), _make_device()]
        result = filter_devices(devices, "   ", set(), set())
        assert result == devices

    def test_search_no_match_returns_empty(self) -> None:
        devices = [_make_device(name="router-01"), _make_device(name="switch-02")]
        result = filter_devices(devices, "zzznotfound", set(), set())
        assert result == []


# ---------------------------------------------------------------------------
# Type filter
# ---------------------------------------------------------------------------


class TestFilterDevicesTypes:
    def test_empty_type_set_no_filter(self) -> None:
        devices = [
            _make_device(type=DeviceType.Server),
            _make_device(type=DeviceType.Switch),
        ]
        result = filter_devices(devices, "", set(), set())
        assert len(result) == 2

    def test_single_type_filter(self) -> None:
        devices = [
            _make_device(type=DeviceType.Server),
            _make_device(type=DeviceType.Switch),
        ]
        result = filter_devices(devices, "", {DeviceType.Server}, set())
        assert len(result) == 1
        assert result[0].type == DeviceType.Server

    def test_or_within_types(self) -> None:
        """Multiple types in set → OR semantics."""
        devices = [
            _make_device(type=DeviceType.Server),
            _make_device(type=DeviceType.Switch),
            _make_device(type=DeviceType.Router),
        ]
        result = filter_devices(
            devices, "", {DeviceType.Server, DeviceType.Switch}, set()
        )
        assert len(result) == 2

    def test_type_filter_excludes_non_matching(self) -> None:
        devices = [
            _make_device(type=DeviceType.NAS),
            _make_device(type=DeviceType.Docker),
        ]
        result = filter_devices(devices, "", {DeviceType.Server}, set())
        assert result == []


# ---------------------------------------------------------------------------
# AND across categories
# ---------------------------------------------------------------------------


class TestFilterDevicesAndCombination:
    def test_search_and_type_filter(self) -> None:
        devices = [
            _make_device(name="main-server", type=DeviceType.Server),
            _make_device(name="main-switch", type=DeviceType.Switch),
            _make_device(name="backup-server", type=DeviceType.Server),
        ]
        result = filter_devices(devices, "main", {DeviceType.Server}, set())
        assert len(result) == 1
        assert result[0].name == "main-server"

    def test_and_across_categories(self) -> None:
        """Type AND search must both match."""
        devices = [
            _make_device(name="nas-device", type=DeviceType.NAS),
            _make_device(name="nas-router", type=DeviceType.Router),
        ]
        result = filter_devices(devices, "nas", {DeviceType.NAS}, set())
        assert len(result) == 1
        assert result[0].type == DeviceType.NAS

    def test_empty_result_when_no_combined_match(self) -> None:
        devices = [_make_device(name="server-01", type=DeviceType.Server)]
        result = filter_devices(devices, "switch", {DeviceType.Server}, set())
        assert result == []


# ---------------------------------------------------------------------------
# Tag filter (HT-006)
# ---------------------------------------------------------------------------


class TestFilterDevicesTagFilter:
    def test_empty_tag_ids_no_filter(self) -> None:
        devices = [_make_device(), _make_device()]
        result = filter_devices(devices, "", set(), set())
        assert len(result) == 2

    def test_device_with_matching_tag_passes(self) -> None:
        tag_id = uuid.uuid4()
        device = _make_device(tags=(FakeTag(id=tag_id),))
        result = filter_devices([device], "", set(), {tag_id})
        assert len(result) == 1

    def test_device_without_tags_excluded_when_filter_set(self) -> None:
        device = _make_device(tags=())
        result = filter_devices([device], "", set(), {uuid.uuid4()})
        assert result == []

    def test_device_with_different_tag_excluded(self) -> None:
        device = _make_device(tags=(FakeTag(id=uuid.uuid4()),))
        result = filter_devices([device], "", set(), {uuid.uuid4()})
        assert result == []

    def test_or_within_tags(self) -> None:
        """Device needs at least ONE of the requested tags (OR semantics)."""
        tag_a = uuid.uuid4()
        tag_b = uuid.uuid4()
        tag_c = uuid.uuid4()
        device_ab = _make_device(tags=(FakeTag(id=tag_a), FakeTag(id=tag_b)))
        device_c = _make_device(tags=(FakeTag(id=tag_c),))
        result = filter_devices([device_ab, device_c], "", set(), {tag_a, tag_c})
        assert len(result) == 2

    def test_tag_and_search_combined(self) -> None:
        tag_id = uuid.uuid4()
        match = _make_device(name="prod-server", tags=(FakeTag(id=tag_id),))
        no_match_name = _make_device(name="dev-server", tags=(FakeTag(id=tag_id),))
        no_tag = _make_device(name="prod-other", tags=())
        result = filter_devices([match, no_match_name, no_tag], "prod", set(), {tag_id})
        assert len(result) == 1
        assert result[0].name == "prod-server"

    def test_tag_ids_filter_returns_only_matching_devices(self) -> None:
        matching_tag = uuid.uuid4()
        non_matching_tag = uuid.uuid4()
        matching = _make_device(name="match", tags=(FakeTag(id=matching_tag),))
        non_matching = _make_device(name="skip", tags=(FakeTag(id=non_matching_tag),))
        result = filter_devices(
            [matching, non_matching],
            "",
            set(),
            {matching_tag},
        )
        assert [d.name for d in result] == ["match"]


# ---------------------------------------------------------------------------
# Order + immutability
# ---------------------------------------------------------------------------


class TestFilterDevicesContract:
    def test_preserves_input_order(self) -> None:
        names = ["charlie", "alpha", "beta"]
        devices = [_make_device(name=n) for n in names]
        result = filter_devices(devices, "", set(), set())
        assert [d.name for d in result] == names

    def test_does_not_mutate_input_list(self) -> None:
        devices = [_make_device(name="orig")]
        before_len = len(devices)
        filter_devices(devices, "orig", set(), set())
        assert len(devices) == before_len

    def test_returns_new_list(self) -> None:
        devices = [_make_device()]
        result = filter_devices(devices, "", set(), set())
        assert result is not devices


# ---------------------------------------------------------------------------
# normalize_tag_name
# ---------------------------------------------------------------------------


class TestNormalizeTagName:
    def test_lowercases(self) -> None:
        assert normalize_tag_name("Production") == "production"

    def test_strips_whitespace(self) -> None:
        assert normalize_tag_name("  DMZ  ") == "dmz"

    def test_already_normalized(self) -> None:
        assert normalize_tag_name("production") == "production"

    def test_mixed_case_with_spaces(self) -> None:
        assert normalize_tag_name("  MyTag  ") == "mytag"


# ---------------------------------------------------------------------------
# normalize_custom_field_key
# ---------------------------------------------------------------------------


class TestNormalizeCustomFieldKey:
    def test_lowercases(self) -> None:
        assert normalize_custom_field_key("Serial") == "serial"

    def test_strips_whitespace(self) -> None:
        assert normalize_custom_field_key("  Wattage  ") == "wattage"

    def test_already_normalized(self) -> None:
        assert normalize_custom_field_key("wattage") == "wattage"

    def test_mixed_case_with_spaces(self) -> None:
        assert normalize_custom_field_key("  MyKey  ") == "mykey"

    def test_single_char(self) -> None:
        assert normalize_custom_field_key("X") == "x"

    def test_uppercase_only(self) -> None:
        assert normalize_custom_field_key("SERIAL_NUMBER") == "serial_number"


# ---------------------------------------------------------------------------
# validate_hex_color
# ---------------------------------------------------------------------------


class TestValidateHexColor:
    def test_valid_lowercase(self) -> None:
        assert validate_hex_color("#4f46e5") == "#4f46e5"

    def test_valid_uppercase(self) -> None:
        assert validate_hex_color("#4F46E5") == "#4F46E5"

    def test_valid_mixed_case(self) -> None:
        assert validate_hex_color("#aAbBcC") == "#aAbBcC"

    def test_invalid_missing_hash(self) -> None:
        with pytest.raises(ValueError, match="Invalid hex color"):
            validate_hex_color("4f46e5")

    def test_invalid_short(self) -> None:
        with pytest.raises(ValueError, match="Invalid hex color"):
            validate_hex_color("#fff")

    def test_invalid_long(self) -> None:
        with pytest.raises(ValueError, match="Invalid hex color"):
            validate_hex_color("#4f46e500")

    def test_invalid_non_hex_chars(self) -> None:
        with pytest.raises(ValueError, match="Invalid hex color"):
            validate_hex_color("#gggggg")

    def test_empty_string(self) -> None:
        with pytest.raises(ValueError, match="Invalid hex color"):
            validate_hex_color("")


# ---------------------------------------------------------------------------
# get_common_tags (HT-031)
# ---------------------------------------------------------------------------


class TestGetCommonTags:
    def test_empty_selection_returns_empty(self) -> None:
        assert get_common_tags([]) == []

    def test_single_device_returns_all_tags_sorted(self) -> None:
        web = _make_common_tag("web")
        app = _make_common_tag("App")
        device = _make_device(tags=(web, app))
        result = get_common_tags([device])
        assert result == [
            CommonTagOption(id=app.id, name="App", color="#111111"),
            CommonTagOption(id=web.id, name="web", color="#111111"),
        ]

    def test_multiple_devices_returns_only_intersection(self) -> None:
        prod = _make_common_tag("prod", "#22aa66")
        dmz = _make_common_tag("dmz", "#f59e0b")
        backup = _make_common_tag("backup", "#3b82f6")
        d1 = _make_device(tags=(prod, dmz))
        d2 = _make_device(tags=(prod, backup))
        d3 = _make_device(tags=(prod,))

        result = get_common_tags([d1, d2, d3])

        assert result == [CommonTagOption(id=prod.id, name="prod", color="#22aa66")]

    def test_disjoint_tags_returns_empty(self) -> None:
        d1 = _make_device(tags=(_make_common_tag("a"),))
        d2 = _make_device(tags=(_make_common_tag("b"),))
        assert get_common_tags([d1, d2]) == []
