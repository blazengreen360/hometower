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
from src.models.types import ConnectionType, DeviceType
from src.models.workspace import Workspace
from src.services import device_service


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


class TestGetDevicePlacements:
    def test_placements_returns_empty_for_unplaced_device(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        headers_w = {"Authorization": f"Bearer {contributor_token}"}
        headers_r = {"Authorization": f"Bearer {reader_token}"}
        resp = client.post(
            "/api/devices/", json={"name": "lonely", "type": "Server"}, headers=headers_w
        )
        assert resp.status_code == 201
        device_id = resp.json()["id"]

        placements = client.get(
            f"/api/devices/{device_id}/placements", headers=headers_r
        )
        assert placements.status_code == 200
        assert placements.json() == []

    def test_placements_returns_views_containing_device(
        self, session: Session, client: TestClient,
        contributor_token: str, reader_token: str
    ) -> None:
        headers_w = {"Authorization": f"Bearer {contributor_token}"}
        headers_r = {"Authorization": f"Bearer {reader_token}"}
        resp = client.post(
            "/api/devices/", json={"name": "placed-dev", "type": "Switch"}, headers=headers_w
        )
        assert resp.status_code == 201
        device_id = resp.json()["id"]

        # Create a layout containing this device
        _create_layout_with_device(session, uuid.UUID(device_id), "My View")
        session.commit()

        placements = client.get(
            f"/api/devices/{device_id}/placements", headers=headers_r
        )
        assert placements.status_code == 200
        data = placements.json()
        assert len(data) == 1
        assert data[0]["view_name"] == "My View"

    def test_placements_nonexistent_device_returns_404(
        self, client: TestClient, reader_token: str
    ) -> None:
        headers = {"Authorization": f"Bearer {reader_token}"}
        resp = client.get(
            f"/api/devices/{uuid.uuid4()}/placements", headers=headers
        )
        assert resp.status_code == 404


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
        layout = DiagramLayout(
            name="Test View",
            cytoscape_json={
                "elements": [
                    {"data": {"id": str(d1.id)}},
                    {"data": {"id": str(d2.id)}},
                    {"data": {"id": "edge-1", "source": str(d1.id), "target": str(d2.id)}},
                ]
            },
        )
        session.add(layout)
        session.flush()
        session.commit()

        device_service.delete(d1.id, session)

        session.refresh(layout)
        elements = layout.cytoscape_json.get("elements", [])
        remaining_ids = [e["data"]["id"] for e in elements]
        assert str(d1.id) not in remaining_ids
        assert "edge-1" not in remaining_ids  # edge referencing d1 also removed
        assert str(d2.id) in remaining_ids  # d2 survives

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
        _create_layout_with_device(session, d1.id, "V1")
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


class TestPlacedIdsEndpoint:
    def test_reader_can_get_placed_ids(
        self, session: Session, client: TestClient,
        contributor_token: str, reader_token: str,
    ) -> None:
        headers_w = {"Authorization": f"Bearer {contributor_token}"}
        headers_r = {"Authorization": f"Bearer {reader_token}"}

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
        _create_layout_with_device(session, uuid.UUID(placed_id), "EP View")
        session.commit()

        result = client.get("/api/devices/placed-ids", headers=headers_r)
        assert result.status_code == 200
        ids = result.json()
        assert placed_id in ids
        assert unplaced_id not in ids

    def test_unauthenticated_get_placed_ids_returns_401(
        self, client: TestClient,
    ) -> None:
        resp = client.get("/api/devices/placed-ids")
        assert resp.status_code == 401
