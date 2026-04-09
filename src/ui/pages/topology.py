"""Topology page — NiceGUI page at /topology.

Renders a three-column layout:
  Left:   Device palette (draggable type cards).
  Center: Cytoscape.js canvas (main interactive area).
  Right:  Device detail panel (shown on node click).

Auth guard: redirects to /login if no access_token.
"""
import json

import httpx
from nicegui import app as nicegui_app
from nicegui import ui

from src.ui.components.canvas import render_canvas
from src.ui.components.device_detail import render_detail_panel
from src.ui.components.device_palette import render_palette
from src.ui.design.tokens import (
    COLOR_PRIMARY,
    COLOR_PRIMARY_DARK,
    COLOR_SURFACE,
    COLOR_SURFACE_ALT,
    COLOR_TEXT,
    COLOR_TEXT_MUTED,
    SPACING_MD,
    SPACING_SM,
)
from src.ui.services.topology_data import load_canvas_data
from src.utils.logger import logger
from src.utils.settings import settings

_CONTEXT_MENU_JS = """
(function() {
    document.addEventListener('ht:context-menu-request', function(evt) {
        var d = evt.detail;
        var existing = document.getElementById('ht-ctx-menu');
        if (existing) existing.remove();

        var menu = document.createElement('div');
        menu.id = 'ht-ctx-menu';
        menu.style.cssText = [
            'position:fixed', 'z-index:9999',
            'background:#27273a', 'border-radius:6px',
            'padding:4px 0', 'min-width:140px',
            'box-shadow:0 4px 12px rgba(0,0,0,0.5)',
        ].join(';');

        var actions = [
            { label: 'Edit',      event: 'ht:node-edit' },
            { label: 'Duplicate', event: 'ht:node-duplicate' },
            { label: 'Delete',    event: 'ht:node-delete' },
        ];
        actions.forEach(function(action) {
            var item = document.createElement('div');
            item.innerText = action.label;
            item.style.cssText = 'padding:8px 16px;color:#cdd6f4;cursor:pointer;font-size:0.875rem;';
            item.onmouseenter = function() { item.style.background = '#4f46e5'; };
            item.onmouseleave = function() { item.style.background = ''; };
            item.onclick = function() {
                document.dispatchEvent(new CustomEvent(action.event, { detail: d }));
                menu.remove();
            };
            menu.appendChild(item);
        });

        document.body.appendChild(menu);
        // Position near cursor — use last pointer event
        var x = window._htLastCtxX || 200, y = window._htLastCtxY || 200;
        menu.style.left = x + 'px';
        menu.style.top  = y + 'px';

        var dismiss = function() { menu.remove(); document.removeEventListener('click', dismiss); };
        setTimeout(function() { document.addEventListener('click', dismiss); }, 10);
    });

    document.addEventListener('mousemove', function(e) {
        window._htLastCtxX = e.clientX;
        window._htLastCtxY = e.clientY;
    });
})();
"""


@ui.page("/topology")
async def topology_page() -> None:
    """Topology page — requires auth, renders the full canvas view."""
    token: str | None = nicegui_app.storage.user.get("access_token")
    if not token:
        ui.navigate.to("/login")
        return

    ui.query("body").style(
        f"background-color: {COLOR_SURFACE}; color: {COLOR_TEXT}; margin: 0; overflow: hidden;"
    )
    ui.add_body_html(f"<script>{_CONTEXT_MENU_JS}</script>")

    elements, saved_layout = await load_canvas_data(token)

    # ---- Shell layout ----
    with ui.column().style("width: 100vw; height: 100vh; gap: 0;"):
        # Topbar
        with ui.row().style(
            f"width: 100%; height: 48px; background-color: {COLOR_SURFACE_ALT}; "
            f"align-items: center; padding: 0 {SPACING_MD}; justify-content: space-between; "
            "flex-shrink: 0;"
        ):
            ui.label("Hometower — Topology").style(
                f"color: {COLOR_TEXT}; font-weight: 700; font-size: 1rem;"
            )
            with ui.row().style(f"gap: {SPACING_SM};"):
                ui.button(
                    "Save Layout",
                    on_click=lambda: _save_layout(token),
                ).style(
                    f"background-color: {COLOR_PRIMARY}; color: white; font-size: 0.875rem;"
                )
                ui.button("Logout", on_click=_logout).props("flat").style(
                    f"color: {COLOR_TEXT_MUTED}; font-size: 0.875rem;"
                )

        # Three-column body
        with ui.row().style(
            "flex: 1; width: 100%; min-height: 0; gap: 0; flex-wrap: nowrap; align-items: stretch;"
        ):
            # Left: palette
            with ui.element("div").style(
                f"background-color: {COLOR_SURFACE_ALT}; flex-shrink: 0; overflow-y: auto;"
            ):
                render_palette()

            # Center: canvas
            with ui.element("div").style("flex: 1; min-width: 0; min-height: 0; position: relative;"):
                render_canvas(elements, saved_layout)

            # Right: detail panel
            render_detail_panel()


async def _save_layout(token: str) -> None:
    """Capture current canvas state and POST to /api/diagrams/."""
    canvas_json: dict[str, object] | None = await ui.run_javascript("getCanvasJson()")
    if not canvas_json:
        ui.notify("Nothing to save", type="warning")
        return

    payload = {"name": "Autosave", "cytoscape_json": canvas_json}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.api_base_url}/api/diagrams/",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0,
            )
        if resp.status_code == 201:
            ui.notify("Layout saved", type="positive")
        else:
            ui.notify(f"Save failed ({resp.status_code})", type="negative")
    except httpx.HTTPError as exc:
        logger.error("Layout save failed: {error}", error=str(exc))
        ui.notify("Connection error", type="negative")


def _logout() -> None:
    """Clear auth token and redirect to login."""
    nicegui_app.storage.user.pop("access_token", None)
    ui.run_javascript("sessionStorage.removeItem('access_token')")
    ui.navigate.to("/login")
