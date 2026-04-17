"""HT-011: RBAC coverage audit and Reader write-access enforcement tests.

§10 coverage test: asserts every /api/ route (except login) has a
require_role dependency marked with _rbac_protected=True.

Reader 403 tests: parametrized over all Contributor+/Admin+ write endpoints
to prove that a Reader JWT is denied before any handler logic runs.
"""
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from src.api.app import app


# ---------------------------------------------------------------------------
# Route collection helpers
# ---------------------------------------------------------------------------

def _collect_api_routes(application: FastAPI) -> list[tuple[str, str]]:
    """Return (method, path) pairs for all /api/ routes excluding login."""
    excluded = {"/api/auth/login", "/api/health"}
    results: list[tuple[str, str]] = []
    for route in application.routes:
        if not isinstance(route, APIRoute):
            continue
        if not route.path.startswith("/api/"):
            continue
        if route.path in excluded:
            continue
        for method in route.methods or []:
            results.append((method, route.path))
    return results


def _has_rbac_dependency(route: APIRoute) -> bool:
    """Return True if any route-level dependency carries _rbac_protected=True."""
    return any(
        getattr(dep.dependency, "_rbac_protected", False)
        for dep in route.dependencies
    )


# ---------------------------------------------------------------------------
# §10 Coverage test — all routes except login must have require_role
# ---------------------------------------------------------------------------

_ROUTES = _collect_api_routes(app)


@pytest.mark.parametrize("method,path", _ROUTES, ids=lambda x: x)
def test_route_has_role_dependency(method: str, path: str) -> None:
    """Every /api/ route except login must declare a require_role dependency."""
    matching = [
        r for r in app.routes
        if isinstance(r, APIRoute) and r.path == path and method in (r.methods or [])
    ]
    assert len(matching) == 1, f"Could not locate route {method} {path}"
    route = matching[0]
    assert _has_rbac_dependency(route), (
        f"{method} {path} has no require_role dependency — "
        "add dependencies=[Depends(require_role(Role.X))] to this endpoint"
    )


# ---------------------------------------------------------------------------
# Reader 403 integration tests — write endpoints deny Readers
# ---------------------------------------------------------------------------

_PLACEHOLDER = "00000000-0000-0000-0000-000000000001"

# (method, path, json_body)  — body is ignored for DELETE/path-only requests
_WRITE_ENDPOINTS: list[tuple[str, str, dict | None]] = [
    ("POST",   "/api/devices/",                                     {"name": "x", "type": "Server"}),
    ("PATCH",  f"/api/devices/{_PLACEHOLDER}",                      {"name": "y", "version": 1}),
    ("DELETE", f"/api/devices/{_PLACEHOLDER}",                      None),
    ("PUT",    "/api/power/settings",                               {"cost_per_kwh": 0.15, "currency": "USD"}),
    ("POST",   "/api/connections/",                                  {"source_id": _PLACEHOLDER, "target_id": _PLACEHOLDER, "type": "Ethernet"}),
    ("DELETE", f"/api/connections/{_PLACEHOLDER}",                   None),
    ("POST",   "/api/locations/",                                    {"name": "rack1", "type": "rack"}),
    ("PATCH",  f"/api/locations/{_PLACEHOLDER}",                     {"name": "rack2"}),
    ("DELETE", f"/api/locations/{_PLACEHOLDER}",                     None),
    ("POST",   "/api/tags/",                                         {"name": "test", "color": "#aabbcc"}),
    ("DELETE", f"/api/tags/{_PLACEHOLDER}",                          None),
    ("POST",   f"/api/devices/{_PLACEHOLDER}/tags",                  {"tag_id": _PLACEHOLDER}),
    ("DELETE", f"/api/devices/{_PLACEHOLDER}/tags/{_PLACEHOLDER}",   None),
    ("POST",   f"/api/devices/{_PLACEHOLDER}/custom-fields",         {"key": "k", "value": "v"}),
    ("PATCH",  f"/api/devices/{_PLACEHOLDER}/custom-fields/k",       {"value": "v2"}),
    ("DELETE", f"/api/devices/{_PLACEHOLDER}/custom-fields/k",       None),
    ("POST",   "/api/diagrams/",                                     {"name": "d", "cytoscape_json": {}}),
    ("PUT",    f"/api/diagrams/{_PLACEHOLDER}",                      {"name": "d2", "cytoscape_json": {}}),
    ("DELETE", f"/api/diagrams/{_PLACEHOLDER}",                      None),
    ("PUT",    f"/api/topologies/{_PLACEHOLDER}/personal-draft",     {"cytoscape_json": {"elements": {"nodes": [], "edges": []}}}),
    ("POST",   f"/api/topologies/{_PLACEHOLDER}/save-version",       {"snapshot_name": "v1", "cytoscape_json": {"elements": {"nodes": [], "edges": []}}}),
    ("POST",   f"/api/topologies/{_PLACEHOLDER}/history/{_PLACEHOLDER}/restore", {"base_diagram_version": 1}),
]


@pytest.mark.parametrize("method,path,body", _WRITE_ENDPOINTS, ids=lambda x: str(x))
def test_reader_gets_403_on_write_endpoint(
    method: str,
    path: str,
    body: dict | None,
    client: TestClient,
    reader_token: str,
) -> None:
    """A Reader JWT must receive 403 on all write endpoints (role check before handler)."""
    headers = {"Authorization": f"Bearer {reader_token}"}
    if method == "POST":
        resp = client.post(path, json=body, headers=headers)
    elif method == "PATCH":
        resp = client.patch(path, json=body or {}, headers=headers)
    elif method == "PUT":
        resp = client.put(path, json=body or {}, headers=headers)
    elif method == "DELETE":
        resp = client.delete(path, headers=headers)
    else:
        pytest.skip(f"Unhandled method {method}")
    assert resp.status_code == 403, (
        f"Expected 403 for Reader on {method} {path}, got {resp.status_code}"
    )
