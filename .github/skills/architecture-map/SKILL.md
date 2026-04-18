---
name: architecture-map
description: Full source tree and key files index for Hometower. Read this when you need to locate a file, understand the directory structure, or find the right module to edit.
---

# architecture-map

## Source Tree

```
src/
├── api/
│   ├── app.py                        # FastAPI + NiceGUI mount via ui.run_with()
│   ├── middleware/
│   │   ├── auth.py                   # JWT decode + RBAC
│   │   ├── rate_limit.py             # slowapi
│   │   └── security_headers.py
│   └── routers/                      # one file per resource
│       ├── auth.py, connections.py, data_transfer.py
│       ├── devices.py, device_sub_routes.py
│       ├── diagrams.py, health.py, locations.py
│       ├── services.py, system.py, tags.py
│       ├── topologies.py, users.py, views.py  # views.py = legacy compat
│       └── workspaces.py
├── domain/                           # pure functions, zero I/O
│   ├── auth.py, connections.py, devices.py
│   ├── export.py, inventory.py, locations.py
│   ├── rbac.py, search.py, services.py
│   └── workspaces.py
├── models/                           # SQLModel = DB table + Pydantic schema
│   ├── types.py                      # all enums
│   ├── device.py, connection.py, location.py
│   ├── tag.py, custom_field.py, user.py, diagram.py
│   ├── service.py, service_dependency.py
│   ├── workspace.py, topology.py
│   └── export_schema.py
├── repositories/                     # SQLModel Session queries, one per model
│   ├── connection_repository.py, custom_field_repository.py
│   ├── device_repository.py, diagram_repository.py
│   ├── location_repository.py, service_repository.py
│   ├── tag_repository.py, topology_repository.py
│   ├── user_repository.py, workspace_repository.py
├── services/                         # orchestrate domain + repos, own transactions
│   ├── auth_service.py, connection_service.py
│   ├── custom_field_service.py, device_service.py
│   ├── device_enrichment_service.py, diagram_service.py
│   ├── export_service.py, import_service.py, import_validation.py
│   ├── location_service.py, service_service.py
│   ├── system_service.py, tag_service.py
│   ├── topology_service.py, user_service.py
│   └── workspace_service.py
├── ui/
│   ├── components/                   # NiceGUI components + JS embeds
│   │   ├── app_shell.py, sidebar.py, breadcrumb.py, toast.py
│   │   ├── canvas.py, canvas_js.py, canvas_js_helpers.py, canvas_js_utils.py
│   │   ├── canvas_events.py, canvas_container_events.py
│   │   ├── canvas_styles.py, canvas_shortcuts.py, canvas_zoom.py
│   │   ├── canvas_mode.py, canvas_tooltip.py
│   │   ├── device_detail_panel.py, device_detail_*.py
│   │   ├── device_palette.py, topology_edit_toggle.py
│   │   ├── topology_layout_bar.py, topology_layout_*.py
│   │   ├── connection_detail_panel.py, inventory_edit_modal.py
│   │   └── dialogs/
│   ├── design/tokens.py              # design system constants
│   ├── pages/
│   │   ├── dashboard.py, inventory.py, topology.py
│   │   ├── workspaces.py, workspace_detail.py
│   │   ├── settings_*.py, login.py, access_denied.py
│   │   └── device_edit.py
│   └── services/                     # UI-layer data helpers (not backend services)
│       ├── topology_data.py, topology_data_helpers.py
│       └── topology_layout.py
└── utils/
    ├── auth.py                       # JWT helpers, hash/verify password
    ├── db.py                         # get_session() dependency
    ├── logger.py                     # Loguru — use everywhere
    └── settings.py                   # pydantic-settings config
```

## Key Files

| File | Purpose |
|---|---|
| `src/models/types.py` | All enums: DeviceType, ConnectionType, Role, LocationType, DeviceStatus, ServiceProtocol, ServiceStatus |
| `src/utils/logger.py` | Loguru instance — import this everywhere |
| `src/utils/auth.py` | JWT helpers, `hash_password()`, `verify_password()` |
| `src/utils/settings.py` | pydantic-settings: `DATABASE_URL`, `SECRET_KEY`, etc. |
| `src/api/middleware/auth.py` | JWT decode + RBAC enforcement |
| `src/api/app.py` | FastAPI app + NiceGUI mount |
| `src/ui/design/tokens.py` | Design system constants |
| `tests/conftest.py` | Shared fixtures: `session`, `client`, `admin_token`, `contributor_token`, `reader_token`, `two_devices` |

## Doc Files

| Path | Purpose |
|---|---|
| `doc/backlog.md` | Product backlog (Product-Owner) |
| `doc/stories/` | Active stories `HT-{id}.md` |
| `doc/stories/done/` | Archived completed stories |
| `doc/rfc/` | Architect RFCs `RFC-HT-{id}-{slug}.md` |
| `doc/bugs/` | Active bug reports |
| `doc/bugs/completed/` | Archived remediated bugs |
| `doc/security/` | Active security findings |
| `doc/security/completed/` | Archived security reports |
| `doc/tracker.md` | PM's engineering tracker |
| `doc/progress.md` | PM's pipeline state |
| `CHANGELOG.md` | All changes under `[Unreleased]` |
