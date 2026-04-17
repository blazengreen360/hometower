"""Execution tests for the settings users page."""
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


class TestSettingsUsersPage:
    def test_settings_users_page_handles_create_edit_and_delete(self, monkeypatch: pytest.MonkeyPatch) -> None:
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
                            "username": "alice",
                            "email": "alice@test.local",
                            "role": "Admin",
                            "is_active": True,
                        },
                        {
                            "id": "user-2",
                            "username": "bob",
                            "email": "bob@test.local",
                            "role": "Contributor",
                            "is_active": True,
                        },
                    ],
                ),
                make_response("POST", 201, {"id": "user-3"}),
                make_response(
                    "GET",
                    200,
                    [
                        {
                            "id": "user-1",
                            "username": "alice",
                            "email": "alice@test.local",
                            "role": "Admin",
                            "is_active": True,
                        },
                        {
                            "id": "user-2",
                            "username": "bob",
                            "email": "bob@test.local",
                            "role": "Contributor",
                            "is_active": True,
                        },
                        {
                            "id": "user-3",
                            "username": "carol",
                            "email": "carol@test.local",
                            "role": "Reader",
                            "is_active": True,
                        },
                    ],
                ),
                make_response("PATCH", 200, {"id": "user-2"}),
                make_response(
                    "GET",
                    200,
                    [
                        {
                            "id": "user-1",
                            "username": "alice",
                            "email": "alice@test.local",
                            "role": "Admin",
                            "is_active": True,
                        },
                        {
                            "id": "user-2",
                            "username": "bobby",
                            "email": "bob@test.local",
                            "role": "Contributor",
                            "is_active": True,
                        },
                        {
                            "id": "user-3",
                            "username": "carol",
                            "email": "carol@test.local",
                            "role": "Reader",
                            "is_active": True,
                        },
                    ],
                ),
                make_response("DELETE", 204, {}),
                make_response(
                    "GET",
                    200,
                    [
                        {
                            "id": "user-1",
                            "username": "alice",
                            "email": "alice@test.local",
                            "role": "Admin",
                            "is_active": True,
                        },
                        {
                            "id": "user-2",
                            "username": "bobby",
                            "email": "bob@test.local",
                            "role": "Contributor",
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
            assert len(table.rows) == 2
            assert table.rows[0]["is_self"] is True

            add_button = next(button for button in fake_ui.created["button"] if button.value == "+ Add User")
            await _invoke(add_button.handlers["click"])
            inputs = fake_ui.created["input"]
            role_select = fake_ui.created["select"][0]
            active_checkbox = fake_ui.created["checkbox"][0]
            inputs[0].value = "carol"
            inputs[1].value = "carol@test.local"
            inputs[2].value = ""
            role_select.value = "Reader"
            active_checkbox.value = True
            save_button = next(button for button in fake_ui.created["button"] if button.value == "Save")
            await _invoke(save_button.handlers["click"])
            assert any(label.text_value == "Password is required." for label in fake_ui.created["label"])

            inputs[2].value = "secret123"
            await _invoke(save_button.handlers["click"])
            assert any(notification[1].get("type") == "positive" for notification in fake_ui.notifications)
            assert len(table.rows) == 3

            await _invoke(lambda: table.handlers["edit"](SimpleNamespace(args=table.rows[1])))
            inputs[0].value = "bobby"
            inputs[1].value = "bob@test.local"
            inputs[2].value = ""
            role_select.value = "Contributor"
            await _invoke(save_button.handlers["click"])
            assert any(row["username"] == "bobby" for row in table.rows)

            await _invoke(lambda: table.handlers["delete"](SimpleNamespace(args=table.rows[2])))
            delete_button = next(button for button in fake_ui.created["button"] if button.value == "Delete")
            await _invoke(delete_button.handlers["click"])
            await _drain_pending(fake_ui)

        asyncio.run(exercise())

        assert any(method == "POST" for method, _ in client_stub.calls)
        assert any(method == "PATCH" for method, _ in client_stub.calls)
        assert any(method == "DELETE" for method, _ in client_stub.calls)
        assert len(fake_ui.created["table"][0].rows) == 2