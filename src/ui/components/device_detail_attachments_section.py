"""Attachments section renderer for the device detail panel (HT-042)."""
import html
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
import uuid

import httpx
from nicegui import ui

from src.models.attachment import DeviceAttachmentResponse
from src.ui.design.primitives import card_section
from src.ui.design.primitives import card_surface
from src.ui.design.primitives import danger_button
from src.ui.design.primitives import secondary_button
from src.ui.components.device_detail_attachments_helpers import (
    _ACCEPT_EXTENSIONS,
    extract_upload_bytes as _extract_upload_bytes,
    format_file_size as _format_file_size,
    response_detail as _response_detail,
    run_on_change as _run_on_change,
    render_file_attachments,
    render_image_attachments,
)
from src.ui.components.toast import show_toast
from src.utils.logger import logger
from src.utils.settings import settings


def render_attachments_section(
    device_id: uuid.UUID,
    attachments: list[DeviceAttachmentResponse],
    token: str,
    is_editor: bool,
    on_change: Callable[[], None] | Callable[[], Awaitable[None]],
) -> None:
    """Render image thumbnails, file links, upload, and delete actions."""
    image_attachments = [attachment for attachment in attachments if attachment.is_image]
    file_attachments = [attachment for attachment in attachments if not attachment.is_image]

    if is_editor:
        ui.label("Up to 20 files, 10 MB each.").style(
            "font-size:0.75rem; color:var(--ht-text-secondary);"
        )

        async def _upload_attachment(e: object) -> None:
            upload_file = getattr(e, "file", None)
            filename = str(
                getattr(upload_file, "name", "")
                or getattr(e, "name", "")
                or ""
            )
            file_bytes = await _extract_upload_bytes(
                upload_file if upload_file is not None else getattr(e, "content", None)
            )
            if not filename or file_bytes is None:
                show_toast(type="error", title="Unable to read uploaded file")
                return
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{settings.api_base_url}/api/devices/{device_id}/attachments",
                        files={"file": (filename, file_bytes, "application/octet-stream")},
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=30.0,
                    )
            except httpx.HTTPError as exc:
                logger.error("Attachment upload failed: {}", str(exc))
                show_toast(type="error", title="Connection error")
                return

            if response.status_code == 201:
                show_toast(type="success", title="Attachment uploaded")
                await _run_on_change(on_change)
                return
            show_toast(type="error", title=_response_detail(response))

        ui.upload(
            label="Upload attachments",
            on_upload=_upload_attachment,
            auto_upload=True,
        ).props(f"accept={_ACCEPT_EXTENSIONS}").classes("w-full")

    if not attachments:
        ui.label("No attachments").style(
            "font-size:0.875rem; color:var(--ht-text-secondary);"
        )
        return

    def _render_delete_action(attachment: DeviceAttachmentResponse) -> None:
        if not is_editor:
            return

        confirm_dlg = ui.dialog()

        async def _delete_attachment(
            target: DeviceAttachmentResponse = attachment,
            dialog=confirm_dlg,
        ) -> None:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.delete(
                        f"{settings.api_base_url}/api/devices/{device_id}/attachments/{target.id}",
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=10.0,
                    )
            except httpx.HTTPError as exc:
                logger.error("Attachment delete failed: {}", str(exc))
                show_toast(type="error", title="Connection error")
                return

            if response.status_code != 204:
                show_toast(type="error", title=_response_detail(response))
                return

            dialog.close()
            show_toast(type="success", title="Attachment deleted")
            await _run_on_change(on_change)

        with confirm_dlg:
            with card_surface(ui.card()).classes("min-w-[320px]"):
                with card_section(ui.column()):
                    ui.label(f"Delete {html.escape(attachment.filename)}?").classes("ht-section-title")
                    with ui.row().classes("justify-end gap-2"):
                        secondary_button(ui.button("Cancel", on_click=confirm_dlg.close))
                        danger_button(ui.button("Delete", on_click=_delete_attachment))

        ui.button(icon="delete", on_click=lambda dlg=confirm_dlg: dlg.open()).props(
            "flat dense round size=sm aria-label='Delete attachment'"
        ).classes("text-[var(--ht-error)]")

    if image_attachments:
        render_image_attachments(device_id, image_attachments, _render_delete_action, ui)

    if file_attachments:
        render_file_attachments(device_id, file_attachments, _render_delete_action, ui)
