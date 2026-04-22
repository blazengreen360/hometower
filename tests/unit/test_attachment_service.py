"""Unit tests for attachment service validation and cleanup."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import uuid

import pytest
from fastapi import HTTPException
from PIL import Image
from sqlmodel import Session

from src.models.device import Device
from src.models.types import DeviceType
from src.services import attachment_service
from src.utils.settings import Settings, settings



def _png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGBA", (2, 2), (255, 0, 0, 255)).save(output, format="PNG")
    return output.getvalue()


_PNG_BYTES = _png_bytes()


@pytest.fixture
def attachment_root(tmp_path: Path) -> Path:
    original = settings.attachments_root
    root = tmp_path / "attachments"
    settings.attachments_root = str(root)
    try:
        yield root
    finally:
        settings.attachments_root = original


def _create_device(session: Session) -> uuid.UUID:
    device = Device(name="Attachment Test", type=DeviceType.Server)
    session.add(device)
    session.commit()
    session.refresh(device)
    return device.id


def test_upload_rejects_svg_payload(
    session: Session,
    attachment_root: Path,
) -> None:
    device_id = _create_device(session)

    with pytest.raises(HTTPException) as exc:
        attachment_service.upload(
            device_id,
            "diagram.svg",
            b"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1 1'></svg>",
            session,
        )

    assert exc.value.status_code == 422
    assert exc.value.detail == "File type not allowed"


def test_upload_rejects_mismatched_extension_payload(
    session: Session,
    attachment_root: Path,
) -> None:
    device_id = _create_device(session)

    with pytest.raises(HTTPException) as exc:
        attachment_service.upload(device_id, "photo.jpg", b"%PDF-1.7", session)

    assert exc.value.status_code == 422
    assert exc.value.detail == "File type not allowed"


def test_delete_all_for_device_removes_files_and_rows(
    session: Session,
    attachment_root: Path,
) -> None:
    device_id = _create_device(session)

    attachment_service.upload(device_id, "photo.png", _PNG_BYTES, session)
    attachment_service.upload(device_id, "notes.txt", b"hello", session)

    deleted_count = attachment_service.delete_all_for_device(
        device_id,
        session,
        commit=True,
    )

    assert deleted_count == 2
    assert attachment_service.list_for_device(device_id, session) == []
    assert not (attachment_root / str(device_id)).exists()


def test_delete_all_for_device_without_commit_keeps_files_until_outer_commit(
    session: Session,
    attachment_root: Path,
) -> None:
    device_id = _create_device(session)

    attachment_service.upload(device_id, "photo.png", _PNG_BYTES, session)
    attachment_service.upload(device_id, "notes.txt", b"hello", session)

    deleted_count = attachment_service.delete_all_for_device(
        device_id,
        session,
        commit=False,
    )

    assert deleted_count == 2
    assert (attachment_root / str(device_id)).exists()


def test_settings_default_attachment_root_targets_persistent_volume() -> None:
    config = Settings(
        database_url="sqlite://",
        secret_key="x" * 32,
        admin_email="admin@test.local",
        admin_password="strong_test_password_123",
    )

    assert config.attachments_root == "/data/attachments"