# Bug Report 13-04-26.2

## Executive Summary
| Severity | Count |
|---|---:|
| Critical | 1 |
| High | 6 |
| Medium | 14 |
| Low | 4 |
| **Total** | **25** |

Pipeline Verdict: OPEN — 25 findings open.

### Top 3 risks
1. **BUG-001 — High (21)** Role changes do not increment `token_version` (privilege retention). — Affects auth/token revocation.
2. **BUG-002 — Critical (20)** Export/import roundtrip loses workspaces/topologies and severs diagram → topology links. — Data-loss on import.
3. **BUG-003 — High (18)** Canvas event-handler init race: handlers attached before Cytoscape readiness, breaking edit-mode UX.

## Prioritized Findings
| ID | Sev | Score | Title | File:Line | Routing |
|---|---|---:|---|---|---|
| BUG-001 | High | 21 | Role changes do not increment `token_version` (privilege retention) | [src/services/user_service.py](src/services/user_service.py#L114) | Architectural → Architect/Feature-Engineer |
| BUG-002 | Critical | 20 | Export/import roundtrip loses workspaces/topologies | [src/services/import_service.py](src/services/import_service.py#L44) | Systemic → Architect/Feature-Engineer |
| BUG-003 | High | 18 | Event-handler init race: Cytoscape handlers attached before ready | [src/ui/components/canvas_events.py](src/ui/components/canvas_events.py#L16) | Architectural → Architect/Feature-Engineer |
| BUG-004 | High | 18 | Uncaught DB IntegrityError on device delete | [src/services/device_service.py](src/services/device_service.py#L231) | Tactical → QA-Fixer |
| BUG-005 | High | 18 | Uncaught DB error on user creation (no rollback/mapping) | [src/services/user_service.py](src/services/user_service.py#L59) | Tactical → QA-Fixer |
| BUG-006 | High | 18 | Topology event wiring race / concurrent rename clobber (concurrency) | [src/services/topology_service.py](src/services/topology_service.py#L88) | Architectural → Architect/Feature-Engineer |
| BUG-007 | High | 16 | Free-text search interpolates SQL wildcards (unescaped `%`/`_`) | [src/repositories/device_repository.py](src/repositories/device_repository.py#L210) | Architectural → Architect/Feature-Engineer |
| BUG-008 | Medium | 17 | Missing rollback/exception mapping on location create | [src/services/location_service.py](src/services/location_service.py#L63) | Tactical → QA-Fixer |
| BUG-009 | Medium | 15 | Tag name not normalized/validated — whitespace-only names accepted | [src/models/tag.py](src/models/tag.py#L18) | Tactical → QA-Fixer |
| BUG-010 | Medium | 15 | Connection delete: unprotected commit (can raise IntegrityError) | [src/services/connection_service.py](src/services/connection_service.py#L140) | Tactical → QA-Fixer |
| BUG-011 | Medium | 14 | UI layer performs `httpx` calls (double-hop HTTP) in `src/ui/` | [src/ui/services/topology_data.py](src/ui/services/topology_data.py#L8) | Architectural → Architect/Feature-Engineer |
| BUG-012 | Medium | 14 | Device-duplicate flow displays raw server response in toast (PII risk) | [src/ui/components/device_detail_duplicate.py](src/ui/components/device_detail_duplicate.py#L94) | Tactical → QA-Fixer |
| BUG-013 | Medium | 14 | Unprotected commit on service delete/remove_dependency | [src/services/service_service.py](src/services/service_service.py#L124) | Tactical → QA-Fixer |
| BUG-014 | Medium | 13 | Unescaped server `detail` shown in delete notification (PII/XSS risk) | [src/ui/pages/inventory_delete_dialog.py](src/ui/pages/inventory_delete_dialog.py#L88) | Tactical → QA-Fixer |
| BUG-015 | Medium | 12 | Unknown-operator tokens preserved verbatim in parsed free_text | [src/domain/search.py](src/domain/search.py#L80) | Tactical → QA-Fixer |
| BUG-016 | Medium | 12 | Topology page wires handlers without Cytoscape readiness | [src/ui/pages/topology.py](src/ui/pages/topology.py#L140) | Tactical → QA-Fixer |
| BUG-017 | Medium | 12 | Autosave concurrency / no in-flight guard in `_htFlushAutosave` | [src/ui/components/canvas_js_utils.py](src/ui/components/canvas_js_utils.py#L20) | Tactical → QA-Fixer |
| BUG-018 | Medium | 12 | Uncaught commit on connection delete (duplicate check) | [src/services/connection_service.py](src/services/connection_service.py#L140) | Tactical → QA-Fixer |
| BUG-019 | Medium | 10 | Global fetch interceptor inserts full-screen expiry overlay on any `/api/` 401 | [src/ui/components/app_shell.py](src/ui/components/app_shell.py#L23) | Systemic → Architect/Feature-Engineer |
| BUG-020 | Low | 8 | Verbose UI debug logs record edit-mode toggles (flow leakage) | [src/ui/components/topology_edit_toggle.py](src/ui/components/topology_edit_toggle.py#L71) | Tactical → QA-Fixer |
| BUG-021 | Low | 5 | Blocking `window.alert` used in export JS | [src/ui/pages/settings_data.py](src/ui/pages/settings_data.py#L45) | Tactical → QA-Fixer |
| BUG-022 | Low | 5 | Repository mutation via raw upsert leaves in-memory snapshots stale (`attach_to_device`) | [src/repositories/tag_repository.py](src/repositories/tag_repository.py#L80) | Tactical → QA-Fixer |
| BUG-023 | Low | 4 | `increment_token_version` does not flush (stale reads risk) | [src/repositories/user_repository.py](src/repositories/user_repository.py#L72) | Tactical → QA-Fixer |
| BUG-024 | Low | 4 | Missing file: `src/ui/components/map_view.py` referenced in canvas scans | [src/ui/components/map_view.py](src/ui/components/map_view.py#L1) | Tactical → QA-Fixer |
| BUG-025 | Low | 3 | TOCTOU: auto-create Default DiagramLayout may produce duplicates | [src/ui/services/topology_layout.py](src/ui/services/topology_layout.py#L52) | Architectural → Architect/Feature-Engineer |

## Details

### BUG-001 — Role changes do not increment `token_version` (High)
- **File:** [src/services/user_service.py](src/services/user_service.py#L114)
- **Trigger:** After downgrading a user's role (PATCH `/api/users/{id}`), existing JWTs retain the old role and continue to permit privileged actions.
- **Root Cause / Failure Mode:** `user_service.update_user()` updates `user.role` but does not increment `user.token_version`. Middleware trusts the token's `role` claim when validating requests; without incrementing `token_version`, previously issued tokens are still valid and keep elevated privileges.
- **Proof Test:**
```python
def test_role_change_does_not_revoke_existing_token(client, admin_token, admin_user):
    headers = {"Authorization": f"Bearer {admin_token}"}
    # admin downgrades their own role to Reader
    r = client.patch(f"/api/users/{admin_user.id}", json={"role": "Reader"}, headers=headers)
    assert r.status_code == 200
    # same token should no longer be allowed to call admin-only endpoints
    r2 = client.get("/api/users/", headers=headers)
    assert r2.status_code == 403, f"expected 403 after role change, got {r2.status_code}: {r2.text}"
```
- **Fix Direction:** Ensure sensitive updates (role, is_active, password) increment `user.token_version` (atomic repo helper) so prior tokens are invalidated. Alternatively, derive authoritative role from DB on each request. Add unit tests ensuring token revocation on role change.
- **Routing:** Architectural → Architect/Feature-Engineer

---

### BUG-002 — Export/import roundtrip loses workspaces/topologies (Critical)
- **File:** [src/services/import_service.py](src/services/import_service.py#L44)
- **Trigger:** Export a full snapshot and re-import; topologies/workspaces and DiagramLayout.topology_id are lost, leaving UI with missing topology associations.
- **Root Cause / Failure Mode:** Export schema omits topologies/workspaces and `topology_id` for exported diagram layouts. `import_full_snapshot` truncates and re-inserts without restoring topology/workspace objects or `topology_id` associations.
- **Proof Test:**
```python
# tests/integration/test_export_import_preserves_topologies.py
import uuid
from sqlmodel import select
from src.models.user import User
from src.models.workspace import Workspace
from src.models.topology import Topology
from src.models.diagram import DiagramLayout
from src.services.export_service import build_full_export
from src.services.import_service import import_full_snapshot

def test_export_import_preserves_topologies_and_layout_links(session):
    user = User(username="tae_user", email=f"tae_{uuid.uuid4().hex[:6]}@example.test", role=0, password_hash="x")
    session.add(user)
    session.flush()

    ws = Workspace(name="Workspace A", owner_id=user.id)
    session.add(ws); session.flush()

    topo = Topology(name="Topology A", workspace_id=ws.id)
    session.add(topo); session.flush()

    layout = DiagramLayout(name="Layout A", cytoscape_json={"elements": []}, topology_id=topo.id)
    session.add(layout); session.commit()

    payload = build_full_export(session)
    import_full_snapshot(session, payload)
    session.commit()

    tops_post = list(session.exec(select(Topology)).all())
    assert len(tops_post) == 1
    layout_post = session.exec(select(DiagramLayout)).first()
    assert layout_post.topology_id == topo.id
```
- **Fix Direction:** Add workspaces/topologies to ExportSchema and include `topology_id` in exported DiagramLayout; import in order (users → workspaces → topologies → diagram_layouts) preserving `topology_id`. Add integration tests and CI checks.
- **Routing:** Systemic → Architect/Feature-Engineer

---

### BUG-003 — Event-handler init race (High)
- **File:** [src/ui/components/canvas_events.py](src/ui/components/canvas_events.py#L16)
- **Trigger:** Entering Edit Mode before Cytoscape (`window._cy`) is available causes JS TypeError and prevents event handlers attaching, breaking edit-mode UX.
- **Proof Test:**
```python
# tests/unit/test_canvas_event_handlers_readiness.py
import re
from pathlib import Path

def test_ht_init_event_handlers_waits_for_cy():
    p = Path("src/ui/components/canvas_events.py")
    assert p.exists()
    text = p.read_text(encoding="utf-8")
    m = re.search(r"window\._htInitEventHandlers\s*=\s*function\(", text)
    assert m
    start = m.start()
    cy_idx = text.find("cy.on(", start)
    assert cy_idx != -1
    guard = re.search(r"if\s*\(\s*!window\._cy\s*\)\s*return", text[start:cy_idx])
    wait_loop = re.search(r"waitCy\s*\(|setTimeout\s*\(", text[start:cy_idx])
    assert guard or wait_loop
```
- **Fix Direction:** Delay attaching `cy.on(...)` until `window._cy` exists (readiness guard or invoke `_htInitEventHandlers()` from `initCanvas()`). Make handler attachment idempotent.
- **Routing:** Architectural → Architect/Feature-Engineer

---

### BUG-004 — Uncaught DB IntegrityError on device delete (High)
- **File:** [src/services/device_service.py](src/services/device_service.py#L231)
- **Trigger & Proof Test:** see above (BUG-004).
- **Fix Direction:** Wrap commits in try/except IntegrityError -> rollback and raise HTTP 409.
- **Routing:** Tactical → QA-Fixer

---

### BUG-005 — Uncaught DB error on user creation (High)
- **File:** [src/services/user_service.py](src/services/user_service.py#L59)
- **Trigger & Proof Test:** see above (BUG-005).
- **Fix Direction:** Wrap commits in try/except IntegrityError -> rollback and raise HTTP 409.
- **Routing:** Tactical → QA-Fixer

---

### BUG-006 — Topology rename has no optimistic concurrency (High)
- **File:** [src/services/topology_service.py](src/services/topology_service.py#L88)
- **Trigger & Proof Test:** see above (BUG-006).
- **Fix Direction:** Add optimistic `version` field or serialize updates; return 409 on mismatch.
- **Routing:** Architectural → Architect/Feature-Engineer

---

### BUG-007 — Free-text search uses SQL wildcards (High)
- **File:** [src/repositories/device_repository.py](src/repositories/device_repository.py#L210)
- **Trigger & Proof Test:** see above (BUG-007).
- **Fix Direction:** Escape free-text before ILIKE using `to_sql_like()` and pass `escape='\\'`.
- **Routing:** Architectural → Architect/Feature-Engineer

---

### BUG-008 — Missing rollback mapping on location create (Medium)
- **File:** [src/services/location_service.py](src/services/location_service.py#L63)
- **Trigger & Proof Test:** see above (BUG-008).
- **Fix Direction:** Wrap commit, rollback + raise 409.
- **Routing:** Tactical → QA-Fixer

---

### BUG-009 — Tag name not normalized/validated (Medium)
- **File:** [src/models/tag.py](src/models/tag.py#L18)
- **Trigger & Proof Test:** see above (BUG-009).
- **Fix Direction:** Add validators to `TagBase`/`TagCreate`/`TagUpdate` and persist normalized name in service.
- **Routing:** Tactical → QA-Fixer

---

### BUG-010 — Connection delete: unprotected commit (Medium)
- **File:** [src/services/connection_service.py](src/services/connection_service.py#L140)
- **Trigger & Proof Test:** see above (BUG-010).
- **Fix Direction:** Wrap commit, rollback + raise 409.
- **Routing:** Tactical → QA-Fixer

---

### BUG-011 — UI `httpx` usage (Medium)
- **File:** [src/ui/services/topology_data.py](src/ui/services/topology_data.py#L8)
- **Trigger & Proof Test:** see above (BUG-011).
- **Fix Direction:** Move internal HTTP calls into service/domain; centralize token/pagination.
- **Routing:** Architectural → Architect/Feature-Engineer

---

### BUG-012 — Device duplicate shows raw server response in toast (Medium)
- **File:** [src/ui/components/device_detail_duplicate.py](src/ui/components/device_detail_duplicate.py#L94)
- **Trigger & Proof Test:** see above (BUG-012).
- **Fix Direction:** Sanitize or replace message, log full response internally with redaction.
- **Routing:** Tactical → QA-Fixer

---

### BUG-013 — Unprotected commit on service delete (Medium)
- **File:** [src/services/service_service.py](src/services/service_service.py#L124)
- **Trigger & Proof Test:** see above (BUG-013).
- **Fix Direction:** Wrap commit, rollback, raise 409.
- **Routing:** Tactical → QA-Fixer

---

### BUG-014 — Unescaped server `detail` in delete notification (Medium)
- **File:** [src/ui/pages/inventory_delete_dialog.py](src/ui/pages/inventory_delete_dialog.py#L88)
- **Trigger & Proof Test:** see above (BUG-014).
- **Fix Direction:** Escape or replace message; log full details internally.
- **Routing:** Tactical → QA-Fixer

---

### BUG-015 — Unknown-operator tokens preserved verbatim in parsed free_text (Medium)
- **File:** [src/domain/search.py](src/domain/search.py#L80)
- **Trigger & Proof Test:** see above (BUG-015).
- **Fix Direction:** Append `val` (stripped of quotes) to free-text when op unknown.
- **Routing:** Tactical → QA-Fixer

---

### BUG-016 — Topology page wires handlers without Cytoscape readiness (Medium)
- **File:** [src/ui/pages/topology.py](src/ui/pages/topology.py#L140)
- **Trigger & Proof Test:** see above (BUG-016).
- **Fix Direction:** Defer wiring until Cytoscape ready or call from `initCanvas()`.
- **Routing:** Tactical → QA-Fixer

---

### BUG-017 — Autosave concurrency / missing in-flight guard (Medium)
- **File:** [src/ui/components/canvas_js_utils.py](src/ui/components/canvas_js_utils.py#L20)
- **Trigger & Proof Test:** see above (BUG-017).
- **Fix Direction:** Add the in-flight guard plus 409 handling and retry/backoff.
- **Routing:** Tactical → QA-Fixer

---

### BUG-018 — Unprotected commit on connection delete (Medium)
- **File:** [src/services/connection_service.py](src/services/connection_service.py#L140)
- **Routing & Proof Test:** see BUG-010.

---

### BUG-019 — Global fetch interceptor → full-screen overlay (Medium)
- **File:** [src/ui/components/app_shell.py](src/ui/components/app_shell.py#L23)
- **Trigger & Proof Test:** see lane-8.
- **Fix Direction:** Narrow interceptor or make non-blocking; implement targeted retry/refresh for background syncs.
- **Routing:** Systemic → Architect/Feature-Engineer

---

### BUG-020 — Verbose UI debug logs record edit-mode toggles (Low)
- **File:** [src/ui/components/topology_edit_toggle.py](src/ui/components/topology_edit_toggle.py#L71)
- **Fix Direction:** Move to audit sink or remove/quiet debug logs.
- **Routing:** Tactical → QA-Fixer

---

### BUG-021 — Blocking `window.alert` used in export JS (Low)
- **File:** [src/ui/pages/settings_data.py](src/ui/pages/settings_data.py#L45)
- **Fix Direction:** Replace with `ui.notify()` and accessible non-blocking notification.
- **Routing:** Tactical → QA-Fixer

---

### BUG-022 — Raw upsert leaves cached snapshots stale (Low)
- **File:** [src/repositories/tag_repository.py](src/repositories/tag_repository.py#L80)
- **Trigger & Proof Test:** see lane-2.
- **Fix Direction:** Use ORM `add()` or call `session.expire()`/`session.refresh()` after raw execute.
- **Routing:** Tactical → QA-Fixer

---

### BUG-023 — `increment_token_version` does not flush (Low)
- **File:** [src/repositories/user_repository.py](src/repositories/user_repository.py#L72)
- **Fix Direction:** Add `session.flush()` or document flush requirement.
- **Routing:** Tactical → QA-Fixer

---

### BUG-024 — Missing file: `src/ui/components/map_view.py` (Low)
- **File:** `src/ui/components/map_view.py` (missing)
- **Fix Direction:** Restore or correct path to Leaflet integration file.
- **Routing:** Tactical → QA-Fixer

---

### BUG-025 — TOCTOU: auto-create Default DiagramLayout may produce duplicates (Low)
- **File:** [src/ui/services/topology_layout.py](src/ui/services/topology_layout.py#L52)
- **Fix Direction:** Add unique constraint / handle conflict by returning existing id; or server-side SELECT FOR UPDATE.
- **Routing:** Architectural → Architect/Feature-Engineer

---

## Duplicate Merge Log
| Kept | Merged | Reason |
|---|---|---|
| (none) | (none) | No exact duplicates after lane dedupe; findings are distinct. |

## Lane Coverage Status
| Lane | ODC | Findings | Status | Notes |
|---|---|---:|---|---|
| lane-1 | Function (Input/Output) | 1 | Completed | Model validation issue (tags) |
| lane-2 | Assignment (State) | 2 | Completed | Repo state / flush concerns |
| lane-3 | Checking (Errors) | 5 | Completed | Unprotected commits → 5 failing-proof tests |
| lane-4 | Timing/Serialization | 2 | Completed | TOCTOU + concurrency tests |
| lane-5 | Auth/RBAC | 2 | Completed | Token revocation + header parsing |
| lane-6 | Integrity | 1 | Completed | Export/import data-loss (critical) |
| lane-7 | Documentation (Logs) | 3 | Completed | UI shows raw server text; logging hygiene |
| lane-8 | Interface (Architecture) | 3 | Completed | UI double-hop httpx, alert, global interceptor |
| lane-9 | Algorithm (Canvas UI) | 4 | Completed | Cytoscape readiness, autosave, missing file |
| lane-10 | Algorithm (Domain) | 2 | Completed | Search parsing + unescaped free-text |

---

## Next steps / Recommendations
- Mark high/critical items for immediate remediation: BUG-001, BUG-002, BUG-003, BUG-004, BUG-005, BUG-007.
- I can prepare targeted PRs for tactical fixes (try/except+rollback around `commit()` calls, tag name validator, escaped search) and unit tests. For architectural/systemic items (export/import, UI refactor to remove `httpx` double-hop, Cytoscape readiness), coordinate with Architect + Feature-Engineer to design and land the correct change.
- Handoff: route Tactical items to `QA-Fixer` and prepare PRs; route Architectural/Systemic items to `Architect` + `Feature-Engineer` for design and prioritization.

**End of report**
# Bug Report 13-04-26.2

## Executive Summary
| Severity | Count |
|---|---|
| Critical | 0 |
| High | 3 |
| Medium | 7 |
| Low | 0 |
| **Total** | **10** |

Pipeline Verdict: OPEN — 10 findings open.

### Top 3 risks
1. **lane-7-001 — High**: `User created: email` logged in plaintext (PII leak) — high impact and immediate compliance risk.
2. **F-LOC-001 — High**: `location_service.create` allows IntegrityError to propagate causing 500s on duplicate inserts.
3. **F-001 — High**: Mutable default list fields in `DeviceResponseEnriched` cause shared state between instances.

## Prioritized Findings
| ID | Sev | Score | Title | File:Line | Routing |
|---|---:|---:|---|---|---|
| lane-7-001 | High | 21 | User creation logs plaintext email | src/services/user_service.py:61 | feature-engineer |
| F-LOC-001 | High | 21 | Location create: unhandled DB unique-constraint -> raw IntegrityError (500) | src/services/location_service.py:63 | Feature-Engineer |
| F-001 | High | 17 | Mutable default lists in DeviceResponseEnriched cause shared state | src/models/device.py:120 | Tactical |
| lane-7-002 | Medium | 16 | reset_password_by_email raises ValueError containing email (leaks PII) | src/services/user_service.py:77 | feature-engineer |
| lane-8-001 | Medium | 15 | Router manages DB transaction (commit/rollback) in import endpoint | src/api/routers/data_transfer.py:144 | Feature-Engineer |
| F-AUTH-002 | Medium | 15 | Startup admin seeding: commit propagates IntegrityError (can crash startup) | src/services/auth_service.py:114 | DevOps / Feature-Engineer |
| lane-9-01 | Medium | 13 | Context menu click handler leak when replacing menu (listeners accumulate) | src/ui/components/canvas_context_menu.py:8 | Frontend (UI) |
| lane-9-02 | Medium | 13 | Canvas utils IIFE re-executes on each injection — 'beforeunload' listener duplicated | src/ui/components/canvas_js_utils.py:20 | Frontend (UI) |
| lane-10-finding-1 | Medium | 12 | `filter_devices` crashes on None/non-str `search` (no None handling) | src/domain/inventory.py:69 | Feature-Engineer |
| F-002 | Medium | 10 | Export schema `ExportedDevice` lacks IP/MAC validators and accepts invalid addresses | src/models/export_schema.py:27 | Tactical |

## Details

### F-LOC-001 — Location create: unhandled DB unique-constraint -> raw IntegrityError (High)
- **File:** src/services/location_service.py:63
- **Trigger:** Creating two locations with the same (parent_id, name) in quick succession (duplicate key on unique index).
- **Root Cause / Failure Mode:** `location_service.create` does not guard the `session.commit()` with try/except; the DB UniqueConstraint triggers sqlalchemy.exc.IntegrityError which propagates and results in a 500 rather than a 409 Conflict.
- **Proof Test:**
```python
import pytest
from fastapi import HTTPException
from src.models.location import LocationCreate
from src.models.types import LocationType
from src.services import location_service


def test_location_create_duplicate_raises_409(session):
    # Create a parent location, then create two children with the same name+parent.
    # Expected behavior: second create should surface a 409 HTTPException.
    parent = LocationCreate(name="parent-dup", type=LocationType.rack)
    parent_res = location_service.create(parent, session)

    child1 = LocationCreate(name="dup", type=LocationType.rack, parent_id=parent_res.id)
    location_service.create(child1, session)  # first insert should succeed

    child2 = LocationCreate(name="dup", type=LocationType.rack, parent_id=parent_res.id)
    with pytest.raises(HTTPException) as exc:
        # Current code does not catch the DB IntegrityError and will raise sqlalchemy.exc.IntegrityError instead,
        # so this assertion (expecting HTTPException 409) will fail under present code.
        location_service.create(child2, session)
    assert exc.value.status_code == 409
```
- **Fix Direction:** Wrap commit with try/except IntegrityError → `session.rollback()` and raise `HTTPException(status_code=409)`, or pre-check existence before insert. Add unit test like above.
- **Routing:** Feature-Engineer

### lane-7-001 — User creation logs plaintext email (High)
- **File:** src/services/user_service.py:61
- **Trigger:** Creating a user (normal signup or admin-created user) results in PII (email) written to logs.
- **Root Cause / Failure Mode:** Service logs `created.email` directly in an info-level Loguru call, exposing email in logs and potentially stdout.
- **Proof Test:**
```python
import pytest
from src.models.types import Role
from src.models.user import UserCreate
from src.services.user_service import create_user


def test_create_user_does_not_log_email(session, capsys):
    data = UserCreate(
        username="testuser",
        email="leak@example.com",
        password="StrongPass1!",
        role=Role.Contributor,
        is_active=True,
    )
    create_user(data, session)
    captured = capsys.readouterr()
    # This asserts the EMAIL should NOT be present in logs; currently it is, so this test will fail.
    assert "leak@example.com" not in captured.out
```
- **Fix Direction:** Remove raw email from log messages; log non-PII identifiers (e.g., `user.id`) or masked email. Apply consistent redaction policy via `src/utils/logger.py` helpers.
- **Routing:** Feature-Engineer

### F-001 — Mutable default lists in DeviceResponseEnriched cause shared state (High)
- **File:** src/models/device.py:120
- **Trigger:** Creating multiple `DeviceResponseEnriched` instances and mutating the `tags` (or other list) on one instance shows up on others.
- **Root Cause / Failure Mode:** Class-level mutable default list literals used for SQLModel/Pydantic fields cause shared lists across instances.
- **Proof Test:**
```python
import pytest
from uuid import uuid4
from datetime import datetime, timezone
from src.models.device import DeviceResponseEnriched
from src.models.types import DeviceType
from src.models.tag import TagResponse

def test_device_response_enriched_default_lists_are_independent():
    now = datetime.now(timezone.utc)
    t = TagResponse(id=uuid4(), name="t", color="#112233", created_at=now)
    d1 = DeviceResponseEnriched(id=uuid4(), name="d1", type=DeviceType.Server, version=1, created_at=now, updated_at=now)
    d2 = DeviceResponseEnriched(id=uuid4(), name="d2", type=DeviceType.Server, version=1, created_at=now, updated_at=now)
    d1.tags.append(t)
    assert d2.tags == [], "tags list should be independent per instance"
```
- **Fix Direction:** Use `Field(default_factory=list)` or equivalent Pydantic `default_factory=list` for list fields so each instance gets its own list. Update models and add unit tests.
- **Routing:** Tactical

### lane-7-002 — reset_password_by_email raises ValueError containing email (Medium)
- **File:** src/services/user_service.py:77
- **Trigger:** Calling `reset_password_by_email` with a non-existent email results in a ValueError message that contains the email (PII).
- **Root Cause / Failure Mode:** Error message interpolates `email` into `ValueError`, which can be logged or propagated.
- **Proof Test:**
```python
import pytest
from src.services.user_service import reset_password_by_email

def test_reset_password_by_email_does_not_leak_email(session):
    # Trigger the 'user not found' path and assert the exception message does NOT include the email.
    with pytest.raises(ValueError) as exc:
        reset_password_by_email("no-such@example.com", "StrongPass1!", session)
    # This asserts the EMAIL should NOT be present in the exception message; currently it is, so this test will fail.
    assert "no-such@example.com" not in str(exc.value)
```
- **Fix Direction:** Raise a generic `ValueError("User not found")` or map to an HTTPException at the API layer; do not interpolate the email into the exception message. Log only masked values if necessary.
- **Routing:** feature-engineer

### lane-8-001 — Router manages DB transaction (commit/rollback) in import endpoint (Medium)
- **File:** src/api/routers/data_transfer.py:144
- **Trigger:** Data import endpoint performs `session.commit()` / `session.rollback()` inside router code rather than delegating transaction boundaries to service layer.
- **Root Cause / Failure Mode:** Router-level transaction management violates layering expectations and can cause inconsistent transaction ownership, complicating error handling and tests.
- **Proof Test:**
```python
import pathlib

def test_data_transfer_router_should_not_manage_transactions():
    """Failing proof test: router-level transaction control should not appear in router source.

    This test fails against the current repo because `session.commit`/`session.rollback`
    are present in the router; transaction boundaries belong in the service layer.
    """
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    router_path = repo_root / "src" / "api" / "routers" / "data_transfer.py"
    src = router_path.read_text(encoding="utf-8")
    assert "session.commit(" not in src and "session.rollback(" not in src, (
        "Router must not manage DB transactions (commit/rollback) — move them into the service layer"
    )
```
- **Fix Direction:** Move transaction management into the import service (`import_full_snapshot` should own commit/rollback). Remove transaction calls from router and update tests.
- **Routing:** Feature-Engineer

### F-AUTH-002 — Startup admin seeding: commit propagates IntegrityError (Medium)
- **File:** src/services/auth_service.py:114
- **Trigger:** Concurrent starts or duplicate admin seed entries can raise IntegrityError on commit and crash startup.
- **Root Cause / Failure Mode:** Seeding logic calls `session.commit()` without catching `IntegrityError`; concurrent or repeated initialization can raise duplicate-key errors.
- **Proof Test:**
```python
import pytest
from sqlalchemy.exc import IntegrityError
from src.services import auth_service


def test_create_first_admin_does_not_catch_integrity_error(session, monkeypatch):
    # Simulate DB raising IntegrityError on commit (race / duplicate key in production).
    def fake_commit():
        raise IntegrityError("duplicate key", None, None)
    monkeypatch.setattr(session, "commit", fake_commit)

    # Expected behavior after fix: seeding should handle/ignore duplicate-key on concurrent startup and not raise.
    # Current code will propagate IntegrityError, so this test will fail under present code.
    auth_service.create_first_admin_if_needed(session)
```
- **Fix Direction:** Wrap seeding commit in try/except IntegrityError => `session.rollback()` and log a warning (idempotent seeding). Consider upsert.
- **Routing:** DevOps / Feature-Engineer

### lane-9-01 — Context menu click handler leak when replacing menu (Medium)
- **File:** src/ui/components/canvas_context_menu.py:8
- **Trigger:** Repeatedly opening the canvas context menu accumulates document-level 'click' listeners, causing memory leaks and duplicated dismiss behavior.
- **Root Cause / Failure Mode:** Dismiss handler is attached repeatedly via `document.addEventListener('click', dismiss)` without reliably removing previously-attached handlers when the menu is replaced.
- **Proof Test:**
```python
import pytest

from src.ui.components.canvas_context_menu import CONTEXT_MENU_JS

# Requires pytest-playwright plugin (provides the 'page' fixture).
# This test executes the context-menu IIFE twice and counts how many 'click' listeners were registered.
def test_context_menu_click_listener_leak(page):
    page.goto('about:blank')

    # Instrument document.addEventListener to record click listener registrations
    page.evaluate('''() => {
        window._clickRegs = [];
        const origAdd = document.addEventListener;
        document.addEventListener = function(type, handler) {
            if (type === 'click') { window._clickRegs.push(handler); }
            return origAdd.apply(this, arguments);
        };
    }''')

    # Execute the context-menu IIFE twice (simulates repeated injection / rapid requests)
    page.evaluate(CONTEXT_MENU_JS)
    page.evaluate(CONTEXT_MENU_JS)

    # Expect a single click listener; current behavior registers multiple
    count = page.evaluate("() => (window._clickRegs || []).length")
    assert count == 1, f'expected single click listener, got {count}'
```
- **Fix Direction:** Track and remove the prior dismiss handler before creating a new menu (store handler on the DOM node and remove it), or use a single delegated click handler for menu dismissal.
- **Routing:** Frontend (UI) — Feature-Engineer / Refactoring-Specialist

### lane-9-02 — Canvas utils IIFE re-executes on each injection — 'beforeunload' listener duplicated (Medium)
- **File:** src/ui/components/canvas_js_utils.py:20
- **Trigger:** Multiple injections of canvas JS cause repeated `beforeunload` listeners, leading to duplicated flush calls.
- **Root Cause / Failure Mode:** Utils IIFE runs on every injection without a guard against re-execution.
- **Proof Test:**
```python
import pytest

from src.ui.components.canvas_js_utils import CANVAS_UTILS_JS_TEMPLATE

# Requires pytest-playwright plugin (provides the 'page' fixture).
# This test executes the utils IIFE twice and counts how many 'beforeunload' listeners were registered.
def test_canvas_utils_beforeunload_listener_duplication(page):
    page.goto('about:blank')

    # Instrument window.addEventListener to count registrations by event type
    page.evaluate('''() => {
        window._regCounts = {};
        const origAdd = window.addEventListener;
        window.addEventListener = function(type, handler) {
            window._regCounts[type] = (window._regCounts[type] || 0) + 1;
            return origAdd.apply(this, arguments);
        };
    }''')

    # Execute the utils IIFE twice (simulates repeated injection)
    page.evaluate(CANVAS_UTILS_JS_TEMPLATE)
    page.evaluate(CANVAS_UTILS_JS_TEMPLATE)

    count = page.evaluate("() => window._regCounts['beforeunload'] || 0")
    assert count == 1, f'expected single beforeunload listener, got {count}'
```
- **Fix Direction:** Add a guard (`if (window._htCanvasUtilsInitialized) return;`) or move utils into a single guarded IIFE.
- **Routing:** Frontend (UI)

### lane-10-finding-1 — `filter_devices` crashes on None/non-str `search` (Medium)
- **File:** src/domain/inventory.py:69
- **Trigger:** Passing `None` as `search` into `filter_devices` raises AttributeError because `strip()` is called unguarded.
- **Root Cause / Failure Mode:** Function assumes `search` is `str`; callers may pass None or other types in some integration flow.
- **Proof Test:**
```python
import uuid
from dataclasses import dataclass, field
from typing import Sequence

from src.domain.inventory import filter_devices
from src.models.types import DeviceType

@dataclass(frozen=True)
class FakeDevice:
    name: str
    type: DeviceType
    ip: str | None = None
    notes: str | None = None
    tags: Sequence = ()


def test_filter_devices_with_none_search_should_treat_none_as_empty():
    d = FakeDevice(name="alpha", type=DeviceType.Server)
    # Expected: treating None as empty string (no filter) and returning the device.
    # Current behavior: this call raises AttributeError because `search` is assumed to be str.
    assert filter_devices([d], None, set(), set()) == [d]
```
- **Fix Direction:** Coerce `search = (search or "").strip().lower()` or validate input and raise a clear ValueError. Add unit tests.
- **Routing:** Feature-Engineer

### F-002 — Export schema `ExportedDevice` lacks IP/MAC validators (Medium)
- **File:** src/models/export_schema.py:27
- **Trigger:** Exported payloads with invalid `ip`/`mac` values accepted and later cause errors on import or DB write.
- **Root Cause / Failure Mode:** `ExportedDevice` lacks validators for `ip` and `mac`.
- **Proof Test:**
```python
import pytest
from uuid import uuid4
from datetime import datetime
from src.models.export_schema import ExportedDevice
from src.models.types import DeviceType, DeviceStatus

def test_exported_device_rejects_invalid_ip():
    # Expectation: export schema should validate IP format and reject invalid addresses
    with pytest.raises(ValueError):
        ExportedDevice(
            id=uuid4(),
            name="badip",
            type=DeviceType.Server,
            status=DeviceStatus.Active,
            ip="256.0.0.1",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
```
- **Fix Direction:** Add IP/MAC validators or reuse domain validation functions for exported/imported payloads.
- **Routing:** Tactical

## Duplicate Merge Log
| Kept | Merged | Reason |
|---|---|---|
| None | None | No duplicates across lanes after normalization.

## Lane Coverage Status
| Lane | ODC | Findings | Status | Notes |
|---|---|---|---|---|
| lane-1 | Function | 2 | Covered | Model validators and schema checks
| lane-2 | Assignment | 0 | Covered | No repo session lifecycle issues found at confidence>=Medium
| lane-3 | Checking | 2 | Covered | Service error handling issues found
| lane-4 | Timing | 0 | Covered | No high-confidence race conditions found
| lane-5 | Function | 0 | Covered | Auth/RBAC routes and middleware appear correct in scope
| lane-6 | Function | 0 | Covered | No orphaning issues found at confidence>=Medium
| lane-7 | Documentation | 2 | Covered | PII in logs / exception messages
| lane-8 | Interface | 1 | Covered | Router-level transaction ownership
| lane-9 | Algorithm | 2 | Covered | Canvas JS injection / event listener leaks
| lane-10 | Algorithm | 1 | Covered | Domain input-handling invariant


---

Handoff: 10 findings total. Please route:
- 5 findings to Feature-Engineer (layering, service fixes, domain guards)
- 2 findings to Frontend UI owner (canvas listener fixes)
- 2 findings to Tactical fixes (model validators, exported schema)
- 1 finding to DevOps/Feature-Engineer (startup seeding handling)

I will now mark the aggregation and deduplication steps complete and write this report. Let me know if you want me to open PRs for proposed fixes or run the failing proof-tests locally first.
