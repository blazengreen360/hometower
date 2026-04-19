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
- **`src/repositories/`** — Only layer with SQLModel `Session`. Uses `flush()` not `commit()`.
- **`src/services/`** — Orchestrates domain + repos. Owns `session.commit()`. One per feature.
- **`src/api/routers/`** — Delegates to services. `Depends(require_role(...))` on every handler.
- **`src/ui/`** — No repository imports. Uses design tokens, not hardcoded colors.

Read local role skills as needed:
- `architect` for architecture maps, data model details, auth/RBAC boundaries, and established backend patterns
- `backend-engineer` and `db-engineer` for service, repository, model, and migration conventions
- `frontend-engineer` and `ux-designer` for NiceGUI, map, canvas, and design-token guidance
- `deterministic-review-tooling` for Codex-local scope and review enforcement scripts
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
| QA-Orchestrator | Bug-Finder (`qa-bug-finder`) | Parallel 10-lane fan-out |
| Security-Orchestrator | Security-Auditor, Architect | STRIDE fan-out + remediation design |
All other agents are **terminal** — read contracts, produce artifacts, return to PM.
User-invocable: `product-owner`, `project-manager`. All others via PM pipelines only.
`CI-Gatekeeper` owns mandatory CI/static gates. `Code-Reviewer` owns semantic, logical, architectural, and acceptance review.
Every story closeout requires **two independent parallel `Code-Reviewer` lanes** against a passing current-pipeline `CI-Gatekeeper` report.
Neither reviewer may commit during the initial review pass. After both reviewers independently return `APPROVED`, PM may authorize one approved reviewer to commit the reviewed diff locally. Code-Reviewer must never push; push remains a human decision.

For Codex:
- Root `AGENTS.md` is the runtime source of truth
- `.agents/skills/` holds Codex role skills
- `.agents/skills/product-owner/SKILL.md` and `.agents/skills/project-manager/SKILL.md` are the self-contained behavior specs for those roles
- `QA-Fixer` is the stable PM routing alias for the `.agents/skills/qa-remediation/SKILL.md` skill/agent
- `Bug-Finder` is the stable PM routing alias for the `.agents/skills/qa-bug-finder/SKILL.md` skill/agent
- `.github/agents/*.agent.md` remain human-readable behavior references.
- If any agent-specific instruction conflicts with this file, follow this file
- Spawned subagents are never the main agent.
- Spawned subagents must never act as Project-Manager or Product-Owner.
- Only the main agent may act as Project-Manager or Product-Owner.
- Only the main agent may edit `doc/progress.md`, `doc/tracker.md`, or `doc/backlog.md`.
- Spawned subagents must treat `doc/progress.md`, `doc/tracker.md`, and `doc/backlog.md` as read-only.
- The no-further-spawning rule has two explicit exemptions. When running as a worker subagent, these roles may spawn additional bounded subagents as listed:
  - `QA-Orchestrator` may spawn `Bug-Finder` (`qa-bug-finder`) workers for parallel lane fan-out.
  - `Security-Orchestrator` may spawn `Security-Auditor` and `Architect` workers for STRIDE fan-out.
  - No other worker subagent may spawn further subagents under any circumstance.

### Boundary Rules
1. No lateral invocation — agents return to PM, PM dispatches next agent
2. Contract documents are the API — agents read inputs, produce outputs, PM routes
3. Exempted sub-agents stay scoped — no further chaining
4. PM owns the transaction — only PM advances, retries, or escalates
For the full contract document model, agent roster, and report lifecycle, follow this file plus `.agents/skills/project-manager/SKILL.md` and `.agents/skills/pm-handoff/SKILL.md`.
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
If the reviewed diff touches `requirements.txt`, `CI-Gatekeeper` must also run dependency SAST on that manifest and fail closed on missing or failing audit evidence.

## Codex Enforcement

These practices remain mandatory after the migration from Copilot custom agents:
1. Read the relevant source files and skills before planning or editing.
2. Follow the layer boundaries in this file and the deeper rules in the referenced skills.
3. Keep `doc/progress.md`, `doc/tracker.md`, and `doc/backlog.md` consistent with the current workflow when acting in a role that owns them.
4. Run the pre-push quality gate for code changes unless the user explicitly limits scope and accepts the gap.
5. Treat the old Copilot custom-agent frontmatter, tool allowlists, and lateral invocation assumptions as reference material only; Codex must apply the workflow intentionally through `AGENTS.md` and repo skills.
6. Treat any `CI-Gatekeeper` report without mandatory-gate evidence as invalid, and treat any story closeout without two independent `Code-Reviewer` approvals against a passing current-pipeline gate report as invalid. PM must re-route review rather than accepting or summarizing it as approval.
7. Optimize for accuracy over apparent speed. Do not summarize a task as complete while any required acceptance path, mandatory gate, or valid review proof is still missing or contradicted by stronger evidence.
8. When evidence conflicts, trust the strongest direct evidence available: live acceptance behavior > focused implementation claims, completed gate output > assumptions, and exact review evidence > paraphrased status.
9. Treat any spawned subagent that edits `doc/progress.md`, `doc/tracker.md`, or `doc/backlog.md`, or behaves like PM/PO, as an invalid lane that must be rejected and replaced.
10. Initial `Code-Reviewer` verdicts must not commit. After two independent `Code-Reviewer` lanes return `APPROVED` against a valid passing `CI-Gatekeeper` report, PM may authorize one approved reviewer to commit the reviewed diff locally; it must never push.

## Maintenance Rule
When Product-Owner, Project-Manager, or Codex delegation behavior changes, update:
1. `AGENTS.md`
2. The relevant local skill in `.agents/skills/`
3. The corresponding `.github/agents/*.agent.md` reference if the human-readable role doc should stay in sync
