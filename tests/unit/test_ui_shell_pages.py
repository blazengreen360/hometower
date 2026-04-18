"""Execution tests for shell-backed NiceGUI pages."""
from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import uuid

import httpx
import pytest

from tests.unit.nicegui_fakes import AsyncClientStub, FakeResponse, FakeUI, install_fake_ui
from src.models.types import Role


@contextmanager
def _noop_shell() -> Iterator[None]:
    yield


def _run(result: object) -> object:
    if inspect.isawaitable(result):
        return asyncio.run(result)  # type: ignore[arg-type]
    return result


def _extract_ht_render_map_payload(run_javascript_calls: list[str]) -> dict[str, object]:
    prefix = "window.htRenderMap("
    map_call = next(
        (script for script in run_javascript_calls if script.startswith(prefix)),
        None,
    )
    assert map_call is not None
    assert map_call.endswith(")")
    payload = json.loads(map_call[len(prefix):-1])
    assert isinstance(payload, dict)
    return payload


class TestLoginPage:
    def test_login_success_stores_storage_and_redirects(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.pages.login as login_module

        fake_ui = FakeUI()
        app = install_fake_ui(monkeypatch, login_module, fake_ui, user={})
        fake_ui.run_javascript_responses = [
            json.dumps(
                {
                    "role": "Admin",
                    "user_id": "user-1",
                    "token_exp": 123456,
                    "access_token": "token-1",
                    "email": "admin@hometower.local",
                }
            )
        ]

        asyncio.run(login_module.login_page(expired="1", next="/inventory"))

        assert any(
            label.text_value == "Your session expired. Please sign in again."
            for label in fake_ui.created["label"]
        )

        login_button = next(button for button in fake_ui.created["button"] if button.value == "Log in")
        _run(login_button.handlers["click"]())

        assert app.storage.user["role"] == "Admin"
        assert app.storage.user["user_id"] == "user-1"
        assert app.storage.user["access_token"] == "token-1"
        assert fake_ui.navigate.to_calls[-1] == ("/inventory", False)

    def test_login_empty_and_invalid_show_errors(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.pages.login as login_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, login_module, fake_ui, user={})
        fake_ui.run_javascript_responses = [
            json.dumps({"error": "empty"}),
            json.dumps({"error": "invalid"}),
        ]

        asyncio.run(login_module.login_page())
        login_button = next(button for button in fake_ui.created["button"] if button.value == "Log in")
        error_label = next(
            label
            for label in fake_ui.created["label"]
            if any("var(--ht-error)" in style for style in label.style_calls)
        )

        _run(login_button.handlers["click"]())
        assert error_label.text_value == "Please enter email and password"

        _run(login_button.handlers["click"]())
        assert error_label.text_value == "Invalid email or password"


class TestAccessDeniedPage:
    def test_access_denied_renders_home_button(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.pages.access_denied as access_denied_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, access_denied_module, fake_ui)

        asyncio.run(access_denied_module.access_denied_page())

        assert "403 — Access Denied" in [label.text_value for label in fake_ui.created["label"]]
        assert "You do not have permission to view this page." in [label.text_value for label in fake_ui.created["label"]]
        home_button = next(button for button in fake_ui.created["button"] if button.value == "Go to Home")
        _run(home_button.handlers["click"]())
        assert fake_ui.navigate.to_calls[-1] == ("/topology", False)


class TestDashboardPage:
    def test_relative_time_handles_boundaries(self) -> None:
        from src.ui.pages.dashboard import _relative_time

        now = datetime.now(timezone.utc)
        assert _relative_time((now - timedelta(seconds=30)).isoformat()) == "just now"
        assert _relative_time((now - timedelta(minutes=2)).isoformat()) == "2m ago"
        assert _relative_time((now - timedelta(hours=3)).isoformat()) == "3h ago"
        assert _relative_time((now - timedelta(days=4)).isoformat()) == "4d ago"
        assert _relative_time("not-an-iso") == "not-an-iso"

    def test_dashboard_shows_empty_recent_activity_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.pages.dashboard as dashboard_module

        fake_ui = FakeUI()
        app = install_fake_ui(monkeypatch, dashboard_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(dashboard_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(dashboard_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(dashboard_module, "get_ui_role", lambda: Role.Contributor)
        client_stub = AsyncClientStub(
            [
                httpx.Response(
                    200,
                    json={
                        "devices": 13,
                        "workspaces": 3,
                        "topologies": 5,
                        "offline_devices": 1,
                        "recent_edits": 7,
                        "power": {
                            "workspace_options": [{"id": None, "name": "All Workspaces"}],
                            "selected_workspace_id": None,
                            "selected_workspace_name": "All Workspaces",
                            "total_watts": 480,
                            "estimated_monthly_cost": 54.3,
                            "currency": "USD",
                        },
                        "inventory_breakdown": {"status_counts": [], "type_counts": []},
                        "recent_activity": [],
                    },
                ),
            ]
        )
        monkeypatch.setattr(
            dashboard_module.httpx,
            "AsyncClient",
            lambda *args, **kwargs: client_stub,
        )

        asyncio.run(dashboard_module.dashboard_page())

        assert any(label.text_value == "13" for label in fake_ui.created["label"])
        assert any(label.text_value == "3" for label in fake_ui.created["label"])
        assert any(label.text_value == "480W" for label in fake_ui.created["label"])
        assert any(label.text_value == "54.30 USD / month" for label in fake_ui.created["label"])
        assert any(
            label.text_value == "No recent activity yet"
            for label in fake_ui.created["label"]
        )
        assert len(client_stub.calls) == 1
        assert client_stub.calls[0][1].endswith("/api/dashboard/summary")
        assert app.storage.user["access_token"] == "token"

    def test_dashboard_renders_recent_activity_and_breakdown_links(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.pages.dashboard as dashboard_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, dashboard_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(dashboard_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(dashboard_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(dashboard_module, "get_ui_role", lambda: Role.Contributor)
        updated_at = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
        client_stub = AsyncClientStub(
            [
                httpx.Response(
                    200,
                    json={
                        "devices": 5,
                        "workspaces": 2,
                        "topologies": 3,
                        "offline_devices": 0,
                        "recent_edits": 1,
                        "power": {
                            "workspace_options": [{"id": None, "name": "All Workspaces"}],
                            "selected_workspace_id": None,
                            "selected_workspace_name": "All Workspaces",
                            "total_watts": 140,
                            "estimated_monthly_cost": 18.55,
                            "currency": "USD",
                        },
                        "inventory_breakdown": {
                            "status_counts": [
                                {
                                    "key": "Offline",
                                    "count": 2,
                                    "route": "/inventory?status=Offline",
                                }
                            ],
                            "type_counts": [
                                {
                                    "key": "Server",
                                    "count": 5,
                                    "route": "/inventory?type=Server",
                                }
                            ],
                        },
                        "recent_activity": [
                            {
                                "kind": "device_updated",
                                "title": "VM",
                                "subtitle": "Device updated",
                                "timestamp": updated_at,
                                "route": "/inventory?search=VM",
                            }
                        ],
                    },
                ),
            ]
        )
        monkeypatch.setattr(
            dashboard_module.httpx,
            "AsyncClient",
            lambda *args, **kwargs: client_stub,
        )

        asyncio.run(dashboard_module.dashboard_page())

        assert any(link.value == "VM" for link in fake_ui.created["link"])
        assert any(link.value == "Offline" for link in fake_ui.created["link"])
        assert any(link.value == "Server" for link in fake_ui.created["link"])
        assert any(
            'data-ht-route="/inventory?search=VM"' in prop
            for link in fake_ui.created["link"]
            for prop in link.props_calls
        )
        assert any(
            'data-ht-route="/inventory?status=Offline"' in prop
            for link in fake_ui.created["link"]
            for prop in link.props_calls
        )
        assert any(
            'data-ht-route="/inventory?type=Server"' in prop
            for link in fake_ui.created["link"]
            for prop in link.props_calls
        )
        recent_link = next(link for link in fake_ui.created["link"] if link.value == "VM")
        assert "click" not in recent_link.js_handlers
        _run(recent_link.handlers["click"](SimpleNamespace()))
        assert fake_ui.navigate.to_calls[-1] == ("/inventory?search=VM", False)

        status_link = next(link for link in fake_ui.created["link"] if link.value == "Offline")
        assert "click" not in status_link.js_handlers
        _run(status_link.handlers["click"](SimpleNamespace()))
        assert fake_ui.navigate.to_calls[-1] == ("/inventory?status=Offline", False)

        type_link = next(link for link in fake_ui.created["link"] if link.value == "Server")
        assert "click" not in type_link.js_handlers
        _run(type_link.handlers["click"](SimpleNamespace()))
        assert fake_ui.navigate.to_calls[-1] == ("/inventory?type=Server", False)
        assert any(label.text_value == "Device updated" for label in fake_ui.created["label"])
        assert any(label.text_value == "2m ago" for label in fake_ui.created["label"])
        assert any(label.text_value == "140W" for label in fake_ui.created["label"])
        assert len(client_stub.calls) == 1
        assert client_stub.calls[0][1].endswith("/api/dashboard/summary")

    def test_dashboard_workspace_switch_refreshes_summary_breakdown_and_activity(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.pages.dashboard as dashboard_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, dashboard_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(dashboard_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(dashboard_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(dashboard_module, "get_ui_role", lambda: Role.Contributor)
        updated_at = datetime.now(timezone.utc).isoformat()
        client_stub = AsyncClientStub(
            [
                httpx.Response(
                    200,
                    json={
                        "devices": 5,
                        "workspaces": 2,
                        "topologies": 3,
                        "offline_devices": 0,
                        "recent_edits": 1,
                        "power": {
                            "workspace_options": [
                                {"id": None, "name": "All Workspaces"},
                                {"id": "ws-1", "name": "Lab One"},
                            ],
                            "selected_workspace_id": None,
                            "selected_workspace_name": "All Workspaces",
                            "total_watts": 140,
                            "estimated_monthly_cost": 18.55,
                            "currency": "USD",
                        },
                        "inventory_breakdown": {
                            "status_counts": [
                                {
                                    "key": "Offline",
                                    "count": 2,
                                    "route": "/inventory?status=Offline",
                                }
                            ],
                            "type_counts": [
                                {
                                    "key": "Server",
                                    "count": 5,
                                    "route": "/inventory?type=Server",
                                }
                            ],
                        },
                        "recent_activity": [
                            {
                                "kind": "device_updated",
                                "title": "VM",
                                "subtitle": "Device updated",
                                "timestamp": updated_at,
                                "route": "/inventory?search=VM",
                            }
                        ],
                    },
                ),
                httpx.Response(
                    200,
                    json={
                        "devices": 19,
                        "workspaces": 1,
                        "topologies": 7,
                        "offline_devices": 4,
                        "recent_edits": 11,
                        "power": {
                            "workspace_options": [
                                {"id": None, "name": "All Workspaces"},
                                {"id": "ws-1", "name": "Lab One"},
                            ],
                            "selected_workspace_id": "ws-1",
                            "selected_workspace_name": "Lab One",
                            "total_watts": 220,
                            "estimated_monthly_cost": 28.75,
                            "currency": "USD",
                        },
                        "inventory_breakdown": {
                            "status_counts": [
                                {
                                    "key": "Online",
                                    "count": 9,
                                    "route": "/inventory?status=Online",
                                }
                            ],
                            "type_counts": [
                                {
                                    "key": "Switch",
                                    "count": 6,
                                    "route": "/inventory?type=Switch",
                                }
                            ],
                        },
                        "recent_activity": [
                            {
                                "kind": "device_updated",
                                "title": "Scoped VM",
                                "subtitle": "Device updated",
                                "timestamp": updated_at,
                                "route": "/inventory?search=Scoped%20VM",
                            }
                        ],
                    },
                ),
            ]
        )
        monkeypatch.setattr(
            dashboard_module.httpx,
            "AsyncClient",
            lambda *args, **kwargs: client_stub,
        )

        asyncio.run(dashboard_module.dashboard_page())

        workspace_select = fake_ui.created["select"][0]
        asyncio.run(workspace_select.handlers["value_change"](SimpleNamespace(value="ws-1")))

        labels = [label.text_value for label in fake_ui.created["label"]]
        links = [link.value for link in fake_ui.created["link"]]

        assert "19" in labels
        assert "7" in labels
        assert "11" in labels
        assert "220W" in labels
        assert "28.75 USD / month" in labels
        assert "Lab One" in labels
        assert "Online" in links
        assert "Switch" in links
        assert "Scoped VM" in links
        assert len(client_stub.calls) == 2
        assert any("history.replaceState" in script for script in fake_ui.run_javascript_calls)
        assert client_stub.call_kwargs[1]["params"] == {"workspace_id": "ws-1"}
        scoped_recent_link = [link for link in fake_ui.created["link"] if link.value == "Scoped VM"][-1]
        assert "click" not in scoped_recent_link.js_handlers
        _run(scoped_recent_link.handlers["click"](SimpleNamespace()))
        assert fake_ui.navigate.to_calls[-1] == ("/inventory?workspace_id=ws-1&search=Scoped%20VM", False)

        scoped_status_link = [link for link in fake_ui.created["link"] if link.value == "Online"][-1]
        assert "click" not in scoped_status_link.js_handlers
        _run(scoped_status_link.handlers["click"](SimpleNamespace()))
        assert fake_ui.navigate.to_calls[-1] == ("/inventory?workspace_id=ws-1&status=Online", False)

        inventory_button = [
            button for button in fake_ui.created["button"] if button.value == "View Inventory"
        ][-1]
        assert "click" not in inventory_button.js_handlers
        _run(inventory_button.handlers["click"]())
        assert fake_ui.navigate.to_calls[-1] == ("/inventory?workspace_id=ws-1", False)

    def test_dashboard_scope_query_renders_filtered_summary_on_first_load(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.pages.dashboard as dashboard_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, dashboard_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(dashboard_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(dashboard_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(dashboard_module, "get_ui_role", lambda: Role.Contributor)
        updated_at = datetime.now(timezone.utc).isoformat()
        client_stub = AsyncClientStub(
            [
                httpx.Response(
                    200,
                    json={
                        "devices": 12,
                        "workspaces": 1,
                        "topologies": 4,
                        "offline_devices": 2,
                        "recent_edits": 6,
                        "power": {
                            "workspace_options": [
                                {"id": None, "name": "All Workspaces"},
                                {"id": "ws-1", "name": "Lab One"},
                            ],
                            "selected_workspace_id": "ws-1",
                            "selected_workspace_name": "Lab One",
                            "total_watts": 215,
                            "estimated_monthly_cost": 27.5,
                            "currency": "USD",
                        },
                        "inventory_breakdown": {
                            "status_counts": [
                                {
                                    "key": "Online",
                                    "count": 8,
                                    "route": "/inventory?status=Online",
                                }
                            ],
                            "type_counts": [
                                {
                                    "key": "Switch",
                                    "count": 3,
                                    "route": "/inventory?type=Switch",
                                }
                            ],
                        },
                        "recent_activity": [
                            {
                                "kind": "device_updated",
                                "title": "Scoped VM",
                                "subtitle": "Device updated",
                                "timestamp": updated_at,
                                "route": "/inventory?search=Scoped%20VM",
                            }
                        ],
                    },
                ),
            ]
        )
        monkeypatch.setattr(
            dashboard_module.httpx,
            "AsyncClient",
            lambda *args, **kwargs: client_stub,
        )

        asyncio.run(dashboard_module.dashboard_page(workspace_id="ws-1"))

        labels = [label.text_value for label in fake_ui.created["label"]]
        links = [link.value for link in fake_ui.created["link"]]
        inventory_button = next(
            button for button in fake_ui.created["button"] if button.value == "View Inventory"
        )

        assert "12" in labels
        assert "4" in labels
        assert "6" in labels
        assert "215W" in labels
        assert "27.50 USD / month" in labels
        assert "Lab One" in labels
        assert "Online" in links
        assert "Switch" in links
        assert "Scoped VM" in links
        scoped_recent_link = next(link for link in fake_ui.created["link"] if link.value == "Scoped VM")
        assert "click" not in scoped_recent_link.js_handlers
        _run(scoped_recent_link.handlers["click"](SimpleNamespace()))
        assert fake_ui.navigate.to_calls[-1] == ("/inventory?workspace_id=ws-1&search=Scoped%20VM", False)

        scoped_status_link = next(link for link in fake_ui.created["link"] if link.value == "Online")
        assert "click" not in scoped_status_link.js_handlers
        _run(scoped_status_link.handlers["click"](SimpleNamespace()))
        assert fake_ui.navigate.to_calls[-1] == ("/inventory?workspace_id=ws-1&status=Online", False)

        assert "click" not in inventory_button.js_handlers
        _run(inventory_button.handlers["click"]())
        assert fake_ui.navigate.to_calls[-1] == ("/inventory?workspace_id=ws-1", False)
        assert client_stub.call_kwargs[0]["params"] == {"workspace_id": "ws-1"}

    def test_dashboard_hides_write_actions_for_reader(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.pages.dashboard as dashboard_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, dashboard_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(dashboard_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(dashboard_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(dashboard_module, "get_ui_role", lambda: Role.Reader)
        client_stub = AsyncClientStub(
            [
                httpx.Response(
                    200,
                    json={
                        "devices": 1,
                        "workspaces": 1,
                        "topologies": 1,
                        "offline_devices": 0,
                        "recent_edits": 0,
                        "power": {
                            "workspace_options": [{"id": None, "name": "All Workspaces"}],
                            "selected_workspace_id": None,
                            "selected_workspace_name": "All Workspaces",
                            "total_watts": 0,
                            "estimated_monthly_cost": None,
                            "currency": None,
                        },
                        "inventory_breakdown": {"status_counts": [], "type_counts": []},
                        "recent_activity": [],
                    },
                ),
            ]
        )
        monkeypatch.setattr(
            dashboard_module.httpx,
            "AsyncClient",
            lambda *args, **kwargs: client_stub,
        )

        asyncio.run(dashboard_module.dashboard_page())

        button_values = [button.value for button in fake_ui.created["button"]]
        assert "View Inventory" in button_values
        assert "Add Device" not in button_values
        assert "Manage Locations" not in button_values

    def test_dashboard_shows_write_actions_for_contributor(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.pages.dashboard as dashboard_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, dashboard_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(dashboard_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(dashboard_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(dashboard_module, "get_ui_role", lambda: Role.Contributor)
        client_stub = AsyncClientStub(
            [
                httpx.Response(
                    200,
                    json={
                        "devices": 1,
                        "workspaces": 1,
                        "topologies": 1,
                        "offline_devices": 0,
                        "recent_edits": 0,
                        "power": {
                            "workspace_options": [{"id": None, "name": "All Workspaces"}],
                            "selected_workspace_id": None,
                            "selected_workspace_name": "All Workspaces",
                            "total_watts": 0,
                            "estimated_monthly_cost": None,
                            "currency": None,
                        },
                        "inventory_breakdown": {"status_counts": [], "type_counts": []},
                        "recent_activity": [],
                    },
                ),
            ]
        )
        monkeypatch.setattr(
            dashboard_module.httpx,
            "AsyncClient",
            lambda *args, **kwargs: client_stub,
        )

        asyncio.run(dashboard_module.dashboard_page())

        button_values = [button.value for button in fake_ui.created["button"]]
        assert "View Inventory" in button_values
        assert "Add Device" in button_values
        assert "Manage Locations" in button_values


class TestInventoryPage:
    def test_inventory_hydrates_initial_type_and_status_filters(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.pages.inventory_page_controller as controller_module
        import src.ui.pages.inventory_table as inventory_table_module

        fake_ui = FakeUI()
        monkeypatch.setattr(controller_module, "ui", fake_ui)
        monkeypatch.setattr(inventory_table_module, "ui", fake_ui)
        monkeypatch.setattr(controller_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(controller_module, "render_type_chips", lambda *args, **kwargs: None)

        async def _fake_load_tag_chips(*args: object, **kwargs: object) -> list[dict[str, object]]:
            return []

        async def _fake_load_inventory_devices(
            token: str,
            workspace_id: str | None,
        ) -> list[object]:
            _ = token, workspace_id
            now = datetime.now(timezone.utc).isoformat()
            return [
                controller_module.DeviceResponseEnriched.model_validate(
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Server Active",
                        "type": "Server",
                        "status": "Active",
                        "ip": "10.0.0.10",
                        "mac": "aa:bb:cc:dd:ee:ff",
                        "os": "Linux",
                        "notes": "A",
                        "power_watts": None,
                        "location_name": "Rack 1",
                        "tags": [],
                        "custom_fields": [],
                        "services": [],
                        "networks": [],
                        "children": [],
                        "parent_chain": [],
                        "version": 1,
                        "created_at": now,
                        "updated_at": now,
                    }
                ),
                controller_module.DeviceResponseEnriched.model_validate(
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Server Offline",
                        "type": "Server",
                        "status": "Offline",
                        "ip": "10.0.0.20",
                        "mac": "aa:bb:cc:dd:ee:11",
                        "os": "Linux",
                        "notes": "B",
                        "power_watts": None,
                        "location_name": "Rack 1",
                        "tags": [],
                        "custom_fields": [],
                        "services": [],
                        "networks": [],
                        "children": [],
                        "parent_chain": [],
                        "version": 1,
                        "created_at": now,
                        "updated_at": now,
                    }
                ),
                controller_module.DeviceResponseEnriched.model_validate(
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Switch Offline",
                        "type": "Switch",
                        "status": "Offline",
                        "ip": "10.0.0.30",
                        "mac": "aa:bb:cc:dd:ee:22",
                        "os": "Linux",
                        "notes": "C",
                        "power_watts": None,
                        "location_name": "Rack 1",
                        "tags": [],
                        "custom_fields": [],
                        "services": [],
                        "networks": [],
                        "children": [],
                        "parent_chain": [],
                        "version": 1,
                        "created_at": now,
                        "updated_at": now,
                    }
                ),
            ]

        async def _fake_load_inventory_placement_data(
            token: str,
            device_ids: set[object],
            workspace_id: str | None,
        ) -> tuple[set[str], dict[str, int]]:
            _ = token, device_ids, workspace_id
            return set(), {}

        monkeypatch.setattr(controller_module, "load_tag_chips", _fake_load_tag_chips)
        monkeypatch.setattr(controller_module, "load_inventory_devices", _fake_load_inventory_devices)
        monkeypatch.setattr(
            controller_module,
            "load_inventory_placement_data",
            _fake_load_inventory_placement_data,
        )

        asyncio.run(
            controller_module.render_inventory_page(
                token="token",
                user_role=Role.Reader,
                initial_type="Server",
                initial_status="Offline",
            )
        )

        table = fake_ui.created["table"][0]
        status_scope = next(
            element
            for element in fake_ui.created["element"]
            if any("ht-banner ht-banner-info" in classes for classes in element.classes_calls)
        )
        clear_status_button = next(
            button for button in fake_ui.created["button"] if button.value == "Clear status filter"
        )
        assert any(label.text_value == "Status filter: Offline" for label in fake_ui.created["label"])
        assert status_scope.visible is True
        assert clear_status_button.visible is True
        assert [str(row.get("name")) for row in table.rows] == ["Server Offline"]

    def test_inventory_hydrates_initial_search_filter(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.pages.inventory_page_controller as controller_module
        import src.ui.pages.inventory_table as inventory_table_module

        fake_ui = FakeUI()
        monkeypatch.setattr(controller_module, "ui", fake_ui)
        monkeypatch.setattr(inventory_table_module, "ui", fake_ui)
        monkeypatch.setattr(controller_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(controller_module, "render_type_chips", lambda *args, **kwargs: None)

        async def _fake_load_tag_chips(*args: object, **kwargs: object) -> list[dict[str, object]]:
            return []

        device_one_id = str(uuid.uuid4())
        device_two_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        async def _fake_load_inventory_devices(
            token: str,
            workspace_id: str | None,
        ) -> list[object]:
            _ = token, workspace_id
            return [
                controller_module.DeviceResponseEnriched.model_validate(
                    {
                        "id": device_one_id,
                        "name": "VM Cluster",
                        "type": "Server",
                        "status": "Active",
                        "ip": "10.0.0.10",
                        "mac": "aa:bb:cc:dd:ee:ff",
                        "os": "Linux",
                        "notes": "A",
                        "power_watts": None,
                        "location_name": "Rack 1",
                        "tags": [],
                        "custom_fields": [],
                        "services": [],
                        "networks": [],
                        "children": [],
                        "parent_chain": [],
                        "version": 1,
                        "created_at": now,
                        "updated_at": now,
                    }
                ),
                controller_module.DeviceResponseEnriched.model_validate(
                    {
                        "id": device_two_id,
                        "name": "Core Switch",
                        "type": "Switch",
                        "status": "Active",
                        "ip": "10.0.0.20",
                        "mac": "aa:bb:cc:dd:ee:11",
                        "os": "Linux",
                        "notes": "B",
                        "power_watts": None,
                        "location_name": "Rack 1",
                        "tags": [],
                        "custom_fields": [],
                        "services": [],
                        "networks": [],
                        "children": [],
                        "parent_chain": [],
                        "version": 1,
                        "created_at": now,
                        "updated_at": now,
                    }
                ),
            ]

        async def _fake_load_inventory_placement_data(
            token: str,
            device_ids: set[object],
            workspace_id: str | None,
        ) -> tuple[set[str], dict[str, int]]:
            _ = token, device_ids, workspace_id
            return set(), {}

        monkeypatch.setattr(controller_module, "load_tag_chips", _fake_load_tag_chips)
        monkeypatch.setattr(controller_module, "load_inventory_devices", _fake_load_inventory_devices)
        monkeypatch.setattr(
            controller_module,
            "load_inventory_placement_data",
            _fake_load_inventory_placement_data,
        )

        asyncio.run(
            controller_module.render_inventory_page(
                token="token",
                user_role=Role.Reader,
                initial_search="vm",
            )
        )

        search_input = fake_ui.created["input"][0]
        table = fake_ui.created["table"][0]
        assert search_input.value == "vm"
        assert [str(row.get("id")) for row in table.rows] == [device_one_id]

    def test_inventory_hydrates_initial_workspace_scope_for_loaders(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.pages.inventory_page_controller as controller_module
        import src.ui.pages.inventory_table as inventory_table_module

        fake_ui = FakeUI()
        monkeypatch.setattr(controller_module, "ui", fake_ui)
        monkeypatch.setattr(inventory_table_module, "ui", fake_ui)
        monkeypatch.setattr(controller_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(controller_module, "render_type_chips", lambda *args, **kwargs: None)

        captured_workspace_ids: list[str | None] = []
        now = datetime.now(timezone.utc).isoformat()

        async def _fake_load_tag_chips(*args: object, **kwargs: object) -> list[dict[str, object]]:
            return []

        async def _fake_load_inventory_devices(
            token: str,
            workspace_id: str | None,
        ) -> list[object]:
            _ = token
            captured_workspace_ids.append(workspace_id)
            return [
                controller_module.DeviceResponseEnriched.model_validate(
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Scoped Server",
                        "type": "Server",
                        "status": "Active",
                        "ip": "10.0.0.10",
                        "mac": "aa:bb:cc:dd:ee:ff",
                        "os": "Linux",
                        "notes": "A",
                        "power_watts": None,
                        "location_name": "Rack 1",
                        "tags": [],
                        "custom_fields": [],
                        "services": [],
                        "networks": [],
                        "children": [],
                        "parent_chain": [],
                        "version": 1,
                        "created_at": now,
                        "updated_at": now,
                    }
                )
            ]

        async def _fake_load_inventory_placement_data(
            token: str,
            device_ids: set[object],
            workspace_id: str | None,
        ) -> tuple[set[str], dict[str, int]]:
            _ = token, device_ids
            captured_workspace_ids.append(workspace_id)
            return set(), {}

        monkeypatch.setattr(controller_module, "load_tag_chips", _fake_load_tag_chips)
        monkeypatch.setattr(controller_module, "load_inventory_devices", _fake_load_inventory_devices)
        monkeypatch.setattr(
            controller_module,
            "load_inventory_placement_data",
            _fake_load_inventory_placement_data,
        )

        asyncio.run(
            controller_module.render_inventory_page(
                token="token",
                user_role=Role.Reader,
                initial_workspace_id="ws-1",
            )
        )

        assert captured_workspace_ids == ["ws-1", "ws-1"]


class TestSettingsAboutPage:
    def test_settings_about_renders_stats(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.pages.settings_about as settings_about_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, settings_about_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(settings_about_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(settings_about_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(
            settings_about_module.httpx,
            "AsyncClient",
            lambda *args, **kwargs: AsyncClientStub(
                [
                    FakeResponse(200, {"uptime_seconds": 123.4}),
                    FakeResponse(
                        200,
                        {
                            "db_version": "PostgreSQL 16",
                            "db_size_bytes": 8 * 1024 * 1024,
                            "devices": 9,
                            "connections": 3,
                            "locations": 2,
                            "tags": 1,
                            "custom_fields": 4,
                            "diagrams": 5,
                            "users": 6,
                        },
                    ),
                ]
            ),
        )

        asyncio.run(settings_about_module.settings_about_page())

        labels = [label.text_value for label in fake_ui.created["label"]]
        assert "About Hometower" in labels
        assert "Hometower" in labels
        assert "1.0.0" in labels
        assert "123s" in labels
        assert "8.0 MB" in labels
        assert "6" in labels

    def test_settings_about_uses_fallbacks_on_http_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.pages.settings_about as settings_about_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, settings_about_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(settings_about_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(settings_about_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(
            settings_about_module.httpx,
            "AsyncClient",
            lambda *args, **kwargs: AsyncClientStub([httpx.HTTPError("boom")]),
        )

        asyncio.run(settings_about_module.settings_about_page())

        assert "—" in [label.text_value for label in fake_ui.created["label"]]


class TestSettingsProfilePage:
    def test_settings_profile_rejects_password_mismatch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.pages.settings_profile as settings_profile_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, settings_profile_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(settings_profile_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(settings_profile_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(settings_profile_module, "show_toast", lambda *args, **kwargs: None)

        asyncio.run(settings_profile_module.settings_profile_page())
        current_pw, new_pw, confirm_pw = fake_ui.created["input"]
        current_pw.value = "old"
        new_pw.value = "new-1"
        confirm_pw.value = "new-2"
        save_button = next(button for button in fake_ui.created["button"] if button.value == "Update Password")

        _run(save_button.handlers["click"]())

        assert any(label.text_value == "Passwords do not match." for label in fake_ui.created["label"])

    def test_settings_profile_updates_and_clears_inputs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.pages.settings_profile as settings_profile_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, settings_profile_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(settings_profile_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(settings_profile_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(settings_profile_module, "show_toast", lambda *args, **kwargs: None)
        monkeypatch.setattr(
            settings_profile_module.httpx,
            "AsyncClient",
            lambda *args, **kwargs: AsyncClientStub([FakeResponse(204)]),
        )

        asyncio.run(settings_profile_module.settings_profile_page())
        current_pw, new_pw, confirm_pw = fake_ui.created["input"]
        current_pw.value = "old"
        new_pw.value = "new"
        confirm_pw.value = "new"
        save_button = next(button for button in fake_ui.created["button"] if button.value == "Update Password")

        _run(save_button.handlers["click"]())

        assert current_pw.value == ""
        assert new_pw.value == ""
        assert confirm_pw.value == ""

    def test_settings_profile_surfaces_api_detail(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.pages.settings_profile as settings_profile_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, settings_profile_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(settings_profile_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(settings_profile_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(settings_profile_module, "show_toast", lambda *args, **kwargs: None)
        monkeypatch.setattr(
            settings_profile_module.httpx,
            "AsyncClient",
            lambda *args, **kwargs: AsyncClientStub([FakeResponse(400, {"detail": "Bad password"})]),
        )

        asyncio.run(settings_profile_module.settings_profile_page())
        current_pw, new_pw, confirm_pw = fake_ui.created["input"]
        current_pw.value = "old"
        new_pw.value = "new"
        confirm_pw.value = "new"
        save_button = next(button for button in fake_ui.created["button"] if button.value == "Update Password")

        _run(save_button.handlers["click"]())

        assert any(label.text_value == "Bad password" for label in fake_ui.created["label"])


class TestMapPage:
    def test_map_page_honors_auth_guard(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.pages.map as map_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, map_module, fake_ui, {"access_token": "token"})
        called: dict[str, str] = {}

        def _redirect(**kwargs: object) -> bool:
            current_path = kwargs.get("current_path")
            if isinstance(current_path, str):
                called["path"] = current_path
            return True

        monkeypatch.setattr(map_module, "redirect_if_unauthenticated", _redirect)

        asyncio.run(map_module.map_page())

        assert called["path"] == "/map"

    def test_map_page_injects_leaflet_assets_and_map_bridge(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.pages.map as map_module
        import src.ui.components.map_view as map_view_module

        expected_location = {
            "id": "loc-asset",
            "name": "Rack A",
            "lat": 51.0,
            "lng": -0.1,
            "device_count": 1,
            "devices": [
                {
                    "id": "dev-asset",
                    "name": "Node A",
                    "type": "Server",
                    "status": "Active",
                }
            ],
        }

        fake_ui = FakeUI()
        install_fake_ui(
            monkeypatch,
            map_module,
            fake_ui,
            {"access_token": "token", "theme": "dark"},
        )
        install_fake_ui(monkeypatch, map_view_module, fake_ui)
        fake_ui.run_javascript_responses = [{"ok": True, "marker_count": 1}]
        monkeypatch.setattr(map_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(map_module, "redirect_if_unauthenticated", lambda **kwargs: False)

        async def _load_locations() -> list[dict[str, object]]:
            return [expected_location]

        monkeypatch.setattr(map_module, "load_geo_locations", _load_locations)

        asyncio.run(map_module.map_page())

        assert any("leaflet/1.9.4/leaflet.css" in html for html in fake_ui.head_html)
        assert any("leaflet/1.9.4/leaflet.js" in html for html in fake_ui.head_html)
        assert any("leaflet.markercluster/1.5.3/MarkerCluster.css" in html for html in fake_ui.head_html)
        assert any(
            "leaflet.markercluster/1.5.3/MarkerCluster.Default.css" in html
            for html in fake_ui.head_html
        )
        assert any("leaflet.markercluster/1.5.3/leaflet.markercluster.js" in html for html in fake_ui.head_html)
        assert any("window.htRenderMap" in html for html in fake_ui.body_html)
        assert any("window.htFocusMapLocation" in html for html in fake_ui.body_html)
        assert any("tooltipText.textContent" in html for html in fake_ui.body_html)
        payload = _extract_ht_render_map_payload(fake_ui.run_javascript_calls)
        assert payload == {
            "element_id": "ht-map-canvas",
            "tile_url": map_view_module._OSM_DARK_TILE,
            "attribution": map_view_module._OSM_DARK_ATTRIBUTION,
            "locations": [expected_location],
        }

    def test_map_page_shows_empty_state_for_no_geo_locations(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.pages.map as map_module

        fake_ui = FakeUI()
        install_fake_ui(
            monkeypatch,
            map_module,
            fake_ui,
            {"access_token": "token", "theme": "dark"},
        )
        monkeypatch.setattr(map_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(map_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(map_module, "inject_map_view_assets", lambda: None)

        async def _load_locations() -> list[dict[str, object]]:
            return []

        monkeypatch.setattr(map_module, "load_geo_locations", _load_locations)

        asyncio.run(map_module.map_page())

        assert any(
            label.text_value
            == "No geographic locations yet — add a location with coordinates in Settings → Locations"
            for label in fake_ui.created["label"]
        )
        assert all("htRenderMap" not in script for script in fake_ui.run_javascript_calls)

    def test_map_page_falls_back_when_leaflet_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.pages.map as map_module

        fake_ui = FakeUI()
        install_fake_ui(
            monkeypatch,
            map_module,
            fake_ui,
            {"access_token": "token", "theme": "dark"},
        )
        fake_ui.run_javascript_responses = [{"ok": False, "error": "leaflet-unavailable"}]
        monkeypatch.setattr(map_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(map_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(map_module, "inject_map_view_assets", lambda: None)
        async def _load_locations() -> list[dict[str, object]]:
            return [
                {
                    "id": "loc-1",
                    "name": "Home Rack",
                    "lat": 40.123,
                    "lng": -72.5,
                    "device_count": 2,
                    "devices": [
                        {
                            "id": "dev-1",
                            "name": "Proxmox",
                            "type": "Server",
                            "status": "Active",
                        }
                    ],
                }
            ]

        monkeypatch.setattr(map_module, "load_geo_locations", _load_locations)

        asyncio.run(map_module.map_page())

        assert any("htRenderMap" in script for script in fake_ui.run_javascript_calls)
        assert any("dark_all" in script for script in fake_ui.run_javascript_calls)
        assert any(
            label.text_value.startswith(
                "Map unavailable in this browser session. Showing geo locations list instead"
            )
            for label in fake_ui.created["label"]
        )
        assert any(
            table.rows and table.rows[0]["name"] == "Home Rack"
            for table in fake_ui.created["table"]
        )

    def test_map_page_falls_back_when_map_bootstrap_js_throws(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.pages.map as map_module

        fake_ui = FakeUI()
        install_fake_ui(
            monkeypatch,
            map_module,
            fake_ui,
            {"access_token": "token", "theme": "dark"},
        )

        def _raise_bootstrap_error(_code: str) -> object:
            raise RuntimeError("bridge-missing")

        fake_ui.run_javascript_responses = [_raise_bootstrap_error]
        monkeypatch.setattr(map_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(map_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(map_module, "inject_map_view_assets", lambda: None)

        async def _load_locations() -> list[dict[str, object]]:
            return [
                {
                    "id": "loc-2",
                    "name": "Lab",
                    "lat": 12.34,
                    "lng": 56.78,
                    "device_count": 1,
                    "devices": [
                        {
                            "id": "dev-2",
                            "name": "Switch",
                            "type": "Switch",
                            "status": "Active",
                        }
                    ],
                }
            ]

        monkeypatch.setattr(map_module, "load_geo_locations", _load_locations)

        asyncio.run(map_module.map_page())

        assert any("htRenderMap" in script for script in fake_ui.run_javascript_calls)
        assert any(
            "bridge-missing" in label.text_value
            for label in fake_ui.created["label"]
        )
        assert any(
            table.rows and table.rows[0]["name"] == "Lab"
            for table in fake_ui.created["table"]
        )

    def test_map_page_marker_selection_opens_drawer_and_links_to_topology(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.pages.map as map_module

        fake_ui = FakeUI()
        install_fake_ui(
            monkeypatch,
            map_module,
            fake_ui,
            {"access_token": "token", "theme": "light"},
        )
        fake_ui.run_javascript_responses = [{"ok": True, "marker_count": 1}, None]
        monkeypatch.setattr(map_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(map_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(map_module, "inject_map_view_assets", lambda: None)
        async def _load_locations() -> list[dict[str, object]]:
            return [
                {
                    "id": "loc-1",
                    "name": "Garage",
                    "lat": 50.0,
                    "lng": 12.0,
                    "device_count": 1,
                    "devices": [
                        {
                            "id": "dev-1",
                            "name": "Edge Router",
                            "type": "Router",
                            "status": "Active",
                        }
                    ],
                }
            ]

        monkeypatch.setattr(map_module, "load_geo_locations", _load_locations)

        asyncio.run(map_module.map_page())
        assert any(
            "ht-page-shell" in classes
            for column in fake_ui.created["column"]
            for classes in column.classes_calls
        )
        assert any(
            "ht-page-header" in classes
            for column in fake_ui.created["column"]
            for classes in column.classes_calls
        )
        handler = fake_ui.on_handlers["map_location_selected"]
        _run(handler(SimpleNamespace(args={"location_id": "loc-1"})))

        device_button = next(button for button in fake_ui.created["button"] if button.value == "Edge Router")
        assert any("ht-btn ht-btn-secondary" in classes for classes in device_button.classes_calls)
        _run(device_button.handlers["click"]())

        drawer = next(
            element
            for element in fake_ui.created["element"]
            if any('id="ht-map-drawer"' in props for props in element.props_calls)
        )
        assert drawer.visible is True
        assert "add:ht-map-drawer-open" in drawer.classes_calls

        close_button = next(button for button in fake_ui.created["button"] if button.value == "close")
        _run(close_button.handlers["click"]())

        assert drawer.visible is False
        assert "remove:ht-map-drawer-open" in drawer.classes_calls
        assert fake_ui.navigate.to_calls[-1] == ("/topology?device_id=dev-1", False)
