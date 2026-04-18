"""Execution tests for device detail panel undo-aware save wiring (HT-032)."""

from __future__ import annotations

import asyncio
import inspect
from types import SimpleNamespace
import uuid
from collections.abc import Awaitable, Callable

import pytest

from tests.unit.nicegui_fakes import AsyncClientStub, FakeResponse
from tests.unit.nicegui_fakes import FakeUI, install_fake_ui


async def _invoke(handler: Callable[..., object]) -> object:
    result = handler()
    if inspect.isawaitable(result):
        return await result
    return result


class TestDevicePanelHelpersExecution:
    def test_render_editable_row_uses_injected_save_value_callback(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.device_panel_helpers as panel_helpers

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, panel_helpers, fake_ui)

        captured_values: list[str | None] = []
        saved_calls = {"count": 0}

        async def _save_value(value: str | None) -> bool:
            captured_values.append(value)
            return True

        def _on_saved() -> None:
            saved_calls["count"] += 1

        panel_helpers.render_editable_row(
            label="Name",
            current="old-name",
            field="name",
            device_id=uuid.uuid4(),
            token="token",
            is_editor=True,
            version=3,
            on_saved=_on_saved,
            save_value=_save_value,
        )

        edit_button = next(button for button in fake_ui.created["button"] if button.value == "edit")
        save_button = next(button for button in fake_ui.created["button"] if button.value == "check")
        value_input = fake_ui.created["input"][0]

        async def exercise() -> None:
            await _invoke(edit_button.handlers["click"])
            value_input.value = "new-name"
            await _invoke(save_button.handlers["click"])

        asyncio.run(exercise())

        assert captured_values == ["new-name"]
        assert saved_calls["count"] == 1

    def test_render_editable_int_row_maps_empty_to_none_and_numeric_to_int(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.device_panel_helpers as panel_helpers

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, panel_helpers, fake_ui)

        captured_values: list[object] = []

        async def _save_value(value: object) -> bool:
            captured_values.append(value)
            return True

        panel_helpers.render_editable_int_row(
            label="Power (W)",
            current=75,
            device_id=uuid.uuid4(),
            token="token",
            is_editor=True,
            version=2,
            save_value=_save_value,
        )

        edit_button = next(button for button in fake_ui.created["button"] if button.value == "edit")
        save_button = next(button for button in fake_ui.created["button"] if button.value == "check")
        value_input = fake_ui.created["input"][0]

        async def exercise() -> None:
            await _invoke(edit_button.handlers["click"])
            value_input.value = "120"
            await _invoke(save_button.handlers["click"])

            await _invoke(edit_button.handlers["click"])
            value_input.value = ""
            await _invoke(save_button.handlers["click"])

        asyncio.run(exercise())

        assert captured_values == [120, None]

    def test_render_editable_int_row_rejects_negative_values(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.device_panel_helpers as panel_helpers

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, panel_helpers, fake_ui)

        captured_values: list[object] = []

        async def _save_value(value: object) -> bool:
            captured_values.append(value)
            return True

        panel_helpers.render_editable_int_row(
            label="Power (W)",
            current=75,
            device_id=uuid.uuid4(),
            token="token",
            is_editor=True,
            version=2,
            save_value=_save_value,
        )

        edit_button = next(button for button in fake_ui.created["button"] if button.value == "edit")
        save_button = next(button for button in fake_ui.created["button"] if button.value == "check")
        value_input = fake_ui.created["input"][0]

        async def exercise() -> None:
            await _invoke(edit_button.handlers["click"])
            value_input.value = "-20"
            await _invoke(save_button.handlers["click"])

        asyncio.run(exercise())

        assert captured_values == []
        assert any(
            args[0] == "Power must be 0 or greater"
            for args, kwargs in fake_ui.notifications
            if kwargs.get("type") == "negative"
        )


class TestDeviceDetailPanelExecution:
    def test_detail_panel_routes_field_updates_through_undo_stack_contract(self) -> None:
        import src.ui.components.device_detail_panel as detail_panel_module

        source = inspect.getsource(detail_panel_module.render_detail_panel)

        assert "save_value=" in source
        assert "update_device_field" in source
        assert "Attachments" in source
        assert "Power (W)" in source
        assert "power_watts" in source

    def test_detail_panel_content_uses_markdown_notes_and_ip_quick_links(self) -> None:
        import src.ui.components.device_detail_panel_content as panel_content_module

        source = inspect.getsource(panel_content_module)

        assert "render_markdown_notes_row(" in source
        assert "render_ip_quick_links(device.ip)" in source

    def test_detail_bridge_routes_ghost_nodes_to_ghost_panel_event(self) -> None:
        from src.ui.components.device_detail_panel_bridge import DEVICE_DETAIL_PANEL_BRIDGE_JS

        assert "ghost_panel_select" in DEVICE_DETAIL_PANEL_BRIDGE_JS
        assert "nodeData.ghost" in DEVICE_DETAIL_PANEL_BRIDGE_JS
        assert "ghost_device_id" in DEVICE_DETAIL_PANEL_BRIDGE_JS


class TestDeviceDetailTagsSectionExecution:
    def test_render_tags_section_shows_visible_editor_state_when_no_tags_are_attachable(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.device_detail_tags_section as tags_section_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, tags_section_module, fake_ui)

        tags_section_module.render_tags_section(
            device_id=uuid.uuid4(),
            tags=[],
            all_tags=[],
            token="token",
            is_editor=True,
            on_change=lambda: None,
        )

        label_values = [label.value for label in fake_ui.created["label"]]
        button_values = [button.value for button in fake_ui.created["button"]]

        assert "No tags available to add yet" in label_values
        assert "add" in button_values

    def test_render_tags_section_keeps_detach_action_for_attached_tags(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.device_detail_tags_section as tags_section_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, tags_section_module, fake_ui)

        tag = SimpleNamespace(id=uuid.uuid4(), name="prod", color="var(--ht-accent)")

        tags_section_module.render_tags_section(
            device_id=uuid.uuid4(),
            tags=[tag],
            all_tags=[tag],
            token="token",
            is_editor=True,
            on_change=lambda: None,
        )

        button_values = [button.value for button in fake_ui.created["button"]]

        assert "close" in button_values

    def test_render_tags_section_does_not_refresh_or_clear_on_attach_non_2xx(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.device_detail_tags_section as tags_section_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, tags_section_module, fake_ui)
        client_stub = AsyncClientStub([FakeResponse(status_code=409, payload={"detail": "duplicate"})])
        monkeypatch.setattr(tags_section_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

        on_change_calls = {"count": 0}
        tag = SimpleNamespace(id=uuid.uuid4(), name="prod", color="var(--ht-accent)")

        tags_section_module.render_tags_section(
            device_id=uuid.uuid4(),
            tags=[],
            all_tags=[tag],
            token="token",
            is_editor=True,
            on_change=lambda: on_change_calls.__setitem__("count", on_change_calls["count"] + 1),
        )

        select = fake_ui.created["select"][0]

        async def exercise() -> None:
            select.value = str(tag.id)
            result = select.handlers["value_change"](SimpleNamespace(value=str(tag.id)))
            if inspect.isawaitable(result):
                await result

        asyncio.run(exercise())

        assert on_change_calls["count"] == 0
        assert select.value == str(tag.id)
        assert any(kwargs.get("type") == "negative" for _, kwargs in fake_ui.notifications)

    def test_render_tags_section_does_not_close_dialog_or_refresh_on_detach_non_2xx(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.device_detail_tags_section as tags_section_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, tags_section_module, fake_ui)
        client_stub = AsyncClientStub([FakeResponse(status_code=500, payload={"detail": "server error"})])
        monkeypatch.setattr(tags_section_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

        on_change_calls = {"count": 0}
        tag = SimpleNamespace(id=uuid.uuid4(), name="prod", color="var(--ht-accent)")

        tags_section_module.render_tags_section(
            device_id=uuid.uuid4(),
            tags=[tag],
            all_tags=[tag],
            token="token",
            is_editor=True,
            on_change=lambda: on_change_calls.__setitem__("count", on_change_calls["count"] + 1),
        )

        remove_button = next(button for button in fake_ui.created["button"] if button.value == "Remove")
        confirm_dialog = fake_ui.created["dialog"][0]

        asyncio.run(_invoke(remove_button.handlers["click"]))

        assert on_change_calls["count"] == 0
        assert confirm_dialog.closed is False
        assert any(kwargs.get("type") == "negative" for _, kwargs in fake_ui.notifications)


class TestDeviceDetailCustomFieldsSectionExecution:
    def test_render_custom_fields_section_keeps_editor_open_on_patch_non_2xx(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.device_detail_custom_fields_section as custom_fields_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, custom_fields_module, fake_ui)
        client_stub = AsyncClientStub([FakeResponse(status_code=500, payload={"detail": "boom"})])
        monkeypatch.setattr(custom_fields_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

        field = SimpleNamespace(id=uuid.uuid4(), key="Owner", value="Alice")

        custom_fields_module.render_custom_fields_section(
            device_id=uuid.uuid4(),
            fields=[field],
            token="token",
            is_editor=True,
            on_change=lambda: None,
        )

        value_label = fake_ui.created["label"][1]
        edit_button = next(button for button in fake_ui.created["button"] if button.value == "edit")
        save_button = next(button for button in fake_ui.created["button"] if button.value == "check")
        edit_row = fake_ui.created["row"][1]
        value_input = fake_ui.created["input"][0]

        async def exercise() -> None:
            await _invoke(edit_button.handlers["click"])
            value_input.value = "Bob"
            await _invoke(save_button.handlers["click"])

        asyncio.run(exercise())

        assert value_label.text_value == "Alice"
        assert value_label.visible is False
        assert edit_row.style_calls[-1] == "display:flex"
        assert any(kwargs.get("type") == "negative" for _, kwargs in fake_ui.notifications)
        assert not any(args[0] == "Field updated" for args, _ in fake_ui.notifications)

    def test_render_custom_fields_section_does_not_close_dialog_or_refresh_on_delete_non_2xx(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.device_detail_custom_fields_section as custom_fields_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, custom_fields_module, fake_ui)
        client_stub = AsyncClientStub([FakeResponse(status_code=500, payload={"detail": "boom"})])
        monkeypatch.setattr(custom_fields_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

        on_change_calls = {"count": 0}
        field = SimpleNamespace(id=uuid.uuid4(), key="Owner", value="Alice")

        custom_fields_module.render_custom_fields_section(
            device_id=uuid.uuid4(),
            fields=[field],
            token="token",
            is_editor=True,
            on_change=lambda: on_change_calls.__setitem__("count", on_change_calls["count"] + 1),
        )

        delete_button = next(button for button in fake_ui.created["button"] if button.value == "Delete")
        confirm_dialog = fake_ui.created["dialog"][0]

        asyncio.run(_invoke(delete_button.handlers["click"]))

        assert on_change_calls["count"] == 0
        assert confirm_dialog.closed is False
        assert any(kwargs.get("type") == "negative" for _, kwargs in fake_ui.notifications)

    def test_render_custom_fields_section_does_not_clear_inputs_or_refresh_on_add_non_2xx(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.device_detail_custom_fields_section as custom_fields_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, custom_fields_module, fake_ui)
        client_stub = AsyncClientStub([FakeResponse(status_code=500, payload={"detail": "boom"})])
        monkeypatch.setattr(custom_fields_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

        on_change_calls = {"count": 0}

        custom_fields_module.render_custom_fields_section(
            device_id=uuid.uuid4(),
            fields=[],
            token="token",
            is_editor=True,
            on_change=lambda: on_change_calls.__setitem__("count", on_change_calls["count"] + 1),
        )

        key_input, value_input = fake_ui.created["input"]
        add_button = next(button for button in fake_ui.created["button"] if button.value == "add")

        async def exercise() -> None:
            key_input.value = "Owner"
            value_input.value = "Alice"
            await _invoke(add_button.handlers["click"])

        asyncio.run(exercise())

        assert on_change_calls["count"] == 0
        assert key_input.value == "Owner"
        assert value_input.value == "Alice"
        assert any(kwargs.get("type") == "negative" for _, kwargs in fake_ui.notifications)
