"""Unit tests for src/domain/power.py pure functions (HT-044)."""
import uuid

import pytest

from src.domain.power import (
    build_recursive_location_rollups,
    estimate_monthly_cost,
    estimate_monthly_kwh,
    validate_cost_settings,
)


def _uid(value: str) -> uuid.UUID:
    return uuid.UUID(value)


class TestValidateCostSettings:
    def test_both_none_is_valid(self) -> None:
        assert validate_cost_settings(None, None) == (None, None)

    def test_both_present_is_valid(self) -> None:
        assert validate_cost_settings(0.12, "USD") == (0.12, "USD")

    def test_missing_currency_is_invalid(self) -> None:
        with pytest.raises(
            ValueError,
            match="cost_per_kwh and currency must be provided together",
        ):
            validate_cost_settings(0.12, None)

    def test_missing_cost_is_invalid(self) -> None:
        with pytest.raises(
            ValueError,
            match="cost_per_kwh and currency must be provided together",
        ):
            validate_cost_settings(None, "USD")


class TestPowerEstimation:
    def test_estimate_monthly_kwh_formula(self) -> None:
        assert estimate_monthly_kwh(1250) == 913.2

    def test_estimate_monthly_kwh_zero(self) -> None:
        assert estimate_monthly_kwh(0) == 0.0

    def test_estimate_monthly_cost_none_when_rate_missing(self) -> None:
        assert estimate_monthly_cost(750, None) is None

    def test_estimate_monthly_cost_uses_rounded_kwh(self) -> None:
        assert estimate_monthly_cost(1250, 0.12) == 109.58


class TestRecursiveLocationRollups:
    def test_rollups_include_descendants_and_sort_desc_total_watts(self) -> None:
        root = _uid("00000000-0000-0000-0000-000000000001")
        child = _uid("00000000-0000-0000-0000-000000000002")
        empty = _uid("00000000-0000-0000-0000-000000000003")

        locations = [
            {"id": root, "name": "Root", "parent_id": None},
            {"id": child, "name": "Child", "parent_id": root},
            {"id": empty, "name": "Empty", "parent_id": None},
        ]
        devices = [
            {"location_id": root, "power_watts": 100},
            {"location_id": child, "power_watts": 200},
            {"location_id": child, "power_watts": 0},
            {"location_id": root, "power_watts": None},
            {"location_id": None, "power_watts": 50},
            {
                "location_id": _uid("00000000-0000-0000-0000-000000000099"),
                "power_watts": 75,
            },
        ]

        rollups = build_recursive_location_rollups(devices, locations, 0.1)

        assert [row["location_name"] for row in rollups] == ["Root", "Child"]

        root_row = rollups[0]
        assert root_row["location_id"] == root
        assert root_row["total_watts"] == 300
        assert root_row["device_count"] == 3
        assert root_row["estimated_monthly_cost"] == 21.92

        child_row = rollups[1]
        assert child_row["location_id"] == child
        assert child_row["total_watts"] == 200
        assert child_row["device_count"] == 2
        assert child_row["estimated_monthly_cost"] == 14.61

    def test_zero_watt_devices_are_counted_as_known_power(self) -> None:
        location_id = _uid("00000000-0000-0000-0000-000000000010")
        rollups = build_recursive_location_rollups(
            devices=[{"location_id": location_id, "power_watts": 0}],
            locations=[{"id": location_id, "name": "Zero", "parent_id": None}],
            cost_per_kwh=None,
        )

        assert len(rollups) == 1
        assert rollups[0]["total_watts"] == 0
        assert rollups[0]["device_count"] == 1
        assert rollups[0]["estimated_monthly_cost"] is None

    def test_corrupt_cycle_is_guarded(self) -> None:
        a = _uid("00000000-0000-0000-0000-000000000020")
        b = _uid("00000000-0000-0000-0000-000000000021")

        rollups = build_recursive_location_rollups(
            devices=[
                {"location_id": a, "power_watts": 10},
                {"location_id": b, "power_watts": 20},
            ],
            locations=[
                {"id": a, "name": "A", "parent_id": b},
                {"id": b, "name": "B", "parent_id": a},
            ],
            cost_per_kwh=None,
        )

        assert len(rollups) == 2
        assert {row["location_name"] for row in rollups} == {"A", "B"}
        assert {row["total_watts"] for row in rollups} == {30}
        assert {row["device_count"] for row in rollups} == {2}
