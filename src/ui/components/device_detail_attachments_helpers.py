"""Rendering and formatting helpers for the device detail attachments section."""

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
import inspect
from pathlib import Path
from typing import Protocol, Self, cast
import uuid

from src.models.attachment import DeviceAttachmentResponse


class _UiElement(Protocol):
    def style(self, add: str = "") -> Self: ...

    def classes(self, add: str = "") -> Self: ...

    def props(self, add: str = "") -> Self: ...

    def on(self, event: str, handler: Callable[[], object]) -> Self: ...

    def set_text(self, text: str) -> None: ...

    def clear(self) -> None: ...

    def set_visibility(self, visible: bool) -> None: ...

    def open(self) -> None: ...

    def close(self) -> None: ...

    def __enter__(self) -> Self: ...

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None: ...


class _UiModule(Protocol):
    def separator(self, *args: object, **kwargs: object) -> _UiElement: ...

    def label(self, *args: object, **kwargs: object) -> _UiElement: ...

    def dialog(self, *args: object, **kwargs: object) -> _UiElement: ...

    def card(self, *args: object, **kwargs: object) -> _UiElement: ...

    def row(self, *args: object, **kwargs: object) -> _UiElement: ...

    def button(self, *args: object, **kwargs: object) -> _UiElement: ...

    def column(self, *args: object, **kwargs: object) -> _UiElement: ...

    def element(self, *args: object, **kwargs: object) -> _UiElement: ...

    def link(self, *args: object, **kwargs: object) -> _UiElement: ...

    def icon(self, *args: object, **kwargs: object) -> _UiElement: ...

_ACCEPT_EXTENSIONS = ",".join(
    [
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".gif",
        ".pdf",
        ".txt",
        ".md",
        ".csv",
        ".json",
        ".yaml",
        ".yml",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
    ]
)


async def extract_upload_bytes(raw: object) -> bytes | None:
    data: object = raw
    nested_content = getattr(data, "content", None)
    if nested_content is not None and nested_content is not data:
        nested_bytes = await extract_upload_bytes(nested_content)
        if nested_bytes is not None:
            return nested_bytes

    reader = getattr(data, "read", None)
    if callable(reader):
        try:
            data = reader()
            if inspect.isawaitable(data):
                data = await data
        except Exception:
            return None
    if isinstance(data, bytes):
        return data
    if isinstance(data, bytearray):
        return bytes(data)
    if isinstance(data, memoryview):
        return data.tobytes()
    return None


def format_file_size(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{int(size_bytes)} B"


def format_uploaded_at(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d")


def download_url(device_id: uuid.UUID, attachment_id: uuid.UUID) -> str:
    return f"/api/devices/{device_id}/attachments/{attachment_id}/download"


def preview_url(device_id: uuid.UUID, attachment_id: uuid.UUID) -> str:
    return f"/api/devices/{device_id}/attachments/{attachment_id}/preview"


def thumbnail_url(device_id: uuid.UUID, attachment_id: uuid.UUID) -> str:
    return f"/api/devices/{device_id}/attachments/{attachment_id}/thumbnail"


def attachment_icon(filename: str) -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext == "pdf":
        return "picture_as_pdf"
    if ext in {"doc", "docx"}:
        return "description"
    if ext in {"xls", "xlsx", "csv"}:
        return "table_chart"
    if ext in {"json", "yaml", "yml"}:
        return "data_object"
    if ext in {"txt", "md"}:
        return "article"
    return "attach_file"


def response_detail(response: object) -> str:
    try:
        payload = getattr(response, "json")()
    except Exception:
        payload = None
    if isinstance(payload, dict) and payload.get("detail"):
        return str(payload["detail"])
    text = str(getattr(response, "text", "") or "").strip()
    if text:
        return text
    status_code = getattr(response, "status_code", "unknown")
    return f"Request failed ({status_code})"


async def run_on_change(on_change: Callable[[], object]) -> None:
    result = on_change()
    if inspect.isawaitable(result):
        await result


def render_image_attachments(
    device_id: uuid.UUID,
    image_attachments: list[DeviceAttachmentResponse],
    render_delete_action: Callable[[DeviceAttachmentResponse], None],
    ui_module: object,
) -> None:
    ui_api = cast(_UiModule, ui_module)
    ui_api.separator()
    ui_api.label("Images").style("font-size:0.875rem; font-weight:600;")

    lightbox_state = {"index": 0}
    with ui_api.dialog() as lightbox:
        with ui_api.card().classes("w-full").style(
            "max-width:95vw; background:var(--ht-bg-surface-raised);"
        ):
            with ui_api.row().classes("justify-between items-center w-full"):
                lightbox_title = ui_api.label("").style(
                    "font-size:1rem; font-weight:600; color:var(--ht-text-primary);"
                )
                ui_api.button(icon="close", on_click=lightbox.close).props(
                    "flat dense aria-label='Close image preview'"
                )
            lightbox_image = ui_api.column().classes("w-full items-center gap-2")
            lightbox_meta = ui_api.label("").style(
                "font-size:0.8125rem; color:var(--ht-text-secondary);"
            )
            lightbox_download = ui_api.row().classes("w-full justify-end")
            with ui_api.row().classes("w-full justify-between items-center"):
                prev_btn = ui_api.button(icon="chevron_left").props(
                    "flat dense aria-label='Previous image'"
                )
                next_btn = ui_api.button(icon="chevron_right").props(
                    "flat dense aria-label='Next image'"
                )

    def _render_lightbox() -> None:
        current = image_attachments[lightbox_state["index"]]
        lightbox_title.set_text(current.filename)
        lightbox_meta.set_text(
            f"{format_file_size(current.size_bytes)} • {format_uploaded_at(current.created_at)}"
        )
        lightbox_image.clear()
        lightbox_download.clear()
        with lightbox_image:
            ui_api.element("img").props(
                f'src="{preview_url(device_id, current.id)}"'
            ).style(
                "max-width:90vw; max-height:70vh; width:auto; height:auto; object-fit:contain; border-radius:12px;"
            )
        with lightbox_download:
            ui_api.link("Download", download_url(device_id, current.id)).props(
                'target="_blank"'
            ).style("font-size:0.875rem; color:var(--ht-accent);")

    def _step_lightbox(delta: int) -> None:
        lightbox_state["index"] = (lightbox_state["index"] + delta) % len(image_attachments)
        _render_lightbox()

    prev_btn.on("click", lambda: _step_lightbox(-1))
    next_btn.on("click", lambda: _step_lightbox(1))
    prev_btn.set_visibility(len(image_attachments) > 1)
    next_btn.set_visibility(len(image_attachments) > 1)

    def _open_lightbox(index: int) -> None:
        lightbox_state["index"] = index
        _render_lightbox()
        lightbox.open()

    with ui_api.row().classes("w-full flex-wrap gap-3"):
        for index, attachment in enumerate(image_attachments):
            thumb_src = (
                thumbnail_url(device_id, attachment.id)
                if attachment.has_thumbnail
                else preview_url(device_id, attachment.id)
            )
            with ui_api.column().style("width:150px; gap:6px;"):
                with ui_api.button(on_click=lambda idx=index: _open_lightbox(idx)).props(
                    "flat dense no-caps"
                ).style("padding:0; width:150px; min-height:0;"):
                    ui_api.element("img").props(f'src="{thumb_src}"').style(
                        "width:150px; height:150px; object-fit:cover; border-radius:12px;"
                    )
                ui_api.link(attachment.filename, download_url(device_id, attachment.id)).props(
                    'target="_blank"'
                ).style(
                    "font-size:0.75rem; color:var(--ht-accent); word-break:break-all;"
                )
                ui_api.label(
                    f"{format_file_size(attachment.size_bytes)} • {format_uploaded_at(attachment.created_at)}"
                ).style("font-size:0.75rem; color:var(--ht-text-secondary);")
                render_delete_action(attachment)


def render_file_attachments(
    device_id: uuid.UUID,
    file_attachments: list[DeviceAttachmentResponse],
    render_delete_action: Callable[[DeviceAttachmentResponse], None],
    ui_module: object,
) -> None:
    ui_api = cast(_UiModule, ui_module)
    ui_api.separator()
    ui_api.label("Files").style("font-size:0.875rem; font-weight:600;")
    for attachment in file_attachments:
        with ui_api.row().classes("w-full items-center justify-between gap-2").style(
            "padding:4px 0;"
        ):
            with ui_api.row().classes("items-center gap-2"):
                ui_api.icon(attachment_icon(attachment.filename)).style(
                    "color:var(--ht-text-secondary);"
                )
                with ui_api.column().classes("gap-0"):
                    ui_api.link(
                        attachment.filename,
                        download_url(device_id, attachment.id),
                    ).props('target="_blank"').style(
                        "font-size:0.875rem; color:var(--ht-accent); word-break:break-all;"
                    )
                    ui_api.label(
                        f"{format_file_size(attachment.size_bytes)} • {format_uploaded_at(attachment.created_at)}"
                    ).style(
                        "font-size:0.75rem; color:var(--ht-text-secondary);"
                    )
            render_delete_action(attachment)