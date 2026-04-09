# Changelog

All notable changes to Hometower will be documented in this file.

## [Unreleased]

### Added
- HT-002: Device CRUD operations (backend)
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
