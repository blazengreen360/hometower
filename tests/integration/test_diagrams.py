"""Integration tests for /api/diagrams/ CRUD endpoints and RBAC."""
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session

from src.models.diagram import DiagramLayout
from src.models.types import Role
from src.models.user import User
from src.utils.auth import create_jwt, hash_password

LAYOUT_PAYLOAD: dict[str, object] = {
    "name": "My Homelab",
    "cytoscape_json": {
        "elements": [
            {"data": {"id": "n1", "label": "Server-1"}, "position": {"x": 100, "y": 200}},
        ],
        "zoom": 1.0,
        "pan": {"x": 0, "y": 0},
    },
}


def _make_user(session: Session, role: Role = Role.Contributor) -> tuple[User, str]:
    user = User(
        username=f"u_{uuid4().hex[:8]}",
        email=f"{uuid4().hex[:8]}@test.local",
        password_hash=hash_password("x"),
        role=role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    token = create_jwt({"sub": str(user.id), "role": role.value, "version": user.token_version})
    return user, token


def _create_workspace_and_topology(
    client: TestClient,
    token: str,
) -> tuple[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    ws_resp = client.post(
        "/api/workspaces/",
        json={"name": f"WS-{uuid4().hex[:8]}"},
        headers=headers,
    )
    assert ws_resp.status_code == 201
    workspace_id = ws_resp.json()["id"]

    topo_resp = client.post(
        f"/api/workspaces/{workspace_id}/topologies/",
        json={"name": f"TOPO-{uuid4().hex[:8]}"},
        headers=headers,
    )
    assert topo_resp.status_code == 201
    topology_id = topo_resp.json()["id"]
    return workspace_id, topology_id


class TestCreateDiagram:
    def test_contributor_can_save_layout_returns_201(
        self, client: TestClient, contributor_token: str
    ) -> None:
        response = client.post(
            "/api/diagrams/",
            json=LAYOUT_PAYLOAD,
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My Homelab"
        assert "id" in data
        assert data["version"] == 1
        assert "created_at" in data
        assert "updated_at" in data
        assert "cytoscape_json" in data
        assert data["cytoscape_json"]["zoom"] == 1.0

    def test_reader_cannot_save_layout_returns_403(
        self, client: TestClient, reader_token: str
    ) -> None:
        response = client.post(
            "/api/diagrams/",
            json=LAYOUT_PAYLOAD,
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 403


class TestListDiagrams:
    def test_owner_can_list_diagrams_returns_200(
        self, client: TestClient, contributor_token: str
    ) -> None:
        client.post(
            "/api/diagrams/",
            json=LAYOUT_PAYLOAD,
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        response = client.get(
            "/api/diagrams/",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert data["total"] >= 1
        assert data["page"] == 1
        assert data["limit"] == 50

    def test_list_returns_summaries_without_cytoscape_json(
        self, client: TestClient, contributor_token: str
    ) -> None:
        client.post(
            "/api/diagrams/",
            json=LAYOUT_PAYLOAD,
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        response = client.get(
            "/api/diagrams/",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) >= 1
        for item in items:
            assert "cytoscape_json" not in item
            assert "name" in item
            assert "id" in item
            assert "created_at" in item
            assert "updated_at" in item


class TestGetDiagram:
    def test_owner_can_get_diagram_by_id_with_full_json(
        self, client: TestClient, contributor_token: str
    ) -> None:
        create_resp = client.post(
            "/api/diagrams/",
            json=LAYOUT_PAYLOAD,
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert create_resp.status_code == 201
        diagram_id = create_resp.json()["id"]

        response = client.get(
            f"/api/diagrams/{diagram_id}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "My Homelab"
        assert data["version"] == 1
        assert "cytoscape_json" in data
        assert data["cytoscape_json"]["zoom"] == 1.0

    def test_get_nonexistent_diagram_returns_404(
        self, client: TestClient, reader_token: str
    ) -> None:
        response = client.get(
            f"/api/diagrams/{uuid4()}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 404


class TestUpdateDiagram:
    def test_contributor_can_update_existing_layout_returns_200(
        self, client: TestClient, contributor_token: str
    ) -> None:
        create_resp = client.post(
            "/api/diagrams/",
            json={"name": "Autosave", "cytoscape_json": {"elements": [{"data": {"id": "a"}}]}},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert create_resp.status_code == 201
        created = create_resp.json()
        diagram_id = created["id"]
        version = created["version"]

        update_resp = client.put(
            f"/api/diagrams/{diagram_id}",
            json={
                "name": "Autosave",
                "cytoscape_json": {"elements": [{"data": {"id": "b"}}], "zoom": 2.0},
                "version": version,
            },
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert update_resp.status_code == 200
        payload = update_resp.json()
        assert payload["id"] == diagram_id
        assert payload["name"] == "Autosave"
        assert payload["cytoscape_json"]["zoom"] == 2.0
        assert payload["version"] == version + 1

    def test_update_without_version_returns_422(
        self, client: TestClient, contributor_token: str
    ) -> None:
        create_resp = client.post(
            "/api/diagrams/",
            json=LAYOUT_PAYLOAD,
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert create_resp.status_code == 201
        diagram_id = create_resp.json()["id"]

        update_resp = client.put(
            f"/api/diagrams/{diagram_id}",
            json={
                "name": "No Version",
                "cytoscape_json": {"elements": [{"data": {"id": "b"}}], "zoom": 2.0},
            },
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert update_resp.status_code == 422

    def test_reader_cannot_update_diagram_returns_403(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        create_resp = client.post(
            "/api/diagrams/",
            json=LAYOUT_PAYLOAD,
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert create_resp.status_code == 201
        created = create_resp.json()
        diagram_id = created["id"]
        version = created["version"]

        update_resp = client.put(
            f"/api/diagrams/{diagram_id}",
            json={**LAYOUT_PAYLOAD, "version": version},
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert update_resp.status_code == 403

    def test_unauthenticated_update_diagram_returns_401(
        self, client: TestClient, contributor_token: str
    ) -> None:
        create_resp = client.post(
            "/api/diagrams/",
            json=LAYOUT_PAYLOAD,
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert create_resp.status_code == 201
        created = create_resp.json()
        diagram_id = created["id"]
        version = created["version"]

        update_resp = client.put(
            f"/api/diagrams/{diagram_id}",
            json={**LAYOUT_PAYLOAD, "version": version},
        )
        assert update_resp.status_code == 401

    def test_diagram_update_rejects_stale_version(
        self, client: TestClient, admin_token: str
    ) -> None:
        headers = {"Authorization": f"Bearer {admin_token}"}
        create_resp = client.post(
            "/api/diagrams/",
            json=LAYOUT_PAYLOAD,
            headers=headers,
        )
        assert create_resp.status_code == 201
        diagram_id = create_resp.json()["id"]

        first_update = client.put(
            f"/api/diagrams/{diagram_id}",
            json={
                "name": "v1",
                "cytoscape_json": {"elements": [{"data": {"id": "n1"}}]},
                "version": 1,
            },
            headers=headers,
        )
        assert first_update.status_code == 200

        stale_update = client.put(
            f"/api/diagrams/{diagram_id}",
            json={
                "name": "v2",
                "cytoscape_json": {"elements": [{"data": {"id": "n2"}}]},
                "version": 1,
            },
            headers=headers,
        )
        assert stale_update.status_code == 409
        assert stale_update.json()["detail"] == (
            "Conflict: diagram was modified by another request"
        )


class TestDeleteDiagram:
    def test_admin_can_delete_own_diagram_returns_204(
        self, client: TestClient, admin_token: str
    ) -> None:
        create_resp = client.post(
            "/api/diagrams/",
            json=LAYOUT_PAYLOAD,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert create_resp.status_code == 201
        diagram_id = create_resp.json()["id"]

        response = client.delete(
            f"/api/diagrams/{diagram_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 204

        get_resp = client.get(
            f"/api/diagrams/{diagram_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert get_resp.status_code == 404

    def test_contributor_can_delete_own_diagram_returns_204(
        self, client: TestClient, contributor_token: str
    ) -> None:
        create_resp = client.post(
            "/api/diagrams/",
            json=LAYOUT_PAYLOAD,
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert create_resp.status_code == 201
        diagram_id = create_resp.json()["id"]

        response = client.delete(
            f"/api/diagrams/{diagram_id}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 204

    def test_delete_nonexistent_diagram_returns_404(
        self, client: TestClient, admin_token: str
    ) -> None:
        response = client.delete(
            f"/api/diagrams/{uuid4()}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404


class TestDiagramOwnership:
    def test_contributor_cannot_list_other_users_diagrams(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, owner_token = _make_user(session, Role.Contributor)
        _, intruder_token = _make_user(session, Role.Contributor)
        _, owner_topology_id = _create_workspace_and_topology(client, owner_token)
        _, intruder_topology_id = _create_workspace_and_topology(client, intruder_token)

        owner_headers = {"Authorization": f"Bearer {owner_token}"}
        intruder_headers = {"Authorization": f"Bearer {intruder_token}"}

        owner_create = client.post(
            "/api/diagrams/",
            json={
                "name": "Owner Diagram",
                "cytoscape_json": {"elements": {"nodes": [], "edges": []}},
                "topology_id": owner_topology_id,
            },
            headers=owner_headers,
        )
        assert owner_create.status_code == 201
        owner_diagram_id = owner_create.json()["id"]

        intruder_create = client.post(
            "/api/diagrams/",
            json={
                "name": "Intruder Diagram",
                "cytoscape_json": {"elements": {"nodes": [], "edges": []}},
                "topology_id": intruder_topology_id,
            },
            headers=intruder_headers,
        )
        assert intruder_create.status_code == 201
        intruder_diagram_id = intruder_create.json()["id"]

        list_resp = client.get(
            "/api/diagrams/",
            params={"page": 1, "limit": 10},
            headers=owner_headers,
        )
        assert list_resp.status_code == 200
        visible_ids = [item["id"] for item in list_resp.json()["items"]]
        assert owner_diagram_id in visible_ids
        assert intruder_diagram_id not in visible_ids

    def test_contributor_cannot_get_other_users_diagram(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, owner_token = _make_user(session, Role.Contributor)
        _, intruder_token = _make_user(session, Role.Contributor)
        _, owner_topology_id = _create_workspace_and_topology(client, owner_token)
        owner_headers = {"Authorization": f"Bearer {owner_token}"}
        intruder_headers = {"Authorization": f"Bearer {intruder_token}"}

        create_resp = client.post(
            "/api/diagrams/",
            json={
                "name": "Owner Private Diagram",
                "cytoscape_json": {"elements": {"nodes": [], "edges": []}},
                "topology_id": owner_topology_id,
            },
            headers=owner_headers,
        )
        assert create_resp.status_code == 201
        diagram_id = create_resp.json()["id"]

        get_resp = client.get(
            f"/api/diagrams/{diagram_id}",
            headers=intruder_headers,
        )
        assert get_resp.status_code == 404

    def test_contributor_can_update_and_delete_own_workspace_diagram(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, owner_token = _make_user(session, Role.Contributor)
        _, topology_id = _create_workspace_and_topology(client, owner_token)
        headers = {"Authorization": f"Bearer {owner_token}"}

        create_resp = client.post(
            "/api/diagrams/",
            json={
                "name": "Owned Diagram",
                "cytoscape_json": {"elements": {"nodes": [], "edges": []}},
                "topology_id": topology_id,
            },
            headers=headers,
        )
        assert create_resp.status_code == 201
        created = create_resp.json()
        diagram_id = created["id"]
        version = created["version"]

        update_resp = client.put(
            f"/api/diagrams/{diagram_id}",
            json={
                "name": "Owned Diagram Updated",
                "cytoscape_json": {"elements": {"nodes": [], "edges": []}, "zoom": 1.25},
                "topology_id": topology_id,
                "version": version,
            },
            headers=headers,
        )
        assert update_resp.status_code == 200

        delete_resp = client.delete(
            f"/api/diagrams/{diagram_id}",
            headers=headers,
        )
        assert delete_resp.status_code == 204

    def test_contributor_cannot_update_or_delete_other_users_diagram(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, owner_token = _make_user(session, Role.Contributor)
        _, intruder_token = _make_user(session, Role.Contributor)
        _, topology_id = _create_workspace_and_topology(client, owner_token)
        owner_headers = {"Authorization": f"Bearer {owner_token}"}
        intruder_headers = {"Authorization": f"Bearer {intruder_token}"}

        create_resp = client.post(
            "/api/diagrams/",
            json={
                "name": "Private Diagram",
                "cytoscape_json": {"elements": {"nodes": [], "edges": []}},
                "topology_id": topology_id,
            },
            headers=owner_headers,
        )
        assert create_resp.status_code == 201
        created = create_resp.json()
        diagram_id = created["id"]
        version = created["version"]

        update_resp = client.put(
            f"/api/diagrams/{diagram_id}",
            json={
                "name": "Intruder Update",
                "cytoscape_json": {"elements": {"nodes": [], "edges": []}, "zoom": 2.0},
                "topology_id": topology_id,
                "version": version,
            },
            headers=intruder_headers,
        )
        assert update_resp.status_code == 404

        delete_resp = client.delete(
            f"/api/diagrams/{diagram_id}",
            headers=intruder_headers,
        )
        assert delete_resp.status_code == 404


class TestDiagramLegacyNullTopology:
    def test_create_without_topology_id_binds_to_owner_default_topology(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, owner_token = _make_user(session, Role.Contributor)
        _, intruder_token = _make_user(session, Role.Contributor)
        owner_headers = {"Authorization": f"Bearer {owner_token}"}
        intruder_headers = {"Authorization": f"Bearer {intruder_token}"}

        create_resp = client.post(
            "/api/diagrams/",
            json={
                "name": "Auto-bound Diagram",
                "cytoscape_json": {"elements": {"nodes": [], "edges": []}},
            },
            headers=owner_headers,
        )
        assert create_resp.status_code == 201
        created = create_resp.json()
        assert created["topology_id"] is not None

        intruder_get = client.get(
            f"/api/diagrams/{created['id']}",
            headers=intruder_headers,
        )
        assert intruder_get.status_code == 404

    def test_legacy_null_topology_layout_is_not_visible_in_owner_scoped_apis(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, owner_token = _make_user(session, Role.Contributor)
        _, intruder_token = _make_user(session, Role.Contributor)
        owner_headers = {"Authorization": f"Bearer {owner_token}"}
        intruder_headers = {"Authorization": f"Bearer {intruder_token}"}

        legacy_layout = DiagramLayout(
            name=f"Legacy-Null-{uuid4().hex[:8]}",
            cytoscape_json={"elements": {"nodes": [], "edges": []}},
            topology_id=None,
        )
        session.add(legacy_layout)
        session.commit()
        session.refresh(legacy_layout)

        owner_get = client.get(
            f"/api/diagrams/{legacy_layout.id}",
            headers=owner_headers,
        )
        intruder_get = client.get(
            f"/api/diagrams/{legacy_layout.id}",
            headers=intruder_headers,
        )
        assert owner_get.status_code == 404
        assert intruder_get.status_code == 404

        owner_list = client.get("/api/diagrams/", headers=owner_headers)
        intruder_list = client.get("/api/diagrams/", headers=intruder_headers)
        assert owner_list.status_code == 200
        assert intruder_list.status_code == 200

        owner_visible_ids = {item["id"] for item in owner_list.json()["items"]}
        intruder_visible_ids = {item["id"] for item in intruder_list.json()["items"]}
        assert str(legacy_layout.id) not in owner_visible_ids
        assert str(legacy_layout.id) not in intruder_visible_ids
