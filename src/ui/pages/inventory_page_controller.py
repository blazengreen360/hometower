"""Inventory page controller for HT-031 bulk actions."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Awaitable, Callable, cast
import uuid

import httpx
from nicegui import ui
from nicegui.element import Element
from nicegui.elements.checkbox import Checkbox
from nicegui.elements.input import Input
from nicegui.elements.table import Table
from nicegui.events import ValueChangeEventArguments

from src.domain import inventory as inventory_domain
from src.models.device import DeviceResponseEnriched
from src.models.location import LocationResponse
from src.models.types import DeviceType, Role
from src.ui.components.app_shell import app_shell
from src.ui.pages.inventory_bulk_actions import BulkActionOutcome, BulkProgress
from src.ui.pages.inventory_bulk_handlers import InventoryBulkHandlers
from src.ui.pages.inventory_bulk_toolbar import (
    BulkToolbarRefs,
    create_bulk_toolbar,
    sync_bulk_toolbar,
)
from src.ui.pages.inventory_page_controller_helpers import (
    relative_time as _relative_time,
    resolve_selection_after_bulk,
)
from src.ui.pages.inventory_delete_dialog import (
    show_bulk_delete_confirmation,
    show_delete_confirmation,
)
from src.ui.pages.inventory_filters import load_tag_chips, render_type_chips
from src.ui.pages.inventory_table import (
    build_inventory_rows,
    create_inventory_table,
    inventory_table_columns,
)
from src.utils.logger import logger
from src.utils.settings import settings

@dataclass
class InventoryState:
    """Page-local state for filters, selection, and bulk progress."""

    all_devices: list[DeviceResponseEnriched] = field(default_factory=list)
    filtered_devices: list[DeviceResponseEnriched] = field(default_factory=list)
    search: str = ""
    types: set[DeviceType] = field(default_factory=set)
    tag_ids: set[uuid.UUID] = field(default_factory=set)
    orphan_ids: set[str] = field(default_factory=set)
    placement_counts: dict[str, int] = field(default_factory=dict)
    orphan_only: bool = False
    show_power: bool = False
    selected_ids: set[str] = field(default_factory=set)
    bulk_busy: bool = False
    bulk_action: str | None = None
    bulk_progress_done: int = 0
    bulk_progress_total: int = 0
    all_tags: list[dict[str, object]] = field(default_factory=list)
    locations: list[LocationResponse] | None = None

async def render_inventory_page(token: str, user_role: Role | None) -> None:
    """Render inventory UI and wire HT-031 bulk behavior."""
    can_bulk_edit = user_role in {Role.Contributor, Role.Admin}
    can_delete = can_bulk_edit
    state = InventoryState()
    refs: dict[str, object] = {"chips": [], "tag_chips": []}

    def _table() -> Table:
        return cast(Table, refs["table"])

    def _toolbar() -> BulkToolbarRefs | None:
        return cast(BulkToolbarRefs | None, refs.get("bulk_toolbar"))

    def _selected_devices() -> list[DeviceResponseEnriched]:
        return [d for d in state.all_devices if str(d.id) in state.selected_ids]

    def _sync_selected_rows() -> None:
        if not can_bulk_edit:
            return
        selected_rows = [
            row
            for row in _table().rows
            if isinstance(row, dict) and str(row.get("id", "")) in state.selected_ids
        ]
        setattr(_table(), "selected", selected_rows)
        _table().update()

    def _sync_table_columns() -> None:
        _table().columns = inventory_table_columns(state.show_power)
        _table().update()

    def _sync_toolbar() -> None:
        toolbar = _toolbar()
        if toolbar is None:
            return
        common_tags = inventory_domain.get_common_tags(_selected_devices())
        sync_bulk_toolbar(
            toolbar,
            selection_count=len(state.selected_ids),
            all_tags=state.all_tags,
            common_tags=common_tags,
            locations=state.locations,
            busy=state.bulk_busy,
            action_label=state.bulk_action,
            progress_done=state.bulk_progress_done,
            progress_total=state.bulk_progress_total,
        )

    def _set_busy(action: str, total: int) -> None:
        state.bulk_busy = True
        state.bulk_action = action
        state.bulk_progress_done = 0
        state.bulk_progress_total = total
        _sync_toolbar()

    def _clear_busy() -> None:
        state.bulk_busy = False
        state.bulk_action = None
        _sync_toolbar()

    def _apply_filters(*, clear_selection: bool) -> None:
        filtered = inventory_domain.filter_devices(
            state.all_devices,
            state.search,
            state.types,
            state.tag_ids,
        )
        if state.orphan_only:
            filtered = [d for d in filtered if str(d.id) in state.orphan_ids]
        state.filtered_devices = filtered

        rows = build_inventory_rows(
            filtered,
            _relative_time,
            orphan_ids=state.orphan_ids,
            can_delete=can_delete,
            placement_counts=state.placement_counts,
        )
        _table().update_rows(rows, clear_selection=clear_selection)

        if clear_selection:
            state.selected_ids.clear()
            setattr(_table(), "selected", [])
        else:
            visible_ids = {
                str(row.get("id", ""))
                for row in rows
                if isinstance(row, dict) and row.get("id")
            }
            state.selected_ids.intersection_update(visible_ids)
            _sync_selected_rows()

        has_filter = bool(state.search or state.types or state.tag_ids or state.orphan_only)
        cast(Element, refs["empty"]).set_visibility(len(rows) == 0 and has_filter)
        _sync_toolbar()

    def _on_search(e: ValueChangeEventArguments) -> None:
        state.search = e.value or ""
        _apply_filters(clear_selection=True)

    def _on_orphan_toggle(e: ValueChangeEventArguments) -> None:
        state.orphan_only = bool(e.value)
        _apply_filters(clear_selection=True)

    def _on_show_power_toggle(e: ValueChangeEventArguments) -> None:
        state.show_power = bool(e.value)
        _sync_table_columns()
        _apply_filters(clear_selection=False)

    def _clear_filters() -> None:
        state.search = ""
        state.types.clear()
        state.tag_ids.clear()
        state.orphan_only = False
        cast(Input, refs["search"]).set_value("")
        cast(Checkbox, refs["orphan_cb"]).set_value(False)

        for meta in cast(list[dict[str, object]], refs["chips"]):
            meta["active"] = False
            cast(Element, meta["chip"]).props('color="grey-8" text-color="white"')
        for meta in cast(list[dict[str, object]], refs["tag_chips"]):
            meta["active"] = False
            cast(Element, meta["chip"]).props('color="grey-8" text-color="white"')
        _apply_filters(clear_selection=True)

    def _make_chip_toggle(dtype: DeviceType, color: str) -> Callable[[], None]:
        def _toggle() -> None:
            metas = cast(list[dict[str, object]], refs["chips"])
            meta = next((m for m in metas if m["dtype"] == dtype), None)
            if meta is None:
                return
            active = not bool(meta["active"])
            meta["active"] = active
            if active:
                state.types.add(dtype)
                cast(Element, meta["chip"]).props(f'color="{color}" text-color="white"')
            else:
                state.types.discard(dtype)
                cast(Element, meta["chip"]).props('color="grey-8" text-color="white"')
            _apply_filters(clear_selection=True)

        return _toggle

    def _render_type_chips() -> None:
        helper_state: dict[str, object] = {"all": state.all_devices, "types": state.types}
        helper_refs: dict[str, object] = {
            "chips_row": cast(Element, refs["chips_row"]),
            "chips": cast(list[dict[str, object]], refs["chips"]),
        }
        render_type_chips(
            helper_state,
            helper_refs,
            _make_chip_toggle,
            lambda: _apply_filters(clear_selection=True),
        )
        state.types = cast(set[DeviceType], helper_state["types"])
        refs["chips"] = helper_refs["chips"]

    async def _load_orphan_data() -> None:
        all_ids = {str(device.id) for device in state.all_devices}
        try:
            async with httpx.AsyncClient() as http:
                response = await http.get(
                    f"{settings.api_base_url}/api/devices/placed-ids",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10.0,
                )
            if response.status_code == 200:
                placed = set(response.json())
                state.orphan_ids = all_ids.difference(placed)
                state.placement_counts = {did: (1 if did in placed else 0) for did in all_ids}
        except Exception as exc:
            logger.error("Orphan data load error: {}", str(exc))

    async def _load_devices() -> None:
        try:
            async with httpx.AsyncClient() as http:
                response = await http.get(
                    f"{settings.api_base_url}/api/devices/",
                    params={"include": "location,tags,services,networks", "limit": "1000"},
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10.0,
                )
            if response.status_code != 200:
                logger.error("Inventory load failed: status={}", response.status_code)
                return
            state.all_devices = [
                DeviceResponseEnriched.model_validate(item)
                for item in response.json().get("items", [])
            ]
            await _load_orphan_data()
            _render_type_chips()
            _apply_filters(clear_selection=True)
        except Exception as exc:
            logger.error("Inventory load error: {}", str(exc))

    def _on_table_select(event: object) -> None:
        selected_rows = getattr(event, "selection", [])
        if not isinstance(selected_rows, list):
            selected_rows = []
        state.selected_ids = {
            str(row.get("id", ""))
            for row in selected_rows
            if isinstance(row, dict) and row.get("id")
        }
        setattr(_table(), "selected", selected_rows)
        _sync_toolbar()

    def _on_progress(progress: BulkProgress) -> None:
        state.bulk_progress_done = progress.completed
        state.bulk_progress_total = progress.total
        _sync_toolbar()

    async def _run_bulk(
        *,
        action: str,
        runner: Callable[
            [list[DeviceResponseEnriched], Callable[[BulkActionOutcome], None]],
            Awaitable[BulkActionOutcome],
        ],
        on_success: Callable[[BulkActionOutcome], None],
    ) -> tuple[BulkActionOutcome, int] | None:
        if state.bulk_busy:
            return None
        selected = _selected_devices()
        if not selected:
            return None

        requested_ids = set(state.selected_ids)
        _set_busy(action, len(selected))
        settled_updates_applied = False

        def _on_settled(item_outcome: BulkActionOutcome) -> None:
            nonlocal settled_updates_applied
            settled_updates_applied = True
            on_success(item_outcome)
            _apply_filters(clear_selection=False)

        outcome = await runner(selected, _on_settled)
        if not settled_updates_applied:
            on_success(outcome)
        state.selected_ids = resolve_selection_after_bulk(requested_ids, outcome)
        _clear_busy()
        _apply_filters(clear_selection=False)
        return outcome, len(selected)

    bulk_handlers = InventoryBulkHandlers(
        state=state,
        token=token,
        run_bulk=_run_bulk,
        on_progress=_on_progress,
    )

    async def _confirm_bulk_delete() -> None:
        await show_bulk_delete_confirmation(
            selected_count=len(state.selected_ids),
            on_confirm=bulk_handlers.delete_selected,
        )

    async def _handle_delete(event: object) -> None:
        args = getattr(event, "args", None)
        if not isinstance(args, dict):
            return
        device_id = str(args.get("id", ""))
        if not device_id:
            return
        try:
            placement_count = int(args.get("placement_count", 0) or 0)
        except (TypeError, ValueError):
            placement_count = 0
        await show_delete_confirmation(
            device_id,
            str(args.get("name", "")),
            placement_count,
            token,
            _load_devices,
        )

    with app_shell("Inventory", "/inventory", breadcrumb=["Inventory"]):
        ui.label("Inventory").style("font-size:1.25rem; font-weight:600; color:var(--ht-text-primary)")
        ui.label("Use the Edit action to open the dedicated device editor page.").style(
            "font-size:0.85rem; color:var(--ht-text-secondary)"
        )

        refs["search"] = (
            ui.input(placeholder="Search by name, IP, or notes...")
            .classes("w-full")
            .props("debounce=200")
            .style("background:var(--ht-bg-surface-raised); color:var(--ht-text-primary)")
            .on_value_change(_on_search)
        )
        refs["chips_row"] = ui.row().classes("flex-wrap gap-2 items-center")
        refs["tag_chip_row"] = ui.row().classes("flex-wrap gap-2 items-center")
        refs["orphan_cb"] = ui.checkbox("Orphaned only", on_change=_on_orphan_toggle).style(
            "color:var(--ht-text-secondary); font-size:0.875rem"
        )
        show_power_cb = ui.checkbox("Show Power", on_change=_on_show_power_toggle).style(
            "color:var(--ht-text-secondary); font-size:0.875rem"
        )
        show_power_cb.set_value(state.show_power)
        refs["show_power_cb"] = show_power_cb

        if can_bulk_edit:
            refs["bulk_toolbar"] = create_bulk_toolbar(
                on_add_tag=lambda value: asyncio.create_task(bulk_handlers.add_tag(value)),
                on_remove_tag=lambda value: asyncio.create_task(bulk_handlers.remove_tag(value)),
                on_set_location=lambda value: asyncio.create_task(bulk_handlers.set_location(value)),
                on_delete=lambda: asyncio.create_task(_confirm_bulk_delete()),
            )

        refs["table"] = create_inventory_table(
            can_bulk_edit=can_bulk_edit,
            on_select=_on_table_select,
            show_power=state.show_power,
        )
        ui.on("inventory_delete", _handle_delete)

        with ui.column().classes("items-center py-8 gap-3") as empty_state:
            empty_state.set_visibility(False)
            refs["empty"] = empty_state
            ui.label("No devices match - try clearing filters").style("color:var(--ht-text-secondary)")
            ui.button("Clear filters", on_click=_clear_filters).style(
                "background:var(--ht-accent); color:var(--ht-text-on-accent)"
            )

    await _load_devices()
    state.all_tags = await load_tag_chips(
        token,
        cast(Element, refs["tag_chip_row"]),
        state.tag_ids,
        cast(list[dict[str, object]], refs["tag_chips"]),
        lambda: _apply_filters(clear_selection=True),
    )
    _sync_toolbar()
