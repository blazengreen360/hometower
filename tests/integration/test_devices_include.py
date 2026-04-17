"""Integration tests for GET /api/devices/?include=location enriched endpoint."""
import pytest
from fastapi.testclient import TestClient

_DEVICE = {"name": "test-device", "type": "Server"}
_LOCATION = {"name": "Main Rack", "type": "rack", "rack": "A", "row": "1"}


class TestNoIncludeBackwardCompat:
    def test_list_without_include_returns_classic_format(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        """GET /api/devices/ without include returns PaginatedDeviceResponse (no location_name)."""
        client.post(
            "/api/devices/",
            json=_DEVICE,
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        resp = client.get(
            "/api/devices/",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        if data["items"]:
            assert "location_name" not in data["items"][0]

    def test_include_empty_string_is_backward_compat(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        """?include= (empty) behaves the same as omitting the param."""
        client.post(
            "/api/devices/",
            json=_DEVICE,
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        resp = client.get(
            "/api/devices/?include=",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        if data["items"]:
            assert "location_name" not in data["items"][0]


class TestIncludeLocation:
    def test_include_location_adds_location_name_field(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        """?include=location returns items with location_name key in each item."""
        client.post(
            "/api/devices/",
            json=_DEVICE,
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        resp = client.get(
            "/api/devices/?include=location",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        for item in data["items"]:
            assert "location_name" in item

    def test_include_location_with_actual_location(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        """Device with location_id returns the correct location_name."""
        loc_resp = client.post(
            "/api/locations/",
            json=_LOCATION,
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert loc_resp.status_code == 201
        location_id = loc_resp.json()["id"]

        dev_resp = client.post(
            "/api/devices/",
            json={"name": "located-server", "type": "Server", "location_id": location_id},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert dev_resp.status_code == 201
        device_id = dev_resp.json()["id"]

        list_resp = client.get(
            "/api/devices/?include=location&limit=1000",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert list_resp.status_code == 200
        items = list_resp.json()["items"]
        device = next((d for d in items if d["id"] == device_id), None)
        assert device is not None
        assert device["location_name"] == "Main Rack"

    def test_include_location_device_without_location(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        """Device with no location_id returns location_name=null in enriched response."""
        dev_resp = client.post(
            "/api/devices/",
            json={"name": "no-loc-server", "type": "Server"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert dev_resp.status_code == 201
        device_id = dev_resp.json()["id"]

        list_resp = client.get(
            "/api/devices/?include=location&limit=1000",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert list_resp.status_code == 200
        items = list_resp.json()["items"]
        device = next((d for d in items if d["id"] == device_id), None)
        assert device is not None
        assert device["location_name"] is None

    def test_include_multiple_keys_returns_location_and_tags(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        """?include=location,tags returns both enriched location_name and populated tags."""
        loc_resp = client.post(
            "/api/locations/",
            json=_LOCATION,
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert loc_resp.status_code == 201
        location_id = loc_resp.json()["id"]

        tag_resp = client.post(
            "/api/tags/",
            json={"name": "prod", "color": "#22aa66"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert tag_resp.status_code == 201
        tag = tag_resp.json()

        dev_resp = client.post(
            "/api/devices/",
            json={
                "name": "enriched-server",
                "type": "Server",
                "location_id": location_id,
            },
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert dev_resp.status_code == 201
        device_id = dev_resp.json()["id"]

        attach_resp = client.post(
            f"/api/devices/{device_id}/tags",
            json={"tag_id": tag["id"]},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert attach_resp.status_code == 204

        resp = client.get(
            "/api/devices/?include=location,tags&limit=1000",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        device = next((d for d in items if d["id"] == device_id), None)
        assert device is not None
        assert device["location_name"] == "Main Rack"
        assert len(device["tags"]) == 1
        assert device["tags"][0]["id"] == tag["id"]
        assert device["tags"][0]["name"] == tag["name"]

    def test_include_unknown_key_returns_enriched_without_crash(
        self, client: TestClient, reader_token: str
    ) -> None:
        """Unknown include key is silently ignored."""
        resp = client.get(
            "/api/devices/?include=unknown_key",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 200


class TestLimitCap:
    def test_limit_1000_accepted(
        self, client: TestClient, reader_token: str
    ) -> None:
        """Limit of 1000 is now valid (previously capped at 100)."""
        resp = client.get(
            "/api/devices/?limit=1000",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 200

    def test_limit_above_1000_rejected(
        self, client: TestClient, reader_token: str
    ) -> None:
        """Limit above 1000 is rejected with 422."""
        resp = client.get(
            "/api/devices/?limit=1001",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 422

    def test_pagination_structure_preserved_with_include(
        self, client: TestClient, reader_token: str
    ) -> None:
        """Enriched response has same pagination envelope as classic response."""
        resp = client.get(
            "/api/devices/?include=location&page=1&limit=10",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["limit"] == 10
        assert "total" in data
        assert "items" in data


class TestIncludeLocationWithSort:
    def test_include_location_sort_by_name_ascending(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        """GET /api/devices/?include=location&sort=name orders by name ascending."""
        headers = {"Authorization": f"Bearer {contributor_token}"}
        r1 = client.post("/api/devices/", json={"name": "Zebra-IncSort", "type": "Server"}, headers=headers)
        r2 = client.post("/api/devices/", json={"name": "Alpha-IncSort", "type": "Server"}, headers=headers)
        assert r1.status_code == 201
        assert r2.status_code == 201

        resp = client.get(
            "/api/devices/?include=location&sort=name&limit=1000",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        names = [d["name"] for d in items]
        assert names.index("Alpha-IncSort") < names.index("Zebra-IncSort")
        # Enriched fields must still be present
        for item in items:
            assert "location_name" in item

    def test_include_location_sort_by_name_descending(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        """GET /api/devices/?include=location&sort=-name orders by name descending."""
        headers = {"Authorization": f"Bearer {contributor_token}"}
        r1 = client.post("/api/devices/", json={"name": "Zebra-IncSortD", "type": "Server"}, headers=headers)
        r2 = client.post("/api/devices/", json={"name": "Alpha-IncSortD", "type": "Server"}, headers=headers)
        assert r1.status_code == 201
        assert r2.status_code == 201

        resp = client.get(
            "/api/devices/?include=location&sort=-name&limit=1000",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        names = [d["name"] for d in items]
        assert names.index("Zebra-IncSortD") < names.index("Alpha-IncSortD")
        for item in items:
            assert "location_name" in item
