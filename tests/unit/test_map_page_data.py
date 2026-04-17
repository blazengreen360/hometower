"""Unit tests for map page data merging helpers."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest

from tests.unit.nicegui_fakes import AsyncClientStub


class TestMapPageData:
    def test_load_geo_locations_merges_power_summary_by_location(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.pages.map_page_data as map_page_data_module

        monkeypatch.setattr(
            map_page_data_module,
            "nicegui_app",
            SimpleNamespace(storage=SimpleNamespace(user={"access_token": "token"})),
            raising=False,
        )
        client_stub = AsyncClientStub(
            [
                httpx.Response(
                    200,
                    json=[
                        {
                            "id": "loc-1",
                            "name": "Rack A",
                            "lat": 51.5,
                            "lng": -0.1,
                            "devices": [],
                        },
                        {
                            "id": "loc-2",
                            "name": "Rack B",
                            "lat": 52.5,
                            "lng": -0.2,
                            "devices": [],
                        },
                    ],
                ),
                httpx.Response(
                    200,
                    json={
                        "by_location": [
                            {
                                "location_id": "loc-1",
                                "total_watts": 250,
                                "device_count": 4,
                            }
                        ]
                    },
                ),
            ]
        )
        monkeypatch.setattr(
            map_page_data_module.httpx,
            "AsyncClient",
            lambda *args, **kwargs: client_stub,
        )

        locations = asyncio.run(map_page_data_module.load_geo_locations())

        by_id = {item["id"]: item for item in locations}
        assert by_id["loc-1"]["power_total_watts"] == 250
        assert by_id["loc-1"]["power_device_count"] == 4
        assert by_id["loc-2"]["power_total_watts"] == 0
        assert by_id["loc-2"]["power_device_count"] == 0

    def test_load_geo_locations_returns_locations_when_power_summary_fails(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.pages.map_page_data as map_page_data_module

        monkeypatch.setattr(
            map_page_data_module,
            "nicegui_app",
            SimpleNamespace(storage=SimpleNamespace(user={"access_token": "token"})),
            raising=False,
        )
        client_stub = AsyncClientStub(
            [
                httpx.Response(
                    200,
                    json=[
                        {
                            "id": "loc-3",
                            "name": "Garage",
                            "lat": 40.0,
                            "lng": 10.0,
                            "devices": [],
                        }
                    ],
                ),
                httpx.Response(503, json={"detail": "unavailable"}),
            ]
        )
        monkeypatch.setattr(
            map_page_data_module.httpx,
            "AsyncClient",
            lambda *args, **kwargs: client_stub,
        )

        locations = asyncio.run(map_page_data_module.load_geo_locations())

        assert len(locations) == 1
        assert locations[0]["id"] == "loc-3"
        assert locations[0]["power_total_watts"] == 0
        assert locations[0]["power_device_count"] == 0

    def test_parse_power_by_location_clamps_negative_and_non_int_values(self) -> None:
        import src.ui.pages.map_page_data as map_page_data_module

        raw = {
            "by_location": [
                {"location_id": "loc-neg", "total_watts": -50, "device_count": -1},
                {"location_id": 2, "total_watts": "not-int", "device_count": None},
                {"location_id": None, "total_watts": 10, "device_count": 1},
            ]
        }

        merged = map_page_data_module._parse_power_by_location(raw)

        # Negative values must be clamped to 0 and non-int totals treated as 0
        assert merged.get("loc-neg") == (0, 0)
        assert merged.get("2") == (0, 0)
        # None location_id entries are skipped
        assert None not in merged
