"""Integration tests for HT-032 canvas undo API routes."""

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from src.models.device import Device
from src.models.diagram import DiagramLayout
from src.models.topology_history_entry import TopologyHistoryEntry
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


def _create_service(
    client: TestClient,
    headers: dict[str, str],
    device_id: str,
    name: str,
) -> dict[str, object]:
    response = client.post(
        f"/api/devices/{device_id}/services",
        json={"name": name, "protocol": "tcp", "port": 443},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def _create_tag(
    client: TestClient,
    headers: dict[str, str],
    name: str,
) -> dict[str, object]:
    response = client.post(
        "/api/tags/",
        json={"name": name, "color": "#2255aa"},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def _create_network(
    client: TestClient,
    headers: dict[str, str],
    name: str,
) -> dict[str, object]:
    response = client.post(
        "/api/networks/",
        json={
            "name": name,
            "vlan_id": 220,
            "cidr": "10.22.0.0/24",
            "gateway": "10.22.0.1",
            "color": "#123456",
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def _create_diagram(
    client: TestClient,
    headers: dict[str, str],
    name: str,
    cytoscape_json: dict[str, object],
) -> dict[str, object]:
    response = client.post(
        "/api/diagrams/",
        json={"name": name, "cytoscape_json": cytoscape_json},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def _create_workspace(
    client: TestClient,
    headers: dict[str, str],
    name: str,
) -> dict[str, object]:
    response = client.post(
        "/api/workspaces/",
        json={"name": name},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def _create_topology(
    client: TestClient,
    headers: dict[str, str],
    workspace_id: str,
    name: str,
) -> dict[str, object]:
    response = client.post(
        f"/api/workspaces/{workspace_id}/topologies/",
        json={"name": name},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def _single_device_canvas(device_id: str, name: str, device_type: str = "Server") -> dict[str, object]:
    return {
        "elements": {
            "nodes": [
                {
                    "data": {
                        "id": device_id,
                        "label": name,
                        "raw_name": name,
                        "device_type": device_type,
                        "raw_device_type": device_type,
                        "status": "Active",
                    },
                    "position": {"x": 120, "y": 180},
                }
            ],
            "edges": [],
        },
        "zoom": 1,
        "pan": {"x": 0, "y": 0},
        "collapsedNodes": [],
    }


class TestCanvasUndoApi:
    def test_contributor_can_canvas_delete_and_receive_snapshot(
        self,
        client: TestClient,
        contributor_token: str,
    ) -> None:
        headers = {"Authorization": f"Bearer {contributor_token}"}
        source_id = _create_device(client, headers, "undo-source")
        target_id = _create_device(client, headers, "undo-target")
        conn_id = _create_connection(client, headers, source_id, target_id)

        diagram = _create_diagram(
            client,
            headers,
            "Undo View",
            {
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

        delete_response = client.post(f"/api/devices/{source_id}/canvas-delete", headers=headers)

        assert delete_response.status_code == 200
        body = delete_response.json()
        assert body["snapshot"]["device"]["id"] == source_id
        assert len(body["snapshot"]["connections"]) == 1
        assert len(body["snapshot"]["placements"]) == 1
        assert body["snapshot"]["restore_token"]
        assert body["modified_diagrams"][0]["diagram_id"] == diagram["id"]

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

        diagram = _create_diagram(
            client,
            headers,
            "Restore View",
            {
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
        layout = session.get(DiagramLayout, uuid.UUID(diagram["id"]))
        assert layout is not None
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

    def test_canvas_delete_does_not_mutate_immutable_history_layout_needed_for_ghost_restore(
        self,
        client: TestClient,
        session: Session,
        contributor_token: str,
    ) -> None:
        headers = {"Authorization": f"Bearer {contributor_token}"}
        device_id = _create_device(client, headers, "history-canvas-delete-device")
        workspace = _create_workspace(client, headers, "WS Canvas Delete History")
        topology = _create_topology(
            client,
            headers,
            str(workspace["id"]),
            "Topo Canvas Delete History",
        )

        save_response = client.post(
            f"/api/topologies/{topology['id']}/save-version",
            json={
                "snapshot_name": "before-canvas-delete",
                "cytoscape_json": _single_device_canvas(
                    device_id=device_id,
                    name="history-canvas-delete-device",
                ),
            },
            headers=headers,
        )
        assert save_response.status_code == 200, save_response.text

        history_response = client.get(
            f"/api/topologies/{topology['id']}/history",
            headers=headers,
        )
        assert history_response.status_code == 200, history_response.text
        history_entry_id = history_response.json()["items"][0]["id"]

        history_entry = session.get(TopologyHistoryEntry, uuid.UUID(history_entry_id))
        assert history_entry is not None
        immutable_layout = session.get(DiagramLayout, history_entry.diagram_id)
        assert immutable_layout is not None

        delete_response = client.post(
            f"/api/devices/{device_id}/canvas-delete",
            headers=headers,
        )
        assert delete_response.status_code == 200, delete_response.text

        deleted_read = client.get(f"/api/devices/{device_id}", headers=headers)
        assert deleted_read.status_code == 404

        session.refresh(immutable_layout)
        immutable_nodes_after_delete = immutable_layout.cytoscape_json["elements"]["nodes"]

        restore_response = client.post(
            f"/api/topologies/{topology['id']}/history/{history_entry_id}/restore",
            json={},
            headers=headers,
        )
        assert restore_response.status_code == 200, restore_response.text

        restored_nodes = restore_response.json()["cytoscape_json"]["elements"]["nodes"]
        assert any(node["data"]["id"] == device_id for node in immutable_nodes_after_delete)

        restored_node = next(
            (node for node in restored_nodes if node["data"]["id"] == device_id),
            None,
        )
        assert restored_node is not None
        assert restored_node["data"]["ghost"] is True
        assert restored_node["data"]["ghost_reason"] == "deleted_from_inventory"

    def test_restore_preserves_power_watts_for_canvas_delete(
        self,
        client: TestClient,
        contributor_token: str,
    ) -> None:
        headers = {"Authorization": f"Bearer {contributor_token}"}
        create_response = client.post(
            "/api/devices/",
            json={
                "name": "restore-powered-device",
                "type": "Server",
                "power_watts": 480,
            },
            headers=headers,
        )
        assert create_response.status_code == 201, create_response.text
        device_id = str(create_response.json()["id"])

        _create_diagram(
            client,
            headers,
            "Power Restore View",
            {
                "elements": [
                    {
                        "group": "nodes",
                        "data": {"id": device_id, "label": "restore-powered-device"},
                        "position": {"x": 10, "y": 20},
                    }
                ]
            },
        )

        delete_response = client.post(
            f"/api/devices/{device_id}/canvas-delete",
            headers=headers,
        )
        assert delete_response.status_code == 200, delete_response.text

        restore_response = client.post(
            f"/api/devices/{device_id}/restore",
            headers=headers,
            json=delete_response.json()["snapshot"],
        )
        assert restore_response.status_code == 200, restore_response.text

        restored_response = client.get(f"/api/devices/{device_id}", headers=headers)

        assert restored_response.status_code == 200, restored_response.text
        assert restored_response.json()["power_watts"] == 480

    def test_canvas_delete_snapshot_captures_attached_service_inventory(
        self,
        client: TestClient,
        contributor_token: str,
    ) -> None:
        headers = {"Authorization": f"Bearer {contributor_token}"}
        device_id = _create_device(client, headers, "snapshot-service-device")
        service = _create_service(client, headers, device_id, "https")
        _create_diagram(
            client,
            headers,
            "Service Snapshot View",
            {
                "elements": [
                    {
                        "group": "nodes",
                        "data": {"id": device_id, "label": "snapshot-service-device"},
                        "position": {"x": 10, "y": 20},
                    }
                ]
            },
        )

        delete_response = client.post(
            f"/api/devices/{device_id}/canvas-delete",
            headers=headers,
        )

        assert delete_response.status_code == 200, delete_response.text

        snapshot = delete_response.json()["snapshot"]
        device_snapshot = snapshot["device"]
        service_snapshots = snapshot.get("services")
        if service_snapshots is None:
            service_snapshots = device_snapshot.get("services")

        assert isinstance(service_snapshots, list)
        assert any(
            isinstance(entry, dict)
            and entry.get("id") == service["id"]
            and entry.get("name") == service["name"]
            for entry in service_snapshots
        )

    def test_restore_round_trips_device_scoped_inventory(
        self,
        client: TestClient,
        contributor_token: str,
    ) -> None:
        headers = {"Authorization": f"Bearer {contributor_token}"}
        create_response = client.post(
            "/api/devices/",
            json={
                "name": "restore-inventory-device",
                "type": "Server",
                "power_watts": 350,
            },
            headers=headers,
        )
        assert create_response.status_code == 201, create_response.text
        device_id = str(create_response.json()["id"])

        tag = _create_tag(client, headers, "restore-inventory-tag")
        attach_tag_response = client.post(
            f"/api/devices/{device_id}/tags",
            json={"tag_id": tag["id"]},
            headers=headers,
        )
        assert attach_tag_response.status_code == 204, attach_tag_response.text

        custom_field_response = client.post(
            f"/api/devices/{device_id}/custom-fields",
            json={"key": "serial", "value": "restore-serial"},
            headers=headers,
        )
        assert custom_field_response.status_code == 201, custom_field_response.text
        custom_field = custom_field_response.json()

        network = _create_network(client, headers, "restore-inventory-network")
        attach_network_response = client.post(
            f"/api/devices/{device_id}/networks",
            json={"network_id": network["id"], "ip_address": "10.22.0.15"},
            headers=headers,
        )
        assert attach_network_response.status_code == 201, attach_network_response.text

        service_a = _create_service(client, headers, device_id, "https")
        service_b = _create_service(client, headers, device_id, "metrics")
        dependency_response = client.post(
            f"/api/services/{service_a['id']}/dependencies",
            json={"depends_on": service_b["id"]},
            headers=headers,
        )
        assert dependency_response.status_code == 201, dependency_response.text

        delete_response = client.post(
            f"/api/devices/{device_id}/canvas-delete",
            headers=headers,
        )
        assert delete_response.status_code == 200, delete_response.text

        restore_response = client.post(
            f"/api/devices/{device_id}/restore",
            headers=headers,
            json=delete_response.json()["snapshot"],
        )
        assert restore_response.status_code == 200, restore_response.text

        restored_device = client.get(f"/api/devices/{device_id}", headers=headers)
        assert restored_device.status_code == 200, restored_device.text
        assert restored_device.json()["power_watts"] == 350

        restored_tags = client.get(f"/api/devices/{device_id}/tags", headers=headers)
        assert restored_tags.status_code == 200, restored_tags.text
        assert {row["id"] for row in restored_tags.json()} == {tag["id"]}

        restored_custom_fields = client.get(
            f"/api/devices/{device_id}/custom-fields",
            headers=headers,
        )
        assert restored_custom_fields.status_code == 200, restored_custom_fields.text
        assert [
            {
                "id": row["id"],
                "device_id": row["device_id"],
                "key": row["key"],
                "value": row["value"],
            }
            for row in restored_custom_fields.json()
        ] == [
            {
                "id": custom_field["id"],
                "device_id": custom_field["device_id"],
                "key": custom_field["key"],
                "value": custom_field["value"],
            }
        ]

        restored_networks = client.get(f"/api/devices/{device_id}/networks", headers=headers)
        assert restored_networks.status_code == 200, restored_networks.text
        assert any(
            row["network_id"] == network["id"] and row["ip_address"] == "10.22.0.15"
            for row in restored_networks.json()
        )

        restored_services = client.get(f"/api/devices/{device_id}/services", headers=headers)
        assert restored_services.status_code == 200, restored_services.text
        restored_service_ids = {row["id"] for row in restored_services.json()}
        assert restored_service_ids == {service_a["id"], service_b["id"]}

        restored_dependencies = client.get(
            f"/api/services/{service_a['id']}/dependencies",
            headers=headers,
        )
        assert restored_dependencies.status_code == 200, restored_dependencies.text
        assert [row["id"] for row in restored_dependencies.json()] == [service_b["id"]]

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
