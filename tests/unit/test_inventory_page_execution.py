"""Execution tests for inventory page and HT-031 controller behavior."""
from __future__ import annotations

import asyncio
import inspect
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest

from src.models.types import DeviceStatus, DeviceType, Role
from src.ui.pages.inventory_bulk_actions import BulkActionOutcome, BulkFailure
from tests.unit.nicegui_fakes import AsyncClientStub, FakeElement, FakeUI, install_fake_ui


async def _invoke(handler: Callable[..., object]) -> object:
    result = handler()
    if inspect.isawaitable(result):
        return await result
    return result


@contextmanager
def _noop_shell() -> Iterator[None]:
    yield


def _device_payload(
    device_id: str,
    name: str,
    power_watts: int | None = None,
) -> dict[str, object]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": device_id,
        "name": name,
        "type": DeviceType.Server.value,
        "status": DeviceStatus.Active.value,
        "ip": "10.0.0.10",
        "mac": "aa:bb:cc:dd:ee:ff",
        "os": "Linux",
        "notes": "Primary server",
        "power_watts": power_watts,
        "location_name": "Rack 1",
        "tags": [],
        "custom_fields": [],
        "services": [],
        "networks": [],
        "children": [],
        "parent_chain": [],
        "version": 1,
        "created_at": now,
        "updated_at": now,
    }


def _bulk_toolbar_row(fake_ui: FakeUI) -> FakeElement | None:
    for row in fake_ui.created["row"]:
        if any("ht-bulk-toolbar" in classes for classes in row.classes_calls):
            return row
    return None


def test_inventory_route_delegates_to_page_controller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.ui.pages.inventory as inventory_module

    fake_ui = FakeUI()
    install_fake_ui(monkeypatch, inventory_module, fake_ui, {"access_token": "token-123"})
    monkeypatch.setattr(inventory_module, "redirect_if_unauthenticated", lambda **kwargs: False)
    monkeypatch.setattr(inventory_module, "get_ui_role", lambda: Role.Contributor)

    captured: list[tuple[str, Role | None]] = []

    async def _fake_render_inventory_page(token: str, user_role: Role | None) -> None:
        captured.append((token, user_role))

    monkeypatch.setattr(inventory_module, "render_inventory_page", _fake_render_inventory_page)

    asyncio.run(inventory_module.inventory_page())

    assert captured == [("token-123", Role.Contributor)]


def test_contributor_search_change_clears_selection_and_hides_toolbar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.ui.pages.inventory_bulk_toolbar as bulk_toolbar_module
    import src.ui.pages.inventory_page_controller as controller_module
    import src.ui.pages.inventory_table as inventory_table_module

    fake_ui = FakeUI()
    monkeypatch.setattr(controller_module, "ui", fake_ui)
    monkeypatch.setattr(inventory_table_module, "ui", fake_ui)
    monkeypatch.setattr(bulk_toolbar_module, "ui", fake_ui)
    monkeypatch.setattr(controller_module, "app_shell", lambda *args, **kwargs: _noop_shell())
    monkeypatch.setattr(controller_module, "render_type_chips", lambda *args, **kwargs: None)

    async def _fake_load_tag_chips(*args: object, **kwargs: object) -> list[dict[str, object]]:
        return []

    monkeypatch.setattr(controller_module, "load_tag_chips", _fake_load_tag_chips)

    first_id = str(uuid.uuid4())
    second_id = str(uuid.uuid4())
    client_stub = AsyncClientStub(
        [
            httpx.Response(
                200,
                json={
                    "items": [
                        _device_payload(first_id, "Server Alpha"),
                        _device_payload(second_id, "Server Beta"),
                    ]
                },
                request=httpx.Request("GET", "http://test.local/api/devices/"),
            ),
            httpx.Response(
                200,
                json=[first_id, second_id],
                request=httpx.Request("GET", "http://test.local/api/devices/placed-ids"),
            ),
        ]
    )
    monkeypatch.setattr(controller_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

    async def exercise() -> None:
        await controller_module.render_inventory_page(token="token", user_role=Role.Contributor)

        table = fake_ui.created["table"][0]
        search_input = fake_ui.created["input"][0]
        toolbar = _bulk_toolbar_row(fake_ui)

        assert table.selection == "multiple"
        assert toolbar is not None
        assert len(table.rows) == 2

        first_row = table.rows[0]
        table.selected = [first_row]
        await _invoke(lambda: table.handlers["select"](SimpleNamespace(selection=[first_row])))
        assert toolbar.visible is True

        await _invoke(lambda: search_input.handlers["value_change"](SimpleNamespace(value="zzz")))

        assert table.selected == []
        assert toolbar.visible is False

    asyncio.run(exercise())


def test_header_select_all_with_active_filter_selects_filtered_rows_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.ui.pages.inventory_bulk_toolbar as bulk_toolbar_module
    import src.ui.pages.inventory_page_controller as controller_module
    import src.ui.pages.inventory_table as inventory_table_module

    fake_ui = FakeUI()
    monkeypatch.setattr(controller_module, "ui", fake_ui)
    monkeypatch.setattr(inventory_table_module, "ui", fake_ui)
    monkeypatch.setattr(bulk_toolbar_module, "ui", fake_ui)
    monkeypatch.setattr(controller_module, "app_shell", lambda *args, **kwargs: _noop_shell())
    monkeypatch.setattr(controller_module, "render_type_chips", lambda *args, **kwargs: None)

    async def _fake_load_tag_chips(*args: object, **kwargs: object) -> list[dict[str, object]]:
        return []

    monkeypatch.setattr(controller_module, "load_tag_chips", _fake_load_tag_chips)

    first_id = str(uuid.uuid4())
    second_id = str(uuid.uuid4())
    client_stub = AsyncClientStub(
        [
            httpx.Response(
                200,
                json={
                    "items": [
                        _device_payload(first_id, "Server Alpha"),
                        _device_payload(second_id, "Server Beta"),
                    ]
                },
                request=httpx.Request("GET", "http://test.local/api/devices/"),
            ),
            httpx.Response(
                200,
                json=[first_id, second_id],
                request=httpx.Request("GET", "http://test.local/api/devices/placed-ids"),
            ),
        ]
    )
    monkeypatch.setattr(controller_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

    async def exercise() -> None:
        await controller_module.render_inventory_page(token="token", user_role=Role.Contributor)

        table = fake_ui.created["table"][0]
        search_input = fake_ui.created["input"][0]

        assert len(table.rows) == 2

        await _invoke(lambda: search_input.handlers["value_change"](SimpleNamespace(value="alpha")))

        assert len(table.rows) == 1
        assert str(table.rows[0]["id"]) == first_id

        visible_rows = list(table.rows)
        await _invoke(lambda: table.handlers["select"](SimpleNamespace(selection=visible_rows)))

        assert {str(row.get("id", "")) for row in table.selected} == {first_id}

    asyncio.run(exercise())


def test_show_power_toggle_rebuilds_table_columns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.ui.pages.inventory_bulk_toolbar as bulk_toolbar_module
    import src.ui.pages.inventory_page_controller as controller_module
    import src.ui.pages.inventory_table as inventory_table_module

    fake_ui = FakeUI()
    monkeypatch.setattr(controller_module, "ui", fake_ui)
    monkeypatch.setattr(inventory_table_module, "ui", fake_ui)
    monkeypatch.setattr(bulk_toolbar_module, "ui", fake_ui)
    monkeypatch.setattr(controller_module, "app_shell", lambda *args, **kwargs: _noop_shell())
    monkeypatch.setattr(controller_module, "render_type_chips", lambda *args, **kwargs: None)

    async def _fake_load_tag_chips(*args: object, **kwargs: object) -> list[dict[str, object]]:
        return []

    monkeypatch.setattr(controller_module, "load_tag_chips", _fake_load_tag_chips)

    first_id = str(uuid.uuid4())
    second_id = str(uuid.uuid4())
    client_stub = AsyncClientStub(
        [
            httpx.Response(
                200,
                json={
                    "items": [
                        _device_payload(first_id, "Server Alpha", power_watts=120),
                        _device_payload(second_id, "Server Beta", power_watts=None),
                    ]
                },
                request=httpx.Request("GET", "http://test.local/api/devices/"),
            ),
            httpx.Response(
                200,
                json=[first_id, second_id],
                request=httpx.Request("GET", "http://test.local/api/devices/placed-ids"),
            ),
        ]
    )
    monkeypatch.setattr(controller_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

    async def exercise() -> None:
        await controller_module.render_inventory_page(token="token", user_role=Role.Contributor)

        table = fake_ui.created["table"][0]
        assert "power" not in [str(col.get("name")) for col in table.columns]

        show_power_checkbox = next(
            cb for cb in fake_ui.created["checkbox"] if cb.value is False
        )
        await _invoke(
            lambda: show_power_checkbox.handlers["change"](SimpleNamespace(value=True))
        )

        assert "power" in [str(col.get("name")) for col in table.columns]
        assert len(table.rows) == 2

    asyncio.run(exercise())


def test_bulk_action_updates_rows_as_each_item_settles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.ui.pages.inventory_bulk_toolbar as bulk_toolbar_module
    import src.ui.pages.inventory_page_controller as controller_module
    import src.ui.pages.inventory_table as inventory_table_module

    fake_ui = FakeUI()
    monkeypatch.setattr(controller_module, "ui", fake_ui)
    monkeypatch.setattr(inventory_table_module, "ui", fake_ui)
    monkeypatch.setattr(bulk_toolbar_module, "ui", fake_ui)
    monkeypatch.setattr(controller_module, "app_shell", lambda *args, **kwargs: _noop_shell())
    monkeypatch.setattr(controller_module, "render_type_chips", lambda *args, **kwargs: None)

    async def _fake_load_tag_chips(*args: object, **kwargs: object) -> list[dict[str, object]]:
        return []

    monkeypatch.setattr(controller_module, "load_tag_chips", _fake_load_tag_chips)

    first_id = str(uuid.uuid4())
    second_id = str(uuid.uuid4())
    client_stub = AsyncClientStub(
        [
            httpx.Response(
                200,
                json={
                    "items": [
                        _device_payload(first_id, "Server Alpha"),
                        _device_payload(second_id, "Server Beta"),
                    ]
                },
                request=httpx.Request("GET", "http://test.local/api/devices/"),
            ),
            httpx.Response(
                200,
                json=[first_id, second_id],
                request=httpx.Request("GET", "http://test.local/api/devices/placed-ids"),
            ),
        ]
    )
    monkeypatch.setattr(controller_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

    first_settled = asyncio.Event()
    allow_finish = asyncio.Event()
    captured: dict[str, object] = {}

    class _FakeBulkHandlers:
        def __init__(
            self,
            *,
            state: object,
            token: str,
            run_bulk: Callable[..., object],
            on_progress: Callable[..., object],
        ) -> None:
            _ = token, on_progress
            self._state = state
            self._run_bulk = run_bulk
            captured["handler"] = self

        async def add_tag(self, tag_id_raw: str) -> None:
            _ = tag_id_raw

            async def _runner(
                devices: list[object],
                on_settled: Callable[[BulkActionOutcome], None],
            ) -> BulkActionOutcome:
                first_device_id = str(getattr(devices[0], "id"))
                second_device_id = str(getattr(devices[1], "id"))
                on_settled(BulkActionOutcome(succeeded_ids=[first_device_id]))
                first_settled.set()
                await allow_finish.wait()
                on_settled(BulkActionOutcome(succeeded_ids=[second_device_id]))
                return BulkActionOutcome(succeeded_ids=[first_device_id, second_device_id])

            def _on_success(outcome: BulkActionOutcome) -> None:
                for device in getattr(self._state, "all_devices"):
                    if str(getattr(device, "id")) in outcome.succeeded_ids and not str(
                        getattr(device, "name")
                    ).endswith(" (done)"):
                        device.name = f"{device.name} (done)"

            await self._run_bulk(action="Adding", runner=_runner, on_success=_on_success)

        async def remove_tag(self, tag_id_raw: str) -> None:
            _ = tag_id_raw

        async def set_location(self, location_id_raw: str) -> None:
            _ = location_id_raw

        async def delete_selected(self) -> None:
            return None

    monkeypatch.setattr(controller_module, "InventoryBulkHandlers", _FakeBulkHandlers)

    async def exercise() -> None:
        await controller_module.render_inventory_page(token="token", user_role=Role.Contributor)

        table = fake_ui.created["table"][0]
        selected_rows = list(table.rows)
        await _invoke(lambda: table.handlers["select"](SimpleNamespace(selection=selected_rows)))

        handler = captured["handler"]
        bulk_task = asyncio.create_task(handler.add_tag(str(uuid.uuid4())))  # type: ignore[attr-defined]

        await asyncio.wait_for(first_settled.wait(), timeout=1.0)
        first_pass_names = [str(row.get("name", "")) for row in table.rows]
        assert "Server Alpha (done)" in first_pass_names
        assert "Server Beta (done)" not in first_pass_names

        allow_finish.set()
        await asyncio.wait_for(bulk_task, timeout=1.0)

        final_names = [str(row.get("name", "")) for row in table.rows]
        assert "Server Alpha (done)" in final_names
        assert "Server Beta (done)" in final_names

    asyncio.run(exercise())


def test_reader_has_no_bulk_controls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.ui.pages.inventory_page_controller as controller_module
    import src.ui.pages.inventory_table as inventory_table_module

    fake_ui = FakeUI()
    monkeypatch.setattr(controller_module, "ui", fake_ui)
    monkeypatch.setattr(inventory_table_module, "ui", fake_ui)
    monkeypatch.setattr(controller_module, "app_shell", lambda *args, **kwargs: _noop_shell())
    monkeypatch.setattr(controller_module, "render_type_chips", lambda *args, **kwargs: None)

    async def _fake_load_tag_chips(*args: object, **kwargs: object) -> list[dict[str, object]]:
        return []

    monkeypatch.setattr(controller_module, "load_tag_chips", _fake_load_tag_chips)

    device_id = str(uuid.uuid4())
    client_stub = AsyncClientStub(
        [
            httpx.Response(
                200,
                json={"items": [_device_payload(device_id, "Reader Device")]},
                request=httpx.Request("GET", "http://test.local/api/devices/"),
            ),
            httpx.Response(
                200,
                json=[device_id],
                request=httpx.Request("GET", "http://test.local/api/devices/placed-ids"),
            ),
        ]
    )
    monkeypatch.setattr(controller_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

    asyncio.run(controller_module.render_inventory_page(token="token", user_role=Role.Reader))

    table = fake_ui.created["table"][0]
    assert table.selection is None
    assert _bulk_toolbar_row(fake_ui) is None


def test_resolve_selection_after_bulk_handles_partial_and_success() -> None:
    import src.ui.pages.inventory_page_controller as controller_module

    requested = {"a", "b", "c"}

    partial = BulkActionOutcome(
        succeeded_ids=["a"],
        failed=[BulkFailure(device_id="b", device_name="B", detail="failed")],
        skipped=[BulkFailure(device_id="c", device_name="C", detail="skipped")],
    )
    assert controller_module.resolve_selection_after_bulk(requested, partial) == {"b", "c"}

    all_success = BulkActionOutcome(succeeded_ids=["a", "b", "c"])
    assert controller_module.resolve_selection_after_bulk(requested, all_success) == set()

    aborted = BulkActionOutcome(
        succeeded_ids=["a"],
        failed=[BulkFailure(device_id="b", device_name="B", detail="failed")],
        aborted=True,
        abort_detail="network dropped",
    )
    assert controller_module.resolve_selection_after_bulk(requested, aborted) == {"b", "c"}


def test_remove_tag_toast_titles_include_tag_name(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.ui.pages.inventory_bulk_handlers as handlers_module

    tag_id = uuid.uuid4()
    device_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    state = SimpleNamespace(
        all_devices=[
            SimpleNamespace(
                id=device_id,
                name="Server Alpha",
                tags=[
                    SimpleNamespace(
                        id=tag_id,
                        name="production",
                        color="#22aa66",
                        created_at=now,
                    )
                ],
            )
        ],
        all_tags=[
            {
                "id": str(tag_id),
                "name": "production",
                "color": "#22aa66",
                "created_at": now.isoformat(),
            }
        ],
        locations=None,
        orphan_ids=set(),
        placement_counts={},
    )

    toasts: list[dict[str, str]] = []

    def _fake_show_toast(
        *,
        type: str,
        title: str,
        description: str | None = None,
    ) -> None:
        toasts.append({"type": type, "title": title, "description": description or ""})

    monkeypatch.setattr(handlers_module, "show_toast", _fake_show_toast)

    queued_results: list[tuple[BulkActionOutcome, int]] = [
        (BulkActionOutcome(succeeded_ids=[str(device_id)]), 1),
        (
            BulkActionOutcome(
                succeeded_ids=[str(device_id)],
                failed=[BulkFailure(device_id="failed", device_name="failed", detail="boom")],
            ),
            2,
        ),
    ]

    async def _run_bulk(*, action: str, runner: object, on_success: Callable[[BulkActionOutcome], None]) -> tuple[BulkActionOutcome, int] | None:
        _ = action, runner
        outcome, total = queued_results.pop(0)
        on_success(outcome)
        return outcome, total

    handlers = handlers_module.InventoryBulkHandlers(
        state=state,
        token="token",
        run_bulk=_run_bulk,
        on_progress=lambda _progress: None,
    )

    async def exercise() -> None:
        await handlers.remove_tag(str(tag_id))
        await handlers.remove_tag(str(tag_id))

    asyncio.run(exercise())

    assert toasts[0]["title"] == "Tag 'production' removed from 1 devices"
    assert toasts[1]["title"] == "Tag 'production' removed from 1 of 2 devices"