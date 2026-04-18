"""Stateful runtime helpers for the inventory page controller."""
from __future__ import annotations

from typing import Awaitable, Callable

from nicegui.element import Element
from nicegui.elements.table import Table
from nicegui.events import ValueChangeEventArguments

from src.domain import inventory as inventory_domain
from src.models.device import DeviceResponseEnriched
from src.ui.pages.inventory_bulk_actions import BulkActionOutcome, BulkProgress
from src.ui.pages.inventory_bulk_toolbar import BulkToolbarRefs, sync_bulk_toolbar
from src.ui.pages.inventory_page_runtime_contracts import (
    InventoryPageDeps,
    InventoryRuntimeRefs,
    InventoryStateProtocol,
    _require,
)
from src.ui.pages.inventory_page_runtime_filters import InventoryRuntimeFilters


class InventoryPageRuntime:
    def __init__(
        self,
        *,
        state: InventoryStateProtocol,
        refs: InventoryRuntimeRefs,
        token: str,
        can_bulk_edit: bool,
        can_delete: bool,
        deps: InventoryPageDeps,
    ) -> None:
        self._state = state
        self._refs = refs
        self._token = token
        self._can_bulk_edit = can_bulk_edit
        self._can_delete = can_delete
        self._deps = deps
        self._filters = InventoryRuntimeFilters(
            state=state,
            refs=refs,
            deps=deps,
            token=token,
            can_delete=can_delete,
            table_getter=self._table,
            empty_getter=self._empty,
            sync_selected_rows=self._sync_selected_rows,
            sync_toolbar=self.sync_toolbar,
        )
        self.bulk_handlers = deps.bulk_handlers_factory(
            state=state,
            token=token,
            run_bulk=self._run_bulk,
            on_progress=self.on_progress,
        )

    def _table(self) -> Table:
        return _require(self._refs.table, "table")

    def _empty(self) -> Element:
        return _require(self._refs.empty, "empty")

    def _selected_devices(self) -> list[DeviceResponseEnriched]:
        return [d for d in self._state.all_devices if str(d.id) in self._state.selected_ids]

    def _sync_selected_rows(self) -> None:
        if not self._can_bulk_edit:
            return
        selected_rows = [
            row
            for row in self._table().rows
            if isinstance(row, dict) and str(row.get("id", "")) in self._state.selected_ids
        ]
        setattr(self._table(), "selected", selected_rows)
        self._table().update()

    def _sync_table_columns(self) -> None:
        self._table().columns = self._deps.inventory_table_columns(self._state.show_power)
        self._table().update()

    def sync_toolbar(self) -> None:
        if self._refs.bulk_toolbar is None:
            return
        sync_bulk_toolbar(
            self._refs.bulk_toolbar,
            selection_count=len(self._state.selected_ids),
            all_tags=self._state.all_tags,
            common_tags=inventory_domain.get_common_tags(self._selected_devices()),
            locations=self._state.locations,
            busy=self._state.bulk_busy,
            action_label=self._state.bulk_action,
            progress_done=self._state.bulk_progress_done,
            progress_total=self._state.bulk_progress_total,
        )

    def _set_busy(self, action: str, total: int) -> None:
        self._state.bulk_busy = True
        self._state.bulk_action = action
        self._state.bulk_progress_done = 0
        self._state.bulk_progress_total = total
        self.sync_toolbar()

    def _clear_busy(self) -> None:
        self._state.bulk_busy = False
        self._state.bulk_action = None
        self.sync_toolbar()

    def apply_filters(self, *, clear_selection: bool) -> None:
        self._filters.apply_filters(clear_selection=clear_selection)

    def on_search(self, event: ValueChangeEventArguments) -> None:
        self._state.search = event.value or ""
        self.apply_filters(clear_selection=True)

    def on_orphan_toggle(self, event: ValueChangeEventArguments) -> None:
        self._state.orphan_only = bool(event.value)
        self.apply_filters(clear_selection=True)

    def on_show_power_toggle(self, event: ValueChangeEventArguments) -> None:
        self._state.show_power = bool(event.value)
        self._sync_table_columns()
        self.apply_filters(clear_selection=False)

    async def export_csv(self) -> None:
        await self._filters.export_csv()

    def clear_filters(self) -> None:
        self._filters.clear_filters()

    async def load_devices(self) -> None:
        await self._filters.load_devices()

    async def load_tag_filters(self) -> None:
        await self._filters.load_tag_filters()

    def on_table_select(self, event: object) -> None:
        selected_rows = getattr(event, "selection", [])
        if not isinstance(selected_rows, list):
            selected_rows = []
        self._state.selected_ids = {
            str(row.get("id", ""))
            for row in selected_rows
            if isinstance(row, dict) and row.get("id")
        }
        setattr(self._table(), "selected", selected_rows)
        self.sync_toolbar()

    def on_progress(self, progress: BulkProgress) -> None:
        self._state.bulk_progress_done = progress.completed
        self._state.bulk_progress_total = progress.total
        self.sync_toolbar()

    async def _run_bulk(
        self,
        *,
        action: str,
        runner: Callable[
            [list[DeviceResponseEnriched], Callable[[BulkActionOutcome], None]],
            Awaitable[BulkActionOutcome],
        ],
        on_success: Callable[[BulkActionOutcome], None],
    ) -> tuple[BulkActionOutcome, int] | None:
        if self._state.bulk_busy:
            return None
        selected = self._selected_devices()
        if not selected:
            return None

        requested_ids = set(self._state.selected_ids)
        self._set_busy(action, len(selected))
        settled_updates_applied = False

        def _on_settled(item_outcome: BulkActionOutcome) -> None:
            nonlocal settled_updates_applied
            settled_updates_applied = True
            on_success(item_outcome)
            self.apply_filters(clear_selection=False)

        outcome = await runner(selected, _on_settled)
        if not settled_updates_applied:
            on_success(outcome)
        self._state.selected_ids = self._deps.resolve_selection_after_bulk(
            requested_ids,
            outcome,
        )
        self._clear_busy()
        self.apply_filters(clear_selection=False)
        return outcome, len(selected)

    async def confirm_bulk_delete(self) -> None:
        await self._deps.show_bulk_delete_confirmation(
            selected_count=len(self._state.selected_ids),
            on_confirm=self.bulk_handlers.delete_selected,
        )

    async def handle_delete(self, event: object) -> None:
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
        await self._deps.show_delete_confirmation(
            device_id,
            str(args.get("name", "")),
            placement_count,
            self._token,
            self.load_devices,
        )


__all__ = ["InventoryPageDeps", "InventoryPageRuntime", "InventoryRuntimeRefs"]