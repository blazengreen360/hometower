"""Execution tests for settings pages."""
from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from types import SimpleNamespace

import httpx
import pytest

from src.models.types import Role
from tests.unit.nicegui_fakes import AsyncClientStub, FakeUI, install_fake_ui


class _AwaitableValue:
    def __init__(self, value: object) -> None:
        self.value = value

    def __await__(self) -> Iterator[object]:
        async def _coro() -> object:
            return self.value

        return _coro().__await__()


class _JavaScriptStub:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, code: str) -> _AwaitableValue:
        self.calls.append(code)
        return _AwaitableValue(None)


async def _invoke(handler: Callable[..., object]) -> object:
    result = handler()
    if inspect.isawaitable(result):
        return await result
    return result


async def _drain_pending(fake_ui: FakeUI) -> None:
    if not fake_ui.pending_tasks:
        return
    pending = list(fake_ui.pending_tasks)
    fake_ui.pending_tasks.clear()
    await asyncio.gather(*pending)


@contextmanager
def _noop_shell() -> Iterator[None]:
    yield


class TestSettingsDataPage:
    def test_settings_data_export_and_import(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.pages.settings_data as settings_data_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, settings_data_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(settings_data_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(settings_data_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(settings_data_module, "get_ui_role", lambda: Role.Admin)
        js_stub = _JavaScriptStub()
        fake_ui.run_javascript = js_stub  # type: ignore[assignment]
        client_stub = AsyncClientStub([httpx.Response(200, json={"devices": 2, "connections": 1})])
        monkeypatch.setattr(settings_data_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

        async def exercise() -> None:
            await settings_data_module.settings_data_page()
            export_button = next(button for button in fake_ui.created["button"] if button.value == "Export JSON")
            await _invoke(export_button.handlers["click"])
            assert any("/api/export" in code for code in js_stub.calls)

            upload = fake_ui.created["upload"][0]
            await _invoke(lambda: upload.handlers["upload"](SimpleNamespace(name="export.json", content=b"{\"ok\": true}")))
            import_button = next(button for button in fake_ui.created["button"] if button.value == "Import JSON")
            await _invoke(import_button.handlers["click"])
            assert fake_ui.created["dialog"][0].opened is True

            confirm_input = fake_ui.created["input"][-1]
            confirm_input.value = "CONFIRM"
            proceed_button = next(button for button in fake_ui.created["button"] if button.value == "Proceed")
            await _invoke(proceed_button.handlers["click"])
            await _drain_pending(fake_ui)

        asyncio.run(exercise())

        assert any(notification[1].get("type") == "positive" for notification in fake_ui.notifications)
        assert fake_ui.navigate.reload_calls == 1
        assert any(method == "POST" for method, _ in client_stub.calls)

    def test_settings_data_reader_export_is_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.pages.settings_data as settings_data_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, settings_data_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(settings_data_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(settings_data_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(settings_data_module, "get_ui_role", lambda: Role.Reader)

        asyncio.run(settings_data_module.settings_data_page())

        export_button = next(button for button in fake_ui.created["button"] if button.value == "Export JSON")
        assert any("disable" in prop for prop in export_button.props_calls)
        assert any(
            "Requires: Contributor or higher" in str(label.value)
            for label in fake_ui.created["label"]
        )

    def test_settings_data_contributor_export_is_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.pages.settings_data as settings_data_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, settings_data_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(settings_data_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(settings_data_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(settings_data_module, "get_ui_role", lambda: Role.Contributor)
        js_stub = _JavaScriptStub()
        fake_ui.run_javascript = js_stub  # type: ignore[assignment]

        asyncio.run(settings_data_module.settings_data_page())

        export_button = next(button for button in fake_ui.created["button"] if button.value == "Export JSON")
        # Simulate click handler invocation using awaitable-safe helper
        asyncio.run(_invoke(export_button.handlers["click"]))
        assert any("/api/export" in code for code in js_stub.calls)


class TestSettingsLocationsPage:
    def test_settings_locations_page_handles_create_edit_delete(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.pages.settings_locations as settings_locations_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, settings_locations_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(settings_locations_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(settings_locations_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(settings_locations_module, "redirect_if_insufficient_role", lambda *args, **kwargs: False)

        modal_state: dict[str, object] = {"mode": None, "errors": []}
        captured: dict[str, object] = {}

        def fake_create_location_modal(form: dict[str, str], on_submit: Callable[[], object]) -> object:
            captured["form"] = form
            captured["submit"] = on_submit

            def open_for_mode(mode: str) -> None:
                modal_state["mode"] = mode

            def close() -> None:
                modal_state["mode"] = "closed"

            def set_error(message: str) -> None:
                modal_state.setdefault("errors", [])
                errors = modal_state["errors"]
                assert isinstance(errors, list)
                errors.append(message)

            def clear_error() -> None:
                modal_state["errors"] = []

            return SimpleNamespace(
                open_for_mode=open_for_mode,
                close=close,
                set_error=set_error,
                clear_error=clear_error,
            )

        monkeypatch.setattr(settings_locations_module, "create_location_modal", fake_create_location_modal)

        def make_response(method: str, status: int, payload: object) -> httpx.Response:
            return httpx.Response(
                status,
                json=payload,
                request=httpx.Request(method, "http://test.local"),
            )

        client_stub = AsyncClientStub(
            [
                make_response("GET", 200, [{"id": "loc-1", "name": "Rack One", "type": "rack", "rack": "R1", "row": "1", "lat": None, "lng": None, "parent_id": None}]),
                make_response("POST", 201, {"id": "loc-2"}),
                make_response("GET", 200, [{"id": "loc-1", "name": "Rack One", "type": "rack", "rack": "R1", "row": "1", "lat": None, "lng": None, "parent_id": None}, {"id": "loc-2", "name": "Geo One", "type": "geo", "lat": 1.0, "lng": 2.0, "rack": None, "row": None, "parent_id": None}]),
                make_response("PATCH", 200, {"id": "loc-1"}),
                make_response("GET", 200, [{"id": "loc-1", "name": "Rack One Renamed", "type": "rack", "rack": "R2", "row": "2", "lat": None, "lng": None, "parent_id": None}, {"id": "loc-2", "name": "Geo One", "type": "geo", "lat": 1.0, "lng": 2.0, "rack": None, "row": None, "parent_id": None}]),
                make_response("DELETE", 204, {}),
                make_response("GET", 200, []),
            ]
        )
        monkeypatch.setattr(settings_locations_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

        async def exercise() -> None:
            await settings_locations_module.settings_locations_page()
            table = fake_ui.created["table"][0]
            assert len(table.rows) == 1

            create_button = next(button for button in fake_ui.created["button"] if button.value == "+ Add Location")
            await _invoke(create_button.handlers["click"])
            assert modal_state["mode"] == "create"
            form = captured["form"]
            assert isinstance(form, dict)
            form["name"] = "Geo One"
            form["type"] = "geo"
            form["lat"] = "10.5"
            form["lng"] = "20.5"
            await _invoke(captured["submit"])
            assert len(table.rows) == 2

            await _invoke(lambda: table.handlers["edit"](SimpleNamespace(args=table.rows[0])))
            assert modal_state["mode"] == "edit"
            form["type"] = "geo"
            form["lat"] = "bad"
            form["lng"] = "bad"
            await _invoke(captured["submit"])
            errors = modal_state["errors"]
            assert isinstance(errors, list)
            assert errors[-1] == "Latitude and longitude must be valid numbers."

            form["type"] = "rack"
            form["rack"] = "R2"
            form["row"] = "2"
            form["name"] = "Rack One Renamed"
            await _invoke(captured["submit"])
            assert any(row["name"] == "Rack One Renamed" for row in table.rows)

            await _invoke(lambda: table.handlers["delete_row"](SimpleNamespace(args=table.rows[0])))
            await _drain_pending(fake_ui)
            delete_button = next(button for button in fake_ui.created["button"] if button.value == "Delete")
            await _invoke(delete_button.handlers["click"])
            await _drain_pending(fake_ui)

        asyncio.run(exercise())

        assert any(notification[1].get("type") == "positive" for notification in fake_ui.notifications)
        assert any(method == "POST" for method, _ in client_stub.calls)
        assert any(method == "PATCH" for method, _ in client_stub.calls)
        assert any(method == "DELETE" for method, _ in client_stub.calls)

    def test_settings_locations_page_shows_friendly_server_validation_and_recovers(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.pages.settings_locations as settings_locations_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, settings_locations_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(settings_locations_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(settings_locations_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(settings_locations_module, "redirect_if_insufficient_role", lambda *args, **kwargs: False)

        modal_state: dict[str, object] = {"mode": None, "errors": []}
        captured: dict[str, object] = {}

        def fake_create_location_modal(form: dict[str, str], on_submit: Callable[[], object]) -> object:
            captured["form"] = form
            captured["submit"] = on_submit

            def open_for_mode(mode: str) -> None:
                modal_state["mode"] = mode

            def close() -> None:
                modal_state["mode"] = "closed"

            def set_error(message: str) -> None:
                modal_state.setdefault("errors", [])
                errors = modal_state["errors"]
                assert isinstance(errors, list)
                errors.append(message)

            def clear_error() -> None:
                modal_state["errors"] = []

            return SimpleNamespace(
                open_for_mode=open_for_mode,
                close=close,
                set_error=set_error,
                clear_error=clear_error,
            )

        monkeypatch.setattr(settings_locations_module, "create_location_modal", fake_create_location_modal)

        def make_response(method: str, status: int, payload: object) -> httpx.Response:
            return httpx.Response(
                status,
                json=payload,
                request=httpx.Request(method, "http://test.local"),
            )

        client_stub = AsyncClientStub(
            [
                make_response("GET", 200, []),
                make_response(
                    "POST",
                    422,
                    {
                        "detail": "[{'type': 'string_too_short', 'loc': ['body', 'name'], 'msg': 'String should have at least 1 character', 'input': ''}]"
                    },
                ),
                make_response("POST", 201, {"id": "loc-1"}),
                make_response(
                    "GET",
                    200,
                    [
                        {
                            "id": "loc-1",
                            "name": "Rack A",
                            "type": "rack",
                            "rack": "R1",
                            "row": "1",
                            "lat": None,
                            "lng": None,
                            "parent_id": None,
                        }
                    ],
                ),
            ]
        )
        monkeypatch.setattr(settings_locations_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

        async def exercise() -> None:
            await settings_locations_module.settings_locations_page()
            table = fake_ui.created["table"][0]
            create_button = next(button for button in fake_ui.created["button"] if button.value == "+ Add Location")
            await _invoke(create_button.handlers["click"])

            form = captured["form"]
            assert isinstance(form, dict)
            form["name"] = "Rack A"
            form["type"] = "rack"
            await _invoke(captured["submit"])

            errors = modal_state["errors"]
            assert isinstance(errors, list)
            assert errors == ["Name is required."]
            assert modal_state["mode"] == "create"

            await _invoke(captured["submit"])
            assert modal_state["mode"] == "closed"
            assert len(table.rows) == 1

        asyncio.run(exercise())


class TestSettingsUsersPage:
    def test_settings_users_page_shows_friendly_server_validation_and_clears_on_input(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.pages.settings_users as settings_users_module

        fake_ui = FakeUI()
        install_fake_ui(
            monkeypatch,
            settings_users_module,
            fake_ui,
            {"access_token": "token", "user_id": "user-1"},
        )
        monkeypatch.setattr(settings_users_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(settings_users_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(settings_users_module, "redirect_if_insufficient_role", lambda *args, **kwargs: False)

        def make_response(method: str, status: int, payload: object) -> httpx.Response:
            return httpx.Response(
                status,
                json=payload,
                request=httpx.Request(method, "http://test.local"),
            )

        client_stub = AsyncClientStub(
            [
                make_response(
                    "GET",
                    200,
                    [
                        {
                            "id": "user-1",
                            "username": "admin",
                            "email": "admin@test.local",
                            "role": "Admin",
                            "is_active": True,
                        }
                    ],
                ),
                make_response(
                    "POST",
                    422,
                    {
                        "detail": "&quot;[{\"type\":\"value_error\",\"loc\":[\"body\",\"username\"],\"msg\":\"Value error, username cannot be empty or whitespace-only\",\"input\":\"\"}]&quot;"
                    },
                ),
                make_response("POST", 201, {"id": "user-2"}),
                make_response(
                    "GET",
                    200,
                    [
                        {
                            "id": "user-1",
                            "username": "admin",
                            "email": "admin@test.local",
                            "role": "Admin",
                            "is_active": True,
                        },
                        {
                            "id": "user-2",
                            "username": "newuser",
                            "email": "newuser@test.local",
                            "role": "Reader",
                            "is_active": True,
                        },
                    ],
                ),
            ]
        )
        monkeypatch.setattr(settings_users_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

        async def exercise() -> None:
            await settings_users_module.settings_users_page()
            table = fake_ui.created["table"][0]
            add_button = next(button for button in fake_ui.created["button"] if button.value == "+ Add User")
            save_button = next(button for button in fake_ui.created["button"] if button.value == "Save")

            await _invoke(add_button.handlers["click"])
            username_input, email_input, password_input = [
                input_element
                for input_element in fake_ui.created["input"]
                if input_element.label in {"Username", "Email", "Password"}
            ]
            role_select = fake_ui.created["select"][0]

            password_input.value = "Password123!"
            await _invoke(save_button.handlers["click"])

            error_label = next(
                label
                for label in fake_ui.created["label"]
                if any("var(--ht-error)" in style for style in label.style_calls)
            )
            dialog = fake_ui.created["dialog"][0]
            assert dialog.closed is False
            assert error_label.visible is True
            assert error_label.text_value == "Username is required."

            username_input.value = "newuser"
            await _invoke(
                lambda: username_input.handlers["value_change"](SimpleNamespace(value="newuser"))
            )
            assert error_label.visible is False
            assert error_label.text_value == ""

            email_input.value = "newuser@test.local"
            role_select.value = "Reader"
            await _invoke(save_button.handlers["click"])

            assert len(table.rows) == 2
            assert any(notification[1].get("type") == "positive" for notification in fake_ui.notifications)

        asyncio.run(exercise())


class TestSettingsProfilePage:
    def test_settings_profile_shows_friendly_validation_for_invalid_and_incorrect_passwords(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.pages.settings_profile as settings_profile_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, settings_profile_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(settings_profile_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(settings_profile_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(settings_profile_module, "show_toast", lambda *args, **kwargs: None)
        client_stub = AsyncClientStub(
            [
                httpx.Response(
                    422,
                    json={
                        "detail": "&quot;[{\"loc\":[\"body\",\"new_password\"],\"msg\":\"String should have at least 8 characters\"}]&quot;"
                    },
                ),
                httpx.Response(401, json={"detail": "Current password is incorrect"}),
                RuntimeError("backend crashed"),
            ]
        )
        monkeypatch.setattr(
            settings_profile_module.httpx,
            "AsyncClient",
            lambda *args, **kwargs: client_stub,
        )

        async def exercise() -> None:
            await settings_profile_module.settings_profile_page()
            current_pw, new_pw, confirm_pw = fake_ui.created["input"]
            save_button = next(button for button in fake_ui.created["button"] if button.value == "Update Password")
            error_label = next(
                label
                for label in fake_ui.created["label"]
                if any("var(--ht-error)" in style for style in label.style_calls)
            )

            current_pw.value = "OldPassword123!"
            new_pw.value = "short"
            confirm_pw.value = "short"
            await _invoke(save_button.handlers["click"])

            assert "at least 8" in error_label.text_value.lower()
            assert error_label.text_value != "New password is required."
            assert error_label.visible is True

            new_pw.value = "StrongPassword123!"
            await _invoke(
                lambda: new_pw.handlers["value_change"](SimpleNamespace(value="StrongPassword123!"))
            )
            assert error_label.text_value == ""
            assert error_label.visible is False

            current_pw.value = "WrongPassword123!"
            confirm_pw.value = "StrongPassword123!"
            await _invoke(save_button.handlers["click"])

            assert error_label.text_value == "Current password is incorrect."
            assert error_label.visible is True

            current_pw.value = "OldPassword123!"
            await _invoke(save_button.handlers["click"])
            assert error_label.text_value == "Couldn't update password right now. Please try again."
            assert error_label.visible is True

        asyncio.run(exercise())


class TestSettingsNetworksPage:
    def test_settings_networks_page_handles_create_edit_delete(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.pages.settings_networks as settings_networks_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, settings_networks_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(settings_networks_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(settings_networks_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(settings_networks_module, "redirect_if_insufficient_role", lambda *args, **kwargs: False)

        modal_state: dict[str, object] = {"mode": None, "errors": []}
        captured: dict[str, object] = {}

        def fake_create_network_modal(form: dict[str, str], on_submit: Callable[[], object]) -> object:
            captured["form"] = form
            captured["submit"] = on_submit

            def open_for_mode(mode: str) -> None:
                modal_state["mode"] = mode

            def close() -> None:
                modal_state["mode"] = "closed"

            def set_error(message: str) -> None:
                modal_state.setdefault("errors", [])
                errors = modal_state["errors"]
                assert isinstance(errors, list)
                errors.append(message)

            def clear_error() -> None:
                modal_state["errors"] = []

            return SimpleNamespace(
                open_for_mode=open_for_mode,
                close=close,
                set_error=set_error,
                clear_error=clear_error,
            )

        monkeypatch.setattr(settings_networks_module, "create_network_modal", fake_create_network_modal)

        def make_response(method: str, status: int, payload: object) -> httpx.Response:
            return httpx.Response(
                status,
                json=payload,
                request=httpx.Request(method, "http://test.local"),
            )

        client_stub = AsyncClientStub(
            [
                make_response("GET", 200, [{"id": "net-1", "name": "Mgmt", "vlan_id": 10, "cidr": "10.0.10.0/24", "gateway": "10.0.10.1", "description": "Core", "color": "#3b82f6", "device_count": 1}]),
                make_response("POST", 201, {"id": "net-2"}),
                make_response("GET", 200, [{"id": "net-1", "name": "Mgmt", "vlan_id": 10, "cidr": "10.0.10.0/24", "gateway": "10.0.10.1", "description": "Core", "color": "#3b82f6", "device_count": 1}, {"id": "net-2", "name": "Lab", "vlan_id": 20, "cidr": "10.0.20.0/24", "gateway": "10.0.20.1", "description": "Lab", "color": "#22d3ee", "device_count": 0}]),
                make_response("PATCH", 200, {"id": "net-1"}),
                make_response("GET", 200, [{"id": "net-1", "name": "Mgmt Updated", "vlan_id": 11, "cidr": "10.0.10.0/24", "gateway": "10.0.10.1", "description": "Core", "color": "#3b82f6", "device_count": 1}, {"id": "net-2", "name": "Lab", "vlan_id": 20, "cidr": "10.0.20.0/24", "gateway": "10.0.20.1", "description": "Lab", "color": "#22d3ee", "device_count": 0}]),
                make_response("DELETE", 204, {}),
                make_response("GET", 200, [{"id": "net-2", "name": "Lab", "vlan_id": 20, "cidr": "10.0.20.0/24", "gateway": "10.0.20.1", "description": "Lab", "color": "#22d3ee", "device_count": 0}]),
            ]
        )
        monkeypatch.setattr(settings_networks_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

        async def exercise() -> None:
            await settings_networks_module.settings_networks_page()
            table = fake_ui.created["table"][0]
            assert len(table.rows) == 1

            create_button = next(button for button in fake_ui.created["button"] if button.value == "+ Add Network")
            await _invoke(create_button.handlers["click"])
            assert modal_state["mode"] == "create"
            form = captured["form"]
            assert isinstance(form, dict)
            form["name"] = "Lab"
            form["vlan_id"] = "20"
            form["cidr"] = "10.0.20.0/24"
            form["gateway"] = "10.0.20.1"
            form["description"] = "Lab"
            form["color"] = "#22d3ee"
            await _invoke(captured["submit"])
            assert len(table.rows) == 2

            await _invoke(lambda: table.handlers["edit"](SimpleNamespace(args=table.rows[0])))
            assert modal_state["mode"] == "edit"
            form["vlan_id"] = "bad"
            await _invoke(captured["submit"])
            errors = modal_state["errors"]
            assert isinstance(errors, list)
            assert errors[-1] == "VLAN ID must be an integer"

            form["name"] = "Mgmt Updated"
            form["vlan_id"] = "11"
            await _invoke(captured["submit"])
            assert any(row["name"] == "Mgmt Updated" for row in table.rows)

            await _invoke(lambda: table.handlers["delete_row"](SimpleNamespace(args=table.rows[0])))
            await _drain_pending(fake_ui)
            delete_button = next(button for button in fake_ui.created["button"] if button.value == "Delete")
            await _invoke(delete_button.handlers["click"])
            await _drain_pending(fake_ui)

        asyncio.run(exercise())

        assert any(notification[1].get("type") == "positive" for notification in fake_ui.notifications)
        assert any(method == "POST" for method, _ in client_stub.calls)
        assert any(method == "PATCH" for method, _ in client_stub.calls)
        assert any(method == "DELETE" for method, _ in client_stub.calls)