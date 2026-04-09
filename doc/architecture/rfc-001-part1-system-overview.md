# RFC-001 Part 1: Phase 1 System Overview

**Status:** Approved  
**Author:** Architect  
**Date:** 9 April 2026  
**Parts:** [Part 1 (this)] · [Part 2 – Data Model](rfc-001-part2-data-model.md) · [Part 3 – API Layer](rfc-001-part3-api-layer.md) · [Part 4 – Integrations](rfc-001-part4-integrations.md) · [Part 5 – Auth & Ops](rfc-001-part5-auth-ops.md)

---

## 1. Overview and Goals

Hometower is a self-hosted homelab inventory tool. Its core insight is that **the topology diagram is the inventory** — every node drawn on the canvas creates a database record, and every database record appears as a canvas node. There is no separate import/export step in normal use.

Phase 1 delivers: device CRUD, topology canvas (Cytoscape.js), geographic map (Leaflet.js), tag and custom field systems, location management, RBAC, JSON export/import, and dark mode.

---

## 2. Layer Architecture

```
NiceGUI UI  ──HTTP──►  FastAPI Routers  ──►  Services  ──►  Repositories  ──►  PostgreSQL
                                                │
                                                ▼
                                          Domain Logic
                                     (pure Python, no I/O)
```

### 2.1 Layer Responsibilities

| Layer | Package | Responsibility |
|---|---|---|
| UI | `src/ui/` | NiceGUI pages, Cytoscape.js and Leaflet.js embedding, user interaction |
| API | `src/api/routers/` | Route handling, Pydantic validation, JWT + RBAC checks |
| Middleware | `src/api/middleware/` | JWT decode, request logging |
| Services | `src/services/` | Orchestrates domain logic + repositories, owns DB transactions |
| Domain | `src/domain/` | Pure business rules: validation, graph logic, RBAC rules |
| Repositories | `src/repositories/` | SQLModel queries — sole owner of `Session` |
| Models | `src/models/` | SQLModel classes (DB schema + Pydantic schema combined) |
| Utils | `src/utils/` | Loguru logger, bcrypt/JWT helpers, DB session factory |

### 2.2 Import Direction Rules

These rules are **absolute** — violations are rejected at code review:

```
src/ui/        → may import from src/services/, src/models/, src/utils/
src/ui/        → NEVER import from src/repositories/ directly
src/api/       → may import from src/services/, src/models/, src/utils/
src/services/  → may import from src/domain/, src/repositories/, src/models/, src/utils/
src/domain/    → may ONLY import from src/models/types.py
src/repositories/ → may import from src/models/, src/utils/db.py
```

---

## 3. Directory Structure

### 3.1 `src/` Package Tree

```
src/
├── api/
│   ├── app.py                        # FastAPI app, middleware registration, ui.run_with()
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── auth.py                   # JWT decode + RBAC; attaches user to request.state
│   │   └── logging.py                # Loguru request/response logging
│   └── routers/
│       ├── __init__.py
│       ├── auth.py                   # POST /api/auth/login, /logout
│       ├── devices.py                # GET/POST /api/devices, GET/PATCH/DELETE /api/devices/{id}
│       ├── connections.py            # CRUD /api/connections
│       ├── locations.py              # CRUD /api/locations
│       ├── tags.py                   # CRUD /api/tags + /api/devices/{id}/tags
│       ├── custom_fields.py          # CRUD /api/devices/{id}/fields
│       ├── diagrams.py               # GET/POST /api/diagrams, GET/DELETE /api/diagrams/{id}
│       ├── users.py                  # Admin CRUD /api/users
│       ├── export_.py                # GET /api/export/json
│       ├── import_.py                # POST /api/import/json
│       └── search.py                 # GET /api/devices/search
├── domain/
│   ├── __init__.py
│   ├── devices.py                    # validate_ip(), validate_mac(), check_device_deletable()
│   ├── topology.py                   # detect_cycle(), find_path(), get_neighbors()
│   ├── inventory.py                  # filter_devices(), paginate(), build_search_query()
│   ├── export_.py                    # serialize_inventory(), deserialize_inventory()
│   └── rbac.py                       # can_perform(), require_role() dependency
├── models/
│   ├── __init__.py
│   ├── types.py                      # DeviceType, ConnectionType, Role, LocationType enums
│   ├── device.py                     # Device, DeviceTag, CustomField SQLModel models
│   ├── connection.py                 # Connection SQLModel model
│   ├── location.py                   # Location SQLModel model
│   ├── user.py                       # User SQLModel model
│   └── diagram.py                    # DiagramLayout SQLModel model
├── repositories/
│   ├── __init__.py
│   ├── device_repository.py          # create, get_by_id, get_all, update, delete, search
│   ├── connection_repository.py      # create, get_by_id, get_by_device, update, delete
│   ├── location_repository.py        # create, get_by_id, get_all, get_children, update, delete
│   ├── tag_repository.py             # create, get_by_id, get_all, assign, remove, update, delete
│   ├── custom_field_repository.py    # create, get_by_device, get_by_key, update, delete
│   ├── user_repository.py            # create, get_by_id, get_by_email, get_all, update, delete
│   └── diagram_repository.py         # create, get_active, get_by_id, get_all, delete
├── services/
│   ├── __init__.py
│   ├── auth_service.py               # authenticate(), create_jwt(), first_boot_admin()
│   ├── device_service.py             # create, read, list, update, delete (validates connections)
│   ├── connection_service.py         # create, read, list, update, delete
│   ├── location_service.py           # create, read, list, update, delete, get_hierarchy
│   ├── tag_service.py                # create, read, list, assign, remove, update, delete
│   ├── custom_field_service.py       # create, read_for_device, update, delete
│   ├── diagram_service.py            # save_layout, get_active_layout, list, delete
│   ├── user_service.py               # create, read, list, update, delete, change_password
│   ├── export_service.py             # build_export_payload()
│   └── import_service.py             # parse_import_payload(), apply_import()
├── ui/
│   ├── __init__.py
│   ├── pages/
│   │   ├── __init__.py
│   │   ├── login.py                  # /login — NiceGUI login form
│   │   ├── topology.py               # /topology — Cytoscape.js canvas page
│   │   ├── map_view.py               # /map — Leaflet.js map page
│   │   ├── inventory.py              # /inventory — searchable table page
│   │   └── admin.py                  # /admin — user management (Admin only)
│   ├── components/
│   │   ├── __init__.py
│   │   ├── canvas.py                 # Cytoscape.js HTML + JS injection + event bridge
│   │   ├── map_component.py          # Leaflet.js HTML + JS injection + event bridge
│   │   ├── device_palette.py         # Draggable device type sidebar
│   │   ├── device_detail.py          # Device detail side panel
│   │   ├── nav_bar.py                # Top navigation bar
│   │   └── search_bar.py             # Search and filter controls
│   └── design/
│       └── tokens.py                 # Colors, spacing, font sizes (no hardcoded values elsewhere)
└── utils/
    ├── __init__.py
    ├── logger.py                     # Loguru singleton: `from src.utils.logger import logger`
    ├── auth.py                       # hash_password(), verify_password(), create_jwt(), decode_jwt()
    └── db.py                         # engine, SessionFactory, get_session() FastAPI dependency
```

### 3.2 Project Root Tree

```
hometower/
├── src/                              # Application source (see above)
├── tests/
│   ├── conftest.py                   # Fixtures: test DB, test client, JWT helper
│   ├── fixtures/
│   │   └── sample_data.py            # Seed data factories (no file I/O)
│   ├── unit/                         # Domain-only; no mocking required
│   │   ├── test_domain_devices.py
│   │   ├── test_domain_topology.py
│   │   ├── test_domain_inventory.py
│   │   ├── test_domain_export.py
│   │   └── test_domain_rbac.py
│   └── integration/                  # FastAPI TestClient + real test DB
│       ├── test_auth.py
│       ├── test_devices.py
│       ├── test_connections.py
│       ├── test_locations.py
│       ├── test_tags.py
│       ├── test_custom_fields.py
│       ├── test_diagrams.py
│       ├── test_users.py
│       ├── test_export_import.py
│       └── test_search.py
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial_schema.py
├── doc/
│   ├── architecture/                 # ← this RFC lives here
│   ├── backlog.md
│   ├── stories/
│   └── bugs/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── alembic.ini
├── .env.example
└── AGENTS.md
```

---

## 4. Design Decisions Record

| Decision | Choice | Reason |
|---|---|---|
| Unified server | NiceGUI + FastAPI via `ui.run_with()` | Single port, shared Pydantic models, no CORS |
| Position storage | Stored in `diagram_layouts.cytoscape_json`, not on `Device` | Device is data; layout is presentation |
| Last-write-wins | No locking or optimistic concurrency | Solo homelab use; adds no complexity |
| Token revocation | Not in v1 | Stateless JWT is sufficient; adds no complexity |
| Migrations | Alembic autogenerate from SQLModel models | Single source of truth; no manual sync |
| UUID primary keys | All tables use `gen_random_uuid()` | Safe for future federation; avoids sequential ID guessing |
