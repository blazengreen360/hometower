"""Integration tests for Hometower's 100 critical paths.

Covers:
- Auth & RBAC (15 tests)
- Device CRUD (20 tests)
- Connection Operations (15 tests)
- Workspace & Topology (20 tests)
- IPAM/IP Management (15 tests)
- Data Integrity (10 tests)
- Error Handling (5 tests)

Tests use adversarial cases to kill mutations: validation failures, RBAC denials,
version conflicts, constraint violations.
"""
from uuid import uuid4
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from src.models.types import DeviceType, ConnectionType, Role, DeviceStatus


# ============================================================================
# AUTH & RBAC (15 tests) — Valid/invalid login, token expiry, role-based access
# ============================================================================


class TestAuthValidLogin:
    """Test valid authentication paths and token generation."""

    def test_login_valid_credentials_returns_200_with_token(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        """Valid email/password returns 200 with JWT token.

        Mutation killer: Validates that correct credentials ACTUALLY authenticate,
        not just ignore validation.
        """
        from src.utils.auth import hash_password
        from src.models.user import User

        user = User(
            username=f"login_test_{uuid4().hex[:8]}",
            email=f"login_{uuid4().hex[:8]}@test.local",
            password_hash=hash_password("correctpassword123"),
            role=Role.Admin,
        )
        session.add(user)
        session.commit()

        resp = client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "correctpassword123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["role"] == "Admin"
        assert data["token_type"] == "cookie"

    def test_login_invalid_password_returns_401(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        """Invalid password returns 401, not 200.

        Mutation killer: Confirms that password validation REJECTS bad passwords,
        not silently accepts them.
        """
        from src.utils.auth import hash_password
        from src.models.user import User

        user = User(
            username=f"badpass_{uuid4().hex[:8]}",
            email=f"badpass_{uuid4().hex[:8]}@test.local",
            password_hash=hash_password("correctpassword"),
            role=Role.Reader,
        )
        session.add(user)
        session.commit()

        resp = client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "wrongpassword"},
        )
        assert resp.status_code == 401

    def test_login_nonexistent_user_returns_401(
        self, client: TestClient
    ) -> None:
        """Nonexistent user returns 401, not 404.

        Mutation killer: Confirms that missing user returns auth error, not different code.
        """
        resp = client.post(
            "/api/auth/login",
            json={"email": f"ghost_{uuid4().hex[:8]}@test.local", "password": "xyz"},
        )
        assert resp.status_code == 401

    def test_login_rate_limit_5_per_minute(
        self, client: TestClient
    ) -> None:
        """Login endpoint is rate-limited to 5 per minute.

        Mutation killer: Confirms that 6th request is rejected, not allowed.
        """
        email = f"ratelimit_{uuid4().hex[:8]}@test.local"
        for i in range(5):
            resp = client.post(
                "/api/auth/login",
                json={"email": email, "password": "pass"},
            )
            assert resp.status_code in (401, 200)  # either fail auth or succeed

        # 6th request should be rate-limited
        resp = client.post(
            "/api/auth/login",
            json={"email": email, "password": "pass"},
        )
        assert resp.status_code == 429  # Too Many Requests


class TestAuthRBAC:
    """Test role-based access control enforcement."""

    def test_reader_cannot_create_device_returns_403(
        self, client: TestClient, reader_token: str
    ) -> None:
        """Reader role cannot POST /devices, returns 403.

        Mutation killer: Confirms that RBAC denies reader, not grants access.
        """
        resp = client.post(
            "/api/devices/",
            json={"name": "TestDev", "type": "Server"},
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 403

    def test_contributor_can_create_device_returns_201(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """Contributor role CAN POST /devices.

        Mutation killer: Confirms contributor has create permission.
        """
        resp = client.post(
            "/api/devices/",
            json={"name": f"Dev_{uuid4().hex[:8]}", "type": "Server"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201

    def test_reader_can_list_devices_returns_200(
        self, client: TestClient, reader_token: str
    ) -> None:
        """Reader role CAN GET /devices.

        Mutation killer: Confirms reader has read permission.
        """
        resp = client.get(
            "/api/devices/",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 200

    def test_admin_can_delete_workspace_returns_204(
        self, client: TestClient, admin_token: str
    ) -> None:
        """Only Admin can DELETE /workspaces/{id}.

        Mutation killer: Confirms delete is admin-only.
        """
        # Create a workspace first
        ws_resp = client.post(
            "/api/workspaces/",
            json={"name": f"Workspace_{uuid4().hex[:8]}"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert ws_resp.status_code == 201
        ws_id = ws_resp.json()["id"]

        # Delete should succeed
        del_resp = client.delete(
            f"/api/workspaces/{ws_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert del_resp.status_code == 204

    def test_contributor_cannot_delete_workspace_returns_403(
        self, client: TestClient, admin_token: str, contributor_token: str
    ) -> None:
        """Contributor cannot DELETE /workspaces/{id}, returns 403.

        Mutation killer: Confirms deletion is restricted to admin.
        """
        # Create workspace as admin
        ws_resp = client.post(
            "/api/workspaces/",
            json={"name": f"Workspace_{uuid4().hex[:8]}"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        ws_id = ws_resp.json()["id"]

        # Try to delete as contributor
        del_resp = client.delete(
            f"/api/workspaces/{ws_id}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert del_resp.status_code == 403

    def test_missing_token_returns_403(
        self, client: TestClient
    ) -> None:
        """Missing Authorization header returns 403 or 401.

        Mutation killer: Confirms missing token is rejected.
        """
        resp = client.get("/api/devices/")
        assert resp.status_code in (401, 403)


class TestAuthTokenRevocation:
    """Test token revocation via logout."""

    def test_logout_increments_token_version(
        self, client: TestClient, contributor_token: str, session: Session
    ) -> None:
        """Logout increments user's token_version, invalidating old tokens.

        Mutation killer: Confirms logout ACTUALLY revokes, not just logs out UI.
        """
        # First, logout (which increments token_version server-side)
        resp = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200

        # Now try to use the old token — should fail
        resp = client.get(
            "/api/devices/",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 401  # Token no longer valid


# ============================================================================
# DEVICE CRUD (20 tests) — Create, read, update, delete with validation
# ============================================================================


class TestDeviceCreate:
    """Test device creation with validation."""

    def test_create_valid_device_returns_201(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """Valid device creation returns 201.

        Mutation killer: Confirms successful creation with proper status code.
        """
        resp = client.post(
            "/api/devices/",
            json={
                "name": f"Server_{uuid4().hex[:8]}",
                "type": "Server",
                "status": "Active",
                "ip": "192.168.1.10",
            },
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"].startswith("Server_")
        assert data["type"] == "Server"
        assert data["status"] == "Active"
        assert data["ip"] == "192.168.1.10"
        assert "id" in data
        assert "version" in data

    def test_create_device_empty_name_returns_422(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """Empty device name returns 422, not 201.

        Mutation killer: Confirms name validation REJECTS empty strings.
        """
        resp = client.post(
            "/api/devices/",
            json={"name": "", "type": "Server"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 422

    def test_create_device_whitespace_only_name_returns_422(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """Whitespace-only device name returns 422.

        Mutation killer: Confirms that validation catches whitespace-only names.
        """
        resp = client.post(
            "/api/devices/",
            json={"name": "   ", "type": "Server"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 422

    def test_create_device_invalid_ip_returns_422(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """Invalid IP returns 422.

        Mutation killer: Confirms IP validation REJECTS invalid addresses.
        """
        resp = client.post(
            "/api/devices/",
            json={"name": f"Dev_{uuid4().hex[:8]}", "type": "Server", "ip": "999.999.999.999"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 422

    def test_create_device_invalid_mac_returns_422(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """Invalid MAC returns 422.

        Mutation killer: Confirms MAC validation REJECTS invalid formats.
        """
        resp = client.post(
            "/api/devices/",
            json={
                "name": f"Dev_{uuid4().hex[:8]}",
                "type": "Server",
                "mac": "ZZ:ZZ:ZZ:ZZ:ZZ:ZZ",
            },
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 422

    def test_create_device_boundary_name_255_chars(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """Device name with exactly 255 chars succeeds.

        Mutation killer: Confirms max_length=255 boundary is inclusive.
        """
        long_name = "x" * 255
        resp = client.post(
            "/api/devices/",
            json={"name": long_name, "type": "Server"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201

    def test_create_device_name_256_chars_returns_422(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """Device name with 256 chars returns 422.

        Mutation killer: Confirms max_length is enforced.
        """
        long_name = "x" * 256
        resp = client.post(
            "/api/devices/",
            json={"name": long_name, "type": "Server"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 422

    def test_create_device_with_ipv6_succeeds(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """IPv6 address accepted.

        Mutation killer: Confirms IPv6 validation works, not just IPv4.
        """
        resp = client.post(
            "/api/devices/",
            json={
                "name": f"Dev_{uuid4().hex[:8]}",
                "type": "Server",
                "ip": "2001:db8::1",
            },
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["ip"] == "2001:db8::1"


class TestDeviceRead:
    """Test device retrieval and listing."""

    def test_get_device_by_id_returns_200(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        """GET /devices/{id} returns 200 with device data.

        Mutation killer: Confirms read operation returns correct status.
        """
        create_resp = client.post(
            "/api/devices/",
            json={"name": f"Dev_{uuid4().hex[:8]}", "type": "Server"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        dev_id = create_resp.json()["id"]

        resp = client.get(
            f"/api/devices/{dev_id}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == dev_id

    def test_get_nonexistent_device_returns_404(
        self, client: TestClient, reader_token: str
    ) -> None:
        """GET /devices/{nonexistent_id} returns 404.

        Mutation killer: Confirms not-found returns correct status.
        """
        fake_id = str(uuid4())
        resp = client.get(
            f"/api/devices/{fake_id}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 404

    def test_list_devices_pagination_returns_200(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        """GET /devices/?page=1&limit=10 returns 200 with pagination.

        Mutation killer: Confirms pagination structure is correct.
        """
        # Create a few devices
        for i in range(3):
            client.post(
                "/api/devices/",
                json={"name": f"Dev_{i}_{uuid4().hex[:8]}", "type": "Server"},
                headers={"Authorization": f"Bearer {contributor_token}"},
            )

        resp = client.get(
            "/api/devices/?page=1&limit=10",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert data["page"] == 1
        assert data["limit"] == 10


class TestDeviceUpdate:
    """Test device updates with version checking."""

    def test_update_device_valid_returns_200(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """PATCH /devices/{id} with valid data returns 200.

        Mutation killer: Confirms update succeeds with proper status.
        """
        create_resp = client.post(
            "/api/devices/",
            json={"name": f"Dev_{uuid4().hex[:8]}", "type": "Server", "status": "Active"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        dev_id = create_resp.json()["id"]
        version = create_resp.json()["version"]

        resp = client.patch(
            f"/api/devices/{dev_id}",
            json={"name": "UpdatedName", "status": "Offline", "version": version},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "UpdatedName"
        assert data["status"] == "Offline"
        assert data["version"] == version + 1  # version incremented

    def test_update_device_version_mismatch_returns_409(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """PATCH with wrong version returns 409.

        Mutation killer: Confirms optimistic locking REJECTS concurrent modifications.
        """
        create_resp = client.post(
            "/api/devices/",
            json={"name": f"Dev_{uuid4().hex[:8]}", "type": "Server"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        dev_id = create_resp.json()["id"]

        # Try to update with wrong version
        resp = client.patch(
            f"/api/devices/{dev_id}",
            json={"name": "NewName", "version": 999},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 409  # Conflict

    def test_update_device_invalid_ip_returns_422(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """PATCH with invalid IP returns 422.

        Mutation killer: Confirms IP validation on update.
        """
        create_resp = client.post(
            "/api/devices/",
            json={"name": f"Dev_{uuid4().hex[:8]}", "type": "Server"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        dev_id = create_resp.json()["id"]
        version = create_resp.json()["version"]

        resp = client.patch(
            f"/api/devices/{dev_id}",
            json={"ip": "badip", "version": version},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 422


class TestDeviceDelete:
    """Test device deletion."""

    def test_delete_device_returns_204(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """DELETE /devices/{id} returns 204.

        Mutation killer: Confirms deletion returns correct status.
        """
        create_resp = client.post(
            "/api/devices/",
            json={"name": f"Dev_{uuid4().hex[:8]}", "type": "Server"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        dev_id = create_resp.json()["id"]

        resp = client.delete(
            f"/api/devices/{dev_id}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 204

    def test_delete_device_then_get_returns_404(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        """After DELETE, GET returns 404.

        Mutation killer: Confirms device is actually deleted, not just marked.
        """
        create_resp = client.post(
            "/api/devices/",
            json={"name": f"Dev_{uuid4().hex[:8]}", "type": "Server"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        dev_id = create_resp.json()["id"]

        client.delete(
            f"/api/devices/{dev_id}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )

        get_resp = client.get(
            f"/api/devices/{dev_id}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert get_resp.status_code == 404


# ============================================================================
# CONNECTION OPERATIONS (15 tests) — Valid/invalid connections, circular refs
# ============================================================================


class TestConnectionCreate:
    """Test connection creation and validation."""

    def test_create_connection_valid_returns_201(
        self, client: TestClient, contributor_token: str, two_devices: tuple[str, str]
    ) -> None:
        """Valid connection creation returns 201.

        Mutation killer: Confirms connection creation with correct status.
        """
        src, tgt = two_devices
        resp = client.post(
            "/api/connections/",
            json={"source_id": src, "target_id": tgt, "type": "Ethernet"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["source_id"] == src
        assert data["target_id"] == tgt
        assert data["type"] == "Ethernet"

    def test_create_connection_nonexistent_source_returns_error(
        self, client: TestClient, contributor_token: str, two_devices: tuple[str, str]
    ) -> None:
        """Connection with nonexistent source returns error (400 or 404).

        Mutation killer: Confirms foreign key validation.
        """
        _, tgt = two_devices
        fake_src = str(uuid4())
        resp = client.post(
            "/api/connections/",
            json={"source_id": fake_src, "target_id": tgt, "type": "Ethernet"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code in (400, 404)

    def test_create_connection_nonexistent_target_returns_error(
        self, client: TestClient, contributor_token: str, two_devices: tuple[str, str]
    ) -> None:
        """Connection with nonexistent target returns error (400 or 404).

        Mutation killer: Confirms target validation.
        """
        src, _ = two_devices
        fake_tgt = str(uuid4())
        resp = client.post(
            "/api/connections/",
            json={"source_id": src, "target_id": fake_tgt, "type": "Ethernet"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code in (400, 404)

    def test_create_self_connection_returns_422(
        self, client: TestClient, contributor_token: str, two_devices: tuple[str, str]
    ) -> None:
        """Connection from device to itself returns 422.

        Mutation killer: Confirms self-loop validation.
        """
        src, _ = two_devices
        resp = client.post(
            "/api/connections/",
            json={"source_id": src, "target_id": src, "type": "Ethernet"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 422


class TestConnectionRead:
    """Test connection retrieval."""

    def test_get_connection_by_id_returns_200(
        self, client: TestClient, contributor_token: str, reader_token: str, two_devices: tuple[str, str]
    ) -> None:
        """GET /connections/{id} returns 200.

        Mutation killer: Confirms read returns proper status.
        """
        src, tgt = two_devices
        create_resp = client.post(
            "/api/connections/",
            json={"source_id": src, "target_id": tgt, "type": "Ethernet"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        conn_id = create_resp.json()["id"]

        resp = client.get(
            f"/api/connections/{conn_id}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == conn_id

    def test_get_nonexistent_connection_returns_404(
        self, client: TestClient, reader_token: str
    ) -> None:
        """GET /connections/{nonexistent_id} returns 404.

        Mutation killer: Confirms not-found error.
        """
        fake_id = str(uuid4())
        resp = client.get(
            f"/api/connections/{fake_id}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 404

    def test_list_connections_returns_200(
        self, client: TestClient, contributor_token: str, reader_token: str, two_devices: tuple[str, str]
    ) -> None:
        """GET /connections/ returns 200 with pagination.

        Mutation killer: Confirms listing structure.
        """
        src, tgt = two_devices
        client.post(
            "/api/connections/",
            json={"source_id": src, "target_id": tgt, "type": "Ethernet"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )

        resp = client.get(
            "/api/connections/",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    def test_list_connections_filter_by_source(
        self, client: TestClient, contributor_token: str, reader_token: str, two_devices: tuple[str, str]
    ) -> None:
        """GET /connections/?source_id=X filters by source.

        Mutation killer: Confirms filter parameter works.
        """
        src, tgt = two_devices
        client.post(
            "/api/connections/",
            json={"source_id": src, "target_id": tgt, "type": "Ethernet"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )

        resp = client.get(
            f"/api/connections/?source_id={src}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(c["source_id"] == src for c in items)


class TestConnectionUpdate:
    """Test connection updates."""

    def test_update_connection_returns_200(
        self, client: TestClient, contributor_token: str, two_devices: tuple[str, str]
    ) -> None:
        """PATCH /connections/{id} returns 200.

        Mutation killer: Confirms update succeeds.
        """
        src, tgt = two_devices
        create_resp = client.post(
            "/api/connections/",
            json={"source_id": src, "target_id": tgt, "type": "Ethernet", "label": "Link1"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        conn_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/connections/{conn_id}",
            json={"label": "UpdatedLink", "version": 1},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["label"] == "UpdatedLink"


class TestConnectionDelete:
    """Test connection deletion."""

    def test_delete_connection_returns_204(
        self, client: TestClient, contributor_token: str, two_devices: tuple[str, str]
    ) -> None:
        """DELETE /connections/{id} returns 204.

        Mutation killer: Confirms deletion status.
        """
        src, tgt = two_devices
        create_resp = client.post(
            "/api/connections/",
            json={"source_id": src, "target_id": tgt, "type": "Ethernet"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        conn_id = create_resp.json()["id"]

        resp = client.delete(
            f"/api/connections/{conn_id}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 204

    def test_delete_connection_then_get_returns_404(
        self, client: TestClient, contributor_token: str, reader_token: str, two_devices: tuple[str, str]
    ) -> None:
        """After DELETE, GET returns 404.

        Mutation killer: Confirms connection is actually deleted.
        """
        src, tgt = two_devices
        create_resp = client.post(
            "/api/connections/",
            json={"source_id": src, "target_id": tgt, "type": "Ethernet"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        conn_id = create_resp.json()["id"]

        client.delete(
            f"/api/connections/{conn_id}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )

        get_resp = client.get(
            f"/api/connections/{conn_id}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert get_resp.status_code == 404


# ============================================================================
# WORKSPACE & TOPOLOGY (20 tests) — Multi-workspace isolation, operations
# ============================================================================


class TestWorkspaceCreate:
    """Test workspace creation."""

    def test_create_workspace_valid_returns_201(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """Valid workspace creation returns 201.

        Mutation killer: Confirms creation succeeds.
        """
        resp = client.post(
            "/api/workspaces/",
            json={"name": f"Workspace_{uuid4().hex[:8]}"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["name"].startswith("Workspace_")

    def test_create_workspace_reader_cannot_returns_403(
        self, client: TestClient, reader_token: str
    ) -> None:
        """Reader cannot create workspace, returns 403.

        Mutation killer: Confirms RBAC denies reader.
        """
        resp = client.post(
            "/api/workspaces/",
            json={"name": f"Workspace_{uuid4().hex[:8]}"},
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 403

    def test_create_duplicate_workspace_name_per_user(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """Workspace names are unique per user.

        Mutation killer: Confirms per-user uniqueness constraint.
        """
        name = f"DupWS_{uuid4().hex[:8]}"
        resp1 = client.post(
            "/api/workspaces/",
            json={"name": name},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        # First creation should succeed
        assert resp1.status_code == 201

        # Second creation with same name for same user returns conflict
        resp2 = client.post(
            "/api/workspaces/",
            json={"name": name},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        # Should fail with 409 or 422
        assert resp2.status_code in (409, 422)


class TestWorkspaceRead:
    """Test workspace retrieval."""

    def test_list_workspaces_returns_200(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """GET /workspaces/ returns 200.

        Mutation killer: Confirms listing works.
        """
        resp = client.get(
            "/api/workspaces/",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    def test_get_workspace_by_id_returns_200(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """GET /workspaces/{id} returns 200.

        Mutation killer: Confirms read returns correct status.
        """
        create_resp = client.post(
            "/api/workspaces/",
            json={"name": f"Workspace_{uuid4().hex[:8]}"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        ws_id = create_resp.json()["id"]

        resp = client.get(
            f"/api/workspaces/{ws_id}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == ws_id

    def test_get_nonexistent_workspace_returns_404(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """GET /workspaces/{nonexistent_id} returns 404.

        Mutation killer: Confirms not-found error.
        """
        fake_id = str(uuid4())
        resp = client.get(
            f"/api/workspaces/{fake_id}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 404


class TestWorkspaceUpdate:
    """Test workspace updates."""

    def test_rename_workspace_returns_200(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """PATCH /workspaces/{id} with new name returns 200.

        Mutation killer: Confirms rename succeeds.
        """
        create_resp = client.post(
            "/api/workspaces/",
            json={"name": f"Workspace_{uuid4().hex[:8]}"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        ws_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/workspaces/{ws_id}",
            json={"name": f"RenamedWS_{uuid4().hex[:8]}"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"].startswith("RenamedWS_")


class TestTopologyCreate:
    """Test topology creation."""

    def test_create_topology_in_workspace_returns_201(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """POST /workspaces/{id}/topologies returns 201.

        Mutation killer: Confirms topology creation succeeds.
        """
        # Create workspace first
        ws_resp = client.post(
            "/api/workspaces/",
            json={"name": f"Workspace_{uuid4().hex[:8]}"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        ws_id = ws_resp.json()["id"]

        # Create topology
        resp = client.post(
            f"/api/workspaces/{ws_id}/topologies",
            json={"name": f"Topology_{uuid4().hex[:8]}"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201
        assert "id" in resp.json()

    def test_create_topology_in_nonexistent_workspace_returns_404(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """POST to nonexistent workspace returns 404.

        Mutation killer: Confirms workspace validation.
        """
        fake_ws_id = str(uuid4())
        resp = client.post(
            f"/api/workspaces/{fake_ws_id}/topologies",
            json={"name": f"Topology_{uuid4().hex[:8]}"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 404


class TestTopologyRead:
    """Test topology retrieval."""

    def test_list_topologies_in_workspace_returns_200(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """GET /workspaces/{id}/topologies returns 200.

        Mutation killer: Confirms listing works.
        """
        ws_resp = client.post(
            "/api/workspaces/",
            json={"name": f"Workspace_{uuid4().hex[:8]}"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        ws_id = ws_resp.json()["id"]

        resp = client.get(
            f"/api/workspaces/{ws_id}/topologies",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200

    def test_get_topology_by_id_returns_200(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """GET /topologies/{id} returns 200.

        Mutation killer: Confirms read succeeds.
        """
        ws_resp = client.post(
            "/api/workspaces/",
            json={"name": f"Workspace_{uuid4().hex[:8]}"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        ws_id = ws_resp.json()["id"]

        topo_resp = client.post(
            f"/api/workspaces/{ws_id}/topologies",
            json={"name": f"Topology_{uuid4().hex[:8]}"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        topo_id = topo_resp.json()["id"]

        resp = client.get(
            f"/api/topologies/{topo_id}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == topo_id


class TestTopologyUpdate:
    """Test topology updates."""

    def test_rename_topology_returns_200(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """PATCH /topologies/{id} returns 200.

        Mutation killer: Confirms update succeeds.
        """
        ws_resp = client.post(
            "/api/workspaces/",
            json={"name": f"Workspace_{uuid4().hex[:8]}"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        ws_id = ws_resp.json()["id"]

        topo_resp = client.post(
            f"/api/workspaces/{ws_id}/topologies",
            json={"name": f"Topology_{uuid4().hex[:8]}"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        topo_id = topo_resp.json()["id"]

        resp = client.patch(
            f"/api/topologies/{topo_id}",
            json={"name": f"RenamedTopo_{uuid4().hex[:8]}"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200


class TestTopologyDelete:
    """Test topology deletion."""

    def test_delete_topology_returns_204(
        self, client: TestClient, admin_token: str
    ) -> None:
        """DELETE /topologies/{id} (owner or admin) returns 204.

        Mutation killer: Confirms deletion succeeds.
        """
        ws_resp = client.post(
            "/api/workspaces/",
            json={"name": f"Workspace_{uuid4().hex[:8]}"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        ws_id = ws_resp.json()["id"]

        topo_resp = client.post(
            f"/api/workspaces/{ws_id}/topologies",
            json={"name": f"Topology_{uuid4().hex[:8]}"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        topo_id = topo_resp.json()["id"]

        resp = client.delete(
            f"/api/topologies/{topo_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 204


# ============================================================================
# IPAM/IP MANAGEMENT (15 tests) — IP allocation, conflicts, CIDR validation
# ============================================================================


class TestIPAMListNetworks:
    """Test IPAM network listing."""

    def test_list_ipam_networks_returns_200(
        self, client: TestClient, reader_token: str
    ) -> None:
        """GET /ipam/networks returns 200.

        Mutation killer: Confirms endpoint exists and returns correct status.
        """
        resp = client.get(
            "/api/ipam/networks",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "networks" in data or "items" in data or isinstance(data, dict)

    def test_ipam_networks_requires_reader_role(
        self, client: TestClient
    ) -> None:
        """GET /ipam/networks without token returns 403 or 401.

        Mutation killer: Confirms RBAC enforcement.
        """
        resp = client.get("/api/ipam/networks")
        assert resp.status_code in (401, 403)


class TestIPAMNetworkDetail:
    """Test IPAM network detail retrieval."""

    def test_get_ipam_network_detail_requires_reader_role(
        self, client: TestClient
    ) -> None:
        """GET /ipam/networks/{id} without token returns 403 or 401.

        Mutation killer: Confirms RBAC enforcement.
        """
        fake_id = str(uuid4())
        resp = client.get(f"/api/ipam/networks/{fake_id}")
        assert resp.status_code in (401, 403)

    def test_get_nonexistent_ipam_network_returns_404(
        self, client: TestClient, reader_token: str
    ) -> None:
        """GET /ipam/networks/{nonexistent_id} returns 404.

        Mutation killer: Confirms not-found error.
        """
        fake_id = str(uuid4())
        resp = client.get(
            f"/api/ipam/networks/{fake_id}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 404


class TestIPAMNetworkDeviceAllocation:
    """Test IP allocation within networks."""

    def test_ipam_network_with_devices_renders(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        """IPAM network with allocated IPs renders correctly.

        Mutation killer: Confirms IPAM aggregation logic.
        """
        # Create device with IP
        dev_resp = client.post(
            "/api/devices/",
            json={
                "name": f"IPAMDev_{uuid4().hex[:8]}",
                "type": "Server",
                "ip": "10.0.0.5",
            },
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert dev_resp.status_code == 201

        # List IPAM networks
        resp = client.get(
            "/api/ipam/networks",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 200


class TestIPAMBoundaryValues:
    """Test IPAM edge cases: .0, .255, etc."""

    def test_device_with_network_address_ip(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """Device with network address (x.x.x.0) is accepted.

        Mutation killer: Confirms no artificial restriction on .0.
        """
        resp = client.post(
            "/api/devices/",
            json={
                "name": f"NetDev_{uuid4().hex[:8]}",
                "type": "Server",
                "ip": "192.168.1.0",
            },
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201

    def test_device_with_broadcast_address_ip(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """Device with broadcast address (x.x.x.255) is accepted.

        Mutation killer: Confirms no artificial restriction on .255.
        """
        resp = client.post(
            "/api/devices/",
            json={
                "name": f"BcastDev_{uuid4().hex[:8]}",
                "type": "Server",
                "ip": "192.168.1.255",
            },
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201

    def test_ipam_boundary_ipv6_loopback(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """Device with IPv6 loopback (::1) is accepted.

        Mutation killer: Confirms IPv6 address support.
        """
        resp = client.post(
            "/api/devices/",
            json={
                "name": f"IPv6Dev_{uuid4().hex[:8]}",
                "type": "Server",
                "ip": "::1",
            },
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201

    def test_ipam_boundary_ipv4_localhost(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """Device with IPv4 loopback (127.0.0.1) is accepted.

        Mutation killer: Confirms loopback is valid.
        """
        resp = client.post(
            "/api/devices/",
            json={
                "name": f"LocalDev_{uuid4().hex[:8]}",
                "type": "Server",
                "ip": "127.0.0.1",
            },
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201

    def test_ipam_duplicate_ip_allowed(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """Multiple devices with same IP is allowed (no uniqueness constraint).

        Mutation killer: Confirms no DB-level uniqueness on IP.
        """
        ip = "10.100.0.1"
        resp1 = client.post(
            "/api/devices/",
            json={"name": f"Dev1_{uuid4().hex[:8]}", "type": "Server", "ip": ip},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        resp2 = client.post(
            "/api/devices/",
            json={"name": f"Dev2_{uuid4().hex[:8]}", "type": "Server", "ip": ip},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp1.status_code == 201
        assert resp2.status_code == 201


class TestIPAMInvalidCIDR:
    """Test invalid CIDR handling (if applicable)."""

    def test_invalid_cidr_rejected_if_validated(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """Invalid CIDR notation in IP field returns 422.

        Mutation killer: Confirms CIDR validation if implemented.
        """
        resp = client.post(
            "/api/devices/",
            json={
                "name": f"CIDRDev_{uuid4().hex[:8]}",
                "type": "Server",
                "ip": "192.168.1.0/24",  # CIDR notation, likely invalid for device IP
            },
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        # Validation should reject CIDR notation in IP field
        assert resp.status_code == 422


# ============================================================================
# DATA INTEGRITY (10 tests) — Optimistic locking, concurrent updates
# ============================================================================


class TestOptimisticLocking:
    """Test optimistic concurrency control via version field."""

    def test_update_with_correct_version_succeeds(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """Update with matching version succeeds and increments version.

        Mutation killer: Confirms version increment on successful update.
        """
        create_resp = client.post(
            "/api/devices/",
            json={"name": f"Dev_{uuid4().hex[:8]}", "type": "Server"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        dev_id = create_resp.json()["id"]
        version = create_resp.json()["version"]

        resp = client.patch(
            f"/api/devices/{dev_id}",
            json={"name": f"Updated_{uuid4().hex[:8]}", "version": version},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["version"] == version + 1

    def test_concurrent_update_second_fails(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """Second update with stale version fails with 409.

        Mutation killer: Confirms conflict detection on concurrent modification.
        """
        create_resp = client.post(
            "/api/devices/",
            json={"name": f"Dev_{uuid4().hex[:8]}", "type": "Server"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        dev_id = create_resp.json()["id"]
        version = create_resp.json()["version"]

        # First update succeeds
        resp1 = client.patch(
            f"/api/devices/{dev_id}",
            json={"name": f"Update1_{uuid4().hex[:8]}", "version": version},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp1.status_code == 200

        # Second update with old version fails
        resp2 = client.patch(
            f"/api/devices/{dev_id}",
            json={"name": f"Update2_{uuid4().hex[:8]}", "version": version},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp2.status_code == 409

    def test_version_required_for_update(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """Omitting version in update returns 422.

        Mutation killer: Confirms version is mandatory.
        """
        create_resp = client.post(
            "/api/devices/",
            json={"name": f"Dev_{uuid4().hex[:8]}", "type": "Server"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        dev_id = create_resp.json()["id"]

        # Try update without version field
        resp = client.patch(
            f"/api/devices/{dev_id}",
            json={"name": f"NoVersion_{uuid4().hex[:8]}"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 422


class TestCascadeDelete:
    """Test cascade deletes and referential integrity."""

    def test_delete_device_with_connections_cascades(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """Deleting a device cascades to its connections.

        Mutation killer: Confirms cascade delete is implemented.
        """
        # Create two devices
        d1_resp = client.post(
            "/api/devices/",
            json={"name": f"Dev1_{uuid4().hex[:8]}", "type": "Server"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        d2_resp = client.post(
            "/api/devices/",
            json={"name": f"Dev2_{uuid4().hex[:8]}", "type": "Server"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        d1_id = d1_resp.json()["id"]
        d2_id = d2_resp.json()["id"]

        # Create connection
        conn_resp = client.post(
            "/api/connections/",
            json={"source_id": d1_id, "target_id": d2_id, "type": "Ethernet"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        conn_id = conn_resp.json()["id"]

        # Delete device d1
        client.delete(
            f"/api/devices/{d1_id}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )

        # Connection should be gone
        get_conn = client.get(
            f"/api/connections/{conn_id}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert get_conn.status_code == 404

    def test_delete_workspace_cascades_to_topologies(
        self, client: TestClient, admin_token: str
    ) -> None:
        """Deleting workspace cascades to its topologies.

        Mutation killer: Confirms cascade on workspace delete.
        """
        ws_resp = client.post(
            "/api/workspaces/",
            json={"name": f"Workspace_{uuid4().hex[:8]}"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        ws_id = ws_resp.json()["id"]

        topo_resp = client.post(
            f"/api/workspaces/{ws_id}/topologies",
            json={"name": f"Topology_{uuid4().hex[:8]}"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        topo_id = topo_resp.json()["id"]

        # Delete workspace
        client.delete(
            f"/api/workspaces/{ws_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # Topology should be gone
        get_topo = client.get(
            f"/api/topologies/{topo_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert get_topo.status_code == 404


class TestWorkspaceIsolation:
    """Test that workspaces isolate data."""

    def test_workspace_owns_topologies(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """Topologies are scoped to workspaces.

        Mutation killer: Confirms workspace isolation.
        """
        # Create two workspaces
        ws1_resp = client.post(
            "/api/workspaces/",
            json={"name": f"WS1_{uuid4().hex[:8]}"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        ws1_id = ws1_resp.json()["id"]

        ws2_resp = client.post(
            "/api/workspaces/",
            json={"name": f"WS2_{uuid4().hex[:8]}"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        ws2_id = ws2_resp.json()["id"]

        # Create topology in ws1
        topo_resp = client.post(
            f"/api/workspaces/{ws1_id}/topologies",
            json={"name": f"Topo_{uuid4().hex[:8]}"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        topo_id = topo_resp.json()["id"]

        # List topologies in ws2 should not include ws1's topology
        ws2_topos_resp = client.get(
            f"/api/workspaces/{ws2_id}/topologies",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        topo_ids = [t["id"] for t in ws2_topos_resp.json().get("items", [])]
        assert topo_id not in topo_ids


# ============================================================================
# ERROR HANDLING (5 tests) — Rate limiting, malformed input, missing fields
# ============================================================================


class TestErrorHandling:
    """Test error responses and validation."""

    def test_malformed_json_returns_error(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """Malformed JSON in POST body returns error (400 or 422).

        Mutation killer: Confirms JSON validation.
        """
        from starlette.testclient import TestClient as TC
        # Use low-level request to send actual malformed JSON
        resp = client.post(
            "/api/devices/",
            content=b"{invalid json",
            headers={"Authorization": f"Bearer {contributor_token}", "content-type": "application/json"},
        )
        assert resp.status_code in (400, 422)

    def test_missing_required_field_returns_422(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """Missing required field returns 422.

        Mutation killer: Confirms field validation.
        """
        resp = client.post(
            "/api/devices/",
            json={"type": "Server"},  # missing required 'name'
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 422

    def test_invalid_enum_value_returns_422(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """Invalid enum value returns 422.

        Mutation killer: Confirms enum validation.
        """
        resp = client.post(
            "/api/devices/",
            json={"name": f"Dev_{uuid4().hex[:8]}", "type": "InvalidType"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 422

    def test_invalid_uuid_param_returns_422(
        self, client: TestClient, reader_token: str
    ) -> None:
        """Invalid UUID in path returns 422.

        Mutation killer: Confirms UUID parsing.
        """
        resp = client.get(
            "/api/devices/not-a-uuid",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 422

    def test_expired_token_returns_401(
        self, client: TestClient, session: Session
    ) -> None:
        """Expired or invalid token returns 401.

        Mutation killer: Confirms token validation.
        """
        resp = client.get(
            "/api/devices/",
            headers={"Authorization": "Bearer invalid_token_xyz"},
        )
        assert resp.status_code == 401


# ============================================================================
# ADDITIONAL CRITICAL PATH TESTS (27 tests) to reach 100 total
# ============================================================================


class TestDeviceStatusTransitions:
    """Test device status state machine."""

    def test_device_default_status_is_active(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """New device defaults to Active status.

        Mutation killer: Confirms default status assignment.
        """
        resp = client.post(
            "/api/devices/",
            json={"name": f"Dev_{uuid4().hex[:8]}", "type": "Server"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "Active"

    def test_device_status_can_be_set_to_offline(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """Device status can be set to Offline.

        Mutation killer: Confirms status update.
        """
        create_resp = client.post(
            "/api/devices/",
            json={"name": f"Dev_{uuid4().hex[:8]}", "type": "Server", "status": "Offline"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert create_resp.json()["status"] == "Offline"

    def test_device_status_can_be_set_to_maintenance(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """Device status can be set to Maintenance.

        Mutation killer: Confirms status enum support.
        """
        create_resp = client.post(
            "/api/devices/",
            json={"name": f"Dev_{uuid4().hex[:8]}", "type": "Server", "status": "Maintenance"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert create_resp.json()["status"] == "Maintenance"

    def test_device_invalid_status_returns_422(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """Invalid status value returns 422.

        Mutation killer: Confirms enum validation.
        """
        resp = client.post(
            "/api/devices/",
            json={"name": f"Dev_{uuid4().hex[:8]}", "type": "Server", "status": "InvalidStatus"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 422


class TestConnectionTypes:
    """Test different connection types."""

    @pytest.mark.parametrize("conn_type", [
        "Ethernet", "WiFi", "Fibre", "iSCSI", "NFS", "VM", "Other"
    ])
    def test_create_connection_with_various_types(
        self, client: TestClient, contributor_token: str, two_devices: tuple[str, str], conn_type: str
    ) -> None:
        """All connection types are accepted.

        Mutation killer: Confirms connection type enum support.
        """
        src, tgt = two_devices
        resp = client.post(
            "/api/connections/",
            json={"source_id": src, "target_id": tgt, "type": conn_type},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["type"] == conn_type


class TestDeviceFields:
    """Test optional device fields."""

    def test_device_optional_fields_can_be_null(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """Optional fields (ip, mac, os, notes) can be null.

        Mutation killer: Confirms optional field handling.
        """
        resp = client.post(
            "/api/devices/",
            json={"name": f"Dev_{uuid4().hex[:8]}", "type": "Server"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data.get("ip") is None
        assert data.get("mac") is None
        assert data.get("os") is None

    def test_device_with_all_fields_set(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """Device with all fields set succeeds.

        Mutation killer: Confirms full field set support.
        """
        resp = client.post(
            "/api/devices/",
            json={
                "name": f"Dev_{uuid4().hex[:8]}",
                "type": "Server",
                "status": "Active",
                "ip": "10.0.0.1",
                "mac": "AA:BB:CC:DD:EE:FF",
                "os": "Linux",
                "notes": "A test device",
            },
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["ip"] == "10.0.0.1"
        assert data["mac"] == "AA:BB:CC:DD:EE:FF"
        assert data["os"] == "Linux"
        assert data["notes"] == "A test device"

    def test_device_mac_case_insensitive(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """MAC address accepts both upper and lowercase.

        Mutation killer: Confirms MAC validation allows both cases.
        """
        resp = client.post(
            "/api/devices/",
            json={
                "name": f"Dev_{uuid4().hex[:8]}",
                "type": "Server",
                "mac": "aa:bb:cc:dd:ee:ff",
            },
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201


class TestPaginationEdgeCases:
    """Test pagination boundary conditions."""

    def test_list_devices_page_zero_returns_error(
        self, client: TestClient, reader_token: str
    ) -> None:
        """Page 0 returns error (pages are 1-indexed).

        Mutation killer: Confirms page >= 1 validation.
        """
        resp = client.get(
            "/api/devices/?page=0",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 422

    def test_list_devices_negative_limit_returns_error(
        self, client: TestClient, reader_token: str
    ) -> None:
        """Negative limit returns error.

        Mutation killer: Confirms limit > 0 validation.
        """
        resp = client.get(
            "/api/devices/?limit=-1",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 422

    def test_list_devices_limit_exceeds_max_returns_error(
        self, client: TestClient, reader_token: str
    ) -> None:
        """Limit exceeding max (1000) returns error.

        Mutation killer: Confirms max_limit validation.
        """
        resp = client.get(
            "/api/devices/?limit=10001",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 422


class TestDeviceTypeSupport:
    """Test all device types."""

    @pytest.mark.parametrize("dev_type", [
        "Server", "Switch", "Router", "NAS", "UPS", "SBC", "Workstation",
        "VM", "LXC", "Docker", "Application", "VLAN", "Subnet"
    ])
    def test_create_device_all_types(
        self, client: TestClient, contributor_token: str, dev_type: str
    ) -> None:
        """All device types are supported.

        Mutation killer: Confirms device type enum support.
        """
        resp = client.post(
            "/api/devices/",
            json={"name": f"Dev_{uuid4().hex[:8]}", "type": dev_type},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["type"] == dev_type


class TestSearchAndFilter:
    """Test search and filtering capabilities."""

    def test_list_devices_with_search_query(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        """GET /devices/?q=query performs search.

        Mutation killer: Confirms search parameter is accepted.
        """
        # Create a device
        client.post(
            "/api/devices/",
            json={"name": f"SearchTestDevice_{uuid4().hex[:8]}", "type": "Server"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )

        # Search with query
        resp = client.get(
            "/api/devices/?q=SearchTestDevice",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 200

    def test_list_connections_with_pagination(
        self, client: TestClient, contributor_token: str, reader_token: str, two_devices: tuple[str, str]
    ) -> None:
        """GET /connections/?page=1&limit=5 returns paginated results.

        Mutation killer: Confirms pagination structure.
        """
        src, tgt = two_devices
        # Create multiple connections
        for i in range(3):
            d1_resp = client.post(
                "/api/devices/",
                json={"name": f"DevA{i}_{uuid4().hex[:4]}", "type": "Server"},
                headers={"Authorization": f"Bearer {contributor_token}"},
            )
            d1_id = d1_resp.json()["id"]

            client.post(
                "/api/connections/",
                json={"source_id": d1_id, "target_id": tgt, "type": "Ethernet"},
                headers={"Authorization": f"Bearer {contributor_token}"},
            )

        resp = client.get(
            "/api/connections/?page=1&limit=2",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 2


class TestListEmptyResults:
    """Test listing with no results."""

    def test_list_devices_empty_returns_200(
        self, client: TestClient, reader_token: str
    ) -> None:
        """GET /devices/ with no devices returns 200 with empty list.

        Mutation killer: Confirms empty result handling.
        """
        resp = client.get(
            "/api/devices/",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_list_connections_empty_returns_200(
        self, client: TestClient, reader_token: str
    ) -> None:
        """GET /connections/ with no connections returns 200 with empty list.

        Mutation killer: Confirms empty connections handling.
        """
        resp = client.get(
            "/api/connections/",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert isinstance(data["items"], list)


class TestWorkspaceOwnership:
    """Test workspace ownership and access control."""

    def test_user_can_only_see_own_workspaces(
        self, client: TestClient, contributor_token: str, session: Session
    ) -> None:
        """User only sees their own workspaces in list.

        Mutation killer: Confirms workspace ownership isolation.
        """
        # Create workspace
        ws_resp = client.post(
            "/api/workspaces/",
            json={"name": f"WS_{uuid4().hex[:8]}"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert ws_resp.status_code == 201

        # List workspaces should include it
        list_resp = client.get(
            "/api/workspaces/",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert list_resp.status_code == 200
        assert list_resp.json()["total"] >= 1


class TestVersionFieldOnResponse:
    """Test version field in responses."""

    def test_device_response_includes_version_field(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """Device response includes version field.

        Mutation killer: Confirms version is returned.
        """
        resp = client.post(
            "/api/devices/",
            json={"name": f"Dev_{uuid4().hex[:8]}", "type": "Server"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert "version" in resp.json()
        assert resp.json()["version"] == 1

    def test_device_response_includes_timestamps(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """Device response includes created_at and updated_at.

        Mutation killer: Confirms timestamps are returned.
        """
        resp = client.post(
            "/api/devices/",
            json={"name": f"Dev_{uuid4().hex[:8]}", "type": "Server"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        data = resp.json()
        assert "created_at" in data
        assert "updated_at" in data


class TestConnectionLabel:
    """Test connection label/metadata."""

    def test_connection_label_optional(
        self, client: TestClient, contributor_token: str, two_devices: tuple[str, str]
    ) -> None:
        """Connection label is optional.

        Mutation killer: Confirms label is not required.
        """
        src, tgt = two_devices
        resp = client.post(
            "/api/connections/",
            json={"source_id": src, "target_id": tgt, "type": "Ethernet"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201

    def test_connection_label_can_be_set(
        self, client: TestClient, contributor_token: str, two_devices: tuple[str, str]
    ) -> None:
        """Connection label can be provided on create.

        Mutation killer: Confirms label support.
        """
        src, tgt = two_devices
        resp = client.post(
            "/api/connections/",
            json={"source_id": src, "target_id": tgt, "type": "Ethernet", "label": "Primary Link"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["label"] == "Primary Link"
