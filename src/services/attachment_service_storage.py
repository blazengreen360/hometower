"""Attachment service file storage helpers."""

from pathlib import Path
import shutil
import uuid

from src.models.attachment import DeviceAttachment
from src.utils.logger import logger
from src.utils.settings import settings

_THUMBNAIL_SUFFIX = "_thumb.png"
_CANVAS_STAGING_DIR = ".canvas-undo-staging"


def storage_root() -> Path:
    return Path(settings.attachments_root)


def _device_dir(device_id: uuid.UUID) -> Path:
    return storage_root() / str(device_id)


def _staged_device_dir(device_id: uuid.UUID, stash_id: uuid.UUID) -> Path:
    return storage_root() / _CANVAS_STAGING_DIR / str(stash_id) / str(device_id)


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


def _move_tree(source: Path, destination: Path) -> bool:
    if not source.exists():
        return False
    if destination.exists():
        raise OSError(f"Destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(destination))
    return True


def _prune_empty_stage_dirs(staged_dir: Path) -> None:
    staging_root = storage_root() / _CANVAS_STAGING_DIR
    current = staged_dir.parent
    while current != staging_root and current.exists():
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent
    try:
        staging_root.rmdir()
    except OSError:
        return


def stage_device_storage(device_id: uuid.UUID, stash_id: uuid.UUID) -> bool:
    return _move_tree(_device_dir(device_id), _staged_device_dir(device_id, stash_id))


def restore_staged_device_storage(device_id: uuid.UUID, stash_id: uuid.UUID) -> bool:
    staged_dir = _staged_device_dir(device_id, stash_id)
    restored = _move_tree(staged_dir, _device_dir(device_id))
    if restored:
        _prune_empty_stage_dirs(staged_dir)
    return restored


def remove_device_dir_if_empty(device_id: uuid.UUID) -> None:
    directory = _device_dir(device_id)
    try:
        directory.rmdir()
    except OSError:
        return


def cleanup_device_storage(device_id: uuid.UUID) -> None:
    directory = _device_dir(device_id)
    try:
        shutil.rmtree(directory)
    except FileNotFoundError:
        return
    except OSError as exc:
        logger.warning("Attachment cleanup failed for {}: {}", directory, str(exc))