"""Unit tests for src/ui/components/auth_guard — HT-038."""
from unittest.mock import MagicMock, patch

import pytest


class TestSafeNextPath:
    def test_valid_simple_path(self) -> None:
        from src.ui.components.auth_guard import safe_next_path
        assert safe_next_path("/topology") == "/topology"

    def test_valid_nested_path(self) -> None:
        from src.ui.components.auth_guard import safe_next_path
        assert safe_next_path("/settings/locations") == "/settings/locations"

    def test_valid_root(self) -> None:
        from src.ui.components.auth_guard import safe_next_path
        assert safe_next_path("/") == "/"

    def test_rejects_external_https(self) -> None:
        from src.ui.components.auth_guard import safe_next_path
        assert safe_next_path("https://evil.com") is None

    def test_rejects_external_http(self) -> None:
        from src.ui.components.auth_guard import safe_next_path
        assert safe_next_path("http://evil.com") is None

    def test_rejects_protocol_relative(self) -> None:
        from src.ui.components.auth_guard import safe_next_path
        assert safe_next_path("//evil.com") is None

    def test_rejects_no_leading_slash(self) -> None:
        from src.ui.components.auth_guard import safe_next_path
        assert safe_next_path("topology") is None

    def test_rejects_empty_string(self) -> None:
        from src.ui.components.auth_guard import safe_next_path
        assert safe_next_path("") is None

    def test_rejects_none_like_empty(self) -> None:
        from src.ui.components.auth_guard import safe_next_path
        assert safe_next_path("   ") is None


class TestRedirectIfUnauthenticated:
    def test_no_token_redirects_to_login(self) -> None:
        from src.ui.components.auth_guard import redirect_if_unauthenticated

        with patch("src.ui.components.auth_guard.nicegui_app") as mock_app:
            mock_app.storage.user = {}  # no token
            with patch("src.ui.components.auth_guard.get_ui_role", return_value=None):
                with patch("src.ui.components.auth_guard.ui") as mock_ui:
                    result = redirect_if_unauthenticated()

        assert result is True
        mock_ui.navigate.to.assert_called_once_with("/login")

    def test_valid_token_returns_false(self) -> None:
        from src.models.types import Role
        from src.ui.components.auth_guard import redirect_if_unauthenticated

        with patch("src.ui.components.auth_guard.nicegui_app") as mock_app:
            mock_app.storage.user = {"role": "Admin"}
            with patch("src.ui.components.auth_guard.get_ui_role", return_value=Role.Admin):
                result = redirect_if_unauthenticated()

        assert result is False

    def test_expired_token_with_path_redirects_with_expired_param(self) -> None:
        from src.ui.components.auth_guard import redirect_if_unauthenticated

        with patch("src.ui.components.auth_guard.nicegui_app") as mock_app:
            mock_app.storage.user = {"role": "Admin"}
            with patch("src.ui.components.auth_guard.get_ui_role", return_value=None):
                with patch("src.ui.components.auth_guard.ui") as mock_ui:
                    result = redirect_if_unauthenticated(current_path="/topology")

        assert result is True
        mock_ui.navigate.to.assert_called_once_with("/login?expired=1&next=/topology")

    def test_expired_token_without_path_redirects_to_plain_login(self) -> None:
        from src.ui.components.auth_guard import redirect_if_unauthenticated

        with patch("src.ui.components.auth_guard.nicegui_app") as mock_app:
            mock_app.storage.user = {"role": "Admin"}
            with patch("src.ui.components.auth_guard.get_ui_role", return_value=None):
                with patch("src.ui.components.auth_guard.ui") as mock_ui:
                    result = redirect_if_unauthenticated()

        assert result is True
        mock_ui.navigate.to.assert_called_once_with("/login")

    def test_expired_token_with_unsafe_path_falls_back_to_plain_login(self) -> None:
        from src.ui.components.auth_guard import redirect_if_unauthenticated

        with patch("src.ui.components.auth_guard.nicegui_app") as mock_app:
            mock_app.storage.user = {"role": "Admin"}
            with patch("src.ui.components.auth_guard.get_ui_role", return_value=None):
                with patch("src.ui.components.auth_guard.ui") as mock_ui:
                    result = redirect_if_unauthenticated(current_path="https://evil.com")

        assert result is True
        mock_ui.navigate.to.assert_called_once_with("/login")

    def test_no_token_with_path_redirects_to_plain_login(self) -> None:
        """No token at all (not expired, just absent) → no expired param."""
        from src.ui.components.auth_guard import redirect_if_unauthenticated

        with patch("src.ui.components.auth_guard.nicegui_app") as mock_app:
            mock_app.storage.user = {}  # no token — not expired, just missing
            with patch("src.ui.components.auth_guard.get_ui_role", return_value=None):
                with patch("src.ui.components.auth_guard.ui") as mock_ui:
                    result = redirect_if_unauthenticated(current_path="/inventory")

        assert result is True
        # Must NOT add expired=1 when there was no token to begin with
        mock_ui.navigate.to.assert_called_once_with("/login")
