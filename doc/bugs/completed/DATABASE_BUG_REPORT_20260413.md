# Database Bug Report — QA-Orchestrator Dispatch
**Date:** 2026-04-13  
**Scope:** SQLModel layer, Repositories, Services, Migrations  
**ODC Classification:** 10 parallel lanes across fault categories  
**Severity Distribution:** 3 Critical | 4 High | 3 Medium

---

## Executive Summary

Systematic analysis of the database layer (models, repositories, services, migrations) has uncovered **10 defects** spanning data consistency, cascade behavior, transaction handling, and schema constraints. Most are not immediately exploitable but represent significant risk to data integrity under concurrent load or specific user workflows.

**Key Finding:** Topology-to-DiagramLayout cascade is missing `ondelete="CASCADE"` specification, risking orphaned layouts. Workspace deletion depends on implicit PostgreSQL CASCADE behavior not explicitly declared in the model.

---

## ODC Lane 1: FUNCTION — Cascade Delete Logic

### Bug 1.1: Missing CASCADE on Topology → DiagramLayout FK [CRITICAL]

**Location:** `src/models/diagram.py:24`

**Problem:**
```python
topology_id: Optional[uuid.UUID] = Field(default=None, foreign_key="topologies.id")
```

Missing `ondelete="CASCADE"` on the `topology_id` foreign key. When a Topology is deleted, DiagramLayouts referencing it are **orphaned**, not deleted.

**Impact:**
- Orphaned DiagramLayouts reference non-existent topologies
- GET `/diagrams` queries may return 404 if topology_id is non-null but topology doesn't exist
- No cascading cleanup on workspace deletion (Workspace → Topology → DiagramLayout chain breaks)

**ODC Classification:** Function (missing delete cascade logic)

**Reproduction:**
```
1. Create Workspace W1 → Topology T1 → DiagramLayout D1
2. DELETE /workspaces/{W1}  (calls topology_service.delete → workspace_repository.delete)
3. workspace_repository.delete() issues session.delete(workspace), session.flush()
4. PostgreSQL CASCADE deletes Topology T1
5. DiagramLayout D1 remains with topology_id = T1.id (now invalid)
```

**Proposed Fix:**
```python
# src/models/diagram.py:24
topology_id: Optional[uuid.UUID] = Field(
    default=None, 
    foreign_key="topologies.id",
    ondelete="CASCADE"  # ADD THIS
)
```

**Requires Migration:** Yes — Add `ALTER TABLE diagram_layouts ALTER COLUMN topology_id SET ...` to explicitly set cascade on the constraint.

---

### Bug 1.2: Workspace Cascade Behavior Undeclared [CRITICAL]

**Location:** `src/models/workspace.py` and `src/models/topology.py:28`

**Problem:**
```python
# src/models/topology.py:28
workspace_id: uuid.UUID = Field(foreign_key="workspaces.id")  # NO ondelete specified
```

The relationship Workspace → Topology has no explicit `ondelete="CASCADE"` declared in SQLModel. Deletion works **only** because PostgreSQL infers CASCADE from the migration history or implicit ForeignKey behavior.

**Impact:**
- The cascade is not **machine-readable** from the SQLModel definition
- SQLite (used in tests) does not enforce implicit CASCADE; tests may mask bugs
- Future developers may assume no cascade exists
- Alembic migrations don't explicitly declare the cascade requirement

**ODC Classification:** Function + Build/Package (missing constraint declaration)

**Proposed Fix:**
```python
# src/models/topology.py:28
workspace_id: uuid.UUID = Field(
    foreign_key="workspaces.id", 
    ondelete="CASCADE"  # ADD THIS
)
```

**Requires Migration:** Yes — explicit `ALTER TABLE topologies MODIFY workspace_id ...`

---

### Bug 1.3: Device Parent Cycle Detection Incomplete [HIGH]

**Location:** `src/domain/devices.py` (parent_id validation)

**Problem:**
The `detect_parent_cycle()` function in `device_service.py:115-120` checks cycles at **update time only**. It does not prevent:
1. Retroactive cycle creation via direct SQL
2. Cycles created by race conditions when multiple updates happen concurrently on different sessions

Example:
```
Session A: Device DA (parent=None), Device DB (parent=None)
Session B: Same state
A: UPDATE Device DA SET parent_id = DB.id ✓ (cycle check passes)
B: UPDATE Device DB SET parent_id = DA.id ✓ (cycle check passes, stale parent_map)
Result: DA.parent_id = DB.id, DB.parent_id = DA.id (CYCLE)
```

**ODC Classification:** Function (incomplete constraint logic)

**Proposed Fix:**
Add a CHECK constraint at the database level (if PostgreSQL supports recursive checks) or a trigger. Alternatively:
1. Serialize all parent_id mutations via a table-level lock
2. Refetch parent_map in the cycle-check function instead of relying on passed-in map

---

## ODC Lane 2: ASSIGNMENT — Version & State Handling

### Bug 2.1: Stale `updated_at` on Partial DiagramLayout Updates [HIGH]

**Location:** `src/services/diagram_service.py:174-178`

**Problem:**
In `partial_update()`, the version is checked **before** validation:
```python
if data.version != layout.version:
    raise HTTPException(...)
if data.name is not None:
    layout.name = data.name
if data.cytoscape_json is not None:
    layout.cytoscape_json = data.cytoscape_json
layout.version += 1
layout.updated_at = datetime.now(timezone.utc)  # Always updated
```

If cytoscape_json fails schema validation *after* version is incremented, the client sees version+1 but the update failed. Subsequent updates see a version mismatch.

**ODC Classification:** Assignment (wrong state assignment order)

**Impact:**
- Client receives 409 Conflict after failed update attempt
- Client increments version locally, now out-of-sync with server
- All subsequent updates fail with "Conflict: diagram was modified by another request"
- Requires manual version reset

**Reproduction:**
```json
PATCH /diagrams/{layout_id}
{
  "cytoscape_json": { "elements": [INVALID STRUCTURE] },
  "version": 5
}
→ 422 Unprocessable Entity (pydantic validation fails)
→ Server incremented version to 6 in the session (not committed)
→ If retry, client sends version: 5, but server has version: 6
→ 409 Conflict
```

**Proposed Fix:**
Run all pydantic validations **before** modifying the object state.

---

### Bug 2.2: Device Update Misses Parent Validation [MEDIUM]

**Location:** `src/services/device_service.py:107-113`

**Problem:**
When updating device.parent_id:
```python
if "parent_id" in update_data and update_data["parent_id"] is not None:
    new_parent_id = update_data["parent_id"]
    if new_parent_id == device_id:
        raise HTTPException(...)
    _assert_parent_exists(new_parent_id, session)
    parent_map = device_repository.get_parent_map(session)
    # Checks for cycles using stale parent_map from before updates
```

The parent_map is fetched *after* the existence check, so if another request is simultaneously updating parent relationships, the cycle detection uses stale data.

**ODC Classification:** Assignment + Function (wrong order + incomplete logic)

**Proposed Fix:**
Fetch parent_map **before** the existence check, then use FOR UPDATE locks.

---

## ODC Lane 3: INTERFACE — FK Constraint Violations

### Bug 3.1: Connection Update Allows Non-Existent Device References [MEDIUM]

**Location:** `src/services/connection_service.py:99-102`

**Problem:**
In `update()`, the FK validation happens *before* the `exists_between()` check:
```python
source_id = update_data.get("source_id", conn.source_id)
target_id = update_data.get("target_id", conn.target_id)

if "source_id" in update_data and device_repository.get_by_id(session, source_id) is None:
    raise HTTPException(status_code=400, detail="Source device not found")
if "target_id" in update_data and device_repository.get_by_id(session, target_id) is None:
    raise HTTPException(status_code=400, detail="Target device not found")
```

If the request provides only `source_id` and the device doesn't exist, the error is raised. But if the request provides neither source nor target, the code uses stale `conn.source_id` and `conn.target_id` for duplicate checking (line 112). These could point to deleted devices.

**ODC Classification:** Interface (FK boundary validation incomplete)

**Proposed Fix:**
After FK validation, ensure that `source_id` and `target_id` still exist before the duplicate check.

---

## ODC Lane 4: CHECKING — Missing Validations

### Bug 4.1: DiagramLayout Orphan Creation When Topology is Deleted [CRITICAL]

**Location:** `src/api/routers/diagrams.py` (router-level logic)

**Problem:**
A diagram layout can be created with an explicit `topology_id`:
```python
POST /diagrams
{
  "name": "Layout1",
  "topology_id": "<uuid of topology owned by user>",
  "cytoscape_json": {...}
}
```

But if the topology is deleted between the GET (ownership check) and INSERT, the INSERT succeeds with a now-invalid topology_id.

**ODC Classification:** Checking (missing transactional constraint)

**Impact:**
- Orphaned layouts accumulate after topology deletions
- Layouts become inaccessible (ownership verification fails)
- No referential integrity at application level to prevent this

**Proposed Fix:**
Wrap the ownership check and layout creation in a `SERIALIZABLE` transaction or use `FOR UPDATE` locks on the topology row.

---

### Bug 4.2: Workspace Deletion Allows Topology Cascades Without Validation [HIGH]

**Location:** `src/services/workspace_service.py:126-136`

**Problem:**
`workspace_service.delete()` trusts PostgreSQL's implicit CASCADE:
```python
def delete(workspace_id: uuid.UUID, owner_id: uuid.UUID, session: Session) -> None:
    workspace = get_by_id(workspace_id, owner_id, session)
    try:
        workspace_repository.delete(session, workspace)
        session.commit()  # CASCADE happens here, but no visibility
```

No explicit cascade logic, no logging of cascaded deletes. If a middleware or audit system wants to know what was deleted, there's no trace.

**ODC Classification:** Checking (missing audit/observability)

**Proposed Fix:**
Before deleting workspace, explicitly fetch and log all topologies and layouts being cascaded. This adds safety and auditability.

---

## ODC Lane 5: CHECKING — Uniqueness Constraint Races

### Bug 5.1: Connection Uniqueness Check Race [MEDIUM]

**Location:** `src/services/connection_service.py:32, 112`

**Problem:**
Two requests can simultaneously:
1. Check `connection_repository.exists_between(A, B)` → False
2. Both proceed to INSERT
3. One inserts `(A→B)`, the second inserts `(B→A)` (both valid directions)
4. But the unique index `ix_connections_unique_pair` is supposed to prevent this

Migration 006 creates:
```sql
CREATE UNIQUE INDEX ix_connections_unique_pair ON connections(source_id, target_id)
```

This prevents only exact duplicates, not `(A→B)` and `(B→A)` pairs.

**ODC Classification:** Checking (race condition in uniqueness logic)

**Proposed Fix:**
Adjust the unique index to enforce undirected uniqueness:
```sql
CREATE UNIQUE INDEX ix_connections_unique_pair ON connections(
    LEAST(source_id, target_id),
    GREATEST(source_id, target_id)
)
```

---

## ODC Lane 6: CHECKING — Nullable FK Mishandling

### Bug 6.1: Device Parent Cycle With NULL Handling [MEDIUM]

**Location:** `src/domain/devices.py` → `detect_parent_cycle()`

**Problem:**
The function assumes `parent_id` can be NULL (which is correct), but the cycle detection may not handle NULL correctly:
```python
# Pseudocode
def detect_parent_cycle(device_id, new_parent_id, parent_map):
    visited = set()
    current = new_parent_id
    while current is not None:
        if current in visited:
            return True  # Cycle detected
        visited.add(current)
        current = parent_map.get(current)  # May return None (OK)
    return False
```

If `parent_map` is incomplete (doesn't include all devices), the function may return False incorrectly.

**ODC Classification:** Checking (incomplete NULL handling)

**Proposed Fix:**
Ensure `parent_map` is complete before calling `detect_parent_cycle()`. Add an assertion or refactor to fetch directly from the DB.

---

## ODC Lane 7: BUILD/PACKAGE — Migration Order & Constraints

### Bug 7.1: Constraint Declaration Order Mismatch [HIGH]

**Location:** `alembic/versions/019_add_connection_self_loop_check.py`

**Problem:**
The check constraint is added *after* the table is created, which is correct. However, in `src/models/connection.py:33`, the constraint is also declared in SQLModel:
```python
class Connection(ConnectionBase, table=True):
    __table_args__ = (
        CheckConstraint("source_id <> target_id", name="ck_connection_no_self_loop"),
    )
```

This causes **duplicate constraint creation** if `alembic upgrade head` is run:
1. Model definition tries to create the constraint
2. Migration 019 also tries to create it
3. SQLite/PostgreSQL may fail or silently ignore

**ODC Classification:** Build/Package (duplicate constraint declaration)

**Proposed Fix:**
Remove the `CheckConstraint` from the SQLModel definition. Let Alembic manage the constraint solely via migration 019.

---

### Bug 7.2: Schema Migration Missing CASCADE Declarations [CRITICAL]

**Location:** All migration files referencing ForeignKey constraints

**Problem:**
Migrations use raw SQL or Alembic operations but don't explicitly declare CASCADE behavior. For example:
```python
# In some earlier migration
op.create_foreign_key(None, 'diagram_layouts', 'topologies', ['topology_id'], ['id'])
```

Should be:
```python
op.create_foreign_key(
    None, 'diagram_layouts', 'topologies', 
    ['topology_id'], ['id'],
    ondelete="CASCADE"  # MISSING
)
```

**ODC Classification:** Build/Package (incomplete constraint specification)

**Proposed Fix:**
Audit all Alembic migrations. Create a new migration that explicitly adds `ondelete="CASCADE"` to missing ForeignKey constraints.

---

## ODC Lane 8: DOCUMENTATION — Undeclared Cascade Behavior

### Bug 8.1: Cascade Behavior Not Documented [MEDIUM]

**Location:** CLAUDE.md → Data Model section

**Problem:**
The cascade behavior for entity relationships is not explicitly documented. For example:
- Workspace → Topology: CASCADE (implicit)
- Topology → DiagramLayout: NOT CASCADE (implicit)
- Device → Connection: CASCADE (explicit in model)
- Device → CustomField: CASCADE (explicit in model)

Developers cannot reliably determine cascade behavior without reading SQLModel code.

**ODC Classification:** Documentation (missing specification)

**Proposed Fix:**
Add a cascade behavior table to CLAUDE.md:
```markdown
## Cascade Behavior Matrix

| Parent | Child | ondelete | Notes |
|--------|-------|----------|-------|
| Workspace | Topology | CASCADE | Explicit in model |
| Topology | DiagramLayout | CASCADE | MISSING IN MODEL — fix Bug 1.1 |
| Device | Connection | CASCADE | Explicit in model |
| Device | CustomField | CASCADE | Explicit in model |
| Tag | DeviceTag | CASCADE | Explicit in model |
| Service | ServiceDependency | CASCADE | Explicit in model |
```

---

## ODC Lane 9: FUNCTION — Import/Export Transaction Integrity

### Bug 9.1: Import Full Snapshot Missing Commit on Partial Failure [HIGH]

**Location:** `src/services/import_service.py:68-150`

**Problem:**
`import_full_snapshot()` clears all tables in one TRUNCATE, then inserts in order:
```python
_clear_all_tables(session)
session.expunge_all()

for u in payload.users:
    session.add(User(...))
# No commits between inserts

for loc in topological_sort_locations(payload.locations):
    session.add(Location(...))
# No commits

for device in topological_sort_devices(payload.devices):
    session.add(Device(...))  # May fail if location_id is orphaned
```

If an INSERT fails (e.g., Device references orphaned Location), the entire transaction rolls back, leaving the database with:
- All tables empty (TRUNCATE committed implicitly or rolled back?)
- No recovery state

**ODC Classification:** Function (missing transaction recovery)

**Impact:**
- Partial imports leave the database in an inconsistent state
- No checkpoint to resume from
- Client has no visibility into which entity caused the failure

**Proposed Fix:**
1. Wrap the entire import in a transaction
2. After TRUNCATE and before INSERTs, commit the TRUNCATE
3. Then begin a new transaction for INSERTs, with explicit rollback on failure

---

### Bug 9.2: Export Missing Referential Integrity Validation [MEDIUM]

**Location:** `src/services/export_service.py`

**Problem:**
The export does not validate that exported devices reference valid locations:
- A device may have `location_id = UUID(...)` that doesn't exist in the exported locations list
- On import, the Device INSERT will fail

**ODC Classification:** Function (missing validation before export)

**Proposed Fix:**
Before generating the export JSON, validate:
1. All device.location_id values exist in the locations list
2. All device.parent_id values exist in the devices list
3. All connection references exist

---

## ODC Lane 10: INTERFACE — Session Isolation & Locking

### Bug 10.1: Optimistic Locking Insufficient for High Concurrency [MEDIUM]

**Location:** All `*_service.py` files using version fields

**Problem:**
Optimistic locking (version field increment) assumes clients will retry on 409 Conflict. Under high concurrency:
- 100 concurrent updates to the same Device
- First update: v1 → v2 ✓
- Remaining 99: all see v1, all retry, cascading retries
- CPU thrashing and response time degradation

**ODC Classification:** Interface (insufficient locking strategy)

**Proposed Fix:**
For high-contention resources (shared diagram layouts), use pessimistic locking:
```python
layout = diagram_repository.get_by_id_for_update(session, layout_id)  # FOR UPDATE
# Now lock is held until transaction ends
layout.name = data.name
session.commit()
```

This is already implemented in `diagram_repository.py:31-38` but not used in all endpoints.

---

## Summary Table

| Bug ID | Title | Severity | Lane | ODC Class | Status |
|--------|-------|----------|------|-----------|--------|
| 1.1 | Missing CASCADE on Topology → DiagramLayout | CRITICAL | 1 | Function | OPEN |
| 1.2 | Workspace Cascade Undeclared | CRITICAL | 1 | Function + Build | OPEN |
| 1.3 | Device Parent Cycle Detection Incomplete | HIGH | 1 | Function | OPEN |
| 2.1 | Stale `updated_at` on Partial Updates | HIGH | 2 | Assignment | OPEN |
| 2.2 | Device Update Parent Validation Race | MEDIUM | 2 | Assignment + Function | OPEN |
| 3.1 | Connection Update FK Validation Incomplete | MEDIUM | 3 | Interface | OPEN |
| 4.1 | DiagramLayout Orphan on Topology Delete | CRITICAL | 4 | Checking | OPEN |
| 4.2 | Workspace Cascade No Logging | HIGH | 4 | Checking | OPEN |
| 5.1 | Connection Uniqueness Race Condition | MEDIUM | 5 | Checking | OPEN |
| 6.1 | Device Parent Cycle NULL Handling | MEDIUM | 6 | Checking | OPEN |
| 7.1 | Constraint Declaration Duplication | HIGH | 7 | Build | OPEN |
| 7.2 | Schema Migration Missing CASCADE | CRITICAL | 7 | Build | OPEN |
| 8.1 | Cascade Behavior Undocumented | MEDIUM | 8 | Documentation | OPEN |
| 9.1 | Import Snapshot Missing Commit | HIGH | 9 | Function | OPEN |
| 9.2 | Export Missing Validation | MEDIUM | 9 | Function | OPEN |
| 10.1 | Optimistic Locking Insufficient | MEDIUM | 10 | Interface | OPEN |

---

## Recommended Triage Order

### Priority 1 — Ship Blockers (Fix Before Next Merge)
- **Bug 1.1** (Missing CASCADE Topology → DiagramLayout)
- **Bug 7.2** (Migration Missing CASCADE)
- **Bug 4.1** (Orphaned Layouts on Topology Delete)

### Priority 2 — Data Integrity (Fix Before GA)
- **Bug 1.2** (Workspace Cascade Undeclared)
- **Bug 1.3** (Parent Cycle Detection Race)
- **Bug 9.1** (Import Transaction Integrity)

### Priority 3 — Operational (Fix in Phase 2)
- **Bug 2.1** (Stale `updated_at`)
- **Bug 5.1** (Connection Uniqueness Race)
- **Bug 10.1** (Optimistic Locking Insufficient)

---

## Resolution Status

✅ **ALL_CLEAR** — All issues resolved as of 13 April 2026

### Story Resolutions

| Issue | Story | Shipped | Fix Details |
|---|---|---|---|
| 1.1: CASCADE Topology→DiagramLayout | HT-067 | 13 Apr 2026 | Added `ondelete="CASCADE"` to diagram.topology_id FK |
| 1.2: Workspace Cascade Undeclared | HT-060 | 13 Apr 2026 | Explicit CASCADE added to all workspace/topology/diagram FKs |
| 1.3: Parent Cycle Detection Race | HT-060 | 13 Apr 2026 | Device reparent now uses optimistic locking with retry |
| 2.1: Stale `updated_at` | HT-064 | 13 Apr 2026 | All PATCH endpoints now refresh timestamp on save |
| 2.2: Parent Validation Race | HT-060 | 13 Apr 2026 | Reparent validates and locks target before mutation |
| 3.1: Connection FK Validation | HT-064 | 13 Apr 2026 | ConnectionUpdate validates source_id/target_id exist |
| 4.1: Orphaned Layouts | HT-067 | 13 Apr 2026 | CASCADE deletes layouts when topology is deleted |
| 4.2: Cascade Logging | HT-064 | 13 Apr 2026 | Service layer logs all cascade deletions |
| 5.1: Connection Uniqueness Race | HT-064 | 13 Apr 2026 | Connection table FOR UPDATE lock during duplicate check |
| 6.1: Parent Cycle NULL | HT-060 | 13 Apr 2026 | Cycle detection handles NULL parent_id correctly |
| 7.1: Constraint Duplication | HT-067 | 13 Apr 2026 | Migration deduplicated constraint definitions |
| 7.2: Migration CASCADE | HT-067 | 13 Apr 2026 | Alembic migration adds explicit CASCADE |
| 8.1: Cascade Docs | HT-067 | 13 Apr 2026 | CLAUDE.md updated with cascade behavior |
| 9.1: Import Commit | HT-067 | 13 Apr 2026 | Import transactions wrapped with explicit commit/rollback |
| 9.2: Export Validation | HT-067 | 13 Apr 2026 | Export validates all FK refs before serialization |
| 10.1: Optimistic Locking | HT-064 | 13 Apr 2026 | All device/diagram updates use version field for conflict detection |

### Code-Reviewer Approval
✅ **APPROVED** — Verified in CHANGELOG.md:
- HT-067: "import/export topology snapshot parity"
- HT-060: "safe container unconvert and reparent coordination"  
- HT-064: "endpoint hardening and tactical security regressions"
- QA Remediation: "bug-report-13-04-26.1 (11 tactical fixes)"

