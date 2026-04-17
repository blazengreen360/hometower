"""Custom fields section renderer for the device detail panel."""
import html
import uuid
from collections.abc import Callable
from typing import Optional

import httpx
from nicegui import ui

from src.models.custom_field import CustomFieldResponse
from src.utils.logger import logger
from src.utils.settings import settings


def render_custom_fields_section(
    device_id: uuid.UUID,
    fields: list[CustomFieldResponse],
    token: str,
    is_editor: bool,
    on_change: Callable[[], None],
) -> None:
    """Key-value rows with inline edit and delete for Contributors."""
    if not fields and not is_editor:
        ui.label("No custom fields").style(
            "font-size:0.875rem; color:var(--ht-text-secondary);"
        )
        return

    for cf in fields:
        with ui.row().classes("items-center gap-1 w-full"):
            ui.label(f"{html.escape(cf.key)}:").style(
                "font-size:0.875rem; color:var(--ht-text-secondary); "
                "min-width:72px; flex-shrink:0; word-break:break-all;"
            )
            val_lbl = ui.label(html.escape(cf.value or "\u2014")).style(
                "font-size:0.875rem; color:var(--ht-text-primary); flex:1; word-break:break-all;"
            )
            if not is_editor:
                continue

            with ui.row().classes("items-center gap-0").style("display:none") as erow:
                inp = (
                    ui.input(value=cf.value or "")
                    .props("dense")
                    .style("font-size:0.8125rem; flex:1;")
                )

                async def _save_cf(
                    cf_id: uuid.UUID = cf.id,
                    vl: object = val_lbl,
                    er: object = erow,
                    i: object = inp,
                ) -> None:
                    new_val: Optional[str] = getattr(i, "value", "")
                    try:
                        async with httpx.AsyncClient() as c:
                            await c.patch(
                                f"{settings.api_base_url}/api/devices/{device_id}"
                                f"/custom-fields/{cf_id}",
                                json={"value": new_val},
                                headers={"Authorization": f"Bearer {token}"},
                                timeout=5.0,
                            )
                        getattr(vl, "set_text")(html.escape(new_val or "\u2014"))
                        ui.notify("Field updated", type="positive")
                    except httpx.HTTPError as exc:
                        logger.error("CF save: {}", str(exc))
                        ui.notify("Connection error", type="negative")
                    getattr(vl, "set_visibility")(True)
                    getattr(er, "style")("display:none")

                def _cancel_cf(vl: object = val_lbl, er: object = erow) -> None:
                    getattr(vl, "set_visibility")(True)
                    getattr(er, "style")("display:none")

                ui.button(icon="check", on_click=_save_cf).props(
                    "flat dense round size=xs"
                ).style("color:var(--ht-success);")
                ui.button(icon="close", on_click=_cancel_cf).props(
                    "flat dense round size=xs"
                ).style("color:var(--ht-error);")

            def _start_cf(
                vl: object = val_lbl,
                er: object = erow,
                i: object = inp,
                v: str = cf.value or "",
            ) -> None:
                getattr(i, "set_value")(v)
                getattr(vl, "set_visibility")(False)
                getattr(er, "style")("display:flex")

            confirm_dlg = ui.dialog()

            async def _delete_cf(cf_id: uuid.UUID = cf.id, dlg=confirm_dlg) -> None:
                try:
                    async with httpx.AsyncClient() as c:
                        await c.delete(
                            f"{settings.api_base_url}/api/devices/{device_id}"
                            f"/custom-fields/{cf_id}",
                            headers={"Authorization": f"Bearer {token}"},
                            timeout=5.0,
                        )
                except httpx.HTTPError as exc:
                    logger.error("CF delete: {}", str(exc))
                    ui.notify("Connection error", type="negative")
                    return
                dlg.close()
                on_change()

            with confirm_dlg:
                with ui.card().style("min-width:300px"):
                    ui.label(f"Delete custom field '{html.escape(cf.key)}'?").style(
                        "font-weight:600;"
                    )
                    with ui.row().classes("justify-end gap-2"):
                        ui.button("Delete", on_click=_delete_cf).props(
                            "color=negative"
                        )
                        ui.button("Cancel", on_click=confirm_dlg.close).props("flat")

            ui.button(icon="edit", on_click=_start_cf).props(
                "flat dense round size=xs aria-label='Edit field'"
            ).style("color:var(--ht-text-secondary);")
            ui.button(icon="delete", on_click=lambda dlg=confirm_dlg: dlg.open()).props(
                "flat dense round size=xs aria-label='Delete field'"
            ).style("color:var(--ht-error);")

    if not is_editor:
        return

    ui.separator()
    with ui.row().classes("items-center gap-1 w-full"):
        key_inp = (
            ui.input(placeholder="Key")
            .props("dense")
            .style("flex:1; font-size:0.8125rem;")
        )
        val_inp = (
            ui.input(placeholder="Value")
            .props("dense")
            .style("flex:1; font-size:0.8125rem;")
        )

        async def _add_field() -> None:
            key = key_inp.value.strip()
            val = val_inp.value.strip()
            if not key:
                ui.notify("Key required", type="warning")
                return
            try:
                async with httpx.AsyncClient() as c:
                    r = await c.post(
                        f"{settings.api_base_url}/api/devices/{device_id}/custom-fields",
                        json={"key": key, "value": val},
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=5.0,
                    )
                if r.status_code == 409:
                    ui.notify("Key already exists", type="warning")
                    return
                key_inp.set_value("")
                val_inp.set_value("")
                on_change()
            except httpx.HTTPError as exc:
                logger.error("CF add: {}", str(exc))
                ui.notify("Connection error", type="negative")

        ui.button(icon="add", on_click=_add_field).props(
            "flat dense round aria-label='Add field'"
        ).style("color:var(--ht-accent);")
