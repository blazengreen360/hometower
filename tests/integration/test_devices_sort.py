"""Integration tests for GET /api/devices sort parameter — HT-026."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def two_named_devices(client: TestClient, contributor_token: str) -> list[str]:
    """Create two devices with names chosen to test alphabetical sort."""
    headers = {"Authorization": f"Bearer {contributor_token}"}
    r1 = client.post(
        "/api/devices/",
        json={"name": "Zulu-SortTest", "type": "Server"},
        headers=headers,
    )
    r2 = client.post(
        "/api/devices/",
        json={"name": "Alpha-SortTest", "type": "Switch"},
        headers=headers,
    )
    assert r1.status_code == 201
    assert r2.status_code == 201
    return [r1.json()["id"], r2.json()["id"]]


class TestDeviceSort:
    def test_sort_by_name_ascending_returns_200_and_sorted(
        self,
        client: TestClient,
        contributor_token: str,
        reader_token: str,
        two_named_devices: list[str],
    ) -> None:
        response = client.get(
            "/api/devices/?sort=name&limit=200",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        names = [i["name"] for i in data["items"]]
        assert names == sorted(names)

    def test_sort_by_name_descending_returns_200_and_sorted(
        self,
        client: TestClient,
        contributor_token: str,
        reader_token: str,
        two_named_devices: list[str],
    ) -> None:
        response = client.get(
            "/api/devices/?sort=-name&limit=200",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        names = [i["name"] for i in data["items"]]
        assert names == sorted(names, reverse=True)

    def test_sort_by_updated_at_descending_returns_200(
        self,
        client: TestClient,
        contributor_token: str,
        reader_token: str,
        two_named_devices: list[str],
    ) -> None:
        response = client.get(
            "/api/devices/?sort=-updated_at",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_sort_by_created_at_descending_returns_200(
        self,
        client: TestClient,
        reader_token: str,
        two_named_devices: list[str],
    ) -> None:
        response = client.get(
            "/api/devices/?sort=-created_at",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 200

    def test_sort_by_created_at_ascending_returns_200(
        self,
        client: TestClient,
        reader_token: str,
        two_named_devices: list[str],
    ) -> None:
        response = client.get(
            "/api/devices/?sort=created_at",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 200

    def test_sort_updated_at_ascending_returns_200(
        self,
        client: TestClient,
        reader_token: str,
        two_named_devices: list[str],
    ) -> None:
        response = client.get(
            "/api/devices/?sort=updated_at",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 200

    def test_invalid_sort_value_falls_back_gracefully(
        self,
        client: TestClient,
        reader_token: str,
    ) -> None:
        """Invalid sort values must be silently ignored — no 4xx error."""
        response = client.get(
            "/api/devices/?sort=invalid_field_name",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_no_sort_param_still_works(
        self,
        client: TestClient,
        reader_token: str,
    ) -> None:
        """Backward compatibility: no sort param must still return 200."""
        response = client.get(
            "/api/devices/",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_sort_and_pagination_combined(
        self,
        client: TestClient,
        contributor_token: str,
        reader_token: str,
        two_named_devices: list[str],
    ) -> None:
        """Sort must combine correctly with page/limit params."""
        response = client.get(
            "/api/devices/?sort=name&limit=1&page=1",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["limit"] == 1
        assert len(data["items"]) <= 1
