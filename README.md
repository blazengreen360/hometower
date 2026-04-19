# Hometower

**Homelab modelling, inventory management, and documentation platform** — Cloudcraft for homelabbers.

Draw your infrastructure as an interactive topology diagram or pin locations on a geographic map. Every node you place populates a searchable inventory database. Attach notes, track lifecycle, and manage services with dependency graphs.

> **Status**: Active development. Not yet released.

## Tech Stack

| Layer | Technology |
|---|---|
| UI | NiceGUI |
| Topology canvas | Cytoscape.js |
| Map view | Leaflet.js + OpenStreetMap |
| API | FastAPI + Pydantic |
| ORM | SQLModel + Alembic |
| Database | PostgreSQL 16 |
| Auth | passlib (bcrypt) + python-jose (JWT) |
| Deployment | Docker Compose |

## Architecture

```
NiceGUI UI → FastAPI Routers → Services → Repositories → PostgreSQL
                                   ↑
                              Domain Logic
                         (pure Python, no I/O)
```

NiceGUI and FastAPI share a single process via `ui.run_with()`. UI and API are both served on port 8080; API routes are prefixed `/api/`.

## Running Locally

```bash
cp .env.example .env
# Set ADMIN_EMAIL, ADMIN_PASSWORD, SECRET_KEY, DB_PASSWORD, DATABASE_URL
docker compose up -d
docker compose exec api alembic upgrade head
```

- **UI**: http://localhost:8080
- **API docs**: http://localhost:8080/docs
- **PgAdmin**: http://localhost:5050

First boot seeds an admin account from `.env` (one-time).

## Development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
docker compose exec api pytest
docker compose exec api mypy src/ --ignore-missing-imports
```

## Roadmap

### Phase 1 — Core Platform (in progress)
Topology canvas, device inventory, connections, containers, services with dependency graphs, RBAC, JWT auth, import/export, multi-workspace, theme engine.

### Phase 2 — LightTower (planned)
Auto-discovery (Proxmox, Docker, Home Assistant), LDAP/SSO, audit logging, webhook integrations, collaborative editing.

## Contributing

Architecture constraints, coding patterns, and agent workflows are in **`AGENTS.md`**.
