"""Unit tests for dashboard page API wiring."""
import inspect
from pathlib import Path

import src.ui.pages.dashboard as dashboard_module
from src.ui.pages.dashboard import _load_dashboard_summary
from src.ui.pages.dashboard import dashboard_page
from src.ui.components.dashboard_sections import _inventory_route_with_scope


def test_dashboard_uses_single_summary_endpoint() -> None:
    """Dashboard fetches should use only the HT-082 aggregate summary API."""
    source = inspect.getsource(_load_dashboard_summary) + inspect.getsource(dashboard_page)

    assert "/api/dashboard/summary" in source
    assert "/api/power/summary" not in source
    assert "/api/devices/" not in source
    assert "/api/connections/" not in source
    assert "/api/locations/" not in source
    assert "/api/tags/" not in source


def test_dashboard_workspace_switch_supports_scoped_initial_load() -> None:
    source = inspect.getsource(dashboard_page)

    assert "async def dashboard_page(workspace_id: str | None = None)" in source
    assert "selected_workspace_id = _scope_value(workspace_id)" in source
    assert "summary = await _load_dashboard_summary(headers, selected_workspace_id)" in source
    assert "scoped_workspace_id = _selected_workspace_id(content_summary, selected_workspace_id)" in source
    assert "inventory_route = _inventory_route(scoped_workspace_id)" in source
    assert "_dashboard_history_js(_selected_workspace_id(refreshed_summary, workspace_id))" in source
    assert "content.clear()" in source
    assert "render_dashboard_power_card(ui, power, _refresh_dashboard)" in source


def test_dashboard_module_stays_within_file_limit() -> None:
    source_path = Path(dashboard_module.__file__ or "")
    assert len(source_path.read_text().splitlines()) <= 250


def test_dashboard_route_scoping_keeps_topology_and_edit_routes_opaque() -> None:
    assert _inventory_route_with_scope(
        "/topology?workspace_id=ws-1&topology_id=topo-1&device_id=device-1",
        "ws-2",
    ) == "/topology?workspace_id=ws-1&topology_id=topo-1&device_id=device-1"
    assert _inventory_route_with_scope(
        "/inventory/edit/device-1",
        "ws-2",
    ) == "/inventory/edit/device-1"
    assert _inventory_route_with_scope(
        "/inventory?status=Online",
        "ws-2",
    ) == "/inventory?workspace_id=ws-2&status=Online"
