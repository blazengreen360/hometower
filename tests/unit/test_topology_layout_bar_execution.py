"""Execution tests for topology history toolbar behavior (HT-072)."""
from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable, Iterator
from types import SimpleNamespace

import httpx
import pytest

from tests.unit.nicegui_fakes import AsyncClientStub, FakeUI, install_fake_ui


class _AwaitableValue:
    def __init__(self, value: object) -> None:
        self.value = value

    def __await__(self) -> Iterator[object]:
        async def _coro() -> object:
            return self.value

        return _coro().__await__()


class _JavaScriptStub:
    def __init__(self, canvas_json: dict[str, object] | None = None) -> None:
        self.canvas_json = canvas_json or {"elements": {"nodes": [], "edges": []}}
        self.calls: list[str] = []

    def __call__(self, code: str) -> _AwaitableValue:
        self.calls.append(code)
        if "getCanvasJson()" in code:
            return _AwaitableValue(self.canvas_json)
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


class TestTopologyHistoryToolbar:
    def test_render_layout_bar_exposes_history_primary_action_and_no_legacy_labels(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.topology_layout_bar as layout_bar_module
        import src.ui.components.topology_layout_dialogs as layout_dialogs_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, layout_bar_module, fake_ui)
        monkeypatch.setattr(layout_dialogs_module, "ui", fake_ui)
        fake_ui.run_javascript = _JavaScriptStub()  # type: ignore[assignment]

        async def history_stub(*args: object, **kwargs: object) -> list[dict[str, object]]:
            return [
                {
                    "id": "history-current",
                    "snapshot_name": "Current",
                    "action": "save_version",
                    "is_current": True,
                }
            ]

        monkeypatch.setattr(layout_bar_module, "get_layouts", history_stub)
        monkeypatch.setattr(layout_bar_module.httpx, "AsyncClient", lambda *args, **kwargs: AsyncClientStub([]))

        async def exercise() -> None:
            layout_bar_module.render_layout_bar(
                token="token",
                user_role="Contributor",
                topology_id="topology-1",
            )
            await _drain_pending(fake_ui)

        asyncio.run(exercise())

        button_labels = [str(button.value) for button in fake_ui.created["button"]]
        assert "Save Version" in button_labels
        assert "History" in button_labels
        assert "Save Layout" not in button_labels

    def test_render_layout_bar_saves_and_restores_history_version(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.components.topology_layout_bar as layout_bar_module
        import src.ui.components.topology_layout_dialogs as layout_dialogs_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, layout_bar_module, fake_ui)
        monkeypatch.setattr(layout_dialogs_module, "ui", fake_ui)

        js_stub = _JavaScriptStub()
        fake_ui.run_javascript = js_stub  # type: ignore[assignment]

        toasts: list[dict[str, object]] = []

        history_calls = {"count": 0}

        async def history_stub(*args: object, **kwargs: object) -> list[dict[str, object]]:
            history_calls["count"] += 1
            if history_calls["count"] == 1:
                return [
                    {
                        "id": "history-current",
                        "snapshot_name": "Current",
                        "action": "save_version",
                        "is_current": True,
                    },
                    {
                        "id": "history-old",
                        "snapshot_name": "Older",
                        "action": "save_version",
                        "is_current": False,
                    },
                ]
            return [
                {
                    "id": "history-new",
                    "snapshot_name": "Latest",
                    "action": "restore",
                    "is_current": True,
                },
                {
                    "id": "history-old",
                    "snapshot_name": "Older",
                    "action": "save_version",
                    "is_current": False,
                }
            ]

        client_stub = AsyncClientStub(
            [
                httpx.Response(
                    200,
                    json={
                        "history_entry_id": "history-saved",
                        "current_diagram_id": "diagram-new",
                        "current_diagram_version": 1,
                        "draft_version": None,
                        "has_unsaved_changes": False,
                        "cytoscape_json": {"elements": {"nodes": [], "edges": []}},
                    },
                ),
                httpx.Response(
                    200,
                    json={
                        "history_entry_id": "history-new",
                        "current_diagram_id": "diagram-restored",
                        "current_diagram_version": 1,
                        "draft_version": None,
                        "has_unsaved_changes": False,
                        "cytoscape_json": {"elements": {"nodes": [], "edges": []}},
                    },
                ),
            ]
        )

        monkeypatch.setattr(layout_bar_module, "get_layouts", history_stub)
        monkeypatch.setattr(layout_bar_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)
        monkeypatch.setattr(layout_bar_module, "show_toast", lambda *args, **kwargs: toasts.append(dict(kwargs)))

        async def exercise() -> None:
            layout_bar_module.render_layout_bar(
                token="token",
                user_role="Contributor",
                topology_id="topology-1",
                initial_diagram_id="diagram-initial",
                initial_diagram_version=3,
                initial_draft_version=2,
                initial_has_unsaved_changes=True,
            )
            await _drain_pending(fake_ui)

            select = fake_ui.created["select"][0]
            assert select.value == "history-current"
            assert "history-current" in (select.options or {})

            save_buttons = [button for button in fake_ui.created["button"] if button.value == "Save Version"]
            save_button = save_buttons[0]
            await _invoke(save_button.handlers["click"])
            await _drain_pending(fake_ui)

            history_button = next(button for button in fake_ui.created["button"] if button.value == "History")
            await _invoke(history_button.handlers["click"])
            await _invoke(lambda: select.handlers["value_change"](SimpleNamespace(value="history-old")))
            restore_action_button = next(
                button for button in fake_ui.created["button"] if button.value == "Restore Selected"
            )
            await _invoke(restore_action_button.handlers["click"])
            restore_confirm_button = next(button for button in fake_ui.created["button"] if button.value == "Restore")
            await _invoke(restore_confirm_button.handlers["click"])
            await _drain_pending(fake_ui)

        asyncio.run(exercise())

        assert any(toast.get("title") == "Version saved" for toast in toasts)
        assert any(toast.get("title") == "Version restored" for toast in toasts)
        assert any("window._htCurrentDiagramId" in code for code in js_stub.calls)
        assert any("window._htSetDraftStatus(true);" in code for code in js_stub.calls)
        assert any("window._htSetDraftStatus(false);" in code for code in js_stub.calls)
        assert any(method == "POST" and "/save-version" in url for method, url in client_stub.calls)
        assert any(method == "POST" and "/history/history-old/restore" in url for method, url in client_stub.calls)

    def test_history_restore_normalizes_label_selection_to_history_id(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.topology_layout_bar as layout_bar_module
        import src.ui.components.topology_layout_dialogs as layout_dialogs_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, layout_bar_module, fake_ui)
        monkeypatch.setattr(layout_dialogs_module, "ui", fake_ui)

        js_stub = _JavaScriptStub()
        fake_ui.run_javascript = js_stub  # type: ignore[assignment]

        async def history_stub(*args: object, **kwargs: object) -> list[dict[str, object]]:
            return [
                {
                    "id": "history-current",
                    "snapshot_name": "Current",
                    "action": "save_version",
                    "is_current": True,
                },
                {
                    "id": "history-old",
                    "snapshot_name": "Older",
                    "action": "save_version",
                    "is_current": False,
                },
            ]

        client_stub = AsyncClientStub(
            [
                httpx.Response(
                    200,
                    json={
                        "history_entry_id": "history-new",
                        "current_diagram_id": "diagram-restored",
                        "current_diagram_version": 2,
                        "draft_version": None,
                        "cytoscape_json": {"elements": {"nodes": [], "edges": []}},
                    },
                ),
            ]
        )

        monkeypatch.setattr(layout_bar_module, "get_layouts", history_stub)
        monkeypatch.setattr(layout_bar_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)
        monkeypatch.setattr(layout_bar_module, "show_toast", lambda *args, **kwargs: None)

        async def exercise() -> None:
            layout_bar_module.render_layout_bar(
                token="token",
                user_role="Contributor",
                topology_id="topology-restore-1",
                initial_diagram_id="diagram-current",
                initial_diagram_version=1,
            )
            await _drain_pending(fake_ui)

            history_button = next(button for button in fake_ui.created["button"] if button.value == "History")
            await _invoke(history_button.handlers["click"])

            history_select = fake_ui.created["select"][0]
            await _invoke(
                lambda: history_select.handlers["value_change"](
                    SimpleNamespace(value={"value": 1, "label": "Older"})
                )
            )

            restore_action_button = next(
                button for button in fake_ui.created["button"] if button.value == "Restore Selected"
            )
            await _invoke(restore_action_button.handlers["click"])

            restore_confirm_button = next(button for button in fake_ui.created["button"] if button.value == "Restore")
            await _invoke(restore_confirm_button.handlers["click"])
            await _drain_pending(fake_ui)

        asyncio.run(exercise())

        assert any(method == "POST" and "/history/history-old/restore" in url for method, url in client_stub.calls)

    def test_restore_action_closes_history_dialog_before_confirmation(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.topology_layout_bar as layout_bar_module
        import src.ui.components.topology_layout_dialogs as layout_dialogs_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, layout_bar_module, fake_ui)
        monkeypatch.setattr(layout_dialogs_module, "ui", fake_ui)

        fake_ui.run_javascript = _JavaScriptStub()  # type: ignore[assignment]

        async def history_stub(*args: object, **kwargs: object) -> list[dict[str, object]]:
            return [
                {
                    "id": "history-current",
                    "snapshot_name": "Current",
                    "action": "save_version",
                    "is_current": True,
                },
                {
                    "id": "history-old",
                    "snapshot_name": "Older",
                    "action": "save_version",
                    "is_current": False,
                },
            ]

        monkeypatch.setattr(layout_bar_module, "get_layouts", history_stub)
        monkeypatch.setattr(layout_bar_module.httpx, "AsyncClient", lambda *args, **kwargs: AsyncClientStub([]))

        async def exercise() -> None:
            layout_bar_module.render_layout_bar(
                token="token",
                user_role="Contributor",
                topology_id="topology-dialog-order",
                initial_diagram_id="diagram-current",
                initial_diagram_version=1,
            )
            await _drain_pending(fake_ui)

            dialogs = fake_ui.created["dialog"]
            assert len(dialogs) >= 2
            restore_dialog = dialogs[0]
            history_dialog = dialogs[1]

            history_button = next(button for button in fake_ui.created["button"] if button.value == "History")
            await _invoke(history_button.handlers["click"])
            assert history_dialog.opened is True

            history_select = fake_ui.created["select"][0]
            await _invoke(lambda: history_select.handlers["value_change"](SimpleNamespace(value="history-old")))

            restore_action_button = next(
                button for button in fake_ui.created["button"] if button.value == "Restore Selected"
            )
            await _invoke(restore_action_button.handlers["click"])

            assert history_dialog.closed is True
            assert restore_dialog.opened is True

        asyncio.run(exercise())

    def test_save_version_primary_action_saves_without_name_dialog(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.topology_layout_bar as layout_bar_module
        import src.ui.components.topology_layout_dialogs as layout_dialogs_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, layout_bar_module, fake_ui)
        monkeypatch.setattr(layout_dialogs_module, "ui", fake_ui)

        js_stub = _JavaScriptStub()
        fake_ui.run_javascript = js_stub  # type: ignore[assignment]

        async def history_stub(*args: object, **kwargs: object) -> list[dict[str, object]]:
            return []

        client_stub = AsyncClientStub(
            [
                httpx.Response(
                    200,
                    json={
                        "history_entry_id": "history-v1",
                        "current_diagram_id": "diagram-v1",
                        "current_diagram_version": 1,
                        "draft_version": None,
                        "cytoscape_json": {"elements": {"nodes": [], "edges": []}},
                    },
                ),
            ]
        )

        monkeypatch.setattr(layout_bar_module, "get_layouts", history_stub)
        monkeypatch.setattr(layout_bar_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)
        monkeypatch.setattr(layout_bar_module, "show_toast", lambda *args, **kwargs: None)

        async def exercise() -> None:
            layout_bar_module.render_layout_bar(
                token="token",
                user_role="Contributor",
                topology_id="topology-save-1",
            )
            await _drain_pending(fake_ui)

            save_buttons = [button for button in fake_ui.created["button"] if button.value == "Save Version"]
            save_button = save_buttons[-1]
            await _invoke(save_button.handlers["click"])
            await _drain_pending(fake_ui)

        asyncio.run(exercise())

        assert any(method == "POST" and "/save-version" in url for method, url in client_stub.calls)

    def test_save_version_422_shows_warning_toast(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.components.topology_layout_bar as layout_bar_module
        import src.ui.components.topology_layout_dialogs as layout_dialogs_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, layout_bar_module, fake_ui)
        monkeypatch.setattr(layout_dialogs_module, "ui", fake_ui)
        fake_ui.run_javascript = _JavaScriptStub()  # type: ignore[assignment]

        async def history_stub(*args: object, **kwargs: object) -> list[dict[str, object]]:
            return []

        client_stub = AsyncClientStub([httpx.Response(422, json={"detail": "invalid"})])
        toasts: list[dict[str, object]] = []

        monkeypatch.setattr(layout_bar_module, "get_layouts", history_stub)
        monkeypatch.setattr(layout_bar_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)
        monkeypatch.setattr(layout_bar_module, "show_toast", lambda *args, **kwargs: toasts.append(dict(kwargs)))

        async def exercise() -> None:
            layout_bar_module.render_layout_bar(
                token="token",
                user_role="Contributor",
                topology_id="topology-2",
            )
            await _drain_pending(fake_ui)

            save_buttons = [button for button in fake_ui.created["button"] if button.value == "Save Version"]
            save_button = save_buttons[0]
            await _invoke(save_button.handlers["click"])
            await _drain_pending(fake_ui)

        asyncio.run(exercise())

        assert any(toast.get("title") == "Save validation failed" for toast in toasts)

    def test_render_layout_bar_hides_editor_controls_for_readers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.components.topology_layout_bar as layout_bar_module
        import src.ui.components.topology_layout_dialogs as layout_dialogs_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, layout_bar_module, fake_ui)
        monkeypatch.setattr(layout_dialogs_module, "ui", fake_ui)
        fake_ui.run_javascript = _JavaScriptStub()  # type: ignore[assignment]

        async def history_stub(*args: object, **kwargs: object) -> list[dict[str, object]]:
            return []

        monkeypatch.setattr(layout_bar_module, "get_layouts", history_stub)
        monkeypatch.setattr(layout_bar_module.httpx, "AsyncClient", lambda *args, **kwargs: AsyncClientStub([]))

        async def exercise() -> None:
            layout_bar_module.render_layout_bar(token="token", user_role="Reader", topology_id="topology-3")
            await _drain_pending(fake_ui)

        asyncio.run(exercise())

        buttons = [button.value for button in fake_ui.created["button"]]
        assert "Save Version" not in buttons
        assert "History" in buttons
        assert "Restore Selected" not in buttons

    def test_layout_bar_click_handlers_do_not_detach_tasks(self) -> None:
        from src.ui.components import topology_layout_bar

        source = inspect.getsource(topology_layout_bar.render_layout_bar)
        assert "asyncio.ensure_future" not in source
