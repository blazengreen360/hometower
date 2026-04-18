"""Workspace detail page — /workspaces/{workspace_id}."""
import html

import httpx
from nicegui import app as nicegui_app
from nicegui import ui
from nicegui.elements.table import Table

from src.ui.components.app_shell import app_shell
from src.ui.components.auth_guard import redirect_if_unauthenticated
from src.ui.components.breadcrumb import render_breadcrumb
from src.ui.components.dialogs.name_dialog import show_name_dialog
from src.ui.design.primitives import card_surface
from src.ui.design.primitives import danger_button
from src.ui.design.primitives import page_container
from src.ui.design.primitives import primary_button
from src.ui.design.primitives import render_page_intro
from src.ui.design.primitives import secondary_button
from src.ui.design.table_patterns import create_standard_table
from src.ui.design.table_patterns import render_table_search_input
from src.ui.pages.workspace_detail_table import TOPOLOGY_TABLE_BODY_SLOT
from src.ui.pages.workspace_detail_table import TOPOLOGY_TABLE_COLUMNS
from src.ui.utils.formatting import LAST_MODIFIED_BROWSER_LOCAL_BRIDGE_SCRIPT
from src.ui.utils.formatting import LAST_MODIFIED_BROWSER_LOCAL_CELL_EXPRESSION
from src.ui.utils.formatting import enrich_last_modified_rows
from src.utils.logger import logger
from src.utils.settings import settings

_API = settings.api_base_url


def _auth_headers() -> dict[str, str]:
    token = nicegui_app.storage.user.get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


@ui.page("/workspaces/{workspace_id}/topologies/{topology_id}")
async def topology_redirect_page(workspace_id: str, topology_id: str) -> None:
    """Redirect old views-table route directly to the canvas."""
    path = f"/workspaces/{workspace_id}/topologies/{topology_id}"
    if redirect_if_unauthenticated(current_path=path):
        return
    ui.navigate.to(
        f"/topology?topology_id={topology_id}&workspace_id={workspace_id}",
        new_tab=False,
    )


@ui.page("/workspaces/{workspace_id}")
async def workspace_detail_page(workspace_id: str) -> None:
    """Workspace detail — lists topologies."""
    if redirect_if_unauthenticated(current_path=f"/workspaces/{workspace_id}"):
        return

    ws_name = "Workspace"
    topologies: list[dict[str, object]] = []
    table: Table | None = None

    async def load_workspace() -> None:
        nonlocal ws_name
        try:
            async with httpx.AsyncClient() as http:
                resp = await http.get(
                    f"{_API}/api/workspaces/{workspace_id}",
                    headers=_auth_headers(), timeout=10.0,
                )
            if resp.status_code == 200:
                ws_name = resp.json().get("name", "Workspace")
        except Exception as exc:
            logger.error("Workspace load error: {}", str(exc))

    async def load_topologies() -> None:
        try:
            async with httpx.AsyncClient() as http:
                resp = await http.get(
                    f"{_API}/api/workspaces/{workspace_id}/topologies/",
                    headers=_auth_headers(), timeout=10.0,
                )
            if resp.status_code == 200:
                topologies.clear()
                topologies.extend(enrich_last_modified_rows(resp.json().get("items", [])))
                if table is None:
                    return
                table.rows = topologies
                table.update()
        except Exception as exc:
            logger.error("Topologies load error: {}", str(exc))

    async def on_create(name: str) -> str | None:
        try:
            async with httpx.AsyncClient() as http:
                resp = await http.post(
                    f"{_API}/api/workspaces/{workspace_id}/topologies/",
                    json={"name": name}, headers=_auth_headers(), timeout=10.0,
                )
            if resp.status_code == 201:
                ui.notify("Topology created", type="positive")
                await load_topologies()
                return None
            if resp.status_code == 409:
                return "A topology with this name already exists."

            else:
                detail = resp.json().get("detail", "Error")
                ui.notify(html.escape(str(detail)), type="negative")
                return None
        except Exception as exc:
            logger.error("Topology create failed: {}", str(exc))
            ui.notify("Could not create topology. Please try again.", type="negative")
            return None

    async def on_rename(topo_id: str, name: str) -> str | None:
        try:
            async with httpx.AsyncClient() as http:
                resp = await http.patch(
                    f"{_API}/api/topologies/{topo_id}",
                    json={"name": name}, headers=_auth_headers(), timeout=10.0,
                )
            if resp.status_code == 200:
                ui.notify("Renamed", type="positive")
                await load_topologies()
                return None
            if resp.status_code == 409:
                return "A topology with this name already exists."

            else:
                detail = resp.json().get("detail", "Error")
                ui.notify(html.escape(str(detail)), type="negative")
                return None
        except Exception as exc:
            logger.error("Topology rename failed: {}", str(exc))
            ui.notify("Could not rename topology. Please try again.", type="negative")
            return None

    async def confirm_delete(topo_id: str, name: str) -> None:
        async def do_delete() -> None:
            try:
                async with httpx.AsyncClient() as http:
                    resp = await http.delete(
                        f"{_API}/api/topologies/{topo_id}",
                        headers=_auth_headers(), timeout=10.0,
                    )
                if resp.status_code == 204:
                    ui.notify("Deleted", type="positive")
                    await load_topologies()
                else:
                    detail = resp.json().get("detail", "Error")
                    ui.notify(html.escape(str(detail)), type="negative")
            except Exception as exc:
                logger.error("Topology delete failed: {}", str(exc))

        with ui.dialog() as dlg, card_surface(ui.card()).classes("min-w-[360px]"):
            with ui.column().classes("ht-card-section"):
                ui.label(f"Delete '{html.escape(name)}'?").classes("ht-section-title")
                ui.label("The topology and its canvas data will be deleted.").classes("ht-muted-copy")
                with ui.row().classes("gap-2 justify-end"):
                    secondary_button(ui.button("Cancel", on_click=dlg.close))

                    async def _do() -> None:
                        dlg.close()
                        await do_delete()

                    danger_button(ui.button("Delete", on_click=_do))
        dlg.open()

    await load_workspace()

    with app_shell("Workspace", f"/workspaces/{workspace_id}", breadcrumb=["Workspaces"]):
        ui.add_body_html(LAST_MODIFIED_BROWSER_LOCAL_BRIDGE_SCRIPT)

        with page_container(ui.column()):
            def _apply_search(value: str) -> None:
                if table is not None:
                    table.set_filter(value)

            render_breadcrumb([("Workspaces", "/workspaces"), (ws_name, "")])
            with ui.row().classes("w-full items-end justify-between gap-4 flex-wrap"):
                render_page_intro(
                    ui,
                    ws_name,
                    "A workspace groups related topologies so diagrams, inventory, and history stay anchored to the same operating context.",
                    "Workspace",
                )
                primary_button(ui.button(
                    "+ New Topology",
                    on_click=lambda: show_name_dialog(
                        "New Topology", "Topology name", on_submit=on_create,
                    ),
                ))
            with ui.row().classes("w-full justify-end"):
                render_table_search_input(
                    ui_module=ui,
                    placeholder="Search topologies",
                    on_change=_apply_search,
                )

            table = create_standard_table(ui_module=ui, columns=TOPOLOGY_TABLE_COLUMNS, row_key="id", sort_by="name")
            table.add_slot(
                "body",
                TOPOLOGY_TABLE_BODY_SLOT.replace("__LAST_MODIFIED_DISPLAY__", LAST_MODIFIED_BROWSER_LOCAL_CELL_EXPRESSION),
            )

            async def _open_topology(e: object) -> None:
                """Navigate to a topology canvas."""
                args: dict[str, object] = getattr(e, "args", {})
                topo_id = str(args.get("id", ""))
                if not topo_id:
                    return
                ui.navigate.to(
                    f"/topology?topology_id={topo_id}"
                    f"&workspace_id={workspace_id}"
                )

            table.on("open", _open_topology)
            table.on(
                "rename",
                lambda e: show_name_dialog(
                    "Rename Topology", "Topology name",
                    current_value=e.args.get("name", ""),
                    on_submit=lambda n: on_rename(e.args["id"], n),
                ),
            )
            table.on(
                "delete",
                lambda e: confirm_delete(e.args["id"], e.args.get("name", "")),
            )

    await load_topologies()
