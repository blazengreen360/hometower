"""Integration tests for /api/locations endpoints."""
import uuid
from typing import Generator

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_rack(
    client: TestClient, token: str, name: str = "Main Rack", **kwargs
) -> dict:
    payload = {"name": name, "type": "rack", **kwargs}
    resp = client.post(
        "/api/locations/",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_geo(
    client: TestClient, token: str, name: str = "HQ Site", **kwargs
) -> dict:
    payload = {"name": name, "type": "geo", "lat": 51.5, "lng": -0.1, **kwargs}
    resp = client.post(
        "/api/locations/",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_device(
    client: TestClient,
    token: str,
    name: str,
    location_id: str | None = None,
) -> dict:
    payload: dict[str, str | None] = {
        "name": name,
        "type": "Server",
        "location_id": location_id,
    }
    resp = client.post(
        "/api/devices/",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# CRUD — basic
# ---------------------------------------------------------------------------


class TestCreateLocation:
    def test_create_rack_location(
        self, client: TestClient, contributor_token: str
    ) -> None:
        loc = _create_rack(client, contributor_token, rack="A", row="1")
        assert loc["type"] == "rack"
        assert loc["rack"] == "A"
        assert loc["row"] == "1"
        assert "id" in loc

    def test_create_rack_whitespace_rack_normalizes_to_none(
        self, client: TestClient, contributor_token: str
    ) -> None:
        loc = _create_rack(client, contributor_token, name="Rack Trim", rack="   ")
        assert loc["type"] == "rack"
        assert loc["rack"] is None

    def test_create_geo_location(
        self, client: TestClient, contributor_token: str
    ) -> None:
        loc = _create_geo(client, contributor_token, name="Berlin Office")
        assert loc["type"] == "geo"
        assert loc["lat"] == 51.5
        assert loc["lng"] == -0.1

    def test_create_requires_contributor(
        self, client: TestClient, reader_token: str
    ) -> None:
        resp = client.post(
            "/api/locations/",
            json={"name": "Blocked", "type": "rack"},
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 403

    def test_geo_missing_lat_returns_400(
        self, client: TestClient, contributor_token: str
    ) -> None:
        resp = client.post(
            "/api/locations/",
            json={"name": "Bad Geo", "type": "geo", "lng": -0.1},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 400
        assert "lat and lng" in resp.json()["detail"]

    def test_rack_with_coordinates_returns_400(
        self, client: TestClient, contributor_token: str
    ) -> None:
        resp = client.post(
            "/api/locations/",
            json={"name": "Bad Rack", "type": "rack", "lat": 51.5, "lng": -0.1},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 400
        assert "coordinates" in resp.json()["detail"]

    def test_parent_id_not_found_returns_404(
        self, client: TestClient, contributor_token: str
    ) -> None:
        resp = client.post(
            "/api/locations/",
            json={
                "name": "Child",
                "type": "rack",
                "parent_id": str(uuid.uuid4()),
            },
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 404

    def test_create_with_valid_parent(
        self, client: TestClient, contributor_token: str
    ) -> None:
        parent = _create_rack(client, contributor_token, name="Parent Rack")
        child = _create_rack(
            client,
            contributor_token,
            name="Child Rack",
            parent_id=parent["id"],
        )
        assert child["parent_id"] == parent["id"]


class TestGetLocation:
    def test_get_by_id(self, client: TestClient, contributor_token: str) -> None:
        loc = _create_rack(client, contributor_token)
        resp = client.get(
            f"/api/locations/{loc['id']}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == loc["id"]

    def test_get_not_found(self, client: TestClient, reader_token: str) -> None:
        resp = client.get(
            f"/api/locations/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 404

    def test_get_reader_allowed(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        loc = _create_rack(client, contributor_token)
        resp = client.get(
            f"/api/locations/{loc['id']}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 200

    def test_get_with_ancestors(
        self, client: TestClient, contributor_token: str
    ) -> None:
        grandparent = _create_rack(client, contributor_token, name="GP")
        parent = _create_rack(
            client, contributor_token, name="Parent", parent_id=grandparent["id"]
        )
        child = _create_rack(
            client, contributor_token, name="Child", parent_id=parent["id"]
        )
        resp = client.get(
            f"/api/locations/{child['id']}?include=ancestors",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "ancestors" in data
        ancestor_ids = [a["id"] for a in data["ancestors"]]
        assert parent["id"] in ancestor_ids
        assert grandparent["id"] in ancestor_ids


class TestListLocations:
    def test_list_all(
        self, client: TestClient, contributor_token: str
    ) -> None:
        _create_rack(client, contributor_token, name="List Rack A")
        _create_geo(client, contributor_token, name="List Geo A")
        resp = client.get(
            "/api/locations/",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) >= 2

    def test_filter_by_type_rack(
        self, client: TestClient, contributor_token: str
    ) -> None:
        _create_rack(client, contributor_token, name="Filter Rack B")
        _create_geo(client, contributor_token, name="Filter Geo B")
        resp = client.get(
            "/api/locations/?type=rack",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        assert all(loc["type"] == "rack" for loc in resp.json())

    def test_filter_by_type_geo(
        self, client: TestClient, contributor_token: str
    ) -> None:
        _create_geo(client, contributor_token, name="Filter Geo C")
        resp = client.get(
            "/api/locations/?type=geo",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        assert all(loc["type"] == "geo" for loc in resp.json())

    def test_include_devices_returns_geo_map_payload(
        self,
        client: TestClient,
        contributor_token: str,
        reader_token: str,
    ) -> None:
        target_geo = _create_geo(client, contributor_token, name="Map Site")
        _create_geo(client, contributor_token, name="Other Site")
        _create_rack(client, contributor_token, name="Not On Map", rack="A", row="1")

        first = _create_device(
            client,
            contributor_token,
            name="Map Device One",
            location_id=target_geo["id"],
        )
        second = _create_device(
            client,
            contributor_token,
            name="Map Device Two",
            location_id=target_geo["id"],
        )

        resp = client.get(
            "/api/locations/?type=geo&include=devices",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 200
        payload = resp.json()

        match = next((item for item in payload if item["id"] == target_geo["id"]), None)
        assert match is not None
        assert match["name"] == "Map Site"
        assert match["lat"] == 51.5
        assert match["lng"] == -0.1
        assert match["device_count"] == 2
        assert {device["id"] for device in match["devices"]} == {
            first["id"],
            second["id"],
        }
        for device in match["devices"]:
            assert set(device.keys()) == {"id", "name", "type", "status"}

    def test_without_include_devices_preserves_existing_shape(
        self,
        client: TestClient,
        contributor_token: str,
    ) -> None:
        geo = _create_geo(client, contributor_token, name="Legacy Shape")
        _create_device(
            client,
            contributor_token,
            name="Legacy Device",
            location_id=geo["id"],
        )

        resp = client.get(
            "/api/locations/?type=geo",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        payload = resp.json()
        match = next((item for item in payload if item["id"] == geo["id"]), None)
        assert match is not None
        assert "device_count" not in match
        assert "devices" not in match


class TestUpdateLocation:
    def test_update_name(
        self, client: TestClient, contributor_token: str
    ) -> None:
        loc = _create_rack(client, contributor_token, name="Original Name")
        resp = client.patch(
            f"/api/locations/{loc['id']}",
            json={"name": "Updated Name"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"

    def test_update_type_consistency_enforced(
        self, client: TestClient, contributor_token: str
    ) -> None:
        loc = _create_rack(client, contributor_token, name="Type Switch")
        # Switch to geo without providing lat/lng — must fail
        resp = client.patch(
            f"/api/locations/{loc['id']}",
            json={"type": "geo"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 400
        assert "lat and lng" in resp.json()["detail"]

    def test_update_not_found(
        self, client: TestClient, contributor_token: str
    ) -> None:
        resp = client.patch(
            f"/api/locations/{uuid.uuid4()}",
            json={"name": "Ghost"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 404

    def test_cycle_detection_on_update(
        self, client: TestClient, contributor_token: str
    ) -> None:
        parent = _create_rack(client, contributor_token, name="Cycle Parent")
        child = _create_rack(
            client,
            contributor_token,
            name="Cycle Child",
            parent_id=parent["id"],
        )
        # Try to set parent's parent to child — would create cycle
        resp = client.patch(
            f"/api/locations/{parent['id']}",
            json={"parent_id": child["id"]},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 400
        assert "Cycle" in resp.json()["detail"]

    def test_update_parent_id_not_found_returns_404(
        self, client: TestClient, contributor_token: str
    ) -> None:
        loc = _create_rack(client, contributor_token, name="Parent Missing")
        resp = client.patch(
            f"/api/locations/{loc['id']}",
            json={"parent_id": str(uuid.uuid4())},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 404
        assert "Parent location not found" in resp.json()["detail"]

    def test_update_requires_contributor(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        loc = _create_rack(client, contributor_token, name="RBAC Test")
        resp = client.patch(
            f"/api/locations/{loc['id']}",
            json={"name": "Blocked"},
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 403

    def test_update_rejects_negative_row_without_mutating_db(
        self, client: TestClient, contributor_token: str
    ) -> None:
        loc = _create_rack(
            client,
            contributor_token,
            name="Invalid Row",
            rack="A",
            row="1",
        )
        resp = client.patch(
            f"/api/locations/{loc['id']}",
            json={"row": "-1"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 422

        get_resp = client.get(
            f"/api/locations/{loc['id']}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["row"] == "1"

    def test_update_rejects_whitespace_row_with_422(
        self, client: TestClient, contributor_token: str
    ) -> None:
        loc = _create_rack(client, contributor_token, name="Whitespace Row")
        resp = client.patch(
            f"/api/locations/{loc['id']}",
            json={"row": "   "},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 422

    def test_update_rejects_dash_only_row_with_422(
        self, client: TestClient, contributor_token: str
    ) -> None:
        loc = _create_rack(client, contributor_token, name="Dash Row")
        resp = client.patch(
            f"/api/locations/{loc['id']}",
            json={"row": "---"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 422

    def test_update_whitespace_rack_normalizes_to_none(
        self, client: TestClient, contributor_token: str
    ) -> None:
        loc = _create_rack(client, contributor_token, name="Rack Normalize", rack="A")
        resp = client.patch(
            f"/api/locations/{loc['id']}",
            json={"rack": "   "},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["rack"] is None

    def test_update_rejects_whitespace_only_name(
        self, client: TestClient, contributor_token: str
    ) -> None:
        loc = _create_rack(client, contributor_token, name="Blank Guard")
        resp = client.patch(
            f"/api/locations/{loc['id']}",
            json={"name": "   "},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 422

    def test_update_rejects_empty_name(
        self, client: TestClient, contributor_token: str
    ) -> None:
        loc = _create_rack(client, contributor_token, name="Empty Guard")
        resp = client.patch(
            f"/api/locations/{loc['id']}",
            json={"name": ""},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 422


class TestDeleteLocation:
    def test_delete_location(
        self, client: TestClient, contributor_token: str
    ) -> None:
        loc = _create_rack(client, contributor_token, name="To Delete")
        resp = client.delete(
            f"/api/locations/{loc['id']}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 204
        # Confirm it's gone
        get_resp = client.get(
            f"/api/locations/{loc['id']}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert get_resp.status_code == 404

    def test_delete_not_found(
        self, client: TestClient, contributor_token: str
    ) -> None:
        resp = client.delete(
            f"/api/locations/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 404

    def test_delete_requires_contributor(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        loc = _create_rack(client, contributor_token, name="Reader Cannot Delete")
        resp = client.delete(
            f"/api/locations/{loc['id']}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 403

    def test_delete_blocked_when_device_assigned(
        self, client: TestClient, contributor_token: str
    ) -> None:
        loc = _create_rack(client, contributor_token, name="Occupied Rack")
        # Create a device assigned to this location
        client.post(
            "/api/devices/",
            json={
                "name": "rack-device",
                "type": "Server",
                "location_id": loc["id"],
            },
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        resp = client.delete(
            f"/api/locations/{loc['id']}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 400
        assert "assigned" in resp.json()["detail"]

    def test_delete_blocked_when_child_locations_exist(
        self, client: TestClient, contributor_token: str
    ) -> None:
        parent = _create_rack(client, contributor_token, name="Parent Rack")
        _create_rack(
            client,
            contributor_token,
            name="Child Rack",
            parent_id=parent["id"],
        )
        resp = client.delete(
            f"/api/locations/{parent['id']}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 400
        assert (
            resp.json()["detail"]
            == "Location has child locations. Reassign or delete them first."
        )


class TestLocationTypeTransition:
    """Tests for switching location type via PATCH (rack to geo and back)."""

    def test_rack_to_geo_clears_rack_fields(
        self, client: TestClient, contributor_token: str
    ) -> None:
        loc = _create_rack(
            client, contributor_token, name="Garage", rack="A", row="2"
        )
        resp = client.patch(
            f"/api/locations/{loc['id']}",
            json={
                "type": "geo",
                "lat": 51.5,
                "lng": -0.1,
                "rack": None,
                "row": None,
                "parent_id": None,
            },
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["type"] == "geo"
        assert body["lat"] == 51.5
        assert body["lng"] == -0.1
        assert body["rack"] is None
        assert body["row"] is None

    def test_geo_to_rack_clears_geo_fields(
        self, client: TestClient, contributor_token: str
    ) -> None:
        loc = _create_geo(client, contributor_token, name="DC London")
        resp = client.patch(
            f"/api/locations/{loc['id']}",
            json={
                "type": "rack",
                "lat": None,
                "lng": None,
                "rack": "B",
                "row": "1",
            },
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["type"] == "rack"
        assert body["rack"] == "B"
        assert body["row"] == "1"
        assert body["lat"] is None
        assert body["lng"] is None
