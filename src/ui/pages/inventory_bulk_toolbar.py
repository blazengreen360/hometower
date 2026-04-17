"""Inventory bulk toolbar UI helpers (HT-031)."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from nicegui import ui
from nicegui.elements.button import Button
from nicegui.elements.label import Label
from nicegui.elements.progress import LinearProgress
from nicegui.elements.row import Row
from nicegui.elements.select import Select

from src.domain.inventory import CommonTagOption
from src.models.location import LocationResponse


@dataclass(frozen=True)
class BulkToolbarRefs:
    """Element references used to sync the inventory bulk toolbar."""

    root: Row
    count_label: Label
    add_tag_select: Select
    remove_tag_select: Select
    location_select: Select
    delete_button: Button
    progress_row: Row
    progress_bar: LinearProgress
    progress_label: Label
    helper_label: Label


def create_bulk_toolbar(
    *,
    on_add_tag: Callable[[str], object],
    on_remove_tag: Callable[[str], object],
    on_set_location: Callable[[str], object],
    on_delete: Callable[[], object],
) -> BulkToolbarRefs:
    """Render and return the bulk toolbar controls."""
    with ui.row().classes("w-full items-center q-pa-sm gap-3 ht-bulk-toolbar") as root:
        count_label = ui.label("0 selected").style("font-weight:600")

        add_tag_select = ui.select({}, label="Add Tag", value=None).classes("w-48")
        add_tag_select.props('dense clearable aria-label="Add tag to selected devices"')
        add_tag_select.on_value_change(lambda e: on_add_tag(str(e.value or "")))

        remove_tag_select = ui.select({}, label="Remove Tag", value=None).classes("w-48")
        remove_tag_select.props('dense clearable aria-label="Remove common tag from selected devices"')
        remove_tag_select.on_value_change(lambda e: on_remove_tag(str(e.value or "")))

        location_select = ui.select({}, label="Set Location", value=None).classes("w-48")
        location_select.props('dense clearable aria-label="Set location for selected devices"')
        location_select.on_value_change(lambda e: on_set_location(str(e.value or "")))

        delete_button = ui.button("Delete", on_click=on_delete).props(
            'color=negative aria-label="Delete selected devices"'
        )

    with ui.row().classes("w-full items-center gap-2") as progress_row:
        progress_bar = ui.linear_progress(value=0.0).classes("w-64")
        progress_label = ui.label("").style("font-size:0.85rem")

    helper_label = ui.label("").style("font-size:0.82rem; color:var(--ht-text-secondary)")
    root.set_visibility(False)
    progress_row.set_visibility(False)

    return BulkToolbarRefs(
        root=root,
        count_label=count_label,
        add_tag_select=add_tag_select,
        remove_tag_select=remove_tag_select,
        location_select=location_select,
        delete_button=delete_button,
        progress_row=progress_row,
        progress_bar=progress_bar,
        progress_label=progress_label,
        helper_label=helper_label,
    )


def sync_bulk_toolbar(
    refs: BulkToolbarRefs,
    *,
    selection_count: int,
    all_tags: list[dict[str, object]],
    common_tags: list[CommonTagOption],
    locations: list[LocationResponse] | None,
    busy: bool,
    action_label: str | None,
    progress_done: int,
    progress_total: int,
) -> None:
    """Sync visual state, options, and progress for the bulk toolbar."""
    refs.root.set_visibility(selection_count > 0)
    refs.progress_row.set_visibility(selection_count > 0 and busy)

    if selection_count <= 0:
        refs.count_label.set_text("0 selected")
        refs.helper_label.set_text("")
        return

    refs.count_label.set_text(f"{selection_count} selected")

    add_tag_options: dict[str, str] = {
        str(tag.get("id")): str(tag.get("name", ""))
        for tag in all_tags
        if tag.get("id") is not None and tag.get("name") is not None
    }
    refs.add_tag_select.set_options(add_tag_options, value=None)

    remove_tag_options: dict[str, str] = {
        str(tag.id): tag.name
        for tag in common_tags
    }
    refs.remove_tag_select.set_options(remove_tag_options, value=None)

    location_options: dict[str, str] = {
        str(location.id): location.name
        for location in (locations or [])
    }
    refs.location_select.set_options(location_options, value=None)

    controls = [
        refs.add_tag_select,
        refs.remove_tag_select,
        refs.location_select,
        refs.delete_button,
    ]
    for control in controls:
        control.props("disable" if busy else "disable=false")

    if common_tags:
        refs.helper_label.set_text("")
    else:
        refs.helper_label.set_text("No common tags across selection")

    if busy:
        total = progress_total if progress_total > 0 else 1
        refs.progress_bar.set_value(progress_done / total)
        label = action_label or "Running"
        refs.progress_label.set_text(f"{label} {progress_done} of {progress_total}")
    else:
        refs.progress_bar.set_value(0.0)
        refs.progress_label.set_text("")
