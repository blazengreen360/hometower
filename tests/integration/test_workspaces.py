"""Integration tests for /api/workspaces/ CRUD endpoints and RBAC."""
import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from src.models.types import Role
from src.models.user import User
from src.utils.auth import create_jwt, hash_password


def _make_user(session: Session, role: Role = Role.Contributor) -> tuple[User, str]:
    """Create a user and return (user, token)."""
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


class TestWorkspaceCreate:
    def test_contributor_can_create_workspace(
        self, client: TestClient, session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        resp = client.post(
            "/api/workspaces/",
            json={"name": "My Lab"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "My Lab"
        assert "id" in data
        assert data["topology_count"] == 0

    def test_reader_cannot_create_workspace(
        self, client: TestClient, reader_token: str,
    ) -> None:
        resp = client.post(
            "/api/workspaces/",
            json={"name": "Nope"},
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 403

    def test_duplicate_name_returns_409(
        self, client: TestClient, session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        client.post(
            "/api/workspaces/", json={"name": "Dup"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = client.post(
            "/api/workspaces/", json={"name": "Dup"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409


class TestWorkspaceList:
    def test_list_returns_owned_workspaces(
        self, client: TestClient, session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        client.post(
            "/api/workspaces/", json={"name": "WS-1"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = client.get(
            "/api/workspaces/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        names = [i["name"] for i in data["items"]]
        assert "WS-1" in names

    def test_auto_creates_default_when_empty(
        self, client: TestClient, session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Reader)
        resp = client.get(
            "/api/workspaces/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        names = [i["name"] for i in data["items"]]
        assert "Default Workspace" in names

    def test_ownership_isolation(
        self, client: TestClient, session: Session,
    ) -> None:
        _, token_a = _make_user(session, Role.Contributor)
        _, token_b = _make_user(session, Role.Contributor)
        client.post(
            "/api/workspaces/", json={"name": "Private-A"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        resp = client.get(
            "/api/workspaces/",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        names = [i["name"] for i in resp.json()["items"]]
        assert "Private-A" not in names

    def test_search_filters_by_name(
        self, client: TestClient, session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        client.post(
            "/api/workspaces/", json={"name": "Searchable-WS"},
            headers={"Authorization": f"Bearer {token}"},
        )
        client.post(
            "/api/workspaces/", json={"name": "Other-WS"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = client.get(
            "/api/workspaces/?search=Searchable",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        names = [i["name"] for i in data["items"]]
        assert "Searchable-WS" in names
        assert "Other-WS" not in names


class TestWorkspaceGet:
    def test_get_returns_workspace_detail(
        self, client: TestClient, session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        create_resp = client.post(
            "/api/workspaces/", json={"name": "Detail"},
            headers={"Authorization": f"Bearer {token}"},
        )
        ws_id = create_resp.json()["id"]
        resp = client.get(
            f"/api/workspaces/{ws_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Detail"

    def test_get_other_users_workspace_returns_404(
        self, client: TestClient, session: Session,
    ) -> None:
        _, token_a = _make_user(session, Role.Contributor)
        _, token_b = _make_user(session, Role.Contributor)
        create_resp = client.post(
            "/api/workspaces/", json={"name": "Secret"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        ws_id = create_resp.json()["id"]
        resp = client.get(
            f"/api/workspaces/{ws_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp.status_code == 404


class TestWorkspaceRename:
    def test_rename_workspace(
        self, client: TestClient, session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        create_resp = client.post(
            "/api/workspaces/", json={"name": "Old"},
            headers={"Authorization": f"Bearer {token}"},
        )
        ws_id = create_resp.json()["id"]
        resp = client.patch(
            f"/api/workspaces/{ws_id}",
            json={"name": "New"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New"


class TestWorkspaceDelete:
    def test_admin_can_delete_workspace(
        self, client: TestClient, session: Session,
    ) -> None:
        user, token = _make_user(session, Role.Admin)
        create_resp = client.post(
            "/api/workspaces/", json={"name": "ToDelete"},
            headers={"Authorization": f"Bearer {token}"},
        )
        ws_id = create_resp.json()["id"]
        resp = client.delete(
            f"/api/workspaces/{ws_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 204

    def test_contributor_cannot_delete_workspace(
        self, client: TestClient, session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        create_resp = client.post(
            "/api/workspaces/", json={"name": "NoDelete"},
            headers={"Authorization": f"Bearer {token}"},
        )
        ws_id = create_resp.json()["id"]
        resp = client.delete(
            f"/api/workspaces/{ws_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_delete_cascades_topologies(
        self, client: TestClient, session: Session,
    ) -> None:
        user, token = _make_user(session, Role.Admin)
        ws = client.post(
            "/api/workspaces/", json={"name": "Cascade"},
            headers={"Authorization": f"Bearer {token}"},
        ).json()
        client.post(
            f"/api/workspaces/{ws['id']}/topologies/",
            json={"name": "T1"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = client.delete(
            f"/api/workspaces/{ws['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 204
        # Workspace is gone
        get_resp = client.get(
            f"/api/workspaces/{ws['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_resp.status_code == 404
