"""Integration tests for the Tag system (HT-006).

Covers: CRUD, attach/detach, idempotency, 409 duplicate name,
GET /api/tags device_count, GET /api/devices/{id}?include=tags enriched response.

NOTE: Tag names must be unique within the test session (LOWER(name) unique index).
Each test uses uuid-based names to ensure isolation.
"""
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

_DEVICE = {"name": "test-node", "type": "Server"}


def _fresh_tag(color: str = "#4f46e5") -> dict:
    """Return a tag payload with a unique name to avoid constraint conflicts."""
    return {"name": f"tag-{uuid.uuid4().hex[:8]}", "color": color}


def _create_tag(client: TestClient, token: str, tag: dict | None = None) -> dict:
    payload = tag if tag is not None else _fresh_tag()
    resp = client.post(
        "/api/tags/",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_device(client: TestClient, token: str) -> dict:
    resp = client.post(
        "/api/devices/",
        json=_DEVICE,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Tag CRUD
# ---------------------------------------------------------------------------


class TestTagCreate:
    def test_create_tag_success(
        self, client: TestClient, contributor_token: str
    ) -> None:
        payload = _fresh_tag()
        resp = client.post(
            "/api/tags/",
            json=payload,
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == payload["name"]
        assert data["color"] == payload["color"]
        assert "id" in data
        assert "created_at" in data

    def test_create_tag_duplicate_name_case_insensitive(
        self, client: TestClient, contributor_token: str
    ) -> None:
        payload = _fresh_tag()
        _create_tag(client, contributor_token, payload)
        resp = client.post(
            "/api/tags/",
            json={"name": payload["name"].upper(), "color": "#000000"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 409
        assert resp.json()["detail"] == "Tag name already exists"

    def test_create_tag_invalid_color(
        self, client: TestClient, contributor_token: str
    ) -> None:
        resp = client.post(
            "/api/tags/",
            json={"name": f"tag-{uuid.uuid4().hex[:8]}", "color": "not-a-color"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 422

    def test_create_tag_requires_contributor(
        self, client: TestClient, reader_token: str
    ) -> None:
        resp = client.post(
            "/api/tags/",
            json=_fresh_tag(),
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 403

    def test_create_tag_integrity_error_translated_to_409(
        self, client: TestClient, contributor_token: str
    ) -> None:
        payload = _fresh_tag()
        with patch(
            "src.services.tag_service.tag_repository.create",
            side_effect=IntegrityError(
                "INSERT INTO tags ...",
                {},
                Exception("duplicate key value violates unique constraint ix_tags_name_lower"),
            ),
        ):
            resp = client.post(
                "/api/tags/",
                json=payload,
                headers={"Authorization": f"Bearer {contributor_token}"},
            )
        assert resp.status_code == 409
        assert resp.json()["detail"] == "Tag name already exists"


class TestTagList:
    def test_list_tags_returns_device_count(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        tag = _create_tag(client, contributor_token)
        tag_id = tag["id"]

        list_resp = client.get(
            "/api/tags/",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert list_resp.status_code == 200
        tags = list_resp.json()
        assert isinstance(tags, list)
        found = next((t for t in tags if t["id"] == tag_id), None)
        assert found is not None
        assert "device_count" in found
        assert found["device_count"] == 0

    def test_list_tags_empty_or_has_items(
        self, client: TestClient, reader_token: str
    ) -> None:
        resp = client.get(
            "/api/tags/",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestTagGetById:
    def test_get_tag_success(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        tag = _create_tag(client, contributor_token)
        tag_id = tag["id"]

        resp = client.get(
            f"/api/tags/{tag_id}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == tag_id

    def test_get_tag_not_found(
        self, client: TestClient, reader_token: str
    ) -> None:
        resp = client.get(
            f"/api/tags/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 404


class TestTagUpdate:
    def test_patch_tag_name(
        self, client: TestClient, contributor_token: str
    ) -> None:
        tag = _create_tag(client, contributor_token)
        tag_id = tag["id"]
        new_name = f"renamed-{uuid.uuid4().hex[:8]}"

        resp = client.patch(
            f"/api/tags/{tag_id}",
            json={"name": new_name},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == new_name

    def test_patch_tag_duplicate_name_409(
        self, client: TestClient, contributor_token: str
    ) -> None:
        tag_a = _create_tag(client, contributor_token)
        tag_b = _create_tag(client, contributor_token)

        resp = client.patch(
            f"/api/tags/{tag_b['id']}",
            json={"name": tag_a["name"].upper()},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 409

    def test_patch_tag_not_found(
        self, client: TestClient, contributor_token: str
    ) -> None:
        resp = client.patch(
            f"/api/tags/{uuid.uuid4()}",
            json={"name": f"ghost-{uuid.uuid4().hex[:8]}"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 404

    def test_patch_tag_integrity_error_translated_to_409(
        self, client: TestClient, contributor_token: str
    ) -> None:
        tag = _create_tag(client, contributor_token)
        with patch(
            "src.services.tag_service.tag_repository.update",
            side_effect=IntegrityError(
                "UPDATE tags ...",
                {},
                Exception("duplicate key value violates unique constraint ix_tags_name_lower"),
            ),
        ):
            resp = client.patch(
                f"/api/tags/{tag['id']}",
                json={"name": f"renamed-{uuid.uuid4().hex[:8]}"},
                headers={"Authorization": f"Bearer {contributor_token}"},
            )
        assert resp.status_code == 409
        assert resp.json()["detail"] == "Tag name already exists"


class TestTagDelete:
    def test_delete_tag(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        tag = _create_tag(client, contributor_token)
        tag_id = tag["id"]

        del_resp = client.delete(
            f"/api/tags/{tag_id}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert del_resp.status_code == 204

        get_resp = client.get(
            f"/api/tags/{tag_id}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert get_resp.status_code == 404

    def test_delete_tag_not_found(
        self, client: TestClient, contributor_token: str
    ) -> None:
        resp = client.delete(
            f"/api/tags/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Attach / Detach
# ---------------------------------------------------------------------------


class TestTagAttachDetach:
    def test_attach_tag_to_device(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        tag = _create_tag(client, contributor_token)
        device = _create_device(client, contributor_token)

        resp = client.post(
            f"/api/devices/{device['id']}/tags",
            json={"tag_id": tag["id"]},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 204

        tags_resp = client.get(
            f"/api/devices/{device['id']}/tags",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert tags_resp.status_code == 200
        assert any(t["id"] == tag["id"] for t in tags_resp.json())

    def test_attach_idempotent(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        tag = _create_tag(client, contributor_token)
        device = _create_device(client, contributor_token)
        headers = {"Authorization": f"Bearer {contributor_token}"}

        r1 = client.post(
            f"/api/devices/{device['id']}/tags",
            json={"tag_id": tag["id"]},
            headers=headers,
        )
        r2 = client.post(
            f"/api/devices/{device['id']}/tags",
            json={"tag_id": tag["id"]},
            headers=headers,
        )
        assert r1.status_code == 204
        assert r2.status_code == 204

        tags_resp = client.get(
            f"/api/devices/{device['id']}/tags",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert len([t for t in tags_resp.json() if t["id"] == tag["id"]]) == 1

    def test_detach_tag_from_device(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        tag = _create_tag(client, contributor_token)
        device = _create_device(client, contributor_token)
        headers = {"Authorization": f"Bearer {contributor_token}"}

        client.post(
            f"/api/devices/{device['id']}/tags",
            json={"tag_id": tag["id"]},
            headers=headers,
        )
        del_resp = client.delete(
            f"/api/devices/{device['id']}/tags/{tag['id']}",
            headers=headers,
        )
        assert del_resp.status_code == 204

        tags_resp = client.get(
            f"/api/devices/{device['id']}/tags",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert all(t["id"] != tag["id"] for t in tags_resp.json())

    def test_detach_noop_if_not_attached(
        self, client: TestClient, contributor_token: str
    ) -> None:
        tag = _create_tag(client, contributor_token)
        device = _create_device(client, contributor_token)

        resp = client.delete(
            f"/api/devices/{device['id']}/tags/{tag['id']}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 204

    def test_attach_unknown_device_404(
        self, client: TestClient, contributor_token: str
    ) -> None:
        tag = _create_tag(client, contributor_token)
        resp = client.post(
            f"/api/devices/{uuid.uuid4()}/tags",
            json={"tag_id": tag["id"]},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 404

    def test_attach_unknown_tag_404(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token)
        resp = client.post(
            f"/api/devices/{device['id']}/tags",
            json={"tag_id": str(uuid.uuid4())},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 404

    def test_device_count_increments_on_attach(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        tag = _create_tag(client, contributor_token)
        device = _create_device(client, contributor_token)

        client.post(
            f"/api/devices/{device['id']}/tags",
            json={"tag_id": tag["id"]},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )

        tags_resp = client.get(
            "/api/tags/",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        found = next(t for t in tags_resp.json() if t["id"] == tag["id"])
        assert found["device_count"] == 1


# ---------------------------------------------------------------------------
# GET /api/devices/{id}?include=tags enriched response
# ---------------------------------------------------------------------------


class TestDeviceGetEnriched:
    def test_get_device_without_include_returns_base(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        device = _create_device(client, contributor_token)

        get_resp = client.get(
            f"/api/devices/{device['id']}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert get_resp.status_code == 200
        assert "tags" not in get_resp.json()

    def test_get_device_include_tags_returns_enriched(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        tag = _create_tag(client, contributor_token)
        device = _create_device(client, contributor_token)

        client.post(
            f"/api/devices/{device['id']}/tags",
            json={"tag_id": tag["id"]},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )

        get_resp = client.get(
            f"/api/devices/{device['id']}?include=tags",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert "tags" in data
        assert len(data["tags"]) == 1
        assert data["tags"][0]["id"] == tag["id"]

    def test_get_device_include_tags_empty_when_none_attached(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        device = _create_device(client, contributor_token)

        get_resp = client.get(
            f"/api/devices/{device['id']}?include=tags",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["tags"] == []

    def test_delete_tag_cascades_device_association(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        tag = _create_tag(client, contributor_token)
        device = _create_device(client, contributor_token)

        client.post(
            f"/api/devices/{device['id']}/tags",
            json={"tag_id": tag["id"]},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        client.delete(
            f"/api/tags/{tag['id']}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )

        get_resp = client.get(
            f"/api/devices/{device['id']}?include=tags",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["tags"] == []



