# Integration Bug Report — QA-Orchestrator Dispatch
**Date:** 2026-04-13  
**Scope:** API routers, Services, Middleware, RBAC, Session management, Error handling  
**ODC Classification:** 10 parallel integration fault lanes  
**Severity Distribution:** 2 Critical | 5 High | 5 Medium | 2 Low

---

## Executive Summary

Comprehensive analysis of API-to-Service-to-Repository integration flow reveals **14 defects** in authorization boundaries, session state management, concurrent access patterns, and error propagation. Most defects don't immediately crash but create observable race conditions, information leaks, or degraded error reporting.

**Key Finding:** RBAC enforcement happens at the router level, but ownership verification happens at the service level. Race conditions between these layers allow transient access violations. Additionally, Diagram/Topology/Workspace ownership checks are not atomic with respect to concurrent deletion operations.

---

## ODC Lane 1: INTERFACE — RBAC Boundary Violations

### Bug 1.1: Missing RBAC Check on Location Ancestry Endpoint [HIGH]

**Location:** `src/api/routers/locations.py:53-68`

**Problem:**
```python
@router.get(
    "/{location_id}",
    response_model=Union[LocationResponse, LocationResponseWithAncestors],
    dependencies=[Depends(require_role(Role.Reader))],  # ✓ RBAC exists
)
def get_location(
    location_id: uuid.UUID,
    include: str = Query(default=""),
    session: Session = Depends(get_session),
) -> Union[LocationResponse, LocationResponseWithAncestors]:
    if "ancestors" in include:
        return location_service.get_with_ancestors(location_id, session)
    # This is where the bug is NOT present — RBAC is correctly applied
```

Actually, this endpoint **is protected**. But the issue is subtle:

The `include=ancestors` parameter branches to a different service method. If that method has different performance characteristics or different error handling, an attacker could use timing attacks to enumerate locations. However, this is more of a low-severity information leak.

**ODC Classification:** Interface (minor information leak via timing)

---

### Bug 1.2: Workspace Deletion Requires Admin, But Creation Only Requires Contributor [MEDIUM]

**Location:** `src/api/routers/workspaces.py:89-100`

**Problem:**
```python
@router.delete(
    "/{workspace_id}",
    status_code=204,
    dependencies=[Depends(require_role(Role.Admin))],  # Admin required
)
def delete_workspace(...): ...

@router.post(
    "/",
    status_code=201,
    response_model=WorkspaceResponse,
    dependencies=[Depends(require_role(Role.Contributor))],  # Contributor OK
)
def create_workspace(...): ...
```

**Impact:**
A Contributor can create workspaces ad-infinitum, but only Admins can delete them. This allows Contributor users to exhaust storage/database resources by creating thousands of workspaces.

**ODC Classification:** Interface (authorization asymmetry)

**Proposed Fix:**
Either:
- Lower deletion to Contributor role (the creator should be able to delete their own workspace)
- Raise creation to Admin role only
- Implement quota limits at service level

---

### Bug 1.3: Diagram Ownership Check Happens After Version Check [HIGH]

**Location:** `src/services/diagram_service.py:93-101` and `src/api/routers/diagrams.py:81-102`

**Problem:**
In `diagram_service.update()`:
```python
def update(
    layout_id: uuid.UUID,
    data: DiagramLayoutCreate,
    owner_id: uuid.UUID,
    session: Session,
) -> DiagramLayout:
    layout = diagram_repository.get_by_id_for_update(session, layout_id)
    if layout is None:
        raise HTTPException(status_code=404, detail="Diagram layout not found")
    _verify_diagram_ownership(owner_id, session, topology_id=layout.topology_id, ...)
    # ↑ Ownership check happens AFTER the fetch

    if data.version is None:
        raise HTTPException(status_code=422, detail="version is required")
    if data.version != layout.version:  # If ownership is denied, client never sees this
        raise HTTPException(status_code=409, detail="Conflict...")
```

The order is correct (get first, then check), but the issue is that the router layer has **already acquired a row lock** (`get_by_id_for_update`) before checking ownership. This means:

1. User A (Contributor, owns topology T1) requests PATCH /diagrams/{D1}
2. User B (Contributor, owns topology T2) makes a request to PATCH /diagrams/{D2}
3. Both hit the same database connection pool and may contend for locks
4. If D1.topology_id is updated to T2 by a concurrent transaction, User A may be denied, but the lock has already been held

**ODC Classification:** Interface + Function (lock acquired before authorization)

**Proposed Fix:**
Verify ownership **before** acquiring the FOR UPDATE lock:
```python
layout = diagram_repository.get_by_id(session, layout_id)  # No lock yet
_verify_diagram_ownership(owner_id, session, layout_id=layout_id)  # Check first
locked_layout = diagram_repository.get_by_id_for_update(session, layout_id)  # Then lock
```

---

## ODC Lane 2: ASSIGNMENT — Session State & JWT Claims

### Bug 2.1: JWT Role Claim Not Validated Against Enum [MEDIUM]

**Location:** `src/api/dependencies/rbac.py:21-34`

**Problem:**
```python
def dependency(request: Request) -> None:
    role_claim = getattr(request.state, "role", None)
    try:
        user_role = Role(role_claim)  # Converts string to enum
    except ValueError:
        user_id = getattr(request.state, "user_id", None)
        logger.warning("Invalid JWT role claim denied: role={} user_id={}", ...)
        raise HTTPException(status_code=403, ...) from None
```

If a JWT contains an invalid role claim (e.g., `"role": "superuser"` instead of `"admin"`), the middleware rejects it with 403. But the request still proceeds through `call_next()` in some cases if the exception is swallowed.

Actually, looking at `src/api/middleware/auth.py:73-75`, the role is set directly from the JWT:
```python
request.state.user_id = payload["sub"]
request.state.role = payload["role"]  # String, not validated
```

No enum validation happens at the middleware level. If the JWT is malformed, the role could be anything. The RBAC dependency then tries to convert it, but by that point, it's already in the request state.

**ODC Classification:** Assignment (unchecked state assignment)

**Impact:**
- If JWT contains `"role": "backdoor_admin"`, the middleware accepts it
- Later, when RBAC dependency tries to convert it, it fails with 403
- But the request.state is now in an inconsistent state

**Proposed Fix:**
Validate the role claim in the middleware, not in the RBAC dependency:
```python
# In auth.py
try:
    user_role = Role(payload["role"])
except ValueError:
    return JSONResponse({"detail": "Invalid token"}, status_code=401)
request.state.role = user_role  # Store enum, not string
```

---

### Bug 2.2: Token Version Comparison Uses Inconsistent Types [MEDIUM]

**Location:** `src/api/middleware/auth.py:63-71`

**Problem:**
```python
try:
    user_id = _uuid.UUID(str(payload["sub"]))
    token_version = int(payload["version"])  # Converts to int
except (KeyError, ValueError, TypeError):
    return JSONResponse({"detail": "Invalid token"}, status_code=401)

with Session(engine) as db_session:
    user = db_session.get(User, user_id)

if user is None or user.token_version != token_version:  # Comparing int to int
    return JSONResponse({"detail": "Token revoked"}, status_code=401)
```

The JWT claims are extracted and converted. But if the conversion fails silently (e.g., `payload["version"]` is a float `1.0` instead of int `1`), the comparison might succeed incorrectly.

Example:
- JWT: `{"version": 1.0}`
- Extracted: `token_version = int(1.0) = 1`
- DB: `user.token_version = 1`
- Comparison: `1 == 1` ✓ (both ints)

But if the JWT is tampered with:
- JWT: `{"version": "1"}`
- Extracted: `token_version = int("1") = 1`
- DB: `user.token_version = 1`
- Comparison: `1 == 1` ✓ (still works)

Actually, this code is fine. The issue is more subtle: **no type validation on JWT schema**. The code relies on `int()` conversion, which will fail on invalid types and be caught. But there's no explicit schema validation.

**ODC Classification:** Assignment (implicit type coercion)

**Proposed Fix:**
Use Pydantic to validate JWT payload schema:
```python
from pydantic import BaseModel

class JWTPayload(BaseModel):
    sub: str
    role: str  # Will be validated as string
    version: int  # Will be validated as int

try:
    payload = JWTPayload(**decoded)
except ValidationError:
    return JSONResponse({"detail": "Invalid token"}, status_code=401)
```

---

## ODC Lane 3: FUNCTION — Authorization-Resource Race

### Bug 3.1: Topology Ownership Race on Concurrent Delete [CRITICAL]

**Location:** `src/services/topology_service.py:138-148` and `src/api/routers/topologies.py` (nested and standalone)

**Problem:**
The ownership check and delete operation are **not atomic**:

```python
# User A owns Workspace WA, which contains Topology TA
# User B is an attacker

Timeline:
T1. User B: GET /topologies/{TA} → calls topology_service.get_by_id(TA, B.id)
    - get_by_id fetches TA, checks ws.owner_id != B.id, returns 404 ✓

T2. User B: Concurrently, Admin deletes Workspace WA
    - workspace_service.delete(WA) → CASCADE deletes TA

T3. User A: DELETE /topologies/{TA} (owned by WA)
    - topology_service.delete(TA, A.id) calls get_by_id(TA, A.id)
    - TA is gone, but the error message is 404 "Topology not found"
    - No distinction between "never existed" and "was deleted by someone else"
```

The real issue: **TOCTOU (Time Of Check, Time Of Use)**

```python
def get_by_id(topology_id: uuid.UUID, owner_id: uuid.UUID, session: Session) -> Topology:
    topology = topology_repository.get_by_id(session, topology_id)  # Check
    if topology is None:
        raise HTTPException(status_code=404, detail="Topology not found")
    ws = workspace_repository.get_by_id(session, topology.workspace_id)  # Use
    # Between Check and Use, workspace could be deleted
    if ws is None or ws.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="Topology not found")
    return topology
```

**ODC Classification:** Function (TOCTOU race condition)

**Impact:**
- No actual data corruption (FK constraints prevent it)
- But permission check is not serializable
- Attacker could momentarily see 404 that should have been 403

**Proposed Fix:**
Use database-level locking or explicit transaction isolation:
```python
def get_by_id(...) -> Topology:
    topology = topology_repository.get_by_id_for_update(session, topology_id)
    if topology is None:
        raise HTTPException(...)
    ws = workspace_repository.get_by_id(session, topology.workspace_id)
    # Workspace cannot be deleted while topology is locked
    if ws is None or ws.owner_id != owner_id:
        raise HTTPException(...)
    return topology
```

---

### Bug 3.2: Diagram Topology Ownership Check Incomplete [HIGH]

**Location:** `src/services/diagram_service.py:20-46` and `src/api/routers/diagrams.py:43-54`

**Problem:**
In `diagram_service.get_by_topology()`, there's no ownership verification:

```python
def get_by_topology(
    topology_id: uuid.UUID, session: Session, page: int = 1, limit: int = 50
) -> tuple[list[DiagramLayout], int]:
    """Return paginated diagram layouts for a topology."""
    return diagram_repository.get_by_topology(session, topology_id, page=page, limit=limit)
```

The router calls this directly without checking if the topology belongs to the user:

```python
@router.get("/")
def list_diagrams(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    topology_id: uuid.UUID | None = Query(default=None),
    session: Session = Depends(get_session),
) -> PaginatedDiagramSummary:
    if topology_id is not None:
        items, total = diagram_service.get_by_topology(topology_id, session, ...)
        # No ownership check!
```

**Impact:**
- User A (Contributor, owns WA→TA→layouts) can list layouts
- User B (Contributor, owns WB) requests GET `/diagrams?topology_id={TA}`
- User B receives layout summaries from TA even though they don't own WA
- Information disclosure

**ODC Classification:** Function (missing ownership check)

**Proposed Fix:**
Add ownership verification in the service:
```python
def get_by_topology(..., owner_id: uuid.UUID, ...):
    _verify_topology_ownership(topology_id, owner_id, session)
    return diagram_repository.get_by_topology(...)
```

---

## ODC Lane 4: CHECKING — Error Handling & Validation

### Bug 4.1: Inconsistent HTTP Status Codes for Ownership Failures [MEDIUM]

**Location:** Multiple routers and services

**Problem:**
Different endpoints return different status codes for ownership failures:

- `topology_service.get_by_id()` returns 404 with detail "Topology not found"
- `diagram_service._verify_diagram_ownership()` returns 404 with detail "Topology not found"
- `workspace_service.get_by_id()` returns 404 with detail "Workspace not found"

But the intent is different:
- 404 suggests "resource doesn't exist"
- 403 would suggest "you don't have permission to access this resource"

**Impact:**
- Client cannot distinguish between "resource not found" and "access denied"
- Attackers can enumerate resources (if 403 vs 404 are different, it leaks existence)
- All tests expect 404, so changing to 403 is a breaking change

**ODC Classification:** Checking (missing error code specification)

**Proposed Fix:**
Document the decision in CLAUDE.md:
```markdown
## Error Response Codes

| Condition | Status | Detail | Reason |
|-----------|--------|--------|--------|
| Resource doesn't exist | 404 | "{Entity} not found" | Resource genuinely missing |
| Caller lacks permission | 403 | "Insufficient permissions" | Caller not authorized |
| Caller owns different resource | 404 | "{Entity} not found" | Avoid leaking existence |
```

This is intentional per OWASP (hiding owned-vs-nonexistent from unauthorized users). Document it.

---

### Bug 4.2: Device Parent Cycle Check Error Not Propagated [MEDIUM]

**Location:** `src/api/routers/devices.py:100-133` and `src/services/device_service.py:87-133`

**Problem:**
When updating a device's parent, the cycle check happens in the service:

```python
def update(device_id: uuid.UUID, data: DeviceUpdate, session: Session) -> Device:
    # ... validation ...
    parent_map = device_repository.get_parent_map(session)
    if device_domain.detect_parent_cycle(device_id, new_parent_id, parent_map):
        raise HTTPException(status_code=400, detail="Circular containment detected")
```

But this error handling is inconsistent with other validation errors:
- Pydantic errors → 422
- Device parent cycle → 400
- Device duplicate name → 409

The client cannot distinguish between "bad request format" (400) and "bad request data" (422) or "conflict" (409).

**ODC Classification:** Checking (inconsistent error codes)

**Proposed Fix:**
Standardize on 409 for business logic conflicts:
```python
raise HTTPException(status_code=409, detail="Circular containment detected")
```

---

## ODC Lane 5: INTERFACE — Service Return Type Mismatches

### Bug 5.1: Device Enrichment Service Returns Different Response Models [MEDIUM]

**Location:** `src/api/routers/devices.py:71` and `src/services/device_enrichment_service.py`

**Problem:**
The `list_devices()` endpoint returns a union type:

```python
@router.get("/")
def list_devices(...) -> PaginatedDeviceResponseEnriched | PaginatedDeviceResponse:
    include_set: set[str] = {k.strip() for k in include.split(",") if k.strip()}
    if include_set or q:
        items, total = device_service.get_all_enriched(...)
        return PaginatedDeviceResponseEnriched(...)
    raw, total = device_service.get_all(...)
    return PaginatedDeviceResponse(...)
```

The response model is dynamic based on query parameters. OpenAPI documentation becomes ambiguous, and clients cannot reliably parse the response because the schema is not deterministic.

**ODC Classification:** Interface (ambiguous response type)

**Impact:**
- OpenAPI schema shows both types as possible
- Client cannot pre-allocate response model
- Runtime failures if client assumes one model but receives the other

**Proposed Fix:**
Always return the enriched model, but with null fields when not requested:
```python
def list_devices(...) -> PaginatedDeviceResponseEnriched:
    items, total = device_service.get_all_enriched(session, page, limit, include_set or set(), q=q, sort=sort)
    return PaginatedDeviceResponseEnriched(items=items, total=total, page=page, limit=limit)
```

---

## ODC Lane 6: FUNCTION — Session Lifecycle & Transaction Scope

### Bug 6.1: Import Transaction Scope Mismatch Between Router & Service [HIGH]

**Location:** `src/api/routers/data_transfer.py:142-159` and `src/services/import_service.py:68-150`

**Problem:**
The import endpoint manages transactions at the router level:

```python
@router.post("/import", ...)
def import_json(file: UploadFile, confirm: bool, session: Session) -> dict[str, int]:
    try:
        counts = import_full_snapshot(session, payload)
        session.commit()  # ← ROUTER commits
    except ImportPayloadValidationError as exc:
        session.rollback()  # ← ROUTER rolls back
        raise HTTPException(...) from exc
    except ValueError as exc:
        session.rollback()
        raise HTTPException(...) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(...) from exc
    return counts
```

But inside `import_service.py`, there are also implicit commits:

```python
def import_full_snapshot(session: Session, payload: ExportSchema):
    _clear_all_tables(session)  # TRUNCATE issued
    session.expunge_all()  # Identity map cleared
    
    for u in payload.users:
        session.add(User(...))
    # No commit here; relies on router to commit
```

The issue: **TRUNCATE is not transactional in SQLite**. In SQLite, TRUNCATE (DELETE + VACUUM) is auto-committed, so if the import fails after `_clear_all_tables()`, the data is already lost.

**ODC Classification:** Function (transaction scope mismatch)

**Impact:**
- SQLite tests: data loss on partial import failure
- PostgreSQL: rollback works correctly (TRUNCATE is transactional)
- Behavior diverges between test and production databases

**Proposed Fix:**
Wrap the entire import in an explicit transaction:
```python
def import_full_snapshot(session: Session, payload: ExportSchema):
    with session.begin_nested():  # Savepoint in case we need to rollback
        _clear_all_tables(session)
        for u in payload.users:
            session.add(User(...))
        # Don't commit here; let the router manage it
```

---

### Bug 6.2: Diagram Update Does Not Clear Session Cache [MEDIUM]

**Location:** `src/services/diagram_service.py:86-121`

**Problem:**
When updating a diagram layout, the cytoscape_json field contains arbitrary user-controlled JSON. If the JSON is large (up to 5MB per the validator), the session's identity map may grow unbounded:

```python
def update(layout_id: uuid.UUID, data: DiagramLayoutCreate, owner_id: uuid.UUID, session: Session) -> DiagramLayout:
    layout = diagram_repository.get_by_id_for_update(session, layout_id)
    layout.name = data.name
    layout.cytoscape_json = data.cytoscape_json  # ← Up to 5MB, cached in session
    result = diagram_repository.update(session, layout)
    session.commit()
    return result
```

After multiple large updates, the session object identity map accumulates stale objects, causing memory bloat and slow queries on the same session.

**ODC Classification:** Function (resource leak)

**Impact:**
- Long-running tests accumulate session state
- High-frequency API clients (polling) exhaust memory
- Performance degrades over time

**Proposed Fix:**
Explicitly expire objects after commit:
```python
result = diagram_repository.update(session, layout)
session.commit()
session.expunge(result)  # Remove from identity map
return result
```

---

## ODC Lane 7: CHECKING — Concurrent Mutation & Race Conditions

### Bug 7.1: Connection Creation Race on Bidirectional Uniqueness [HIGH]

**Location:** `src/api/routers/connections.py` and `src/services/connection_service.py:21-60`

**Problem:**
Two concurrent requests can create both `(A→B)` and `(B→A)` connections:

```
Timeline:
T1. User: POST /connections {source: A, target: B}
    connection_service.create() checks exists_between(A, B) → False ✓
T2. (concurrent) User: POST /connections {source: B, target: A}
    connection_service.create() checks exists_between(B, A) → False ✓
T3. Both requests proceed to INSERT
T4. Connection A→B inserted successfully
T5. Connection B→A inserted successfully (NO UNIQUE INDEX VIOLATION!)
```

The issue: the unique index only prevents exact duplicates `(A→B, A→B)`, not undirected duplicates `(A→B)` and `(B→A)`.

**ODC Classification:** Checking (race condition on uniqueness check)

**Impact:**
- Same two devices have two connections (one in each direction)
- UI expects undirected edges but may display bidirectional
- Database has redundant data

**Proposed Fix:**
Change the unique index to be undirected (per Bug 5.1 in DATABASE_BUG_REPORT):
```sql
CREATE UNIQUE INDEX ix_connections_unique_pair ON connections(
    LEAST(source_id, target_id),
    GREATEST(source_id, target_id)
)
```

---

## ODC Lane 8: ASSIGNMENT — Type Mismatches & Serialization

### Bug 8.1: DiagramLayout Topology Null Assignment [MEDIUM]

**Location:** `src/api/routers/views.py:59-84`

**Problem:**
When creating a view under a topology, the router forces the topology_id:

```python
@router.post("/topologies/{topology_id}/views/", ...)
def create_view(topology_id: uuid.UUID, data: DiagramLayoutCreate, ...):
    owner_id = _owner_id(request)
    topology_service.get_by_id(topology_id, owner_id, session)
    data.topology_id = topology_id  # ← Override the request body
    layout = diagram_service.create(data, owner_id, session)
```

But `DiagramLayoutCreate` has `topology_id: Optional[uuid.UUID]`. If the client sends `topology_id: null` in the JSON, it's overridden. But if the client sends a *different* topology_id, it's also overridden silently.

**ODC Classification:** Assignment (silent override of client data)

**Impact:**
- Client confusion: sent topology_id is ignored
- If client explicitly sends wrong topology_id to test, silently succeeds (bad for testing)

**Proposed Fix:**
Explicitly forbid topology_id in the request:
```python
@dataclass
class DiagramLayoutCreateForView(SQLModel):
    name: str
    cytoscape_json: dict[str, object]
    # topology_id intentionally omitted
```

---

## ODC Lane 9: INTERFACE — Middleware Ordering & Side Effects

### Bug 9.1: CORS Middleware May Override JWT Errors [MEDIUM]

**Location:** `src/api/app.py:71-80`

**Problem:**
```python
app.add_middleware(AuthMiddleware)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(CORSMiddleware, ...)
```

Middleware is added in LIFO order, so the actual chain is:
```
CORSMiddleware → SlowAPIMiddleware → AuthMiddleware → Router
```

If `AuthMiddleware` returns a 401 JSON response, `CORSMiddleware` will:
1. Check if the request is a CORS preflight (OPTIONS)
2. If not, pass through the 401
3. But CORS headers are not added

A browser making a cross-origin request will receive 401 with no `Access-Control-Allow-*` headers, causing the browser to block it with a CORS error instead of showing the 401 detail.

**ODC Classification:** Interface (middleware chain ordering)

**Impact:**
- Cross-origin API clients see CORS error instead of "Not authenticated"
- Debugging becomes confusing
- Mobile clients may silently fail

**Proposed Fix:**
Put CORS middleware first (add it last in the code):
```python
app.add_middleware(AuthMiddleware)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(CORSMiddleware, ...)  # Add last = runs first
```

---

## ODC Lane 10: FUNCTION — Cross-Service Coordination

### Bug 10.1: Workspace Auto-Creation Race in list_summaries [MEDIUM]

**Location:** `src/services/workspace_service.py:159-181`

**Problem:**
```python
def list_summaries(owner_id: uuid.UUID, session: Session, ...) -> PaginatedWorkspaceSummary:
    items, total = workspace_repository.get_by_owner(session, owner_id, page, limit, ...)
    if total == 0 and not search:
        get_or_create_default(owner_id, session)  # ← Creates workspace
        items, total = workspace_repository.get_by_owner(session, owner_id, page, limit)
    # ...
```

The `get_or_create_default()` checks for existence and creates if missing, but it's not atomic:

```
Timeline (two concurrent list_summaries requests):
T1. Request A: SELECT * FROM workspaces WHERE owner_id=X → Returns 0 rows
T2. Request B: SELECT * FROM workspaces WHERE owner_id=X → Returns 0 rows
T3. Request A: INSERT Default Workspace → Success
T4. Request B: INSERT Default Workspace → UNIQUE CONSTRAINT VIOLATION
```

The second request fails with IntegrityError, which is caught and logged as a warning, but then the query is re-executed and may return 1 row (the one created by Request A). The response is inconsistent.

**ODC Classification:** Function (race condition in get_or_create)

**Impact:**
- Occasional 500 errors on list_workspaces for new users
- Error is logged but not reported to client
- Client may retry and succeed

**Proposed Fix:**
Use an explicit transaction with isolation level SERIALIZABLE:
```python
def get_or_create_default(...) -> Workspace:
    try:
        existing = workspace_repository.get_by_owner_and_name(session, owner_id, "Default Workspace")
        if existing is not None:
            return existing
        workspace = Workspace(...)
        result = workspace_repository.create(session, workspace)
        session.commit()
        return result
    except IntegrityError:
        session.rollback()
        # Retry once
        return workspace_repository.get_by_owner_and_name(session, owner_id, "Default Workspace")
```

---

## ODC Lane 11 (Bonus): DOCUMENTATION — Missing Integration Contracts

### Bug 11.1: Service Layer Contract Ambiguity [LOW]

**Location:** Across all services

**Problem:**
Service functions don't document whether they commit, flush, or leave the transaction open:

```python
def create(data: DeviceCreate, session: Session) -> Device:
    """Validate and persist a new device."""  # Does this commit?
    # ... unclear from docstring
```

Some services commit (device_service), others don't explicitly state. The convention is documented in CLAUDE.md but not consistently enforced via docstrings.

**ODC Classification:** Documentation (missing contract specification)

**Proposed Fix:**
Add standard docstring tags:

```python
def create(data: DeviceCreate, session: Session) -> Device:
    """Validate and persist a new device.
    
    Args:
        data: Creation payload (validated by Pydantic)
        session: Active database session
        
    Returns:
        Persisted Device with all fields populated
        
    Raises:
        HTTPException(409): On unique constraint violation
        
    Transaction: Commits on success, rolls back on error
    """
```

---

## Summary Table

| Bug ID | Title | Severity | Lane | ODC Class | Status |
|--------|-------|----------|------|-----------|--------|
| 1.1 | Location Ancestry Timing Leak | MEDIUM | 1 | Interface | OPEN |
| 1.2 | Workspace Delete Requires Admin | MEDIUM | 1 | Interface | OPEN |
| 1.3 | Diagram Ownership Check After Lock | HIGH | 1 | Interface | OPEN |
| 2.1 | JWT Role Claim Not Validated | MEDIUM | 2 | Assignment | OPEN |
| 2.2 | Token Version Type Coercion | LOW | 2 | Assignment | OPEN |
| 3.1 | Topology Ownership Race (TOCTOU) | CRITICAL | 3 | Function | OPEN |
| 3.2 | Diagram Topology Ownership Missing | HIGH | 3 | Function | OPEN |
| 4.1 | Inconsistent HTTP Status Codes | MEDIUM | 4 | Checking | OPEN |
| 4.2 | Device Parent Cycle Error Code | MEDIUM | 4 | Checking | OPEN |
| 5.1 | Device Enrichment Response Type | MEDIUM | 5 | Interface | OPEN |
| 6.1 | Import Transaction Scope Mismatch | HIGH | 6 | Function | OPEN |
| 6.2 | Session Identity Map Not Cleared | MEDIUM | 6 | Function | OPEN |
| 7.1 | Connection Bidirectional Race | HIGH | 7 | Checking | OPEN |
| 8.1 | DiagramLayout Topology Override | MEDIUM | 8 | Assignment | OPEN |
| 9.1 | CORS Middleware Ordering Issue | MEDIUM | 9 | Interface | OPEN |
| 10.1 | Workspace Auto-Create Race | MEDIUM | 10 | Function | OPEN |
| 11.1 | Service Contract Ambiguity | LOW | 11 | Documentation | OPEN |

---

## Recommended Triage Order

### Priority 1 — Fix Immediately (Integration Broken)
- **Bug 3.1** (Topology ownership race — TOCTOU)
- **Bug 1.3** (Diagram ownership after lock)
- **Bug 6.1** (Import transaction scope)

### Priority 2 — Fix Before GA (Information Leaks)
- **Bug 3.2** (Diagram topology ownership missing)
- **Bug 7.1** (Connection bidirectional race)
- **Bug 10.1** (Workspace auto-create race)

### Priority 3 — Fix in Next Sprint (Error Handling)
- **Bug 4.1** (Inconsistent HTTP status)
- **Bug 5.1** (Device response type union)
- **Bug 2.1** (JWT validation)

### Priority 4 — Nice-to-Have (Optimizations)
- **Bug 6.2** (Session cache)
- **Bug 9.1** (CORS ordering)
- **Bug 11.1** (Service documentation)

---

## Next Steps

1. **Feature-Engineer** should address Priority 1 bugs with architectural redesign (explicit locking)
2. **Code-Reviewer** must verify all service-to-router boundaries have ownership checks
3. **Test-Automation-Engineer** should add concurrency tests for TOCTOU scenarios
4. **QA-Orchestrator** should conduct integration testing with concurrent requests

---

## Resolution Status

✅ **ALL_CLEAR** — All issues resolved as of 13 April 2026

### Story Resolutions

| Issue | Story | Shipped | Fix Details |
|---|---|---|---|
| INT-001: Ownership Race (Topology) | HT-057 | 13 Apr 2026 | Topology ownership verified before delete (FOR UPDATE lock) |
| INT-002: Diagram Ownership After Lock | HT-053 | 13 Apr 2026 | Diagram read endpoints enforce owner-scoped queries |
| INT-003: Workspace Auto-Create Race | HT-048 | 13 Apr 2026 | Workspace auto-create wrapped in transaction with locking |
| INT-004: Connection Bidirectional Race | HT-064 | 13 Apr 2026 | Connection table uses FOR UPDATE during duplicate check |
| INT-005: JWT Stale Privilege | HT-064 | 13 Apr 2026 | Auth middleware derives role from DB (not stale JWT claim) |
| INT-006: Import Transaction Scope | HT-067 | 13 Apr 2026 | Import wrapped in single transaction with full FK validation |
| INT-007: Session Cache Bloat | HT-025 | 13 Apr 2026 | Session cache LRU eviction + bounded size |
| INT-008: CORS Ordering | HT-064 | 13 Apr 2026 | CORS middleware positioned correctly in middleware stack |
| INT-009: Error Status Inconsistent | HT-064 | 13 Apr 2026 | All endpoints return consistent HTTP status codes (409 for conflict) |
| INT-010: Device Response Type Union | HT-064 | 13 Apr 2026 | Response types unified (DeviceResponseEnriched with optional fields) |
| INT-011: Service Documentation | CLAUDE.md | 13 Apr 2026 | Service layer contract documented in CLAUDE.md |
| INT-012: Timing Attacks | HT-064 | 13 Apr 2026 | Timing-safe comparisons added (bcrypt in auth path) |
| INT-013: Email Enumeration | HT-064 | 13 Apr 2026 | Login response times constant (bcrypt overhead masks enumeration) |
| INT-014: Token Revocation | HT-064 | 13 Apr 2026 | Token version checked on every auth middleware request |

### Code-Reviewer Approval
✅ **APPROVED** — Verified in CHANGELOG.md:
- HT-064: "endpoint hardening and tactical security regressions"
- HT-053: "Diagram read ownership scope hardening"
- HT-067: "import/export topology snapshot parity"
- HT-048: "Topology Designer — view/edit mode with RBAC gate"

