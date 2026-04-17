"""Integration tests for HT-032 canvas undo API routes."""

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from src.models.device import Device
from src.models.diagram import DiagramLayout
from src.models.types import DeviceType


def _create_device(client: TestClient, headers: dict[str, str], name: str) -> str:
    response = client.post(
        "/api/devices/",
        json={"name": name, "type": "Server"},
        headers=headers,
    )
    assert response.status_code == 201
    return str(response.json()["id"])


def _create_connection(
    client: TestClient,
    headers: dict[str, str],
    source_id: str,
    target_id: str,
) -> str:
    response = client.post(
        "/api/connections/",
        json={"source_id": source_id, "target_id": target_id, "type": "Ethernet"},
        headers=headers,
    )
    assert response.status_code == 201
    return str(response.json()["id"])


class TestCanvasUndoApi:
    def test_contributor_can_canvas_delete_and_receive_snapshot(
        self,
        client: TestClient,
        session: Session,
        contributor_token: str,
    ) -> None:
        headers = {"Authorization": f"Bearer {contributor_token}"}
        source_id = _create_device(client, headers, "undo-source")
        target_id = _create_device(client, headers, "undo-target")
        conn_id = _create_connection(client, headers, source_id, target_id)

        layout = DiagramLayout(
            name="Undo View",
            cytoscape_json={
                "elements": [
                    {
                        "group": "nodes",
                        "data": {"id": source_id, "label": "undo-source"},
                        "position": {"x": 10, "y": 20},
                    },
                    {
                        "group": "nodes",
                        "data": {"id": target_id, "label": "undo-target"},
                        "position": {"x": 110, "y": 120},
                    },
                    {
                        "group": "edges",
                        "data": {
                            "id": conn_id,
                            "source": source_id,
                            "target": target_id,
                        },
                    },
                ],
                "collapsedNodes": [source_id],
            },
        )
        session.add(layout)
        session.commit()
        session.refresh(layout)

        delete_response = client.post(f"/api/devices/{source_id}/canvas-delete", headers=headers)

        assert delete_response.status_code == 200
        body = delete_response.json()
        assert body["snapshot"]["device"]["id"] == source_id
        assert len(body["snapshot"]["connections"]) == 1
        assert len(body["snapshot"]["placements"]) == 1
        assert body["modified_diagrams"][0]["diagram_id"] == str(layout.id)

    def test_reader_cannot_call_canvas_delete_or_restore(
        self,
        client: TestClient,
        contributor_token: str,
        reader_token: str,
    ) -> None:
        contributor_headers = {"Authorization": f"Bearer {contributor_token}"}
        reader_headers = {"Authorization": f"Bearer {reader_token}"}
        device_id = _create_device(client, contributor_headers, "rbac-canvas-undo")

        delete_response = client.post(
            f"/api/devices/{device_id}/canvas-delete",
            headers=reader_headers,
        )

        assert delete_response.status_code == 403

        restore_response = client.post(
            f"/api/devices/{device_id}/restore",
            headers=reader_headers,
            json={
                "device": {
                    "id": device_id,
                    "name": "rbac-canvas-undo",
                    "type": "Server",
                    "status": "Active",
                    "ip": None,
                    "mac": None,
                    "os": None,
                    "notes": None,
                    "location_id": None,
                    "parent_id": None,
                    "version": 1,
                },
                "connections": [],
                "placements": [],
            },
        )

        assert restore_response.status_code == 403

    def test_restore_recreates_device_connections_and_updates_layout_versions(
        self,
        client: TestClient,
        session: Session,
        contributor_token: str,
    ) -> None:
        headers = {"Authorization": f"Bearer {contributor_token}"}
        source_id = _create_device(client, headers, "restore-source")
        target_id = _create_device(client, headers, "restore-target")
        conn_id = _create_connection(client, headers, source_id, target_id)

        layout = DiagramLayout(
            name="Restore View",
            cytoscape_json={
                "elements": [
                    {
                        "group": "nodes",
                        "data": {"id": source_id, "label": "restore-source"},
                        "position": {"x": 10, "y": 20},
                    },
                    {
                        "group": "nodes",
                        "data": {"id": target_id, "label": "restore-target"},
                        "position": {"x": 110, "y": 120},
                    },
                    {
                        "group": "edges",
                        "data": {
                            "id": conn_id,
                            "source": source_id,
                            "target": target_id,
                        },
                    },
                ],
            },
        )
        session.add(layout)
        session.commit()
        session.refresh(layout)
        initial_version = layout.version

        delete_response = client.post(f"/api/devices/{source_id}/canvas-delete", headers=headers)
        assert delete_response.status_code == 200
        delete_body = delete_response.json()

        restore_response = client.post(
            f"/api/devices/{source_id}/restore",
            headers=headers,
            json=delete_body["snapshot"],
        )

        assert restore_response.status_code == 200

        device_response = client.get(f"/api/devices/{source_id}", headers=headers)
        assert device_response.status_code == 200

        connections_response = client.get(f"/api/devices/{source_id}/connections", headers=headers)
        assert connections_response.status_code == 200
        connection_ids = {row["id"] for row in connections_response.json()}
        assert conn_id in connection_ids

        session.refresh(layout)
        assert layout.version >= initial_version + 2

    def test_restore_returns_409_if_device_id_has_been_reused(
        self,
        client: TestClient,
        session: Session,
        contributor_token: str,
    ) -> None:
        headers = {"Authorization": f"Bearer {contributor_token}"}
        source_id = _create_device(client, headers, "reuse-source")

        delete_response = client.post(f"/api/devices/{source_id}/canvas-delete", headers=headers)
        assert delete_response.status_code == 200
        snapshot = delete_response.json()["snapshot"]

        reused = Device(
            id=uuid.UUID(source_id),
            name="reused-id-holder",
            type=DeviceType.Server,
        )
        session.add(reused)
        session.commit()

        restore_response = client.post(
            f"/api/devices/{source_id}/restore",
            headers=headers,
            json=snapshot,
        )

        assert restore_response.status_code == 409

    def test_canvas_delete_rejects_parent_devices_with_children(
        self,
        client: TestClient,
        contributor_token: str,
    ) -> None:
        headers = {"Authorization": f"Bearer {contributor_token}"}

        parent = client.post(
            "/api/devices/",
            json={"name": "undo-parent", "type": "Server"},
            headers=headers,
        )
        assert parent.status_code == 201
        parent_id = str(parent.json()["id"])

        child = client.post(
            "/api/devices/",
            json={"name": "undo-child", "type": "VM", "parent_id": parent_id},
            headers=headers,
        )
        assert child.status_code == 201

        delete_response = client.post(
            f"/api/devices/{parent_id}/canvas-delete",
            headers=headers,
        )

        assert delete_response.status_code == 400
