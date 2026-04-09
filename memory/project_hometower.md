---
name: Hometower project context
description: Complete product decisions, tech stack, and requirements for the Hometower homelab inventory tool
type: project
---

Hometower is a self-hosted homelab inventory management tool — Cloudcraft for homelabbers. Users draw infrastructure on a drag-and-drop canvas; the diagram is the inventory.

**Why:** Existing tools (diagramming apps) are flat and give no real inventory. Hometower bridges the gap.

**Phase 2 name:** LightTower (small teams, different branding)

## Final Tech Stack

- UI: NiceGUI
- Topology canvas: Cytoscape.js (embedded in NiceGUI)
- Map view: Leaflet.js + OpenStreetMap (embedded in NiceGUI)
- API: FastAPI + Pydantic (unified with NiceGUI via `ui.run_with()`)
- ORM: SQLModel + Alembic
- Database: PostgreSQL 16
- Auth: passlib (bcrypt) + python-jose (JWT)
- Logging: Loguru
- Deployment: Docker Compose (no reverse proxy in v1)

**Why FastAPI over Falcon:** NiceGUI runs FastAPI internally. Unifying them removes dual-server complexity and gives Pydantic validation + auto OpenAPI docs for free.

**Why Cytoscape.js over draw.io:** Data model IS the diagram — no XML parsing or dual representation. Network topology purpose-built library.

**Why Leaflet.js:** Open source, no API key, OpenStreetMap tiles, perfect for self-hosted.

## Product Decisions

| Decision | Choice | Reason |
|---|---|---|
| Concurrency | Last-write-wins | Simple, sufficient for solo/small team |
| Reverse proxy | None for v1 | Added complexity without clear benefit yet |
| First admin | .env vars (ADMIN_EMAIL, ADMIN_PASSWORD) | Simple, standard pattern |
| Custom fields | Yes — free key-value pairs per device | Power users need serial numbers, warranty dates etc |
| Location grouping | Yes — rack and geo types | Supports both physical racks and distributed infra |
| Map view | Yes — Leaflet.js + OpenStreetMap | Users have VPS, colocation, remote nodes |

## Features Confirmed for v1

- Drag-and-drop topology canvas (Cytoscape.js)
- Geographic map view (Leaflet.js)
- Device types: Server, Switch, Router, NAS, UPS, SBC, Workstation, VM, LXC, Docker Container, Application, VLAN, Subnet
- Connection types: Ethernet, WiFi, Fibre, iSCSI, NFS, VM, Other
- Tags on all devices
- Custom key-value fields per device
- Location grouping (rack + geo with lat/lng)
- Notes per device
- Timestamps (created_at, updated_at) on all records
- RBAC: Admin, Contributor, Reader
- Export: JSON + PNG/SVG + pg_dump
- Import: Hometower JSON format
- Dark mode (NiceGUI native)
- Keyboard shortcuts on canvas (Delete, Ctrl+Z, Ctrl+A)
- Password reset via CLI escape hatch

## Phase 2 (LightTower) — Out of Scope for v1

- Proxmox, Docker, Home Assistant integrations
- Multi-workspace
- Traefik/SSL
- Scheduled backups
- Audit log
- LDAP/SSO

**How to apply:** Any feature request touching these areas goes to the Icebox in the product backlog. Build Hometower v1 first.
