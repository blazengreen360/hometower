"""Integration tests for HT-052 device deletion, placements, and cascade behavior."""
import json
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from src.models.connection import Connection
from src.models.device import Device
from src.models.diagram import DiagramLayout
from src.models.topology import Topology
from src.models.types import ConnectionType, DeviceType, Role
from src.models.user import User
from src.models.workspace import Workspace
from src.repositories import device_repository_support
from src.services import device_service
from src.utils.auth import create_jwt, hash_password


def _create_device(session: Session, name: str = "test-dev") -> Device:
    device = Device(name=name, type=DeviceType.Server)
    session.add(device)
    session.flush()
    session.refresh(device)
    return device


def _create_connection(
    session: Session, source_id: uuid.UUID, target_id: uuid.UUID
) -> Connection:
    conn = Connection(
        source_id=source_id, target_id=target_id, type=ConnectionType.Ethernet
    )
    session.add(conn)
    session.flush()
    session.refresh(conn)
    return conn


def _create_layout_with_device(
    session: Session, device_id: uuid.UUID, view_name: str = "View 1",
    topology_id: uuid.UUID | None = None,
) -> DiagramLayout:
    cj = {
        "elements": [
            {"data": {"id": str(device_id)}},
        ]
    }
    layout = DiagramLayout(
        name=view_name,
        cytoscape_json=cj,
        topology_id=topology_id,
    )
    session.add(layout)
    session.flush()
    session.refresh(layout)
    return layout


def _create_current_layout(
    session: Session,
    owner_id: uuid.UUID,
    cytoscape_json: dict[str, object],
    view_name: str = "View 1",
) -> DiagramLayout:
    workspace = Workspace(
        name=f"ws-{uuid.uuid4().hex[:8]}",
        owner_id=owner_id,
    )
    session.add(workspace)
    session.flush()
    topology = Topology(
        name=f"topo-{uuid.uuid4().hex[:8]}",
        workspace_id=workspace.id,
        tags=[],
    )
    session.add(topology)
    session.flush()
    layout = DiagramLayout(
        name=view_name,
        cytoscape_json=cytoscape_json,
        topology_id=topology.id,
    )
    session.add(layout)
    session.flush()
    topology.current_diagram_id = layout.id
    session.add(topology)
    session.flush()
    session.refresh(layout)
    return layout


def _make_user(session: Session, role: Role = Role.Contributor) -> tuple[User, str]:
    user = User(
        username=f"device_delete_{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:8]}@device-delete.local",
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


class TestGetDevicePlacements:
    def test_placements_returns_empty_for_unplaced_device(
        self, session: Session, client: TestClient
    ) -> None:
        owner, owner_token = _make_user(session, Role.Contributor)
        headers_w = {"Authorization": f"Bearer {owner_token}"}
        resp = client.post(
            "/api/devices/", json={"name": "lonely", "type": "Server"}, headers=headers_w
        )
        assert resp.status_code == 201
        device_id = resp.json()["id"]

        owner.role = Role.Reader
        session.add(owner)
        session.commit()
        session.refresh(owner)
        owner_reader_token = create_jwt(
            {
                "sub": str(owner.id),
                "role": Role.Reader.value,
                "version": owner.token_version,
            }
        )
        headers_r = {"Authorization": f"Bearer {owner_reader_token}"}

        placements = client.get(
            f"/api/devices/{device_id}/placements", headers=headers_r
        )
        assert placements.status_code == 200
        assert placements.json() == []

    def test_placements_exclude_other_owner_current_layouts(
        self, session: Session, client: TestClient
    ) -> None:
        owner, owner_token = _make_user(session, Role.Contributor)
        intruder, _ = _make_user(session, Role.Contributor)
        headers_w = {"Authorization": f"Bearer {owner_token}"}

        resp = client.post(
            "/api/devices/",
            json={"name": "owner-scoped-placement", "type": "Server"},
            headers=headers_w,
        )
        assert resp.status_code == 201
        device_id = resp.json()["id"]

        owner_layout = _create_current_layout(
            session,
            owner.id,
            {"elements": [{"data": {"id": device_id}}]},
            "Owner View",
        )
        _create_current_layout(
            session,
            intruder.id,
            {"elements": [{"data": {"id": device_id}}]},
            "Intruder View",
        )
        session.commit()

        owner.role = Role.Reader
        session.add(owner)
        session.commit()
        session.refresh(owner)
        owner_reader_token = create_jwt(
            {
                "sub": str(owner.id),
                "role": Role.Reader.value,
                "version": owner.token_version,
            }
        )

        placements = client.get(
            f"/api/devices/{device_id}/placements",
            headers={"Authorization": f"Bearer {owner_reader_token}"},
        )

        assert placements.status_code == 200
        data = placements.json()
        assert len(data) == 1
        assert data[0]["view_id"] == str(owner_layout.id)
        assert data[0]["view_name"] == "Owner View"

    def test_placements_returns_views_containing_device(
        self, session: Session, client: TestClient
    ) -> None:
        owner, owner_token = _make_user(session, Role.Contributor)
        headers_w = {"Authorization": f"Bearer {owner_token}"}
        resp = client.post(
            "/api/devices/", json={"name": "placed-dev", "type": "Switch"}, headers=headers_w
        )
        assert resp.status_code == 201
        device_id = resp.json()["id"]

        _create_current_layout(
            session,
            owner.id,
            {"elements": [{"data": {"id": str(device_id)}}]},
            "My View",
        )
        session.commit()

        owner.role = Role.Reader
        session.add(owner)
        session.commit()
        session.refresh(owner)
        owner_reader_token = create_jwt(
            {
                "sub": str(owner.id),
                "role": Role.Reader.value,
                "version": owner.token_version,
            }
        )
        headers_r = {"Authorization": f"Bearer {owner_reader_token}"}

        placements = client.get(
            f"/api/devices/{device_id}/placements", headers=headers_r
        )
        assert placements.status_code == 200
        data = placements.json()
        assert len(data) == 1
        assert data[0]["view_name"] == "My View"

    def test_placements_support_device_id_nodes(
        self, session: Session, client: TestClient
    ) -> None:
        owner, owner_token = _make_user(session, Role.Contributor)
        headers_w = {"Authorization": f"Bearer {owner_token}"}
        resp = client.post(
            "/api/devices/", json={"name": "placed-canonical", "type": "Switch"}, headers=headers_w
        )
        assert resp.status_code == 201
        device_id = resp.json()["id"]

        _create_current_layout(
            session,
            owner.id,
            {
                "elements": {
                    "nodes": [
                        {
                            "group": "nodes",
                            "data": {"id": "node-1", "device_id": device_id},
                            "position": {"x": 100, "y": 50},
                        }
                    ],
                    "edges": [],
                }
            },
            "Canonical View",
        )
        session.commit()

        owner.role = Role.Reader
        session.add(owner)
        session.commit()
        session.refresh(owner)
        owner_reader_token = create_jwt(
            {
                "sub": str(owner.id),
                "role": Role.Reader.value,
                "version": owner.token_version,
            }
        )
        headers_r = {"Authorization": f"Bearer {owner_reader_token}"}

        placements = client.get(
            f"/api/devices/{device_id}/placements", headers=headers_r
        )

        assert placements.status_code == 200
        data = placements.json()
        assert len(data) == 1
        assert data[0]["view_name"] == "Canonical View"

    def test_placements_ignore_historical_only_layouts(
        self, session: Session, client: TestClient
    ) -> None:
        owner, owner_token = _make_user(session, Role.Contributor)
        headers_w = {"Authorization": f"Bearer {owner_token}"}
        resp = client.post(
            "/api/devices/",
            json={"name": "history-only-placement", "type": "Switch"},
            headers=headers_w,
        )
        assert resp.status_code == 201
        device_id = uuid.UUID(resp.json()["id"])

        workspace = Workspace(name="Placement History Workspace", owner_id=owner.id)
        session.add(workspace)
        session.flush()
        topology = Topology(
            name="Placement History Topology",
            workspace_id=workspace.id,
            tags=[],
        )
        session.add(topology)
        session.flush()
        historical_layout = _create_layout_with_device(
            session,
            device_id,
            "Historical View",
            topology.id,
        )
        current_layout = _create_layout_with_device(
            session,
            uuid.uuid4(),
            "Current View",
            topology.id,
        )
        topology.current_diagram_id = current_layout.id
        session.add(topology)
        session.commit()
        session.refresh(historical_layout)

        owner.role = Role.Reader
        session.add(owner)
        session.commit()
        session.refresh(owner)
        owner_reader_token = create_jwt(
            {
                "sub": str(owner.id),
                "role": Role.Reader.value,
                "version": owner.token_version,
            }
        )
        headers_r = {"Authorization": f"Bearer {owner_reader_token}"}

        placements = client.get(
            f"/api/devices/{device_id}/placements",
            headers=headers_r,
        )

        assert placements.status_code == 200
        assert placements.json() == []

    def test_placements_nonexistent_device_returns_404(
        self, client: TestClient, reader_token: str
    ) -> None:
        headers = {"Authorization": f"Bearer {reader_token}"}
        resp = client.get(
            f"/api/devices/{uuid.uuid4()}/placements", headers=headers
        )
        assert resp.status_code == 404

    def test_placements_other_owner_device_returns_404(
        self, session: Session, client: TestClient
    ) -> None:
        _, owner_token = _make_user(session, Role.Contributor)
        _, other_reader_token = _make_user(session, Role.Reader)

        resp = client.post(
            "/api/devices/",
            json={"name": "placed-owner-only", "type": "Switch"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert resp.status_code == 201
        device_id = resp.json()["id"]

        placements = client.get(
            f"/api/devices/{device_id}/placements",
            headers={"Authorization": f"Bearer {other_reader_token}"},
        )

        assert placements.status_code == 404


class TestDeleteDeviceCascade:
    def test_delete_cascades_connections(
        self, session: Session
    ) -> None:
        d1 = _create_device(session, "dev-a")
        d2 = _create_device(session, "dev-b")
        _create_connection(session, d1.id, d2.id)
        session.commit()

        device_service.delete(d1.id, session)

        # Connection should be gone
        from src.repositories import connection_repository
        count = connection_repository.count_by_device(session, d1.id)
        assert count == 0

    def test_delete_cleans_cytoscape_json(
        self, session: Session
    ) -> None:
        d1 = _create_device(session, "canvas-dev")
        d2 = _create_device(session, "other-dev")
        owner, _ = _make_user(session, Role.Contributor)
        workspace = Workspace(
            name=f"delete-cleanup-{uuid.uuid4().hex[:8]}",
            owner_id=owner.id,
        )
        session.add(workspace)
        session.flush()
        topology = Topology(
            name=f"delete-cleanup-topology-{uuid.uuid4().hex[:8]}",
            workspace_id=workspace.id,
            tags=[],
        )
        session.add(topology)
        session.flush()

        layout_payload = {
            "elements": [
                {"data": {"id": str(d1.id)}},
                {"data": {"id": str(d2.id)}},
                {"data": {"id": "edge-1", "source": str(d1.id), "target": str(d2.id)}},
            ]
        }
        historical_layout = DiagramLayout(
            name="History Snapshot",
            cytoscape_json=json.loads(json.dumps(layout_payload)),
            topology_id=topology.id,
        )
        current_layout = DiagramLayout(
            name="Current View",
            cytoscape_json=json.loads(json.dumps(layout_payload)),
            topology_id=topology.id,
        )
        session.add(historical_layout)
        session.add(current_layout)
        session.flush()
        topology.current_diagram_id = current_layout.id
        session.add(topology)
        session.commit()

        device_service.delete(d1.id, session)

        session.refresh(current_layout)
        session.refresh(historical_layout)

        current_raw_elements = current_layout.cytoscape_json.get("elements", [])
        current_elements = current_raw_elements if isinstance(current_raw_elements, list) else []
        current_remaining_ids = [element["data"]["id"] for element in current_elements]
        assert str(d1.id) not in current_remaining_ids
        assert "edge-1" not in current_remaining_ids
        assert str(d2.id) in current_remaining_ids

        history_raw_elements = historical_layout.cytoscape_json.get("elements", [])
        history_elements = history_raw_elements if isinstance(history_raw_elements, list) else []
        history_remaining_ids = [element["data"]["id"] for element in history_elements]
        assert str(d1.id) in history_remaining_ids
        assert "edge-1" in history_remaining_ids
        assert str(d2.id) in history_remaining_ids

    def test_delete_with_children_returns_400(
        self, client: TestClient, contributor_token: str
    ) -> None:
        headers = {"Authorization": f"Bearer {contributor_token}"}
        parent = client.post(
            "/api/devices/", json={"name": "parent", "type": "Server"}, headers=headers
        )
        assert parent.status_code == 201
        parent_id = parent.json()["id"]

        child = client.post(
            "/api/devices/",
            json={"name": "child", "type": "VM", "parent_id": parent_id},
            headers=headers,
        )
        assert child.status_code == 201

        resp = client.delete(f"/api/devices/{parent_id}", headers=headers)
        assert resp.status_code == 400
        assert "child devices" in resp.json()["detail"]

    def test_delete_device_via_api_returns_204(
        self, client: TestClient, contributor_token: str
    ) -> None:
        headers = {"Authorization": f"Bearer {contributor_token}"}
        resp = client.post(
            "/api/devices/", json={"name": "to-delete", "type": "NAS"}, headers=headers
        )
        assert resp.status_code == 201
        device_id = resp.json()["id"]

        del_resp = client.delete(f"/api/devices/{device_id}", headers=headers)
        assert del_resp.status_code == 204

        get_resp = client.get(
            f"/api/devices/{device_id}", headers=headers
        )
        assert get_resp.status_code == 404

    def test_reader_cannot_delete_device(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        headers_w = {"Authorization": f"Bearer {contributor_token}"}
        headers_r = {"Authorization": f"Bearer {reader_token}"}
        resp = client.post(
            "/api/devices/", json={"name": "rbac-dev", "type": "Router"}, headers=headers_w
        )
        assert resp.status_code == 201
        device_id = resp.json()["id"]

        del_resp = client.delete(f"/api/devices/{device_id}", headers=headers_r)
        assert del_resp.status_code == 403

    def test_other_owner_cannot_delete_device(
        self, session: Session, client: TestClient
    ) -> None:
        _, owner_token = _make_user(session, Role.Contributor)
        _, other_token = _make_user(session, Role.Contributor)

        resp = client.post(
            "/api/devices/",
            json={"name": "delete-owner-only", "type": "Router"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert resp.status_code == 201
        device_id = resp.json()["id"]

        del_resp = client.delete(
            f"/api/devices/{device_id}",
            headers={"Authorization": f"Bearer {other_token}"},
        )

        assert del_resp.status_code == 404

    def test_delete_legacy_owner_scope_uses_current_diagram_membership(
        self, session: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        owner, owner_token = _make_user(session, Role.Contributor)
        headers = {"Authorization": f"Bearer {owner_token}"}

        resp = client.post(
            "/api/devices/",
            json={"name": "legacy-delete-device", "type": "Router"},
            headers=headers,
        )
        assert resp.status_code == 201
        device_id = uuid.UUID(resp.json()["id"])

        workspace = Workspace(name="Legacy Delete Workspace", owner_id=owner.id)
        session.add(workspace)
        session.flush()
        topology = Topology(
            name="Legacy Delete Topology",
            workspace_id=workspace.id,
            tags=[],
        )
        session.add(topology)
        session.flush()
        current_layout = _create_layout_with_device(
            session,
            device_id,
            "Legacy Delete Current",
            topology.id,
        )
        topology.current_diagram_id = current_layout.id
        session.add(topology)
        session.commit()

        monkeypatch.setattr(
            device_repository_support,
            "device_owner_scope_available",
            lambda _session: False,
        )

        del_resp = client.delete(f"/api/devices/{device_id}", headers=headers)
        assert del_resp.status_code == 204

        get_resp = client.get(f"/api/devices/{device_id}", headers=headers)
        assert get_resp.status_code == 404


class TestOrphanDetection:
    def test_get_placed_device_ids_empty_layouts(
        self, session: Session
    ) -> None:
        placed = device_service.get_placed_device_ids(session)
        # May contain devices from other tests, but should be a set
        assert isinstance(placed, set)

    def test_placed_device_detected(
        self, session: Session
    ) -> None:
        d1 = _create_device(session, "placed")
        owner, _ = _make_user(session)
        _create_current_layout(
            session,
            owner.id,
            {"elements": [{"data": {"id": str(d1.id)}}]},
            "V1",
        )
        session.commit()

        placed = device_service.get_placed_device_ids(session)
        assert d1.id in placed

    def test_unplaced_device_not_in_set(
        self, session: Session
    ) -> None:
        d1 = _create_device(session, "orphan")
        session.commit()

        placed = device_service.get_placed_device_ids(session)
        assert d1.id not in placed

    def test_flat_layout_edges_do_not_count_as_placed_devices(
        self, session: Session
    ) -> None:
        placed_device = _create_device(session, "placed-flat")
        edge_id = uuid.uuid4()
        owner, _ = _make_user(session)
        _create_current_layout(
            session,
            owner.id,
            {
                "elements": [
                    {"data": {"id": str(placed_device.id)}},
                    {
                        "data": {
                            "id": str(edge_id),
                            "source": str(placed_device.id),
                            "target": str(uuid.uuid4()),
                        }
                    },
                ]
            },
            "Flat Layout",
        )
        session.commit()

        placed = device_service.get_placed_device_ids(session)

        assert placed_device.id in placed
        assert edge_id not in placed


class TestPlacedIdsEndpoint:
    def test_reader_can_get_placed_ids(
        self,
        session: Session,
        client: TestClient,
    ) -> None:
        owner, owner_token = _make_user(session, Role.Contributor)
        headers_w = {"Authorization": f"Bearer {owner_token}"}

        # Create a placed device
        resp = client.post(
            "/api/devices/", json={"name": "placed-ep", "type": "Server"},
            headers=headers_w,
        )
        assert resp.status_code == 201
        placed_id = resp.json()["id"]

        # Create an unplaced device
        resp2 = client.post(
            "/api/devices/", json={"name": "unplaced-ep", "type": "Switch"},
            headers=headers_w,
        )
        assert resp2.status_code == 201
        unplaced_id = resp2.json()["id"]

        # Place only the first device on a layout
        _create_current_layout(
            session,
            owner.id,
            {"elements": [{"data": {"id": placed_id}}]},
            "EP View",
        )
        session.commit()

        owner.role = Role.Reader
        session.add(owner)
        session.commit()
        session.refresh(owner)
        owner_reader_token = create_jwt(
            {
                "sub": str(owner.id),
                "role": Role.Reader.value,
                "version": owner.token_version,
            }
        )

        result = client.get(
            "/api/devices/placed-ids",
            headers={"Authorization": f"Bearer {owner_reader_token}"},
        )
        assert result.status_code == 200
        ids = result.json()
        assert placed_id in ids
        assert unplaced_id not in ids

    def test_unauthenticated_get_placed_ids_returns_401(
        self, client: TestClient,
    ) -> None:
        resp = client.get("/api/devices/placed-ids")
        assert resp.status_code == 401

    def test_default_placed_ids_scope_excludes_other_owner_devices(
        self,
        session: Session,
        client: TestClient,
    ) -> None:
        owner, owner_token = _make_user(session, Role.Contributor)
        intruder, intruder_token = _make_user(session, Role.Contributor)

        owner_device_response = client.post(
            "/api/devices/",
            json={"name": "owner-placed", "type": "Server"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        intruder_device_response = client.post(
            "/api/devices/",
            json={"name": "intruder-placed", "type": "Switch"},
            headers={"Authorization": f"Bearer {intruder_token}"},
        )

        assert owner_device_response.status_code == 201
        assert intruder_device_response.status_code == 201

        owner_device_id = owner_device_response.json()["id"]
        intruder_device_id = intruder_device_response.json()["id"]

        _create_current_layout(
            session,
            owner.id,
            {"elements": [{"data": {"id": owner_device_id}}]},
            "Owner View",
        )
        _create_current_layout(
            session,
            intruder.id,
            {"elements": [{"data": {"id": intruder_device_id}}]},
            "Intruder View",
        )
        session.commit()

        owner.role = Role.Reader
        session.add(owner)
        session.commit()
        session.refresh(owner)
        owner_reader_token = create_jwt(
            {
                "sub": str(owner.id),
                "role": Role.Reader.value,
                "version": owner.token_version,
            }
        )

        response = client.get(
            "/api/devices/placed-ids",
            headers={"Authorization": f"Bearer {owner_reader_token}"},
        )

        assert response.status_code == 200
        placed_ids = response.json()
        assert owner_device_id in placed_ids
        assert intruder_device_id not in placed_ids

    def test_default_placed_ids_scope_ignores_foreign_layout_reference_to_owner_device(
        self,
        session: Session,
        client: TestClient,
    ) -> None:
        owner, owner_token = _make_user(session, Role.Contributor)
        intruder, _ = _make_user(session, Role.Contributor)

        owner_device_response = client.post(
            "/api/devices/",
            json={"name": "owner-not-placed", "type": "Server"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        assert owner_device_response.status_code == 201
        owner_device_id = owner_device_response.json()["id"]

        _create_current_layout(
            session,
            intruder.id,
            {"elements": [{"data": {"id": owner_device_id}}]},
            "Intruder References Owner Device",
        )
        session.commit()

        owner.role = Role.Reader
        session.add(owner)
        session.commit()
        session.refresh(owner)
        owner_reader_token = create_jwt(
            {
                "sub": str(owner.id),
                "role": Role.Reader.value,
                "version": owner.token_version,
            }
        )

        response = client.get(
            "/api/devices/placed-ids",
            headers={"Authorization": f"Bearer {owner_reader_token}"},
        )

        assert response.status_code == 200
        placed_ids = response.json()
        assert owner_device_id not in placed_ids
