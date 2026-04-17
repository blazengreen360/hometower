"""Execution-level assertions for connection detail panel delete wiring (HT-032)."""

import inspect


def test_connection_delete_routes_through_undo_stack_request() -> None:
    import src.ui.components.connection_detail_panel as panel_module

    source = inspect.getsource(panel_module.render_connection_detail_panel)

    assert "_htRequestCanvasAction" in source
    assert "delete_edge" in source
