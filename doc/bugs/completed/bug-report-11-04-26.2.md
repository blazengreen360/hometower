# QA-Orchestrator Bug Report: 11-04-26.2

**Date:** 12 April 2026
**Target:** Hometower (Phase 1)
**Orchestrator:** QA-Orchestrator
**Methodology:** ODC-typed lane dispatch + STRIDE-per-element static audit

## Executive Summary
A comprehensive bug hunt was conducted across the source code following strict Orthogonal Defect Classification (ODC) lanes. The codebase exhibits strong adherence to architectural layering (no `src/domain/` impurity, no UI repository access). However, two **Critical/High** severity structural defects were identified that directly threaten runtime performance and application security.

### Verdict
🔴 **BLOCKED / VULNERABLE**
There are active IDOR vulnerabilities and complete API-layer concurrency starvation.

---

## Findings

### LANE: Concurrency & Performance (ODC: Timing/Serialization)

| ID | Severity | File | Description |
|---|---|---|---|
| **BUG-1102-01** | **CRITICAL** | `src/api/routers/*.py` | **Systemic ASGI Thread Starvation (Sync-in-Async).** Every route path operation function across `devices.py`, `topologies.py`, `workspaces.py`, `locations.py`, etc., is defined with `async def`. However, they all execute synchronous database calls via SQLModel's standard `Session`. In the FastAPI architecture, `async def` functions run directly on the single main event loop thread without threadpool delegation. **Impact:** A single slow database query or sequential batch request to any endpoint currently blocks the entire server from processing any other incoming HTTP requests. |

*Proof of Concept (BUG-1102-01):*
```python
# src/api/routers/devices.py (Line 64)
@router.get("/")
async def list_devices(session: Session = Depends(get_session)):
    # This blocks the event loop because session.exec() is synchronous!
    return device_service.get_all(session)
```
*Recommendation:* Immediately refactor all router methods interacting with sync DB services to standard `def` to force FastAPI to delegate them to standard worker threads.

---

### LANE: Security & Auth (STRIDE: Elevation of Privilege / IDOR)

| ID | Severity | File | Description |
|---|---|---|---|
| **BUG-1102-02** | **HIGH** | `src/services/diagram_service.py` | **IDOR on DiagramLayout Operations.** Unlike `topology_service.py`, which invokes `_verify_workspace_ownership()`, the diagram service's methods (`update`, `delete`, `partial_update`) only accept `layout_id` and do not verify the calling user's permissions over the topology/workspace the diagram belongs to. **Impact:** Any user with `Contributor` access can blindly modify, overwrite, or delete any DiagramLayout across the system if they acquire or guess its UUID. |

*Proof of Concept (BUG-1102-02):*
- Setup: User A creates Topology T1 and Diagram D1 in Workspace W1. User B has Contributor role in the system.
- Action: User B sends `DELETE /api/diagrams/{D1_UUID}`.
- Expected: 403/404 because User B does not own W1.
- Actual: 200 OK. Diagram is deleted.

*Recommendation:* Pass `owner_id` from the token into all `diagram_service` mutating methods. Fetch the parent Topology and query `workspace_repository.get_by_id()` to enforce ownership identically to topologies. (This aligns directly with backlog item HT-053).

---

### LANE: Logic & Data Integrity (ODC: Function/Algorithm)

| ID | Severity | File | Description |
|---|---|---|---|
| **BUG-1102-03** | **MEDIUM** | `src/models/diagram.py` | **SQLite JSON Persistence Risk.** The `cytoscape_json` field is typed as `Column(JSON)`. While SQLite can store JSON, the field validation logic inside `DiagramLayoutCreate` rejects payloads > 5MB. However, there is no validation capping atomic `update` payloads in the router. A malicious or looping client pushing a highly malformed or artificially bloated Cytoscape position delta loop could saturate the DB. |

---

## Routing & Next Steps Operations

1. **BUG-1102-01 (Sync-in-Async):** Route to `Architect` → `Feature-Engineer`. Requires an automated sweep of `src/api/routers/` to strip `async` from 40+ methods.
2. **BUG-1102-02 (Diagram IDOR):** Route to `QA-Fixer`. `diagram_service.py` and `src/api/routers/diagrams.py` require specific `owner_id` wiring.
3. **Tracking Update:** Record these findings in `doc/bugs/bug-report-11-04-26.2.md` and alert PM.
