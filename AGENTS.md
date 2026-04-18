# AGENTS.md

Single source of truth for Hometower architecture constraints, operating rules, and codebase conventions. Every Codex session reads this file. GitHub Copilot custom-agent docs remain in `.github/agents/`, but Codex does not execute their frontmatter/runtime. Copilot reference skills live in `.github/skills/`; Codex role skills live in `.agents/skills/`.

## Product
**Hometower** is a homelab modelling, inventory, and documentation platform (Cloudcraft for homelabbers). Users draw infrastructure on interactive topology canvases or pin it on a map; the diagram *is* the inventory. PostgreSQL backs everything.
Three pillars:
- **Modelling**: topology canvases + map
- **Inventory**: tags, custom fields, services, metadata
- **Documentation**: notes, reports, device types
Phase 2 (LightTower): multi-workspace teams, auto-discovery (Proxmox, Docker), audit logging, LDAP/SSO.
### Topology Model
- **Workspace** > **Topology** > **History**; history is immutable and created only by explicit `Save Version`
- **Personal Draft** is per-user autosaved state, not shared history
- Restore is append-only; deleted devices reappear only as ghost placeholders
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

Read reference skills as needed:
- `architecture-map` for file tree and key files
- `coding-patterns` for SQLModel, repo, service, and route patterns
- `data-model` for entities, tables, and relationships
- `auth-rbac` for auth and RBAC details
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
When Code-Reviewer returns `APPROVED` with valid mandatory-gate evidence, it may invoke `Git-Committer` to stage and create the local commit for the approved diff. `Git-Committer` must never push; push remains a human decision.

For Codex:
- Root `AGENTS.md` is the runtime source of truth
- `.agents/skills/` holds Codex role skills
- `.agents/skills/product-owner/SKILL.md` and `.agents/skills/project-manager/SKILL.md` are the self-contained behavior specs for those roles
- `.github/agents/*.agent.md` remain human-readable behavior references.
- If any agent-specific instruction conflicts with this file, follow this file
- Spawned subagents are never the main agent.
- Spawned subagents must never act as Project-Manager or Product-Owner.
- Only the main agent may act as Project-Manager or Product-Owner.
- Only the main agent may edit `doc/progress.md`, `doc/tracker.md`, or `doc/backlog.md`.
- Spawned subagents must treat `doc/progress.md`, `doc/tracker.md`, and `doc/backlog.md` as read-only.

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
These are the **mandatory review gates** for every code review run.
Code-Reviewer must run them as part of the review, report the exact commands and pass/fail results, and approve the full `git diff` only after all three pass.
If any mandatory gate is skipped, interrupted, missing from the verdict, or fails, the review is invalid and must not return `APPROVED`.

## Codex Enforcement

These practices remain mandatory after the migration from Copilot custom agents:
1. Read the relevant source files and skills before planning or editing.
2. Follow the layer boundaries in this file and the deeper rules in the referenced skills.
3. Keep `doc/progress.md`, `doc/tracker.md`, and `doc/backlog.md` consistent with the current workflow when acting in a role that owns them.
4. Run the pre-push quality gate for code changes unless the user explicitly limits scope and accepts the gap.
5. Treat the old Copilot custom-agent frontmatter, tool allowlists, and lateral invocation assumptions as reference material only; Codex must apply the workflow intentionally through `AGENTS.md` and repo skills.
6. Treat any Code-Reviewer verdict without mandatory-gate evidence as invalid. PM must re-route review rather than accepting or summarizing it as approval.
7. Optimize for accuracy over apparent speed. Do not summarize a task as complete while any required acceptance path, mandatory gate, or valid review proof is still missing or contradicted by stronger evidence.
8. When evidence conflicts, trust the strongest direct evidence available: live acceptance behavior > focused implementation claims, completed gate output > assumptions, and exact review evidence > paraphrased status.
9. Treat any spawned subagent that edits `doc/progress.md`, `doc/tracker.md`, or `doc/backlog.md`, or behaves like PM/PO, as an invalid lane that must be rejected and replaced.
10. If Code-Reviewer returns `APPROVED`, the reviewed diff may be committed locally via `Git-Committer`; it must never be pushed by any agent.

## Maintenance Rule
When Product-Owner, Project-Manager, or Codex delegation behavior changes, update:
1. `AGENTS.md`
2. The relevant local skill in `.agents/skills/`
3. The corresponding `.github/agents/*.agent.md` reference if the human-readable role doc should stay in sync
