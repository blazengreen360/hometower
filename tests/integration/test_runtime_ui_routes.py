"""Runtime UI-route regression tests for NiceGUI page registration."""

from unittest.mock import patch

from fastapi.testclient import TestClient


def _get_map_response() -> object:
    import src.main as runtime_main

    with patch("src.api.app._startup"):
        with TestClient(runtime_main.app) as client:
            return client.get("/map", follow_redirects=False)


def test_map_route_is_reachable_on_runtime_app() -> None:
    """`/map` must resolve through `src.main:app` (historical regression guard)."""
    response = _get_map_response()

    assert response.status_code == 200
    assert "NiceGUI" in response.text


def test_map_route_includes_leaflet_assets_and_csp_allows_them() -> None:
    """Regression guard: CSP must permit map dependencies and tile images."""
    response = _get_map_response()
    csp = response.headers.get("Content-Security-Policy", "")

    assert response.status_code == 200
    assert "script-src" in csp and "cdnjs.cloudflare.com" in csp
    assert "style-src" in csp and "cdnjs.cloudflare.com" in csp
    assert "*.tile.openstreetmap.org" in csp
    assert "*.basemaps.cartocdn.com" in csp


def test_map_route_includes_leaflet_image_size_guards() -> None:
    """Regression guard: map bridge must protect Leaflet tiles/icons from base img rules."""
    import src.ui.components.map_view as map_view_module

    assert "#ht-map-canvas .leaflet-tile" in map_view_module._MAP_STYLE
    assert "#ht-map-canvas .leaflet-marker-icon" in map_view_module._MAP_STYLE
    assert "max-width: none" in map_view_module._MAP_STYLE
    assert "_invalidateMapAfterLayout" in map_view_module._MAP_BRIDGE_JS
    assert "setTimeout(attempt, 50)" in map_view_module._MAP_BRIDGE_JS
