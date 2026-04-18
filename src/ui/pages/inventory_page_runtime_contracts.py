"""Shared protocols and refs for the inventory page runtime."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Awaitable, Callable, Protocol, TypeVar
import uuid

from nicegui.element import Element
from nicegui.elements.checkbox import Checkbox
from nicegui.elements.input import Input
from nicegui.elements.table import Table

from src.models.device import DeviceResponseEnriched
from src.models.location import LocationResponse
from src.models.types import DeviceType
from src.ui.pages.inventory_bulk_actions import BulkActionOutcome
from src.ui.pages.inventory_bulk_toolbar import BulkToolbarRefs

T = TypeVar("T")


class UiJavascriptRunner(Protocol):
    def run_javascript(self, code: str, *, timeout: float = 1.0) -> Awaitable[object]:
        ...


class InventoryStateProtocol(Protocol):
    all_devices: list[DeviceResponseEnriched]
    filtered_devices: list[DeviceResponseEnriched]
    search: str
    types: set[DeviceType]
    tag_ids: set[uuid.UUID]
    orphan_ids: set[str]
    placement_counts: dict[str, int]
    orphan_only: bool
    show_power: bool
    selected_ids: set[str]
    bulk_busy: bool
    bulk_action: str | None
    bulk_progress_done: int
    bulk_progress_total: int
    all_tags: list[dict[str, object]]
    locations: list[LocationResponse] | None


class BulkHandlerProtocol(Protocol):
    async def add_tag(self, tag_id_raw: str) -> None:
        ...

    async def remove_tag(self, tag_id_raw: str) -> None:
        ...

    async def set_location(self, location_id_raw: str) -> None:
        ...

    async def delete_selected(self) -> None:
        ...


@dataclass
class InventoryRuntimeRefs:
    table: Table | None = None
    empty: Element | None = None
    search: Input | None = None
    orphan_cb: Checkbox | None = None
    chips_row: Element | None = None
    tag_chip_row: Element | None = None
    bulk_toolbar: BulkToolbarRefs | None = None
    chips: list[dict[str, object]] = field(default_factory=list)
    tag_chips: list[dict[str, object]] = field(default_factory=list)


@dataclass(frozen=True)
class InventoryPageDeps:
    ui: UiJavascriptRunner
    relative_time: Callable[[datetime], str]
    resolve_selection_after_bulk: Callable[[set[str], BulkActionOutcome], set[str]]
    render_type_chips: Callable[..., None]
    build_inventory_rows: Callable[..., list[dict[str, object]]]
    inventory_table_columns: Callable[[bool], list[dict[str, object]]]
    build_inventory_csv: Callable[[list[DeviceResponseEnriched]], str]
    build_inventory_csv_download_js: Callable[[str], str]
    load_inventory_devices: Callable[[str], Awaitable[list[DeviceResponseEnriched]]]
    load_inventory_placement_data: Callable[
        [str, set[uuid.UUID]],
        Awaitable[tuple[set[str], dict[str, int]]],
    ]
    load_tag_chips: Callable[
        [str, Element, set[uuid.UUID], list[dict[str, object]], Callable[[], None]],
        Awaitable[list[dict[str, object]]],
    ]
    show_bulk_delete_confirmation: Callable[..., Awaitable[None]]
    show_delete_confirmation: Callable[..., Awaitable[None]]
    bulk_handlers_factory: Callable[..., BulkHandlerProtocol]


def _require(value: T | None, name: str) -> T:
    if value is None:
        raise RuntimeError(f"Inventory runtime missing required ref: {name}")
    return value


__all__ = [
    "BulkHandlerProtocol",
    "InventoryPageDeps",
    "InventoryRuntimeRefs",
    "InventoryStateProtocol",
    "UiJavascriptRunner",
]