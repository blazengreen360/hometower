"""Device palette sidebar — draggable device type cards for the topology canvas.

Each card uses HTML5 drag-and-drop: dragstart sets dataTransfer with the
device type string; the canvas drop handler reads it to create a new node.
"""
from nicegui import ui

from src.models.types import DeviceType
from src.ui.components.device_type_options import get_creatable_device_types
from src.ui.design.tokens import (
    COLOR_PRIMARY,
    DEVICE_TYPE_COLORS,
    DEVICE_TYPE_ICONS,
)

_DRAG_SCRIPT = """
function htPaletteCardDrag(el, deviceType) {
    el.setAttribute('draggable', 'true');
    el.addEventListener('dragstart', function(e) {
        e.dataTransfer.setData('deviceType', deviceType);
        e.dataTransfer.effectAllowed = 'copy';
        el.style.opacity = '0.5';
    });
    el.addEventListener('dragend', function() {
        el.style.opacity = '1';
    });
}
"""

_PALETTE_WIDTH = "184px"


def render_palette() -> None:
    """Render the device type palette sidebar."""
    ui.add_body_html(f"<script>{_DRAG_SCRIPT}</script>")
    _inject_palette_hover_style()

    with ui.column().style(
        f"width: {_PALETTE_WIDTH}; background: var(--ht-bg-sidebar);"
        " border-right: 1px solid var(--ht-border);"
        " padding: 12px 10px; gap: 6px; overflow-y: auto;"
    ):
        # Header
        with ui.row().style(
            "align-items: center; gap: 6px; padding: 2px 4px; margin-bottom: 2px;"
        ):
            ui.icon("drag_indicator").style(
                "color: var(--ht-text-secondary); font-size: 1rem;"
            )
            ui.label("Device Tools").style(
                "color: var(--ht-text-primary); font-size: 0.875rem;"
                " font-weight: 600; letter-spacing: 0.03em;"
            )

        # Hint text
        ui.label("Drag onto canvas").style(
            "color: var(--ht-text-secondary); font-size: 0.7rem;"
            " padding: 0 4px; margin-bottom: 4px;"
        )

        for device_type in get_creatable_device_types():
            _render_palette_card(device_type)


def _render_palette_card(device_type: DeviceType) -> None:
    """Render a single draggable palette card with icon and accent color."""
    card_id = f"palette-{device_type.value.lower()}"
    accent = DEVICE_TYPE_COLORS.get(device_type, COLOR_PRIMARY)
    icon_name = DEVICE_TYPE_ICONS.get(device_type, "devices")

    with ui.element("div").props(f'id="{card_id}"').style(
        "display: flex; align-items: center; gap: 8px;"
        " padding: 6px 8px; border-radius: var(--ht-radius-input); cursor: grab;"
        " background: var(--ht-bg-surface-raised);"
        " border: 1px solid var(--ht-border);"
        " user-select: none; transition: all var(--ht-transition-fast);"
    ).classes("ht-palette-card"):
        # Icon chip
        with ui.element("div").style(
            f"width: 28px; height: 28px; border-radius: 6px;"
            f" background: {accent}18; display: flex;"
            " align-items: center; justify-content: center; flex-shrink: 0;"
        ):
            ui.icon(icon_name).style(
                f"color: {accent}; font-size: 1rem;"
            )
        ui.label(device_type.value).style(
            "color: var(--ht-text-primary); font-size: 0.875rem;"
            " font-weight: 500; white-space: nowrap;"
        )

    ui.run_javascript(
        f"htPaletteCardDrag(document.getElementById('{card_id}'), '{device_type.value}')"
    )


# Inject hover style once (scoped via class)
_HOVER_CSS = """
<style>
.ht-palette-card:hover {
    border-color: var(--ht-accent) !important;
    background: var(--ht-bg-surface-raised) !important;
    transform: translateX(2px);
    box-shadow: var(--ht-shadow-sm);
}
</style>
"""


def _inject_palette_hover_style() -> None:
    """Inject palette card hover CSS into the page head."""
    ui.add_head_html(_HOVER_CSS)
