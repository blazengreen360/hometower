# Hometower

Self-hosted homelab inventory management — **Cloudcraft for homelabbers**. Draw your infrastructure as an interactive topology diagram or pin locations on a geographic map. Every node you place and every connection you draw populates a searchable, filterable inventory database.

## Views

| View | Description |
|---|---|
| **Topology Canvas** | Drag & drop devices, draw connections, group by rack/location (Cytoscape.js) |
| **Map View** | Pin locations on a geographic map for distributed infrastructure (Leaflet.js) |
| **Inventory List** | Searchable, filterable table with tags and custom fields |
| **Device Detail** | Full record with custom fields, tags, notes, connections |

## What You Can Inventory

| Category | Types |
|---|---|
| Physical | Server, Switch, Router, NAS, UPS, SBC, Workstation |
| Virtual | VM, LXC Container |
| Services | Docker Container, Application (Plex, Nextcloud, Vaultwarden, etc.) |
| Network | VLAN, Subnet |

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
│   ├── api/                    # FastAPI routers and middleware
│   │   ├── routers/            # devices, connections, locations, users, export, auth
│   │   ├── middleware/         # JWT auth, RBAC enforcement, request logging
│   │   └── app.py              # FastAPI app — NiceGUI mounted here via ui.run_with()
│   ├── domain/                 # Pure business logic (no I/O, no DB imports)
│   │   ├── devices.py          # Device validation and business rules
│   │   ├── topology.py         # Graph operations (cycle detection, path finding)
│   │   ├── inventory.py        # Search, filter, and aggregation logic
│   │   ├── export.py           # JSON export/import logic
│   │   └── rbac.py             # Role permission rules
│   ├── models/                 # SQLModel models (DB table + Pydantic schema in one)
│   │   ├── device.py
│   │   ├── connection.py
│   │   ├── location.py
│   │   ├── user.py
│   │   └── types.py            # Enums: DeviceType, ConnectionType, Role
│   ├── repositories/           # Database access (SQLModel sessions only)
│   ├── services/               # Application services (orchestrate domain + repositories)
│   ├── ui/                     # NiceGUI pages and components
│   │   ├── pages/              # topology.py, map.py, inventory.py, device.py, settings.py, admin.py
│   │   ├── components/         # canvas.py, map_view.py, search_bar.py, device_panel.py, sidebar.py
│   │   ├── design/             # tokens.py (design system), global.css
│   │   └── app.py              # NiceGUI startup and routing
│   └── utils/
│       ├── logger.py           # Loguru setup — always use this, never print() or logging.*
│       └── auth.py             # JWT encode/decode, password hashing helpers
├── tests/
│   ├── unit/                   # Domain logic tests (no DB)
│   ├── integration/            # API + DB tests (uses test PostgreSQL)
│   └── conftest.py             # Fixtures: test DB session, test client, sample data
├── migrations/                 # Alembic migration scripts
├── doc/
│   ├── backlog.md              # Product backlog (managed by Product-Manager agent)
│   ├── bugs/                   # QA-Orchestrator bug reports
│   └── security/               # Security-Orchestrator findings
├── .env.example
├── docker-compose.yml
├── CHANGELOG.md
└── AGENTS.md                   # AI agent guidance (symlinked as CLAUDE.md)
```

## Getting Started

```bash
git clone https://github.com/your-org/hometower
cd hometower
cp .env.example .env
# Edit .env: set ADMIN_EMAIL, ADMIN_PASSWORD, SECRET_KEY, DATABASE_URL
docker compose up -d
```

- **UI**: `http://localhost:8080`
- **API docs**: `http://localhost:8080/docs`

First boot reads `ADMIN_EMAIL` and `ADMIN_PASSWORD` from `.env` and creates the admin account if it doesn't exist.

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

| Entity | Key Fields |
|---|---|
| **Device** | name, type (DeviceType), ip, mac, os, notes, location_id, tags[], custom_fields{}, created_at, updated_at |
| **Connection** | source_id, target_id, type (Ethernet/WiFi/Fibre/iSCSI/NFS/VM/Other), label |
| **Location** | name, type (rack\|geo), lat, lng (geo), rack, row (physical), parent_id |
| **Tag** | name, color — applied to devices for filtering |
| **CustomField** | device_id, key, value — free key-value pairs (serial_number, warranty, etc.) |
| **User** | username, email, password_hash (bcrypt), role, created_at |
| **DiagramLayout** | name, cytoscape_json — saved canvas positions |

## Export & Backup

| Type | Format | Access |
|---|---|---|
| Inventory export | JSON (versioned) | All roles |
| Diagram snapshot | PNG / SVG | All roles |
| Full DB backup | pg_dump (.sql) | Admin only |

Import accepts Hometower JSON format. On import, existing records are preserved; conflicts are skipped with a report.

## Concurrency

Last-write-wins on diagram saves. No locking for v1. Suitable for solo homelabers and small teams where simultaneous edits are rare.

## Roadmap — Phase 2 (LightTower — team edition)

- Multi-workspace support
- Proxmox, Docker, Home Assistant auto-discovery integrations
- Traefik reverse proxy with Let's Encrypt SSL
- Scheduled auto-backups
- Audit log for team changes
- LDAP / SSO support
