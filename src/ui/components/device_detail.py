"""Device detail panel — right-side panel shown when a node is tapped on the canvas.

Listens for the `ht:node-selected` custom DOM event dispatched by the canvas
component and renders device metadata. Initially hidden.
"""
from nicegui import ui

from src.ui.design.tokens import (
    COLOR_SURFACE_ALT,
    COLOR_TEXT,
    COLOR_TEXT_MUTED,
    COLOR_PRIMARY,
    SPACING_MD,
    SPACING_SM,
    FONT_SM,
    FONT_LG,
)

_DETAIL_LISTENER_JS = """
(function() {
    document.addEventListener('ht:node-selected', function(evt) {
        var d = evt.detail;
        var panel = document.getElementById('device-detail-panel');
        if (!panel) return;
        panel.style.display = 'flex';

        function setField(id, val) {
            var el = document.getElementById(id);
            if (el) el.innerText = val || '—';
        }
        setField('dd-name', d.label || d.id);
        setField('dd-type', d.device_type || '');
        setField('dd-ip',   d.ip   || '');
        setField('dd-mac',  d.mac  || '');
        setField('dd-os',   d.os   || '');
        setField('dd-notes',d.notes|| '');
    });

    // Context menu — Edit / Duplicate / Delete actions
    document.addEventListener('ht:node-context', function(evt) {
        var d = evt.detail;
        document.dispatchEvent(new CustomEvent('ht:context-menu-request', { detail: d }));
    });
})();
"""


def render_detail_panel() -> None:
    """Render the device detail side-panel (hidden until a node is selected)."""
    ui.add_body_html(f"<script>{_DETAIL_LISTENER_JS}</script>")

    with ui.element("div").props('id="device-detail-panel"').style(
        f"display: none; flex-direction: column; gap: {SPACING_SM}; "
        f"width: 220px; padding: {SPACING_MD}; "
        f"background-color: {COLOR_SURFACE_ALT}; overflow-y: auto;"
    ):
        with ui.row().classes("justify-between items-center w-full"):
            ui.label("Device Info").style(
                f"color: {COLOR_TEXT}; font-size: {FONT_LG}; font-weight: 600;"
            )

            async def _close_panel() -> None:
                await ui.run_javascript(
                    "document.getElementById('device-detail-panel').style.display='none'"
                )

            ui.button(
                icon="close",
                on_click=_close_panel,
            ).props("flat dense").style(f"color: {COLOR_TEXT_MUTED};")

        ui.separator()
        _detail_row("Name", "dd-name")
        _detail_row("Type", "dd-type")
        _detail_row("IP", "dd-ip")
        _detail_row("MAC", "dd-mac")
        _detail_row("OS", "dd-os")
        _detail_row("Notes", "dd-notes")


def _detail_row(label: str, field_id: str) -> None:
    """Render a label/value row in the detail panel."""
    with ui.column().style(f"gap: 2px;"):
        ui.label(label).style(f"color: {COLOR_TEXT_MUTED}; font-size: {FONT_SM}; font-weight: 600;")
        ui.element("span").props(f'id="{field_id}"').style(f"color: {COLOR_TEXT}; font-size: {FONT_SM};")
