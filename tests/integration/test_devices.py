"""Integration tests for /api/devices/ CRUD endpoints and access control."""
import uuid
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from src.models.device import Device
from src.models.types import Role
from src.models.user import User
from src.repositories import device_repository_support
from src.services import device_layout_service_support
from src.utils.auth import create_jwt, hash_password

DEVICE_PAYLOAD: dict[str, str] = {"name": "test-server", "type": "Server"}


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_user(session: Session, role: Role = Role.Contributor) -> tuple[User, str]:
    user = User(
        username=f"devices_{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:8]}@devices.local",
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


def _create_workspace(
    client: TestClient,
    token: str,
    name: str,
) -> dict[str, object]:
    response = client.post(
        "/api/workspaces/",
        json={"name": name},
        headers=_auth(token),
    )
    assert response.status_code == 201
    return response.json()


def _create_topology(
    client: TestClient,
    token: str,
    workspace_id: str,
    name: str,
) -> dict[str, object]:
    response = client.post(
        f"/api/workspaces/{workspace_id}/topologies/",
        json={"name": name},
        headers=_auth(token),
    )
    assert response.status_code == 201
    return response.json()


def _save_topology_version(
    client: TestClient,
    token: str,
    topology_id: str,
    snapshot_name: str,
    device_ids: list[str],
) -> None:
    nodes = [
        {
            "data": {
                "id": f"node-{index}",
                "device_id": device_id,
            },
            "position": {"x": index * 120, "y": 100},
        }
        for index, device_id in enumerate(device_ids, start=1)
    ]
    response = client.post(
        f"/api/topologies/{topology_id}/save-version",
        json={
            "snapshot_name": snapshot_name,
            "cytoscape_json": {
                "elements": {"nodes": nodes, "edges": []},
                "zoom": 1,
                "pan": {"x": 0, "y": 0},
                "collapsedNodes": [],
            },
        },
        headers=_auth(token),
    )
    assert response.status_code == 200


class TestCreateDevice:
    def test_create_device_as_contributor_returns_201(
        self, client: TestClient, contributor_token: str
    ) -> None:
        response = client.post(
            "/api/devices/",
            json=DEVICE_PAYLOAD,
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-server"
        assert data["type"] == "Server"
        assert "id" in data
        assert "created_at" in data

    def test_create_device_persists_power_watts(
        self, client: TestClient, contributor_token: str
    ) -> None:
        response = client.post(
            "/api/devices/",
            json={"name": "power-device", "type": "Server", "power_watts": 65},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 201
        assert response.json()["power_watts"] == 65

    def test_create_device_stamps_authenticated_owner_id(
        self, client: TestClient, session: Session
    ) -> None:
        owner, owner_token = _make_user(session, Role.Contributor)

        response = client.post(
            "/api/devices/",
            json={"name": "owned-device", "type": "Server"},
            headers=_auth(owner_token),
        )

        assert response.status_code == 201
        created_id = uuid.UUID(response.json()["id"])
        persisted = session.exec(
            select(Device).where(Device.id == created_id)
        ).one()
        assert persisted.owner_id == owner.id

    def test_create_device_as_reader_returns_403(
        self, client: TestClient, reader_token: str
    ) -> None:
        response = client.post(
            "/api/devices/",
            json=DEVICE_PAYLOAD,
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 403


class TestGetDevice:
    def test_get_device_by_id_returns_200(
        self, session: Session, client: TestClient
    ) -> None:
        owner, owner_token = _make_user(session, Role.Contributor)
        create_resp = client.post(
            "/api/devices/",
            json={"name": "get-me", "type": "Router"},
            headers=_auth(owner_token),
        )
        assert create_resp.status_code == 201
        device_id = create_resp.json()["id"]

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
            f"/api/devices/{device_id}",
            headers=_auth(owner_reader_token),
        )
        assert response.status_code == 200
        assert response.json()["name"] == "get-me"

    def test_get_nonexistent_device_returns_404(
        self, client: TestClient, reader_token: str
    ) -> None:
        response = client.get(
            f"/api/devices/{uuid4()}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 404

    def test_get_other_owner_device_returns_404(
        self, session: Session, client: TestClient
    ) -> None:
        _, owner_token = _make_user(session, Role.Contributor)
        _, other_reader_token = _make_user(session, Role.Reader)

        create_resp = client.post(
            "/api/devices/",
            json={"name": "owner-only", "type": "Router"},
            headers=_auth(owner_token),
        )
        assert create_resp.status_code == 201
        device_id = create_resp.json()["id"]

        response = client.get(
            f"/api/devices/{device_id}",
            headers=_auth(other_reader_token),
        )

        assert response.status_code == 404


class TestListDevices:
    def test_list_devices_returns_paginated_response(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        client.post(
            "/api/devices/",
            json={"name": "list-me", "type": "Switch"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        response = client.get(
            "/api/devices/",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert isinstance(data["items"], list)

    def test_list_devices_pagination_params(
        self, client: TestClient, reader_token: str
    ) -> None:
        response = client.get(
            "/api/devices/?page=2&limit=10",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["limit"] == 10

    def test_list_devices_workspace_scope_uses_current_diagram_membership(
        self, client: TestClient, contributor_token: str
    ) -> None:
        headers = _auth(contributor_token)
        workspace_one = _create_workspace(client, contributor_token, "Scoped One")
        workspace_two = _create_workspace(client, contributor_token, "Scoped Two")
        topology_one = _create_topology(
            client, contributor_token, str(workspace_one["id"]), "Topo One"
        )
        topology_two = _create_topology(
            client, contributor_token, str(workspace_two["id"]), "Topo Two"
        )

        stale_device = client.post(
            "/api/devices/",
            json={"name": "Stale Device", "type": "Server"},
            headers=headers,
        ).json()
        current_device = client.post(
            "/api/devices/",
            json={"name": "Current Device", "type": "Server"},
            headers=headers,
        ).json()
        other_workspace_device = client.post(
            "/api/devices/",
            json={"name": "Other Workspace Device", "type": "Switch"},
            headers=headers,
        ).json()

        _save_topology_version(
            client,
            contributor_token,
            str(topology_one["id"]),
            "Initial",
            [str(stale_device["id"])],
        )
        _save_topology_version(
            client,
            contributor_token,
            str(topology_one["id"]),
            "Current",
            [str(current_device["id"])],
        )
        _save_topology_version(
            client,
            contributor_token,
            str(topology_two["id"]),
            "Other Workspace",
            [str(other_workspace_device["id"])],
        )

        raw_response = client.get(
            f"/api/devices/?workspace_id={workspace_one['id']}&limit=1000",
            headers=headers,
        )
        enriched_response = client.get(
            f"/api/devices/?workspace_id={workspace_one['id']}&include=location&limit=1000",
            headers=headers,
        )

        assert raw_response.status_code == 200
        assert enriched_response.status_code == 200
        assert raw_response.json()["total"] == 1
        assert [item["name"] for item in raw_response.json()["items"]] == ["Current Device"]
        assert enriched_response.json()["total"] == 1
        assert [item["name"] for item in enriched_response.json()["items"]] == [
            "Current Device"
        ]

    def test_list_devices_workspace_scope_excludes_foreign_same_diagram_devices(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, owner_one_token = _make_user(session, Role.Contributor)
        _, owner_two_token = _make_user(session, Role.Contributor)

        workspace = _create_workspace(client, owner_one_token, "Mixed Scope Workspace")
        topology = _create_topology(
            client,
            owner_one_token,
            str(workspace["id"]),
            "Mixed Scope Topology",
        )
        owned_device_response = client.post(
            "/api/devices/",
            json={"name": "Mixed Scope Owned Device", "type": "Server"},
            headers=_auth(owner_one_token),
        )
        foreign_device_response = client.post(
            "/api/devices/",
            json={"name": "Mixed Scope Foreign Device", "type": "Switch"},
            headers=_auth(owner_two_token),
        )

        assert owned_device_response.status_code == 201
        assert foreign_device_response.status_code == 201

        owned_device = owned_device_response.json()
        foreign_device = foreign_device_response.json()

        _save_topology_version(
            client,
            owner_one_token,
            str(topology["id"]),
            "Mixed Scope Snapshot",
            [str(owned_device["id"]), str(foreign_device["id"])],
        )

        raw_response = client.get(
            f"/api/devices/?workspace_id={workspace['id']}&limit=1000",
            headers=_auth(owner_one_token),
        )
        enriched_response = client.get(
            f"/api/devices/?workspace_id={workspace['id']}&include=location&limit=1000",
            headers=_auth(owner_one_token),
        )

        assert raw_response.status_code == 200
        assert enriched_response.status_code == 200
        assert raw_response.json()["total"] == 1
        assert [item["name"] for item in raw_response.json()["items"]] == [
            "Mixed Scope Owned Device"
        ]
        assert enriched_response.json()["total"] == 1
        assert [item["name"] for item in enriched_response.json()["items"]] == [
            "Mixed Scope Owned Device"
        ]

    def test_list_devices_workspace_scope_rejects_non_owned_workspace(
        self,
        client: TestClient,
        contributor_token: str,
        reader_token: str,
    ) -> None:
        workspace = _create_workspace(client, contributor_token, "Hidden Workspace")

        response = client.get(
            f"/api/devices/?workspace_id={workspace['id']}",
            headers=_auth(reader_token),
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Workspace not found"

    def test_list_devices_default_scope_excludes_other_owner_devices(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        owner, owner_token = _make_user(session, Role.Contributor)
        _, intruder_token = _make_user(session, Role.Contributor)

        owner_device_response = client.post(
            "/api/devices/",
            json={"name": "Owner Device", "type": "Server"},
            headers=_auth(owner_token),
        )
        intruder_device_response = client.post(
            "/api/devices/",
            json={"name": "Intruder Device", "type": "Switch"},
            headers=_auth(intruder_token),
        )

        assert owner_device_response.status_code == 201
        assert intruder_device_response.status_code == 201

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
            "/api/devices/?limit=1000",
            headers=_auth(owner_reader_token),
        )

        assert response.status_code == 200
        names = [item["name"] for item in response.json()["items"]]
        assert "Owner Device" in names
        assert "Intruder Device" not in names

    def test_list_devices_default_enriched_scope_excludes_other_owner_devices(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        owner, owner_token = _make_user(session, Role.Contributor)
        _, intruder_token = _make_user(session, Role.Contributor)

        owner_device_response = client.post(
            "/api/devices/",
            json={"name": "Owner Device Enriched", "type": "Server"},
            headers=_auth(owner_token),
        )
        intruder_device_response = client.post(
            "/api/devices/",
            json={"name": "Intruder Device Enriched", "type": "Switch"},
            headers=_auth(intruder_token),
        )

        assert owner_device_response.status_code == 201
        assert intruder_device_response.status_code == 201

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
            "/api/devices/?include=location&limit=1000",
            headers=_auth(owner_reader_token),
        )

        assert response.status_code == 200
        names = [item["name"] for item in response.json()["items"]]
        assert "Owner Device Enriched" in names
        assert "Intruder Device Enriched" not in names


class TestUpdateDevice:
    def test_update_device_as_contributor_returns_200(
        self, client: TestClient, contributor_token: str
    ) -> None:
        create_resp = client.post(
            "/api/devices/",
            json={"name": "update-me", "type": "NAS"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert create_resp.status_code == 201
        created = create_resp.json()
        device_id = created["id"]
        created_at = created["created_at"]

        response = client.patch(
            f"/api/devices/{device_id}",
            json={"name": "updated-name", "version": created["version"]},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "updated-name"
        assert data["type"] == "NAS"
        assert data["updated_at"] >= created_at

    def test_update_device_can_set_and_clear_power_watts(
        self, client: TestClient, contributor_token: str
    ) -> None:
        headers = {"Authorization": f"Bearer {contributor_token}"}
        create_resp = client.post(
            "/api/devices/",
            json={"name": "power-edit", "type": "Server"},
            headers=headers,
        )
        assert create_resp.status_code == 201
        created = create_resp.json()

        set_resp = client.patch(
            f"/api/devices/{created['id']}",
            json={"power_watts": 120, "version": created["version"]},
            headers=headers,
        )
        assert set_resp.status_code == 200
        set_payload = set_resp.json()
        assert set_payload["power_watts"] == 120

        clear_resp = client.patch(
            f"/api/devices/{created['id']}",
            json={"power_watts": None, "version": set_payload["version"]},
            headers=headers,
        )
        assert clear_resp.status_code == 200
        assert clear_resp.json()["power_watts"] is None

    def test_update_nonexistent_device_returns_404(
        self, client: TestClient, contributor_token: str
    ) -> None:
        response = client.patch(
            f"/api/devices/{uuid4()}",
            json={"name": "ghost", "version": 1},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 404

    def test_update_other_owner_device_returns_404(
        self, session: Session, client: TestClient
    ) -> None:
        _, owner_token = _make_user(session, Role.Contributor)
        _, other_token = _make_user(session, Role.Contributor)

        create_resp = client.post(
            "/api/devices/",
            json={"name": "owner-update-only", "type": "Server"},
            headers=_auth(owner_token),
        )
        assert create_resp.status_code == 201
        device = create_resp.json()

        response = client.patch(
            f"/api/devices/{device['id']}",
            json={"name": "stolen-update", "version": device["version"]},
            headers=_auth(other_token),
        )

        assert response.status_code == 404

class TestPlacedIdsCurrentTopologyShape:
    def test_placed_ids_support_nested_topology_elements_nodes_shape(
        self, session: Session, client: TestClient
    ) -> None:
        owner, owner_token = _make_user(session, Role.Contributor)

        workspace = _create_workspace(client, owner_token, "Placed IDs Workspace")
        topology = _create_topology(
            client,
            owner_token,
            str(workspace["id"]),
            "Placed IDs Topology",
        )

        placed_response = client.post(
            "/api/devices/",
            json={"name": "nested-placed", "type": "Server"},
            headers=_auth(owner_token),
        )
        unplaced_response = client.post(
            "/api/devices/",
            json={"name": "nested-unplaced", "type": "Switch"},
            headers=_auth(owner_token),
        )

        assert placed_response.status_code == 201
        assert unplaced_response.status_code == 201

        placed_id = placed_response.json()["id"]
        unplaced_id = unplaced_response.json()["id"]

        _save_topology_version(
            client,
            owner_token,
            str(topology["id"]),
            "Nested Shape Snapshot",
            [placed_id],
        )

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
            f"/api/devices/placed-ids?workspace_id={workspace['id']}",
            headers=_auth(owner_reader_token),
        )

        assert response.status_code == 200
        placed_ids = response.json()
        assert placed_id in placed_ids
        assert unplaced_id not in placed_ids

    def test_placed_ids_workspace_scope_excludes_other_owner_devices(
        self, session: Session, client: TestClient
    ) -> None:
        owner, owner_token = _make_user(session, Role.Contributor)
        _, intruder_token = _make_user(session, Role.Contributor)

        owner_workspace = _create_workspace(client, owner_token, "Owner Workspace")
        owner_topology = _create_topology(
            client,
            owner_token,
            str(owner_workspace["id"]),
            "Owner Topology",
        )
        intruder_workspace = _create_workspace(
            client,
            intruder_token,
            "Intruder Workspace",
        )
        intruder_topology = _create_topology(
            client,
            intruder_token,
            str(intruder_workspace["id"]),
            "Intruder Topology",
        )

        owner_device = client.post(
            "/api/devices/",
            json={"name": "owner-placed", "type": "Server"},
            headers=_auth(owner_token),
        )
        intruder_device = client.post(
            "/api/devices/",
            json={"name": "intruder-placed", "type": "Switch"},
            headers=_auth(intruder_token),
        )

        assert owner_device.status_code == 201
        assert intruder_device.status_code == 201

        owner_device_id = owner_device.json()["id"]
        intruder_device_id = intruder_device.json()["id"]

        _save_topology_version(
            client,
            owner_token,
            str(owner_topology["id"]),
            "Owner Snapshot",
            [owner_device_id],
        )
        _save_topology_version(
            client,
            intruder_token,
            str(intruder_topology["id"]),
            "Intruder Snapshot",
            [intruder_device_id],
        )

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
            f"/api/devices/placed-ids?workspace_id={owner_workspace['id']}",
            headers=_auth(owner_reader_token),
        )

        assert response.status_code == 200
        assert owner_device_id in response.json()
        assert intruder_device_id not in response.json()

    def test_placed_ids_legacy_owner_scope_uses_current_diagram_membership(
        self, session: Session, client: TestClient, monkeypatch
    ) -> None:
        owner, owner_token = _make_user(session, Role.Contributor)
        _, intruder_token = _make_user(session, Role.Contributor)

        owner_workspace = _create_workspace(client, owner_token, "Legacy Owner Workspace")
        owner_topology = _create_topology(
            client,
            owner_token,
            str(owner_workspace["id"]),
            "Legacy Owner Topology",
        )
        intruder_workspace = _create_workspace(
            client,
            intruder_token,
            "Legacy Intruder Workspace",
        )
        intruder_topology = _create_topology(
            client,
            intruder_token,
            str(intruder_workspace["id"]),
            "Legacy Intruder Topology",
        )

        owner_device = client.post(
            "/api/devices/",
            json={"name": "legacy-owner-placed", "type": "Server"},
            headers=_auth(owner_token),
        )
        intruder_device = client.post(
            "/api/devices/",
            json={"name": "legacy-intruder-placed", "type": "Switch"},
            headers=_auth(intruder_token),
        )

        assert owner_device.status_code == 201
        assert intruder_device.status_code == 201

        owner_device_id = owner_device.json()["id"]
        intruder_device_id = intruder_device.json()["id"]

        _save_topology_version(
            client,
            owner_token,
            str(owner_topology["id"]),
            "Legacy Owner Snapshot",
            [owner_device_id],
        )
        _save_topology_version(
            client,
            intruder_token,
            str(intruder_topology["id"]),
            "Legacy Intruder Snapshot",
            [intruder_device_id],
        )

        monkeypatch.setattr(
            device_layout_service_support,
            "_device_owner_scope_available",
            lambda _session: False,
        )
        monkeypatch.setattr(
            device_layout_service_support.device_layout_repository_support,
            "get_visible_device_ids",
            lambda _session, _device_ids, _owner_id: set(),
        )

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
            headers=_auth(owner_reader_token),
        )

        assert response.status_code == 200
        placed_ids = response.json()
        assert owner_device_id in placed_ids
        assert intruder_device_id not in placed_ids

    def test_placed_ids_ignore_historical_only_layouts(
        self, session: Session, client: TestClient
    ) -> None:
        owner, owner_token = _make_user(session, Role.Contributor)

        workspace = _create_workspace(client, owner_token, "History Scope Workspace")
        topology = _create_topology(
            client,
            owner_token,
            str(workspace["id"]),
            "History Scope Topology",
        )

        historical_device = client.post(
            "/api/devices/",
            json={"name": "historical-only-device", "type": "Server"},
            headers=_auth(owner_token),
        )
        current_device = client.post(
            "/api/devices/",
            json={"name": "current-device", "type": "Switch"},
            headers=_auth(owner_token),
        )

        assert historical_device.status_code == 201
        assert current_device.status_code == 201

        historical_device_id = historical_device.json()["id"]
        current_device_id = current_device.json()["id"]

        _save_topology_version(
            client,
            owner_token,
            str(topology["id"]),
            "Historical Snapshot",
            [historical_device_id],
        )
        _save_topology_version(
            client,
            owner_token,
            str(topology["id"]),
            "Current Snapshot",
            [current_device_id],
        )

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
            f"/api/devices/placed-ids?workspace_id={workspace['id']}",
            headers=_auth(owner_reader_token),
        )

        assert response.status_code == 200
        placed_ids = response.json()
        assert current_device_id in placed_ids
        assert historical_device_id not in placed_ids

    def test_get_device_legacy_owner_scope_uses_current_diagram_membership(
        self, session: Session, client: TestClient, monkeypatch
    ) -> None:
        owner, owner_token = _make_user(session, Role.Contributor)
        _, intruder_token = _make_user(session, Role.Contributor)

        owner_workspace = _create_workspace(client, owner_token, "Legacy Device Workspace")
        owner_topology = _create_topology(
            client,
            owner_token,
            str(owner_workspace["id"]),
            "Legacy Device Topology",
        )
        intruder_workspace = _create_workspace(
            client,
            intruder_token,
            "Legacy Intruder Device Workspace",
        )
        intruder_topology = _create_topology(
            client,
            intruder_token,
            str(intruder_workspace["id"]),
            "Legacy Intruder Device Topology",
        )

        owner_device = client.post(
            "/api/devices/",
            json={"name": "legacy-readable-device", "type": "Server"},
            headers=_auth(owner_token),
        )
        intruder_device = client.post(
            "/api/devices/",
            json={"name": "legacy-hidden-device", "type": "Switch"},
            headers=_auth(intruder_token),
        )

        assert owner_device.status_code == 201
        assert intruder_device.status_code == 201

        owner_device_id = owner_device.json()["id"]
        intruder_device_id = intruder_device.json()["id"]

        _save_topology_version(
            client,
            owner_token,
            str(owner_topology["id"]),
            "Legacy Device Snapshot",
            [owner_device_id],
        )
        _save_topology_version(
            client,
            intruder_token,
            str(intruder_topology["id"]),
            "Legacy Hidden Snapshot",
            [intruder_device_id],
        )

        monkeypatch.setattr(
            device_repository_support,
            "device_owner_scope_available",
            lambda _session: False,
        )

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
            f"/api/devices/{owner_device_id}",
            headers=_auth(owner_reader_token),
        )
        hidden_response = client.get(
            f"/api/devices/{intruder_device_id}",
            headers=_auth(owner_reader_token),
        )

        assert response.status_code == 200
        assert response.json()["id"] == owner_device_id
        assert hidden_response.status_code == 404

    def test_update_without_version_returns_422(
        self, client: TestClient, contributor_token: str
    ) -> None:
        create_resp = client.post(
            "/api/devices/",
            json={"name": "must-have-version", "type": "NAS"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert create_resp.status_code == 201
        device_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/devices/{device_id}",
            json={"name": "missing-version"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 422

    def test_device_update_rejects_stale_version(
        self, client: TestClient, admin_token: str
    ) -> None:
        headers = {"Authorization": f"Bearer {admin_token}"}
        create_resp = client.post(
            "/api/devices/",
            json={"name": "versioned-device", "type": "Server"},
            headers=headers,
        )
        assert create_resp.status_code == 201
        created = create_resp.json()
        device_id = created["id"]
        current_version = created["version"]

        first_update = client.patch(
            f"/api/devices/{device_id}",
            json={"name": "updated-once", "version": current_version},
            headers=headers,
        )
        assert first_update.status_code == 200

        stale_update = client.patch(
            f"/api/devices/{device_id}",
            json={"ip": "10.0.0.2", "version": 1},
            headers=headers,
        )
        assert stale_update.status_code == 409
        assert stale_update.json()["detail"] == (
            "Conflict: device was modified by another request"
        )

    def test_patch_parent_id_reparents_device_via_device_endpoint(
        self, client: TestClient, contributor_token: str
    ) -> None:
        headers = {"Authorization": f"Bearer {contributor_token}"}
        parent = client.post(
            "/api/devices/",
            json={"name": "parent-device", "type": "Server"},
            headers=headers,
        )
        child = client.post(
            "/api/devices/",
            json={"name": "child-device", "type": "VM"},
            headers=headers,
        )
        assert parent.status_code == 201
        assert child.status_code == 201

        child_payload = child.json()
        parent_id = parent.json()["id"]

        response = client.patch(
            f"/api/devices/{child_payload['id']}",
            json={"parent_id": parent_id, "version": child_payload["version"]},
            headers=headers,
        )

        assert response.status_code == 200
        assert response.json()["parent_id"] == parent_id
        assert response.json()["version"] == child_payload["version"] + 1


class TestDeleteDevice:
    def test_delete_device_as_contributor_returns_204(
        self, client: TestClient, contributor_token: str
    ) -> None:
        create_resp = client.post(
            "/api/devices/",
            json={"name": "delete-me", "type": "VM"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert create_resp.status_code == 201
        device_id = create_resp.json()["id"]

        response = client.delete(
            f"/api/devices/{device_id}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 204

    def test_delete_nonexistent_device_returns_404(
        self, client: TestClient, contributor_token: str
    ) -> None:
        response = client.delete(
            f"/api/devices/{uuid4()}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 404

    def test_delete_device_as_reader_returns_403(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        create_resp = client.post(
            "/api/devices/",
            json={"name": "no-delete", "type": "Docker"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert create_resp.status_code == 201
        device_id = create_resp.json()["id"]

        response = client.delete(
            f"/api/devices/{device_id}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 403

    def test_delete_device_cascades_connections(
        self, client: TestClient, contributor_token: str
    ) -> None:
        headers = {"Authorization": f"Bearer {contributor_token}"}
        d1 = client.post("/api/devices/", json={"name": "src-dev", "type": "Server"}, headers=headers)
        d2 = client.post("/api/devices/", json={"name": "tgt-dev", "type": "Switch"}, headers=headers)
        assert d1.status_code == 201
        assert d2.status_code == 201
        d1_id = d1.json()["id"]
        d2_id = d2.json()["id"]

        conn = client.post(
            "/api/connections/",
            json={"source_id": d1_id, "target_id": d2_id, "type": "Ethernet"},
            headers=headers,
        )
        assert conn.status_code == 201

        # Delete d1 — connection should cascade
        resp = client.delete(f"/api/devices/{d1_id}", headers=headers)
        assert resp.status_code == 204

        # Verify connection is gone
        conns = client.get("/api/connections/", headers=headers)
        assert conns.status_code == 200
        conn_ids = [c["id"] for c in conns.json()["items"]]
        assert conn.json()["id"] not in conn_ids


class TestUnauthenticated:
    def test_unauthenticated_request_returns_401(self, client: TestClient) -> None:
        response = client.get("/api/devices/")
        assert response.status_code == 401
