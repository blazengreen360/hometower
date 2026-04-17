"""Execution tests for the device edit page."""
from __future__ import annotations

import asyncio
import inspect
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from types import SimpleNamespace

import httpx
import pytest

from src.models.types import DeviceStatus, DeviceType, Role
from tests.unit.nicegui_fakes import AsyncClientStub, FakeUI, install_fake_ui


async def _invoke(handler: Callable[..., object]) -> object:
    result = handler()
    if inspect.isawaitable(result):
        return await result
    return result


@contextmanager
def _noop_shell() -> Iterator[None]:
    yield


class TestDeviceEditPage:
    def test_inventory_device_edit_page_rejects_invalid_uuid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.pages.device_edit as device_edit_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, device_edit_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(device_edit_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(device_edit_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(device_edit_module, "get_ui_role", lambda: Role.Admin)

        asyncio.run(device_edit_module.inventory_device_edit_page("not-a-uuid"))

        assert any(label.text_value == "Invalid device id" for label in fake_ui.created["label"])
        assert any(button.value == "Back to Inventory" for button in fake_ui.created["button"])

    def test_inventory_device_edit_page_handles_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.pages.device_edit as device_edit_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, device_edit_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(device_edit_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(device_edit_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(device_edit_module, "get_ui_role", lambda: Role.Admin)

        async def fake_load_device(*args: object, **kwargs: object) -> object | None:
            return None

        monkeypatch.setattr(device_edit_module, "_load_device", fake_load_device)

        device_id = str(uuid.uuid4())
        asyncio.run(device_edit_module.inventory_device_edit_page(device_id))

        assert any(label.text_value == "Device not found or unavailable" for label in fake_ui.created["label"])
        assert any(button.value == "Back to Inventory" for button in fake_ui.created["button"])

    def test_inventory_device_edit_page_saves_device(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.pages.device_edit as device_edit_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, device_edit_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(device_edit_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(device_edit_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(device_edit_module, "get_ui_role", lambda: Role.Contributor)
        monkeypatch.setattr(
            device_edit_module,
            "show_toast",
            lambda *args, **kwargs: fake_ui.notifications.append((args, kwargs)),
        )

        device_id = uuid.uuid4()
        device = SimpleNamespace(
            id=device_id,
            name="Server One",
            type=DeviceType.Server,
            status=DeviceStatus.Active,
            ip="10.0.0.1",
            mac="aa:bb:cc:dd:ee:ff",
            os="Linux",
            notes="Initial",
            power_watts=65,
            version=1,
        )

        async def fake_load_device(*args: object, **kwargs: object) -> object:
            return device

        monkeypatch.setattr(device_edit_module, "_load_device", fake_load_device)
        client_stub = AsyncClientStub([httpx.Response(200, json={"id": str(device_id)})])
        monkeypatch.setattr(device_edit_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

        async def exercise() -> None:
            await device_edit_module.inventory_device_edit_page(str(device_id))
            name_input = fake_ui.created["input"][0]
            type_select = fake_ui.created["select"][0]
            status_select = fake_ui.created["select"][1]
            ip_input = fake_ui.created["input"][1]
            mac_input = fake_ui.created["input"][2]
            os_input = fake_ui.created["input"][3]
            power_input = fake_ui.created["input"][4]
            notes_input = fake_ui.created["textarea"][0]
            name_input.value = "Server Two"
            type_select.value = DeviceType.Server.value
            status_select.value = DeviceStatus.Offline.value
            ip_input.value = "10.0.0.2"
            mac_input.value = "11:22:33:44:55:66"
            os_input.value = "Linux"
            power_input.value = "120"
            notes_input.value = "Updated"
            save_button = next(button for button in fake_ui.created["button"] if button.value == "Save Changes")
            await _invoke(save_button.handlers["click"])

        asyncio.run(exercise())

        assert any(notification[1].get("type") == "success" for notification in fake_ui.notifications)
        assert fake_ui.navigate.to_calls[-1] == ("/inventory", False)
        assert any(method == "PATCH" for method, _ in client_stub.calls)
        assert client_stub.call_kwargs[-1]["json"]["power_watts"] == 120

    def test_inventory_device_edit_page_rejects_negative_power_with_visible_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.pages.device_edit as device_edit_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, device_edit_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(device_edit_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(device_edit_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(device_edit_module, "get_ui_role", lambda: Role.Contributor)

        device_id = uuid.uuid4()
        device = SimpleNamespace(
            id=device_id,
            name="Server One",
            type=DeviceType.Server,
            status=DeviceStatus.Active,
            ip="10.0.0.1",
            mac="aa:bb:cc:dd:ee:ff",
            os="Linux",
            notes="Initial",
            power_watts=65,
            version=1,
        )

        async def fake_load_device(*args: object, **kwargs: object) -> object:
            return device

        monkeypatch.setattr(device_edit_module, "_load_device", fake_load_device)
        client_stub = AsyncClientStub([])
        monkeypatch.setattr(device_edit_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

        async def exercise() -> None:
            await device_edit_module.inventory_device_edit_page(str(device_id))
            power_input = fake_ui.created["input"][4]
            power_input.value = "-50"
            save_button = next(button for button in fake_ui.created["button"] if button.value == "Save Changes")
            await _invoke(save_button.handlers["click"])

        asyncio.run(exercise())

        assert not client_stub.calls
        assert any(
            label.text_value == "Power must be a whole number 0 or greater"
            for label in fake_ui.created["label"]
        )

    def test_inventory_device_edit_page_renders_read_only_for_reader(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.pages.device_edit as device_edit_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, device_edit_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(device_edit_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(device_edit_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(device_edit_module, "get_ui_role", lambda: Role.Reader)
        device = SimpleNamespace(
            id=uuid.uuid4(),
            name="Server One",
            type=DeviceType.Server,
            status=DeviceStatus.Active,
            ip="10.0.0.1",
            mac="aa:bb:cc:dd:ee:ff",
            os="Linux",
            notes="Initial",
            power_watts=None,
            version=1,
        )

        async def fake_load_device(*args: object, **kwargs: object) -> object:
            return device

        monkeypatch.setattr(device_edit_module, "_load_device", fake_load_device)

        asyncio.run(device_edit_module.inventory_device_edit_page(str(device.id)))

        assert any(label.text_value == "Read-only: your role cannot update devices." for label in fake_ui.created["label"])
        assert any("readonly" in prop for input_el in fake_ui.created["input"] for prop in input_el.props_calls)
        save_button = next(button for button in fake_ui.created["button"] if button.value == "Save Changes")
        assert any("disable" in prop for prop in save_button.props_calls)