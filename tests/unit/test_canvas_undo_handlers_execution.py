"""Execution tests for canvas undo handler API bridge behavior (HT-032)."""

from __future__ import annotations

import asyncio
import inspect
import json
from types import SimpleNamespace
from typing import Callable

import pytest

from tests.unit.nicegui_fakes import FakeUI


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, object] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict[str, object]:
        return self._payload


async def _invoke(handler: Callable[..., object], args: dict[str, object]) -> object:
    result = handler(SimpleNamespace(args=args))
    if inspect.isawaitable(result):
        return await result
    return result


def _extract_success_payload(scripts: list[str]) -> dict[str, object]:
    marker = "window._htResolveUndoApiSuccess("
    call = next(script for script in reversed(scripts) if marker in script)
    start = call.index(marker) + len(marker)
    end = call.rindex(");")
    args = json.loads(f"[{call[start:end]}]")
    return args[2]


class TestCanvasUndoHandlersExecution:
    def test_create_published_edge_returns_entry_patch_with_recreated_connection_id(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.canvas_undo_handlers as handlers_module

        fake_ui = FakeUI()
        monkeypatch.setattr(handlers_module, "ui", fake_ui)

        class _Client:
            async def __aenter__(self) -> "_Client":
                return self

            async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
                return None

            async def request(
                self,
                method: str,
                url: str,
                json: dict[str, object] | None = None,
                headers: dict[str, str] | None = None,
                timeout: float | None = None,
            ) -> _FakeResponse:
                _ = method, url, json, headers, timeout
                return _FakeResponse(
                    201,
                    {
                        "id": "new-connection-id",
                        "source_id": "source-1",
                        "target_id": "target-1",
                        "type": "Ethernet",
                        "label": "uplink",
                    },
                )

        monkeypatch.setattr(handlers_module.httpx, "AsyncClient", lambda *args, **kwargs: _Client())

        handlers_module.register_canvas_undo_handlers("token", "Contributor")

        undo_handler = fake_ui.on_handlers["ht_canvas_undo_request"]
        entry = {
            "entry_id": "entry-1",
            "forward": {
                "op": "delete_published_edge",
                "payload": {
                    "connection_id": "old-connection-id",
                    "source_id": "source-1",
                    "target_id": "target-1",
                    "connection_type": "Ethernet",
                    "label": "uplink",
                },
            },
            "reverse": {
                "op": "create_published_edge",
                "payload": {
                    "connection_id": "old-connection-id",
                    "source_id": "source-1",
                    "target_id": "target-1",
                    "connection_type": "Ethernet",
                    "label": "uplink",
                },
            },
        }

        asyncio.run(_invoke(undo_handler, {"direction": "undo", "entry": entry}))

        payload = _extract_success_payload(fake_ui.run_javascript_calls)

        entry_patch = payload.get("entry_patch")
        assert isinstance(entry_patch, dict)
        forward = entry_patch.get("forward")
        reverse = entry_patch.get("reverse")
        assert isinstance(forward, dict)
        assert isinstance(reverse, dict)
        assert isinstance(forward.get("payload"), dict)
        assert isinstance(reverse.get("payload"), dict)
        assert forward["payload"]["connection_id"] == "new-connection-id"
        assert reverse["payload"]["connection_id"] == "new-connection-id"

    def test_delete_published_device_prefers_active_diagram_snapshot_node_set(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.canvas_undo_handlers as handlers_module

        fake_ui = FakeUI()
        monkeypatch.setattr(handlers_module, "ui", fake_ui)

        snapshot = {
            "device": {"id": "device-1"},
            "connections": [],
            "placements": [
                {
                    "diagram_id": "diagram-a",
                    "node": {
                        "group": "nodes",
                        "data": {"id": "node-a", "label": "A"},
                        "position": {"x": 10, "y": 10},
                    },
                },
                {
                    "diagram_id": "diagram-b",
                    "node": {
                        "group": "nodes",
                        "data": {"id": "node-b", "label": "B"},
                        "position": {"x": 20, "y": 20},
                    },
                },
            ],
        }

        class _Client:
            async def __aenter__(self) -> "_Client":
                return self

            async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
                return None

            async def request(
                self,
                method: str,
                url: str,
                json: dict[str, object] | None = None,
                headers: dict[str, str] | None = None,
                timeout: float | None = None,
            ) -> _FakeResponse:
                _ = method, url, json, headers, timeout
                return _FakeResponse(200, {"snapshot": snapshot, "modified_diagrams": []})

        monkeypatch.setattr(handlers_module.httpx, "AsyncClient", lambda *args, **kwargs: _Client())

        handlers_module.register_canvas_undo_handlers("token", "Contributor")

        undo_handler = fake_ui.on_handlers["ht_canvas_undo_request"]
        entry = {
            "entry_id": "entry-2",
            "forward": {
                "op": "delete_published_device",
                "payload": {
                    "device_id": "device-1",
                    "active_diagram_id": "diagram-b",
                },
            },
            "reverse": {"op": "restore_published_device", "payload": {}},
        }

        asyncio.run(_invoke(undo_handler, {"direction": "redo", "entry": entry}))

        payload = _extract_success_payload(fake_ui.run_javascript_calls)
        graph_patch = payload.get("graph_patch")
        assert isinstance(graph_patch, dict)
        snapshot_payload = graph_patch.get("snapshot")
        assert isinstance(snapshot_payload, dict)
        nodes = snapshot_payload.get("nodes")
        assert isinstance(nodes, list)
        assert isinstance(nodes[0], dict)
        assert isinstance(nodes[0].get("data"), dict)
        assert nodes[0]["data"]["id"] == "node-b"

    def test_update_device_field_undo_uses_current_device_version_not_stale_cursor(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.canvas_undo_handlers as handlers_module

        fake_ui = FakeUI()
        monkeypatch.setattr(handlers_module, "ui", fake_ui)

        class _Client:
            def __init__(self) -> None:
                self.patch_versions: list[int] = []

            async def __aenter__(self) -> "_Client":
                return self

            async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
                return None

            async def get(
                self,
                url: str,
                headers: dict[str, str] | None = None,
                timeout: float | None = None,
            ) -> _FakeResponse:
                _ = url, headers, timeout
                return _FakeResponse(200, {"version": 7})

            async def patch(
                self,
                url: str,
                json: dict[str, object] | None = None,
                headers: dict[str, str] | None = None,
                timeout: float | None = None,
            ) -> _FakeResponse:
                _ = url, headers, timeout
                body = json or {}
                version = int(body.get("version", -1))
                self.patch_versions.append(version)
                if version != 7:
                    return _FakeResponse(409, {"detail": "Conflict"})
                return _FakeResponse(200, {"version": 8})

        client = _Client()
        monkeypatch.setattr(handlers_module.httpx, "AsyncClient", lambda *args, **kwargs: client)

        handlers_module.register_canvas_undo_handlers("token", "Contributor")

        undo_handler = fake_ui.on_handlers["ht_canvas_undo_request"]
        entry = {
            "entry_id": "entry-3",
            "forward": {"op": "update_device_field", "payload": {}},
            "reverse": {
                "op": "update_device_field",
                "payload": {
                    "device_id": "550e8400-e29b-41d4-a716-446655440000",
                    "field": "name",
                    "before": "old-name",
                    "after": "new-name",
                    "version_cursor": 2,
                    "node_patch": {"name": "new-name", "version": 2},
                },
            },
        }

        asyncio.run(_invoke(undo_handler, {"direction": "undo", "entry": entry}))

        payload = _extract_success_payload(fake_ui.run_javascript_calls)
        assert client.patch_versions == [7]

        graph_patch = payload.get("graph_patch")
        assert isinstance(graph_patch, dict)
        patch = graph_patch.get("patch")
        assert isinstance(patch, dict)
        assert patch.get("version") == 8
