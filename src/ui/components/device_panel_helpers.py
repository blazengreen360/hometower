"""Helper renderers for the device detail panel."""
from collections.abc import Awaitable, Callable
import html
import uuid
from typing import Optional

import httpx
from nicegui import ui

from src.utils.logger import logger
from src.utils.settings import settings


def _parse_nullable_non_negative_int(raw: object) -> tuple[object, str | None]:
    if raw is None:
        return None, None

    cleaned = str(raw).strip()
    if cleaned == "":
        return None, None

    try:
        value = int(cleaned)
    except ValueError:
        return None, "Power must be a whole number 0 or greater"

    if value < 0:
        return None, "Power must be 0 or greater"

    return value, None


def render_editable_row(
    label: str,
    current: Optional[str],
    field: str,
    device_id: uuid.UUID,
    token: str,
    is_editor: bool,
    version: int,
    on_saved: Callable[[], None] | None = None,
    save_value: Callable[[Optional[str]], Awaitable[bool]] | None = None,
) -> None:
    """Render a label:value row with optional inline edit for Contributors."""
    with ui.row().classes("items-center gap-1 w-full"):
        ui.label(f"{label}:").style(
            "font-size:0.875rem; color:var(--ht-text-secondary); min-width:44px; flex-shrink:0;"
        )
        val_lbl = ui.label(html.escape(current or "\u2014")).style(
            "font-size:0.875rem; color:var(--ht-text-primary); flex:1; word-break:break-all;"
        )
        if not is_editor:
            return

        with ui.row().classes("items-center gap-1").style("display:none") as edit_row:
            inp = (
                ui.input(value=current or "")
                .props(f'dense aria-label="Edit {label}"')
                .style("font-size:0.8125rem; flex:1;")
            )

            async def _legacy_direct_patch(new_val: Optional[str]) -> bool:
                try:
                    async with httpx.AsyncClient() as c:
                        r = await c.patch(
                            f"{settings.api_base_url}/api/devices/{device_id}",
                            json={field: new_val, "version": version},
                            headers={"Authorization": f"Bearer {token}"},
                            timeout=5.0,
                        )
                    if r.status_code == 200:
                        ui.notify(f"{label} updated")
                        return True
                    ui.notify(f"Save failed ({r.status_code})", type="negative")
                    return False
                except httpx.HTTPError as exc:
                    logger.error("Inline save {}: {}", field, str(exc))
                    ui.notify("Connection error", type="negative")
                    return False

            async def _save() -> None:
                new_val: Optional[str] = inp.value.strip() or None
                if save_value is not None:
                    ok = await save_value(new_val)
                else:
                    ok = await _legacy_direct_patch(new_val)
                if ok:
                    val_lbl.set_text(html.escape(new_val or "\u2014"))
                    if on_saved is not None:
                        on_saved()
                val_lbl.set_visibility(True)
                edit_row.style("display:none")

            def _cancel() -> None:
                val_lbl.set_visibility(True)
                edit_row.style("display:none")

            ui.button(icon="check", on_click=_save).props(
                "flat dense round size=xs"
            ).style("color:var(--ht-success);")
            ui.button(icon="close", on_click=_cancel).props(
                "flat dense round size=xs"
            ).style("color:var(--ht-error);")

        def _start() -> None:
            inp.set_value(current or "")
            val_lbl.set_visibility(False)
            edit_row.style("display:flex")

        ui.button(icon="edit", on_click=_start).props(
            f'flat dense round size=xs aria-label="Edit {label}"'
        ).style("color:var(--ht-text-secondary);")


def render_editable_int_row(
    label: str,
    current: Optional[int],
    device_id: uuid.UUID,
    token: str,
    is_editor: bool,
    version: int,
    on_saved: Callable[[], None] | None = None,
    save_value: Callable[[object], Awaitable[bool]] | None = None,
) -> None:
    """Render an inline-editable integer row where an empty value maps to null."""
    with ui.row().classes("items-center gap-1 w-full"):
        ui.label(f"{label}:").style(
            "font-size:0.875rem; color:var(--ht-text-secondary); min-width:72px; flex-shrink:0;"
        )
        val_lbl = ui.label("\u2014" if current is None else str(current)).style(
            "font-size:0.875rem; color:var(--ht-text-primary); flex:1;"
        )
        if not is_editor:
            return

        with ui.row().classes("items-center gap-1").style("display:none") as edit_row:
            inp = (
                ui.input(value="" if current is None else str(current))
                .props(f'inputmode=numeric dense aria-label="Edit {label}"')
                .style("font-size:0.8125rem; flex:1;")
            )

            async def _legacy_direct_patch(new_val: object) -> bool:
                try:
                    async with httpx.AsyncClient() as c:
                        r = await c.patch(
                            f"{settings.api_base_url}/api/devices/{device_id}",
                            json={"power_watts": new_val, "version": version},
                            headers={"Authorization": f"Bearer {token}"},
                            timeout=5.0,
                        )
                    if r.status_code == 200:
                        ui.notify(f"{label} updated")
                        return True
                    ui.notify(f"Save failed ({r.status_code})", type="negative")
                    return False
                except httpx.HTTPError as exc:
                    logger.error("Inline save power_watts: {}", str(exc))
                    ui.notify("Connection error", type="negative")
                    return False

            async def _save() -> None:
                next_value, error_message = _parse_nullable_non_negative_int(inp.value)
                if error_message is not None:
                    ui.notify(error_message, type="negative")
                    return

                if save_value is not None:
                    ok = await save_value(next_value)
                else:
                    ok = await _legacy_direct_patch(next_value)

                if ok:
                    val_lbl.set_text("\u2014" if next_value is None else str(next_value))
                    if on_saved is not None:
                        on_saved()
                val_lbl.set_visibility(True)
                edit_row.style("display:none")

            def _cancel() -> None:
                val_lbl.set_visibility(True)
                edit_row.style("display:none")

            ui.button(icon="check", on_click=_save).props(
                "flat dense round size=xs"
            ).style("color:var(--ht-success);")
            ui.button(icon="close", on_click=_cancel).props(
                "flat dense round size=xs"
            ).style("color:var(--ht-error);")

        def _start() -> None:
            inp.set_value("" if current is None else str(current))
            val_lbl.set_visibility(False)
            edit_row.style("display:flex")

        ui.button(icon="edit", on_click=_start).props(
            f'flat dense round size=xs aria-label="Edit {label}"'
        ).style("color:var(--ht-text-secondary);")
