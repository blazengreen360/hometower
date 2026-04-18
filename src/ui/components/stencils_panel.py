"""Inventory stencils panel — drag published devices onto the canvas (HT-049).

Renders a collapsible panel with search, type filter, and draggable device
rows.  Already-placed devices are greyed out with a "Placed" badge.
"""
import json

from nicegui import ui

from src.models.types import DeviceType
from src.ui.components.stencils_panel_js import STENCIL_DRAG_JS, STENCIL_PANEL_JS
from src.ui.design.tokens import DEVICE_TYPE_COLORS, DEVICE_TYPE_ICONS


_STENCIL_WIDTH = "260px"

StencilDevice = dict[str, str | int]


# ── Pure helper functions (tested independently) ─────────────────────────


def filter_stencil_devices(
    devices: list[StencilDevice],
    search: str,
    type_filter: str,
) -> list[StencilDevice]:
    """Filter device list by search text and device type.

    Args:
        devices: List of device dicts with keys: id, name, type, ip.
        search: Case-insensitive substring to match against device name.
        type_filter: Exact DeviceType value (e.g. "Server"), or "" for all.

    Returns:
        Filtered list of device dicts.
    """
    result = devices
    if search:
        lower_search = search.lower()
        result = [d for d in result if lower_search in str(d.get("name", "")).lower()]
    if type_filter:
        result = [d for d in result if str(d.get("type", "")) == type_filter]
    return result


def compute_placed_ids(elements: list[dict[str, object]]) -> set[str]:
    """Extract non-draft, non-edge node IDs from Cytoscape elements.

    These IDs represent devices already placed on the current canvas.
    """
    placed: set[str] = set()
    for elem in elements:
        if elem.get("group") == "edges":
            continue
        data = elem.get("data")
        if not isinstance(data, dict):
            continue
        nid = str(data.get("id", ""))
        if not nid:
            continue
        # Skip drafts
        if nid.startswith("draft-") or data.get("draft"):
            continue
        placed.add(nid)
    return placed


# ── CSS for stencil panel ────────────────────────────────────────────────

_STENCIL_CSS = """
<style>
.ht-stencil-row { transition: all var(--ht-transition-fast); }
.ht-stencil-row:hover:not(.ht-stencil-placed) {
    border-color: var(--ht-accent) !important;
    transform: translateX(2px);
    box-shadow: var(--ht-shadow-sm);
}
.ht-stencil-placed {
    opacity: 0.45;
    cursor: default !important;
    pointer-events: none;
}
.ht-stencil-placed .ht-placed-badge { display: inline-block !important; }
#ht-stencils-panel { transition: width var(--ht-transition-fast); }
.ht-stencils-collapsed { width: 36px !important; min-width: 36px; padding: 12px 2px !important; }
.ht-stencils-collapsed .ht-stencil-content { display: none !important; }
</style>
"""


# ── Render functions ─────────────────────────────────────────────────────


def render_stencils_panel(
    devices: list[StencilDevice],
    placed_ids: set[str],
) -> None:
    """Render the inventory stencils panel with search, filter, and device rows.

    Device rows are rendered client-side via JS virtual scroll for performance
    with large inventories.  Placed-state updates are event-driven (no reload).

    Args:
        devices: Full device list (id, name, type, ip).
        placed_ids: Set of device IDs already on the current canvas.
    """
    ui.add_body_html(f"<script>{STENCIL_DRAG_JS}</script>")
    ui.add_body_html(f"<script>{STENCIL_PANEL_JS}</script>")
    ui.add_head_html(_STENCIL_CSS)

    with ui.column().style(
        f"width: {_STENCIL_WIDTH}; background: var(--ht-bg-sidebar);"
        " border-right: 1px solid var(--ht-border);"
        " padding: 12px 10px; gap: 6px; overflow: hidden;"
    ).props('id="ht-stencils-panel"'):
        # Header with collapse toggle
        with ui.row().style(
            "align-items: center; gap: 6px; padding: 2px 4px;"
            " margin-bottom: 2px; width: 100%;"
        ):
            ui.icon("inventory_2").style(
                "color: var(--ht-text-secondary); font-size: 1rem;"
            ).classes("ht-stencil-content")
            ui.label("Inventory").style(
                "color: var(--ht-text-primary); font-size: 0.875rem;"
                " font-weight: 600; letter-spacing: 0.03em; flex: 1;"
            ).classes("ht-stencil-content")
            ui.button(icon="chevron_left").props(
                'flat dense round size="sm" id="ht-stencil-collapse-btn"'
            ).style("color: var(--ht-text-secondary);").on(
                "click", lambda: ui.run_javascript("htStencilToggle()")
            )

        # Content wrapper (hidden when collapsed)
        with ui.column().style(
            "gap: 6px; width: 100%;"
        ).classes("ht-stencil-content"):
            # Search box
            search_input = ui.input(placeholder="Search devices...").props(
                'dense outlined'
            ).style("width: 100%; font-size: 0.8rem;")

            # Type filter
            type_options = [""] + [dt.value for dt in DeviceType]
            type_select = ui.select(
                options=type_options,
                value="",
                label="Filter by type",
            ).props('dense outlined').style("width: 100%; font-size: 0.8rem;")

            # Device list (JS-rendered with virtual scroll)
            with ui.scroll_area().style(
                "flex: 1; min-height: 120px; width: 100%;"
            ):
                ui.element("div").props('id="ht-stencil-list"')

        # Wire search/filter to JS renderer
        def _trigger_filter() -> None:
            s = json.dumps(search_input.value or "")
            t = json.dumps(type_select.value or "")
            ui.run_javascript(f"htStencilFilter({s},{t})")

        search_input.on("update:model-value", lambda _: _trigger_filter())
        type_select.on("update:model-value", lambda _: _trigger_filter())

        # Initialize JS virtual list
        colors_json = json.dumps({
            dt.value: c for dt, c in DEVICE_TYPE_COLORS.items()
        })
        icons_json = json.dumps({
            dt.value: i for dt, i in DEVICE_TYPE_ICONS.items()
        })
        ui.run_javascript(
            f"htStencilInit('ht-stencil-list',"
            f"{json.dumps(devices)},{json.dumps(list(placed_ids))},"
            f"{colors_json},{icons_json})"
        )
