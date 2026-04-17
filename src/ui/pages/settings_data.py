"""Settings — Data management page at /settings/data (HT-012, HT-013).

Export button triggers authenticated browser download via fetch.
Import section requires Admin role and a confirmation dialog.
"""
import html
import json

import httpx
from nicegui import app as nicegui_app
from nicegui import ui

from src.models.types import Role
from src.ui.components.app_shell import app_shell
from src.ui.components.auth_guard import (
    get_ui_role,
    redirect_if_unauthenticated,
)
from src.utils.logger import logger
from src.utils.settings import settings

_IMPORT_URL = f"{settings.api_base_url}/api/import"

def _export_download_js(token: str) -> str:
    """Return JS for authenticated export download.

    Uses same-origin ``/api/export`` to avoid host-mismatch cookie issues and
    includes Bearer fallback for sessions that rely on storage token state.
    """
    bearer = f"Bearer {token}" if token else ""
    return f"""
        (async () => {{
            const authHeader = {json.dumps(bearer)};
            const headers = {{}};
            if (authHeader) {{
                headers.Authorization = authHeader;
            }}

            const showError = (message) => {{
                const existing = document.getElementById('ht-export-error');
                if (existing) existing.remove();

                const banner = document.createElement('div');
                banner.id = 'ht-export-error';
                banner.setAttribute('role', 'alert');
                banner.style.cssText =
                    'position:fixed;top:16px;right:16px;max-width:420px;'
                    + 'padding:12px 14px;border-radius:8px;z-index:100000;'
                    + 'background:#842029;color:#ffffff;box-shadow:0 6px 18px rgba(0,0,0,0.25);'
                    + 'font-size:14px;line-height:1.4;';
                banner.textContent = message;
                document.body.appendChild(banner);

                window.setTimeout(() => {{
                    if (banner.parentNode) banner.parentNode.removeChild(banner);
                }}, 6000);
            }};

            try {{
                const response = await fetch('/api/export', {{
                    method: 'GET',
                    credentials: 'include',
                    headers,
                }});

                if (!response.ok) {{
                    if (response.status === 401) {{
                        showError('Export failed: your session may have expired. Please sign in again.');
                        return;
                    }}
                    if (response.status === 403) {{
                        showError('Export failed: your account does not have permission to export data.');
                        return;
                    }}
                    if (response.status >= 500) {{
                        showError('Backup failed: the server could not create the export. Please try again.');
                        return;
                    }}
                    showError(`Backup failed (${{response.status}}). Please try again.`);
                    return;
                }}

                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const anchor = document.createElement('a');
                anchor.href = url;
                anchor.download = 'hometower-export.json';
                document.body.appendChild(anchor);
                anchor.click();
                anchor.remove();
                URL.revokeObjectURL(url);
            }} catch (_error) {{
                showError('Backup failed: network error while contacting the server.');
            }}
        }})();
    """


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
        ui.label("Settings — Data").classes("text-2xl font-bold")

        # ── Export section ──────────────────────────────────────────────────
        with ui.card().classes("w-full"):
            ui.label("Export Data").classes("text-lg font-semibold mb-2")
            ui.label(
                "Generates a full JSON backup of all devices, connections, "
                "locations, tags, diagram layouts, and users."
            ).classes("text-sm mb-1")
            ui.label("Requires: Contributor or higher").classes("text-xs text-gray-500 mb-4")
            if role in (Role.Admin, Role.Contributor):
                ui.button(
                    "Export JSON",
                    icon="download",
                    on_click=lambda: ui.run_javascript(_export_download_js(token)),
                ).props("color=primary")
            else:
                ui.button(
                    "Export JSON",
                    icon="download",
                ).props("color=primary disable")
                ui.label(
                    "Export is unavailable for your role. Contributor or higher is required."
                ).classes("text-xs text-gray-500 mt-2")

        # ── Import section (Admin only) ─────────────────────────────────────
        if role == Role.Admin:
            _render_import_section(token)


def _render_import_section(token: str) -> None:
    """Render the Admin-only import card."""
    selected_file: dict[str, object] = {}

    with ui.card().classes("w-full"):
        ui.label("Import Data").classes("text-lg font-semibold mb-2")
        with ui.row().classes("items-center gap-2 mb-2"):
            ui.icon("warning", color="orange")
            ui.label(
                "This will permanently replace ALL existing data."
            ).classes("text-sm font-medium text-orange-700")
        ui.label(
            "Import from a .json file previously exported from Hometower."
        ).classes("text-sm mb-3")

        import_btn = ui.button("Import JSON", icon="upload").props(
            "color=negative disabled"
        )

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
        ).props("accept=.json").classes("w-full mb-2")

        async def _confirm_and_import() -> None:
            with ui.dialog() as dialog, ui.card():
                ui.label(
                    "This will permanently replace ALL existing data. "
                    "Type CONFIRM to proceed."
                ).classes("text-sm font-medium mb-3")
                confirm_input = ui.input(placeholder="CONFIRM").classes("w-full mb-3")
                with ui.row().classes("gap-2"):
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

                    ui.button("Proceed", on_click=do_import).props("color=negative")
                    ui.button("Cancel", on_click=dialog.close).props("flat")
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
