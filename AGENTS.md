# AGENTS.md

Single source of truth for architecture constraints and codebase conventions. Every agent reads this file. Agent-specific behavior lives in `.github/agents/`. Detailed reference material lives in `.agents/skills/` — read the relevant skill when you need depth.

## Product

**Hometower** — homelab modelling, inventory management, and documentation platform (Cloudcraft for homelabbers).

Users draw infrastructure as interactive topology diagrams or pin locations on a map; the diagram *is* the inventory. PostgreSQL backs everything.

Three pillars: **Modelling** (topology canvases + map), **Inventory** (tags, custom fields, services, metadata), **Documentation** (notes, reports, device types).

Phase 2 (LightTower): multi-workspace teams, auto-discovery (Proxmox, Docker), audit logging, LDAP/SSO.

### Topology Model

- **Workspace** > **Topology** > **History** (immutable checkpoints via explicit `Save Version`)
- **Personal Draft** — per-user autosaved state, not shared history
- Restore is append-only (new version, never overwrite). Deleted devices become ghost placeholders.

## Commands

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
docker compose up -d                              # start stack
docker compose exec api pytest                    # run tests
docker compose exec api pytest tests/unit/test_devices.py -v  # single file
docker compose exec api mypy src/ --ignore-missing-imports    # type check
docker compose build                              # validate images
docker compose exec api alembic upgrade head      # run migrations
docker compose exec api alembic revision --autogenerate -m "description"
docker compose exec api pytest --cov=src --cov-report=term-missing

# Architecture enforcement (zero-tolerance)
grep -rn "from sqlmodel\|from fastapi\|from loguru" src/domain/ --include="*.py"  # must return nothing
grep -rn "from src.repositories" src/ui/ --include="*.py"                         # must return nothing
grep -rn "print(" src/ --include="*.py" | grep -v test | grep -v __pycache__      # must return nothing
```

## Tech Stack

| Layer | Technology |
|---|---|
| UI | NiceGUI |
| Canvas | Cytoscape.js via `ui.add_body_html()` — see `canvas-bridge` skill |
| Map | Leaflet.js + OpenStreetMap |
| API | FastAPI + Pydantic, co-served with NiceGUI via `ui.run_with()` |
| ORM | SQLModel + Alembic |
| DB | PostgreSQL 16 |
| Auth | passlib (bcrypt) + python-jose (JWT) |
| Logging | Loguru via `src/utils/logger.py` — never `print()` or `logging.*` |
| Deploy | Docker Compose |

## Architecture

```
UI (NiceGUI) → Routers (FastAPI) → Services → Repositories → PostgreSQL
                                       ↑
                                  Domain (pure Python, no I/O)
```

### Layer Rules

- **`src/domain/`** — Pure functions only. Imports only `src/models/types.py`. No SQLModel, FastAPI, Loguru.
- **`src/repositories/`** — Only layer with SQLModel `Session`. Uses `flush()` not `commit()`.
- **`src/services/`** — Orchestrates domain + repos. Owns `session.commit()`. One per feature.
- **`src/api/routers/`** — Delegates to services. `Depends(require_role(...))` on every handler.
- **`src/ui/`** — No repository imports. Uses design tokens, not hardcoded colors.

For the full file tree and key files, read the `architecture-map` skill.
For coding patterns (SQLModel hierarchy, repo/service/route patterns), read the `coding-patterns` skill.
For data model (entities, tables, relationships), read the `data-model` skill.
For auth/RBAC details, read the `auth-rbac` skill.

## Hard Constraints

1. Files <= 250 lines (cap 400). Test files exempt.
2. No `print()` or `logging.*` — only `src/utils/logger.py`
3. No `Any` types — use explicit types or `Union`
4. Domain (`src/domain/`) = zero side effects, imports only `src/models/types.py`
5. All API input validated by Pydantic before service layer
6. Never store raw passwords — bcrypt via `src/utils/auth.py`
7. `src/ui/` never imports `src/repositories/`
8. Repos use `flush()` — services own `commit()`
9. Every endpoint: `Depends(require_role(...))` — no unprotected routes
10. New models registered in `tests/conftest.py` or tests break
11. Always use `.venv` for local dev
12. No hardcoded UI colors — use `src/ui/design/tokens.py`
13. User-facing terms: Workspace / Topology / History — no new View/Layout concepts
14. Autosave = personal drafts only. `Save Version` = history entries.
15. History restore is append-only. Never auto-recreate deleted inventory devices.

## Agent Coordination

PM is the sole orchestrator. All work flows through PM via contract documents. Agents never invoke each other directly except:

| Parent | Sub-agents | Why |
|---|---|---|
| Code-Reviewer | Git-Committer | Atomic commit-on-approval |
| QA-Orchestrator | Bug-Finder | Parallel 10-lane fan-out |
| Security-Orchestrator | Security-Auditor, Architect | STRIDE fan-out + remediation design |

All other agents are **terminal** — read contracts, produce artifacts, return to PM.

User-invocable: `product-owner`, `project-manager`. All others via PM pipelines only.

### Boundary Rules

1. No lateral invocation — agents return to PM, PM dispatches next agent
2. Contract documents are the API — agents read inputs, produce outputs, PM routes
3. Exempted sub-agents stay scoped — no further chaining
4. PM owns the transaction — only PM advances, retries, or escalates

For the full contract document model, agent roster, and report lifecycle, read the `contract-routing` skill.

## Pre-Push Quality Gate

```bash
docker compose exec api pytest                              # all tests pass
docker compose exec api mypy src/ --ignore-missing-imports  # zero type errors
docker compose build                                        # images build clean
```

Code-Reviewer must approve the full `git diff` before pipeline completes.
