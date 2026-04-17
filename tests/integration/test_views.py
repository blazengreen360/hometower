"""Integration tests for /api/topologies/{id}/views/ and backward compat with /api/diagrams/."""
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


def _setup_workspace_and_topology(
    client: TestClient, token: str,
) -> tuple[str, str]:
    """Create a workspace + topology and return (workspace_id, topology_id)."""
    ws = client.post(
        "/api/workspaces/", json={"name": "VWS"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    t = client.post(
        f"/api/workspaces/{ws['id']}/topologies/",
        json={"name": "VT"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    return str(ws["id"]), str(t["id"])


_EMPTY_CANVAS: dict[str, object] = {"elements": {"nodes": [], "edges": []}}


class TestViewCreate:
    def test_create_view_under_topology(
        self, client: TestClient, session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        _, topo_id = _setup_workspace_and_topology(client, token)
        resp = client.post(
            f"/api/topologies/{topo_id}/views/",
            json={"name": "Top View", "cytoscape_json": _EMPTY_CANVAS},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Top View"
        assert data["topology_id"] == topo_id

    def test_reader_cannot_create_view(
        self, client: TestClient, session: Session,
    ) -> None:
        _, contrib_token = _make_user(session, Role.Contributor)
        _, reader_token = _make_user(session, Role.Reader)
        _, topo_id = _setup_workspace_and_topology(client, contrib_token)
        resp = client.post(
            f"/api/topologies/{topo_id}/views/",
            json={"name": "Nope", "cytoscape_json": _EMPTY_CANVAS},
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code in (403, 404)


class TestViewList:
    def test_list_views_in_topology(
        self, client: TestClient, session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        _, topo_id = _setup_workspace_and_topology(client, token)
        client.post(
            f"/api/topologies/{topo_id}/views/",
            json={"name": "V1", "cytoscape_json": _EMPTY_CANVAS},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = client.get(
            f"/api/topologies/{topo_id}/views/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        names = [i["name"] for i in data["items"]]
        assert "V1" in names

    def test_list_views_empty_topology(
        self, client: TestClient, session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        _, topo_id = _setup_workspace_and_topology(client, token)
        resp = client.get(
            f"/api/topologies/{topo_id}/views/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


class TestBackwardCompat:
    def test_existing_diagrams_endpoint_still_works(
        self, client: TestClient, contributor_token: str,
    ) -> None:
        """POST /api/diagrams/ without topology_id should still work and auto-bind topology."""
        resp = client.post(
            "/api/diagrams/",
            json={"name": "Legacy", "cytoscape_json": {"elements": [{"data": {"id": "n1"}}]}},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Legacy"
        assert data.get("topology_id") is not None

    def test_diagrams_list_includes_topology_id(
        self, client: TestClient, session: Session, contributor_token: str,
    ) -> None:
        """GET /api/diagrams/ should include topology_id in summaries."""
        _, token = _make_user(session, Role.Contributor)
        _, topo_id = _setup_workspace_and_topology(client, token)
        client.post(
            f"/api/topologies/{topo_id}/views/",
            json={"name": "WithTopo", "cytoscape_json": _EMPTY_CANVAS},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = client.get(
            "/api/diagrams/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        topo_items = [i for i in items if i.get("topology_id") == topo_id]
        assert len(topo_items) >= 1
