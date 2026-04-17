"""Execution tests for the power settings page."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable, Iterator
from contextlib import contextmanager

import httpx
import pytest

from src.models.types import Role
from tests.unit.nicegui_fakes import AsyncClientStub, FakeUI, install_fake_ui


async def _invoke(handler: Callable[..., object]) -> object:
    result = handler()
    if inspect.isawaitable(result):
        return await result
    return result


@contextmanager
def _noop_shell() -> Iterator[None]:
    yield


class TestSettingsPowerPage:
    def test_settings_power_page_applies_auth_and_admin_guard(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.pages.settings_power as settings_power_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, settings_power_module, fake_ui, {"access_token": "token"})

        captured_paths: list[str] = []

        def _redirect_if_unauthenticated(**kwargs: object) -> bool:
            current_path = kwargs.get("current_path")
            if isinstance(current_path, str):
                captured_paths.append(current_path)
            return True

        monkeypatch.setattr(
            settings_power_module,
            "redirect_if_unauthenticated",
            _redirect_if_unauthenticated,
        )

        asyncio.run(settings_power_module.settings_power_page())

        assert captured_paths == ["/settings/power"]

    def test_settings_power_page_loads_and_saves_settings(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.pages.settings_power as settings_power_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, settings_power_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(settings_power_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(settings_power_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(settings_power_module, "redirect_if_insufficient_role", lambda _role: False)
        monkeypatch.setattr(
            settings_power_module,
            "show_toast",
            lambda *args, **kwargs: fake_ui.notifications.append((args, kwargs)),
        )

        client_stub = AsyncClientStub(
            [
                httpx.Response(
                    200,
                    json={
                        "cost_per_kwh": 0.15,
                        "currency": "EUR",
                        "updated_at": "2026-04-17T10:15:00Z",
                    },
                ),
                httpx.Response(
                    200,
                    json={
                        "cost_per_kwh": 0.2,
                        "currency": "USD",
                        "updated_at": "2026-04-17T10:30:00Z",
                    },
                ),
            ]
        )
        monkeypatch.setattr(
            settings_power_module.httpx,
            "AsyncClient",
            lambda *args, **kwargs: client_stub,
        )

        async def exercise() -> None:
            await settings_power_module.settings_power_page()
            cost_input = fake_ui.created["input"][0]
            currency_input = fake_ui.created["input"][1]
            cost_input.value = "0.20"
            currency_input.value = "usd"
            save_button = next(
                button
                for button in fake_ui.created["button"]
                if button.value == "Save settings"
            )
            await _invoke(save_button.handlers["click"])

        asyncio.run(exercise())

        assert client_stub.calls[0][0] == "GET"
        assert client_stub.calls[1][0] == "PUT"
        assert client_stub.call_kwargs[1]["json"] == {
            "cost_per_kwh": 0.2,
            "currency": "USD",
        }
        assert any(notification[1].get("type") == "success" for notification in fake_ui.notifications)

    def test_settings_power_page_clear_then_save_sends_null_pair(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.pages.settings_power as settings_power_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, settings_power_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(settings_power_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(settings_power_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(settings_power_module, "redirect_if_insufficient_role", lambda _role: False)
        monkeypatch.setattr(
            settings_power_module,
            "show_toast",
            lambda *args, **kwargs: fake_ui.notifications.append((args, kwargs)),
        )

        client_stub = AsyncClientStub(
            [
                httpx.Response(
                    200,
                    json={
                        "cost_per_kwh": 0.19,
                        "currency": "GBP",
                        "updated_at": "2026-04-17T10:15:00Z",
                    },
                ),
                httpx.Response(
                    200,
                    json={
                        "cost_per_kwh": None,
                        "currency": None,
                        "updated_at": "2026-04-17T10:40:00Z",
                    },
                ),
            ]
        )
        monkeypatch.setattr(
            settings_power_module.httpx,
            "AsyncClient",
            lambda *args, **kwargs: client_stub,
        )

        async def exercise() -> None:
            await settings_power_module.settings_power_page()
            clear_button = next(
                button for button in fake_ui.created["button"] if button.value == "Clear"
            )
            await _invoke(clear_button.handlers["click"])
            assert any(
                label.text_value == "Last updated: unsaved changes"
                for label in fake_ui.created["label"]
            )
            save_button = next(
                button
                for button in fake_ui.created["button"]
                if button.value == "Save settings"
            )
            await _invoke(save_button.handlers["click"])

        asyncio.run(exercise())

        assert client_stub.call_kwargs[1]["json"] == {
            "cost_per_kwh": None,
            "currency": None,
        }
        assert any(
            notification[1].get("type") == "info"
            and notification[1].get("title") == "Fields cleared"
            for notification in fake_ui.notifications
        )
