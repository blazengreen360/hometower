"""Integration tests for HT-022 network and device-network endpoints."""

import uuid

import pytest
from fastapi.testclient import TestClient


def _create_device(client: TestClient, token: str, name: str) -> dict:
    resp = client.post(
        "/api/devices/",
        json={"name": name, "type": "Server"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_network(
    client: TestClient,
    token: str,
    *,
    name: str,
    vlan_id: int | None,
    cidr: str,
    gateway: str | None,
    color: str = "#3b82f6",
) -> dict:
    resp = client.post(
        "/api/networks/",
        json={
            "name": name,
            "vlan_id": vlan_id,
            "cidr": cidr,
            "gateway": gateway,
            "description": "test network",
            "color": color,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _unique_name(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


class TestNetworksCrud:
    def test_create_network_success(self, client: TestClient, contributor_token: str) -> None:
        network_name = _unique_name("Management")
        response = client.post(
            "/api/networks/",
            json={
                "name": network_name,
                "vlan_id": 10,
                "cidr": "10.0.10.0/24",
                "gateway": "10.0.10.1",
                "description": "Management VLAN",
                "color": "#3b82f6",
            },
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["name"] == network_name
        assert body["cidr"] == "10.0.10.0/24"

    def test_create_network_invalid_cidr_returns_400(
        self,
        client: TestClient,
        contributor_token: str,
    ) -> None:
        response = client.post(
            "/api/networks/",
            json={
                "name": _unique_name("Bad CIDR"),
                "vlan_id": 10,
                "cidr": "10.0.10.5/24",
                "gateway": "10.0.10.1",
                "description": "invalid",
                "color": "#3b82f6",
            },
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid CIDR notation"

    def test_create_network_invalid_vlan_returns_400(
        self,
        client: TestClient,
        contributor_token: str,
    ) -> None:
        response = client.post(
            "/api/networks/",
            json={
                "name": _unique_name("Bad VLAN"),
                "vlan_id": 4095,
                "cidr": "10.0.10.0/24",
                "gateway": "10.0.10.1",
                "description": "invalid",
                "color": "#3b82f6",
            },
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "VLAN ID must be between 1 and 4094"

    def test_duplicate_case_insensitive_name_returns_409(
        self,
        client: TestClient,
        contributor_token: str,
    ) -> None:
        base_name = _unique_name("Storage")
        _create_network(
            client,
            contributor_token,
            name=base_name,
            vlan_id=20,
            cidr="10.0.20.0/24",
            gateway="10.0.20.1",
        )
        response = client.post(
            "/api/networks/",
            json={
                "name": base_name.upper(),
                "vlan_id": 21,
                "cidr": "10.0.21.0/24",
                "gateway": "10.0.21.1",
                "description": "dup",
                "color": "#2563eb",
            },
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 409

    def test_reader_is_read_only_for_network_writes(
        self,
        client: TestClient,
        reader_token: str,
    ) -> None:
        response = client.post(
            "/api/networks/",
            json={
                "name": _unique_name("Reader Blocked"),
                "vlan_id": 30,
                "cidr": "10.0.30.0/24",
                "gateway": "10.0.30.1",
                "description": "blocked",
                "color": "#3b82f6",
            },
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 403

    @pytest.mark.parametrize("field_name", ["name", "cidr", "color"])
    def test_patch_rejects_null_for_required_fields_with_400(
        self,
        client: TestClient,
        contributor_token: str,
        field_name: str,
    ) -> None:
        headers = {"Authorization": f"Bearer {contributor_token}"}
        network = _create_network(
            client,
            contributor_token,
            name=_unique_name("PatchNull"),
            vlan_id=222,
            cidr="10.2.22.0/24",
            gateway="10.2.22.1",
        )

        response = client.patch(
            f"/api/networks/{network['id']}",
            json={field_name: None},
            headers=headers,
        )

        assert response.status_code == 400
        assert response.json()["detail"] == f"{field_name} cannot be null"


class TestNetworkMemberships:
    def test_attach_duplicate_and_out_of_subnet_paths(
        self,
        client: TestClient,
        contributor_token: str,
    ) -> None:
        device = _create_device(client, contributor_token, name=f"net-dev-{uuid.uuid4().hex[:8]}")
        network = _create_network(
            client,
            contributor_token,
            name=f"Net-{uuid.uuid4().hex[:8]}",
            vlan_id=40,
            cidr="10.0.40.0/24",
            gateway="10.0.40.1",
        )

        attach_url = f"/api/devices/{device['id']}/networks"
        headers = {"Authorization": f"Bearer {contributor_token}"}

        first = client.post(
            attach_url,
            json={"network_id": network["id"], "ip_address": "10.0.40.20"},
            headers=headers,
        )
        assert first.status_code == 201

        dup = client.post(
            attach_url,
            json={"network_id": network["id"], "ip_address": "10.0.40.21"},
            headers=headers,
        )
        assert dup.status_code == 409

        outside = client.post(
            attach_url,
            json={"network_id": network["id"], "ip_address": "10.0.99.20"},
            headers=headers,
        )
        assert outside.status_code == 400
        assert "is not within subnet" in outside.json()["detail"]

    def test_device_include_networks_and_network_include_devices(
        self,
        client: TestClient,
        contributor_token: str,
    ) -> None:
        device = _create_device(client, contributor_token, name=f"edge-dev-{uuid.uuid4().hex[:8]}")
        network = _create_network(
            client,
            contributor_token,
            name=f"Edge-{uuid.uuid4().hex[:8]}",
            vlan_id=50,
            cidr="10.0.50.0/24",
            gateway="10.0.50.1",
        )

        attach_resp = client.post(
            f"/api/devices/{device['id']}/networks",
            json={"network_id": network["id"], "ip_address": "10.0.50.10"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert attach_resp.status_code == 201

        device_enriched = client.get(
            f"/api/devices/{device['id']}?include=networks",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert device_enriched.status_code == 200
        d_body = device_enriched.json()
        assert len(d_body["networks"]) == 1
        assert d_body["networks"][0]["network_id"] == network["id"]
        assert d_body["networks"][0]["ip_address"] == "10.0.50.10"

        network_enriched = client.get(
            f"/api/networks/{network['id']}?include=devices",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert network_enriched.status_code == 200
        n_body = network_enriched.json()
        assert len(n_body["devices"]) == 1
        assert n_body["devices"][0]["device_id"] == device["id"]
        assert n_body["devices"][0]["ip_address"] == "10.0.50.10"

    def test_delete_blocked_when_members_exist_then_allowed_after_detach(
        self,
        client: TestClient,
        contributor_token: str,
    ) -> None:
        device = _create_device(client, contributor_token, name=f"del-dev-{uuid.uuid4().hex[:8]}")
        network = _create_network(
            client,
            contributor_token,
            name=f"Delete-{uuid.uuid4().hex[:8]}",
            vlan_id=60,
            cidr="10.0.60.0/24",
            gateway="10.0.60.1",
        )

        headers = {"Authorization": f"Bearer {contributor_token}"}
        attach_resp = client.post(
            f"/api/devices/{device['id']}/networks",
            json={"network_id": network["id"], "ip_address": "10.0.60.10"},
            headers=headers,
        )
        assert attach_resp.status_code == 201

        blocked_delete = client.delete(f"/api/networks/{network['id']}", headers=headers)
        assert blocked_delete.status_code == 400

        detach_resp = client.delete(
            f"/api/devices/{device['id']}/networks/{network['id']}",
            headers=headers,
        )
        assert detach_resp.status_code == 204

        final_delete = client.delete(f"/api/networks/{network['id']}", headers=headers)
        assert final_delete.status_code == 204

    def test_update_cidr_rejects_existing_membership_outside_new_subnet(
        self,
        client: TestClient,
        contributor_token: str,
    ) -> None:
        device = _create_device(client, contributor_token, name=f"upd-dev-{uuid.uuid4().hex[:8]}")
        network = _create_network(
            client,
            contributor_token,
            name=f"Update-{uuid.uuid4().hex[:8]}",
            vlan_id=70,
            cidr="10.0.70.0/24",
            gateway="10.0.70.1",
        )

        headers = {"Authorization": f"Bearer {contributor_token}"}
        attach_resp = client.post(
            f"/api/devices/{device['id']}/networks",
            json={"network_id": network["id"], "ip_address": "10.0.70.20"},
            headers=headers,
        )
        assert attach_resp.status_code == 201

        update_resp = client.patch(
            f"/api/networks/{network['id']}",
            json={"cidr": "10.0.71.0/24"},
            headers=headers,
        )
        assert update_resp.status_code == 400
        assert "is not within subnet" in update_resp.json()["detail"]
