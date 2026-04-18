"""Execution tests for shell-backed NiceGUI pages."""
from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

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
                httpx.Response(200, json={"total": 13}),
                httpx.Response(200, json={"total": 3}),
                httpx.Response(200, json=[{"id": "loc-1"}]),
                httpx.Response(200, json=[{"id": "tag-1"}, {"id": "tag-2"}]),
                httpx.Response(200, json={"items": []}),
                httpx.Response(
                    200,
                    json={
                        "total_watts": 480,
                        "estimated_monthly_cost": 54.3,
                        "currency": "USD",
                        "by_location": [
                            {
                                "location_name": "Rack A",
                                "total_watts": 480,
                                "parent_location_id": None,
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

        assert any(label.text_value == "13" for label in fake_ui.created["label"])
        assert any(label.text_value == "3" for label in fake_ui.created["label"])
        assert any(label.text_value == "480W" for label in fake_ui.created["label"])
        assert any(label.text_value == "54.30 USD / month" for label in fake_ui.created["label"])
        assert any(label.text_value == "Rack A" for label in fake_ui.created["label"])
        assert any(label.text_value == "No devices yet — add one from Topology" for label in fake_ui.created["label"])
        assert len(client_stub.calls) == 6
        assert any(url.endswith("/api/power/summary") for _, url in client_stub.calls)
        assert app.storage.user["access_token"] == "token"

    def test_dashboard_renders_recent_devices(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.pages.dashboard as dashboard_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, dashboard_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(dashboard_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(dashboard_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(dashboard_module, "get_ui_role", lambda: Role.Contributor)
        updated_at = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
        client_stub = AsyncClientStub(
            [
                httpx.Response(200, json={"total": 5}),
                httpx.Response(200, json={"total": 2}),
                httpx.Response(200, json=[{"id": "loc-1"}]),
                httpx.Response(200, json=[{"id": "tag-1"}]),
                httpx.Response(200, json={"items": [{"name": "VM", "type": "Server", "updated_at": updated_at}]}),
                httpx.Response(
                    200,
                    json={
                        "total_watts": 140,
                        "estimated_monthly_cost": 18.55,
                        "currency": "USD",
                        "by_location": [
                            {
                                "location_name": "Office Rack",
                                "total_watts": 140,
                                "parent_location_id": None,
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

        assert any(label.text_value == "VM" for label in fake_ui.created["label"])
        assert any(label.text_value == "Server" for label in fake_ui.created["label"])
        assert any(label.text_value == "2m ago" for label in fake_ui.created["label"])
        assert any(label.text_value == "140W" for label in fake_ui.created["label"])
        assert any(label.text_value == "Office Rack" for label in fake_ui.created["label"])
        assert len(client_stub.calls) == 6
        assert any(url.endswith("/api/power/summary") for _, url in client_stub.calls)

    def test_dashboard_hides_write_actions_for_reader(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.pages.dashboard as dashboard_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, dashboard_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(dashboard_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(dashboard_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(dashboard_module, "get_ui_role", lambda: Role.Reader)
        client_stub = AsyncClientStub(
            [
                httpx.Response(200, json={"total": 1}),
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
                httpx.Response(200, json={"total": 1}),
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
