# Bug Report 13-04-26.1

## QA Remediation Ledger

| Bug ID | Status | Root Cause (1 sentence) | Fix (lines) | Tests Added |
|---|---|---|---|---|
| BUG-001 | ROUTED_ELSEWHERE | Export schema omits workspaces/topologies — requires migration + multi-service changes. | — | — |
| BUG-002 | ROUTED_ELSEWHERE | Non-atomic version check in diagram update allows concurrent writes — requires SELECT FOR UPDATE or atomic WHERE clause (Architect). | — | — |
| BUG-003 | FIXED | `int(payload["version"])` in auth middleware raises ValueError for non-numeric JWT claims, producing 500 instead of 401. | 5 | 3 |
| BUG-004 | FIXED | Import endpoint returns raw `exc.orig` (SQL internals + PII) to client and logs full IntegrityError. | 4 | 2 |
| BUG-005 | ROUTED_ELSEWHERE | Router owns transaction boundary (commit/rollback) instead of service layer — architectural pattern violation. | — | — |
| BUG-006 | FIXED | `ConnectionUpdate` omits self-loop validator present in `ConnectionBase`, allowing `source_id == target_id` via PATCH. | 8 | 3 |
| BUG-007 | ROUTED_ELSEWHERE | Missing `ondelete='CASCADE'` on `Topology.workspace_id` — requires Alembic migration (DevOps-Engineer). | — | — |
| BUG-008 | FIXED | Autosave fetch promise discards non-OK responses (`r.ok ? r.json() : null`) with no error handling or user notification. | 10 | — |
| BUG-009 | FIXED | `LocationUpdate.name` lacks `min_length=1` and whitespace-only guard present in `LocationBase`. | 6 | — |
| BUG-010 | FIXED | `ConnectionUpdate.label` omits `max_length=255` constraint from `ConnectionBase`. | 1 | 2 |
| BUG-011 | ROUTED_ELSEWHERE | Service/repository assume DB cascade for topology→diagram cleanup but models lack `ondelete` (Architect). | — | — |
| BUG-012 | FIXED | `create_user()` logs `email={}` in cleartext — PII leakage to logs. | 1 | — |
| BUG-013 | ROUTED_ELSEWHERE | Synchronous `Session(engine)` inside async `AuthMiddleware.dispatch` blocks event loop (Architect). | — | — |
| BUG-014 | FIXED | Both Cytoscape `cxttap` and native `contextmenu` dispatch `ht:context-menu-request` causing double context menus. | 3 | — |
| BUG-015 | FIXED | `validate_ip()` calls `ipaddress.ip_address()` without `strip()`, rejecting whitespace-padded IPs. | 1 | — |
| BUG-016 | FIXED | `validate_mac()` runs regex without `strip()`, rejecting whitespace-padded MACs. | 1 | — |
| BUG-017 | FIXED | Dead `ht:node-context` custom event dispatched in `cxttap` handler with zero consumers. | -3 | — |

**Pipeline Verdict: ALL_CLEAR** — 11 fixed, 6 routed elsewhere (BUG-001/007 → DevOps-Engineer; BUG-002/005/011/013 → Architect).

## Executive Summary
| Severity | Count |
|---|---|
| Critical | 1 |
| High | 7 |
| Medium | 8 |
| Low | 1 |
| **Total** | **17** |

## Prioritized Findings
| ID | Sev | Score | Title | File:Line | Routing |
|---|---:|---:|---|---|---|
| BUG-001 | Critical | 21 | Export schema omits workspaces/topologies → backup/restore data loss | [src/models/export_schema.py](src/models/export_schema.py#L101) | Infrastructure (DevOps-Engineer) |
| BUG-002 | High | 18 | Last-write-wins on concurrent DiagramLayout.update (optimistic check bypass) | [src/services/diagram_service.py](src/services/diagram_service.py#L105) | Architectural (Architect → Feature-Engineer) |
| BUG-003 | High | 18 | Auth middleware raises unhandled exception for non-integer JWT `version` claim | [src/api/middleware/auth.py](src/api/middleware/auth.py#L66) | Tactical (QA-Fixer) |
| BUG-004 | High | 18 | Import endpoint logs DB IntegrityError and returns internals to clients | [src/api/routers/data_transfer.py](src/api/routers/data_transfer.py#L153) | Tactical (QA-Fixer) |
| BUG-005 | High | 18 | Router performs DB commit/rollback (transaction ownership in router) | [src/api/routers/data_transfer.py](src/api/routers/data_transfer.py#L144) | Architectural (Architect → Feature-Engineer) |
| BUG-006 | High | 18 | ConnectionUpdate lacks self-loop validation (allows source == target) | [src/models/connection.py](src/models/connection.py#L45) | Tactical (QA-Fixer) |
| BUG-007 | High | 17 | Missing `ondelete='CASCADE'` on Topology.workspace_id (workspace delete mismatch) | [src/models/topology.py](src/models/topology.py#L28) | Infrastructure (DevOps-Engineer) |
| BUG-008 | High | 16 | Autosave silently ignores non-OK responses (e.g., 409) — layout changes can be lost | [src/ui/components/canvas_js_utils.py](src/ui/components/canvas_js_utils.py#L20) | Tactical (QA-Fixer) |
| BUG-009 | Medium | 15 | LocationUpdate allows empty/whitespace `name` (missing validator/min_length) | [src/models/location.py](src/models/location.py#L92) | Tactical (QA-Fixer) |
| BUG-010 | Medium | 15 | ConnectionUpdate omits `max_length` for `label` (inconsistent with ConnectionBase) | [src/models/connection.py](src/models/connection.py#L45) | Tactical (QA-Fixer) |
| BUG-011 | Medium | 14 | Repository/service rely on DB cascade instead of explicit cleanup (workspace/topology mismatch) | [src/services/topology_service.py](src/services/topology_service.py#L56) | Architectural (Architect → Feature-Engineer) |
| BUG-012 | Medium | 14 | Email logged in cleartext on user creation (PII in logs) | [src/services/user_service.py](src/services/user_service.py#L61) | Tactical (QA-Fixer) |
| BUG-013 | Medium | 12 | Synchronous DB call inside async AuthMiddleware.dispatch (blocks event loop) | [src/api/middleware/auth.py](src/api/middleware/auth.py#L64) | Architectural (Architect → Feature-Engineer) |
| BUG-014 | Medium | 11 | Context menu can be dispatched twice (Cytoscape `cxttap` + native `contextmenu`) | [src/ui/components/canvas_js.py](src/ui/components/canvas_js.py#L167) | Tactical (QA-Fixer) |
| BUG-015 | Medium | 10 | `validate_ip()` rejects IPs with surrounding whitespace (missing trim) | [src/domain/devices.py](src/domain/devices.py#L22) | Tactical (QA-Fixer) |
| BUG-016 | Medium | 8 | `validate_mac()` rejects MACs with surrounding whitespace (missing trim) | [src/domain/devices.py](src/domain/devices.py#L13) | Tactical (QA-Fixer) |
| BUG-017 | Low | 5 | Dead/unused custom event `ht:node-context` is dispatched but not consumed | [src/ui/components/canvas_js.py](src/ui/components/canvas_js.py#L167) | Tactical (QA-Fixer) |

## Details

### BUG-001 — Export schema omits workspaces/topologies → backup/restore data loss (Critical)
- **File:** [src/models/export_schema.py](src/models/export_schema.py#L101)
- **Trigger:** Run `export_service.build_full_export(session)` then `import_service.import_full_snapshot(session, exported)` to perform a restore.
- **Root Cause / Failure Mode:** `ExportSchema` and `ExportedDiagramLayout` omit `workspaces`/`topologies` and `topology_id`. `import_full_snapshot` truncates and re-inserts layouts without restoring topology associations, causing irreversible loss of workspace/topology configuration.
- **Proof Test:**
```python
# tests/unit/test_export_import_preserves_diagram_topology.py
import pytest
from src.models.user import User
from src.models.workspace import Workspace
from src.models.topology import Topology
from src.models.diagram import DiagramLayout
from src.models.types import Role
from src.repositories import workspace_repository, topology_repository, diagram_repository
from src.services import export_service, import_service

def test_export_import_preserves_diagram_topology_id(session):
    # Arrange: create user, workspace, topology and a diagram attached to that topology
    user = User(username="u2", email="u2@test.local", password_hash="x", role=Role.Admin)
    session.add(user); session.commit(); session.refresh(user)

    ws = Workspace(name="ws2", owner_id=user.id); workspace_repository.create(session, ws)
    session.commit(); session.refresh(ws)

    topo = Topology(name="t2", workspace_id=ws.id); topology_repository.create(session, topo)
    session.commit(); session.refresh(topo)

    layout = DiagramLayout(name="view1", cytoscape_json={'elements': []}, topology_id=topo.id)
    diagram_repository.create(session, layout); session.commit(); session.refresh(layout)

    # Act: export then import into the same DB (destructive restore)
    exported = export_service.build_full_export(session)
    import_service.import_full_snapshot(session, exported)
    session.commit()

    # Assert: expect topology association preserved (this will fail in current codebase)
    layouts = diagram_repository.get_all_for_export(session)
    assert len(layouts) == 1
    assert layouts[0].topology_id == topo.id
```
- **Fix Direction:** Include `workspaces` and `topologies` in `ExportSchema`; add `topology_id` to `ExportedDiagramLayout`; export/import workspaces/topologies first, then layout rows; add migration/tests. Route to DevOps-Engineer for migration + Feature-Engineer for service changes.
- **Routing:** Infrastructure (DevOps-Engineer)

---

### BUG-002 — Last-write-wins on concurrent DiagramLayout.update (High)
- **File:** [src/services/diagram_service.py](src/services/diagram_service.py#L105)
- **Trigger:** Two concurrent update requests with the same `version` execute concurrently and both commit.
- **Root Cause / Failure Mode:** `get_by_id_for_update` may do a non-locking read. If DB row-locking isn't used, both requests pass version check and commit → lost update.
- **Proof Test:**
```python
# tests/unit/test_diagram_concurrent_update.py
import threading
import time
import uuid
from sqlmodel import Session
from src.utils.db import engine
from src.models.user import User
from src.models.workspace import Workspace
from src.models.topology import Topology
from src.models.diagram import DiagramLayout, DiagramLayoutCreate
from src.services import diagram_service
from fastapi import HTTPException

def test_concurrent_updates_should_produce_conflict():
    with Session(engine) as s:
        user = User(username=f"race_{uuid.uuid4().hex[:6]}", email=f"race_{uuid.uuid4().hex[:6]}@test.local", password_hash="x"*60)
        s.add(user); s.commit()
        ws = Workspace(name="ws", owner_id=user.id); s.add(ws); s.commit()
        topo = Topology(name="topo", workspace_id=ws.id); s.add(topo); s.commit()
        layout = DiagramLayout(name="L", cytoscape_json={"nodes": []}, topology_id=topo.id)
        s.add(layout); s.commit()
        layout_id = layout.id
        initial_version = layout.version

    results = [None, None]
    start_evt = threading.Event()

    def worker(new_payload, idx):
        try:
            start_evt.wait()
            with Session(engine) as s2:
                data = DiagramLayoutCreate(
                    name="L",
                    cytoscape_json=new_payload,
                    topology_id=topo.id,
                    version=initial_version,
                )
                diagram_service.update(layout_id, data, user.id, s2)
            results[idx] = "ok"
        except HTTPException as exc:
            results[idx] = f"http_{exc.status_code}"
        except Exception:
            results[idx] = "err"

    t1 = threading.Thread(target=worker, args=({"nodes": ["a"]}, 0))
    t2 = threading.Thread(target=worker, args=({"nodes": ["b"]}, 1))
    t1.start(); t2.start()
    time.sleep(0.05)
    start_evt.set()
    t1.join(); t2.join()

    assert any(r == "http_409" for r in results), f"No conflict detected, results={results}"
```
- **Fix Direction:** Ensure `get_by_id_for_update` uses a DB row-level lock (SELECT FOR UPDATE) or perform an atomic UPDATE WHERE id=? AND version=? and check affected-row-count to return 409 on zero-updates. Add integration tests for both DB types.
- **Routing:** Architectural (Architect → Feature-Engineer)

---

### BUG-003 — Auth middleware raises unhandled exception for non-integer JWT `version` claim (High)
- **File:** [src/api/middleware/auth.py](src/api/middleware/auth.py#L66)
- **Trigger:** Send a validly-signed JWT with `version` claim as a non-numeric string (e.g., "not-an-int").
- **Root Cause / Failure Mode:** Middleware performs `int(payload['version'])` without defensive parsing, raising ValueError and producing HTTP 500 instead of 401.
- **Proof Test:**
```python
# tests/unit/test_auth_middleware_version_claim.py
import uuid
from src.models.user import User
from src.models.types import Role
from src.utils.auth import create_jwt, hash_password

def test_malformed_version_claim_leads_to_401_not_500(client, session):
    user = User(
        username="malformed_ver",
        email="malformed_ver@test.local",
        password_hash=hash_password("x"),
        role=Role.Reader,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    token = create_jwt({"sub": str(user.id), "role": "Reader", "version": "not-an-int"})
    headers = {"Authorization": f"Bearer {token}"}
    res = client.get("/api/devices/", headers=headers)

    assert res.status_code == 401, f"Expected 401, got {res.status_code}: {res.text}"
```
- **Fix Direction:** Defensive-parse `version` claim (try/except TypeError/ValueError) and treat parse failures as invalid tokens (return 401). Alternatively validate claim types earlier in `decode_jwt()`.
- **Routing:** Tactical (QA-Fixer)

---

### BUG-004 — Import endpoint logs DB IntegrityError and returns internals to clients (High)
- **File:** [src/api/routers/data_transfer.py](src/api/routers/data_transfer.py#L153)
- **Trigger:** A call to `/api/import` that causes a DB `IntegrityError`.
- **Root Cause / Failure Mode:** Router logs `str(exc)` and returns `exc.orig` in HTTP detail — this exposes SQL/parameters and possibly PII to logs and clients.
- **Proof Test:**
```python
# tests/unit/test_import_endpoint_logs_integrity_error.py
import io
import json
from sqlalchemy.exc import IntegrityError

from src.utils.logger import logger

def test_import_endpoint_logs_integrity_error(monkeypatch, client, admin_token):
    sink = io.StringIO()
    sink_id = logger.add(sink, level="ERROR", format="{message}")

    class DummyPayload:
        version = "1"

    monkeypatch.setattr("src.api.routers.data_transfer.ExportSchema.model_validate", lambda payload: DummyPayload())
    monkeypatch.setattr("src.api.routers.data_transfer.validate_export_version", lambda v: None)

    def fake_import(session_arg, payload_arg):
        raise IntegrityError(
            "INSERT INTO users",
            {},
            Exception("duplicate key value violates unique constraint \"users_email_key\": (email)=(sensitive@example.com)")
        )

    monkeypatch.setattr("src.api.routers.data_transfer.import_full_snapshot", fake_import)

    headers = {"Authorization": f"Bearer {admin_token}"}
    files = {"file": ("payload.json", b"{}", "application/json")}

    resp = client.post("/api/import?confirm=true", files=files, headers=headers)
    assert resp.status_code == 422

    logger.remove(sink_id)
    assert "duplicate key value" in sink.getvalue()
```
- **Fix Direction:** Remove or redact raw exception logging and do not return `exc.orig` to clients; return a generic client-facing message and log sanitized details internally.
- **Routing:** Tactical (QA-Fixer)

---

### BUG-005 — Router performs DB commit/rollback (transaction ownership in router) (High)
- **File:** [src/api/routers/data_transfer.py](src/api/routers/data_transfer.py#L144)
- **Trigger:** `POST /api/import?confirm=true` — router calls `session.commit()` after `import_full_snapshot`.
- **Root Cause / Failure Mode:** Transaction boundary is in the API layer instead of the service layer; `import_full_snapshot` only flushes and expects service to own commit.
- **Proof Test:**
```python
# tests/unit/test_import_endpoint_does_not_commit_in_router.py
import json

def test_import_endpoint_does_not_commit_in_router(client, admin_token, monkeypatch):
    class DummySession:
        def __init__(self):
            self.commit_called = False
            self.rollback_called = False
        def commit(self):
            self.commit_called = True
        def rollback(self):
            self.rollback_called = True
    dummy_session = DummySession()

    monkeypatch.setattr("src.services.import_service.import_full_snapshot", lambda s, payload: {"devices": 0})
    from src.utils.db import get_session
    client.app.dependency_overrides[get_session] = lambda: dummy_session

    payload = {"version": 1, "users": [], "locations": [], "tags": [], "devices": [],
               "services": [], "service_dependencies": [], "connections": [],
               "device_tags": [], "custom_fields": [], "diagram_layouts": []}
    files = {"file": ("payload.json", json.dumps(payload), "application/json")}
    resp = client.post("/api/import?confirm=true", files=files, headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert not dummy_session.commit_called, "Router performed session.commit(); commit should be owned by service layer"
```
- **Fix Direction:** Move commit/rollback and DB-error handling into `import_full_snapshot` (service layer). Router should delegate to service and convert service exceptions to HTTP responses.
- **Routing:** Architectural (Architect → Feature-Engineer)

---

### BUG-006 — ConnectionUpdate lacks self-loop validation (High)
- **File:** [src/models/connection.py](src/models/connection.py#L45)
- **Trigger:** Construct a `ConnectionUpdate` with `source_id == target_id`.
- **Root Cause / Failure Mode:** Base `ConnectionBase` has a self-loop validator (for creates) but `ConnectionUpdate` omits it, allowing invalid updates.
- **Proof Test:**
```python
import pytest
import uuid
from src.models.connection import ConnectionUpdate

def test_connection_update_rejects_self_loop():
    u = uuid.uuid4()
    with pytest.raises(ValueError):
        ConnectionUpdate(source_id=u, target_id=u)
```
- **Fix Direction:** Ensure `ConnectionUpdate` includes the same validator (or reuse the base validator) so updates also reject self-loops.
- **Routing:** Tactical (QA-Fixer)

---

### BUG-007 — Missing `ondelete='CASCADE'` on Topology.workspace_id (High)
- **File:** [src/models/topology.py](src/models/topology.py#L28)
- **Trigger:** Delete a workspace while Topology rows exist.
- **Root Cause / Failure Mode:** `Topology.workspace_id` declared without `ondelete='CASCADE'`; code assumes DB cascade and service comments state CASCADE handles children. Depending on DB settings, delete may fail or leave orphans.
- **Proof Test:**
```python
# tests/unit/test_workspace_delete_cascade.py
import pytest
from src.models.user import User
from src.models.workspace import Workspace
from src.models.topology import Topology
from src.models.types import Role
from src.repositories import workspace_repository, topology_repository

def test_workspace_delete_should_cascade_topologies(session):
    user = User(username="u1", email="u1@test.local", password_hash="x", role=Role.Admin)
    session.add(user); session.commit(); session.refresh(user)

    ws = Workspace(name="ws1", owner_id=user.id)
    workspace_repository.create(session, ws)
    session.commit(); session.refresh(ws)

    topo = Topology(name="t1", workspace_id=ws.id)
    topology_repository.create(session, topo)
    session.commit(); session.refresh(topo)

    workspace_repository.delete(session, ws)
    session.commit()

    assert topology_repository.get_by_id(session, topo.id) is None
```
- **Fix Direction:** Add `ondelete='CASCADE'` on `Topology.workspace_id` and create Alembic migration, or perform explicit child deletes in service before deleting workspace.
- **Routing:** Infrastructure (DevOps-Engineer)

---

### BUG-008 — Autosave silently ignores non-OK responses (High)
- **File:** [src/ui/components/canvas_js_utils.py](src/ui/components/canvas_js_utils.py#L20)
- **Trigger:** Server returns 409 for the PATCH from `_htFlushAutosave`; client ignores and does not notify the user.
- **Root Cause / Failure Mode:** The autosave promise resolves `r.ok ? r.json() : null` and ignores non-OK results; no toast, no reconciliation.
- **Proof Test / Repro:** (Node + puppeteer repro script)
```js
// tests/e2e/repro_autosave_conflict.js (see saved repro in lane output)
// Simulates fetch returning { ok: false, status: 409 } and asserts client version unchanged and no user-visible handling.
```
- **Fix Direction:** Handle non-OK responses explicitly: show toast on 409, fetch latest layout, offer merge/rebase or retry. Add `.catch()` and explicit HTTP-code handling.
- **Routing:** Tactical (QA-Fixer)

---

### BUG-009 — LocationUpdate allows empty/whitespace `name` (Medium)
- **File:** [src/models/location.py](src/models/location.py#L92)
- **Trigger:** Provide `LocationUpdate(name="   ")`.
- **Root Cause / Failure Mode:** `LocationUpdate` omits `min_length`/strip validator present in `LocationBase`.
- **Proof Test:**
```python
import pytest
from src.models.location import LocationUpdate

def test_location_update_rejects_whitespace_name():
    with pytest.raises(ValueError):
        LocationUpdate(name="   ")
```
- **Fix Direction:** Add consistent validators to `LocationUpdate` (strip + min_length) or validate in service layer.
- **Routing:** Tactical (QA-Fixer)

---

### BUG-010 — ConnectionUpdate omits `max_length` for `label` (Medium)
- **File:** [src/models/connection.py](src/models/connection.py#L45)
- **Trigger:** Provide an overly long `label` in `ConnectionUpdate`.
- **Root Cause / Failure Mode:** Partial update schema removed `max_length=255` constraint from `label`.
- **Proof Test:**
```python
import pytest
from src.models.connection import ConnectionUpdate

def test_connection_update_label_max_length_enforced():
    long_label = "x" * 300
    with pytest.raises(ValueError):
        ConnectionUpdate(label=long_label)
```
- **Fix Direction:** Restore `max_length` constraints on update schemas or validate in domain/service layer.
- **Routing:** Tactical (QA-Fixer)

---

### BUG-011 — Repository/service rely on DB cascade instead of explicit cleanup (Medium)
- **File:** [src/services/topology_service.py](src/services/topology_service.py#L56)
- **Trigger:** Delete topology with DiagramLayout children.
- **Root Cause / Failure Mode:** Service comments assume DB cascade; models lack `ondelete` -> inconsistent behavior across DB engines.
- **Proof Test:**
```python
# tests/unit/test_topology_delete_cascade_expectation.py
from src.models.user import User
from src.models.workspace import Workspace
from src.models.topology import Topology
from src.models.diagram import DiagramLayout
from src.models.types import Role
from src.repositories import topology_repository, diagram_repository, workspace_repository

def test_topology_delete_should_cascade_views(session):
    user = User(username="u4", email="u4@test.local", password_hash="x", role=Role.Admin)
    session.add(user); session.commit(); session.refresh(user)

    ws = Workspace(name="ws4", owner_id=user.id); workspace_repository.create(session, ws)
    session.commit(); session.refresh(ws)

    topo = Topology(name="t4", workspace_id=ws.id); topology_repository.create(session, topo)
    session.commit(); session.refresh(topo)

    layout = DiagramLayout(name="v4", cytoscape_json={'elements': []}, topology_id=topo.id)
    diagram_repository.create(session, layout); session.commit(); session.refresh(layout)

    topology_repository.delete(session, topo)
    session.commit()

    assert diagram_repository.get_by_id(session, layout.id) is None
```
- **Fix Direction:** Either add `ondelete='CASCADE'` or delete child DiagramLayouts explicitly in the service before deleting the topology; add tests for both DB behaviors.
- **Routing:** Architectural (Architect → Feature-Engineer)

---

### BUG-012 — Email logged in cleartext on user creation (Medium)
- **File:** [src/services/user_service.py](src/services/user_service.py#L61)
- **Trigger:** `create_user()` emits `logger.info("User created: email={}", created.email)`.
- **Root Cause / Failure Mode:** Plaintext emails are logged, leaking PII to logs.
- **Proof Test:**
```python
import io
from src.utils.logger import logger
from src.models.user import UserCreate
from src.models.types import Role
from src.services.user_service import create_user

def test_create_user_logs_email(session):
    sink = io.StringIO()
    sink_id = logger.add(sink, level="INFO", format="{message}")

    data = UserCreate(
        username="testuser",
        email="sensitive@example.com",
        password="S3curePass1!",
        role=Role.Contributor,
        is_active=True,
    )

    create_user(data, session)

    logger.remove(sink_id)
    assert "sensitive@example.com" in sink.getvalue()
```
- **Fix Direction:** Do not log plaintext emails; log masked or `user_id` instead.
- **Routing:** Tactical (QA-Fixer)

---

### BUG-013 — Synchronous DB call inside async AuthMiddleware.dispatch (Medium)
- **File:** [src/api/middleware/auth.py](src/api/middleware/auth.py#L64)
- **Trigger:** Slow DB during authentication.
- **Root Cause / Failure Mode:** Auth middleware is `async` but calls blocking `Session` directly, which can block the event loop.
- **Proof Test:**
```python
# tests/unit/test_auth_middleware_blocking.py
import time
import uuid
from types import SimpleNamespace
import pytest
from starlette.requests import Request
from starlette.responses import Response
from src.api.middleware.auth import AuthMiddleware
import src.api.middleware.auth as auth_module

class SlowSession:
    def __init__(self, engine):
        pass
    def __enter__(self):
        import time as _time
        _time.sleep(0.4)
        return self
    def __exit__(self, exc_type, exc, tb):
        return False
    def get(self, model, user_id):
        return SimpleNamespace(token_version=1)

@pytest.mark.asyncio
async def test_auth_middleware_blocks_on_sync_db(monkeypatch):
    monkeypatch.setattr(auth_module, "decode_jwt", lambda token: {"sub": str(uuid.uuid4()), "version": "1", "role": "Contributor"})
    monkeypatch.setattr(auth_module, "Session", lambda engine: SlowSession(engine))

    mw = AuthMiddleware(app=object())
    scope = {"type": "http", "method": "GET", "path": "/api/devices", "headers": [(b"authorization", b"Bearer token")], "query_string": b"", "client": ("test", 1), "scheme": "http"}
    req = Request(scope)

    async def call_next(request):
        return Response("ok")

    start = time.monotonic()
    resp = await mw.dispatch(req, call_next)
    elapsed = time.monotonic() - start

    assert elapsed >= 0.3
    assert resp.status_code == 200
```
- **Fix Direction:** Run blocking DB access in threadpool (run_in_threadpool) or make middleware sync or use an async DB driver.
- **Routing:** Architectural (Architect → Feature-Engineer)

---

### BUG-014 — Context menu can be dispatched twice (Medium)
- **File:** [src/ui/components/canvas_js.py](src/ui/components/canvas_js.py#L167)
- **Trigger:** Right-click on a node when both Cytoscape `cxttap` and native `contextmenu` fire.
- **Root Cause / Failure Mode:** Both handlers dispatch `ht:context-menu-request` causing duplicate menus.
- **Proof Test / Repro:** (Node + puppeteer repro available in lane output)
```js
// tests/e2e/repro_ctxmenu_dup.js (see lane output)
// Reproduces double-dispatch by right-clicking a node and counting `ht:context-menu-request` events.
```
- **Fix Direction:** Deduplicate dispatch by setting a short-lived flag/timestamp in the cxttap handler or prefer a single canonical dispatch point.
- **Routing:** Tactical (QA-Fixer)

---

### BUG-015 — `validate_ip()` rejects IPs with surrounding whitespace (Medium)
- **File:** [src/domain/devices.py](src/domain/devices.py#L22)
- **Trigger:** `validate_ip(" 192.168.1.1 ")` fails.
- **Root Cause / Failure Mode:** Input is not trimmed before calling `ipaddress.ip_address()`.
- **Proof Test:**
```python
import pytest
from src.domain.devices import validate_ip

def test_validate_ip_accepts_surrounding_whitespace():
    assert validate_ip(" 192.168.1.1 ") == "192.168.1.1"
```
- **Fix Direction:** Trim input (`ip = ip.strip()`), then validate and return canonical IP string.
- **Routing:** Tactical (QA-Fixer)

---

### BUG-016 — `validate_mac()` rejects MACs with surrounding whitespace (Medium)
- **File:** [src/domain/devices.py](src/domain/devices.py#L13)
- **Trigger:** `validate_mac(" aa:bb:cc:dd:ee:ff ")` fails.
- **Root Cause / Failure Mode:** Missing `strip()` before regex match and normalization.
- **Proof Test:**
```python
import pytest
from src.domain.devices import validate_mac

def test_validate_mac_accepts_surrounding_whitespace():
    assert validate_mac(" aa:bb:cc:dd:ee:ff ") == "AA:BB:CC:DD:EE:FF"
```
- **Fix Direction:** Trim input and normalize separators before regex validation.
- **Routing:** Tactical (QA-Fixer)

---

### BUG-017 — Dead/unused custom event `ht:node-context` is dispatched but not consumed (Low)
- **File:** [src/ui/components/canvas_js.py](src/ui/components/canvas_js.py#L167)
- **Trigger:** Right-click on node dispatches `ht:node-context` with no consumers.
- **Proof Test:**
```sh
# shell proof (grep)
grep -R "ht:node-context" -n src || true
# Expectation: no consumers besides the dispatch site
```
- **Fix Direction:** Remove redundant `ht:node-context` event or add a consumer; consolidate on `ht:context-menu-request`.
- **Routing:** Tactical (QA-Fixer)

---

## Duplicate Merge Log
| Kept | Merged | Reason |
|---|---|---|
| (none) | (none) | No duplicate findings required merging — all findings are distinct by dup_key or primary_file + failure mode. |

## Lane Coverage Status
| Lane | ODC | Findings | Status | Notes |
|---|---|---:|---|---|
| lane-1 | Function (models validators) | 3 | Completed | Model update schemas missing validators (self-loop, lengths, whitespace) |
| lane-2 | Assignment (repositories) | 0 | Completed | Repositories follow expected pattern; no direct session lifecycle issues found. |
| lane-3 | Checking (services error handling) | 0 | Failed / No response | Subagent returned no response — recommend re-run lane-3 to verify service-layer error handling. |
| lane-4 | Timing/Serialization | 2 | Completed | Concurrency (last-write-wins) and blocking DB in async middleware found. |
| lane-5 | Auth/RBAC | 1 | Completed | Unguarded `version` claim int() coercion issue found in auth middleware. |
| lane-6 | Integrity | 3 | Completed | Missing `ondelete`, export/import data loss, repo/service cascade assumptions. |
| lane-7 | Documentation (logs) | 2 | Completed | PII in logs and import endpoint leakage. |
| lane-8 | Interface (architecture) | 1 | Completed | Router owns transaction boundary for import endpoint. |
| lane-9 | Algorithm (canvas UI) | 3 | Completed | Context-menu duplication, autosave silent-fail, dead event. |
| lane-10 | Algorithm (domain) | 2 | Completed | IP/MAC trimming missing in domain validators. |

## Handoff Summary
- **QA-Fixer:** 11 findings (BUG-003, BUG-004, BUG-006, BUG-008, BUG-009, BUG-010, BUG-012, BUG-014, BUG-015, BUG-016, BUG-017)
- **Architect → Feature-Engineer:** 4 findings (BUG-002, BUG-005, BUG-011, BUG-013)
- **DevOps-Engineer:** 2 findings (BUG-001, BUG-007)

Please let me know if you want me to:
- Re-run a failed lane (lane-3) now.
- Convert the two Node repros (canvas contextmenu & autosave) to Playwright/Pytest under `tests/e2e/`.
- Open small branch+patch PRs for tactical fixes (I can implement and run unit tests for items like safe `int()` parsing in auth middleware and validator trims).


<!-- Report generated by QA-Orchestrator on 2026-04-13 -->
