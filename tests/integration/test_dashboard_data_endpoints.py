"""Integration coverage for dashboard data endpoint URLs."""
from fastapi.testclient import TestClient


def test_dashboard_collection_endpoints_with_trailing_slashes(
    client: TestClient,
    contributor_token: str,
    reader_token: str,
) -> None:
    """Dashboard collection endpoints should resolve with slash-terminated paths."""
    contributor_headers = {"Authorization": f"Bearer {contributor_token}"}
    reader_headers = {"Authorization": f"Bearer {reader_token}"}

    create_resp = client.post(
        "/api/devices/",
        json={"name": "dashboard-device", "type": "Server"},
        headers=contributor_headers,
    )
    assert create_resp.status_code == 201

    devices_resp = client.get("/api/devices/?limit=1", headers=reader_headers)
    connections_resp = client.get("/api/connections/?limit=1", headers=reader_headers)
    locations_resp = client.get("/api/locations/", headers=reader_headers)
    tags_resp = client.get("/api/tags/", headers=reader_headers)
    recent_resp = client.get(
        "/api/devices/?sort=-updated_at&limit=5",
        headers=reader_headers,
    )

    assert devices_resp.status_code == 200
    assert connections_resp.status_code == 200
    assert locations_resp.status_code == 200
    assert tags_resp.status_code == 200
    assert recent_resp.status_code == 200

    devices_payload = devices_resp.json()
    recent_payload = recent_resp.json()

    assert "items" in devices_payload and "total" in devices_payload
    assert "items" in recent_payload and "total" in recent_payload
    assert isinstance(locations_resp.json(), list)
    assert isinstance(tags_resp.json(), list)
