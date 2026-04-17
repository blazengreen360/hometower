"""Attachment service payload validation helpers."""

import io
import json
from pathlib import Path
import zipfile

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
MAX_ATTACHMENTS_PER_DEVICE = 20
THUMBNAIL_SIZE = (150, 150)

_ALLOWED_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "webp",
    "gif",
    "pdf",
    "txt",
    "md",
    "csv",
    "json",
    "yaml",
    "yml",
    "doc",
    "docx",
    "xls",
    "xlsx",
}
_PIL_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
_OLE_HEADER = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

_CONTENT_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "gif": "image/gif",
    "pdf": "application/pdf",
    "txt": "text/plain",
    "md": "text/markdown",
    "csv": "text/csv",
    "json": "application/json",
    "yaml": "application/yaml",
    "yml": "application/yaml",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def normalize_filename(filename: str) -> str:
    name = Path(filename or "").name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="File type not allowed")
    return name[:255]


def extension_for_filename(filename: str) -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=422, detail="File type not allowed")
    return ext


def _decode_text(raw: bytes) -> str:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="File type not allowed") from exc

    disallowed_controls = [
        char for char in text if ord(char) < 32 and char not in "\n\r\t\f"
    ]
    if disallowed_controls:
        raise HTTPException(status_code=422, detail="File type not allowed")
    return text


def _validate_image_payload(raw: bytes, ext: str) -> str:
    expected_formats = {
        "jpg": {"JPEG"},
        "jpeg": {"JPEG"},
        "png": {"PNG"},
        "webp": {"WEBP"},
        "gif": {"GIF"},
    }
    try:
        with Image.open(io.BytesIO(raw)) as image:
            actual_format = (image.format or "").upper()
            image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise HTTPException(status_code=422, detail="File type not allowed") from exc

    if actual_format not in expected_formats[ext]:
        raise HTTPException(status_code=422, detail="File type not allowed")
    return _CONTENT_TYPES[ext]


def _validate_openxml_payload(raw: bytes, ext: str) -> str:
    required_prefix = "word/" if ext == "docx" else "xl/"
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names = set(archive.namelist())
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=422, detail="File type not allowed") from exc

    if "[Content_Types].xml" not in names or not any(
        name.startswith(required_prefix) for name in names
    ):
        raise HTTPException(status_code=422, detail="File type not allowed")
    return _CONTENT_TYPES[ext]


def validate_content_type(filename: str, raw: bytes) -> str:
    ext = extension_for_filename(filename)
    if ext in _PIL_IMAGE_EXTENSIONS:
        return _validate_image_payload(raw, ext)
    if ext == "pdf":
        if not raw.startswith(b"%PDF-"):
            raise HTTPException(status_code=422, detail="File type not allowed")
        return _CONTENT_TYPES[ext]
    if ext == "json":
        text = _decode_text(raw)
        try:
            json.loads(text)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail="File type not allowed") from exc
        return _CONTENT_TYPES[ext]
    if ext in {"txt", "md", "csv", "yaml", "yml"}:
        _decode_text(raw)
        return _CONTENT_TYPES[ext]
    if ext in {"docx", "xlsx"}:
        return _validate_openxml_payload(raw, ext)
    if ext in {"doc", "xls"}:
        if not raw.startswith(_OLE_HEADER):
            raise HTTPException(status_code=422, detail="File type not allowed")
        return _CONTENT_TYPES[ext]
    raise HTTPException(status_code=422, detail="File type not allowed")


def build_thumbnail_bytes(raw: bytes, ext: str) -> bytes | None:
    if ext not in _PIL_IMAGE_EXTENSIONS:
        return None
    try:
        with Image.open(io.BytesIO(raw)) as opened_image:
            image: Image.Image = ImageOps.exif_transpose(opened_image)
            image.thumbnail(THUMBNAIL_SIZE)
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            output = io.BytesIO()
            image.save(output, format="PNG")
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise HTTPException(status_code=422, detail="File type not allowed") from exc
    return output.getvalue()


def is_image_content_type(content_type: str) -> bool:
    return content_type.startswith("image/") and content_type != "image/svg+xml"