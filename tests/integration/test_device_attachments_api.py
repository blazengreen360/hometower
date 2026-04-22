"""Integration tests for HT-042 device attachments API."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import uuid

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session

from src.models.types import Role
from src.models.user import User
from src.utils.auth import create_jwt, hash_password
from src.utils.settings import settings



def _png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGBA", (2, 2), (0, 120, 255, 255)).save(output, format="PNG")
    return output.getvalue()


_PNG_BYTES = _png_bytes()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_user(session: Session, role: Role) -> tuple[User, str]:
    user = User(
        username=f"attachments_{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:8]}@attachments.local",
        password_hash=hash_password("x"),
        role=role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    token = create_jwt(
        {"sub": str(user.id), "role": role.value, "version": user.token_version}
    )
    return user, token


def _create_device(client: TestClient, token: str) -> str:
    response = client.post(
        "/api/devices/",
        json={"name": f"attachment-{uuid.uuid4().hex[:8]}", "type": "Server"},
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


@pytest.fixture
def attachment_root(tmp_path: Path) -> Path:
    original = settings.attachments_root
    root = tmp_path / "attachments"
    settings.attachments_root = str(root)
    try:
        yield root
    finally:
        settings.attachments_root = original


class TestDeviceAttachmentsApi:
    def test_contributor_uploads_image_and_can_list_preview_and_download(
        self,
        client: TestClient,
        contributor_token: str,
        attachment_root: Path,
    ) -> None:
        device_id = _create_device(client, contributor_token)

        upload_response = client.post(
            f"/api/devices/{device_id}/attachments",
            files={"file": ("rack.png", _PNG_BYTES, "image/png")},
            headers=_auth(contributor_token),
        )
        assert upload_response.status_code == 201, upload_response.text
        attachment = upload_response.json()
        assert attachment["filename"] == "rack.png"
        assert attachment["is_image"] is True
        assert attachment["has_thumbnail"] is True

        list_response = client.get(
            f"/api/devices/{device_id}/attachments",
            headers=_auth(contributor_token),
        )
        assert list_response.status_code == 200, list_response.text
        assert len(list_response.json()) == 1

        preview_response = client.get(
            f"/api/devices/{device_id}/attachments/{attachment['id']}/preview",
            headers=_auth(contributor_token),
        )
        assert preview_response.status_code == 200
        assert preview_response.headers["content-type"].startswith("image/png")
        assert preview_response.headers["x-content-type-options"] == "nosniff"
        assert "inline" in preview_response.headers["content-disposition"]

        thumbnail_response = client.get(
            f"/api/devices/{device_id}/attachments/{attachment['id']}/thumbnail",
            headers=_auth(contributor_token),
        )
        assert thumbnail_response.status_code == 200
        assert thumbnail_response.headers["content-type"].startswith("image/png")

        download_response = client.get(
            f"/api/devices/{device_id}/attachments/{attachment['id']}/download",
            headers=_auth(contributor_token),
        )
        assert download_response.status_code == 200
        assert download_response.headers["x-content-type-options"] == "nosniff"
        assert "attachment" in download_response.headers["content-disposition"]

        stored_dir = attachment_root / device_id
        assert stored_dir.exists()
        assert len(list(stored_dir.iterdir())) == 2

    def test_foreign_device_attachment_access_returns_404(
        self,
        client: TestClient,
        session: Session,
        attachment_root: Path,
    ) -> None:
        _, owner_token = _make_user(session, Role.Contributor)
        _, foreign_reader_token = _make_user(session, Role.Reader)
        _, foreign_contributor_token = _make_user(session, Role.Contributor)

        device_id = _create_device(client, owner_token)
        upload_response = client.post(
            f"/api/devices/{device_id}/attachments",
            files={"file": ("rack.png", _PNG_BYTES, "image/png")},
            headers=_auth(owner_token),
        )
        assert upload_response.status_code == 201, upload_response.text
        attachment_id = upload_response.json()["id"]

        list_response = client.get(
            f"/api/devices/{device_id}/attachments",
            headers=_auth(foreign_reader_token),
        )
        assert list_response.status_code == 404

        download_response = client.get(
            f"/api/devices/{device_id}/attachments/{attachment_id}/download",
            headers=_auth(foreign_reader_token),
        )
        assert download_response.status_code == 404

        preview_response = client.get(
            f"/api/devices/{device_id}/attachments/{attachment_id}/preview",
            headers=_auth(foreign_reader_token),
        )
        assert preview_response.status_code == 404

        upload_foreign_response = client.post(
            f"/api/devices/{device_id}/attachments",
            files={"file": ("reader.txt", b"hello", "text/plain")},
            headers=_auth(foreign_contributor_token),
        )
        assert upload_foreign_response.status_code == 404

        delete_response = client.delete(
            f"/api/devices/{device_id}/attachments/{attachment_id}",
            headers=_auth(foreign_contributor_token),
        )
        assert delete_response.status_code == 404

    def test_reader_cannot_upload_or_delete_attachments(
        self,
        client: TestClient,
        contributor_token: str,
        reader_token: str,
        attachment_root: Path,
    ) -> None:
        device_id = _create_device(client, contributor_token)
        created = client.post(
            f"/api/devices/{device_id}/attachments",
            files={"file": ("notes.txt", b"hello", "text/plain")},
            headers=_auth(contributor_token),
        )
        assert created.status_code == 201, created.text
        attachment_id = created.json()["id"]

        upload_response = client.post(
            f"/api/devices/{device_id}/attachments",
            files={"file": ("reader.txt", b"hello", "text/plain")},
            headers=_auth(reader_token),
        )
        delete_response = client.delete(
            f"/api/devices/{device_id}/attachments/{attachment_id}",
            headers=_auth(reader_token),
        )

        assert upload_response.status_code == 403
        assert delete_response.status_code == 403

    def test_upload_enforces_size_type_and_count_limits(
        self,
        client: TestClient,
        contributor_token: str,
        attachment_root: Path,
    ) -> None:
        device_id = _create_device(client, contributor_token)

        too_large = client.post(
            f"/api/devices/{device_id}/attachments",
            files={"file": ("big.txt", b"x" * (10 * 1024 * 1024 + 1), "text/plain")},
            headers=_auth(contributor_token),
        )
        assert too_large.status_code == 413
        assert too_large.json()["detail"] == "File too large (max 10 MB)"

        bad_type = client.post(
            f"/api/devices/{device_id}/attachments",
            files={"file": ("virus.exe", b"MZ", "application/octet-stream")},
            headers=_auth(contributor_token),
        )
        assert bad_type.status_code == 422
        assert bad_type.json()["detail"] == "File type not allowed"

        for index in range(20):
            response = client.post(
                f"/api/devices/{device_id}/attachments",
                files={"file": (f"file-{index}.txt", b"ok", "text/plain")},
                headers=_auth(contributor_token),
            )
            assert response.status_code == 201, response.text

        over_limit = client.post(
            f"/api/devices/{device_id}/attachments",
            files={"file": ("overflow.txt", b"ok", "text/plain")},
            headers=_auth(contributor_token),
        )
        assert over_limit.status_code == 422
        assert over_limit.json()["detail"] == "Maximum 20 attachments per device"

    def test_upload_rejects_svg_attachments(
        self,
        client: TestClient,
        contributor_token: str,
        attachment_root: Path,
    ) -> None:
        device_id = _create_device(client, contributor_token)

        svg_response = client.post(
            f"/api/devices/{device_id}/attachments",
            files={
                "file": (
                    "diagram.svg",
                    b"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1 1'></svg>",
                    "image/svg+xml",
                )
            },
            headers=_auth(contributor_token),
        )

        assert svg_response.status_code == 422
        assert svg_response.json()["detail"] == "File type not allowed"

    def test_delete_device_cleans_attachments_from_disk(
        self,
        client: TestClient,
        contributor_token: str,
        attachment_root: Path,
    ) -> None:
        device_id = _create_device(client, contributor_token)

        created = client.post(
            f"/api/devices/{device_id}/attachments",
            files={"file": ("rack.png", _PNG_BYTES, "image/png")},
            headers=_auth(contributor_token),
        )
        assert created.status_code == 201, created.text
        assert (attachment_root / device_id).exists()

        delete_response = client.delete(
            f"/api/devices/{device_id}",
            headers=_auth(contributor_token),
        )
        assert delete_response.status_code == 204, delete_response.text
        assert not (attachment_root / device_id).exists()

    def test_canvas_delete_device_with_attachments_returns_snapshot(
        self,
        client: TestClient,
        contributor_token: str,
        attachment_root: Path,
        test_engine,
    ) -> None:
        device_id = _create_device(client, contributor_token)

        upload_response = client.post(
            f"/api/devices/{device_id}/attachments",
            files={"file": ("rack.png", _PNG_BYTES, "image/png")},
            headers=_auth(contributor_token),
        )
        assert upload_response.status_code == 201, upload_response.text
        assert (attachment_root / device_id).exists()

        pragma_connection = test_engine.raw_connection()
        pragma_connection.execute("PRAGMA foreign_keys=ON")
        pragma_connection.commit()
        pragma_connection.close()
        try:
            delete_response = client.post(
                f"/api/devices/{device_id}/canvas-delete",
                headers=_auth(contributor_token),
            )
        finally:
            reset_connection = test_engine.raw_connection()
            reset_connection.execute("PRAGMA foreign_keys=OFF")
            reset_connection.commit()
            reset_connection.close()

        assert delete_response.status_code == 200, delete_response.text
        assert delete_response.json()["snapshot"]["device"]["id"] == device_id

    def test_restore_canvas_deleted_device_restores_attachment_files(
        self,
        client: TestClient,
        contributor_token: str,
        attachment_root: Path,
        test_engine,
    ) -> None:
        device_id = _create_device(client, contributor_token)

        upload_response = client.post(
            f"/api/devices/{device_id}/attachments",
            files={"file": ("rack.png", _PNG_BYTES, "image/png")},
            headers=_auth(contributor_token),
        )
        assert upload_response.status_code == 201, upload_response.text
        attachment = upload_response.json()

        pragma_connection = test_engine.raw_connection()
        pragma_connection.execute("PRAGMA foreign_keys=ON")
        pragma_connection.commit()
        pragma_connection.close()
        try:
            delete_response = client.post(
                f"/api/devices/{device_id}/canvas-delete",
                headers=_auth(contributor_token),
            )
        finally:
            reset_connection = test_engine.raw_connection()
            reset_connection.execute("PRAGMA foreign_keys=OFF")
            reset_connection.commit()
            reset_connection.close()

        assert delete_response.status_code == 200, delete_response.text
        assert not (attachment_root / device_id).exists()

        restore_response = client.post(
            f"/api/devices/{device_id}/restore",
            json=delete_response.json()["snapshot"],
            headers=_auth(contributor_token),
        )
        assert restore_response.status_code == 200, restore_response.text
        assert (attachment_root / device_id).exists()

        list_response = client.get(
            f"/api/devices/{device_id}/attachments",
            headers=_auth(contributor_token),
        )
        assert list_response.status_code == 200, list_response.text
        assert [row["id"] for row in list_response.json()] == [attachment["id"]]

        download_response = client.get(
            f"/api/devices/{device_id}/attachments/{attachment['id']}/download",
            headers=_auth(contributor_token),
        )
        assert download_response.status_code == 200, download_response.text
        assert download_response.content == _PNG_BYTES