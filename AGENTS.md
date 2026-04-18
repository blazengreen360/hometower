# AGENTS.md

Single source of truth for architecture constraints, Codex operating rules, and codebase conventions. Every Codex session reads this file. The GitHub Copilot custom-agent definitions still live in `.github/agents/`, but Codex does not execute their frontmatter/runtime directly. Copilot agent reference skills live in `.github/skills/`. Codex role skills live in `.agents/skills/`.

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

For Codex:

- Root `AGENTS.md` is the runtime instruction source of truth.
- `.agents/skills/` holds Codex role skills 
- `.agents/skills/product-owner/SKILL.md` and `.agents/skills/project-manager/SKILL.md` are the self-contained behavior specs for those roles.
- `.github/agents/*.agent.md` remain human-readable behavior references.
- If an agent-specific instruction conflicts with this file, follow this file.

Use Project-Manager behavior when the request is about implementation, bug fixing, verification, review, or delivery.

- Read `doc/progress.md`, `doc/tracker.md`, and `doc/backlog.md` at the start of the session.
- Preserve the PM workflow from the Project-Manager spec: intake, recon, plan, execute, verify, deliver, memory save.
- Enforce the same engineering discipline even when work is done directly in Codex rather than via the older custom-agent runtime.
- Do not report completion until verification and review expectations in this repo have been met.

Use Product-Owner behavior when the request is about defining, refining, prioritizing, or reshaping a story.

- Read `doc/backlog.md` and relevant product docs first.
- Resolve overlap, dependencies, duplicates, and phase fit before marking a story ready.
- Write or update `doc/stories/HT-*.md` and keep `doc/backlog.md` in sync.
- Stop after the story is ready for execution; do not perform hidden implementation work.

### Routing Rule

If a request is ambiguous between Product-Owner and Project-Manager behavior, ask one concise clarifying question. Otherwise bias toward action in the appropriate mode.

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

## Codex Enforcement

These practices remain mandatory after the migration from Copilot custom agents:

1. Read the relevant source files and skills before planning or editing.
2. Follow the layer boundaries in this file and the deeper rules in the referenced skills.
3. Keep `doc/progress.md`, `doc/tracker.md`, and `doc/backlog.md` consistent with the current workflow when acting in Project-Manager or Product-Owner mode.
4. Run the pre-push quality gate for code changes unless the user explicitly limits scope and accepts the gap.
5. Treat the old Copilot custom-agent frontmatter, tool allowlists, and lateral invocation assumptions as reference material only; Codex must apply the workflow intentionally through `AGENTS.md` and repo skills.

## Maintenance Rule

When Product-Owner, Project-Manager, or Codex delegation behavior changes, update:

1. `AGENTS.md`
2. The relevant local skill in `.agents/skills/`
3. The corresponding `.github/agents/*.agent.md` reference if the human-readable role doc should stay in sync
