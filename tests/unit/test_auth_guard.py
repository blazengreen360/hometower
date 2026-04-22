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

    def test_valid_path_with_query_and_hash(self) -> None:
        from src.ui.components.auth_guard import safe_next_path

        target = "/topology?workspace_id=ws-123&topology_id=tp-456&device_id=dev-789#details"
        assert safe_next_path(target) == target

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
        mock_ui.navigate.to.assert_called_once_with("/login?expired=1&next=%2Ftopology")

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

    def test_expired_token_with_query_path_encodes_next_param(self) -> None:
        from src.ui.components.auth_guard import redirect_if_unauthenticated

        current_path = "/topology?workspace_id=ws-1&topology_id=topo-1&device_id=dev-1"
        with patch("src.ui.components.auth_guard.nicegui_app") as mock_app:
            mock_app.storage.user = {"role": "Admin"}
            with patch("src.ui.components.auth_guard.get_ui_role", return_value=None):
                with patch("src.ui.components.auth_guard.ui") as mock_ui:
                    result = redirect_if_unauthenticated(current_path=current_path)

        assert result is True
        mock_ui.navigate.to.assert_called_once_with(
            "/login?expired=1&next=%2Ftopology%3Fworkspace_id%3Dws-1%26topology_id%3Dtopo-1%26device_id%3Ddev-1"
        )

    def test_no_token_with_path_redirects_with_next_param_only(self) -> None:
        """No token at all preserves a safe next target without expired=1."""
        from src.ui.components.auth_guard import redirect_if_unauthenticated

        with patch("src.ui.components.auth_guard.nicegui_app") as mock_app:
            mock_app.storage.user = {}  # no token — not expired, just missing
            with patch("src.ui.components.auth_guard.get_ui_role", return_value=None):
                with patch("src.ui.components.auth_guard.ui") as mock_ui:
                    result = redirect_if_unauthenticated(current_path="/inventory")

        assert result is True
        mock_ui.navigate.to.assert_called_once_with("/login?next=%2Finventory")

    def test_no_token_with_query_path_redirects_with_encoded_next_only(self) -> None:
        from src.ui.components.auth_guard import redirect_if_unauthenticated

        current_path = "/topology?workspace_id=ws-1&topology_id=topo-1&device_id=dev-1"
        with patch("src.ui.components.auth_guard.nicegui_app") as mock_app:
            mock_app.storage.user = {}  # no token — not expired, just missing
            with patch("src.ui.components.auth_guard.get_ui_role", return_value=None):
                with patch("src.ui.components.auth_guard.ui") as mock_ui:
                    result = redirect_if_unauthenticated(current_path=current_path)

        assert result is True
        mock_ui.navigate.to.assert_called_once_with(
            "/login?next=%2Ftopology%3Fworkspace_id%3Dws-1%26topology_id%3Dtopo-1%26device_id%3Ddev-1"
        )
