"""Unit tests for dashboard power card rendering contract (HT-044 regression).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx

from tests.unit.nicegui_fakes import AsyncClientStub, FakeUI, install_fake_ui


def _noop_shell():
    class _C:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return None

    return _C()


def test_dashboard_power_card_shows_monthly_cost_and_top_locations(
    monkeypatch,
) -> None:
    import src.ui.pages.dashboard as dashboard_module

    fake_ui = FakeUI()
    install_fake_ui(monkeypatch, dashboard_module, fake_ui, {"access_token": "token"})

    # Prevent auth redirect and app shell rendering
    monkeypatch.setattr(dashboard_module, "redirect_if_unauthenticated", lambda **kwargs: False)
    monkeypatch.setattr(dashboard_module, "app_shell", lambda *args, **kwargs: _noop_shell())

    # Prepare HTTP responses for the six client.get calls in dashboard_page()
    client_stub = AsyncClientStub(
        [
            httpx.Response(200, json={"total": 1}),  # devices
            httpx.Response(200, json={"total": 2}),  # connections
            httpx.Response(200, json=[]),  # locations
            httpx.Response(200, json=[]),  # tags
            httpx.Response(200, json={"items": []}),  # recent devices
            httpx.Response(
                200,
                json={
                    "total_watts": 666,
                    "estimated_monthly_cost": 12.3456,
                    "currency": "USD",
                    "by_location": [
                        {
                            "location_id": "loc-1",
                            "location_name": "Rack 1",
                            "parent_location_id": None,
                            "total_watts": 250,
                        },
                        {
                            "location_id": "loc-2",
                            "location_name": "Rack 2",
                            "parent_location_id": None,
                            "total_watts": 500,
                        },
                        {
                            "location_id": "child-1",
                            "location_name": "Child",
                            "parent_location_id": "loc-1",
                            "total_watts": 10,
                        },
                    ],
                },
            ),
        ]
    )

    monkeypatch.setattr(dashboard_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

    # Invoke the page
    asyncio.run(dashboard_module.dashboard_page())

    labels = [l.text_value for l in fake_ui.created.get("label", [])]

    # Total watts label should be present
    assert any(lbl == "666W" for lbl in labels)

    # Monthly cost should be formatted to two decimals and include currency
    assert any("12.35 USD / month" in lbl for lbl in labels)

    # Top locations should include Rack 1 and Rack 2 and their watt labels
    assert any("Rack 1" == lbl for lbl in labels)
    assert any("250W" == lbl for lbl in labels)
    assert any("Rack 2" == lbl for lbl in labels)
    assert any("500W" == lbl for lbl in labels)


def test_dashboard_power_card_shows_rate_not_configured_when_missing(
    monkeypatch,
) -> None:
    import src.ui.pages.dashboard as dashboard_module

    fake_ui = FakeUI()
    install_fake_ui(monkeypatch, dashboard_module, fake_ui, {"access_token": "token"})

    monkeypatch.setattr(dashboard_module, "redirect_if_unauthenticated", lambda **kwargs: False)
    monkeypatch.setattr(dashboard_module, "app_shell", lambda *args, **kwargs: _noop_shell())

    client_stub = AsyncClientStub(
        [
            httpx.Response(200, json={"total": 0}),
            httpx.Response(200, json={"total": 0}),
            httpx.Response(200, json=[]),
            httpx.Response(200, json=[]),
            httpx.Response(200, json={"items": []}),
            httpx.Response(
                200,
                json={
                    "total_watts": 0,
                    "estimated_monthly_cost": None,
                    "currency": None,
                    "by_location": [],
                },
            ),
        ]
    )

    monkeypatch.setattr(dashboard_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

    asyncio.run(dashboard_module.dashboard_page())

    labels = [l.text_value for l in fake_ui.created.get("label", [])]

    # When rate not configured the dashboard displays a hint string
    assert any(lbl == "Rate not configured" for lbl in labels)
