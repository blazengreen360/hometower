"""Shared client-side table patterns for HT-081."""

from collections.abc import Callable
from typing import Protocol

from nicegui.elements.table import Table
from typing_extensions import Self

from src.ui.design.primitives import table_surface

DEFAULT_ROWS_PER_PAGE = 25
ROWS_PER_PAGE_OPTIONS = [10, 25, 50, 100]


class SupportsStyledInput(Protocol):
    """Protocol for the styled input methods used by the search helper."""

    def props(self, value: str) -> Self: ...
    def classes(self, value: str) -> Self: ...


class SupportsTableUi(Protocol):
    """Protocol for the subset of NiceGUI ui used by the shared helpers."""

    def table(
        self,
        *,
        columns: list[dict[str, object]],
        rows: list[dict[str, object]],
        row_key: str,
        pagination: dict[str, object],
    ) -> Table: ...

    def input(
        self,
        *,
        placeholder: str,
        on_change: Callable[[object], None],
    ) -> SupportsStyledInput: ...


def standard_table_pagination(sort_by: str, descending: bool = False) -> dict[str, object]:
    """Return the default client-side pagination config for data tables."""
    return {
        "rowsPerPage": DEFAULT_ROWS_PER_PAGE,
        "sortBy": sort_by,
        "descending": descending,
    }


def create_standard_table(
    *,
    ui_module: SupportsTableUi,
    columns: list[dict[str, object]],
    row_key: str,
    sort_by: str,
    descending: bool = False,
) -> Table:
    """Create a themed NiceGUI table with HT-081 pagination defaults."""
    table = table_surface(
        ui_module.table(
            columns=columns,
            rows=[],
            row_key=row_key,
            pagination=standard_table_pagination(sort_by, descending),
        )
    )
    table.props(f'rows-per-page-options={ROWS_PER_PAGE_OPTIONS} binary-state-sort')
    return table


def render_table_search_input(
    *,
    ui_module: SupportsTableUi,
    placeholder: str,
    on_change: Callable[[str], None],
) -> SupportsStyledInput:
    """Render the standard table search field."""

    def _handle_change(event: object) -> None:
        on_change(str(getattr(event, "value", "") or ""))

    return ui_module.input(
        placeholder=placeholder,
        on_change=_handle_change,
    ).props("outlined dense clearable").classes("w-full max-w-full sm:max-w-[240px]")