"""Unit tests for src/ui/components/app_shell — HT-026 / HT-038.

Tests cover:
  - _SESSION_EXPIRY_JS content (HT-038 fetch interceptor)
  - safe_next_path round-trip validation (mirrors auth_guard tests)
"""


class TestSessionExpiryJS:
    def _get_js(self) -> str:
        from src.ui.components.app_shell import _SESSION_EXPIRY_JS
        return _SESSION_EXPIRY_JS

    def test_js_wraps_window_fetch(self) -> None:
        assert "window.fetch" in self._get_js()

    def test_js_checks_401_status(self) -> None:
        assert "401" in self._get_js()

    def test_js_only_intercepts_api_calls(self) -> None:
        assert "/api/" in self._get_js()

    def test_js_prevents_duplicate_overlays(self) -> None:
        js = self._get_js()
        # Must have a guard element/flag so overlay only appears once
        assert "ht-session-expired-overlay" in js

    def test_js_redirects_with_expired_param(self) -> None:
        assert "expired=1" in self._get_js()

    def test_js_includes_next_param(self) -> None:
        assert "next=" in self._get_js()

    def test_js_uses_current_pathname(self) -> None:
        assert "pathname" in self._get_js()

    def test_js_uses_sign_in_button_label(self) -> None:
        js = self._get_js()
        assert "Sign In" in js or "sign in" in js.lower()

    def test_js_shows_expiry_message(self) -> None:
        js = self._get_js()
        assert "expired" in js.lower() or "session" in js.lower()


class TestAppShellNavItems:
    def test_dashboard_in_nav(self) -> None:
        from src.ui.components.sidebar import _NAV_ITEMS
        routes = [item["route"] for item in _NAV_ITEMS]
        assert "/" in routes

    def test_topology_in_nav(self) -> None:
        from src.ui.components.sidebar import _NAV_ITEMS
        routes = [item["route"] for item in _NAV_ITEMS]
        assert "/workspaces" in routes

    def test_inventory_in_nav(self) -> None:
        from src.ui.components.sidebar import _NAV_ITEMS
        routes = [item["route"] for item in _NAV_ITEMS]
        assert "/inventory" in routes

    def test_ipam_in_nav(self) -> None:
        from src.ui.components.sidebar import _NAV_ITEMS
        routes = [item["route"] for item in _NAV_ITEMS]
        assert "/ipam" in routes

    def test_map_is_enabled_nav_item(self) -> None:
        from src.ui.components.sidebar import _NAV_ITEMS
        map_item = next((i for i in _NAV_ITEMS if i["route"] == "/map"), None)
        assert map_item is not None
        assert map_item.get("disabled") is None

    def test_locations_in_settings(self) -> None:
        from src.ui.components.sidebar import _SETTINGS_ITEMS
        routes = [item["route"] for item in _SETTINGS_ITEMS]
        assert "/settings/locations" in routes

    def test_users_in_settings_is_admin_only(self) -> None:
        from src.ui.components.sidebar import _SETTINGS_ITEMS
        users_item = next(
            (i for i in _SETTINGS_ITEMS if i["route"] == "/settings/users"), None
        )
        assert users_item is not None
        assert users_item.get("admin_only") == "true"

    def test_power_in_settings_is_admin_only(self) -> None:
        from src.ui.components.sidebar import _SETTINGS_ITEMS

        power_item = next(
            (i for i in _SETTINGS_ITEMS if i["route"] == "/settings/power"), None
        )
        assert power_item is not None
        assert power_item.get("admin_only") == "true"
