"""Geographic map page at /map (HT-008)."""

from __future__ import annotations

import json
from nicegui import app as nicegui_app
from nicegui import ui

from src.ui.components.app_shell import app_shell
from src.ui.components.auth_guard import redirect_if_unauthenticated
from src.ui.components.map_view import inject_map_view_assets, map_bootstrap_payload
from src.ui.design.primitives import page_container, render_page_intro, secondary_button
from src.ui.pages.map_page_data import MapLocation, load_geo_locations
from src.utils.logger import logger

_EMPTY_STATE_TEXT = (
    "No geographic locations yet — add a location with coordinates in Settings → Locations"
)


@ui.page("/map")
async def map_page() -> None:
    """Read-only geographic map page available to all authenticated users."""
    if redirect_if_unauthenticated(current_path="/map"):
        return

    geo_locations = await load_geo_locations()
    by_location_id = {location["id"]: location for location in geo_locations}

    theme_name = str(nicegui_app.storage.user.get("theme", "dark"))
    use_dark_tiles = theme_name != "light"

    state: dict[str, str] = {"value": "loading"}

    with app_shell("Map", "/map", breadcrumb=["Map"]):
        inject_map_view_assets()
        with page_container(ui.column()).classes("flex-1 min-h-0 gap-4"):
            render_page_intro(
                ui,
                "Infrastructure Map",
                "Browse geographic locations and jump directly into the related topology context.",
            )

            with ui.element("div").style(
                "position:relative; flex:1; width:100%; min-height:0; border:1px solid var(--ht-border);"
                "border-radius:10px; overflow:hidden;"
            ):
                map_canvas = ui.element("div").props(
                    'id="ht-map-canvas" aria-label="Geographic locations map" tabindex="0"'
                ).style("position:absolute; inset:0;")

                loading_card = ui.card().style(
                    "position:absolute; top:16px; left:16px; z-index:450;"
                    "background:var(--ht-bg-surface-raised); border:1px solid var(--ht-border);"
                )
                with loading_card:
                    ui.label("Loading geographic locations...").style(
                        "color:var(--ht-text-primary); font-size:0.875rem;"
                    )

                empty_card = ui.card().style(
                    "position:absolute; inset:24px; z-index:440; display:flex; justify-content:center;"
                    "align-items:center; text-align:center; background:var(--ht-bg-surface-raised);"
                    "border:1px dashed var(--ht-border);"
                )
                with empty_card:
                    ui.label(_EMPTY_STATE_TEXT).style(
                        "color:var(--ht-text-secondary); font-size:0.95rem;"
                    )

                fallback_card = ui.card().style(
                    "position:absolute; inset:16px; z-index:445; overflow:auto;"
                    "background:var(--ht-bg-surface-raised); border:1px solid var(--ht-border);"
                )
                with fallback_card:
                    fallback_reason = ui.label(
                        "Map unavailable in this browser session. Showing geo locations list instead."
                    ).style("color:var(--ht-warning); font-size:0.85rem;")
                    fallback_table = ui.table(
                        columns=[
                            {"name": "name", "label": "Location", "field": "name"},
                            {"name": "coords", "label": "Coordinates", "field": "coords"},
                            {"name": "devices", "label": "Devices", "field": "devices"},
                        ],
                        rows=[],
                        row_key="name",
                    ).classes("w-full").style("background:var(--ht-bg-surface);")

                drawer = ui.element("aside").props(
                    'id="ht-map-drawer" role="complementary" aria-label="Location details"'
                ).style(
                    "position:absolute; top:0; right:0; bottom:0; width:320px;"
                    "max-width:92vw; z-index:500; background:var(--ht-bg-surface-raised);"
                    "border-left:1px solid var(--ht-border); box-shadow:var(--ht-shadow-lg);"
                    "display:flex; flex-direction:column; padding:12px; gap:8px;"
                )
                with drawer:
                    with ui.row().classes("w-full items-center justify-between"):
                        drawer_title = ui.label("Location").classes("ht-section-title")
                        ui.button(icon="close", on_click=lambda: _set_drawer_open(False)).props(
                            "flat dense round aria-label='Close location details'"
                        )
                    drawer_meta = ui.label("0 devices").classes("ht-small-copy")
                    device_list = ui.column().classes("w-full").style("gap:6px;")

    def _set_drawer_open(is_open: bool) -> None:
        drawer.set_visibility(is_open)
        if is_open:
            drawer.classes(add="ht-map-drawer-open")
            return
        drawer.classes(remove="ht-map-drawer-open")

    def _set_state(next_state: str) -> None:
        state["value"] = next_state
        loading_card.set_visibility(next_state == "loading")
        empty_card.set_visibility(next_state == "empty")
        fallback_card.set_visibility(next_state == "fallback")
        map_canvas.set_visibility(next_state == "ready")
        if next_state != "ready":
            _set_drawer_open(False)

    def _render_drawer(location: MapLocation) -> None:
        drawer_title.set_text(location["name"])
        device_count = location["device_count"]
        suffix = "device" if device_count == 1 else "devices"
        drawer_meta.set_text(f"{device_count} {suffix}")
        device_list.clear()
        with device_list:
            if not location["devices"]:
                ui.label("No devices assigned to this location.").style(
                    "color:var(--ht-text-secondary); font-size:0.875rem;"
                )
            for device in location["devices"]:
                with ui.row().classes("w-full items-center justify-between"):
                    secondary_button(
                        ui.button(
                            device["name"],
                            icon="dns",
                            on_click=lambda did=device["id"]: ui.navigate.to(
                                f"/topology?device_id={did}"
                            ),
                        ).props("align=left")
                    ).classes("w-full justify-start")
                    ui.label(device["type"]).style(
                        "color:var(--ht-text-secondary); font-size:0.75rem;"
                    )
        _set_drawer_open(True)

    async def _on_map_location_selected(event: object) -> None:
        args = getattr(event, "args", None)
        if not isinstance(args, dict):
            return
        raw_location_id = args.get("location_id")
        if not isinstance(raw_location_id, str):
            return
        location = by_location_id.get(raw_location_id)
        if location is None:
            return
        _render_drawer(location)
        await ui.run_javascript(
            f"if(window.htFocusMapLocation) window.htFocusMapLocation({json.dumps(raw_location_id)});"
        )

    ui.on("map_location_selected", _on_map_location_selected)

    _set_state("loading")
    if not geo_locations:
        _set_state("empty")
        return

    payload = map_bootstrap_payload(
        locations=[dict(location) for location in geo_locations],
        use_dark_tiles=use_dark_tiles,
    )
    try:
        result = await ui.run_javascript(f"window.htRenderMap({json.dumps(payload)})")
    except Exception as exc:
        logger.warning("Map bootstrap JavaScript execution failed: {}", exc)
        result = {"ok": False, "error": str(exc) or "map-bootstrap-failed"}

    if isinstance(result, dict) and result.get("ok") is True:
        _set_state("ready")
        return

    fallback_rows: list[dict[str, str]] = []
    for location in geo_locations:
        fallback_rows.append(
            {
                "name": location["name"],
                "coords": f"{location['lat']:.5f}, {location['lng']:.5f}",
                "devices": str(location["device_count"]),
            }
        )
    fallback_table.rows = fallback_rows
    fallback_table.update()

    error_text = "leaflet-unavailable"
    if isinstance(result, dict):
        raw_error = result.get("error")
        if isinstance(raw_error, str) and raw_error.strip():
            error_text = raw_error.strip()
    fallback_reason.set_text(
        "Map unavailable in this browser session. Showing geo locations list instead "
        f"({error_text})."
    )
    _set_state("fallback")