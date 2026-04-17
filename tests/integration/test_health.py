"""Integration tests for GET /api/health.

All tests run against the full FastAPI stack with SQLite in-memory.
The healthy path exercises a real SELECT 1; the unhealthy path patches
session.exec to simulate a connection failure.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from src.__version__ import __version__


class TestPublicHealthResponse:
    def test_returns_200_without_auth(self, client: TestClient) -> None:
        """Public health endpoint returns HTTP 200."""
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_public_response_contains_only_status(self, client: TestClient) -> None:
        """Unauthenticated callers receive liveness-only status."""
        data = client.get("/api/health").json()
        assert data == {"status": "healthy"}


    def test_returns_503_when_db_fails(
        self, client: TestClient, session: Session
    ) -> None:
        """DB failure causes a 503 response."""
        with patch.object(session, "exec", side_effect=Exception("connection refused")):
            response = client.get("/api/health")
        assert response.status_code == 503

    def test_public_unhealthy_response_omits_sensitive_fields(
        self, client: TestClient, session: Session
    ) -> None:
        """Unauthenticated unhealthy response remains liveness-only."""
        with patch.object(session, "exec", side_effect=Exception("timeout")):
            data = client.get("/api/health").json()
        assert data == {"status": "unhealthy"}


class TestAuthenticatedHealthResponse:
    def test_bearer_token_receives_detailed_response(
        self, client: TestClient, reader_token: str
    ) -> None:
        """Authenticated callers receive the detailed health payload."""
        data = client.get(
            "/api/health",
            headers={"Authorization": f"Bearer {reader_token}"},
        ).json()
        assert data["status"] == "healthy"
        assert data["version"] == __version__
        assert data["database"] == "connected"
        assert isinstance(data["uptime_seconds"], float)
        assert data["uptime_seconds"] >= 0.0

    def test_cookie_token_receives_detailed_response(
        self, client: TestClient, reader_token: str
    ) -> None:
        """Health route should honor the auth cookie on excluded paths."""
        data = client.get(
            "/api/health",
            cookies={"ht_access_token": reader_token},
        ).json()
        assert "version" in data
        assert "database" in data
        assert "uptime_seconds" in data

    def test_authenticated_db_failure_falls_back_to_public_response(
        self,
        client: TestClient,
        reader_token: str,
        session: Session,
    ) -> None:
        """Authenticated callers must still get the degraded public payload when DB auth cannot run."""
        with patch.object(session, "exec", side_effect=Exception("connection refused")):
            with patch.object(session, "get", side_effect=Exception("db unavailable")):
                response = client.get(
                    "/api/health",
                    headers={"Authorization": f"Bearer {reader_token}"},
                )

        assert response.status_code == 503
        assert response.json() == {"status": "unhealthy"}

    def test_stale_token_falls_back_to_public_response(
        self,
        client: TestClient,
        admin_token: str,
        admin_user,
        session: Session,
    ) -> None:
        """Stale tokens must not receive detailed health information."""
        admin_user.token_version += 1
        session.add(admin_user)
        session.commit()

        response = client.get(
            "/api/health",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_inactive_token_falls_back_to_public_response(
        self,
        client: TestClient,
        admin_token: str,
        admin_user,
        session: Session,
    ) -> None:
        """Inactive users must not receive detailed health information."""
        admin_user.is_active = False
        session.add(admin_user)
        session.commit()

        response = client.get(
            "/api/health",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_cookie_takes_precedence_over_authorization_header(
        self,
        client: TestClient,
        admin_token: str,
        admin_user,
        reader_token: str,
        session: Session,
    ) -> None:
        """Optional auth should mirror middleware precedence: cookie first."""
        admin_user.token_version += 1
        session.add(admin_user)
        session.commit()

        response = client.get(
            "/api/health",
            cookies={"ht_access_token": admin_token},
            headers={"Authorization": f"Bearer {reader_token}"},
        )

        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


class TestNoAuthRequired:
    def test_health_endpoint_included_in_excluded_paths(self) -> None:
        """EXCLUDED_API_PATHS in auth middleware contains /api/health."""
        from src.api.middleware.auth import EXCLUDED_API_PATHS

        assert "/api/health" in EXCLUDED_API_PATHS


class TestRouterConcurrency:
    def test_slow_devices_request_does_not_starve_health(
        self, client: TestClient, reader_token: str
    ) -> None:
        """A slow sync router request does not block a second cheap request."""
        slow_started = Event()
        allow_slow_finish = Event()

        def slow_get_all(*args: object, **kwargs: object) -> tuple[list[object], int]:
            slow_started.set()
            if not allow_slow_finish.wait(timeout=1):
                raise AssertionError(
                    "health request did not complete while the slow devices request was running"
                )
            return [], 0

        with patch(
            "src.api.routers.devices.device_service.get_all",
            side_effect=slow_get_all,
        ):
            with patch(
                "src.api.routers.health.check_db_connectivity",
                return_value=True,
            ):
                with ThreadPoolExecutor(max_workers=2) as executor:
                    slow_future = executor.submit(
                        client.get,
                        "/api/devices/",
                        headers={"Authorization": f"Bearer {reader_token}"},
                    )
                    assert slow_started.wait(timeout=1), "slow devices request never started"

                    health_response = client.get("/api/health")
                    allow_slow_finish.set()
                    slow_response = slow_future.result(timeout=1)

        assert health_response.status_code == 200
        assert health_response.json()["status"] == "healthy"
        assert slow_response.status_code == 200
        assert slow_response.json()["total"] == 0
