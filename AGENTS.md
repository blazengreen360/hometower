# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What Hometower Is

Hometower is a **self-hosted homelab inventory management tool** — Cloudcraft for homelabbers. Users draw their infrastructure as an interactive topology diagram or geographic map; that diagram *is* the inventory. Every node placed and connection drawn populates a searchable PostgreSQL database.

**Phase 2 (LightTower)** adds multi-workspace team support, auto-discovery integrations, and LDAP/SSO.

## Commands

```bash
# Set up local virtual environment (required — always use .venv)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start full stack
docker compose up -d

# Run tests
docker compose exec api pytest

# Type check
docker compose exec api mypy src/ --ignore-missing-imports

# Build (validates Docker images build cleanly)
docker compose build

# Run single test file
docker compose exec api pytest tests/unit/test_devices.py -v

# Alembic migrations
docker compose exec api alembic upgrade head
docker compose exec api alembic revision --autogenerate -m "description"

# Generate coverage report
docker compose exec api pytest --cov=src --cov-report=term-missing
```

## Tech Stack

| Layer | Technology |
|---|---|
| UI | NiceGUI |
| Topology canvas | Cytoscape.js (embedded in NiceGUI via `ui.add_body_html()`) |
| Map view | Leaflet.js + OpenStreetMap (embedded in NiceGUI) |
| API | FastAPI + Pydantic — served on same process as NiceGUI via `ui.run_with()` |
| ORM | SQLModel + Alembic |
| Database | PostgreSQL 16 |
| Auth | passlib (bcrypt) + python-jose (JWT) |
| Logging | Loguru — **always use `src/utils/logger.py`, never `print()` or `logging.*`** |
| Deployment | Docker Compose |

## Architecture

Strict layered architecture — import direction must point inward only:

```
NiceGUI UI  →  FastAPI Routers  →  Services  →  Repositories  →  PostgreSQL
                                       ↑
                                  Domain Logic
                             (pure Python, no I/O)
```

### Layer Rules (enforced in code review)

- **`src/ui/`** — NiceGUI pages and components. Never imports from `src/repositories/`. Talks to the API via HTTP or calls service layer directly for internal use.
- **`src/api/`** — FastAPI routers. Pydantic validates all input. JWT + RBAC enforced via middleware before handlers run. Delegates to `src/services/`.
- **`src/services/`** — Orchestrates domain logic and repositories. Owns database transactions. One service per feature area.
- **`src/domain/`** — **Pure Python functions only.** No SQLModel, no FastAPI, no network calls, no file I/O. All business rules and validation logic live here. Every function must be independently testable with no mocking.
- **`src/repositories/`** — Only layer that holds a SQLModel `Session`. One repository per model.

### Key Files

| File | Purpose |
|---|---|
| `src/models/types.py` | Enums: `DeviceType`, `ConnectionType`, `Role`, `LocationType` |
| `src/utils/logger.py` | Loguru instance — import and use this everywhere |
| `src/utils/auth.py` | JWT helpers, `hash_password()`, `verify_password()` |
| `src/api/middleware/auth.py` | JWT decode + RBAC enforcement |
| `src/api/app.py` | FastAPI app creation + NiceGUI mount (`ui.run_with()`) |
| `src/ui/design/tokens.py` | Design system constants — no hardcoded colors elsewhere |
| `doc/backlog.md` | Product backlog (managed by Product-Owner agent) |
| `doc/stories/` | User stories `HT-{id}.md` (Product-Owner owns) |
| `doc/rfc/` | Architect RFCs `RFC-HT-{id}-{slug}.md` — implementation contracts for Feature-Engineer |
| `doc/bugs/` | QA-Orchestrator bug reports |
| `doc/security/` | Security-Orchestrator findings |
| `CHANGELOG.md` | All changes logged here under `[Unreleased]` |

## Data Model

| Entity | Key Fields |
|---|---|
| `Device` | `name`, `type` (DeviceType), `ip`, `mac`, `os`, `notes`, `location_id`, `created_at`, `updated_at` |
| `Connection` | `source_id`, `target_id`, `type` (ConnectionType), `label` |
| `Location` | `name`, `type` (rack\|geo), `lat`, `lng`, `rack`, `row`, `parent_id` |
| `Tag` | `name`, `color` |
| `DeviceTag` | `device_id`, `tag_id` |
| `CustomField` | `device_id`, `key`, `value` |
| `User` | `username`, `email`, `password_hash`, `role` |
| `DiagramLayout` | `name`, `cytoscape_json` |

## Roles & Auth

- Three roles: `Admin`, `Contributor`, `Reader`
- Passwords hashed with bcrypt via `passlib`
- Sessions via JWT (python-jose), enforced in `src/api/middleware/auth.py`
- First admin created from `ADMIN_EMAIL` + `ADMIN_PASSWORD` in `.env` on first boot
- Concurrency: last-write-wins on diagram saves (no locking, v1)

## Canvas & Map Integration

**Cytoscape.js** (topology canvas):
- Embedded via `ui.add_body_html()` + `ui.run_javascript()` in `src/ui/components/canvas.py`
- Node/edge data flows: DB records → Python dict → JSON → Cytoscape elements
- Events (node moved, edge drawn) call back via `POST /api/diagram/` endpoints
- Supports drag, pan, zoom, `cy.png()` and `cy.svg()` for exports

**Leaflet.js** (map view):
- Embedded same pattern in `src/ui/components/map_view.py`
- Uses OpenStreetMap tiles — no API key required
- Location entities with `lat`/`lng` rendered as markers
- Click marker → sidebar shows devices at that location

## Hard Constraints

- Files ≤ 250 lines (hard cap 400)
- No `print()` or `logging.*` — use `src/utils/logger.py` (Loguru)
- No `Any` types in Python — use explicit types or `Union`
- Pure domain functions in `src/domain/` must have zero side effects
- All API input validated by Pydantic before reaching service layer
- Never store raw passwords — always bcrypt via `auth.py`
- `src/ui/` never imports from `src/repositories/` directly
- Always use `.venv` virtual environment for local development — never install into system Python

## Agent Roster

| Agent | Model | Role | Principle | Delegates To | User-invocable |
|---|---|---|---|---|---|
| `product-owner` | Opus 4.6 | Requirements → user stories → backlog → delegate to project-manager | **Kano Model** — classify every requirement as basic/performance/delighter before writing a user story | Project-Manager | Yes |
| `project-manager` | Opus 4.6 | Orchestrator. Decomposes tasks, delegates to specialists, verifies quality gates | **Critical Path Method (CPM)** — map task dependencies, identify the critical path, and sequence delegation to eliminate bottlenecks | Architect, Feature-Engineer, UX-Designer, Refactoring-Specialist, QA-Orchestrator, QA-Fixer, Security-Orchestrator, Code-Reviewer, Test-Automation-Engineer, User-Simulator | Yes |
| `architect` | Sonnet 4.6 | RFC blueprints. Design only — no code changes | **Parnas's Information Hiding** — every module boundary must hide one design decision that can change independently | Feature-Engineer, UX-Designer | No (via project-manager) |
| `feature-engineer` | Sonnet 4.6 | TDD implementation from RFCs | **Strict Red-Green-Refactor** — no production line is written without a failing test first; no refactor until green | Test-Automation-Engineer, Code-Reviewer | No (via project-manager) |
| `ux-designer` | Sonnet 4.6 | NiceGUI UI, Cytoscape/Leaflet canvas quality, WCAG 2.1 AA | **Fitts's Law** — size and placement of every interactive element must be justified by target acquisition time = f(distance, size) | Feature-Engineer | No (via project-manager) |
| `refactoring-specialist` | Sonnet 4.6 | File splits, dead code, complexity reduction | **Connascence Taxonomy** — classify every coupling by type (name → type → meaning → position → algorithm) before removing it | Code-Reviewer | No (via project-manager) |
| `qa-orchestrator` | Haiku 4.5 | Launches 10 parallel bug-finder lanes, aggregates report | **ODC at dispatch** — tag each lane with a defect type (function/interface/assignment/timing/…) so lanes are non-overlapping and cover all classes | Bug-Finder ×10 | No (via project-manager) |
| `bug-finder` | Haiku 4.5 | Worker — hunts defects per ODC lane | **Boundary Value Analysis + Equivalence Partitioning** — every input domain must be tested at its edges and one representative per partition | Test-Automation-Engineer | No (internal) |
| `qa-fixer` / `qa-remediation` | GPT-5.3-Codex | TDD bug remediation | **5-Whys / Ishikawa** — each fix must trace to a root cause category before a patch is written | Test-Automation-Engineer, Code-Reviewer | No (via project-manager) |
| `security-orchestrator` | Sonnet 4.6 | Launches 10 parallel security-auditor lanes | **Attack Surface Reduction (NIST SP 800-53 SA-11)** — quantify attack surface delta on every dispatch; assign lanes by surface area, not evenly | Security-Auditor ×10, Architect (structural findings) | No (via project-manager) |
| `security-auditor` | Haiku 4.5 | Worker — STRIDE-based vulnerability hunting | **STRIDE per-element** — each model element (process, data store, data flow, external entity) gets its own STRIDE pass, not just the system as a whole | — | No (internal) |
| `code-reviewer` | GPT-5.3-Codex | Pre-push gate — rejection matrix walk | **Lehman's Laws of Software Evolution** — flag changes that pass correctness checks but increase complexity (Law of Increasing Complexity) or erode familiarity | — | No (via project-manager) |
| `test-automation-engineer` | Sonnet 4.6 | Adversarial pytest tests, coverage gap analysis | **Mutation Testing** — measure mutation score (target ≥ 80% killed) as the real coverage proxy; line/branch coverage is a floor, not a ceiling | — | No (via project-manager) |
| `user-simulator` | Opus 4.6 | Persona-driven Playwright E2E sessions | **GOMS Model** — each persona session must define explicit Goals, Operators, Methods, and Selection rules before executing Playwright steps | QA-Fixer | No (via project-manager) |

## Core Workflows

```
New feature:                     Product-Owner → Project-Manager → Architect → Feature-Engineer → Code-Reviewer
UI improvement:                  Project-Manager → UX-Designer → (Feature-Engineer if new API needed) → Code-Reviewer
Bug fix:                         Project-Manager → QA-Fixer → Code-Reviewer
Bug discovery:                   Project-Manager → QA-Orchestrator → 10× Bug-Finder → QA-Fixer → Code-Reviewer
Security audit (tactical):       Project-Manager → Security-Orchestrator → 10× Security-Auditor → QA-Fixer → Code-Reviewer
Security audit (structural):     Project-Manager → Security-Orchestrator → 10× Security-Auditor → Architect → Feature-Engineer → Code-Reviewer
Refactoring:                     Project-Manager → Refactoring-Specialist → Code-Reviewer
Exploratory QA:                  Project-Manager → User-Simulator → QA-Fixer → Code-Reviewer
```

## Escalation & Circuit Breaker Policy

Every agent below Project-Manager must observe:

- **2-rejection rule**: If Code-Reviewer rejects the same change twice with the same objection, do NOT retry. Surface to Project-Manager with: original task, repeated objection, and attempted fix.
- **Architectural rejection**: If Code-Reviewer verdict includes `Route: ESCALATE TO ARCHITECT VIA PROJECT-MANAGER`, the receiving agent must NOT retry — surface immediately to Project-Manager.
- **Project-Manager circuit breaker**: If the same correction loop fires twice on the same issue, escalate to the user with both agent perspectives.
- **Security structural findings**: Security-Orchestrator routes structural vulnerabilities to Architect, not QA-Fixer. QA-Fixer handles only tactical (line-level) fixes.

## Pre-Push Quality Gate (Project-Manager enforces)

```bash
docker compose exec api pytest                              # all tests pass
docker compose exec api mypy src/ --ignore-missing-imports  # zero type errors
docker compose build                                        # images build clean
```

Code-Reviewer must be invoked on the full `git diff` — pipeline does not complete without an `APPROVED` verdict.
