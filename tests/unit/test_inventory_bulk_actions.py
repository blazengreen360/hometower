"""Unit tests for HT-031 inventory bulk action execution helpers."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

import httpx

from src.models.types import DeviceStatus, DeviceType
from src.ui.pages.inventory_bulk_actions import (
    add_tag_to_devices,
    delete_devices_with_connection_preflight,
    remove_tag_from_devices,
    set_location_for_devices,
)
from tests.unit.nicegui_fakes import AsyncClientStub


def _device(name: str, version: int = 1) -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), name=name, version=version)


def _device_response_payload(
    *,
    device_id: str,
    version: int,
    location_id: str,
) -> dict[str, object]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": device_id,
        "name": "Updated Device",
        "type": DeviceType.Server.value,
        "status": DeviceStatus.Active.value,
        "ip": "10.0.0.1",
        "mac": "aa:bb:cc:dd:ee:ff",
        "os": "Linux",
        "notes": "bulk updated",
        "location_id": location_id,
        "parent_id": None,
        "version": version,
        "created_at": now,
        "updated_at": now,
    }


def test_add_tag_partial_http_failure(monkeypatch) -> None:
    import src.ui.pages.inventory_bulk_actions as bulk_actions

    first = _device("alpha")
    second = _device("beta")
    tag_id = uuid.uuid4()

    client_stub = AsyncClientStub(
        [
            httpx.Response(204, request=httpx.Request("POST", "http://test.local/api/devices/alpha/tags")),
            httpx.Response(
                409,
                json={"detail": "already attached"},
                request=httpx.Request("POST", "http://test.local/api/devices/beta/tags"),
            ),
        ]
    )
    monkeypatch.setattr(bulk_actions.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

    progress: list[tuple[int, int]] = []

    async def exercise() -> None:
        outcome = await add_tag_to_devices(
            devices=[first, second],
            tag_id=tag_id,
            token="token",
            on_progress=lambda p: progress.append((p.completed, p.total)),
        )

        assert outcome.aborted is False
        assert outcome.succeeded_ids == [str(first.id)]
        assert len(outcome.failed) == 1
        assert outcome.failed[0].device_id == str(second.id)

    asyncio.run(exercise())

    assert progress == [(1, 2), (2, 2)]


def test_remove_tag_all_success(monkeypatch) -> None:
    import src.ui.pages.inventory_bulk_actions as bulk_actions

    first = _device("alpha")
    second = _device("beta")
    tag_id = uuid.uuid4()

    client_stub = AsyncClientStub(
        [
            httpx.Response(204, request=httpx.Request("DELETE", "http://test.local/a")),
            httpx.Response(204, request=httpx.Request("DELETE", "http://test.local/b")),
        ]
    )
    monkeypatch.setattr(bulk_actions.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

    async def exercise() -> None:
        outcome = await remove_tag_from_devices(
            devices=[first, second],
            tag_id=tag_id,
            token="token",
            on_progress=lambda _p: None,
        )

        assert outcome.succeeded_ids == [str(first.id), str(second.id)]
        assert outcome.failed == []
        assert outcome.aborted is False

    asyncio.run(exercise())


def test_set_location_uses_current_version_and_collects_updated_devices(monkeypatch) -> None:
    import src.ui.pages.inventory_bulk_actions as bulk_actions

    device = _device("alpha", version=7)
    location_id = uuid.uuid4()

    client_stub = AsyncClientStub(
        [
            httpx.Response(
                200,
                json=_device_response_payload(
                    device_id=str(device.id),
                    version=8,
                    location_id=str(location_id),
                ),
                request=httpx.Request("PATCH", "http://test.local/api/devices/alpha"),
            ),
        ]
    )
    monkeypatch.setattr(bulk_actions.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

    async def exercise() -> None:
        outcome = await set_location_for_devices(
            devices=[device],
            location_id=location_id,
            token="token",
            on_progress=lambda _p: None,
        )

        assert outcome.succeeded_ids == [str(device.id)]
        assert outcome.updated_devices[str(device.id)].version == 8

    asyncio.run(exercise())

    assert client_stub.call_kwargs[0]["json"] == {
        "location_id": str(location_id),
        "version": 7,
    }


def test_delete_skips_devices_with_active_connections(monkeypatch) -> None:
    import src.ui.pages.inventory_bulk_actions as bulk_actions

    connected = _device("connected")
    clear = _device("clear")

    client_stub = AsyncClientStub(
        [
            httpx.Response(
                200,
                json=[{"id": str(uuid.uuid4())}],
                request=httpx.Request("GET", "http://test.local/api/devices/connected/connections"),
            ),
            httpx.Response(
                200,
                json=[],
                request=httpx.Request("GET", "http://test.local/api/devices/clear/connections"),
            ),
            httpx.Response(204, request=httpx.Request("DELETE", "http://test.local/api/devices/clear")),
        ]
    )
    monkeypatch.setattr(bulk_actions.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

    progress: list[tuple[int, int]] = []

    async def exercise() -> None:
        outcome = await delete_devices_with_connection_preflight(
            devices=[connected, clear],
            token="token",
            on_progress=lambda p: progress.append((p.completed, p.total)),
        )

        assert outcome.succeeded_ids == [str(clear.id)]
        assert len(outcome.skipped) == 1
        assert outcome.skipped[0].device_id == str(connected.id)
        assert "active connections" in outcome.skipped[0].detail
        assert outcome.failed == []

    asyncio.run(exercise())

    assert [method for method, _url in client_stub.calls] == ["GET", "GET", "DELETE"]
    assert progress == [(1, 2), (2, 2)]


def test_delete_aborts_on_network_error_and_preserves_completed_count(monkeypatch) -> None:
    import src.ui.pages.inventory_bulk_actions as bulk_actions

    first = _device("first")
    second = _device("second")

    client_stub = AsyncClientStub(
        [
            httpx.Response(
                200,
                json=[],
                request=httpx.Request("GET", "http://test.local/api/devices/first/connections"),
            ),
            httpx.Response(204, request=httpx.Request("DELETE", "http://test.local/api/devices/first")),
            httpx.ConnectError("connection reset"),
        ]
    )
    monkeypatch.setattr(bulk_actions.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

    progress: list[tuple[int, int]] = []

    async def exercise() -> None:
        outcome = await delete_devices_with_connection_preflight(
            devices=[first, second],
            token="token",
            on_progress=lambda p: progress.append((p.completed, p.total)),
        )

        assert outcome.aborted is True
        assert outcome.succeeded_ids == [str(first.id)]
        assert outcome.abort_detail is not None
        assert "connection reset" in outcome.abort_detail

    asyncio.run(exercise())

    assert progress == [(1, 2)]
