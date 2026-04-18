"""Filter, chip, and loading helpers for the inventory page runtime."""
from __future__ import annotations

from typing import Callable, cast

from nicegui.element import Element
from nicegui.elements.table import Table

from src.domain import inventory as inventory_domain
from src.models.types import DeviceType
from src.ui.components.toast import show_toast
from src.ui.design.primitives import set_filter_chip_state
from src.ui.pages.inventory_page_runtime_contracts import (
    InventoryPageDeps,
    InventoryRuntimeRefs,
    InventoryStateProtocol,
    _require,
)


class InventoryRuntimeFilters:
    def __init__(
        self,
        *,
        state: InventoryStateProtocol,
        refs: InventoryRuntimeRefs,
        deps: InventoryPageDeps,
        token: str,
        can_delete: bool,
        table_getter: Callable[[], Table],
        empty_getter: Callable[[], Element],
        sync_selected_rows: Callable[[], None],
        sync_toolbar: Callable[[], None],
    ) -> None:
        self._state = state
        self._refs = refs
        self._deps = deps
        self._token = token
        self._can_delete = can_delete
        self._table = table_getter
        self._empty = empty_getter
        self._sync_selected_rows = sync_selected_rows
        self._sync_toolbar = sync_toolbar

    def apply_filters(self, *, clear_selection: bool) -> None:
        filtered = inventory_domain.filter_devices(
            self._state.all_devices,
            self._state.search,
            self._state.types,
            self._state.tag_ids,
        )
        if self._state.orphan_only:
            filtered = [device for device in filtered if str(device.id) in self._state.orphan_ids]
        self._state.filtered_devices = filtered

        rows = self._deps.build_inventory_rows(
            filtered,
            self._deps.relative_time,
            orphan_ids=self._state.orphan_ids,
            can_delete=self._can_delete,
            placement_counts=self._state.placement_counts,
        )
        self._table().update_rows(rows, clear_selection=clear_selection)

        if clear_selection:
            self._state.selected_ids.clear()
            setattr(self._table(), "selected", [])
        else:
            visible_ids = {
                str(row.get("id", ""))
                for row in rows
                if isinstance(row, dict) and row.get("id")
            }
            self._state.selected_ids.intersection_update(visible_ids)
            self._sync_selected_rows()

        has_filter = bool(
            self._state.search
            or self._state.types
            or self._state.tag_ids
            or self._state.orphan_only
        )
        self._empty().set_visibility(len(rows) == 0 and has_filter)
        self._sync_toolbar()

    async def export_csv(self) -> None:
        if not self._state.filtered_devices:
            show_toast(type="info", title="No devices to export")
            return
        csv_payload = self._deps.build_inventory_csv(self._state.filtered_devices)
        await self._deps.ui.run_javascript(self._deps.build_inventory_csv_download_js(csv_payload))
        show_toast(type="success", title=f"Exported {len(self._state.filtered_devices)} devices")

    def clear_filters(self) -> None:
        self._state.search = ""
        self._state.types.clear()
        self._state.tag_ids.clear()
        self._state.orphan_only = False
        _require(self._refs.search, "search").set_value("")
        _require(self._refs.orphan_cb, "orphan_cb").set_value(False)
        self._reset_chip_group(self._refs.chips, "chip meta")
        self._reset_chip_group(self._refs.tag_chips, "tag chip meta")
        self.apply_filters(clear_selection=True)

    def make_chip_toggle(self, dtype: DeviceType, color: str) -> Callable[[], None]:
        def _toggle() -> None:
            meta = next((item for item in self._refs.chips if item["dtype"] == dtype), None)
            if meta is None:
                return
            active = not bool(meta["active"])
            meta["active"] = active
            if active:
                self._state.types.add(dtype)
            else:
                self._state.types.discard(dtype)
            set_filter_chip_state(_require(meta.get("chip"), "chip meta"), color, active)
            self.apply_filters(clear_selection=True)

        return _toggle

    def render_type_chips(self) -> None:
        helper_state: dict[str, object] = {
            "all": self._state.all_devices,
            "types": self._state.types,
        }
        helper_refs: dict[str, object] = {
            "chips_row": _require(self._refs.chips_row, "chips_row"),
            "chips": self._refs.chips,
        }
        self._deps.render_type_chips(
            helper_state,
            helper_refs,
            self.make_chip_toggle,
            lambda: self.apply_filters(clear_selection=True),
        )
        self._state.types = cast(set[DeviceType], helper_state["types"])
        self._refs.chips = cast(list[dict[str, object]], helper_refs["chips"])

    async def load_devices(self) -> None:
        self._state.all_devices = await self._deps.load_inventory_devices(self._token)
        self._state.orphan_ids, self._state.placement_counts = (
            await self._deps.load_inventory_placement_data(
                self._token,
                {device.id for device in self._state.all_devices},
            )
        )
        self.render_type_chips()
        self.apply_filters(clear_selection=True)

    async def load_tag_filters(self) -> None:
        self._state.all_tags = await self._deps.load_tag_chips(
            self._token,
            _require(self._refs.tag_chip_row, "tag_chip_row"),
            self._state.tag_ids,
            self._refs.tag_chips,
            lambda: self.apply_filters(clear_selection=True),
        )

    def _reset_chip_group(self, chips: list[dict[str, object]], required_name: str) -> None:
        for meta in chips:
            meta["active"] = False
            set_filter_chip_state(
                _require(meta.get("chip"), required_name),
                str(meta.get("color", "var(--ht-accent)")),
                False,
            )