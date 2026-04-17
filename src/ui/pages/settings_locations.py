"""Settings — Locations management page at /settings/locations.

Renders a table of all locations with create, edit, and delete actions.
"""
import html
from typing import Optional

import httpx
from nicegui import app as nicegui_app
from nicegui import ui

from src.models.types import Role
from src.ui.components.app_shell import app_shell
from src.ui.components.auth_guard import redirect_if_insufficient_role, redirect_if_unauthenticated
from src.ui.components.location_modal import (
    LocationModalController,
    create_location_modal,
)
from src.ui.utils.validation_feedback import friendly_error_message
from src.utils.logger import logger
from src.utils.settings import settings

_API = f"{settings.api_base_url}/api/locations/"
_LOCATION_FIELD_LABELS: dict[str, str] = {
    "name": "Name",
    "lat": "Latitude",
    "lng": "Longitude",
    "row": "Row",
}
_LOCATION_MESSAGE_OVERRIDES: dict[str, str] = {
    "string should have at least": "Name is required.",
    "name must not be blank": "Name is required.",
    "parent location not found": "Parent location was not found.",
}


def _auth_headers() -> dict[str, str]:
    token = nicegui_app.storage.user.get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


def _format_coord_for_form(value: object) -> str:
    """Return an empty string for None while preserving numeric zero values."""
    return str(value) if value is not None else ""


@ui.page("/settings/locations")
async def settings_locations_page() -> None:
    """Location management settings page."""
    if redirect_if_unauthenticated(current_path="/settings/locations"):
        return
    if redirect_if_insufficient_role(Role.Contributor):
        return

    # --- Page state ---
    locations: list[dict] = []
    modal_mode = {"value": "create"}  # "create" | "edit"
    editing_id: dict[str, Optional[str]] = {"value": None}

    # Form field state
    form = {
        "name": "",
        "type": "rack",
        "lat": "",
        "lng": "",
        "rack": "",
        "row": "",
        "parent_id": "",
    }

    modal: LocationModalController

    async def load_locations() -> None:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(_API, headers=_auth_headers())
            resp.raise_for_status()
            locations.clear()
            locations.extend(resp.json())
            table.rows = _to_rows(locations)
            table.update()
        except Exception as exc:
            logger.error("Failed to load locations: {}", exc)
            ui.notify("Couldn't load locations. Please refresh and try again.", type="negative")

    def _to_rows(locs: list[dict]) -> list[dict]:
        pmap: dict[str, str] = {l["id"]: l["name"] for l in locs}
        return [{
            "id": l["id"], "name": l["name"], "type": l["type"],
            "rack": l.get("rack") or "", "row": l.get("row") or "",
            "lat": _format_coord_for_form(l.get("lat")),
            "lng": _format_coord_for_form(l.get("lng")),
            "parent_id": l.get("parent_id") or "",
            "parent": pmap.get(l.get("parent_id") or "", ""),
        } for l in locs]

    def _reset_form() -> None:
        form.update({
            "name": "", "type": "rack", "lat": "", "lng": "",
            "rack": "", "row": "", "parent_id": "",
        })
        modal.clear_error()

    def open_create_modal() -> None:
        _reset_form()
        modal_mode["value"] = "create"
        editing_id["value"] = None
        modal.open_for_mode("create")

    def open_edit_modal(row: dict) -> None:
        _reset_form()
        form["name"] = row["name"]
        form["type"] = row["type"]
        form["rack"] = row.get("rack") or ""
        form["row"] = row.get("row") or ""
        form["lat"] = _format_coord_for_form(row.get("lat"))
        form["lng"] = _format_coord_for_form(row.get("lng"))
        form["parent_id"] = row.get("parent_id") or ""
        modal_mode["value"] = "edit"
        editing_id["value"] = row["id"]
        modal.open_for_mode("edit")

    async def submit_form() -> None:
        modal.clear_error()
        name_value = form["name"].strip()
        if not name_value:
            modal.set_error("Name is required.")
            return

        payload: dict = {"name": name_value, "type": form["type"]}
        if form["type"] == "geo":
            try:
                payload["lat"] = float(form["lat"])
                payload["lng"] = float(form["lng"])
            except ValueError:
                modal.set_error("Latitude and longitude must be valid numbers.")
                return
            # Explicitly clear rack-only fields so type transitions work
            payload["rack"] = None
            payload["row"] = None
            payload["parent_id"] = None
        else:
            if form["rack"]:
                payload["rack"] = form["rack"]
            else:
                payload["rack"] = None
            if form["row"]:
                payload["row"] = form["row"]
            else:
                payload["row"] = None
            if form["parent_id"]:
                payload["parent_id"] = form["parent_id"]
            else:
                payload["parent_id"] = None
            # Explicitly clear geo-only fields so type transitions work
            payload["lat"] = None
            payload["lng"] = None

        try:
            async with httpx.AsyncClient() as client:
                if modal_mode["value"] == "create":
                    resp = await client.post(
                        _API, json=payload, headers=_auth_headers()
                    )
                else:
                    resp = await client.patch(
                        f"{_API}{editing_id['value']}",
                        json=payload,
                        headers=_auth_headers(),
                    )
            if resp.status_code in (200, 201):
                modal.close()
                ui.notify("Saved", type="positive")
                await load_locations()
            else:
                modal.set_error(
                    friendly_error_message(
                        resp,
                        fallback="Couldn't save location. Please check the form and try again.",
                        field_labels=_LOCATION_FIELD_LABELS,
                        message_overrides=_LOCATION_MESSAGE_OVERRIDES,
                    )
                )
        except Exception as exc:
            logger.error("Location save failed: {}", exc)
            modal.set_error("Couldn't save location right now. Please try again.")

    async def confirm_delete(loc_id: str, loc_name: str) -> None:
        async def do_delete() -> None:
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.delete(
                        f"{_API}{loc_id}", headers=_auth_headers()
                    )
                if resp.status_code == 204:
                    ui.notify(f"Deleted '{html.escape(loc_name)}'", type="positive")
                    await load_locations()
                else:
                    ui.notify(
                        friendly_error_message(
                            resp,
                            fallback="Couldn't delete location. Please try again.",
                        ),
                        type="negative",
                    )
            except Exception as exc:
                logger.error("Location delete failed: {}", exc)
                ui.notify("Couldn't delete location right now. Please try again.", type="negative")

        with ui.dialog() as confirm_dlg, ui.card():
            ui.label(f"Delete '{html.escape(loc_name)}'?").classes("font-bold")
            ui.label(
                "If devices are assigned, deletion will be blocked."
            ).style("color: var(--ht-text-secondary); font-size: 0.875rem")
            with ui.row():
                ui.button("Cancel", on_click=confirm_dlg.close).props("flat")

                async def _do_delete_and_close() -> None:
                    confirm_dlg.close()
                    await do_delete()

                ui.button(
                    "Delete",
                    on_click=_do_delete_and_close,
                ).props("color=negative")
        confirm_dlg.open()

    # --- Layout ---
    with app_shell("Locations", "/settings/locations", breadcrumb=["Settings", "Locations"]):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Locations").classes("text-2xl font-bold").style(
                "color: var(--ht-text-primary)"
            )
            ui.button(
                "+ Add Location",
                on_click=open_create_modal,
            ).style("background-color: var(--ht-accent); color: var(--ht-text-on-accent)")

        columns: list[dict] = [
            {"name": "name", "label": "Name", "field": "name", "sortable": True},
            {"name": "type", "label": "Type", "field": "type", "sortable": True},
            {"name": "rack", "label": "Rack", "field": "rack"},
            {"name": "row", "label": "Row", "field": "row"},
            {"name": "lat", "label": "Lat", "field": "lat"},
            {"name": "lng", "label": "Lng", "field": "lng"},
            {"name": "parent", "label": "Parent", "field": "parent"},
            {"name": "actions", "label": "Actions", "field": "actions"},
        ]

        table = ui.table(
            columns=columns,
            rows=[],
            row_key="id",
        ).classes("w-full").style("background-color: var(--ht-bg-surface-raised)")

        table.add_slot(
            "body-cell-actions",
            """
            <q-td :props="props">
              <q-btn flat dense icon="edit" size="sm"
                @click="$parent.$emit('edit', props.row)" />
              <q-btn flat dense icon="delete" size="sm" color="negative"
                @click="$parent.$emit('delete_row', props.row)" />
            </q-td>
            """,
        )
        table.on("edit", lambda e: open_edit_modal(e.args))
        table.on(
            "delete_row",
            lambda e: ui.timer(
                0,
                lambda: confirm_delete(e.args["id"], e.args["name"]),
                once=True,
            ),
        )

    modal = create_location_modal(form=form, on_submit=submit_form)

    await load_locations()
