"""Unit tests for inventory UI helper functions."""
import asyncio
import inspect
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest

from src.ui.pages import inventory_delete_dialog
from src.ui.pages import inventory_filters
from src.ui.pages import inventory_table
from src.models.types import DeviceStatus, DeviceType
from tests.unit.nicegui_fakes import AsyncClientStub, FakeUI


class _FakeLabel:
    def style(self, _style: str) -> "_FakeLabel":
        return self


class _FakeChip:
    def __init__(self, on_click: Callable[[], None] | None = None) -> None:
        self.click_handler: Callable[[], None] | None = on_click
        self.props_calls: list[str] = []

    def style(self, _style: str) -> "_FakeChip":
        return self

    def props(self, props_str: str) -> "_FakeChip":
        self.props_calls.append(props_str)
        return self

    def on(self, event_name: str, handler: Callable[[], None]) -> "_FakeChip":
        if event_name == "click":
            self.click_handler = handler
        return self

    def click(self) -> None:
        assert self.click_handler is not None
        self.click_handler()


class _FakeTagChipRow:
    def clear(self) -> None:
        return None

    def __enter__(self) -> "_FakeTagChipRow":
        return self

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        tb: object,
    ) -> None:
        return None


async def _invoke(handler: Callable[..., object]) -> object:
    result = handler()
    if inspect.isawaitable(result):
        return await result
    return result


def test_render_tag_chip_filters_toggles_uuid_tag_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chips: list[_FakeChip] = []

    def _fake_chip(*_args: object, **_kwargs: object) -> _FakeChip:
        chip = _FakeChip(on_click=_kwargs.get("on_click"))  # type: ignore[arg-type]
        chips.append(chip)
        return chip

    monkeypatch.setattr(inventory_filters.ui, "chip", _fake_chip)
    monkeypatch.setattr(
        inventory_filters.ui,
        "label",
        lambda *_args, **_kwargs: _FakeLabel(),
    )

    selected_tag_ids: set[uuid.UUID] = set()
    tag_chip_metas: list[dict[str, object]] = []
    apply_count = 0

    def _apply_filters() -> None:
        nonlocal apply_count
        apply_count += 1

    tag_id = uuid.uuid4()
    inventory_filters.render_tag_chip_filters(
        tag_chip_row=_FakeTagChipRow(),
        all_tags=[{"id": str(tag_id), "name": "prod", "color": "#22aa66"}],
        selected_tag_ids=selected_tag_ids,
        tag_chip_metas=tag_chip_metas,
        apply_filters=_apply_filters,
    )

    assert len(chips) == 1
    chips[0].click()
    assert selected_tag_ids == {tag_id}

    chips[0].click()
    assert selected_tag_ids == set()
    assert apply_count == 2


def test_inventory_table_includes_edit_and_topology_actions() -> None:
    col_names = [str(col.get("name")) for col in inventory_table._INVENTORY_TABLE_COLUMNS]
    assert "actions" in col_names
    assert "/inventory/edit/" in inventory_table._ACTIONS_SLOT
    assert "/topology?device_id=" in inventory_table._ACTIONS_SLOT


def test_inventory_table_includes_networks_column_and_badge_slot() -> None:
    col_names = [str(col.get("name")) for col in inventory_table._INVENTORY_TABLE_COLUMNS]
    assert "networks" in col_names
    assert "q-chip" in inventory_table._NETWORKS_SLOT


def test_build_inventory_rows_includes_network_badge_payload() -> None:
    now = datetime.now(timezone.utc)
    fake_device = SimpleNamespace(
        id=uuid.uuid4(),
        type=DeviceType.Server,
        status=DeviceStatus.Active,
        name="srv-1",
        ip="10.0.10.10",
        tags=[],
        location_name="",
        services=[],
        networks=[
            SimpleNamespace(network_id=uuid.uuid4(), name="Management", color="#3b82f6"),
            SimpleNamespace(network_id=uuid.uuid4(), name="Storage", color="#22c55e"),
        ],
        updated_at=now,
    )

    rows = inventory_table.build_inventory_rows(
        devices=[fake_device],
        relative_time=lambda _dt: "now",
    )
    assert rows[0]["networks"] == [
        {"id": str(fake_device.networks[0].network_id), "label": "Management", "color": "#3b82f6"},
        {"id": str(fake_device.networks[1].network_id), "label": "Storage", "color": "#22c55e"},
    ]


def test_inventory_table_delete_action_emits_in_place_without_query_navigation() -> None:
    assert "/inventory?delete_id=" not in inventory_table._ACTIONS_SLOT
    assert "onclick=\"emitEvent('inventory_delete'" in inventory_table._ACTIONS_SLOT
    assert "inventory-delete-" in inventory_table._ACTIONS_SLOT


def test_create_inventory_table_enables_selection_for_bulk_edit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ui = FakeUI()
    monkeypatch.setattr(inventory_table, "ui", fake_ui)

    table = inventory_table.create_inventory_table(
        can_bulk_edit=True,
        on_select=lambda _event: None,
    )

    assert table.selection == "multiple"
    assert "select" in table.handlers


def test_create_inventory_table_disables_selection_for_reader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ui = FakeUI()
    monkeypatch.setattr(inventory_table, "ui", fake_ui)

    table = inventory_table.create_inventory_table(
        can_bulk_edit=False,
        on_select=lambda _event: None,
    )

    assert table.selection is None
    assert "select" not in table.handlers


def test_delete_confirmation_fetches_placements_before_open_and_cancel_skips_delete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ui = FakeUI()
    monkeypatch.setattr(inventory_delete_dialog, "ui", fake_ui)

    placements_url = "http://127.0.0.1:8080/api/devices/device-1/placements"
    client_stub = AsyncClientStub(
        [
            httpx.Response(
                200,
                json=[{"view_name": "Core View", "topology_name": "Lab"}],
                request=httpx.Request("GET", placements_url),
            ),
        ]
    )
    monkeypatch.setattr(
        inventory_delete_dialog.httpx,
        "AsyncClient",
        lambda *args, **kwargs: client_stub,
    )

    delete_callbacks: list[str] = []

    async def _on_deleted() -> None:
        delete_callbacks.append("deleted")

    async def exercise() -> None:
        await inventory_delete_dialog.show_delete_confirmation(
            "device-1", "Server Alpha", 1, "token", _on_deleted
        )
        dialog = fake_ui.created["dialog"][0]
        assert dialog.opened is True
        cancel_button = next(
            button for button in fake_ui.created["button"] if button.value == "Cancel"
        )
        await _invoke(cancel_button.click)
        assert dialog.closed is True

    asyncio.run(exercise())

    assert client_stub.calls == [("GET", placements_url)]
    assert delete_callbacks == []


def test_delete_confirmation_confirm_delete_calls_delete_and_refreshes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ui = FakeUI()
    monkeypatch.setattr(inventory_delete_dialog, "ui", fake_ui)

    placements_url = "http://127.0.0.1:8080/api/devices/device-2/placements"
    delete_url = "http://127.0.0.1:8080/api/devices/device-2"
    client_stub = AsyncClientStub(
        [
            httpx.Response(
                200,
                json=[{"view_name": "Core View"}],
                request=httpx.Request("GET", placements_url),
            ),
            httpx.Response(204, request=httpx.Request("DELETE", delete_url)),
        ]
    )
    monkeypatch.setattr(
        inventory_delete_dialog.httpx,
        "AsyncClient",
        lambda *args, **kwargs: client_stub,
    )

    delete_callbacks: list[str] = []

    async def _on_deleted() -> None:
        delete_callbacks.append("deleted")

    async def exercise() -> None:
        await inventory_delete_dialog.show_delete_confirmation(
            "device-2", "Router", 1, "token", _on_deleted
        )
        delete_button = next(
            button
            for button in fake_ui.created["button"]
            if button.value == "Delete device"
        )
        await _invoke(delete_button.click)

    asyncio.run(exercise())

    assert client_stub.calls == [("GET", placements_url), ("DELETE", delete_url)]
    assert delete_callbacks == ["deleted"]


def test_bulk_delete_confirmation_shows_story_copy_and_confirms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ui = FakeUI()
    monkeypatch.setattr(inventory_delete_dialog, "ui", fake_ui)

    confirmed: list[str] = []

    async def _on_confirm() -> None:
        confirmed.append("ok")

    async def exercise() -> None:
        await inventory_delete_dialog.show_bulk_delete_confirmation(
            selected_count=3,
            on_confirm=_on_confirm,
        )
        dialog = fake_ui.created["dialog"][0]
        assert dialog.opened is True

        labels = [str(label.value) for label in fake_ui.created["label"]]
        assert "Delete 3 devices?" in labels
        assert (
            "This cannot be undone. Devices with active connections will be skipped."
            in labels
        )

        confirm_button = next(
            button
            for button in fake_ui.created["button"]
            if button.value == "Delete devices"
        )
        await _invoke(confirm_button.click)
        assert dialog.closed is True

    asyncio.run(exercise())
    assert confirmed == ["ok"]
