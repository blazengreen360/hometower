"""Integration tests for HT-024 IPAM API endpoints."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _create_device(client: TestClient, token: str, *, name: str) -> dict[str, object]:
    response = client.post(
        "/api/devices/",
        json={"name": name, "type": "Server"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_network(
    client: TestClient,
    token: str,
    *,
    name: str,
    cidr: str,
    gateway: str | None,
    vlan_id: int | None = None,
) -> dict[str, object]:
    response = client.post(
        "/api/networks/",
        json={
            "name": name,
            "vlan_id": vlan_id,
            "cidr": cidr,
            "gateway": gateway,
            "description": "ipam test",
            "color": "#3b82f6",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _attach_device(
    client: TestClient,
    token: str,
    *,
    device_id: str,
    network_id: str,
    ip_address: str,
) -> None:
    response = client.post(
        f"/api/devices/{device_id}/networks",
        json={"network_id": network_id, "ip_address": ip_address},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201, response.text


class TestIpamApi:
    def test_reader_can_list_ipam_networks(
        self,
        client: TestClient,
        contributor_token: str,
        reader_token: str,
    ) -> None:
        suffix = uuid.uuid4().hex[:8]
        network = _create_network(
            client,
            contributor_token,
            name=f"IPAM-LIST-{suffix}",
            cidr="10.60.0.0/24",
            gateway="10.60.0.1",
            vlan_id=60,
        )
        device = _create_device(client, contributor_token, name=f"ipam-reader-{suffix}")
        _attach_device(
            client,
            contributor_token,
            device_id=str(device["id"]),
            network_id=str(network["id"]),
            ip_address="10.60.0.10",
        )

        response = client.get(
            "/api/ipam/networks",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["summary"]["total_networks"] >= 1
        item = next(n for n in body["items"] if n["network_id"] == network["id"])
        assert item["render_mode"] == "grid"
        assert item["device_claim_count"] == 1

    def test_reader_can_get_ipam_detail_for_grid_network(
        self,
        client: TestClient,
        contributor_token: str,
        reader_token: str,
    ) -> None:
        suffix = uuid.uuid4().hex[:8]
        network = _create_network(
            client,
            contributor_token,
            name=f"IPAM-GRID-{suffix}",
            cidr="10.61.0.0/24",
            gateway="10.61.0.1",
            vlan_id=61,
        )
        device = _create_device(client, contributor_token, name=f"ipam-grid-{suffix}")
        _attach_device(
            client,
            contributor_token,
            device_id=str(device["id"]),
            network_id=str(network["id"]),
            ip_address="10.61.0.42",
        )

        response = client.get(
            f"/api/ipam/networks/{network['id']}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["network"]["render_mode"] == "grid"
        assert len(body["cells"]) == 256

    def test_reader_can_get_ipam_detail_for_block_summary_network(
        self,
        client: TestClient,
        contributor_token: str,
        reader_token: str,
    ) -> None:
        suffix = uuid.uuid4().hex[:8]
        network = _create_network(
            client,
            contributor_token,
            name=f"IPAM-BLOCK-{suffix}",
            cidr="10.62.0.0/16",
            gateway="10.62.0.1",
            vlan_id=62,
        )
        device = _create_device(client, contributor_token, name=f"ipam-block-{suffix}")
        _attach_device(
            client,
            contributor_token,
            device_id=str(device["id"]),
            network_id=str(network["id"]),
            ip_address="10.62.5.77",
        )

        response = client.get(
            f"/api/ipam/networks/{network['id']}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["network"]["render_mode"] == "block_summary"
        assert body["cells"] == []
        assert len(body["blocks"]) >= 1

    def test_ipam_summary_reports_conflict_counts_for_duplicate_claims(
        self,
        client: TestClient,
        contributor_token: str,
        reader_token: str,
    ) -> None:
        suffix = uuid.uuid4().hex[:8]
        network = _create_network(
            client,
            contributor_token,
            name=f"IPAM-CONFLICT-SUM-{suffix}",
            cidr="10.63.0.0/24",
            gateway="10.63.0.1",
            vlan_id=63,
        )
        device_a = _create_device(client, contributor_token, name=f"ipam-a-{suffix}")
        device_b = _create_device(client, contributor_token, name=f"ipam-b-{suffix}")
        _attach_device(
            client,
            contributor_token,
            device_id=str(device_a["id"]),
            network_id=str(network["id"]),
            ip_address="10.63.0.77",
        )
        _attach_device(
            client,
            contributor_token,
            device_id=str(device_b["id"]),
            network_id=str(network["id"]),
            ip_address="10.63.0.77",
        )

        response = client.get(
            "/api/ipam/networks",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        item = next(n for n in body["items"] if n["network_id"] == network["id"])
        assert item["conflict_ip_count"] == 1
        assert item["device_claim_count"] == 2

    def test_ipam_detail_returns_conflict_cell_with_multiple_device_claims(
        self,
        client: TestClient,
        contributor_token: str,
        reader_token: str,
    ) -> None:
        suffix = uuid.uuid4().hex[:8]
        network = _create_network(
            client,
            contributor_token,
            name=f"IPAM-CONFLICT-DETAIL-{suffix}",
            cidr="10.64.0.0/24",
            gateway="10.64.0.1",
            vlan_id=64,
        )
        device_a = _create_device(client, contributor_token, name=f"ipam-da-{suffix}")
        device_b = _create_device(client, contributor_token, name=f"ipam-db-{suffix}")
        _attach_device(
            client,
            contributor_token,
            device_id=str(device_a["id"]),
            network_id=str(network["id"]),
            ip_address="10.64.0.90",
        )
        _attach_device(
            client,
            contributor_token,
            device_id=str(device_b["id"]),
            network_id=str(network["id"]),
            ip_address="10.64.0.90",
        )

        response = client.get(
            f"/api/ipam/networks/{network['id']}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        allocation = next(a for a in body["allocations"] if a["address"] == "10.64.0.90")
        assert allocation["status"] == "conflict"
        assert len(allocation["device_claims"]) == 2

    def test_ipam_detail_returns_unsupported_for_ipv6_network(
        self,
        client: TestClient,
        contributor_token: str,
        reader_token: str,
    ) -> None:
        suffix = uuid.uuid4().hex[:8]
        network = _create_network(
            client,
            contributor_token,
            name=f"IPAM-IPV6-{suffix}",
            cidr="fd00::/64",
            gateway="fd00::1",
            vlan_id=None,
        )

        response = client.get(
            f"/api/ipam/networks/{network['id']}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["network"]["render_mode"] == "unsupported"
        assert body["cells"] == []
        assert body["blocks"] == []
        assert body["allocations"] == []

    def test_missing_network_returns_404(self, client: TestClient, reader_token: str) -> None:
        missing_id = uuid.uuid4()
        response = client.get(
            f"/api/ipam/networks/{missing_id}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Network not found"

    def test_unauthenticated_request_is_rejected_by_middleware(self, client: TestClient) -> None:
        response = client.get("/api/ipam/networks")
        assert response.status_code == 401
