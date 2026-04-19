"""Unit tests for HT-082 dashboard power widget behavior."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx

from src.models.types import Role
from tests.unit.nicegui_fakes import AsyncClientStub, FakeUI, install_fake_ui


def _noop_shell():
    class _C:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return None

    return _C()


def _summary_payload(*, watts: int, cost: float | None, selected_workspace_id: str | None = None) -> dict[str, object]:
    return {
        "devices": 7,
        "workspaces": 2,
        "topologies": 3,
        "offline_devices": 1,
        "recent_edits": 4,
        "power": {
            "workspace_options": [
                {"id": None, "name": "All Workspaces"},
                {"id": "ws-1", "name": "Lab One"},
            ],
            "selected_workspace_id": selected_workspace_id,
            "selected_workspace_name": "All Workspaces" if selected_workspace_id is None else "Lab One",
            "total_watts": watts,
            "estimated_monthly_cost": cost,
            "currency": "USD" if cost is not None else None,
        },
        "inventory_breakdown": {"status_counts": [], "type_counts": []},
        "recent_activity": [],
    }


def _scoped_summary_payload(
    *,
    devices: int,
    workspaces: int,
    topologies: int,
    offline_devices: int,
    recent_edits: int,
    watts: int,
    cost: float,
    selected_workspace_id: str | None,
    selected_workspace_name: str,
    status_key: str,
    type_key: str,
    activity_title: str,
    activity_route: str,
) -> dict[str, object]:
    return {
        "devices": devices,
        "workspaces": workspaces,
        "topologies": topologies,
        "offline_devices": offline_devices,
        "recent_edits": recent_edits,
        "power": {
            "workspace_options": [
                {"id": None, "name": "All Workspaces"},
                {"id": "ws-1", "name": "Lab One"},
            ],
            "selected_workspace_id": selected_workspace_id,
            "selected_workspace_name": selected_workspace_name,
            "total_watts": watts,
            "estimated_monthly_cost": cost,
            "currency": "USD",
        },
        "inventory_breakdown": {
            "status_counts": [{"key": status_key, "count": 3, "route": f"/inventory?status={status_key}"}],
            "type_counts": [{"key": type_key, "count": 4, "route": f"/inventory?type={type_key}"}],
        },
        "recent_activity": [
            {
                "kind": "device_updated",
                "title": activity_title,
                "subtitle": "Device updated",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "route": activity_route,
            }
        ],
    }


def test_dashboard_power_card_shows_monthly_cost(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    fake_ui = FakeUI()
    install_fake_ui(monkeypatch, dashboard_module, fake_ui, {"access_token": "token"})
    monkeypatch.setattr(dashboard_module, "redirect_if_unauthenticated", lambda **kwargs: False)
    monkeypatch.setattr(dashboard_module, "app_shell", lambda *args, **kwargs: _noop_shell())
    monkeypatch.setattr(dashboard_module, "get_ui_role", lambda: Role.Contributor)
    monkeypatch.setattr(
        dashboard_module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: AsyncClientStub(
            [httpx.Response(200, json=_summary_payload(watts=666, cost=12.3456))]
        ),
    )

    asyncio.run(dashboard_module.dashboard_page())

    labels = [label.text_value for label in fake_ui.created["label"]]
    assert "666W" in labels
    assert "12.35 USD / month" in labels
    workspace_select = fake_ui.created["select"][0]
    inventory_button = next(button for button in fake_ui.created["button"] if button.value == "View Inventory")
    assert workspace_select.label == "Workspace Scope"
    assert workspace_select.options == {"": "All Workspaces", "ws-1": "Lab One"}
    assert "update:model-value" not in workspace_select.js_handlers
    assert "click" not in inventory_button.js_handlers
    inventory_button.handlers["click"]()
    assert fake_ui.navigate.to_calls[-1] == ("/inventory", False)


def test_dashboard_workspace_switch_rerenders_full_summary(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    fake_ui = FakeUI()
    install_fake_ui(monkeypatch, dashboard_module, fake_ui, {"access_token": "token"})
    monkeypatch.setattr(dashboard_module, "redirect_if_unauthenticated", lambda **kwargs: False)
    monkeypatch.setattr(dashboard_module, "app_shell", lambda *args, **kwargs: _noop_shell())
    monkeypatch.setattr(dashboard_module, "get_ui_role", lambda: Role.Contributor)

    client_stub = AsyncClientStub(
        [
            httpx.Response(
                200,
                json=_scoped_summary_payload(
                    devices=7,
                    workspaces=2,
                    topologies=3,
                    offline_devices=1,
                    recent_edits=4,
                    watts=666,
                    cost=12.34,
                    selected_workspace_id=None,
                    selected_workspace_name="All Workspaces",
                    status_key="Offline",
                    type_key="Server",
                    activity_title="Global VM",
                    activity_route="/inventory/edit/device-global",
                ),
            ),
            httpx.Response(
                200,
                json=_scoped_summary_payload(
                    devices=21,
                    workspaces=1,
                    topologies=8,
                    offline_devices=5,
                    recent_edits=13,
                    watts=250,
                    cost=4.56,
                    selected_workspace_id="ws-1",
                    selected_workspace_name="Lab One",
                    status_key="Online",
                    type_key="Switch",
                    activity_title="Scoped VM",
                    activity_route="/topology?workspace_id=ws-1&topology_id=topo-1&device_id=device-scoped",
                ),
            ),
        ]
    )
    monkeypatch.setattr(dashboard_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

    asyncio.run(dashboard_module.dashboard_page())

    workspace_select = fake_ui.created["select"][0]
    asyncio.run(workspace_select.handlers["value_change"](SimpleNamespace(value="ws-1")))

    labels = [label.text_value for label in fake_ui.created["label"]]
    links = [link.value for link in fake_ui.created["link"]]

    assert "21" in labels
    assert "8" in labels
    assert "13" in labels
    assert "Lab One" in labels
    assert "250W" in labels
    assert "4.56 USD / month" in labels
    assert "Online" in links
    assert "Switch" in links
    assert "Scoped VM" in links
    recent_link = [link for link in fake_ui.created["link"] if link.value == "Scoped VM"][-1]
    recent_link.handlers["click"](SimpleNamespace())
    assert fake_ui.navigate.to_calls[-1] == (
        "/topology?workspace_id=ws-1&topology_id=topo-1&device_id=device-scoped",
        False,
    )
    assert any("history.replaceState" in script for script in fake_ui.run_javascript_calls)
    assert client_stub.call_kwargs[1]["params"] == {"workspace_id": "ws-1"}
    inventory_button = [button for button in fake_ui.created["button"] if button.value == "View Inventory"][-1]
    inventory_button.handlers["click"]()
    assert fake_ui.navigate.to_calls[-1] == ("/inventory?workspace_id=ws-1", False)


def test_dashboard_scope_query_loads_filtered_summary(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    fake_ui = FakeUI()
    install_fake_ui(monkeypatch, dashboard_module, fake_ui, {"access_token": "token"})
    monkeypatch.setattr(dashboard_module, "redirect_if_unauthenticated", lambda **kwargs: False)
    monkeypatch.setattr(dashboard_module, "app_shell", lambda *args, **kwargs: _noop_shell())
    monkeypatch.setattr(dashboard_module, "get_ui_role", lambda: Role.Contributor)

    client_stub = AsyncClientStub(
        [
            httpx.Response(
                200,
                json=_scoped_summary_payload(
                    devices=9,
                    workspaces=1,
                    topologies=6,
                    offline_devices=2,
                    recent_edits=5,
                    watts=120,
                    cost=3.21,
                    selected_workspace_id="ws-1",
                    selected_workspace_name="Lab One",
                    status_key="Online",
                    type_key="Switch",
                    activity_title="Scoped VM",
                    activity_route="/topology?workspace_id=ws-1&topology_id=topo-2&device_id=device-scoped",
                ),
            ),
        ]
    )
    monkeypatch.setattr(dashboard_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

    asyncio.run(dashboard_module.dashboard_page(workspace_id="ws-1"))

    labels = [label.text_value for label in fake_ui.created["label"]]
    links = [link.value for link in fake_ui.created["link"]]
    inventory_button = next(button for button in fake_ui.created["button"] if button.value == "View Inventory")

    assert "9" in labels
    assert "6" in labels
    assert "5" in labels
    assert "Lab One" in labels
    assert "120W" in labels
    assert "3.21 USD / month" in labels
    assert "Online" in links
    assert "Switch" in links
    assert "Scoped VM" in links
    assert "click" not in inventory_button.js_handlers
    inventory_button.handlers["click"]()
    assert fake_ui.navigate.to_calls[-1] == ("/inventory?workspace_id=ws-1", False)
    assert client_stub.call_kwargs[0]["params"] == {"workspace_id": "ws-1"}


def test_dashboard_recent_activity_uses_api_fallback_route_without_rewrite(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    fake_ui = FakeUI()
    install_fake_ui(monkeypatch, dashboard_module, fake_ui, {"access_token": "token"})
    monkeypatch.setattr(dashboard_module, "redirect_if_unauthenticated", lambda **kwargs: False)
    monkeypatch.setattr(dashboard_module, "app_shell", lambda *args, **kwargs: _noop_shell())
    monkeypatch.setattr(dashboard_module, "get_ui_role", lambda: Role.Contributor)
    monkeypatch.setattr(
        dashboard_module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: AsyncClientStub(
            [
                httpx.Response(
                    200,
                    json=_scoped_summary_payload(
                        devices=9,
                        workspaces=2,
                        topologies=3,
                        offline_devices=2,
                        recent_edits=5,
                        watts=120,
                        cost=3.21,
                        selected_workspace_id=None,
                        selected_workspace_name="All Workspaces",
                        status_key="Online",
                        type_key="Switch",
                        activity_title="Orphan Node",
                        activity_route="/inventory/edit/device-orphan",
                    ),
                ),
            ]
        ),
    )

    asyncio.run(dashboard_module.dashboard_page())

    recent_link = next(link for link in fake_ui.created["link"] if link.value == "Orphan Node")
    recent_link.handlers["click"](SimpleNamespace())

    assert fake_ui.navigate.to_calls[-1] == ("/inventory/edit/device-orphan", False)
