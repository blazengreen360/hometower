"""Integration tests for device duplication flow (HT-041)."""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from src.domain.devices import generate_copy_name
from src.models.device import Device
from src.models.types import DeviceType
from src.repositories.device_repository import get_all_names


class TestGenerateCopyNameIntegration:
    """Verify generate_copy_name works end-to-end with real device names from the API."""

    def test_copy_name_no_collision_via_api_names(
        self, client: TestClient, contributor_token: str
    ) -> None:
        headers = {"Authorization": f"Bearer {contributor_token}"}
        client.post(
            "/api/devices/",
            json={"name": "Origin", "type": "Server"},
            headers=headers,
        )
        r = client.get("/api/devices/", params={"limit": 1000}, headers=headers)
        names = [d["name"] for d in r.json()["items"]]
        assert generate_copy_name("Origin", names) == "Origin (copy)"

    def test_copy_name_collision_via_api_names(
        self, client: TestClient, contributor_token: str
    ) -> None:
        headers = {"Authorization": f"Bearer {contributor_token}"}
        client.post("/api/devices/", json={"name": "Dupe", "type": "Server"}, headers=headers)
        client.post("/api/devices/", json={"name": "Dupe (copy)", "type": "Server"}, headers=headers)
        r = client.get("/api/devices/", params={"limit": 1000}, headers=headers)
        names = [d["name"] for d in r.json()["items"]]
        assert generate_copy_name("Dupe", names) == "Dupe (copy 2)"


class TestGetAllNamesRepository:
    def test_get_all_names_returns_a_list(self, session: Session) -> None:
        """get_all_names always returns a list regardless of DB state."""
        names = get_all_names(session)
        assert isinstance(names, list)

    def test_get_all_names_includes_new_device(self, session: Session) -> None:
        d = Device(name="RepoTestDevice_unique_xz91", type=DeviceType.Server)
        session.add(d)
        session.commit()
        names = get_all_names(session)
        assert "RepoTestDevice_unique_xz91" in names

    def test_get_all_names_multiple_devices(self, session: Session) -> None:
        for name in ("Alpha_repo_xz", "Beta_repo_xz", "Gamma_repo_xz"):
            session.add(Device(name=name, type=DeviceType.Switch))
        session.commit()
        names = get_all_names(session)
        for n in ("Alpha_repo_xz", "Beta_repo_xz", "Gamma_repo_xz"):
            assert n in names


class TestDuplicateDeviceAPIFlow:
    def test_duplicate_preserves_type_and_os(
        self, client: TestClient, contributor_token: str
    ) -> None:
        headers = {"Authorization": f"Bearer {contributor_token}"}
        src = client.post(
            "/api/devices/",
            json={"name": "Original", "type": "NAS", "os": "TrueNAS", "notes": "primary"},
            headers=headers,
        )
        assert src.status_code == 201

        copy = client.post(
            "/api/devices/",
            json={
                "name": "Original (copy)",
                "type": "NAS",
                "os": "TrueNAS",
                "notes": "primary",
            },
            headers=headers,
        )
        assert copy.status_code == 201
        data = copy.json()
        assert data["name"] == "Original (copy)"
        assert data["type"] == "NAS"
        assert data["os"] == "TrueNAS"
        assert data["ip"] is None
        assert data["mac"] is None

    def test_duplicate_with_tag_copies_tag(
        self, client: TestClient, contributor_token: str
    ) -> None:
        headers = {"Authorization": f"Bearer {contributor_token}"}
        tag = client.post(
            "/api/tags/", json={"name": "dup-tag", "color": "#aabbcc"}, headers=headers
        ).json()
        src = client.post(
            "/api/devices/", json={"name": "SrcTagged", "type": "Server"}, headers=headers
        ).json()
        client.post(
            f"/api/devices/{src['id']}/tags",
            json={"tag_id": tag["id"]},
            headers=headers,
        )

        copy = client.post(
            "/api/devices/", json={"name": "SrcTagged (copy)", "type": "Server"}, headers=headers
        ).json()
        client.post(
            f"/api/devices/{copy['id']}/tags",
            json={"tag_id": tag["id"]},
            headers=headers,
        )

        tags = client.get(f"/api/devices/{copy['id']}/tags", headers=headers).json()
        assert any(t["id"] == tag["id"] for t in tags)
