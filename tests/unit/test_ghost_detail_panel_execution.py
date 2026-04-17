"""Execution tests for ghost detail panel behavior (HT-075)."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from types import SimpleNamespace

import pytest

from tests.unit.nicegui_fakes import AsyncClientStub, FakeResponse, FakeUI, install_fake_ui


async def _invoke(handler: Callable[..., object]) -> object:
    result = handler()
    if inspect.isawaitable(result):
        return await result
    return result


def _success_response_payload() -> dict[str, object]:
    return {
        "history_entry_id": "history-new",
        "current_diagram_id": "diagram-restored",
        "current_diagram_version": 8,
        "draft_version": None,
        "has_unsaved_changes": False,
        "cytoscape_json": {
            "elements": {
                "nodes": [{"data": {"id": "live-1", "label": "Live Device"}}],
                "edges": [],
            }
        },
    }


class TestGhostDetailPanelExecution:
    def test_reader_role_hides_reconcile_actions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.components.ghost_detail_panel as ghost_panel_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, ghost_panel_module, fake_ui)

        ghost_panel_module.render_ghost_detail_panel(token="token", user_role="Reader", topology_id="topo-1")

        button_labels = [str(button.value) for button in fake_ui.created["button"]]
        assert "Recreate as New Device" not in button_labels
        assert "Map Selected Device" not in button_labels

    def test_contributor_role_shows_reconcile_actions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.components.ghost_detail_panel as ghost_panel_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, ghost_panel_module, fake_ui)

        ghost_panel_module.render_ghost_detail_panel(token="token", user_role="Contributor", topology_id="topo-1")

        button_labels = [str(button.value) for button in fake_ui.created["button"]]
        assert "Recreate as New Device" in button_labels
        assert "Map Selected Device" in button_labels

    def test_recreate_action_posts_reconcile_endpoint_and_applies_snapshot(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.ghost_detail_panel as ghost_panel_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, ghost_panel_module, fake_ui)

        client_stub = AsyncClientStub(
            [
                FakeResponse(200, {"items": [{"id": "live-1", "name": "Live", "type": "Server"}]}),
                FakeResponse(200, _success_response_payload()),
            ]
        )
        monkeypatch.setattr(ghost_panel_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)
        monkeypatch.setattr(ghost_panel_module, "show_toast", lambda *args, **kwargs: None)

        async def exercise() -> None:
            ghost_panel_module.render_ghost_detail_panel(
                token="token",
                user_role="Contributor",
                topology_id="topo-restore",
            )
            select_handler = fake_ui.on_handlers["ghost_panel_select"]
            await _invoke(
                lambda: select_handler(
                    SimpleNamespace(
                        args={
                            "ghost_id": "00000000-0000-0000-0000-000000000777",
                            "ghost_original_name": "Old NAS",
                            "ghost_original_type": "NAS",
                            "ghost_status": "Deleted from inventory",
                        }
                    )
                )
            )

            recreate_button = next(
                button for button in fake_ui.created["button"] if button.value == "Recreate as New Device"
            )
            await _invoke(recreate_button.handlers["click"])

        asyncio.run(exercise())

        assert any(
            method == "POST" and "/ghosts/00000000-0000-0000-0000-000000000777/recreate" in url
            for method, url in client_stub.calls
        )
        assert any("window.applyTopologySnapshot" in code for code in fake_ui.run_javascript_calls)

    def test_map_action_posts_selected_live_device(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.components.ghost_detail_panel as ghost_panel_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, ghost_panel_module, fake_ui)

        client_stub = AsyncClientStub(
            [
                FakeResponse(200, {"items": [{"id": "live-1", "name": "Live", "type": "Server"}]}),
                FakeResponse(200, _success_response_payload()),
            ]
        )
        monkeypatch.setattr(ghost_panel_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)
        monkeypatch.setattr(ghost_panel_module, "show_toast", lambda *args, **kwargs: None)

        async def exercise() -> None:
            ghost_panel_module.render_ghost_detail_panel(
                token="token",
                user_role="Contributor",
                topology_id="topo-restore",
            )
            select_handler = fake_ui.on_handlers["ghost_panel_select"]
            await _invoke(
                lambda: select_handler(
                    SimpleNamespace(
                        args={
                            "ghost_id": "00000000-0000-0000-0000-000000000777",
                            "ghost_original_name": "Old NAS",
                            "ghost_original_type": "NAS",
                            "ghost_status": "Deleted from inventory",
                        }
                    )
                )
            )

            map_select = fake_ui.created["select"][0]
            map_select.value = "live-1"
            map_button = next(button for button in fake_ui.created["button"] if button.value == "Map Selected Device")
            await _invoke(map_button.handlers["click"])

        asyncio.run(exercise())

        post_payloads = [
            kwargs.get("json")
            for (method, _url), kwargs in zip(client_stub.calls, client_stub.call_kwargs)
            if method == "POST"
        ]
        assert post_payloads
        assert isinstance(post_payloads[0], dict)
        assert post_payloads[0].get("live_device_id") == "live-1"
