# Hometower

**Homelab modelling, inventory management, and documentation platform** — Cloudcraft for homelabbers. Draw your infrastructure as an interactive topology diagram or pin locations on a geographic map. Every node you place and every connection you draw populates a searchable, filterable inventory database. Attach documentation, track lifecycle, and generate scoped reports for planning and compliance.

**Status**: Phase 1 complete with 67 features shipped. Multi-workspace, theme engine (dark/light/midnight), device containers, services with dependencies, device cloning, topology search/filter, and more. Ready for Phase 2 multi-workspace and auto-discovery integrations.

## Key Features

### Modelling & Visualization
- **Topology Canvas** — Drag & drop devices, draw connections, device containers, type filter overlay, zoom/pan controls, keyboard shortcuts (Ctrl+A, Ctrl+D, Ctrl+Z, F to fit)
- **Diagram Layouts** — Save/load/rename multiple canvas layouts per topology with autosave on drag; supports multiple views of same infrastructure
- **Map View** — Geographic pin locations for distributed infrastructure (Leaflet.js + OpenStreetMap)
- **Service Dependencies** — Visualize application dependencies with cycle detection; understand critical paths

### Inventory Management
- **Inventory List** — Searchable/filterable device table with tags, custom fields, status tracking, bulk device placement from stencil panel
- **Device Detail Panel** — Full CRUD with status (Active/Offline/Maintenance/Planned/Decommissioned), tags, custom fields, connections, services, notes, duplication
- **Searchable Database** — Type-ahead search across devices, IPs, tags, services, locations; structured query operators (type:, ip:, tag:, status:, service:)
- **Bulk Actions** — Multi-select device operations (tag, status change, delete, clone, export)
- **Device Types** — 13 device types (Server, Switch, Router, NAS, VM, Container, SBC, UPS, Workstation, Firewall, LoadBalancer, VLAN, Subnet, etc.)

### Documentation & Knowledge Base
- **Device Notes** — Per-device documentation field for runbooks, configurations, troubleshooting
- **Custom Fields** — Key-value pairs for model numbers, serial numbers, purchase dates, warranty info, cost, IP addressing scheme
- **Quick Links** — Per-device links to management interfaces, wiki articles, monitoring dashboards (planned feature)
- **Tags** — Hierarchical tagging system for organization (tier, environment, function, etc.)
- **Import/Export** — Full JSON backup/restore; supports workspaces, topologies, diagram layouts, device metadata

### Operational Tracking
- **Networks & Subnets** — VLAN management, IP address management (IPAM), subnet tracking with utilization metrics
- **Services** — Per-device services with name, port, protocol, status; service dependencies with cycle detection
- **Connection Management** — Physical and logical connection tracking; device-to-device relationship mapping
- **Device Containers** — Logical or physical grouping (rack, PDU, cluster, zone)

### Reporting & Planning
- **Dashboard** — Inventory summary, recent activity, device status breakdown, search quick-access
- **Health Check Endpoint** — `/api/health` for monitoring and liveness probes
- **Reports** (Planned) — Generate scoped reports on topology, inventory, devices, networks, services by workspace/topology/location

### Administration & Security
- **Multi-Workspace** — Workspace-scoped topologies; team support via role-based access
- **RBAC** — Admin / Contributor / Reader roles with fine-grained endpoint protection and optimistic-locking concurrency control
- **Authentication** — JWT + HttpOnly cookie auth, password-change self-service, session expiry detection with transparent re-login flow
- **Audit Trail** — Complete device history (planned feature for Phase 2)
- **Theme Engine** — Dark (Control Room), Light (Blueprint), Midnight (OLED) themes with CSS custom properties; theme preference persisted per user

## Views

| View | Description |
|---|---|
| **Topology Canvas** | Interactive diagram with Cytoscape.js; drag nodes, draw connections, group devices in containers, type filter overlay, zoom/fit controls |
| **Inventory List** | Server-side search & filter (type:, ip:, tag:, location:, status:, service:, free text); live edit, bulk actions |
| **Device Detail** | Full CRUD with status, tags, custom fields, services, notes, parent container, duplication |
| **Map View** | Geographic map with pinned locations; click to show devices at that location |
| **Diagram Layouts** | Save/load/rename canvas positions; autosave on drag; conflict detection on reload |
| **Dashboard** | Recent activity (5 latest devices), inventory stat cards, quick-action buttons |
| **Settings** | Locations (hierarchy), Users (RBAC), Passwords (self-service change), Data (import/export), System info |

## What You Can Inventory

| Category | Types |
|---|---|
| Physical | Server, Switch, Router, NAS, UPS, SBC, Workstation |
| Virtual | VM, LXC Container |
| Services | Docker Container, Application (Plex, Nextcloud, Vaultwarden, etc.) |
| Network | VLAN, Subnet |
| Organization | Location, Container, Service with Dependencies |

## Tech Stack

| Layer | Technology |
|---|---|
| UI | NiceGUI |
| Topology canvas | Cytoscape.js (embedded in NiceGUI) |
| Map view | Leaflet.js + OpenStreetMap (embedded in NiceGUI) |
| API | FastAPI + Pydantic |
| ORM | SQLModel + Alembic |
| Database | PostgreSQL 16 |
| Auth | passlib (bcrypt) + python-jose (JWT) |
| Logging | Loguru |
| Deployment | Docker Compose |

## Project Structure

```
hometower/
├── src/
│   ├── api/                         # FastAPI + NiceGUI shared server
│   │   ├── routers/                 # REST endpoints (devices, connections, diagrams, workspaces, services,
│   │   │                            #              users, auth, health, system, data_transfer, locations, tags)
│   │   ├── middleware/              # JWT decode, RBAC enforcement, security headers, rate limiting
│   │   ├── dependencies/            # RBAC gate functions, session dependency
│   │   └── app.py                   # FastAPI app + NiceGUI mount via ui.run_with()
│   ├── domain/                      # Pure functions (no I/O, no DB, no FastAPI, no Loguru imports)
│   │   ├── auth.py                  # Password strength validation
│   │   ├── devices.py               # Device validation, parent cycle detection, name collision
│   │   ├── services.py              # Port validation, dependency cycle detection (BFS)
│   │   ├── rbac.py                  # Role hierarchy + permission checks (pure)
│   │   ├── search.py                # Query parser (type:, ip:, tag:, location:, status:, service:)
│   │   ├── export.py                # Export/import domain logic, topological sort, cycle detection
│   │   ├── connections.py           # Validation, self-loop detection
│   │   └── locations.py             # Location hierarchy validation
│   ├── models/                      # SQLModel (table + Pydantic schema combined)
│   │   ├── types.py                 # All enums: DeviceType, ConnectionType, Role, LocationType,
│   │   │                            # DeviceStatus, ServiceProtocol, ServiceStatus
│   │   ├── device.py, connection.py, location.py, user.py, workspace.py, topology.py
│   │   ├── diagram.py, service.py, service_dependency.py, tag.py, custom_field.py
│   │   └── export_schema.py         # Pydantic-only export envelope (no table model)
│   ├── repositories/                # Database access (SQLModel Session + SQL builders only)
│   │   ├── device_repository.py     # CRUD + search, enrichment, batch operations
│   │   ├── diagram_repository.py    # CRUD + row-locking for concurrency
│   │   └── [other_entities]_repository.py
│   ├── services/                    # Orchestration layer (domain + repos, owns transactions)
│   │   ├── auth_service.py          # Login, password change, token revocation
│   │   ├── device_service.py        # Device CRUD, enrichment, validation
│   │   ├── diagram_service.py       # Diagram CRUD + autosave conflict handling
│   │   ├── export_service.py, import_service.py, import_validation.py
│   │   └── [feature_area]_service.py
│   ├── ui/                          # NiceGUI pages and components
│   │   ├── pages/                   # topology, inventory, dashboard, device_edit,
│   │   │                            # login, settings_*, workspaces, workspace_detail
│   │   ├── components/              # canvas.js, canvas_events, canvas_shortcuts, canvas_styles,
│   │   │                            # device_detail_panel, connection_detail_panel,
│   │   │                            # app_shell, sidebar, breadcrumb, toast, auth_guard,
│   │   │                            # inventory_*, device_*, topology_layout_*
│   │   ├── design/                  # tokens.py (CSS custom property vars, color palettes),
│   │   │                            # theme_engine.py (theme builder, client-side applier)
│   │   └── services/                # UI helpers (topology_data.py, topology_layout.py)
│   ├── utils/
│   │   ├── logger.py                # Loguru setup — use everywhere (never print/logging.*)
│   │   ├── auth.py                  # JWT create/decode, password hashing, TOTP helpers
│   │   ├── settings.py              # Pydantic-settings (DATABASE_URL, SECRET_KEY, etc.)
│   │   ├── db.py                    # Session dependency for routes
│   │   └── cli.py                   # Command-line tools (reset password, etc.)
│   └── __version__.py               # Single source of truth for version string
├── tests/
│   ├── unit/                        # Domain logic tests (no DB, no network, pure Python)
│   ├── integration/                 # API + test PostgreSQL (fixtures + RBAC coverage)
│   ├── e2e/                         # Playwright browser automation (optional)
│   └── conftest.py                  # Fixtures (session, client, tokens, users, sample data)
├── alembic/
│   ├── versions/                    # Migration scripts (001_*, 002_*, etc.)
│   └── env.py, alembic.ini          # Alembic config
├── doc/
│   ├── backlog.md                   # Product backlog (current features, sprints)
│   ├── stories/                     # User stories HT-001 through HT-067 (active)
│   ├── stories/done/                # Completed stories (archived)
│   ├── bugs/                        # Active QA bug reports (ODC classification)
│   ├── bugs/completed/              # Resolved bugs with Pipeline Verdict: ALL_CLEAR
│   ├── security/                    # Active security findings
│   ├── security/completed/          # Resolved security findings (compliance archive)
│   ├── tracker.md                   # Engineering tracker (open issues, blockers)
│   ├── progress.md                  # Active pipeline state
│   ├── design/                      # UX specs (site-map, wireframes, components, themes)
│   └── rfc/                         # Architecture RFCs (implementation contracts)
├── .env.example                     # Environment template (copy → .env before first run)
├── docker-compose.yml               # Multi-service stack: api (FastAPI+NiceGUI), postgres, pgadmin
├── Dockerfile                       # Python 3.11+ minimal image
├── requirements.txt                 # Python dependencies (FastAPI, SQLModel, NiceGUI, Loguru, etc.)
├── pytest.ini                       # Pytest config (test discovery, markers, output)
├── CHANGELOG.md                     # All changes under [Unreleased] and per-version headers
├── AGENTS.md                        # AI agent guidance (architecture constraints, patterns)
├── CLAUDE.md                        # Symlink to AGENTS.md (for Claude Code compatibility)
└── README.md                        # This file
```

## Getting Started

```bash
git clone https://github.com/your-org/hometower
cd hometower
cp .env.example .env
# Edit .env: set ADMIN_EMAIL, ADMIN_PASSWORD, SECRET_KEY, DB_PASSWORD, DATABASE_URL
# Generate strong secrets:
# SECRET_KEY:   python -c "import secrets; print(secrets.token_hex(32))"
# DB_PASSWORD:  python -c "import secrets; print(secrets.token_urlsafe(24))"
docker compose up -d
```

**First boot**: `ADMIN_EMAIL` and `ADMIN_PASSWORD` from `.env` create the first admin account (one-time, then deleted from env).

**Access**:
- **UI**: http://localhost:8080
- **API docs**: http://localhost:8080/docs (interactive Swagger)
- **PgAdmin**: http://localhost:5050 (optional, for DB inspection)

### Development Setup

```bash
# Create local virtualenv
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start services
docker compose up -d

# Run migrations
docker compose exec api alembic upgrade head

# Run tests (unit + integration)
docker compose exec api pytest

# Type check
docker compose exec api mypy src/ --ignore-missing-imports

# Run single test file
docker compose exec api pytest tests/unit/test_devices.py -v

# Generate coverage report
docker compose exec api pytest --cov=src --cov-report=term-missing

# View logs
docker compose logs -f api
```

### Architecture Enforcement (zero-tolerance checks)

```bash
# Pure domain layer (no FastAPI, SQLModel, or logging imports)
grep -rn "from fastapi\|from sqlmodel\|from loguru" src/domain/ --include="*.py"  # must return nothing

# UI never imports repositories directly
grep -rn "from src.repositories" src/ui/ --include="*.py"  # must return nothing

# No print() statements (use Loguru instead)
grep -rn "print(" src/ --include="*.py" | grep -v test | grep -v __pycache__  # must return nothing
```

## Architecture

Strict layered architecture — import direction enforced:

```
NiceGUI UI  →  FastAPI Routers  →  Services  →  Repositories  →  PostgreSQL
                                       ↑
                                  Domain Logic
                             (pure Python, no I/O)
```

NiceGUI and FastAPI share a single server process via `ui.run_with(fastapi_app)`. Both the UI and the REST API are served on port 8080. API routes are prefixed `/api/`.

### Layer Rules
- **UI** (`src/ui/`) — Never imports from `src/repositories/` or `src/models/` table classes. Calls API via HTTP or uses service layer.
- **API** (`src/api/`) — Validates with Pydantic, enforces auth/RBAC via middleware, delegates to services.
- **Services** (`src/services/`) — Owns transactions. Calls domain functions then repositories.
- **Domain** (`src/domain/`) — Pure functions only. No SQLModel, no FastAPI, no Loguru calls that have side effects.
- **Repositories** (`src/repositories/`) — Only layer with database session access.

## Roles

| Role | Permissions |
|---|---|
| **Admin** | Manage users, full CRUD, backup/restore, all exports |
| **Contributor** | Add/edit/delete devices, connections, locations, tags |
| **Reader** | View topology, map, inventory; search/filter; no writes |

## Data Model

Core entities with **optimistic locking** (`version` field) and **cascading deletes** on device references:

| Entity | Key Fields | Notes |
|---|---|---|
| **User** | id, username, email, password_hash (bcrypt), role (Admin/Contributor/Reader), is_active, token_version (for JWT revocation), created_at | Passwords never exported; first admin seeded from `.env` on first boot |
| **Workspace** | id, owner_id (→ User), name (unique per owner), created_at | Team support; owner can share workspace roles with contributors/readers |
| **Topology** | id, workspace_id (→ Workspace), name (unique per workspace), tags (JSON), created_at | Canvas container; groups devices into distinct diagram tabs |
| **Device** | id, name, type (enum), status (Active/Offline/Maintenance/Planned/Decommissioned), ip (validated), mac (normalized), os, location_id, parent_id (self-ref for containers), version, created_at | Global inventory; can be placed on multiple topologies via DiagramLayout |
| **Connection** | id, source_id, target_id (both → Device CASCADE), type (Ethernet/WiFi/Fibre/iSCSI/NFS/VM/Other), label, created_at | Enforced no-self-loop constraint at Pydantic + DB layer |
| **Location** | id, name, type (rack\|geo), lat, lng (geo bounds validated), rack (name), row (numeric), parent_id (self-ref, sibling-name unique), created_at | Hierarchy for physical racks or geographic regions |
| **Tag** | id, name, color, created_at | Applied to devices for filtering inventory |
| **DeviceTag** | device_id (FK PK), tag_id (FK PK) | Many-to-many device-tag association |
| **CustomField** | id, device_id (FK CASCADE), key, value, created_at | Free key-value metadata (serial_number, warranty, vendor, etc.) |
| **Service** | id, device_id (FK CASCADE), name (unique per device), port (1-65535), protocol (http/https/tcp/udp/other), url, status (running/stopped/unknown), notes | Per-device microservice tracking |
| **ServiceDependency** | service_id (FK PK CASCADE), depends_on_id (FK PK CASCADE) | Directed edges; cycle detection prevents circular dependencies |
| **DiagramLayout** | id, topology_id (FK CASCADE), name, cytoscape_json (node/edge positions), version, created_at | Save/load canvas layouts per topology; autosave on drag with conflict detection |

## Export & Backup

| Type | Format | Access |
|---|---|---|
| Inventory export | JSON (versioned) | All roles |
| Diagram snapshot | PNG / SVG | All roles |
| Full DB backup | pg_dump (.sql) | Admin only |

Import accepts Hometower JSON format. On import, existing records are preserved; conflicts are skipped with a report.

## Concurrency & Conflict Resolution

**Optimistic Locking** — Device and DiagramLayout entities carry a `version` field. All PATCH requests must include the current version; stale versions return HTTP 409 (Conflict). Client automatically retries with fresh data.

**Autosave Serialization** — Diagram autosave (on drag) uses a queued, serialized PATCH flush so out-of-order saves don't corrupt state. Conflicts surface a "reload to sync" banner.

**Row-Level Locking** — Diagram writes (create/update/delete) use `SELECT ... FOR UPDATE` to prevent concurrent mutations on the same layout.

Suitable for small teams and homelabs where simultaneous canvas edits are rare; ready for Phase 2 WebSocket real-time collaboration.

## Roadmap

### Phase 1 ✓ Complete (Shipped)

67 stories delivered including:
- Core inventory CRUD, topology canvas with drag/drop, connections, device containers
- Multi-workspace support, diagram layouts with autosave, device duplication, stencil panel
- Services (with dependencies & cycle detection), search & filter operators, import/export with round-trip parity
- JWT + HttpOnly cookie auth, session expiry detection, self-service password change, RBAC enforcement
- Theme engine (3 themes), health check endpoint, system info page, app shell with dashboard
- 10+ security & concurrency hardening stories (optimistic locking, ownership scoping, input validation)
- 14 QA/design bug remediation stories (canvas robustness, autosave serialization, orphan cleanup)

### Phase 2 (LightTower — team edition)

- Proxmox, Docker, Home Assistant auto-discovery integrations
- Traefik reverse proxy with Let's Encrypt SSL
- Scheduled auto-backups + incremental snapshots
- Audit log for team changes (who/when/what) with export
- LDAP / SSO support (with group mapping to workspace roles)
- Webhook integrations (device state change → Slack/Discord/webhook)
- API token authentication for automation scripts
- Collaborative diagram editing with real-time sync (WebSocket)

## Contributing

Hometower uses AI-assisted agent coordination for all development. Architecture constraints, coding patterns, and workflows are documented in **`AGENTS.md`** (source of truth for all agents and engineers).

### For Contributors
- Read `AGENTS.md` for architecture rules and strict layered design
- All Python code ≤250 lines per file (hard cap 400 for tests)
- Use Loguru (`src/utils/logger.py`) — never `print()` or `logging.*`
- Type-annotated functions; no `Any` types (use `Union` or explicit types)
- Domain layer (`src/domain/`) must be pure (no I/O, no DB, no side effects)
- Every API endpoint requires RBAC gating via `Depends(require_role(...))`
- Test coverage via pytest; run full suite before pushing: `pytest && mypy src/ && docker compose build`

### For AI Agents
- Architect → Feature-Engineer → Test-Automation-Engineer → Code-Reviewer workflow
- 2-rejection rule: if Code-Reviewer rejects the same change twice with same objection, escalate to Project-Manager
- ODC (Orthogonal Defect Classification) for QA: 10 parallel bug-finder lanes by fault type
- RFCs in `doc/rfc/` are implementation contracts; strictly follow diff-level precision
- Security findings routed to Architect if structural; QA-Fixer handles tactical (line-level) issues

## License & Availability

**Hometower** (this project) — Free for hobbyists. Not open source; source code is proprietary.

**LightTower** (Phase 2, team edition) — Closed source, commercial license. Adds multi-user collaboration, auto-discovery integrations (Proxmox/Docker/Home Assistant), LDAP/SSO, audit logging, and webhook integrations.

For licensing questions, contact the project maintainer.

## Support

For questions, bugs, or feature requests, open an issue on GitHub or consult `doc/tracker.md` for known limitations and workarounds.
