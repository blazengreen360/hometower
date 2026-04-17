# RFC: Bundle A — RBAC Enforcement, Admin User Panel, Password Reset CLI

**Stories:** HT-011 · HT-019 · HT-017  
**Date:** 2026-04-10  
**Status:** DRAFT  
**Author:** Architect  
**Handoff target:** Feature-Engineer, UX-Designer

---

## 1. Overview

This RFC covers three interlocking stories that complete the access-control layer of Hometower:

- **HT-011**: Audit every API endpoint and every UI surface to ensure role-based access control is *explicit* and *tested* — not just implied by JWT middleware presence.
- **HT-019**: Build an Admin-only user management UI (Settings → Users) and the backing API (`/api/users/`).
- **HT-017**: Provide a break-glass `reset-password` CLI for operators who are locked out of the web UI.

**Parnas information-hiding analysis — every new module boundary must hide one specific, nameable design decision:**

| Module (new/modified) | Hidden decision |
|---|---|
| `src/services/user_service.py` | *How* user mutations are validated (self-delete, last-admin, email uniqueness). If business rules change, only this file changes. |
| `src/api/routers/users.py` | The HTTP shape of user management. If the API contract is versioned or restructured, only this file changes. |
| `src/cli.py` | *How* admins interact with the system off-band. If argparse is replaced with Click, only this file changes. |
| `src/ui/components/auth_guard.py` | *How* NiceGUI pages decode the JWT and check roles. If the token format changes, only this file changes. |
| `src/ui/pages/settings_users.py` | The UI layout and interaction model for user management. |

---

## 2. RBAC Audit Matrix

Full audit of every `/api/` route — current state versus required state.

### 2.1 Existing Routers

| Router file | Method | Path | Current enforcement | Required enforcement | Action |
|---|---|---|---|---|---|
| `auth.py` | POST | `/api/auth/login` | None (explicitly excluded from JWT middleware) | None — public endpoint by design | ✅ no change |
| `auth.py` | POST | `/api/auth/logout` | JWT only (middleware validates token) | `require_role(Role.Reader)` — explicitly document minimum | 🔧 add dependency |
| `devices.py` | POST | `/api/devices/` | `require_role(Contributor)` | `require_role(Contributor)` | ✅ no change |
| `devices.py` | GET | `/api/devices/` | `require_role(Reader)` | `require_role(Reader)` | ✅ no change |
| `devices.py` | GET | `/api/devices/{id}` | `require_role(Reader)` | `require_role(Reader)` | ✅ no change |
| `devices.py` | PATCH | `/api/devices/{id}` | `require_role(Contributor)` | `require_role(Contributor)` | ✅ no change |
| `devices.py` | DELETE | `/api/devices/{id}` | `require_role(Contributor)` | `require_role(Contributor)` | ✅ no change |
| `connections.py` | POST | `/api/connections/` | `require_role(Contributor)` | `require_role(Contributor)` | ✅ no change |
| `connections.py` | GET | `/api/connections/` | `require_role(Reader)` | `require_role(Reader)` | ✅ no change |
| `connections.py` | DELETE | `/api/connections/{id}` | `require_role(Contributor)` | `require_role(Contributor)` | ✅ no change |
| `locations.py` | POST | `/api/locations/` | `require_role(Contributor)` | `require_role(Contributor)` | ✅ no change |
| `locations.py` | GET | `/api/locations/` | `require_role(Reader)` | `require_role(Reader)` | ✅ no change |
| `locations.py` | GET | `/api/locations/{id}` | `require_role(Reader)` | `require_role(Reader)` | ✅ no change |
| `locations.py` | PATCH | `/api/locations/{id}` | `require_role(Contributor)` | `require_role(Contributor)` | ✅ no change |
| `locations.py` | DELETE | `/api/locations/{id}` | `require_role(Contributor)` | `require_role(Contributor)` | ✅ no change |
| `tags.py` | POST | `/api/tags/` | `require_role(Contributor)` | `require_role(Contributor)` | ✅ no change |
| `tags.py` | GET | `/api/tags/` | `require_role(Reader)` | `require_role(Reader)` | ✅ no change |
| `tags.py` | DELETE | `/api/tags/{id}` | `require_role(Contributor)` | `require_role(Contributor)` | ✅ no change |
| `device_sub_routes.py` | POST | `/api/devices/{id}/tags` | `require_role(Contributor)` | `require_role(Contributor)` | ✅ no change |
| `device_sub_routes.py` | DELETE | `/api/devices/{id}/tags/{tag_id}` | `require_role(Contributor)` | `require_role(Contributor)` | ✅ no change |
| `device_sub_routes.py` | POST | `/api/devices/{id}/custom-fields` | `require_role(Contributor)` | `require_role(Contributor)` | ✅ no change |
| `device_sub_routes.py` | PATCH | `/api/devices/{id}/custom-fields/{key}` | `require_role(Contributor)` | `require_role(Contributor)` | ✅ no change |
| `device_sub_routes.py` | DELETE | `/api/devices/{id}/custom-fields/{key}` | `require_role(Contributor)` | `require_role(Contributor)` | ✅ no change |
| `diagrams.py` | GET | `/api/diagrams/` | `require_role(Reader)` | `require_role(Reader)` | ✅ no change |
| `diagrams.py` | POST | `/api/diagrams/` | `require_role(Contributor)` | `require_role(Contributor)` | ✅ no change |
| `diagrams.py` | PUT | `/api/diagrams/{id}` | `require_role(Contributor)` | `require_role(Contributor)` | ✅ no change |
| `diagrams.py` | GET | `/api/diagrams/{id}` | `require_role(Reader)` | `require_role(Reader)` | ✅ no change |
| `diagrams.py` | DELETE | `/api/diagrams/{id}` | `require_role(Admin)` | `require_role(Admin)` | ✅ no change |

### 2.2 New Users Router

| Router file | Method | Path | Required enforcement |
|---|---|---|---|
| `users.py` (new) | GET | `/api/users/` | `require_role(Admin)` |
| `users.py` (new) | POST | `/api/users/` | `require_role(Admin)` |
| `users.py` (new) | GET | `/api/users/{user_id}` | `require_role(Admin)` |
| `users.py` (new) | PATCH | `/api/users/{user_id}` | `require_role(Admin)` |
| `users.py` (new) | DELETE | `/api/users/{user_id}` | `require_role(Admin)` |

### 2.3 Audit Conclusion

**One change to existing code** is required by this audit: `POST /api/auth/logout` in `src/api/routers/auth.py` must gain `dependencies=[Depends(require_role(Role.Reader))]`. The JWT middleware already enforces token validity; this change adds an explicit, documented, testable role assertion consistent with all other endpoints.

All other existing endpoints are already correctly enforced. The diagrams router audit found it complete (Reader for reads, Contributor for writes, Admin for delete).

### 2.4 Machine-Testable Enforcement Marker

To support the "all routes covered" integration test without fragile `__qualname__` introspection, make one small addition to `src/domain/rbac.py`:

```python
def require_role(required: Role):
    def dependency(request: Request) -> None:
        user_role = Role(request.state.role)
        if not can_perform(user_role, required):
            raise HTTPException(status_code=403, detail="Insufficient permissions")

    dependency._rbac_protected = True   # ← add this line
    return dependency
```

This attribute is the machine-readable signal the coverage test will check. It costs nothing at runtime and makes the test stable against naming or closure structure changes.

---

## 3. Data Model Changes

**No new SQLModel tables are needed.** The `User` model in `src/models/user.py` is complete as-is. All required schemas (`UserCreate`, `UserUpdate`, `UserResponse`) are already defined.

**No Alembic migration is required.**

### 3.1 Repository Addition Only

Add `count_by_role()` to `src/repositories/user_repository.py`. This is needed by the last-admin deletion guard in the service layer.

```python
def count_by_role(session: Session, role: Role) -> int:
    """Return the number of users with the given role."""
    result = session.exec(
        select(func.count()).select_from(User).where(User.role == role)
    ).one()
    return int(result)
```

**Import addition required:** `from src.models.types import Role` (add to the existing imports in that file).

---

## 4. Domain Logic

No new domain module is required for user management. The business rules (self-delete, last-admin, email uniqueness) are service-layer guard clauses with no reuse outside of `user_service.py`. Extracting them to `src/domain/` would be premature abstraction — a domain function must be independently testable with zero mocking, and these guards require the repository for the last-admin count.

`src/domain/rbac.py` requires the single one-line change described in §2.4 and nothing else.

---

## 5. Service Layer

### New file: `src/services/user_service.py`

*This module hides the decision of how user mutations are validated.*

**Estimated size:** ~90 lines.

```python
"""User service — orchestrates user_repository and bcrypt helpers.

This module hides the decision of how user mutations are validated:
self-delete, last-admin deletion, email uniqueness, and password policy.
"""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session

from src.models.types import Role
from src.models.user import User, UserCreate, UserResponse, UserUpdate
from src.repositories import user_repository
from src.utils.auth import hash_password
from src.utils.logger import logger


def list_users(session: Session) -> list[UserResponse]:
    """Return all users as UserResponse instances (password_hash excluded)."""
    users = user_repository.get_all(session)
    return [UserResponse.model_validate(u.model_dump()) for u in users]


def get_user(user_id: uuid.UUID, session: Session) -> UserResponse:
    """Return a single user by ID.

    Raises:
        HTTPException(404): if the user does not exist.
    """
    user = user_repository.get_by_id(session, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(user.model_dump())


def create_user(data: UserCreate, session: Session) -> UserResponse:
    """Hash password and persist a new user.

    Raises:
        HTTPException(422): if password is fewer than 8 characters.
        HTTPException(409): if email is already registered.
    """
    if len(data.password) < 8:
        raise HTTPException(
            status_code=422, detail="Password must be at least 8 characters"
        )
    if user_repository.get_by_email(session, data.email) is not None:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        username=data.username,
        email=data.email,
        role=data.role,
        is_active=data.is_active,
        password_hash=hash_password(data.password),
    )
    created = user_repository.create(session, user)
    logger.info("User created by admin: user_id={} role={}", created.id, created.role.value)
    return UserResponse.model_validate(created.model_dump())


def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    session: Session,
) -> UserResponse:
    """Apply a partial update to a user.

    Raises:
        HTTPException(404): if the user does not exist.
        HTTPException(409): if the new email is already taken by another user.
        HTTPException(422): if the new password is fewer than 8 characters.
    """
    user = user_repository.get_by_id(session, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if data.email is not None and data.email != user.email:
        if user_repository.get_by_email(session, data.email) is not None:
            raise HTTPException(status_code=409, detail="Email already registered")
        user.email = data.email
    if data.username is not None:
        user.username = data.username
    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.password is not None:
        if len(data.password) < 8:
            raise HTTPException(
                status_code=422, detail="Password must be at least 8 characters"
            )
        user.password_hash = hash_password(data.password)
    user.updated_at = datetime.now(timezone.utc)
    updated = user_repository.update(session, user)
    logger.info("User updated by admin: user_id={}", user_id)
    return UserResponse.model_validate(updated.model_dump())


def delete_user(
    user_id: uuid.UUID,
    requesting_user_id: uuid.UUID,
    session: Session,
) -> None:
    """Delete a user.

    Raises:
        HTTPException(400): if the caller is deleting their own account.
        HTTPException(400): if deleting the last Admin in the system.
        HTTPException(404): if the user does not exist.
    """
    if user_id == requesting_user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    user = user_repository.get_by_id(session, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if (
        user.role == Role.Admin
        and user_repository.count_by_role(session, Role.Admin) <= 1
    ):
        raise HTTPException(
            status_code=400, detail="Cannot delete the last Admin account"
        )
    user_repository.delete(session, user)
    logger.info("User deleted by admin: user_id={}", user_id)
```

**Design note on `requesting_user_id`:** The router extracts `uuid.UUID(request.state.user_id)` — a UUID already validated by `decode_jwt()` at the middleware layer. The service accepts it as `uuid.UUID`, not `str`, to prevent type mismatch bugs.

---

## 6. API Layer

### New file: `src/api/routers/users.py`

*This module hides the HTTP shape of user management.*

**Estimated size:** ~80 lines.

```python
"""Users router — Admin-only CRUD endpoints for User management."""
import uuid

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session

from src.domain.rbac import require_role
from src.models.types import Role
from src.models.user import UserCreate, UserResponse, UserUpdate
from src.services import user_service
from src.utils.db import get_session

router = APIRouter(prefix="/users", tags=["users"])

_ADMIN = [Depends(require_role(Role.Admin))]


@router.get("/", response_model=list[UserResponse], dependencies=_ADMIN)
async def list_users(session: Session = Depends(get_session)) -> list[UserResponse]:
    """List all users. Requires Admin role."""
    return user_service.list_users(session)


@router.post("/", status_code=201, response_model=UserResponse, dependencies=_ADMIN)
async def create_user(
    data: UserCreate,
    session: Session = Depends(get_session),
) -> UserResponse:
    """Create a new user. Requires Admin role."""
    return user_service.create_user(data, session)


@router.get("/{user_id}", response_model=UserResponse, dependencies=_ADMIN)
async def get_user(
    user_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> UserResponse:
    """Get a user by ID. Requires Admin role."""
    return user_service.get_user(user_id, session)


@router.patch("/{user_id}", response_model=UserResponse, dependencies=_ADMIN)
async def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    session: Session = Depends(get_session),
) -> UserResponse:
    """Partially update a user. Requires Admin role."""
    return user_service.update_user(user_id, data, session)


@router.delete("/{user_id}", status_code=204, dependencies=_ADMIN)
async def delete_user(
    user_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_session),
) -> None:
    """Delete a user. Requires Admin role.

    Returns 400 if the caller targets their own account or the last Admin.
    """
    requesting_id = uuid.UUID(request.state.user_id)
    user_service.delete_user(user_id, requesting_id, session)
```

**Status code contract:**

| Scenario | HTTP status |
|---|---|
| Success — list/get/update | 200 |
| Success — create | 201 |
| Success — delete | 204 |
| Unauthenticated | 401 (middleware) |
| Wrong role (non-Admin) | 403 |
| User not found | 404 |
| Self-delete or last-admin delete | 400 |
| Duplicate email | 409 |
| Password too short | 422 |

### Modification to `src/api/app.py`

Add the following import and `include_router` call. Insert after the `tags_router` registration:

```python
# import (add to existing import block):
from src.api.routers.users import router as users_router

# registration (add after existing include_router calls):
app.include_router(users_router, prefix="/api")
```

### Modification to `src/api/routers/auth.py`

**The single audit-driven change** to existing router code. Add the `require_role(Role.Reader)` dependency to `POST /api/auth/logout`:

```python
@router.post("/auth/logout", dependencies=[Depends(require_role(Role.Reader))])
async def logout() -> dict[str, str]:
    """Stateless logout — instructs the client to clear the stored JWT.

    Requires a valid Bearer token with at least Reader role.
    The server does not maintain a token blocklist in v1.
    """
    return {"detail": "Logged out"}
```

Required import addition for `auth.py`: `from src.domain.rbac import require_role` and `from src.models.types import Role`.

---

## 7. CLI Design

### New file: `src/cli.py`

*This module hides the decision of how admins interact with the system off-band.*

**Estimated size:** ~65 lines. Comfortably under the 250-line cap.

**Entry point:** `python -m src.cli reset-password --username EMAIL [--password NEWPASS]`

- If `--password` is omitted, `getpass.getpass()` prompts interactively.
- Uses `src/utils/db.py` engine + `Session` — the same DB wiring as the application.
- Calls `user_repository` directly (no service layer — this is an off-band CLI tool, not a web request path, and introducing FastAPI's `HTTPException` path is unnecessary complexity in a sys.exit context).
- Uses `logger` from `src/utils/logger.py` for all output, consistent with the project rule of no bare `print()`.

```python
"""CLI entry point — operator tools for Hometower.

Usage:
    python -m src.cli reset-password --username EMAIL [--password NEWPASS]

Exit codes:
    0  success
    1  user not found, password policy violation, or database error
"""
import argparse
import getpass
import sys

from sqlmodel import Session

from src.repositories import user_repository
from src.utils.auth import hash_password
from src.utils.db import engine
from src.utils.logger import logger


def _cmd_reset_password(args: argparse.Namespace) -> int:
    """Execute reset-password. Returns POSIX exit code."""
    password: str = args.password or getpass.getpass(prompt="New password: ")
    if len(password) < 8:
        logger.error("Password must be at least 8 characters")
        return 1
    try:
        with Session(engine) as session:
            user = user_repository.get_by_email(session, args.username)
            if user is None:
                logger.error("No user found with email '{}'", args.username)
                return 1
            user.password_hash = hash_password(password)
            user_repository.update(session, user)
    except Exception as exc:  # noqa: BLE001
        logger.error("Database error during password reset: {}", exc)
        return 1
    logger.info("Password reset successfully for {}", args.username)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.cli",
        description="Hometower operator CLI",
    )
    sub = parser.add_subparsers(dest="command")
    sub.required = True

    rp = sub.add_parser("reset-password", help="Reset a user's password by email")
    rp.add_argument(
        "--username",
        required=True,
        metavar="EMAIL",
        help="Email address of the target user",
    )
    rp.add_argument(
        "--password",
        default=None,
        metavar="NEWPASS",
        help="New password (minimum 8 characters). Prompted if omitted.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    if args.command == "reset-password":
        sys.exit(_cmd_reset_password(args))


if __name__ == "__main__":
    main()
```

**Guard table:**

| Condition | Behaviour |
|---|---|
| `--password` omitted | `getpass.getpass()` prompts on stdin |
| Password < 8 characters | `logger.error(...)` → `exit 1` |
| User not found by email | `logger.error(...)` → `exit 1` |
| Database error | `logger.error(...)` → `exit 1` |
| Success | `logger.info(...)` → `exit 0` |

**Note on `print()` rule:** The project forbids bare `print()`. This CLI uses `logger.error()` / `logger.info()` throughout. `getpass.getpass()` writes its prompt to the TTY directly; it is not a `print()` call and is not subject to this rule.

---

## 8. UI Enforcement Strategy

### 8.1 Role Storage on Login

The current login page (`src/ui/pages/login.py`) stores `access_token` in `nicegui_app.storage.user` after a successful login. After this RFC, it must also store `role`:

```python
# After: nicegui_app.storage.user["access_token"] = token_response["access_token"]
from src.utils.auth import decode_jwt
payload = decode_jwt(token_response["access_token"])
nicegui_app.storage.user["role"] = payload["role"]
```

This avoids re-decoding the JWT on every page render. The `role` value mirrors the JWT claim — a plain string matching `Role` enum values (`"Admin"`, `"Contributor"`, `"Reader"`).

### 8.2 Auth Guard Utility

### New file: `src/ui/components/auth_guard.py`

*This module hides the decision of how NiceGUI pages decode and check roles.*

**Estimated size:** ~50 lines.

```python
"""UI authentication and role guard utilities.

This module hides the decision of how NiceGUI pages verify authentication
and enforce role requirements. Import these helpers at the top of every
protected page — do not duplicate auth logic in individual pages.
"""
from typing import Optional

from jose import JWTError
from nicegui import app as nicegui_app
from nicegui import ui

from src.domain.rbac import can_perform
from src.models.types import Role
from src.utils.auth import decode_jwt


def get_ui_role() -> Optional[Role]:
    """Return the authenticated user's role from storage, or None if invalid/missing."""
    token = nicegui_app.storage.user.get("access_token")
    if not token:
        return None
    try:
        payload = decode_jwt(token)
        return Role(payload["role"])
    except (JWTError, KeyError, ValueError):
        nicegui_app.storage.user.pop("access_token", None)
        nicegui_app.storage.user.pop("role", None)
        return None


def redirect_if_unauthenticated() -> bool:
    """Redirect to /login if no valid token is present.

    Returns:
        True if a redirect was issued (caller must return immediately).
    """
    if get_ui_role() is None:
        ui.navigate.to("/login")
        return True
    return False


def redirect_if_insufficient_role(minimum: Role) -> bool:
    """Redirect to /403 if the user's role is below *minimum*.

    Must be called after redirect_if_unauthenticated().

    Returns:
        True if a redirect was issued (caller must return immediately).
    """
    role = get_ui_role()
    if role is None or not can_perform(role, minimum):
        ui.navigate.to("/403")
        return True
    return False
```

**Note:** A `/403` NiceGUI page does not currently exist. Feature-Engineer must add a minimal "Access Denied" page at that path (or redirect to `/` — settle on approach during implementation, but it must not produce a NiceGUI 404 crash).

### 8.3 Per-Page Role Enforcement

Replace the inline `if not token: ui.navigate.to("/login"); return` pattern in every existing page with the new helpers:

| Page file | Current check | New check | Write-gating needed |
|---|---|---|---|
| `topology.py` | `access_token` presence | `redirect_if_unauthenticated()` + extract role | Yes — disable canvas write actions for Reader |
| `inventory.py` | `access_token` presence | `redirect_if_unauthenticated()` + extract role | Yes — hide/disable Create/Edit/Delete buttons for Reader |
| `settings_locations.py` | `access_token` presence | `redirect_if_unauthenticated()` then `redirect_if_insufficient_role(Role.Contributor)` | No — page is write-only; Readers are redirected to /403 |
| `settings_users.py` (new) | n/a | `redirect_if_unauthenticated()` then `redirect_if_insufficient_role(Role.Admin)` | No — page is Admin-only |

### 8.4 Topology Canvas Read-Only Mode for Readers

The topology page already imports `jose.jwt`. After confirming `role == Role.Reader`, inject the JS flag before the canvas renders:

```python
# In topology.py, after role check resolves to Reader:
if user_role == Role.Reader:
    ui.run_javascript("window.HT_READONLY = true;")
```

In `src/ui/components/canvas.py`, the Cytoscape.js initialisation block that registers event handlers (node drag, edge draw, context menu) must be wrapped:

```javascript
if (!window.HT_READONLY) {
    // register drag, edgehandles, context menu write actions
}
```

The context menu `_CONTEXT_MENU_JS` in `topology.py` must also respect `HT_READONLY`:

```javascript
// At the beginning of the ht:context-menu-request handler:
if (window.HT_READONLY) return;
```

The device palette in `src/ui/components/device_palette.py` must disable drag for Readers — the simplest approach is to not render the palette at all when `HT_READONLY` is true, or to add a visible "Read-only mode" label in its place.

---

## 9. Settings Users Page

### New file: `src/ui/pages/settings_users.py`

*NiceGUI page at `/settings/users`. Admin role required.*

**Estimated size:** ~180 lines. Under the 250-line cap.

**Pattern:** follows the same structure as `settings_locations.py` — `_API` constant, `_auth_headers()` helper, `httpx.AsyncClient` for all API calls.

**Layout:**

```
┌─────────────────────────────────────────────────────────────┐
│  Settings — Users                          [ + New User ]   │
├──────────┬──────────────────┬─────────────┬────────┬────────┤
│ Username │ Email            │ Role        │ Active │ Actions│
├──────────┼──────────────────┼─────────────┼────────┼────────┤
│ alice    │ alice@infra.home │ Admin       │ ✓      │ ✎  🗑  │
│ bob      │ bob@infra.home   │ Contributor │ ✓      │ ✎  🗑  │
│ carol    │ carol@infra.home │ Reader      │ ✗      │ ✎  🗑  │
└──────────┴──────────────────┴─────────────┴────────┴────────┘
```

**Interactions:**

| Action | Trigger | Endpoint | Notes |
|---|---|---|---|
| List users | Page load | `GET /api/users/` | Populate table |
| Create user | "+ New User" button | `POST /api/users/` → 201 | Open modal with create form |
| Edit user | Row "✎" button | `PATCH /api/users/{id}` → 200 | Open modal pre-populated |
| Delete user | Row "🗑" button | `DELETE /api/users/{id}` → 204 | Confirmation dialog first |
| Self-delete blocked | Row "🗑" for current user | Client-side disable | Also blocked server-side (400) |

**Form fields (create and edit modal):**

| Field | Type | Validation | Create | Edit |
|---|---|---|---|---|
| Username | text input | required | ✓ | ✓ |
| Email | email input | required | ✓ | ✓ |
| Password | password input | ≥8 chars | required | optional (blank = unchanged) |
| Role | select (Admin/Contributor/Reader) | required | ✓ | ✓ |
| Active | toggle | — | ✓ (default true) | ✓ |

**Self-delete client-side guard:** The page must store the current user's ID from the JWT (`nicegui_app.storage.user.get("user_id")` — this key must also be populated on login). The Delete button for that row is rendered as disabled. This prevents UX confusion even though the server enforces it too.

**Login page addition for `user_id`:** On successful login, also store the user's `sub` claim:

```python
nicegui_app.storage.user["user_id"] = payload["sub"]
```

---

## 10. "All Routes Covered" Integration Test

### New file: `tests/integration/test_rbac_coverage.py`

Uses the `_rbac_protected` marker added to `require_role`'s inner closure (§2.4). Parametrizes over all routes to make failures point to specific routes.

```python
"""HT-011: Assert every /api/ route (except login) has an explicit require_role dependency."""
import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute

from src.api.app import app


def _collect_api_routes(application: FastAPI) -> list[tuple[str, str]]:
    """Return (method, path) pairs for all /api/ routes excluding login."""
    excluded = {"/api/auth/login"}
    results: list[tuple[str, str]] = []
    for route in application.routes:
        if not isinstance(route, APIRoute):
            continue
        if not route.path.startswith("/api/"):
            continue
        if route.path in excluded:
            continue
        for method in route.methods or []:
            results.append((method, route.path))
    return results


def _has_rbac_dependency(route: APIRoute) -> bool:
    """Return True if any route-level dependency carries _rbac_protected=True."""
    return any(
        getattr(dep.dependency, "_rbac_protected", False)
        for dep in route.dependencies
    )


_ROUTES = _collect_api_routes(app)


@pytest.mark.parametrize("method,path", _ROUTES, ids=lambda x: x)
def test_route_has_role_dependency(method: str, path: str) -> None:
    """Every /api/ route except login must declare a require_role dependency."""
    matching = [
        r for r in app.routes
        if isinstance(r, APIRoute) and r.path == path and method in (r.methods or [])
    ]
    assert len(matching) == 1, f"Could not locate route {method} {path}"
    route = matching[0]
    assert _has_rbac_dependency(route), (
        f"{method} {path} has no require_role dependency — "
        "add dependencies=[Depends(require_role(Role.X))] to this endpoint"
    )
```

This test will catch any future router addition that omits `require_role` at CI time—before it reaches production.

---

## 11. Unit and Integration Test Inventory

### `tests/unit/test_user_service.py`

| Test name | What it asserts |
|---|---|
| `test_create_user_short_password_raises_422` | `create_user` with 7-char password raises HTTPException(422) |
| `test_create_user_duplicate_email_raises_409` | `create_user` with existing email raises HTTPException(409) |
| `test_create_user_hashes_password` | Created user's `password_hash` is not equal to plain password |
| `test_create_user_success` | Returns `UserResponse` with correct fields |
| `test_update_user_email_conflict_raises_409` | `update_user` with taken email raises HTTPException(409) |
| `test_update_user_same_email_no_conflict` | `update_user` with same email does not raise 409 |
| `test_update_user_short_password_raises_422` | `update_user` with 7-char password raises HTTPException(422) |
| `test_update_user_not_found_raises_404` | `update_user` for non-existent UUID raises HTTPException(404) |
| `test_delete_self_raises_400` | `delete_user` where `user_id == requesting_user_id` raises HTTPException(400) |
| `test_delete_last_admin_raises_400` | `delete_user` on the only Admin raises HTTPException(400) |
| `test_delete_user_not_found_raises_404` | `delete_user` for non-existent UUID raises HTTPException(404) |
| `test_delete_user_success` | `delete_user` calls `user_repository.delete` with correct user |
| `test_get_user_not_found_raises_404` | `get_user` for non-existent UUID raises HTTPException(404) |

### `tests/integration/test_users_api.py`

| Test name | What it asserts |
|---|---|
| `test_unauthenticated_list_returns_401` | `GET /api/users/` without token → 401 |
| `test_reader_list_returns_403` | `GET /api/users/` with Reader token → 403 |
| `test_contributor_list_returns_403` | `GET /api/users/` with Contributor token → 403 |
| `test_admin_list_returns_200` | `GET /api/users/` with Admin token → 200, list present |
| `test_admin_create_user_returns_201` | `POST /api/users/` with valid data → 201, returns UserResponse |
| `test_create_user_short_password_returns_422` | Password < 8 chars → 422 |
| `test_create_user_duplicate_email_returns_409` | Duplicate email → 409 |
| `test_admin_update_user_returns_200` | `PATCH /api/users/{id}` with valid data → 200 |
| `test_admin_delete_user_returns_204` | `DELETE /api/users/{id}` non-self, non-last-admin → 204 |
| `test_admin_self_delete_returns_400` | `DELETE /api/users/{self_id}` → 400 |
| `test_admin_delete_last_admin_returns_400` | `DELETE /api/users/{only_admin_id}` → 400 |
| `test_get_nonexistent_user_returns_404` | `GET /api/users/{random_uuid}` → 404 |
| `test_user_response_never_contains_password_hash` | `UserResponse` JSON has no `password_hash` key |

### `tests/unit/test_rbac_domain.py` (existing file — add cases)

| New test name | What it asserts |
|---|---|
| `test_require_role_dependency_has_marker` | `require_role(Role.Reader)._rbac_protected is True` |

### `tests/integration/test_rbac_coverage.py`

Described in §10 above.

---

## 12. Security Boundaries

1. **`password_hash` never in API responses:** `UserResponse` in `src/models/user.py` has no `password_hash` field. Feature-Engineer must not add it and must confirm no `model_dump()` call exposes it without `exclude={"password_hash"}`.

2. **Never log passwords or hashes:** `user_service.py` and `cli.py` log only `user_id` and `email` in INFO messages. Log lines must contain no password-derived values.

3. **Auth data confinement:** JWT signing and bcrypt hashing are confined to `src/utils/auth.py`. `user_service.py` imports `hash_password` but does not call `create_jwt` or `decode_jwt` — those remain in `auth_service.py` and the auth guard.

4. **No `/api/me/` endpoint in this RFC scope:** Self-service profile edit (a Reader updating their own password) is out of scope. If added later, it requires a separate endpoint with different RBAC logic. Do not reuse the `/api/users/{id}` PATCH endpoint for self-service — the Admin guard would need to be bypassed.

5. **User ID from JWT, not request body:** The self-delete guard uses `request.state.user_id` (set by `AuthMiddleware` from the JWT `sub` claim). It does not trust any user-supplied ID in the request body.

6. **CLI does not accept environment variables for password:** The CLI uses `getpass.getpass()` or `--password` CLI argument only. No `HT_NEW_PASSWORD` env var — that would expose the password in process listings and shell history.

---

## 13. Files to Create / Modify

### New Files

| Path | Purpose | Est. lines |
|---|---|---|
| `src/api/routers/users.py` | CRUD endpoints for User management (Admin only) | ~80 |
| `src/services/user_service.py` | User business logic: guards, hashing orchestration | ~90 |
| `src/cli.py` | `python -m src.cli reset-password` command | ~65 |
| `src/ui/pages/settings_users.py` | Admin user management page at `/settings/users` | ~180 |
| `src/ui/components/auth_guard.py` | Role-check utilities shared across all NiceGUI pages | ~50 |
| `tests/unit/test_user_service.py` | Unit tests for user_service guards | ~120 |
| `tests/integration/test_users_api.py` | Integration tests for `/api/users/` RBAC | ~150 |
| `tests/integration/test_rbac_coverage.py` | "All routes covered" assertion test | ~50 |

### Modified Files

| Path | Change | Scope |
|---|---|---|
| `src/domain/rbac.py` | Add `dependency._rbac_protected = True` inside `require_role` | 1 line |
| `src/api/routers/auth.py` | Add `require_role(Role.Reader)` to `POST /auth/logout` | 2 lines + 2 imports |
| `src/api/app.py` | Import and register `users_router` | 2 lines |
| `src/repositories/user_repository.py` | Add `count_by_role(session, role)` function | ~8 lines |
| `src/ui/pages/login.py` | Store `role` and `user_id` from decoded JWT in user storage after login | ~3 lines |
| `src/ui/pages/topology.py` | Replace auth check with `auth_guard` helpers; inject `HT_READONLY` for Readers | ~10 lines |
| `src/ui/pages/inventory.py` | Replace auth check with `auth_guard` helpers; hide write buttons for Readers | ~10 lines |
| `src/ui/pages/settings_locations.py` | Replace auth check with `auth_guard` helpers; require Contributor minimum | ~5 lines |
| `src/ui/components/canvas.py` | Gate write-capable Cytoscape event handlers on `!window.HT_READONLY` | JS inline change |

---

## 14. Validation

**Pre-push gate (Project-Manager enforces):**

```bash
docker compose exec api pytest tests/unit/test_user_service.py -v
docker compose exec api pytest tests/integration/test_users_api.py -v
docker compose exec api pytest tests/integration/test_rbac_coverage.py -v
docker compose exec api pytest  # all 308 + new tests pass
docker compose exec api mypy src/ --ignore-missing-imports  # zero new errors
docker compose build
```

**Acceptance criteria mapping:**

| Story | Acceptance Criterion | Validated by |
|---|---|---|
| HT-011 | Reader gets 403 on any write endpoint | `test_reader_list_returns_403` (users) + parametrized RBAC matrix for others |
| HT-011 | Contributor gets 403 on user management | `test_contributor_list_returns_403` |
| HT-011 | All routes have explicit role check | `test_rbac_coverage.py` |
| HT-011 | Admin has no restrictions | All admin happy-path tests pass |
| HT-019 | Self-delete blocked | `test_admin_self_delete_returns_400` |
| HT-019 | Last-admin-delete blocked | `test_admin_delete_last_admin_returns_400` |
| HT-019 | Email uniqueness enforced | `test_create_user_duplicate_email_returns_409` |
| HT-019 | `password_hash` never in response | `test_user_response_never_contains_password_hash` |
| HT-017 | User not found → exit 1 | `test_cli_user_not_found` (unit test with mocked session) |
| HT-017 | Password < 8 chars → exit 1 | `test_cli_short_password` |
| HT-017 | Interactive prompt when `--password` omitted | Verified via `getpass.getpass` mock in unit test |
