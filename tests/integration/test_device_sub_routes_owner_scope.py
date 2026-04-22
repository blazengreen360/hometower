"""Owner-scope regressions for device subroutes."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from src.models.canvas_undo import PublishedDeviceDeleteSnapshot
from src.models.diagram import DiagramLayout
from src.models.types import Role
from src.models.user import User
from src.services.canvas_undo_service_restore_support import _build_restore_token
from src.utils.auth import create_jwt, hash_password


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_user(session: Session, role: Role) -> tuple[User, str]:
    user = User(
        username=f"owner_scope_{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:8]}@owner-scope.local",
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


def _create_device(client: TestClient, token: str, name: str) -> dict[str, object]:
    response = client.post(
        "/api/devices/",
        json={"name": name, "type": "Server"},
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_workspace_and_topology(
    client: TestClient,
    token: str,
) -> tuple[str, str]:
    workspace_response = client.post(
        "/api/workspaces/",
        json={"name": f"ws-{uuid.uuid4().hex[:8]}"},
        headers=_auth(token),
    )
    assert workspace_response.status_code == 201, workspace_response.text
    workspace_id = workspace_response.json()["id"]

    topology_response = client.post(
        f"/api/workspaces/{workspace_id}/topologies/",
        json={"name": f"topo-{uuid.uuid4().hex[:8]}"},
        headers=_auth(token),
    )
    assert topology_response.status_code == 201, topology_response.text
    return workspace_id, topology_response.json()["id"]


def _create_diagram(
    client: TestClient,
    token: str,
    topology_id: str,
    name: str,
    cytoscape_json: dict[str, object],
) -> dict[str, object]:
    response = client.post(
        "/api/diagrams/",
        json={
            "name": name,
            "cytoscape_json": cytoscape_json,
            "topology_id": topology_id,
        },
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_tag(client: TestClient, token: str, name: str) -> dict[str, object]:
    response = client.post(
        "/api/tags/",
        json={"name": name, "color": "#2255aa"},
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_network(client: TestClient, token: str, name: str) -> dict[str, object]:
    response = client.post(
        "/api/networks/",
        json={
            "name": name,
            "vlan_id": 210,
            "cidr": "10.21.0.0/24",
            "gateway": "10.21.0.1",
            "color": "#123456",
        },
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _node_ids(cytoscape_json: dict[str, object]) -> set[str]:
    elements = cytoscape_json.get("elements")
    if not isinstance(elements, list):
        return set()
    return {
        str(data["id"])
        for entry in elements
        if isinstance(entry, dict)
        and entry.get("group") == "nodes"
        and isinstance((data := entry.get("data")), dict)
        and "id" in data
    }


class TestDeviceSubRouteOwnerScope:
    def test_canvas_delete_ignores_foreign_and_hidden_legacy_layouts(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        owner_user, owner_token = _make_user(session, Role.Contributor)
        _, foreign_token = _make_user(session, Role.Contributor)

        device = _create_device(client, owner_token, "owner-delete-scope-device")
        _, owner_topology_id = _create_workspace_and_topology(client, owner_token)
        _, foreign_topology_id = _create_workspace_and_topology(client, foreign_token)

        owner_diagram = _create_diagram(
            client,
            owner_token,
            owner_topology_id,
            "Owner Visible Diagram",
            {
                "elements": [
                    {
                        "group": "nodes",
                        "data": {"id": device["id"], "label": "owner-delete-scope-device"},
                        "position": {"x": 10, "y": 20},
                    }
                ]
            },
        )
        foreign_diagram = _create_diagram(
            client,
            foreign_token,
            foreign_topology_id,
            "Foreign Diagram",
            {
                "elements": [
                    {
                        "group": "nodes",
                        "data": {"id": device["id"], "label": "owner-delete-scope-device"},
                        "position": {"x": 210, "y": 220},
                    }
                ]
            },
        )

        hidden_legacy_layout = DiagramLayout(
            name=f"Legacy-Hidden-{uuid.uuid4().hex[:8]}",
            cytoscape_json={
                "elements": [
                    {
                        "group": "nodes",
                        "data": {"id": device["id"], "label": "owner-delete-scope-device"},
                        "position": {"x": 410, "y": 420},
                    }
                ]
            },
            topology_id=None,
        )
        session.add(hidden_legacy_layout)
        session.commit()
        session.refresh(hidden_legacy_layout)

        delete_response = client.post(
            f"/api/devices/{device['id']}/canvas-delete",
            headers=_auth(owner_token),
        )

        assert delete_response.status_code == 200, delete_response.text
        body = delete_response.json()
        placement_ids = {placement["diagram_id"] for placement in body["snapshot"]["placements"]}
        modified_ids = {diagram["diagram_id"] for diagram in body["modified_diagrams"]}
        assert placement_ids == {owner_diagram["id"]}
        assert modified_ids == {owner_diagram["id"]}

        owner_diagram_response = client.get(
            f"/api/diagrams/{owner_diagram['id']}",
            headers=_auth(owner_token),
        )
        assert owner_diagram_response.status_code == 200
        assert device["id"] not in _node_ids(owner_diagram_response.json()["cytoscape_json"])

        foreign_diagram_response = client.get(
            f"/api/diagrams/{foreign_diagram['id']}",
            headers=_auth(foreign_token),
        )
        assert foreign_diagram_response.status_code == 200
        assert device["id"] in _node_ids(foreign_diagram_response.json()["cytoscape_json"])

        session.refresh(hidden_legacy_layout)
        assert device["id"] in _node_ids(hidden_legacy_layout.cytoscape_json)

    def test_delete_does_not_scrub_hidden_legacy_layouts(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, owner_token = _make_user(session, Role.Contributor)

        device = _create_device(client, owner_token, "owner-delete-legacy-device")
        hidden_legacy_layout = DiagramLayout(
            name=f"Legacy-Delete-{uuid.uuid4().hex[:8]}",
            cytoscape_json={
                "elements": [
                    {
                        "group": "nodes",
                        "data": {
                            "id": device["id"],
                            "label": "owner-delete-legacy-device",
                        },
                        "position": {"x": 510, "y": 520},
                    }
                ]
            },
            topology_id=None,
        )
        session.add(hidden_legacy_layout)
        session.commit()
        session.refresh(hidden_legacy_layout)

        delete_response = client.delete(
            f"/api/devices/{device['id']}",
            headers=_auth(owner_token),
        )

        assert delete_response.status_code == 204, delete_response.text

        session.refresh(hidden_legacy_layout)
        assert device["id"] in _node_ids(hidden_legacy_layout.cytoscape_json)

    def test_foreign_device_tag_routes_return_404(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, owner_token = _make_user(session, Role.Contributor)
        _, foreign_reader_token = _make_user(session, Role.Reader)
        _, foreign_contributor_token = _make_user(session, Role.Contributor)

        device = _create_device(client, owner_token, "owner-tag-device")
        tag = _create_tag(client, owner_token, f"owner-tag-{uuid.uuid4().hex[:8]}")
        attach_response = client.post(
            f"/api/devices/{device['id']}/tags",
            json={"tag_id": tag["id"]},
            headers=_auth(owner_token),
        )
        assert attach_response.status_code == 204, attach_response.text

        list_response = client.get(
            f"/api/devices/{device['id']}/tags",
            headers=_auth(foreign_reader_token),
        )
        assert list_response.status_code == 404

        attach_foreign_response = client.post(
            f"/api/devices/{device['id']}/tags",
            json={"tag_id": tag["id"]},
            headers=_auth(foreign_contributor_token),
        )
        assert attach_foreign_response.status_code == 404

        detach_response = client.delete(
            f"/api/devices/{device['id']}/tags/{tag['id']}",
            headers=_auth(foreign_contributor_token),
        )
        assert detach_response.status_code == 404

    def test_foreign_device_custom_field_and_connection_routes_return_404(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, owner_token = _make_user(session, Role.Contributor)
        _, foreign_reader_token = _make_user(session, Role.Reader)
        _, foreign_contributor_token = _make_user(session, Role.Contributor)

        device = _create_device(client, owner_token, "owner-cf-device")
        other_device = _create_device(client, owner_token, "owner-connection-peer")

        create_cf_response = client.post(
            f"/api/devices/{device['id']}/custom-fields",
            json={"key": "serial", "value": "abc"},
            headers=_auth(owner_token),
        )
        assert create_cf_response.status_code == 201, create_cf_response.text
        custom_field_id = create_cf_response.json()["id"]

        create_connection_response = client.post(
            "/api/connections/",
            json={
                "source_id": device["id"],
                "target_id": other_device["id"],
                "type": "Ethernet",
            },
            headers=_auth(owner_token),
        )
        assert create_connection_response.status_code == 201, create_connection_response.text

        list_cf_response = client.get(
            f"/api/devices/{device['id']}/custom-fields",
            headers=_auth(foreign_reader_token),
        )
        assert list_cf_response.status_code == 404

        list_connections_response = client.get(
            f"/api/devices/{device['id']}/connections",
            headers=_auth(foreign_reader_token),
        )
        assert list_connections_response.status_code == 404

        create_foreign_cf_response = client.post(
            f"/api/devices/{device['id']}/custom-fields",
            json={"key": "asset", "value": "foreign"},
            headers=_auth(foreign_contributor_token),
        )
        assert create_foreign_cf_response.status_code == 404

        update_foreign_cf_response = client.patch(
            f"/api/devices/{device['id']}/custom-fields/{custom_field_id}",
            json={"value": "updated"},
            headers=_auth(foreign_contributor_token),
        )
        assert update_foreign_cf_response.status_code == 404

        delete_foreign_cf_response = client.delete(
            f"/api/devices/{device['id']}/custom-fields/{custom_field_id}",
            headers=_auth(foreign_contributor_token),
        )
        assert delete_foreign_cf_response.status_code == 404

    def test_foreign_device_service_and_network_routes_return_404(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, owner_token = _make_user(session, Role.Contributor)
        _, foreign_reader_token = _make_user(session, Role.Reader)
        _, foreign_contributor_token = _make_user(session, Role.Contributor)

        device = _create_device(client, owner_token, "owner-service-device")
        network = _create_network(client, owner_token, f"owner-net-{uuid.uuid4().hex[:8]}")

        create_service_response = client.post(
            f"/api/devices/{device['id']}/services",
            json={"name": "nginx", "protocol": "tcp", "port": 80},
            headers=_auth(owner_token),
        )
        assert create_service_response.status_code == 201, create_service_response.text

        attach_network_response = client.post(
            f"/api/devices/{device['id']}/networks",
            json={"network_id": network["id"], "ip_address": "10.21.0.20"},
            headers=_auth(owner_token),
        )
        assert attach_network_response.status_code == 201, attach_network_response.text

        list_services_response = client.get(
            f"/api/devices/{device['id']}/services",
            headers=_auth(foreign_reader_token),
        )
        assert list_services_response.status_code == 404

        list_networks_response = client.get(
            f"/api/devices/{device['id']}/networks",
            headers=_auth(foreign_reader_token),
        )
        assert list_networks_response.status_code == 404

        create_foreign_service_response = client.post(
            f"/api/devices/{device['id']}/services",
            json={"name": "foreign", "protocol": "tcp", "port": 81},
            headers=_auth(foreign_contributor_token),
        )
        assert create_foreign_service_response.status_code == 404

        attach_foreign_network_response = client.post(
            f"/api/devices/{device['id']}/networks",
            json={"network_id": network["id"], "ip_address": "10.21.0.21"},
            headers=_auth(foreign_contributor_token),
        )
        assert attach_foreign_network_response.status_code == 404

        detach_foreign_network_response = client.delete(
            f"/api/devices/{device['id']}/networks/{network['id']}",
            headers=_auth(foreign_contributor_token),
        )
        assert detach_foreign_network_response.status_code == 404

    def test_foreign_device_canvas_delete_and_restore_return_404(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, owner_token = _make_user(session, Role.Contributor)
        _, foreign_contributor_token = _make_user(session, Role.Contributor)

        device = _create_device(client, owner_token, "owner-canvas-device")
        _, topology_id = _create_workspace_and_topology(client, owner_token)
        _create_diagram(
            client,
            owner_token,
            topology_id,
            "Owner Scope Canvas",
            {
                "elements": [
                    {
                        "group": "nodes",
                        "data": {"id": device["id"], "label": "owner-canvas-device"},
                        "position": {"x": 10, "y": 20},
                    }
                ],
            },
        )

        foreign_delete_response = client.post(
            f"/api/devices/{device['id']}/canvas-delete",
            headers=_auth(foreign_contributor_token),
        )
        assert foreign_delete_response.status_code == 404

        owner_delete_response = client.post(
            f"/api/devices/{device['id']}/canvas-delete",
            headers=_auth(owner_token),
        )
        assert owner_delete_response.status_code == 200, owner_delete_response.text

        foreign_restore_response = client.post(
            f"/api/devices/{device['id']}/restore",
            json=owner_delete_response.json()["snapshot"],
            headers=_auth(foreign_contributor_token),
        )
        assert foreign_restore_response.status_code == 404

    def test_unplaced_restore_snapshot_remains_bound_to_original_owner(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, owner_token = _make_user(session, Role.Contributor)
        _, foreign_token = _make_user(session, Role.Contributor)

        device = _create_device(client, owner_token, "owner-unplaced-device")

        delete_response = client.post(
            f"/api/devices/{device['id']}/canvas-delete",
            headers=_auth(owner_token),
        )
        assert delete_response.status_code == 200, delete_response.text
        snapshot = delete_response.json()["snapshot"]
        assert snapshot["placements"] == []
        assert snapshot["restore_token"]

        foreign_restore_response = client.post(
            f"/api/devices/{device['id']}/restore",
            json=snapshot,
            headers=_auth(foreign_token),
        )
        assert foreign_restore_response.status_code == 404

        owner_restore_response = client.post(
            f"/api/devices/{device['id']}/restore",
            json=snapshot,
            headers=_auth(owner_token),
        )
        assert owner_restore_response.status_code == 200, owner_restore_response.text

        owner_get_response = client.get(
            f"/api/devices/{device['id']}",
            headers=_auth(owner_token),
        )
        assert owner_get_response.status_code == 200

        foreign_get_response = client.get(
            f"/api/devices/{device['id']}",
            headers=_auth(foreign_token),
        )
        assert foreign_get_response.status_code == 404

    def test_restore_rejects_tampered_placement_targeting_foreign_diagram(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, owner_token = _make_user(session, Role.Contributor)
        _, foreign_token = _make_user(session, Role.Contributor)

        device = _create_device(client, owner_token, "owner-placed-device")
        _, owner_topology_id = _create_workspace_and_topology(client, owner_token)
        _, foreign_topology_id = _create_workspace_and_topology(client, foreign_token)

        owner_diagram = _create_diagram(
            client,
            owner_token,
            owner_topology_id,
            "Owner Restore Diagram",
            {
                "elements": [
                    {
                        "group": "nodes",
                        "data": {"id": device["id"], "label": "owner-placed-device"},
                        "position": {"x": 10, "y": 20},
                    }
                ]
            },
        )
        foreign_diagram = _create_diagram(
            client,
            foreign_token,
            foreign_topology_id,
            "Foreign Diagram",
            {"elements": []},
        )

        delete_response = client.post(
            f"/api/devices/{device['id']}/canvas-delete",
            headers=_auth(owner_token),
        )
        assert delete_response.status_code == 200, delete_response.text
        snapshot = delete_response.json()["snapshot"]
        assert len(snapshot["placements"]) == 1
        assert snapshot["placements"][0]["diagram_id"] == owner_diagram["id"]

        snapshot["placements"][0]["diagram_id"] = foreign_diagram["id"]
        restore_response = client.post(
            f"/api/devices/{device['id']}/restore",
            json=snapshot,
            headers=_auth(owner_token),
        )
        assert restore_response.status_code == 400

        device_response = client.get(
            f"/api/devices/{device['id']}",
            headers=_auth(owner_token),
        )
        assert device_response.status_code == 404

        foreign_diagram_response = client.get(
            f"/api/diagrams/{foreign_diagram['id']}",
            headers=_auth(foreign_token),
        )
        assert foreign_diagram_response.status_code == 200
        assert foreign_diagram_response.json()["cytoscape_json"]["elements"] == []

    def test_restore_rejects_valid_signed_snapshot_targeting_hidden_legacy_layout(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        owner_user, owner_token = _make_user(session, Role.Contributor)

        device = _create_device(client, owner_token, "owner-hidden-restore-device")
        _, owner_topology_id = _create_workspace_and_topology(client, owner_token)
        _create_diagram(
            client,
            owner_token,
            owner_topology_id,
            "Owner Restore Diagram",
            {
                "elements": [
                    {
                        "group": "nodes",
                        "data": {"id": device["id"], "label": "owner-hidden-restore-device"},
                        "position": {"x": 10, "y": 20},
                    }
                ]
            },
        )

        delete_response = client.post(
            f"/api/devices/{device['id']}/canvas-delete",
            headers=_auth(owner_token),
        )
        assert delete_response.status_code == 200, delete_response.text

        hidden_legacy_layout = DiagramLayout(
            name=f"Legacy-Restore-{uuid.uuid4().hex[:8]}",
            cytoscape_json={"elements": []},
            topology_id=None,
        )
        session.add(hidden_legacy_layout)
        session.commit()
        session.refresh(hidden_legacy_layout)

        snapshot = PublishedDeviceDeleteSnapshot.model_validate(
            delete_response.json()["snapshot"]
        )
        snapshot.placements[0].diagram_id = hidden_legacy_layout.id
        snapshot.restore_token = _build_restore_token(snapshot, owner_user.id, owner_user.id)

        restore_response = client.post(
            f"/api/devices/{device['id']}/restore",
            json=snapshot.model_dump(mode="json"),
            headers=_auth(owner_token),
        )

        assert restore_response.status_code == 404

        device_response = client.get(
            f"/api/devices/{device['id']}",
            headers=_auth(owner_token),
        )
        assert device_response.status_code == 404

        session.refresh(hidden_legacy_layout)
        assert hidden_legacy_layout.cytoscape_json["elements"] == []