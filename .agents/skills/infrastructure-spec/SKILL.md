---
name: infrastructure-spec
description: Hometower's infrastructure specification — Twelve-Factor App mapping, Docker Compose service ownership, .env variable inventory, and backup/restore script contracts. Read this when working on Docker, deployment, migrations, or .env configuration.
---

# infrastructure-spec

## Twelve-Factor App Mapping

| Factor | Rule | Hometower Application |
|---|---|---|
| III — Config | All config in env, never in code | Every secret/URL in `.env`, never hardcoded in `src/` or `docker-compose.yml` |
| IV — Backing services | DB is attached resource | PostgreSQL URL in `DATABASE_URL` env var — swap test/prod without code change |
| VI — Processes | Stateless, share-nothing | FastAPI + NiceGUI container holds no local state — canvas data only in PostgreSQL |
| IX — Disposability | Fast startup, graceful shutdown | Container healthy in < 30s; SIGTERM flushes in-flight requests |
| XI — Logs | Event streams | Loguru writes to stdout — Docker captures and rotates; no log files in containers |

## Docker Compose Services

### `api` service
- FastAPI + NiceGUI on same process
- Health check: `/health` endpoint
- Non-root user
- Environment from `.env`
- Restart policy: `unless-stopped`

### `db` service
- PostgreSQL 16 (pinned tag, never `latest`)
- Named volume for data persistence
- Internal network only (no host port exposure by default)
- Environment: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` from `.env`

### Networking
- Internal network for api <-> db
- Only api exposed to host

## .env Variable Inventory

| Variable | Group | Required | Purpose |
|---|---|---|---|
| `DATABASE_URL` | Database | Yes | PostgreSQL connection string |
| `POSTGRES_DB` | Database | Yes | Database name |
| `POSTGRES_USER` | Database | Yes | Database user |
| `POSTGRES_PASSWORD` | Database | Yes | Database password |
| `SECRET_KEY` | Auth | Yes | JWT signing key (>= 32 bytes) |
| `ADMIN_EMAIL` | Auth | Yes | First-boot admin email |
| `ADMIN_PASSWORD` | Auth | Yes | First-boot admin password |
| `LOG_LEVEL` | App | No | Loguru level (default: INFO) |

`.env.example` contains only placeholder values. Real `.env` is always gitignored.

## Backup & Restore Scripts

### `scripts/backup.sh`
- `set -euo pipefail`
- Validates: `DATABASE_URL` set, `pg_dump` available
- Output: timestamped dump to configurable path
- Exit non-zero on any failure

### `scripts/restore.sh`
- `set -euo pipefail`
- Validates: `DATABASE_URL` set, `pg_restore`/`psql` available, backup file exists
- **Must prompt for confirmation before drop+restore**
- Exit non-zero on any failure

## Dockerfile Constraints

- Base image pinned (never `latest`)
- Multi-stage builds where beneficial
- Non-root user for application containers
- `.dockerignore`: `.venv`, `.git`, `__pycache__`, `*.pyc`, `tests/`
