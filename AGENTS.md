# AGENTS.md

Single source of truth for Hometower architecture constraints, operating rules, and codebase conventions. Every agent session reads this file. GitHub Copilot custom-agent docs remain in `.github/agents/`, but the active runtime does not execute their frontmatter/runtime. Copilot reference skills live in `.github/skills/`; local role skills live in `.agents/skills/`.

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
| Canvas | Cytoscape.js via `ui.add_body_html()` — see the `ux-designer` skill (`Canvas Bridge` section) |
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
- **`src/repositories/`** — Encapsulates SQLModel query/mutation mechanics. Repository functions accept an existing `Session`, may query/add/delete/flush/refresh, and never `commit()` or `rollback()`.
- **`src/services/`** — May accept an existing request-scoped `Session` from routers or approved infrastructure entry points. Orchestrates domain + repos and owns `session.commit()` / `session.rollback()`. One per feature.
- **`src/api/routers/`** — Delegates to services. `Depends(require_role(...))` on every handler. Routers may inject `session: Session = Depends(get_session)` and pass it to services, but do not import repositories or own transaction control.
- **`src/ui/`** — No repository imports. Uses design tokens, not hardcoded colors.

Approved `Session` creation points are limited to `src/utils/db.py`, `src/api/app.py`, and `src/api/middleware/auth.py` unless Architect explicitly approves another infrastructure entry point.

Read local role skills as needed:
- `architect` for architecture maps, data model details, auth/RBAC boundaries, and established backend patterns
- `backend-engineer` and `db-engineer` for service, repository, model, and migration conventions
- `frontend-engineer` and `ux-designer` for NiceGUI, map, canvas, and design-token guidance
- `deterministic-review-tooling` for repo-local scope and review enforcement scripts
## Hard Constraints
1. Files <= 250 lines (cap 400). Test files exempt.
2. No `print()` or `logging.*` — only `src/utils/logger.py`
3. No `Any` types — use explicit types or `Union`
4. Domain (`src/domain/`) = zero side effects, imports only `src/models/types.py`
5. All API input validated by Pydantic before service layer
6. Never store raw passwords — bcrypt via `src/utils/auth.py`
7. `src/ui/` never imports `src/repositories/`
8. Repos use `flush()` — services own `commit()` / `rollback()`
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
| QA-Orchestrator | Bug-Finder (`qa-bug-finder`) | Parallel 10-lane fan-out |
| Security-Orchestrator | Security-Auditor, Architect | STRIDE fan-out + remediation design |
All other agents are **terminal** — read contracts, produce artifacts, return to PM.
`Context-Intern` is a terminal read-only recon lane that PM may invoke for bounded repository reconnaissance before planning or when the blast radius is unclear.
User-invocable: `product-owner`, `project-manager`. All others via PM pipelines only.
`CI-Gatekeeper` owns mandatory CI/static gates. `Code-Reviewer` owns semantic, logical, architectural, and acceptance review.
Every story closeout requires **two independent parallel `Code-Reviewer` lanes** against a passing current-pipeline `CI-Gatekeeper` report.
Neither reviewer may commit. After both reviewers independently return `APPROVED`, PM performs the local commit. Push is always a human decision.

For local agent runtimes:
- Root `AGENTS.md` is the runtime source of truth
- Checked-in role references live under `.github/agents/*.agent.md`
- Checked-in repo skills live under `.github/skills/`
- Some external runtimes may also mount `.agents/skills/`, but that tree is not versioned in this workspace and should not be assumed by repo-local tooling
- `QA-Fixer` and `Bug-Finder` remain the stable PM routing aliases for the remediation and bug-finder lanes
- `.github/agents/*.agent.md` remain human-readable behavior references.
- If any agent-specific instruction conflicts with this file, follow this file
- Spawned subagents must never act as Project-Manager or Product-Owner.


### Boundary Rules
1. No lateral invocation — agents return to PM, PM dispatches next agent
2. Contract documents are the API — agents read inputs, produce outputs, PM routes
3. Exempted sub-agents stay scoped — no further chaining
4. PM owns the transaction — only PM advances, retries, or escalates
For the full contract document model, agent roster, and report lifecycle, follow this file plus the checked-in project-manager reference docs under `.github/agents/` and the repo-local skills under `.github/skills/`.
## Pre-Push Quality Gate
```bash
docker compose exec api pytest                              # all tests pass
docker compose exec api mypy src/ --ignore-missing-imports  # zero type errors
docker compose build                                        # images build clean
```
These are the **mandatory review gates** for every code review run.
`CI-Gatekeeper` must run them as part of the review pipeline, report the exact commands and pass/fail results, and return a pass/fail gate report for the full `git diff`.
`Code-Reviewer` must not return `APPROVED` unless a current-pipeline `CI-Gatekeeper` report shows all three passed.
Story closeout is invalid unless two independent parallel `Code-Reviewer` lanes both approve against that gate report.
If any mandatory gate is skipped, interrupted, missing from the gate report, or fails, the review pipeline is invalid and must not return `APPROVED`.
If the reviewed diff touches `requirements.txt`, `CI-Gatekeeper` must also run dependency SAST (`pip-audit`) on that manifest and fail closed on missing or failing audit evidence.
`CI-Gatekeeper` must also run code SAST (`bandit -r src/ -ll -ii`) on every run covering Python implementation files and fail closed on medium or higher severity findings.

## Agent Runtime Enforcement

These practices remain mandatory after the migration from Copilot custom agents:
1. Read the relevant source files and skills before planning or editing.
2. Follow the layer boundaries in this file and the deeper rules in the referenced skills.
3. Keep `doc/progress.md`, `doc/tracker.md`, and `doc/backlog.md` consistent with the current workflow when acting in a role that owns them.
4. Run the pre-push quality gate for code changes unless the user explicitly limits scope and accepts the gap.
5. Treat the old Copilot custom-agent frontmatter, tool allowlists, and lateral invocation assumptions as reference material only; the active runtime must apply the workflow intentionally through `AGENTS.md` and repo skills.
6. Treat any `CI-Gatekeeper` report without mandatory-gate evidence as invalid, and treat any story closeout without two independent `Code-Reviewer` approvals against a passing current-pipeline gate report as invalid. PM must re-route review rather than accepting or summarizing it as approval.
7. Optimize for accuracy over apparent speed. Do not summarize a task as complete while any required acceptance path, mandatory gate, or valid review proof is still missing or contradicted by stronger evidence.
8. When evidence conflicts, trust the strongest direct evidence available: live acceptance behavior > focused implementation claims, completed gate output > assumptions, and exact review evidence > paraphrased status.
9. Treat any spawned subagent that edits `doc/progress.md`, `doc/tracker.md`, or `doc/backlog.md`, or behaves like PM/PO, as an invalid lane that must be rejected and replaced.
10. `Code-Reviewer` verdicts must never commit. After two independent `Code-Reviewer` lanes return `APPROVED` against a valid passing `CI-Gatekeeper` report, PM performs the local commit. Push is always a human decision.

## Maintenance Rule
When Product-Owner, Project-Manager, or agent delegation behavior changes, update:
1. `AGENTS.md`
2. The relevant local skill in `.agents/skills/`
3. The corresponding `.github/agents/*.agent.md` reference if the human-readable role doc should stay in sync
