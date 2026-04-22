---
name: review-checklist
description: Hometower's code review rejection matrix and pattern library — the project-specific checklist items Code-Reviewer walks for every diff. Read this when reviewing code or preparing code for review.
---

# review-checklist

## Rejection Matrix (walk every category for every diff)

### 1. Code Correctness
- [ ] Logic errors, off-by-one, incorrect conditionals
- [ ] SQLModel field types match intended data
- [ ] Pydantic validators cover edge cases (empty string IP, negative port)
- [ ] Unhandled edge cases (empty inventory, device with no connections, null location)
- [ ] Test coverage for new behavior (no tests = BLOCKER)

### 2. Security (JWT + RBAC)
- [ ] No JWT tokens or bcrypt hashes in Loguru logs
- [ ] No passwords stored or returned in API responses
- [ ] All new endpoints have `Depends(require_role(...))` — no unprotected routes
- [ ] RBAC level matches operation (writes >= Contributor, admin = Admin)
- [ ] No sensitive device data (IPs, MACs) in error messages to Reader role
- [ ] Cytoscape/Leaflet labels sanitized before JS injection — no stored XSS
- [ ] Taint tracking: trace external params to repo queries through RBAC validation (IDOR prevention)
- [ ] Idempotency: POST/PUT handle DB constraints via 409 Conflict

### 3. Layered Architecture
- [ ] `src/domain/` imports only `src/models/types.py` — no SQLModel, FastAPI, Loguru
- [ ] `Session` appears only in repositories, services, routers, and approved infrastructure entry points
- [ ] Repositories never `commit()` / `rollback()` and routers do not normally own transaction control
- [ ] `src/api/routers/` delegates to services — no direct repo/domain calls
- [ ] `src/ui/` does not import from `src/repositories/`
- [ ] Business logic not inline in FastAPI handlers

### 4. Data Integrity
- [ ] Device deletion cascades to connections, custom fields, tags
- [ ] Location deletion handles child locations (no orphaned devices)
- [ ] Diagram layout JSON validated before save
- [ ] Last-write-wins implemented cleanly (no partial state from concurrent saves)

### 5. Python Quality
- [ ] No `Any` types
- [ ] No `print()` or `logging.*` — only `src/utils/logger.py`
- [ ] No bare `except:`
- [ ] No mutable default arguments
- [ ] SQLModel sessions closed properly (context manager or FastAPI dependency)

### 6. Performance
- [ ] No N+1 queries — eager load relationships
- [ ] No synchronous blocking in async handlers
- [ ] Large result sets paginated
- [ ] Cytoscape JSON export doesn't serialize entire DB on every canvas move

### 7. Quality Gates
- [ ] Files <= 250 lines (cap 400). Test files exempt.
- [ ] Tests exist for all new behavior
- [ ] `CHANGELOG.md` updated under `[Unreleased]`

### 8. Infrastructure (when diff touches docker-compose.yml, Dockerfile, alembic/, scripts/, .env.example)
- [ ] No real secrets — `.env.example` has only placeholders
- [ ] PostgreSQL port not exposed to host without justification
- [ ] No `latest` image tags
- [ ] Alembic migration includes `downgrade()`
- [ ] New NOT NULL columns have DEFAULT or prior backfill migration
- [ ] DevOps-Engineer review completed if migration present

### 9. Cross-File Consistency
- [ ] Changed function signatures match ALL callers
- [ ] Changed model fields reflected in Pydantic read/create schemas
- [ ] New/changed endpoints have corresponding test coverage
- [ ] Renamed/removed functions not referenced by stale tests/imports

## Rejection Pattern Library

Recurring issues specific to this codebase. Check IN ADDITION to the matrix:

| Pattern | Category | Check |
|---|---|---|
| DiagramLayout JSON schema drift | DataIntegrity | Device/Connection model changes -> verify `cytoscape_json` handles it |
| Cytoscape event handler missing debounce | Performance | New canvas event handlers must debounce (300ms min) |
| Tag color not validated as hex | DataIntegrity | Tag.color must match `^#[0-9a-fA-F]{6}$` |
| Missing cascade on Location delete | DataIntegrity | Location deletion must cascade to child locations + devices |
| RBAC on new endpoint copied from wrong template | Security | Verify role level matches operation semantics, not copy-paste |
