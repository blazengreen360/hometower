"""Workspaces page — /workspaces.

Renders a table of user's workspaces with New/Rename/Delete actions.
"""
import html

import httpx
from nicegui import app as nicegui_app
from nicegui import ui

from src.ui.components.app_shell import app_shell
from src.ui.components.auth_guard import redirect_if_unauthenticated
from src.ui.components.dialogs.name_dialog import show_name_dialog
from src.ui.design.primitives import card_surface
from src.ui.design.primitives import danger_button
from src.ui.design.primitives import page_container
from src.ui.design.primitives import primary_button
from src.ui.design.primitives import render_page_intro
from src.ui.design.primitives import secondary_button
from src.ui.design.primitives import table_surface
from src.ui.utils.formatting import LAST_MODIFIED_BROWSER_LOCAL_BRIDGE_SCRIPT
from src.ui.utils.formatting import LAST_MODIFIED_BROWSER_LOCAL_CELL_EXPRESSION
from src.ui.utils.formatting import enrich_last_modified_rows
from src.utils.logger import logger
from src.utils.settings import settings

_API = f"{settings.api_base_url}/api/workspaces"


def _auth_headers() -> dict[str, str]:
    token = nicegui_app.storage.user.get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


@ui.page("/workspaces")
async def workspaces_page() -> None:
    """Workspaces list page."""
    if redirect_if_unauthenticated(current_path="/workspaces"):
        return

    workspaces: list[dict[str, object]] = []
    refs: dict[str, object] = {}

    async def load_workspaces() -> None:
        try:
            async with httpx.AsyncClient() as http:
                resp = await http.get(
                    f"{_API}/", headers=_auth_headers(), timeout=10.0,
                )
            if resp.status_code == 200:
                data = resp.json()
                workspaces.clear()
                workspaces.extend(enrich_last_modified_rows(data.get("items", [])))
                table.rows = workspaces  # type: ignore[assignment]
                table.update()
            else:
                logger.error("Workspaces load failed: status={}", resp.status_code)
        except Exception as exc:
            logger.error("Workspaces load error: {}", str(exc))

    async def on_create(name: str) -> str | None:
        try:
            async with httpx.AsyncClient() as http:
                resp = await http.post(
                    f"{_API}/", json={"name": name},
                    headers=_auth_headers(), timeout=10.0,
                )
            if resp.status_code == 201:
                ui.notify("Workspace created", type="positive")
                await load_workspaces()
                return None
            if resp.status_code == 409:
                return "A workspace with this name already exists."

            else:
                detail = resp.json().get("detail", "Error")
                ui.notify(html.escape(str(detail)), type="negative")
                return None
        except Exception as exc:
            logger.error("Workspace create failed: {}", str(exc))
            ui.notify("Could not create workspace. Please try again.", type="negative")
            return None

    async def on_rename(ws_id: str, name: str) -> str | None:
        try:
            async with httpx.AsyncClient() as http:
                resp = await http.patch(
                    f"{_API}/{ws_id}", json={"name": name},
                    headers=_auth_headers(), timeout=10.0,
                )
            if resp.status_code == 200:
                ui.notify("Renamed", type="positive")
                await load_workspaces()
                return None
            if resp.status_code == 409:
                return "A workspace with this name already exists."

            else:
                detail = resp.json().get("detail", "Error")
                ui.notify(html.escape(str(detail)), type="negative")
                return None
        except Exception as exc:
            logger.error("Workspace rename failed: {}", str(exc))
            ui.notify("Could not rename workspace. Please try again.", type="negative")
            return None

    async def confirm_delete(ws_id: str, name: str) -> None:
        async def do_delete() -> None:
            try:
                async with httpx.AsyncClient() as http:
                    resp = await http.delete(
                        f"{_API}/{ws_id}", headers=_auth_headers(), timeout=10.0,
                    )
                if resp.status_code == 204:
                    ui.notify("Deleted", type="positive")
                    await load_workspaces()
                else:
                    detail = resp.json().get("detail", "Error")
                    ui.notify(html.escape(str(detail)), type="negative")
            except Exception as exc:
                logger.error("Workspace delete failed: {}", str(exc))

        with ui.dialog() as dlg, card_surface(ui.card()).classes("min-w-[360px]"):
            with ui.column().classes("ht-card-section"):
                ui.label(f"Delete '{html.escape(name)}'?").classes("ht-section-title")
                ui.label("All topologies and views will be deleted.").classes("ht-muted-copy")
                with ui.row().classes("gap-2 justify-end"):
                    secondary_button(ui.button("Cancel", on_click=dlg.close))

                    async def _do() -> None:
                        dlg.close()
                        await do_delete()

                    danger_button(ui.button("Delete", on_click=_do))
        dlg.open()

    with app_shell("Workspaces", "/workspaces", breadcrumb=["Workspaces"]):
        ui.add_body_html(LAST_MODIFIED_BROWSER_LOCAL_BRIDGE_SCRIPT)

        with page_container(ui.column()):
            with ui.row().classes("w-full items-end justify-between gap-4 flex-wrap"):
                render_page_intro(
                    ui,
                    "Workspaces",
                    "Organize homelab environments into focused operating areas, then drill into the topologies each workspace owns.",
                    "Inventory Control",
                )
                primary_button(ui.button(
                    "+ New Workspace",
                    on_click=lambda: show_name_dialog(
                        "New Workspace", "Workspace name", on_submit=on_create,
                    ),
                ))

            columns: list[dict[str, str | bool]] = [
                {"name": "name", "label": "Name", "field": "name", "sortable": True},
                {"name": "topology_count", "label": "Topologies", "field": "topology_count"},
                {"name": "last_modified", "label": "Last Modified", "field": "last_modified_sort", "sortable": True},
                {"name": "actions", "label": "Actions", "field": "actions"},
            ]
            table = table_surface(ui.table(columns=columns, rows=[], row_key="id"))
            table.add_slot(
                "body",
                r"""
                <q-tr :props="props">
                    <q-td key="name">
                        <a :href="'/workspaces/' + props.row.id" class="ht-table-link">
                            {{ props.row.name }}
                        </a>
                    </q-td>
                    <q-td key="topology_count">{{ props.row.topology_count }}</q-td>
                    <q-td key="last_modified">
                        {{ __LAST_MODIFIED_DISPLAY__ }}
                        <q-tooltip v-if="props.row.last_modified_iso">{{ props.row.last_modified_iso }}</q-tooltip>
                    </q-td>
                    <q-td key="actions">
                        <q-btn flat dense icon="edit"
                            @click="() => $parent.$emit('rename', props.row)" />
                        <q-btn flat dense icon="delete" class="ht-btn-icon-danger"
                            @click="() => $parent.$emit('delete', props.row)" />
                    </q-td>
                </q-tr>
                """.replace(
                    "__LAST_MODIFIED_DISPLAY__",
                    LAST_MODIFIED_BROWSER_LOCAL_CELL_EXPRESSION,
                ),
            )
            table.on(
                "rename",
                lambda e: show_name_dialog(
                    "Rename Workspace", "Workspace name",
                    current_value=e.args.get("name", ""),
                    on_submit=lambda n: on_rename(e.args["id"], n),
                ),
            )
            table.on(
                "delete",
                lambda e: confirm_delete(e.args["id"], e.args.get("name", "")),
            )

    await load_workspaces()
