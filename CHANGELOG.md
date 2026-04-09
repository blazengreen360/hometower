# Changelog

All notable changes to Hometower will be documented in this file.

## [Unreleased]

### Fixed
- Canvas: replaced non-existent `cy.renderedToModel()` with manual zoom/pan coordinate conversion in drop handler — fixes all palette drag-drop device creation
- Canvas: bounded retry for Cytoscape CDN race condition (max 50 attempts × 100ms)
- Canvas: fixed 0-height `#cy` container by overriding NiceGUI `.row` align-items with stretch + absolute-fill wrapper
- Device service: wired `validate_mac()` in create and update paths — MAC addresses now normalized to uppercase


### Added
- HT-004: Device-to-device connections
  - `src/models/connection.py` — `Connection`, `ConnectionCreate`, `ConnectionUpdate`, `ConnectionResponse` SQLModel models (UUID PK, FK to devices.id for source and target)
  - `src/domain/connections.py` — pure function `validate_no_self_loop()` (raises ValueError on source==target)
  - `src/repositories/connection_repository.py` — full CRUD + paginated/filtered `get_all()` + `count_by_device()` (counts where device is source OR target)
  - `src/services/connection_service.py` — `create`, `get_by_id`, `get_all`, `update`, `delete` with self-loop and device-existence validation
  - `src/api/routers/connections.py` — `GET/POST /api/connections/`, `GET/PATCH/DELETE /api/connections/{id}` (Contributor writes, Reader reads; source_id/target_id filter params)
  - `alembic/versions/004_create_connections_table.py` — `connections` table with PG_UUID/PG_ENUM, FKs, no-self-loop CHECK constraint, indexes, `updated_at` trigger
  - Wired `_count_device_connections()` in `device_service.py` to use `connection_repository.count_by_device()` — device with active connections now blocked from deletion (HTTP 400)
  - `src/ui/pages/topology.py` — `_load_canvas_data()` now fetches connections from `GET /api/connections/` and builds Cytoscape edge elements
  - `src/ui/components/canvas.py` — added `addEdgeToCanvas()` helper; shift+click two nodes to draw a connection (POST /api/connections/); right-click edge to delete
  - `docker-compose.yml` — added `./tests` and `./alembic` bind mounts so new files are live-reflected without rebuilding
  - 19 new tests (2 unit + 17 integration); all 109 tests pass; mypy zero errors; build clean

- HT-003: Basic Topology Canvas with Drag-Drop
  - `src/models/diagram.py` — `DiagramLayout`, `DiagramLayoutCreate`, `DiagramLayoutResponse`, `DiagramLayoutSummary`, `PaginatedDiagramSummary` SQLModel models (UUID PK, JSON column for Cytoscape state)
  - `src/repositories/diagram_repository.py` — `create`, `get_by_id`, `get_all`, `delete`
  - `src/services/diagram_service.py` — orchestrates diagram CRUD with HTTP 404 guards
  - `src/api/routers/diagrams.py` — `GET/POST /api/diagrams/`, `GET/DELETE /api/diagrams/{id}` (Contributor creates, Reader reads, Admin deletes)
  - `alembic/versions/003_create_diagram_layouts_table.py` — `diagram_layouts` table with JSONB column
  - `src/ui/components/canvas.py` — Cytoscape.js 3.28.1 canvas component (CDN), drag events, context menu, palette drop handler, preset/cose layout
  - `src/ui/components/device_palette.py` — HTML5 drag-and-drop palette sidebar with all DeviceType cards
  - `src/ui/components/device_detail.py` — right-side detail panel, listens for `ht:node-selected` custom event
  - `src/ui/pages/topology.py` — NiceGUI `/topology` page with auth guard, three-column layout, Save Layout button
  - `src/ui/design/tokens.py` — added `DEVICE_SHAPES` mapping all 13 `DeviceType` values → Cytoscape shape strings
  - 13 new integration tests; all 90 tests pass; mypy zero errors


  - `src/models/device.py` — `Device`, `DeviceCreate`, `DeviceUpdate`, `DeviceResponse` SQLModel models (UUID PK, MAC format validator)
  - `src/domain/devices.py` — pure functions: `validate_mac()`, `validate_ip()`, `validate_device_deletable()`
  - `src/repositories/device_repository.py` — full CRUD + paginated `get_all()` + `count()`
  - `src/services/device_service.py` — `create`, `get_by_id`, `get_all`, `update`, `delete` with domain validation
  - `src/api/routers/devices.py` — `POST/GET/PATCH/DELETE /api/devices/` with RBAC (Contributor writes, Reader reads)
  - `alembic/versions/002_create_devices_table.py` — `devices` table + `device_type` enum + indexes + `updated_at` trigger
  - 31 new tests (17 unit + 14 integration); all 69 tests pass

- HT-001: User authentication and session management
  - First-boot admin creation from `ADMIN_EMAIL` / `ADMIN_PASSWORD` env vars
  - JWT login via `POST /api/auth/login` (HS256, 24h expiry)
  - Stateless logout via `POST /api/auth/logout`
  - `AuthMiddleware` for JWT decode and `request.state` injection
  - `src/domain/rbac.py` — `can_perform()` and `require_role()` dependency
  - `src/models/user.py` — `User`, `UserCreate`, `UserUpdate`, `UserResponse` SQLModel models
  - `src/models/types.py` — `DeviceType`, `ConnectionType`, `Role`, `LocationType` enums
  - `src/repositories/user_repository.py` — full CRUD + count
  - `src/services/auth_service.py` — `authenticate()`, `create_first_admin_if_needed()`
  - `src/utils/auth.py` — bcrypt helpers, JWT create/decode
  - `src/utils/settings.py` — Pydantic settings from `.env`
  - `src/utils/logger.py` — Loguru singleton
  - `src/utils/db.py` — SQLModel engine, `get_session()` FastAPI dependency
  - `src/ui/pages/login.py` — NiceGUI login page at `/login`
  - `src/ui/design/tokens.py` — design system constants
  - Alembic migration `001_initial_schema.py` — `users` table, enum, index, trigger
  - Full project scaffolding: `Dockerfile`, `docker-compose.yml`, `alembic.ini`, `.env.example`
  - Unit tests for RBAC domain functions
  - Integration tests for auth endpoints and middleware

### Fixed
- Topology canvas initialization race with dynamically injected Cytoscape CDN script
  - `src/ui/components/canvas.py` now retries `initCanvas(...)` until `window.cytoscape` is available and the `#cy` container has non-zero dimensions before creating the graph instance
  - `src/ui/components/canvas.py` now uses absolute fill positioning for `#cy` (`top/right/bottom/left: 0`) to prevent flex wrapper height-chain collapse
- Topology canvas visibility regression (0px height)
  - `src/ui/pages/topology.py` now forces the three-column body row to use `flex-wrap: nowrap` and `align-items: stretch`, and sets `min-height: 0` on the canvas column
  - `src/ui/components/canvas.py` now wraps `#cy` in an absolute-fill container while `#cy` uses `width: 100%; height: 100%` to keep non-zero dimensions even if Cytoscape mutates inline styles
