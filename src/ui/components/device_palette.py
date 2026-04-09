"""Device palette sidebar — draggable device type cards for the topology canvas.

Each card uses HTML5 drag-and-drop: dragstart sets dataTransfer with the
device type string; the canvas drop handler reads it to create a new node.
"""
from nicegui import ui

from src.models.types import DeviceType
from src.ui.design.tokens import (
    COLOR_PRIMARY,
    COLOR_SURFACE_ALT,
    COLOR_TEXT,
    COLOR_TEXT_MUTED,
    DEVICE_SHAPES,
    SPACING_SM,
    SPACING_XS,
    FONT_SM,
)

# Map Cytoscape shape names to simple Unicode glyphs for visual hint
_SHAPE_GLYPHS: dict[str, str] = {
    "rectangle": "▬",
    "diamond": "◆",
    "triangle": "▲",
    "hexagon": "⬡",
    "round-rectangle": "▭",
    "ellipse": "●",
    "barrel": "⌗",
}

_DRAG_SCRIPT = """
function htPaletteCardDrag(el, deviceType) {
    el.setAttribute('draggable', 'true');
    el.addEventListener('dragstart', function(e) {
        e.dataTransfer.setData('deviceType', deviceType);
        e.dataTransfer.effectAllowed = 'copy';
    });
}
"""


def render_palette() -> None:
    """Render the device type palette sidebar."""
    ui.add_body_html(f"<script>{_DRAG_SCRIPT}</script>")

    with ui.column().style(
        f"width: 160px; gap: {SPACING_SM}; padding: {SPACING_SM}; overflow-y: auto;"
    ):
        ui.label("Devices").style(
            f"color: {COLOR_TEXT}; font-size: {FONT_SM}; font-weight: 600; text-transform: uppercase;"
        )

        for device_type in DeviceType:
            shape = DEVICE_SHAPES.get(device_type, "rectangle")
            glyph = _SHAPE_GLYPHS.get(shape, "■")
            _render_palette_card(device_type, glyph)


def _render_palette_card(device_type: DeviceType, glyph: str) -> None:
    """Render a single draggable palette card."""
    card_id = f"palette-{device_type.value.lower()}"
    with ui.element("div").props(f'id="{card_id}"').style(
        f"display: flex; align-items: center; gap: {SPACING_XS}; "
        f"padding: {SPACING_XS} {SPACING_SM}; border-radius: 6px; cursor: grab; "
        f"background-color: {COLOR_SURFACE_ALT}; user-select: none;"
    ):
        ui.label(glyph).style(f"color: {COLOR_PRIMARY}; font-size: 1rem; min-width: 1.25rem;")
        ui.label(device_type.value).style(f"color: {COLOR_TEXT}; font-size: {FONT_SM};")

    ui.run_javascript(
        f"htPaletteCardDrag(document.getElementById('{card_id}'), '{device_type.value}')"
    )
