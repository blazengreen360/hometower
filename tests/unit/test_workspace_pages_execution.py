"""Execution tests for workspace pages."""
from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from types import SimpleNamespace

import httpx
import pytest

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


class TestWorkspacesPage:
    def test_workspaces_page_formats_last_modified_and_exposes_iso_tooltip(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.pages.workspaces as workspaces_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, workspaces_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(workspaces_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(workspaces_module, "redirect_if_unauthenticated", lambda **kwargs: False)

        client_stub = AsyncClientStub(
            [
                httpx.Response(
                    200,
                    json={
                        "items": [
                            {
                                "id": "ws-1",
                                "name": "Workspace One",
                                "topology_count": 1,
                                "last_modified": "2026-04-12T13:39:49Z",
                            },
                            {
                                "id": "ws-2",
                                "name": "Workspace Two",
                                "topology_count": 0,
                                "last_modified": None,
                            },
                        ]
                    },
                ),
            ]
        )
        monkeypatch.setattr(workspaces_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

        asyncio.run(workspaces_module.workspaces_page())

        table = fake_ui.created["table"][0]
        search_input = fake_ui.created["input"][0]
        last_modified_column = next(column for column in table.columns if column["name"] == "last_modified")
        assert last_modified_column["field"] == "last_modified_sort"
        assert table.pagination == {"rowsPerPage": 25, "sortBy": "name", "descending": False}
        assert any("rows-per-page-options=[10, 25, 50, 100]" in props for props in table.props_calls)
        assert search_input.placeholder == "Search workspaces"
        assert "w-full max-w-full sm:max-w-[240px]" in search_input.classes_calls
        search_input.handlers["change"](SimpleNamespace(value="Workspace One"))
        assert table.filter == "Workspace One"
        search_input.handlers["change"](SimpleNamespace(value=None))
        assert table.filter == ""

        assert table.rows[0]["last_modified"] == "2026-04-12T13:39:49Z"
        assert table.rows[0]["last_modified_display"] == "\u2014"
        assert table.rows[0]["last_modified_display"] != table.rows[0]["last_modified_iso"]
        assert table.rows[0]["last_modified_iso"] == "2026-04-12T13:39:49Z"
        assert table.rows[0]["last_modified_sort"] == "2026-04-12T13:39:49Z"
        assert table.rows[1]["last_modified"] == "\u2014"
        assert table.rows[1]["last_modified_display"] == "\u2014"
        assert table.rows[1]["last_modified_iso"] == ""
        assert table.rows[1]["last_modified_sort"] == ""
        assert "($htFormatLastModifiedLocal && $htFormatLastModifiedLocal(props.row.last_modified_iso, props.row.last_modified_display)) || props.row.last_modified_display" in table.slots["body"]
        assert "<q-tooltip v-if=\"props.row.last_modified_iso\">" in table.slots["body"]

        bridge_script = next(snippet for snippet in fake_ui.body_html if "window.htFormatLastModifiedLocal" in snippet)
        assert "vueApp.config.globalProperties.$htFormatLastModifiedLocal = formatLastModifiedLocal;" in bridge_script
        assert "if (registerVueFormatter() || attempts >= 40)" in bridge_script
        assert "clearInterval(retryTimer);" in bridge_script

    def test_workspaces_page_handles_create_rename_and_delete(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.pages.workspaces as workspaces_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, workspaces_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(workspaces_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(workspaces_module, "redirect_if_unauthenticated", lambda **kwargs: False)

        dialog_calls: list[tuple[str, str]] = []

        async def fake_show_name_dialog(
            title: str,
            placeholder: str = "Name",
            current_value: str = "",
            on_submit: object | None = None,
        ) -> None:
            dialog_calls.append((title, current_value))
            if not callable(on_submit):
                return
            if title.startswith("Rename"):
                await on_submit(f"{current_value} Renamed")
            else:
                await on_submit("Created Workspace")

        monkeypatch.setattr(workspaces_module, "show_name_dialog", fake_show_name_dialog)

        client_stub = AsyncClientStub(
            [
                httpx.Response(200, json={"items": [{"id": "ws-1", "name": "Workspace One", "topology_count": 1, "last_modified": "now"}]}),
                httpx.Response(201, json={"id": "ws-2"}),
                httpx.Response(200, json={"items": [{"id": "ws-1", "name": "Workspace One", "topology_count": 1, "last_modified": "now"}, {"id": "ws-2", "name": "Created Workspace", "topology_count": 0, "last_modified": "now"}]}),
                httpx.Response(200, json={"id": "ws-1"}),
                httpx.Response(200, json={"items": [{"id": "ws-1", "name": "Workspace One Renamed", "topology_count": 1, "last_modified": "now"}, {"id": "ws-2", "name": "Created Workspace", "topology_count": 0, "last_modified": "now"}]}),
                httpx.Response(204),
                httpx.Response(200, json={"items": []}),
            ]
        )
        monkeypatch.setattr(workspaces_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

        async def exercise() -> None:
            await workspaces_module.workspaces_page()
            table = fake_ui.created["table"][0]
            assert len(table.rows) == 1

            create_button = next(button for button in fake_ui.created["button"] if button.value == "+ New Workspace")
            await _invoke(create_button.handlers["click"])
            assert any(notification[1].get("type") == "positive" for notification in fake_ui.notifications)
            assert len(table.rows) == 2

            await _invoke(lambda: table.handlers["rename"](SimpleNamespace(args=table.rows[0])))
            assert any(row["name"] == "Workspace One Renamed" for row in table.rows)

            await _invoke(lambda: table.handlers["delete"](SimpleNamespace(args=table.rows[0])))
            delete_button = next(button for button in fake_ui.created["button"] if button.value == "Delete")
            await _invoke(delete_button.handlers["click"])
            await _drain_pending(fake_ui)

        asyncio.run(exercise())

        assert dialog_calls[0][0] == "New Workspace"
        assert any(call[0] == "Rename Workspace" for call in dialog_calls)
        assert len(fake_ui.created["table"][0].rows) == 0
        assert any(method == "POST" for method, _ in client_stub.calls)
        assert any(method == "PATCH" for method, _ in client_stub.calls)
        assert any(method == "DELETE" for method, _ in client_stub.calls)

    def test_workspaces_page_returns_inline_duplicate_errors_for_create_and_rename(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.pages.workspaces as workspaces_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, workspaces_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(workspaces_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(workspaces_module, "redirect_if_unauthenticated", lambda **kwargs: False)

        submit_handlers: dict[str, Callable[[str], object]] = {}

        async def fake_show_name_dialog(
            title: str,
            placeholder: str = "Name",
            current_value: str = "",
            on_submit: object | None = None,
        ) -> None:
            if callable(on_submit):
                submit_handlers[title] = on_submit

        monkeypatch.setattr(workspaces_module, "show_name_dialog", fake_show_name_dialog)

        client_stub = AsyncClientStub(
            [
                httpx.Response(
                    200,
                    json={"items": [{"id": "ws-1", "name": "Workspace One", "topology_count": 1, "last_modified": "now"}]},
                ),
                httpx.Response(409, json={"detail": "Workspace already exists"}),
                httpx.Response(409, json={"detail": "Workspace already exists"}),
            ]
        )
        monkeypatch.setattr(workspaces_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

        async def exercise() -> None:
            await workspaces_module.workspaces_page()

            create_button = next(button for button in fake_ui.created["button"] if button.value == "+ New Workspace")
            await _invoke(create_button.handlers["click"])
            create_submit = submit_handlers["New Workspace"]
            create_error = create_submit("Workspace One")
            if inspect.isawaitable(create_error):
                create_error = await create_error
            assert create_error == "A workspace with this name already exists."

            table = fake_ui.created["table"][0]
            await _invoke(lambda: table.handlers["rename"](SimpleNamespace(args=table.rows[0])))
            rename_submit = submit_handlers["Rename Workspace"]
            rename_error = rename_submit("Workspace One")
            if inspect.isawaitable(rename_error):
                rename_error = await rename_error
            assert rename_error == "A workspace with this name already exists."

        asyncio.run(exercise())

        assert not fake_ui.notifications

    def test_workspaces_page_shows_toasts_for_create_and_rename_exceptions(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.pages.workspaces as workspaces_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, workspaces_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(workspaces_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(workspaces_module, "redirect_if_unauthenticated", lambda **kwargs: False)

        submit_handlers: dict[str, Callable[[str], object]] = {}

        async def fake_show_name_dialog(
            title: str,
            placeholder: str = "Name",
            current_value: str = "",
            on_submit: object | None = None,
        ) -> None:
            if callable(on_submit):
                submit_handlers[title] = on_submit

        monkeypatch.setattr(workspaces_module, "show_name_dialog", fake_show_name_dialog)

        client_stub = AsyncClientStub(
            [
                httpx.Response(
                    200,
                    json={"items": [{"id": "ws-1", "name": "Workspace One", "topology_count": 1, "last_modified": "now"}]},
                ),
                httpx.TransportError("workspace create network failure"),
                httpx.TransportError("workspace rename network failure"),
            ]
        )
        monkeypatch.setattr(workspaces_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

        async def exercise() -> None:
            await workspaces_module.workspaces_page()

            create_button = next(button for button in fake_ui.created["button"] if button.value == "+ New Workspace")
            await _invoke(create_button.handlers["click"])
            create_submit = submit_handlers["New Workspace"]
            create_result = create_submit("Workspace Two")
            if inspect.isawaitable(create_result):
                create_result = await create_result
            assert create_result is None

            table = fake_ui.created["table"][0]
            await _invoke(lambda: table.handlers["rename"](SimpleNamespace(args=table.rows[0])))
            rename_submit = submit_handlers["Rename Workspace"]
            rename_result = rename_submit("Workspace Two")
            if inspect.isawaitable(rename_result):
                rename_result = await rename_result
            assert rename_result is None

        asyncio.run(exercise())

        negative_messages = [
            str(args[0])
            for args, kwargs in fake_ui.notifications
            if kwargs.get("type") == "negative"
        ]
        assert "Could not create workspace. Please try again." in negative_messages
        assert "Could not rename workspace. Please try again." in negative_messages

    def test_workspaces_page_shows_toasts_for_create_and_rename_non_json_errors(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.pages.workspaces as workspaces_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, workspaces_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(workspaces_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(workspaces_module, "redirect_if_unauthenticated", lambda **kwargs: False)

        submit_handlers: dict[str, Callable[[str], object]] = {}

        async def fake_show_name_dialog(
            title: str,
            placeholder: str = "Name",
            current_value: str = "",
            on_submit: object | None = None,
        ) -> None:
            if callable(on_submit):
                submit_handlers[title] = on_submit

        monkeypatch.setattr(workspaces_module, "show_name_dialog", fake_show_name_dialog)

        client_stub = AsyncClientStub(
            [
                httpx.Response(
                    200,
                    json={"items": [{"id": "ws-1", "name": "Workspace One", "topology_count": 1, "last_modified": "now"}]},
                ),
                httpx.Response(500, text="upstream create failure"),
                httpx.Response(500, text="upstream rename failure"),
            ]
        )
        monkeypatch.setattr(workspaces_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

        async def exercise() -> None:
            await workspaces_module.workspaces_page()

            create_button = next(button for button in fake_ui.created["button"] if button.value == "+ New Workspace")
            await _invoke(create_button.handlers["click"])
            create_submit = submit_handlers["New Workspace"]
            create_result = create_submit("Workspace Two")
            if inspect.isawaitable(create_result):
                create_result = await create_result
            assert create_result is None

            table = fake_ui.created["table"][0]
            await _invoke(lambda: table.handlers["rename"](SimpleNamespace(args=table.rows[0])))
            rename_submit = submit_handlers["Rename Workspace"]
            rename_result = rename_submit("Workspace Two")
            if inspect.isawaitable(rename_result):
                rename_result = await rename_result
            assert rename_result is None

        asyncio.run(exercise())

        negative_messages = [
            str(args[0])
            for args, kwargs in fake_ui.notifications
            if kwargs.get("type") == "negative"
        ]
        assert "Could not create workspace. Please try again." in negative_messages
        assert "Could not rename workspace. Please try again." in negative_messages


class TestWorkspaceDetailPage:
    def test_workspace_detail_page_formats_last_modified_and_exposes_iso_tooltip(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.pages.workspace_detail as workspace_detail_module
        import src.ui.components.breadcrumb as breadcrumb_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, workspace_detail_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(workspace_detail_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(workspace_detail_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(breadcrumb_module, "ui", fake_ui)

        client_stub = AsyncClientStub(
            [
                httpx.Response(200, json={"name": "Workspace Alpha"}),
                httpx.Response(
                    200,
                    json={
                        "items": [
                            {
                                "id": "topo-1",
                                "name": "Topology One",
                                "tags": [],
                                "last_modified": "2026-04-12T13:39:49Z",
                            },
                            {
                                "id": "topo-2",
                                "name": "Topology Two",
                                "tags": [],
                                "last_modified": None,
                            },
                        ]
                    },
                ),
            ]
        )
        monkeypatch.setattr(workspace_detail_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

        asyncio.run(workspace_detail_module.workspace_detail_page("ws-1"))

        table = fake_ui.created["table"][0]
        search_input = fake_ui.created["input"][0]
        last_modified_column = next(column for column in table.columns if column["name"] == "last_modified")
        assert last_modified_column["field"] == "last_modified_sort"
        assert table.pagination == {"rowsPerPage": 25, "sortBy": "name", "descending": False}
        assert any("rows-per-page-options=[10, 25, 50, 100]" in props for props in table.props_calls)
        assert search_input.placeholder == "Search topologies"
        assert "Open topology" in table.slots["body"]
        assert "Rename topology" in table.slots["body"]
        assert "Delete topology" in table.slots["body"]
        search_input.handlers["change"](SimpleNamespace(value="Topology One"))
        assert table.filter == "Topology One"
        search_input.handlers["change"](SimpleNamespace(value=None))
        assert table.filter == ""

        assert table.rows[0]["last_modified"] == "2026-04-12T13:39:49Z"
        assert table.rows[0]["last_modified_display"] == "\u2014"
        assert table.rows[0]["last_modified_display"] != table.rows[0]["last_modified_iso"]
        assert table.rows[0]["last_modified_iso"] == "2026-04-12T13:39:49Z"
        assert table.rows[0]["last_modified_sort"] == "2026-04-12T13:39:49Z"
        assert table.rows[1]["last_modified"] == "\u2014"
        assert table.rows[1]["last_modified_display"] == "\u2014"
        assert table.rows[1]["last_modified_iso"] == ""
        assert table.rows[1]["last_modified_sort"] == ""
        assert "($htFormatLastModifiedLocal && $htFormatLastModifiedLocal(props.row.last_modified_iso, props.row.last_modified_display)) || props.row.last_modified_display" in table.slots["body"]
        assert "<q-tooltip v-if=\"props.row.last_modified_iso\">" in table.slots["body"]

        bridge_script = next(snippet for snippet in fake_ui.body_html if "window.htFormatLastModifiedLocal" in snippet)
        assert "vueApp.config.globalProperties.$htFormatLastModifiedLocal = formatLastModifiedLocal;" in bridge_script
        assert "if (registerVueFormatter() || attempts >= 40)" in bridge_script
        assert "clearInterval(retryTimer);" in bridge_script

    def test_workspace_detail_page_handles_crud_and_open(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.pages.workspace_detail as workspace_detail_module
        import src.ui.components.breadcrumb as breadcrumb_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, workspace_detail_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(workspace_detail_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(workspace_detail_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(breadcrumb_module, "ui", fake_ui)

        dialog_calls: list[tuple[str, str]] = []

        async def fake_show_name_dialog(
            title: str,
            placeholder: str = "Name",
            current_value: str = "",
            on_submit: object | None = None,
        ) -> None:
            dialog_calls.append((title, current_value))
            if not callable(on_submit):
                return
            if title.startswith("Rename"):
                await on_submit(f"{current_value} Renamed")
            else:
                await on_submit("Created Topology")

        monkeypatch.setattr(workspace_detail_module, "show_name_dialog", fake_show_name_dialog)

        client_stub = AsyncClientStub(
            [
                httpx.Response(200, json={"name": "Workspace Alpha"}),
                httpx.Response(200, json={"items": [{"id": "topo-1", "name": "Topology One", "tags": [], "last_modified": "now"}]}),
                httpx.Response(201, json={"id": "topo-2"}),
                httpx.Response(200, json={"items": [{"id": "topo-1", "name": "Topology One", "tags": [], "last_modified": "now"}, {"id": "topo-2", "name": "Created Topology", "tags": [], "last_modified": "now"}]}),
                httpx.Response(200, json={"id": "topo-1"}),
                httpx.Response(200, json={"items": [{"id": "topo-1", "name": "Topology One Renamed", "tags": [], "last_modified": "now"}, {"id": "topo-2", "name": "Created Topology", "tags": [], "last_modified": "now"}]}),
                httpx.Response(204),
                httpx.Response(200, json={"items": []}),
            ]
        )
        monkeypatch.setattr(workspace_detail_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

        async def exercise() -> None:
            await workspace_detail_module.workspace_detail_page("ws-1")
            table = fake_ui.created["table"][0]
            assert len(table.rows) == 1
            assert any(link.value == "Workspaces" for link in fake_ui.created["link"])

            await _invoke(lambda: table.handlers["open"](SimpleNamespace(args=table.rows[0])))
            assert fake_ui.navigate.to_calls[-1] == (
                "/topology?topology_id=topo-1&workspace_id=ws-1",
                False,
            )

            create_button = next(button for button in fake_ui.created["button"] if button.value == "+ New Topology")
            await _invoke(create_button.handlers["click"])
            assert len(table.rows) == 2

            await _invoke(lambda: table.handlers["rename"](SimpleNamespace(args=table.rows[0])))
            assert any(row["name"] == "Topology One Renamed" for row in table.rows)

            await _invoke(lambda: table.handlers["delete"](SimpleNamespace(args=table.rows[0])))
            delete_button = next(button for button in fake_ui.created["button"] if button.value == "Delete")
            await _invoke(delete_button.handlers["click"])
            await _drain_pending(fake_ui)

        asyncio.run(exercise())

        assert dialog_calls[0][0] == "New Topology"
        assert any(call[0] == "Rename Topology" for call in dialog_calls)
        assert len(fake_ui.created["table"][0].rows) == 0
        assert any(method == "POST" for method, _ in client_stub.calls)
        assert any(method == "PATCH" for method, _ in client_stub.calls)
        assert any(method == "DELETE" for method, _ in client_stub.calls)

    def test_workspace_detail_page_returns_inline_duplicate_errors_for_create_and_rename(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.pages.workspace_detail as workspace_detail_module
        import src.ui.components.breadcrumb as breadcrumb_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, workspace_detail_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(workspace_detail_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(workspace_detail_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(breadcrumb_module, "ui", fake_ui)

        submit_handlers: dict[str, Callable[[str], object]] = {}

        async def fake_show_name_dialog(
            title: str,
            placeholder: str = "Name",
            current_value: str = "",
            on_submit: object | None = None,
        ) -> None:
            if callable(on_submit):
                submit_handlers[title] = on_submit

        monkeypatch.setattr(workspace_detail_module, "show_name_dialog", fake_show_name_dialog)

        client_stub = AsyncClientStub(
            [
                httpx.Response(200, json={"name": "Workspace Alpha"}),
                httpx.Response(200, json={"items": [{"id": "topo-1", "name": "Topology One", "tags": [], "last_modified": "now"}]}),
                httpx.Response(409, json={"detail": "Topology already exists"}),
                httpx.Response(409, json={"detail": "Topology already exists"}),
            ]
        )
        monkeypatch.setattr(workspace_detail_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

        async def exercise() -> None:
            await workspace_detail_module.workspace_detail_page("ws-1")

            create_button = next(button for button in fake_ui.created["button"] if button.value == "+ New Topology")
            await _invoke(create_button.handlers["click"])
            create_submit = submit_handlers["New Topology"]
            create_error = create_submit("Topology One")
            if inspect.isawaitable(create_error):
                create_error = await create_error
            assert create_error == "A topology with this name already exists."

            table = fake_ui.created["table"][0]
            await _invoke(lambda: table.handlers["rename"](SimpleNamespace(args=table.rows[0])))
            rename_submit = submit_handlers["Rename Topology"]
            rename_error = rename_submit("Topology One")
            if inspect.isawaitable(rename_error):
                rename_error = await rename_error
            assert rename_error == "A topology with this name already exists."

        asyncio.run(exercise())

        assert not fake_ui.notifications

    def test_workspace_detail_page_shows_toasts_for_create_and_rename_exceptions(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.pages.workspace_detail as workspace_detail_module
        import src.ui.components.breadcrumb as breadcrumb_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, workspace_detail_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(workspace_detail_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(workspace_detail_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(breadcrumb_module, "ui", fake_ui)

        submit_handlers: dict[str, Callable[[str], object]] = {}

        async def fake_show_name_dialog(
            title: str,
            placeholder: str = "Name",
            current_value: str = "",
            on_submit: object | None = None,
        ) -> None:
            if callable(on_submit):
                submit_handlers[title] = on_submit

        monkeypatch.setattr(workspace_detail_module, "show_name_dialog", fake_show_name_dialog)

        client_stub = AsyncClientStub(
            [
                httpx.Response(200, json={"name": "Workspace Alpha"}),
                httpx.Response(200, json={"items": [{"id": "topo-1", "name": "Topology One", "tags": [], "last_modified": "now"}]}),
                httpx.TransportError("topology create network failure"),
                httpx.TransportError("topology rename network failure"),
            ]
        )
        monkeypatch.setattr(workspace_detail_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

        async def exercise() -> None:
            await workspace_detail_module.workspace_detail_page("ws-1")

            create_button = next(button for button in fake_ui.created["button"] if button.value == "+ New Topology")
            await _invoke(create_button.handlers["click"])
            create_submit = submit_handlers["New Topology"]
            create_result = create_submit("Topology Two")
            if inspect.isawaitable(create_result):
                create_result = await create_result
            assert create_result is None

            table = fake_ui.created["table"][0]
            await _invoke(lambda: table.handlers["rename"](SimpleNamespace(args=table.rows[0])))
            rename_submit = submit_handlers["Rename Topology"]
            rename_result = rename_submit("Topology Two")
            if inspect.isawaitable(rename_result):
                rename_result = await rename_result
            assert rename_result is None

        asyncio.run(exercise())

        negative_messages = [
            str(args[0])
            for args, kwargs in fake_ui.notifications
            if kwargs.get("type") == "negative"
        ]
        assert "Could not create topology. Please try again." in negative_messages
        assert "Could not rename topology. Please try again." in negative_messages

    def test_workspace_detail_page_shows_toasts_for_create_and_rename_non_json_errors(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.pages.workspace_detail as workspace_detail_module
        import src.ui.components.breadcrumb as breadcrumb_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, workspace_detail_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(workspace_detail_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(workspace_detail_module, "redirect_if_unauthenticated", lambda **kwargs: False)
        monkeypatch.setattr(breadcrumb_module, "ui", fake_ui)

        submit_handlers: dict[str, Callable[[str], object]] = {}

        async def fake_show_name_dialog(
            title: str,
            placeholder: str = "Name",
            current_value: str = "",
            on_submit: object | None = None,
        ) -> None:
            if callable(on_submit):
                submit_handlers[title] = on_submit

        monkeypatch.setattr(workspace_detail_module, "show_name_dialog", fake_show_name_dialog)

        client_stub = AsyncClientStub(
            [
                httpx.Response(200, json={"name": "Workspace Alpha"}),
                httpx.Response(200, json={"items": [{"id": "topo-1", "name": "Topology One", "tags": [], "last_modified": "now"}]}),
                httpx.Response(500, text="upstream create failure"),
                httpx.Response(500, text="upstream rename failure"),
            ]
        )
        monkeypatch.setattr(workspace_detail_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

        async def exercise() -> None:
            await workspace_detail_module.workspace_detail_page("ws-1")

            create_button = next(button for button in fake_ui.created["button"] if button.value == "+ New Topology")
            await _invoke(create_button.handlers["click"])
            create_submit = submit_handlers["New Topology"]
            create_result = create_submit("Topology Two")
            if inspect.isawaitable(create_result):
                create_result = await create_result
            assert create_result is None

            table = fake_ui.created["table"][0]
            await _invoke(lambda: table.handlers["rename"](SimpleNamespace(args=table.rows[0])))
            rename_submit = submit_handlers["Rename Topology"]
            rename_result = rename_submit("Topology Two")
            if inspect.isawaitable(rename_result):
                rename_result = await rename_result
            assert rename_result is None

        asyncio.run(exercise())

        negative_messages = [
            str(args[0])
            for args, kwargs in fake_ui.notifications
            if kwargs.get("type") == "negative"
        ]
        assert "Could not create topology. Please try again." in negative_messages
        assert "Could not rename topology. Please try again." in negative_messages

    def test_topology_redirect_page_routes_to_topology_canvas(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.pages.workspace_detail as workspace_detail_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, workspace_detail_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(workspace_detail_module, "redirect_if_unauthenticated", lambda **kwargs: False)

        asyncio.run(workspace_detail_module.topology_redirect_page("ws-1", "topo-1"))
        assert fake_ui.navigate.to_calls[-1] == (
            "/topology?topology_id=topo-1&workspace_id=ws-1",
            False,
        )