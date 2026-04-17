# RFC-001 Part 5: Authentication, Configuration, Docker, and Testing

**Parts:** [Part 1 – System Overview](rfc-001-part1-system-overview.md) · [Part 2 – Data Model](rfc-001-part2-data-model.md) · [Part 3 – API Layer](rfc-001-part3-api-layer.md) · [Part 4 – Integrations](rfc-001-part4-integrations.md) · [Part 5 (this)]

---

## 1. Authentication Flow

### 1.1 First-Boot Admin Creation

On application startup, `FastAPI` calls a lifespan handler (not `on_event` which is deprecated):

```python
# src/services/auth_service.py
def create_first_admin_if_needed(session: Session) -> None:
    count = session.exec(select(func.count(User.id))).one()
    if count == 0:
        admin = User(
            username="admin",
            email=settings.admin_email,
            password_hash=hash_password(settings.admin_password),
            role=Role.Admin,
        )
        session.add(admin)
        session.commit()
        logger.info("First-boot admin created: {}", settings.admin_email)
```

```python
# src/api/app.py — lifespan context manager
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    with get_session() as session:
        create_first_admin_if_needed(session)
    yield   # application runs

app = FastAPI(lifespan=lifespan)
```

### 1.2 Login Sequence

```
POST /api/auth/login  {email, password}
  → AuthRouter calls auth_service.authenticate(email, password, session)
  → auth_service queries user by email
  → verify_password(password, user.password_hash)  [bcrypt, cost=12]
  → if invalid: raise 401 "Invalid credentials"
  → if user.is_active == False: raise 401 "Account disabled"
  → create_jwt({"sub": str(user.id), "role": user.role.value, "exp": now+24h})
  → return {access_token, token_type: "bearer"}
```

### 1.3 JWT Structure

```python
# src/utils/auth.py
from jose import jwt, JWTError
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)

def create_jwt(payload: dict[str, str | int]) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    return jwt.encode({**payload, "exp": expire}, settings.secret_key, algorithm="HS256")

def decode_jwt(token: str) -> dict[str, str]:
    """Raises jose.JWTError on invalid or expired token."""
    return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
```

JWT payload fields:
- `sub`: `str(user.id)` (UUID as string)
- `role`: `"Admin"` | `"Contributor"` | `"Reader"`
- `exp`: Unix timestamp (UTC, now + 24 hours)

### 1.4 Middleware (Every Protected Request)

```python
# src/api/middleware/auth.py
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

EXCLUDED_PATHS: frozenset[str] = frozenset({
    "/api/auth/login", "/login", "/health",
    "/docs", "/openapi.json", "/redoc",
})

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in EXCLUDED_PATHS or request.url.path.startswith("/_nicegui"):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)

        token = auth_header.removeprefix("Bearer ")
        try:
            payload = decode_jwt(token)
        except JWTError as exc:
            detail = "Token expired" if "expired" in str(exc) else "Invalid token"
            return JSONResponse({"detail": detail}, status_code=401)

        request.state.user_id = payload["sub"]
        request.state.role    = payload["role"]
        return await call_next(request)
```

### 1.5 Logout

Logout is client-side only (stateless JWT). The server response clears the NiceGUI `app.storage.user` dict and the `sessionStorage` entry holding the token. No server-side token revocation in v1.

### 1.6 Password Reset (CLI — HT-017)

```bash
docker compose exec api python -m src.cli.reset_password --email user@example.com --password newpass
```

`src/cli/reset_password.py` opens a direct DB session, finds the user, calls `hash_password()`, and updates the record. Never stores the plaintext password.

---

## 2. Configuration Management

All secrets and environment-specific values come from environment variables. No secrets in source code or Docker images.

### `.env.example`

```dotenv
# Required
DATABASE_URL=postgresql://hometower:secret@db:5432/hometower
SECRET_KEY=replace_with_32_random_bytes_minimum
ADMIN_EMAIL=admin@hometower.local
ADMIN_PASSWORD=changeme_on_first_boot

# Optional (defaults shown)
JWT_EXPIRE_HOURS=24
LOG_LEVEL=INFO
```

### `src/utils/settings.py` — Pydantic Settings

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    secret_key: str
    admin_email: str
    admin_password: str
    jwt_expire_hours: int = 24
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = Settings()
```

---

## 3. Docker Compose Topology

```yaml
# docker-compose.yml
version: "3.9"

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8080:8080"
    env_file: .env
    environment:
      DATABASE_URL: postgresql://hometower:${DB_PASSWORD:-secret}@db:5432/hometower
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./src:/app/src       # hot-reload in dev; omit in production build
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: hometower
      POSTGRES_USER: hometower
      POSTGRES_PASSWORD: ${DB_PASSWORD:-secret}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U hometower -d hometower"]
      interval: 5s
      timeout: 5s
      retries: 10
    restart: unless-stopped

volumes:
  postgres_data:
```

### Dockerfile (multi-stage)

```dockerfile
FROM python:3.12-slim AS base
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN alembic upgrade head
CMD ["python", "-m", "src.api.app"]
```

---

## 4. Logging Conventions

All logging uses the **Loguru** singleton from `src/utils/logger.py`:

```python
# src/utils/logger.py
from loguru import logger
import sys

logger.remove()
logger.add(sys.stdout, level=settings.log_level,
           format="{time:ISO8601} | {level:<8} | {name}:{line} | {message}")
```

Import everywhere:
```python
from src.utils.logger import logger

logger.info("Device created: id={} name={}", device.id, device.name)
logger.warning("Login failed: email={}", email)
logger.error("Unexpected error in device_service.delete: {}", exc)
```

**Never log:** passwords, JWT tokens, full exception tracebacks in responses.  
**Always log:** resource IDs, user roles (not IDs) for RBAC denials, startup events.

---

## 5. Test Strategy

### 5.1 Unit Tests — `tests/unit/`

Test target: `src/domain/` functions only. No mocks, no DB, no framework.

```python
# tests/unit/test_domain_devices.py
def test_validate_ip_valid():
    assert validate_ip("192.168.1.1") is True

def test_validate_ip_invalid():
    assert validate_ip("999.999.999.999") is False

def test_validate_mac_valid():
    assert validate_mac("AA:BB:CC:DD:EE:FF") is True
```

Coverage target: **≥ 95%** on `src/domain/`.

### 5.2 Integration Tests — `tests/integration/`

Test target: FastAPI routes end-to-end against a real PostgreSQL test database.

**Fixtures (`tests/conftest.py`):**

```python
@pytest.fixture(scope="session")
def engine():
    e = create_engine(TEST_DATABASE_URL)
    SQLModel.metadata.create_all(e)
    yield e
    SQLModel.metadata.drop_all(e)

@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s
        s.rollback()

@pytest.fixture
def client(session):
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)

@pytest.fixture
def admin_token() -> str:
    # Returns a pre-signed JWT for role=Admin; bypasses bcrypt
    return create_jwt({"sub": str(uuid4()), "role": "Admin"})
```

**What to mock:**
- JWT signing/verification is **not** mocked — real tokens are created via `create_jwt()`.
- bcrypt hashing is **not** mocked in db fixture setup — one real hash per test session.
- External HTTP calls: none in Phase 1 (no external integrations).

**What NOT to mock:**
- The database — use a real test PostgreSQL instance with a separate `hometower_test` DB.
- The FastAPI app or any service layer.

Coverage target: **≥ 80%** on `src/api/routers/` and `src/services/`.

### 5.3 Fitness Function Tests

| Constraint | Test |
|---|---|
| `src/domain/` imports only `types.py` | `test_domain_import_isolation.py` uses `importlib` + `ast` |
| Files ≤ 250 lines | `test_file_lengths.py` walks `src/` and fails on any file > 250 lines |
| No `print()` in src/ | `test_no_print.py` uses grep via `subprocess` |
| No `logging.*` in src/ | `test_no_stdlib_logging.py` uses `ast` to detect `import logging` |
| `/api/auth/login` accessible without JWT | Integration test expects 200/401, never 403 |

### 5.4 Coverage Commands

```bash
docker compose exec api pytest --cov=src --cov-report=term-missing
docker compose exec api pytest tests/unit/ --cov=src/domain --cov-fail-under=95
docker compose exec api pytest tests/integration/ --cov=src/api --cov-fail-under=80
```

---

## 6. JSON Import/Export — Merge Policy

`POST /api/import/json` (HT-013) applies an **upsert-only** merge policy inside a single database transaction — all records succeed or none are committed.

| Condition | Action |
|---|---|
| Record ID exists in DB | `UPDATE` all fields with imported values |
| Record ID not in DB | `INSERT` as new record |
| Existing DB record absent from import payload | Leave unchanged — **never DELETE** |

**Previously deleted records are not resurrected.** If a record was hard-deleted from the DB before import, its ID will not exist in the DB; it will be re-`INSERT`ed only if its UUID appears explicitly in the import payload. To avoid unintended resurrection, omit stale IDs from export payloads before re-importing.

**Transaction semantics:** `POST /api/import/json` runs inside a **single database transaction**. If any record fails — Pydantic validation, FK constraint, or unique violation — the entire transaction is rolled back atomically. No partial state is committed.

**Error response format:** On failure, the response is `422` with a structured body listing every failing record:

```json
{
  "detail": [
    {"id": "<uuid>", "field": "type", "reason": "value is not a valid DeviceType"},
    {"id": "<uuid>", "field": "mac",  "reason": "mac must be in format AA:BB:CC:DD:EE:FF"}
  ]
}
```

**No partial retry:** There is no mechanism to re-import individual records. The user must fix all errors in the JSON file and re-submit the entire file. This is intentional — partial imports would leave inventory in an inconsistent intermediate state that is difficult to reason about in a homelab context.
