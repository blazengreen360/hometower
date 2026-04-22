"""Connection detail panel — shown when a canvas edge is clicked (HT-030)."""
import html
import json

from nicegui import ui

from src.models.types import ConnectionType
from src.ui.components.connection_detail_panel_support import can_edit_connection
from src.ui.components.connection_detail_panel_support import patch_connection
from src.ui.components.device_detail_panel_shell import (
    build_panel_visibility_js,
    build_right_rail_panel,
)
from src.ui.components.toast import show_toast
from src.ui.design.primitives import card_section
from src.ui.design.primitives import card_surface
from src.ui.design.primitives import danger_button
from src.ui.design.primitives import primary_button
from src.ui.design.primitives import secondary_button

_CONNECTION_PANEL_HIDE_JS = build_panel_visibility_js("connection-detail-panel", False)

_BRIDGE_JS = """
(function() {
    if (window._htConnBridgeInit) return;
    window._htConnBridgeInit = true;
    document.addEventListener('ht:edge-selected', function(evt) {
        var d = evt && evt.detail;
        if (d && d.id) emitEvent('conn_panel_select', {
            id: String(d.id),
            source: String(d.source || ''),
            target: String(d.target || ''),
            source_label: String(d.source_label || d.source || ''),
            target_label: String(d.target_label || d.target || ''),
            conn_type: String(d.type || 'Ethernet'),
            label: String(d.label || '')
        });
    });
    document.addEventListener('ht:node-selected', function() {
        __HIDE_CONNECTION_PANEL_JS__
    });
    document.addEventListener('ht:canvas-bg-click', function() {
        __HIDE_CONNECTION_PANEL_JS__
    });
})();
""".replace("__HIDE_CONNECTION_PANEL_JS__", _CONNECTION_PANEL_HIDE_JS)

def _build_cy_edge_remove_js(conn_id: str) -> str:
    """Build JS to remove an edge by id using safe JSON serialization."""
    return f"if(window._cy)window._cy.getElementById({json.dumps(conn_id)}).remove();"


def _build_cy_edge_update_js(conn_id: str, conn_type: str, label: str) -> str:
    """Build JS to update an edge label/type using safe JSON serialization."""
    escaped_label = html.escape(label)
    return (
        "if(window._cy){"
        f"var e=window._cy.getElementById({json.dumps(conn_id)});"
        f"if(e.length){{e.data('connection_type',{json.dumps(conn_type)});"
        f"e.data('label',{json.dumps(escaped_label)});"
        f"e.data('raw_label',{json.dumps(label)});}}"
        "}"
    )


def _build_request_delete_edge_js(
    conn_id: str,
    source_id: str,
    target_id: str,
    conn_type: str,
    label: str,
) -> str:
    """Build JS to request an undo-aware published edge delete and close panel on success."""
    payload = {
        "type": "delete_edge",
        "payload": {
            "scope": "published",
            "connection_id": conn_id,
            "source_id": source_id,
            "target_id": target_id,
            "connection_type": conn_type,
            "label": label or None,
        },
    }
    return (
        "(function(){"
        "if(!window._htRequestCanvasAction)return;"
        f"window._htRequestCanvasAction({json.dumps(payload)});"
        f"var edgeId={json.dumps(conn_id)};"
        "var closeIfRemoved=function(){"
        "if(!window._cy)return;"
        "var edge=window._cy.getElementById(edgeId);"
        "if(edge && edge.length)return;"
        f"{build_panel_visibility_js('connection-detail-panel', False)}"
        "};"
        "setTimeout(closeIfRemoved,300);"
        "setTimeout(closeIfRemoved,900);"
        "})();"
    )


def render_connection_detail_panel(token: str, user_role: str) -> None:
    """Render the connection detail panel. Called from topology page."""
    is_editor: bool = can_edit_connection(user_role)
    state: dict[str, object] = {"conn_id": None}
    _src_lbl: list[ui.label] = []
    _tgt_lbl: list[ui.label] = []
    _body_col: list[ui.column] = []

    ui.add_body_html(f"<script>{_BRIDGE_JS}</script>")

    panel = build_right_rail_panel(
        "connection-detail-panel", "Connection details", element_builder=ui.element
    )

    with panel:
        with ui.row().classes("justify-between items-center w-full"):
            ui.label("Connection").style("color:var(--ht-text-primary); font-size:1.25rem; font-weight:600;")

            async def _close() -> None:
                await ui.run_javascript(build_panel_visibility_js("connection-detail-panel", False))
                state["conn_id"] = None

            ui.button(icon="close", on_click=_close).props("flat dense aria-label='Close panel'").style(
                "color:var(--ht-text-secondary);"
            )

        _src_lbl.append(ui.label("\u2014").style("font-size:0.875rem; color:var(--ht-text-secondary);"))
        _tgt_lbl.append(ui.label("\u2014").style("font-size:0.875rem; color:var(--ht-text-secondary);"))
        ui.separator()
        content = ui.column().classes("w-full gap-2")
        _body_col.append(content)

    async def _populate(args: dict[str, object]) -> None:
        cid = str(args.get("id", ""))
        src = str(args.get("source_label", ""))
        tgt = str(args.get("target_label", ""))
        source_id = str(args.get("source", ""))
        target_id = str(args.get("target", ""))
        ctype = str(args.get("conn_type", ConnectionType.Ethernet.value))
        clabel = str(args.get("label", "") or "")
        safe_src = html.escape(src)
        safe_tgt = html.escape(tgt)
        safe_ctype = html.escape(ctype)
        safe_clabel = html.escape(clabel)

        _src_lbl[0].set_text(f"\u2192 from: {safe_src}")
        _tgt_lbl[0].set_text(f"\u2192 to: {safe_tgt}")

        body: ui.column = _body_col[0]
        body.clear()
        with body:
            type_opts = [ct.value for ct in ConnectionType]
            if is_editor:
                ts = ui.select(
                    options=type_opts, label="Type", value=ctype
                ).classes("w-full")
                li = ui.input(label="Label", value=clabel).classes("w-full")

                confirm_dlg = ui.dialog()
                with confirm_dlg:
                    with card_surface(ui.card()).classes("min-w-[280px]"):
                        with card_section(ui.column()):
                            ui.label(f"Delete connection between {safe_src} and {safe_tgt}?").classes(
                                "ht-section-title"
                            )
                            with ui.row().classes("justify-end gap-2"):
                                async def _do_del(_cid: str = cid) -> None:
                                    await ui.run_javascript(
                                        "if(!window._htRequestCanvasAction && window._htNotify) "
                                        "window._htNotify('Delete unavailable: undo bridge not ready.', 'negative');"
                                    )
                                    await ui.run_javascript(
                                        _build_request_delete_edge_js(
                                            conn_id=_cid,
                                            source_id=source_id,
                                            target_id=target_id,
                                            conn_type=ctype,
                                            label=clabel,
                                        )
                                    )
                                    state["conn_id"] = None
                                    confirm_dlg.close()

                                secondary_button(ui.button("Cancel", on_click=confirm_dlg.close))
                                danger_button(ui.button("Delete", on_click=_do_del))

                async def _save(_ts: ui.select = ts, _li: ui.input = li, _cid: str = cid) -> None:
                    ok = await patch_connection(
                        token, _cid, {"type": _ts.value, "label": _li.value or None}
                    )
                    if ok:
                        updated_type = str(_ts.value)
                        updated_label = str(_li.value or "")
                        await ui.run_javascript(
                            _build_cy_edge_update_js(
                                conn_id=_cid,
                                conn_type=updated_type,
                                label=updated_label,
                            )
                        )
                        show_toast(type="success", title="Connection updated")
                    else:
                        show_toast(type="error", title="Update failed")

                with ui.row().classes("gap-2 mt-2 w-full"):
                    primary_button(ui.button("Save", on_click=_save)).props("dense")
                    danger_button(ui.button("Delete", on_click=lambda: confirm_dlg.open())).props("dense")
            else:
                ui.label(f"Type: {safe_ctype}").style("font-size:0.875rem; color:var(--ht-text-primary);")
                ui.label(f"Label: {safe_clabel or '\u2014'}").style(
                    "font-size:0.875rem; color:var(--ht-text-primary);"
                )

        await ui.run_javascript(build_panel_visibility_js("connection-detail-panel", True))

    async def _on_conn_panel_select(e: object) -> None:
        args = getattr(e, "args", None)
        if not isinstance(args, dict):
            return
        cid = args.get("id", "")
        if not isinstance(cid, str) or not cid:
            return
        state["conn_id"] = cid
        await _populate(args)

    ui.on("conn_panel_select", _on_conn_panel_select)
