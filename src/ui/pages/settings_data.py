"""Settings — Data management page at /settings/data (HT-012, HT-013).

Export button triggers authenticated browser download via fetch.
Import section requires Admin role and a confirmation dialog.
"""
import html
import httpx
from nicegui import app as nicegui_app
from nicegui import ui

from src.models.types import Role
from src.ui.components.app_shell import app_shell
from src.ui.components.auth_guard import (
    get_ui_role,
    redirect_if_unauthenticated,
)
from src.ui.design.primitives import card_section
from src.ui.design.primitives import card_surface
from src.ui.design.primitives import danger_button
from src.ui.design.primitives import page_container
from src.ui.design.primitives import primary_button
from src.ui.design.primitives import render_page_intro
from src.ui.design.primitives import secondary_button
from src.ui.pages.settings_data_support import export_download_js
from src.utils.logger import logger
from src.utils.settings import settings

_IMPORT_URL = f"{settings.api_base_url}/api/import"


def _export_download_js(token: str) -> str:
    """Backward-compatible wrapper for tests and page code."""
    return export_download_js(token)


def _extract_upload_bytes(raw: object) -> bytes | None:
    """Normalize NiceGUI upload payload into bytes, or None if unreadable."""
    data: object = raw
    reader = getattr(data, "read", None)
    if callable(reader):
        try:
            data = reader()
        except Exception:
            return None
    if isinstance(data, bytes):
        return data
    if isinstance(data, bytearray):
        return bytes(data)
    if isinstance(data, memoryview):
        return data.tobytes()
    if data is None:
        return None
    return None


@ui.page("/settings/data")
async def settings_data_page() -> None:
    """Settings → Data management page. Auth guard: any authenticated user."""
    if redirect_if_unauthenticated(current_path="/settings/data"):
        return

    role = get_ui_role()
    token: str = nicegui_app.storage.user.get("access_token", "")

    with app_shell("Data", "/settings/data", breadcrumb=["Settings", "Data"]):
        with page_container(ui.column()):
            render_page_intro(
                ui,
                "Data",
                "Export a complete JSON backup or replace the environment from a previously captured Hometower export.",
                "Settings",
            )

            # ── Export section ──────────────────────────────────────────────
            with card_surface(ui.card()):
                with card_section(ui.column()):
                    ui.label("Export Data").classes("ht-section-title")
                    ui.label(
                        "Generates a full JSON backup of all devices, connections, "
                        "locations, tags, diagram layouts, and users."
                    ).classes("ht-muted-copy")
                    ui.label("Requires: Contributor or higher").classes("ht-small-copy")
                    if role in (Role.Admin, Role.Contributor):
                        primary_button(ui.button(
                            "Export JSON",
                            icon="download",
                            on_click=lambda: ui.run_javascript(export_download_js(token)),
                        ))
                    else:
                        primary_button(ui.button(
                            "Export JSON",
                            icon="download",
                        )).props("disable")
                        ui.label(
                            "Export is unavailable for your role. Contributor or higher is required."
                        ).classes("ht-small-copy")

            # ── Import section (Admin only) ─────────────────────────────────
            if role == Role.Admin:
                _render_import_section(token)


def _render_import_section(token: str) -> None:
    """Render the Admin-only import card."""
    selected_file: dict[str, object] = {}

    with card_surface(ui.card()):
        with card_section(ui.column()):
            ui.label("Import Data").classes("ht-section-title")
            with ui.row().classes("items-center gap-2"):
                ui.icon("warning").classes("text-[var(--ht-warning)]")
                ui.label(
                    "This will permanently replace ALL existing data."
                ).classes("ht-danger-copy")
            ui.label(
                "Import from a .json file previously exported from Hometower."
            ).classes("ht-muted-copy")

            import_btn = danger_button(ui.button("Import JSON", icon="upload")).props("disabled")

            def on_upload(e: object) -> None:
                selected_file["name"] = getattr(e, "name", "file.json")
                raw = getattr(e, "content", None)
                file_bytes = _extract_upload_bytes(raw)
                if not file_bytes:
                    selected_file["content"] = None
                    ui.notify("Unable to read uploaded file bytes", type="negative")
                    return
                selected_file["content"] = file_bytes
                import_btn.props(remove="disabled")

            ui.upload(
                label="Select export.json",
                on_upload=on_upload,
                auto_upload=True,
            ).props("accept=.json").classes("w-full")

            async def _confirm_and_import() -> None:
                with ui.dialog() as dialog, card_surface(ui.card()).classes("min-w-[360px]"):
                    with card_section(ui.column()):
                        ui.label(
                            "This will permanently replace ALL existing data. "
                            "Type CONFIRM to proceed."
                        ).classes("ht-muted-copy")
                        confirm_input = ui.input(placeholder="CONFIRM").classes("w-full").props("outlined")
                        with ui.row().classes("gap-2 justify-end"):
                            async def do_import() -> None:
                                if confirm_input.value != "CONFIRM":
                                    ui.notify("Type CONFIRM to proceed", type="warning")
                                    return
                                raw = selected_file.get("content")
                                if not isinstance(raw, bytes) or len(raw) == 0:
                                    ui.notify("No valid import file selected", type="negative")
                                    return
                                dialog.close()
                                await _run_import(token, raw)

                            danger_button(ui.button("Proceed", on_click=do_import))
                            secondary_button(ui.button("Cancel", on_click=dialog.close))
                dialog.open()

            import_btn.on("click", _confirm_and_import)


async def _run_import(token: str, content: bytes) -> None:
    """POST the file bytes to /api/import and show result notification."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{_IMPORT_URL}?confirm=true",
                files={"file": ("export.json", content, "application/json")},
                headers={"Authorization": f"Bearer {token}"},
                timeout=30.0,
            )
        if resp.status_code == 200:
            summary = resp.json()
            msg = (
                f"Import successful — "
                f"{summary.get('devices', 0)} devices, "
                f"{summary.get('connections', 0)} connections"
            )
            ui.notify(msg, type="positive")
            ui.navigate.reload()
        else:
            detail = resp.json().get("detail", resp.text) if resp.headers.get(
                "content-type", ""
            ).startswith("application/json") else resp.text
            ui.notify(
                f"Import failed ({resp.status_code}): {html.escape(str(detail))}",
                type="negative",
            )
    except httpx.HTTPError as exc:
        logger.error("import HTTP error: {e}", e=str(exc))
        ui.notify("Connection error during import", type="negative")
