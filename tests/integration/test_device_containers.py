"""Integration tests for device container features (HT-021).

Covers ?include=children, ?include=ancestors enrichment and
export/import parent_id round-trip.
"""
import json
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from src.domain.export import EXPORT_VERSION
from src.models.user import User


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _user_as_payload(user: User) -> dict:  # type: ignore[type-arg]
    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "role": user.role.value,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else _now(),
        "updated_at": user.updated_at.isoformat() if user.updated_at else _now(),
    }


def _valid_payload(**overrides) -> dict:  # type: ignore[type-arg]
    base: dict = {  # type: ignore[type-arg]
        "version": EXPORT_VERSION,
        "exported_at": _now(),
        "devices": [],
        "connections": [],
        "locations": [],
        "tags": [],
        "device_tags": [],
        "custom_fields": [],
        "diagram_layouts": [],
        "services": [],
        "service_dependencies": [],
        "users": [],
    }
    base.update(overrides)
    return base


def _do_import(
    client: TestClient,
    payload: dict,  # type: ignore[type-arg]
    token: str,
    confirm: bool = True,
) -> object:
    content = json.dumps(payload).encode()
    qs = "?confirm=true" if confirm else ""
    return client.post(
        f"/api/import{qs}",
        files={"file": ("export.json", content, "application/json")},
        headers={"Authorization": f"Bearer {token}"},
    )


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# ?include=children / ?include=ancestors
# ---------------------------------------------------------------------------


class TestIncludeChildren:
    def test_include_children_returns_child_devices(
        self, client: TestClient, contributor_token: str
    ) -> None:
        h = _headers(contributor_token)
        parent = client.post(
            "/api/devices/", json={"name": "Parent", "type": "Server"}, headers=h
        )
        assert parent.status_code == 201
        parent_id = parent.json()["id"]

        child = client.post(
            "/api/devices/",
            json={"name": "Child", "type": "Server", "parent_id": parent_id},
            headers=h,
        )
        assert child.status_code == 201

        resp = client.get(
            f"/api/devices/{parent_id}?include=children",
            headers=h,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "children" in data
        assert len(data["children"]) == 1
        assert data["children"][0]["name"] == "Child"

    def test_include_children_empty_when_no_children(
        self, client: TestClient, contributor_token: str
    ) -> None:
        h = _headers(contributor_token)
        device = client.post(
            "/api/devices/", json={"name": "Standalone", "type": "Switch"}, headers=h
        )
        assert device.status_code == 201
        device_id = device.json()["id"]

        resp = client.get(
            f"/api/devices/{device_id}?include=children",
            headers=h,
        )
        assert resp.status_code == 200
        assert resp.json()["children"] == []


class TestIncludeAncestors:
    def test_include_ancestors_returns_parent_chain(
        self, client: TestClient, contributor_token: str
    ) -> None:
        h = _headers(contributor_token)
        grandparent = client.post(
            "/api/devices/", json={"name": "Grandparent", "type": "Server"}, headers=h
        )
        assert grandparent.status_code == 201
        gp_id = grandparent.json()["id"]

        parent = client.post(
            "/api/devices/",
            json={"name": "Parent", "type": "Server", "parent_id": gp_id},
            headers=h,
        )
        assert parent.status_code == 201
        p_id = parent.json()["id"]

        child = client.post(
            "/api/devices/",
            json={"name": "Child", "type": "Server", "parent_id": p_id},
            headers=h,
        )
        assert child.status_code == 201
        child_id = child.json()["id"]

        resp = client.get(
            f"/api/devices/{child_id}?include=ancestors",
            headers=h,
        )
        assert resp.status_code == 200
        chain = resp.json()["parent_chain"]
        # nearest→root: [Parent, Grandparent]
        assert len(chain) == 2
        assert chain[0]["name"] == "Parent"
        assert chain[1]["name"] == "Grandparent"


# ---------------------------------------------------------------------------
# Export includes parent_id
# ---------------------------------------------------------------------------


class TestExportParentId:
    def test_export_includes_parent_id(
        self, client: TestClient, contributor_token: str
    ) -> None:
        h = _headers(contributor_token)
        parent = client.post(
            "/api/devices/", json={"name": "ExParent", "type": "Server"}, headers=h
        )
        assert parent.status_code == 201
        parent_id = parent.json()["id"]

        client.post(
            "/api/devices/",
            json={"name": "ExChild", "type": "Server", "parent_id": parent_id},
            headers=h,
        )

        resp = client.get("/api/export", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        child_export = next(
            (d for d in data["devices"] if d["name"] == "ExChild"), None
        )
        assert child_export is not None
        assert child_export["parent_id"] == parent_id


# ---------------------------------------------------------------------------
# Import parent_id
# ---------------------------------------------------------------------------


class TestImportParentId:
    def test_import_with_parent_id_creates_relationships(
        self, client: TestClient, admin_token: str, admin_user: "User"
    ) -> None:
        parent_id = str(uuid.uuid4())
        child_id = str(uuid.uuid4())
        payload = _valid_payload(
            devices=[
                {
                    "id": parent_id,
                    "name": "ImportParent",
                    "type": "Server",
                    "ip": None, "mac": None, "os": None, "notes": None,
                    "location_id": None, "parent_id": None,
                    "created_at": _now(), "updated_at": _now(),
                },
                {
                    "id": child_id,
                    "name": "ImportChild",
                    "type": "Server",
                    "ip": None, "mac": None, "os": None, "notes": None,
                    "location_id": None, "parent_id": parent_id,
                    "created_at": _now(), "updated_at": _now(),
                },
            ],
            users=[_user_as_payload(admin_user)],
        )
        resp = _do_import(client, payload, admin_token)
        assert resp.status_code == 200

        export_resp = client.get("/api/export", headers=_headers(admin_token))
        assert export_resp.status_code == 200
        exported_child = next(
            device for device in export_resp.json()["devices"] if device["id"] == child_id
        )
        assert exported_child["parent_id"] == parent_id

    def test_import_dangling_parent_id_returns_422(
        self, client: TestClient, admin_token: str
    ) -> None:
        dangling_parent = str(uuid.uuid4())
        payload = _valid_payload(
            devices=[
                {
                    "id": str(uuid.uuid4()),
                    "name": "Orphan",
                    "type": "Server",
                    "ip": None, "mac": None, "os": None, "notes": None,
                    "location_id": None, "parent_id": dangling_parent,
                    "created_at": _now(), "updated_at": _now(),
                },
            ]
        )
        resp = _do_import(client, payload, admin_token)
        assert resp.status_code == 422
