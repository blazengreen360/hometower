"""Integration tests for /api/workspaces/{id}/topologies/ and /api/topologies/ endpoints."""
import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from src.models.types import Role
from src.models.user import User
from src.utils.auth import create_jwt, hash_password


def _make_user(session: Session, role: Role = Role.Contributor) -> tuple[User, str]:
    user = User(
        username=f"u_{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:8]}@test.local",
        password_hash=hash_password("x"),
        role=role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    token = create_jwt({"sub": str(user.id), "role": role.value, "version": user.token_version})
    return user, token


def _create_workspace(client: TestClient, token: str, name: str = "WS") -> dict[str, object]:
    resp = client.post(
        "/api/workspaces/", json={"name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()


class TestTopologyCreate:
    def test_contributor_can_create_topology(
        self, client: TestClient, session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        ws = _create_workspace(client, token)
        resp = client.post(
            f"/api/workspaces/{ws['id']}/topologies/",
            json={"name": "Home Lab"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Home Lab"
        assert data["workspace_id"] == ws["id"]

    def test_reader_cannot_create_topology(
        self, client: TestClient, session: Session,
    ) -> None:
        _, contrib_token = _make_user(session, Role.Contributor)
        _, reader_token = _make_user(session, Role.Reader)
        ws = _create_workspace(client, contrib_token)
        resp = client.post(
            f"/api/workspaces/{ws['id']}/topologies/",
            json={"name": "Nope"},
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code in (403, 404)

    def test_duplicate_name_in_workspace_returns_409(
        self, client: TestClient, session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        ws = _create_workspace(client, token)
        client.post(
            f"/api/workspaces/{ws['id']}/topologies/",
            json={"name": "Dup"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = client.post(
            f"/api/workspaces/{ws['id']}/topologies/",
            json={"name": "Dup"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409

    def test_create_with_tags(
        self, client: TestClient, session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        ws = _create_workspace(client, token)
        resp = client.post(
            f"/api/workspaces/{ws['id']}/topologies/",
            json={"name": "Tagged", "tags": ["prod", "core"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["tags"] == ["prod", "core"]


class TestTopologyList:
    def test_list_topologies_in_workspace(
        self, client: TestClient, session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        ws = _create_workspace(client, token)
        client.post(
            f"/api/workspaces/{ws['id']}/topologies/",
            json={"name": "T1"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = client.get(
            f"/api/workspaces/{ws['id']}/topologies/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        names = [i["name"] for i in data["items"]]
        assert "T1" in names


class TestTopologyGet:
    def test_get_topology_detail(
        self, client: TestClient, session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        ws = _create_workspace(client, token)
        create_resp = client.post(
            f"/api/workspaces/{ws['id']}/topologies/",
            json={"name": "Detail"},
            headers={"Authorization": f"Bearer {token}"},
        )
        t_id = create_resp.json()["id"]
        resp = client.get(
            f"/api/topologies/{t_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Detail"


class TestTopologyRename:
    def test_rename_topology(
        self, client: TestClient, session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        ws = _create_workspace(client, token)
        t = client.post(
            f"/api/workspaces/{ws['id']}/topologies/",
            json={"name": "Old"},
            headers={"Authorization": f"Bearer {token}"},
        ).json()
        resp = client.patch(
            f"/api/topologies/{t['id']}",
            json={"name": "New"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New"

    def test_update_tags(
        self, client: TestClient, session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        ws = _create_workspace(client, token)
        t = client.post(
            f"/api/workspaces/{ws['id']}/topologies/",
            json={"name": "TagTest"},
            headers={"Authorization": f"Bearer {token}"},
        ).json()
        resp = client.patch(
            f"/api/topologies/{t['id']}",
            json={"tags": ["new-tag"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["tags"] == ["new-tag"]


class TestTopologyDelete:
    def test_admin_can_delete_topology(
        self, client: TestClient, session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Admin)
        ws = _create_workspace(client, token)
        t = client.post(
            f"/api/workspaces/{ws['id']}/topologies/",
            json={"name": "ToDelete"},
            headers={"Authorization": f"Bearer {token}"},
        ).json()
        resp = client.delete(
            f"/api/topologies/{t['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 204

    def test_contributor_cannot_delete_topology(
        self, client: TestClient, session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        ws = _create_workspace(client, token)
        t = client.post(
            f"/api/workspaces/{ws['id']}/topologies/",
            json={"name": "NoDel"},
            headers={"Authorization": f"Bearer {token}"},
        ).json()
        resp = client.delete(
            f"/api/topologies/{t['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_delete_cascade_removes_views(
        self, client: TestClient, session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Admin)
        ws = _create_workspace(client, token)
        t = client.post(
            f"/api/workspaces/{ws['id']}/topologies/",
            json={"name": "CascadeT"},
            headers={"Authorization": f"Bearer {token}"},
        ).json()
        client.post(
            f"/api/topologies/{t['id']}/views/",
            json={"name": "V1", "cytoscape_json": {"elements": {"nodes": []}}},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = client.delete(
            f"/api/topologies/{t['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 204
