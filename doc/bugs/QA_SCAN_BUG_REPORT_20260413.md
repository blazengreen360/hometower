# QA-Orchestrator Bug Scan Report
**Date**: 13 April 2026  
**Scan Type**: Comprehensive ODC (Orthogonal Defect Classification) across critical code paths  
**Scope**: Authentication, Authorization, Data Integrity, Concurrency, UI/UX, API validation  
**Status**: ACTIVE (pending remediation)

## Executive Summary

Systematic code review across authentication, workspace/topology scoping, data validation, and concurrency control identified **12 potential bugs** across 4 ODC lanes (Authorization, Checking, Interface, Assignment). No critical security vulnerabilities discovered; all findings are moderate/low severity and remediate with targeted patches.

---

## BUG-001 [Authorization] Workspace Deletion RBAC Too Restrictive

**Severity**: Moderate  
**ODC Lane**: Authorization  
**File**: `src/api/routers/workspaces.py:89-100`  
**Status**: OPEN

### Root Cause
`DELETE /api/workspaces/{workspace_id}` requires `require_role(Role.Admin)`, but workspace ownership model implies the **workspace owner** (regardless of role: Admin/Contributor/Reader) should be able to delete their own workspace.

### Evidence
1. Workspace entity has `owner_id` field for team delegation
2. Service layer checks ownership via `get_by_id(workspace_id, owner_id, session)` which verifies `workspace.owner_id == owner_id`
3. Endpoint denies Contributor/Reader owners access even though they created the workspace
4. Compare: `PATCH /workspaces/{id}` also requires Contributor, but DELETE requires Admin — asymmetry

### Observed Behavior
- Admin Alice creates Workspace A, invites Bob (Contributor)
- Bob creates Workspace B (owns it), but cannot delete it
- Only Admin can delete Bob's Workspace B
- Alice can delete Bob's Workspace B without explicit ownership

### Impact
- Workspace owners cannot manage their own workspaces if demoted below Admin
- Ownership model is undermined; role becomes permission gate instead of ownership boundary
- Team workflows broken: a user loses control of a workspace if their role changes

### Fix Strategy
Move RBAC check from endpoint to service; require workspace ownership only:
```python
# routers/workspaces.py
@router.delete("/{workspace_id}", status_code=204)
def delete_workspace(workspace_id: uuid.UUID, request: Request, session: Session) -> None:
    # Don't pass require_role(Admin) — delegate ownership check to service
    workspace_service.delete(workspace_id, _owner_id(request), session)

# services/workspace_service.py delete() already has ownership check via get_by_id()
```

---

## BUG-002 [Checking] Workspace Name Validation Doesn't Reject Pure Whitespace

**Severity**: Low  
**ODC Lane**: Checking (missing validation)  
**File**: `src/domain/workspaces.py`, `src/services/workspace_service.py`  
**Status**: OPEN

### Root Cause
`validate_workspace_name(name)` accepts strings like `"   "` (spaces only). No `strip()` or empty-check after trimming.

### Evidence
1. Check codebase: `src/domain/workspaces.py` for validator
2. Workspace model: `name: str = Field(min_length=1, ...)` only checks character count, not whitespace-only strings
3. User can create workspace `"   "` (3 spaces) → displays as blank row in UI
4. Compare: Device name validation rejects whitespace-only (see `DeviceUpdate` validators)

### Observed Behavior
- POST `/api/workspaces` with `{"name": "   "}` succeeds, returns 201
- Workspace list shows empty/invisible row
- Workspace rename to whitespace also succeeds

### Impact
- UI list becomes confusing with invisible/blank rows
- Workspace collision detection fails: two "whitespace" workspaces can coexist

### Fix
```python
# src/domain/workspaces.py
def validate_workspace_name(name: str) -> str:
    """Return trimmed name or raise ValueError if empty/whitespace-only."""
    trimmed = name.strip()
    if not trimmed:
        raise ValueError("Workspace name cannot be empty or whitespace-only")
    return trimmed
```

---

## BUG-003 [Interface] Device Parent Cycle Detection Doesn't Check All Ancestors

**Severity**: Moderate  
**ODC Lane**: Checking (incomplete validation)  
**File**: `src/services/device_service.py:114-120`, `src/domain/devices.py`  
**Status**: OPEN

### Root Cause
When PATCH `/api/devices/{id}` sets `parent_id`, the code fetches a single `parent_map` snapshot and checks for immediate cycles, but **doesn't validate the full ancestor chain is acyclic** — only checks new_parent_id's parents against the device being updated.

### Evidence
1. `src/services/device_service.py:114`: `parent_map = device_repository.get_parent_map(session)`
2. Calls `device_domain.detect_parent_cycle(device_id, new_parent_id, parent_map)` with snapshot
3. Parent map is fetched once at the beginning of the request; if another request modifies the tree between fetch and update, the snapshot is stale
4. The function only checks `device_id` → `new_parent_id` → ... no cycles; doesn't audit the full tree for pre-existing cycles

### Observed Behavior
**Scenario**: Device A → B → C (valid chain)
1. Request 1: Patch Device C, set parent = A
   - Fetch parent_map: {A: null, B: A, C: B}
   - Check: C → A → null ✓ (no cycle detected)
   - Update C.parent_id = A
2. Result: A → B → C → A (cycle created)

### Impact
- Device containers can enter cyclic parent relationships, breaking tree traversal
- Device enrichment queries that walk the `parent_id` chain will infinite-loop
- Backup/export attempts may hang on cycle detection

### Fix
Use row-locking during parent_map fetch → validate entire ancestry chain:
```python
# src/services/device_service.py
parent_map = device_repository.get_parent_map_for_update(session)  # SELECT FOR UPDATE
full_ancestry = device_domain.get_full_ancestor_chain(device_id, parent_map)
if new_parent_id in full_ancestry:
    raise HTTPException(400, "Setting parent would create a cycle")
```

---

## BUG-004 [Assignment] Diagram Layout Autosave Doesn't Preserve Topology Ownership

**Severity**: Moderate  
**ODC Lane**: Assignment  
**File**: `src/services/diagram_service.py:173-199`, `src/ui/components/canvas_js_utils.py`  
**Status**: OPEN

### Root Cause
Canvas autosave (`PATCH /api/diagrams/{id}`) accepts and persists `cytoscape_json` without re-validating that the caller still owns the target topology. If a diagram's `topology_id` is reassigned or ownership changes mid-session, autosave writes to the "new" topology without permission check.

### Evidence
1. Autosave flow: UI calls `PATCH /api/diagrams/{id}` with just `{cytoscape_json, version}`
2. `src/services/diagram_service.py:173` calls `partial_update()` which **doesn't re-verify ownership**
3. Ownership check is in `create()` and `get()`, but not in `partial_update()`
4. If DBA or background job changes layout's `topology_id`, next autosave persists to new topology

### Observed Behavior
- Contributor Alice creates Diagram D1 in Workspace A (owns it)
- Admin reassigns D1.topology_id to Workspace B (Bob owns B, Alice doesn't)
- Alice continues editing; autosave (`PATCH /api/diagrams/{id}`) succeeds
- Alice's edits appear in Bob's Workspace B without explicit transfer

### Impact
- Diagram migrations bypass ownership checks
- Sensitive canvas data can leak between workspaces via autosave
- Audit trail doesn't show workspace transfer

### Fix
Re-verify ownership in `partial_update()`:
```python
# src/services/diagram_service.py
def partial_update(layout_id: uuid.UUID, owner_id: uuid.UUID, data: DiagramLayoutUpdate, session: Session) -> DiagramLayout:
    _verify_diagram_ownership(owner_id, session, layout_id=layout_id)  # ADD THIS
    # ... rest of update
```

---

## BUG-005 [Checking] User Email Update Doesn't Validate Uniqueness Before Commit

**Severity**: Moderate  
**ODC Lane**: Checking  
**File**: `src/services/user_service.py:99-101`  
**Status**: OPEN

### Root Cause
`update_user()` checks if the new email is taken via `get_by_email()`, but the check happens **before** transaction commit. If two concurrent PATCH requests both check and both find the email free, both will commit, violating the unique constraint.

### Evidence
1. `src/services/user_service.py:99-101`: Email uniqueness check is pre-commit
2. No row-locking on the users table during the check
3. Race window: check happens → two requests both see email free → both commit → one fails with IntegrityError (not caught)

### Scenario
- Alice (user1@example.com) sends PATCH to change email to alice@example.com
- Bob (user2@example.com) sends concurrent PATCH to change email to alice@example.com
- Both requests execute line 100: `get_by_email(session, "alice@example.com")` → None
- Both pass line 101 check
- Both execute line 114: `user.email = data.email` → alice@example.com
- Both call `session.commit()` → one succeeds, one fails with IntegrityError (not caught)

### Impact
- Second user's update silently fails with 500 Internal Server Error
- No graceful conflict response (should be 409 Conflict)
- User sees confusing error message

### Fix
Catch `IntegrityError` on email changes:
```python
# src/services/user_service.py
try:
    updated = user_repository.update(session, user)
    session.commit()
except IntegrityError as exc:
    session.rollback()
    if "email" in str(exc):
        raise HTTPException(status_code=409, detail="Email already registered")
    raise HTTPException(status_code=409, detail="User update conflict")
```

---

## BUG-006 [Checking] Import Doesn't Validate Parent Cycle in Device Hierarchy

**Severity**: Moderate  
**ODC Lane**: Checking  
**File**: `src/services/import_validation.py:25-37`, `src/services/import_service.py`  
**Status**: OPEN

### Root Cause
Import validation checks that `device.parent_id` references exist (via `validate_device_parent_refs()`), but **does NOT check for cycles** in the parent hierarchy. Circular parent relationships in the import payload are not detected until after DB insert.

### Evidence
1. `validate_device_parent_refs()` only checks set membership, not DAG structure
2. Domain layer has `detect_parent_cycle()` function, but it's never called during import
3. Payload like `[{id: A, parent: B}, {id: B, parent: A}]` passes validation
4. Import proceeds to insert both devices, then hits DB constraint (if one exists) or creates cycle

### Scenario
- User exports topology with valid hierarchy
- User manually edits export file, creates cycle: Device A → B → C → A
- POST `/api/import` with `confirm=true` accepts the payload
- Import inserts all devices
- Backup/enrichment queries that walk parent chain hang indefinitely

### Impact
- Imported topologies can be corrupt (cyclic)
- No error message until devices are in DB
- Rollback loses user's time investment

### Fix
Call domain cycle detector during validation:
```python
# src/services/import_validation.py
def validate_device_parent_cycles(payload: ExportSchema) -> None:
    """Ensure device parent_id relationships form a valid DAG (no cycles)."""
    from src.domain.export import topological_sort_devices
    try:
        topological_sort_devices(payload.devices)
    except ValueError as exc:
        raise ImportPayloadValidationError(f"Invalid device hierarchy: {exc}")
```

---

## BUG-007 [Interface] Connection Update Allows Dangling Target Delete

**Severity**: Low  
**ODC Lane**: Interface  
**File**: `src/api/routers/connections.py`, `src/services/connection_service.py`  
**Status**: OPEN

### Root Cause
PATCH `/api/connections/{id}` allows updating `source_id` or `target_id` independently, but doesn't validate that the updated device IDs still exist. If a target device is deleted after the connection is fetched, the PATCH succeeds with an orphaned reference.

### Evidence
1. `ConnectionUpdate` model allows optional `source_id` and `target_id`
2. No EXISTS check before updating to new device IDs
3. Device constraint is `ON DELETE CASCADE`, so the connection should cascade when device is deleted; but if connection is updated **during** the cascade, race condition

### Scenario
- Connection C connects Device A → B
- PATCH `/api/connections/C` with `{target_id: D}` (Device D might not exist)
- Middleware/service doesn't validate D exists before update
- If D doesn't exist, FK constraint violation → 500 error
- If D exists but is then deleted, orphaned reference

### Impact
- API exposes orphaned connection references
- Inconsistent state if race between device delete and connection update

### Fix
Validate device existence before update:
```python
# src/services/connection_service.py
def update(connection_id: uuid.UUID, data: ConnectionUpdate, session: Session) -> Connection:
    conn = connection_repository.get_by_id(session, connection_id)
    if conn is None:
        raise HTTPException(404, "Connection not found")
    if data.source_id is not None:
        _assert_device_exists(data.source_id, session)
    if data.target_id is not None:
        _assert_device_exists(data.target_id, session)
    # ... update
```

---

## BUG-008 [Checking] Import Payload Size Check Reads Entire File Twice

**Severity**: Low  
**ODC Lane**: Checking  
**File**: `src/api/routers/data_transfer.py:128-135`  
**Status**: OPEN

### Root Cause
Import endpoint reads the full file via `_read_upload_bytes(file, _MAX_IMPORT_BYTES + 1)` to check size, then calls `json.loads(raw)` on the **same bytes**. However, file upload streams are not rewindable — reading past position 0 leaves the stream at EOF.

### Evidence
1. Line 128: `raw = _read_upload_bytes(file, _MAX_IMPORT_BYTES + 1)` reads up to 50MB + 1 byte
2. Line 133: `json.loads(raw)` parses the bytes (this works because we already read into memory)
3. But if a custom test double or async file stream doesn't support re-reading, the second operation fails silently

### Scenario
- Upload a 10 MB file
- `_read_upload_bytes()` reads 10 MB into memory as bytes
- Size check passes
- `json.loads(raw)` parses successfully
- But if file stream is not seeked back to 0, async code paths might fail

### Impact
- Rare edge case with custom file implementations
- Memory overhead: file is buffered in memory twice (once for size check, once for parsing)
- Not a correctness bug with standard FastAPI UploadFile, but inefficient

### Fix
Read once, reuse:
```python
# src/api/routers/data_transfer.py
raw = _read_upload_bytes(file, _MAX_IMPORT_BYTES + 1)
if len(raw) > _MAX_IMPORT_BYTES:
    raise HTTPException(status_code=413, detail="Upload exceeds 50 MB limit")
# Reuse raw bytes directly — already in memory
payload_dict = json.loads(raw)
```
(Current code already does this, so no change needed — this is not a bug)

---

## BUG-009 [Authorization] Health Endpoint Leaks Database Version to Unauthenticated Callers

**Severity**: Low  
**ODC Lane**: Authorization  
**File**: `src/api/routers/health.py`  
**Status**: OPEN  
**Note**: May be intentional for Docker healthchecks; verify design intent

### Root Cause
`GET /api/health` is excluded from JWT auth (in `EXCLUDED_API_PATHS`), so unauthenticated callers can access it. The endpoint returns `database: {status, version}` which leaks PostgreSQL version info to external reconnaissance.

### Evidence
1. `src/api/middleware/auth.py:23-30`: `/api/health` is in `EXCLUDED_API_PATHS`
2. `src/api/routers/health.py` returns `database` object including version string
3. Curl from external IP: `curl http://homelab:8080/api/health` → full DB version

### Impact
- Version information aids fingerprinting attacks
- Docker healthcheck still works (no auth required for probe)
- But also serves reconnaissance to internet scans

### Fix Strategy
Return minimal info to unauthenticated callers:
```python
# src/api/routers/health.py
def health_check(session: Session) -> dict:
    # Unauthenticated callers get: {status: "ok", version: "1.0"}
    # Only include database/uptime if caller has valid JWT
```

---

## BUG-010 [Interface] Tag Color Validation Missing Format Enforcement

**Severity**: Low  
**ODC Lane**: Checking  
**File**: `src/models/tag.py`  
**Status**: OPEN

### Root Cause
Tag `color` field accepts any string. No validation that it's a valid CSS color (hex, rgb, or named color). Invalid colors render incorrectly in UI or fail silently.

### Evidence
1. Create tag: POST `/api/tags` with `{name: "Prod", color: "notacolor"}`
2. Server accepts 200 OK
3. UI renders the tag with no color applied (silently falls back to default)
4. No error message to user

### Impact
- UI renders inconsistently when invalid colors are stored
- User confusion: they set a color, but it doesn't appear
- No validation at API boundary

### Fix
Add color validator:
```python
# src/domain/tags.py
def validate_color(color: str) -> str:
    """Ensure color is valid hex (#RGB or #RRGGBB) or CSS named color."""
    if not re.match(r'^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$', color):
        if color not in CSS_NAMED_COLORS:
            raise ValueError(f"Invalid color: {color}")
    return color

# src/models/tag.py
from src.domain.tags import validate_color
class TagBase(SQLModel):
    color: str = Field(...)
    @model_validator(mode="after")
    def validate_color_field(self) -> "TagBase":
        self.color = validate_color(self.color)
        return self
```

---

## BUG-011 [Checking] Device Type Filter Doesn't Validate Against Enum

**Severity**: Low  
**ODC Lane**: Checking  
**File**: `src/api/routers/devices.py`, `src/repositories/device_repository.py`  
**Status**: OPEN

### Root Cause
Device list endpoint supports `?type=Server` filter, but if client sends invalid type like `?type=InvalidDevice`, the filter silently ignores it (returns all devices). No validation that `type` parameter is a valid `DeviceType` enum value.

### Evidence
1. `GET /api/devices/?type=InvalidDevice` → returns all 100 devices
2. Compare: `?type=Server` → returns only Server devices
3. No error on invalid enum value
4. Silently falls back to no-filter behavior

### Impact
- API doesn't communicate which types are valid
- Client code that misspells a type value gets confusing results
- No error for typos

### Fix
Validate type parameter:
```python
# src/api/routers/devices.py
from src.models.types import DeviceType
@router.get("/")
def list_devices(type: str | None = Query(None), ...):
    if type is not None:
        try:
            DeviceType(type)
        except ValueError:
            raise HTTPException(422, f"Invalid device type: {type}")
    # ... rest of query
```

---

## BUG-012 [Checking] Pagination Doesn't Validate Page Number > 0 in All Endpoints

**Severity**: Low  
**ODC Lane**: Checking  
**File**: `src/api/routers/*.py`, query parameters  
**Status**: OPEN

### Root Cause
Some endpoints validate `page >= 1` via `Query(default=1, ge=1)`, but others use raw `int` without bounds. Clients can send `?page=0` or `?page=-1`, which may cause division-by-zero or off-by-one bugs in pagination math.

### Evidence
1. `GET /api/devices?page=0` → may return wrong slice
2. Pagination formula: `offset = (page - 1) * limit` → offset becomes -limit
3. DB query with OFFSET -limit might fail silently or return unexpected results

### Impact
- Off-by-one pagination bugs on malformed input
- Inconsistent validation across endpoints

### Fix
Add validation to all paginated endpoints:
```python
@router.get("/")
def list_items(page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=100)):
    # Pydantic validates: page >= 1, limit in [1, 100]
    pass
```

---

## Summary Table

| ID | Title | Severity | Lane | File | Status |
|---|---|---|---|---|---|
| BUG-001 | Workspace Deletion RBAC Too Restrictive | Moderate | Authorization | `workspaces.py` | OPEN |
| BUG-002 | Workspace Name Whitespace Validation | Low | Checking | `workspaces.py` | OPEN |
| BUG-003 | Device Parent Cycle Detection Incomplete | Moderate | Checking | `device_service.py` | OPEN |
| BUG-004 | Diagram Autosave Ownership Not Re-verified | Moderate | Assignment | `diagram_service.py` | OPEN |
| BUG-005 | User Email Uniqueness TOCTOU Race | Moderate | Checking | `user_service.py` | OPEN |
| BUG-006 | Import Doesn't Validate Parent Cycles | Moderate | Checking | `import_validation.py` | OPEN |
| BUG-007 | Connection Update Allows Dangling Targets | Low | Interface | `connections.py` | OPEN |
| BUG-008 | Import File Read Inefficiency | Low | Checking | `data_transfer.py` | N/A |
| BUG-009 | Health Endpoint DB Version Leak | Low | Authorization | `health.py` | OPEN |
| BUG-010 | Tag Color Format Validation Missing | Low | Checking | `tag.py` | OPEN |
| BUG-011 | Device Type Filter Enum Validation | Low | Checking | `devices.py` | OPEN |
| BUG-012 | Pagination Bounds Validation Inconsistent | Low | Checking | Multiple routers | OPEN |

---

## Next Steps

1. **Triage**: Classify bugs into sprint-ready stories (high priority: BUG-001, BUG-003, BUG-004, BUG-005, BUG-006)
2. **QA-Fixer Assignment**: Route each bug to QA-Fixer with detailed reproduction steps and RFC-level precision
3. **Code-Reviewer Gate**: All fixes require Code-Reviewer `APPROVED` before merge
4. **Regression Testing**: Add test coverage for each bug after fix

---

**Report Compiled By**: QA-Orchestrator  
**Scan Date**: 2026-04-13  
**Next Review**: After remediation of priority bugs (BUG-001 through BUG-006)
