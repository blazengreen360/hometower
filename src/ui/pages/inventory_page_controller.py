"""Inventory page controller for HT-031 bulk actions."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import uuid

from nicegui import ui

from src.models.device import DeviceResponseEnriched
from src.models.location import LocationResponse
from src.models.types import DeviceStatus, DeviceType, Role
from src.ui.components.app_shell import app_shell
from src.ui.design.primitives import page_container, primary_button, render_page_intro, secondary_button
from src.ui.pages.inventory_bulk_handlers import InventoryBulkHandlers
from src.ui.pages.inventory_bulk_toolbar import create_bulk_toolbar
from src.ui.pages.inventory_page_controller_helpers import (
    load_inventory_devices,
    load_inventory_placement_data,
    relative_time as _relative_time,
    resolve_selection_after_bulk,
)
from src.ui.pages.inventory_page_runtime import InventoryPageDeps, InventoryPageRuntime, InventoryRuntimeRefs
from src.ui.pages.inventory_delete_dialog import show_bulk_delete_confirmation, show_delete_confirmation
from src.ui.pages.inventory_csv_export import build_inventory_csv, build_inventory_csv_download_js
from src.ui.pages.inventory_filters import load_tag_chips, render_type_chips
from src.ui.pages.inventory_page_runtime_filters import describe_status_scope
from src.ui.pages.inventory_table import build_inventory_rows, create_inventory_table, inventory_table_columns


@dataclass
class InventoryState:
    """Page-local state for filters, selection, and bulk progress."""

    all_devices: list[DeviceResponseEnriched] = field(default_factory=list)
    filtered_devices: list[DeviceResponseEnriched] = field(default_factory=list)
    workspace_id: str | None = None
    search: str = ""
    types: set[DeviceType] = field(default_factory=set)
    statuses: set[DeviceStatus] = field(default_factory=set)
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


def _clear_status_query_param_js() -> str:
    return """
const url = new URL(window.location.href);
url.searchParams.delete('status');
const next = url.searchParams.toString();
window.history.replaceState({}, '', `${url.pathname}${next ? `?${next}` : ''}`);
""".strip()


async def render_inventory_page(
    token: str,
    user_role: Role | None,
    *,
    initial_workspace_id: str | None = None,
    initial_search: str | None = None,
    initial_type: str | None = None,
    initial_status: str | None = None,
) -> None:
    """Render inventory UI and wire HT-031 bulk behavior."""
    can_bulk_edit = user_role in {Role.Contributor, Role.Admin}
    state = InventoryState()
    state.workspace_id = str(initial_workspace_id or "").strip() or None
    state.search = str(initial_search or "").strip()
    if initial_type is not None:
        try:
            state.types.add(DeviceType(initial_type))
        except ValueError:
            pass
    if initial_status is not None:
        try:
            state.statuses.add(DeviceStatus(initial_status))
        except ValueError:
            pass
    refs = InventoryRuntimeRefs()
    runtime = InventoryPageRuntime(
        state=state,
        refs=refs,
        token=token,
        can_bulk_edit=can_bulk_edit,
        can_delete=can_bulk_edit,
        deps=InventoryPageDeps(
            ui=ui,
            relative_time=_relative_time,
            resolve_selection_after_bulk=resolve_selection_after_bulk,
            render_type_chips=render_type_chips,
            build_inventory_rows=build_inventory_rows,
            inventory_table_columns=inventory_table_columns,
            build_inventory_csv=build_inventory_csv,
            build_inventory_csv_download_js=build_inventory_csv_download_js,
            load_inventory_devices=load_inventory_devices,
            load_inventory_placement_data=load_inventory_placement_data,
            load_tag_chips=load_tag_chips,
            show_bulk_delete_confirmation=show_bulk_delete_confirmation,
            show_delete_confirmation=show_delete_confirmation,
            bulk_handlers_factory=InventoryBulkHandlers,
        ),
    )

    with app_shell("Inventory", "/inventory", breadcrumb=["Inventory"]):
        with page_container(ui.column()).classes("flex-1 min-h-0 gap-4"):
            render_page_intro(
                ui,
                "Inventory",
                "Use the Edit action to open the dedicated device editor page.",
            )

            with ui.row().classes("w-full items-center gap-2"):
                refs.search = (
                    ui.input(
                        placeholder="Search by name, IP, or notes...",
                        value=state.search,
                    )
                    .classes("flex-1")
                    .props("debounce=200")
                    .style("background:var(--ht-bg-surface-raised); color:var(--ht-text-primary)")
                    .on_value_change(runtime.on_search)
                )
                primary_button(
                    ui.button(
                        "Export CSV",
                        icon="download",
                        on_click=lambda: asyncio.create_task(runtime.export_csv()),
                    ).props('aria-label="Export inventory CSV"')
                )
            refs.chips_row = ui.row().classes("flex-wrap gap-2 items-center")
            refs.tag_chip_row = ui.row().classes("flex-wrap gap-2 items-center")
            refs.orphan_cb = ui.checkbox("Orphaned only", on_change=runtime.on_orphan_toggle).style(
                "color:var(--ht-text-secondary); font-size:0.875rem"
            )
            show_power_cb = ui.checkbox("Show Power", on_change=runtime.on_show_power_toggle).style(
                "color:var(--ht-text-secondary); font-size:0.875rem"
            )
            show_power_cb.set_value(state.show_power)

            async def _clear_status_scope() -> None:
                state.statuses.clear()
                runtime.apply_filters(clear_selection=True)
                await ui.run_javascript(_clear_status_query_param_js())

            status_scope_text = describe_status_scope(state.statuses)
            with ui.element("div").classes("w-full ht-banner ht-banner-info") as status_scope:
                status_scope.set_visibility(bool(status_scope_text))
                refs.status_scope = status_scope
                with ui.row().classes("w-full flex-wrap items-center justify-between gap-3"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("filter_alt").classes("text-[var(--ht-accent)]")
                        refs.status_scope_label = ui.label(status_scope_text).classes("ht-muted-copy")
                    refs.clear_status_button = secondary_button(
                        ui.button(
                            "Clear status filter",
                            icon="close",
                            on_click=_clear_status_scope,
                        ).props('aria-label="Clear status filter"')
                    )
                    refs.clear_status_button.set_visibility(bool(status_scope_text))

            if can_bulk_edit:
                refs.bulk_toolbar = create_bulk_toolbar(
                    on_add_tag=lambda value: asyncio.create_task(runtime.bulk_handlers.add_tag(value)),
                    on_remove_tag=lambda value: asyncio.create_task(runtime.bulk_handlers.remove_tag(value)),
                    on_set_location=lambda value: asyncio.create_task(runtime.bulk_handlers.set_location(value)),
                    on_delete=lambda: asyncio.create_task(runtime.confirm_bulk_delete()),
                )

            refs.table = create_inventory_table(
                can_bulk_edit=can_bulk_edit,
                on_select=runtime.on_table_select,
                show_power=state.show_power,
            )
            ui.on("inventory_delete", runtime.handle_delete)

            with ui.column().classes("items-center py-8 gap-3") as empty_state:
                empty_state.set_visibility(False)
                refs.empty = empty_state
                ui.label("No devices match - try clearing filters").classes("ht-muted-copy")
                secondary_button(ui.button("Clear filters", on_click=runtime.clear_filters))

    await runtime.load_devices()
    await runtime.load_tag_filters()
    runtime.sync_toolbar()
