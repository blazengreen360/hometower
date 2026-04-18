---
name: testing-conventions
description: Hometower's test conventions — file structure, naming patterns, conftest fixtures, RBAC parametrization, mock boundaries, and test file locations. Read this when writing or reviewing tests.
---

# testing-conventions

## Testing Science

- **Mutation Testing as Coverage Proxy**: tests should fail if core logic, validation, or RBAC checks are broken
- **Equivalence Partitioning**: cover one representative per valid, invalid, and edge class
- **Boundary Value Analysis**: explicitly test just below, at, and just above important thresholds
- **Mock Boundary Principle (Freeman & Pryce, 2009)**: mock only at architectural boundaries, not inside the thing under test

Before calling a suite "good enough," mentally test whether it would catch:
- flipped comparison operators
- removed `None` checks
- swapped role checks
- missing validators
- wrong response branches

## Test File Structure

```python
"""Unit tests for src/domain/devices.py pure functions."""
import uuid
from uuid import uuid4

import pytest
from src.domain.devices import validate_ip, validate_mac

class TestValidateIp:
    def test_validate_ip_valid(self) -> None:
        assert validate_ip("192.168.1.1") == "192.168.1.1"

    def test_validate_ip_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_ip("not-an-ip")

    def test_validate_ip_none_returns_none(self) -> None:
        assert validate_ip(None) is None
```

**Conventions:**
- Classes: `TestXxx` grouping related tests
- Methods: `test_<function>_<scenario>` describing behavior
- Return type `-> None` on every test method
- One assertion per test (or closely related)
- `pytest.raises` with `match=` when message matters

## Integration Test Structure

```python
"""Integration tests for /api/devices/ CRUD endpoints."""
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient

DEVICE_PAYLOAD: dict[str, str] = {"name": "test-server", "type": "Server"}

class TestCreateDevice:
    def test_create_device_as_contributor_returns_201(
        self, client: TestClient, contributor_token: str
    ) -> None:
        response = client.post(
            "/api/devices/",
            json=DEVICE_PAYLOAD,
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-server"
        assert "id" in data
```

## Conftest Fixtures (from `tests/conftest.py`)

Available: `session`, `client`, `admin_token`, `contributor_token`, `reader_token`, `two_devices`, `admin_user`

- Auth headers: `{"Authorization": f"Bearer {token}"}`
- `uuid4()` for unique test data names (prevent cross-test collisions)
- Never create your own session or client — always use conftest
- `client` is sync `TestClient`, not async `AsyncClient`

## RBAC Parametrization Pattern

```python
class TestDeviceRBAC:
    def test_create_as_reader_returns_403(
        self, client: TestClient, reader_token: str
    ) -> None:
        response = client.post(
            "/api/devices/",
            json={"name": "x", "type": "Server"},
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 403

    def test_unauthenticated_returns_401(self, client: TestClient) -> None:
        response = client.get("/api/devices/")
        assert response.status_code == 401
```

**Every endpoint suite must cover:**
1. Happy path with correct role -> expected status
2. Forbidden role -> 403
3. No token -> 401
4. Not found -> 404
5. Invalid input -> 422
6. Conflict (if applicable) -> 409

## Mock Boundaries

**ALWAYS mock:** External HTTP, file system (use `tmp_path`), time (`freezegun`/`monkeypatch`), specific service functions in router tests (`monkeypatch.setattr`)

**NEVER mock:** Domain functions (pure — test directly), Pydantic validation (it's the test subject), SQLModel models (use conftest SQLite), conftest fixtures

## Quality Floor

- every test group needs at least one rejection or failure-mode case
- avoid tautological assertions and `assert True` style checks
- read source and sibling tests before writing new ones
- if a reproducer does not fail on unpatched code, it is not yet a useful regression test

## Test File Locations

| Category | Location | Tests | DB Required |
|---|---|---|---|
| Domain unit | `tests/unit/test_domain_*.py` | Pure functions in `src/domain/` | No |
| Model unit | `tests/unit/test_*_model.py` | SQLModel validators, field defaults | SQLite (conftest) |
| Service unit | `tests/unit/test_*_service.py` | Service orchestration, error handling | SQLite (conftest) |
| Integration | `tests/integration/test_*.py` | Full API endpoint CRUD + RBAC | SQLite (conftest) |
| E2E | `tests/e2e/test_*.py` | Playwright browser flows | Full stack |
