"""Attachment service file storage helpers."""

from pathlib import Path
import shutil
import uuid

from src.models.attachment import DeviceAttachment
from src.utils.logger import logger
from src.utils.settings import settings

_THUMBNAIL_SUFFIX = "_thumb.png"


def storage_root() -> Path:
    return Path(settings.attachments_root)


def relative_path(device_id: uuid.UUID, stored_name: str) -> str:
    return f"{device_id}/{stored_name}"


def resolve_original_path(attachment: DeviceAttachment) -> Path:
    return storage_root() / attachment.stored_path


def resolve_thumbnail_path(attachment: DeviceAttachment) -> Path:
    original_path = resolve_original_path(attachment)
    return build_thumbnail_path(original_path)


def build_thumbnail_path(original_path: Path) -> Path:
    return original_path.with_name(f"{original_path.stem}{_THUMBNAIL_SUFFIX}")


def write_file(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def delete_path(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Attachment cleanup failed for {}: {}", path, str(exc))


def remove_device_dir_if_empty(device_id: uuid.UUID) -> None:
    directory = storage_root() / str(device_id)
    try:
        directory.rmdir()
    except OSError:
        return


def cleanup_device_storage(device_id: uuid.UUID) -> None:
    directory = storage_root() / str(device_id)
    try:
        shutil.rmtree(directory)
    except FileNotFoundError:
        return
    except OSError as exc:
        logger.warning("Attachment cleanup failed for {}: {}", directory, str(exc))