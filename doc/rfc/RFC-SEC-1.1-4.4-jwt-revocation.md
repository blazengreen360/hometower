# RFC: JWT Revocation and Secure Token Storage

**Addresses:** Security findings 1.1 (no server-side revocation) and 4.4 (token in sessionStorage)  
**Date:** 2026-04-11

---

## 1. Design Decisions

| # | Decision | Rationale |
|---|---|---|
| A | **Token versioning** (not a JTI blocklist) | Blocklists grow unboundedly and cannot invalidate all tokens on password change without tracking every issued JTI. A `token_version` integer per user handles both use cases with a single column and a single indexed read per request. |
| B | **Token version check in middleware** (not inside `decode_jwt`) | `src/utils/auth.py` hides JWT crypto (signature + expiry). Revocation logic belongs to `src/api/middleware/auth.py`, which already owns the request-time security check. `decode_jwt` stays a pure function. |
| C | **HttpOnly cookie** replaces `sessionStorage` | `sessionStorage` is readable by any JS on the page. HttpOnly cookies are not. Same-origin + SameSite=Strict blocks CSRF. The Authorization header fallback is kept for programmatic API clients. |
| D | **No new tables, no external services** | `token_version INT DEFAULT 1` on the existing `users` table is sufficient for both logout and password-change invalidation. |

**Module hiding test:**
- `src/utils/auth.py` hides JWT crypto (HS256 signing, claim encoding/decoding)
- `src/api/middleware/auth.py` hides the revocation mechanism (token_version comparison)
- `src/repositories/user_repository.py` hides the increment query
- `src/api/routers/auth.py` hides cookie mechanics (Set-Cookie / Clear-Cookie headers)

---

## 2. Token Format Changes

Add three claims to every JWT. **`create_jwt` signature is unchanged** — callers pass a payload dict; the function appends the new claims internally.

```python
# src/utils/auth.py — new claims added inside create_jwt()
"jti":     str(uuid.uuid4())           # unique token ID (for future audit logging)
"iat":     int(utcnow().timestamp())   # issued-at (Unix seconds)
"version": int                         # caller MUST include this; equals user.token_version at time of issue
```

`decode_jwt` adds a guard for the three new required claims (`jti`, `iat`, `version`) alongside the existing `sub`/`role` check. Raises `JWTError` if any are missing. Return type remains `dict[str, str | int]`.

---

## 3. Data Model Change

**File:** `src/models/user.py`

Add one field to `User` (not `UserBase` — it is internal state, never exposed in API responses):

```python
token_version: int = Field(default=1)
```

**Migration:** `alembic/versions/018_add_user_token_version.py`

```sql
ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 1;
```

No data backfill needed. Existing rows get `token_version=1`. All existing tokens carry no `version` claim → middleware rejects them on first use (users re-login, which is acceptable per requirements).

> **DevOps-Engineer migration review required.**

---

## 4. Repository Change

**File:** `src/repositories/user_repository.py`

Add one function:

```python
def increment_token_version(session: Session, user_id: uuid.UUID) -> None:
    """Atomically increment token_version, invalidating all issued tokens for this user."""
    user = session.get(User, user_id)
    if user is not None:
        user.token_version += 1
        session.add(user)
        # caller commits
```

---

## 5. Service Layer Changes

**File:** `src/services/auth_service.py`

### 5a. `authenticate()` — include `version` in payload

```python
def authenticate(email: str, password: str, session: Session) -> tuple[str, int, str]:
    """Returns (jwt_token, token_exp_unix, role_value)."""
    # ... existing validation ...
    expire_unix = int((datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)).timestamp())
    token = create_jwt({
        "sub": str(user.id),
        "role": user.role.value,
        "version": user.token_version,
    })
    return token, expire_unix, user.role.value
```

### 5b. `change_own_password()` — invalidate tokens after hash update

At the end of the existing function, after `session.commit()`, add:

```python
user_repository.increment_token_version(session, user_id)
session.commit()
logger.info("Tokens invalidated for user_id={} after password change", user_id)
```

### 5c. New: `revoke_tokens()`

```python
def revoke_tokens(user_id: uuid.UUID, session: Session) -> None:
    """Invalidate all tokens for a user by incrementing their token_version."""
    user_repository.increment_token_version(session, user_id)
    session.commit()
    logger.debug("Token version incremented for user_id={}", user_id)
```

---

## 6. Middleware Change

**File:** `src/api/middleware/auth.py`

**New import:** `from sqlmodel import Session` and `from src.utils.db import engine`

**Token extraction order (inside `dispatch`):**

1. Check cookie `ht_access_token` first.
2. Fallback to `Authorization: Bearer` header.
3. If neither present → 401.

**After `decode_jwt(token)` succeeds, add version check:**

```python
user_id = uuid.UUID(payload["sub"])
with Session(engine) as db_session:
    user = db_session.get(User, user_id)
if user is None or user.token_version != payload.get("version"):
    return JSONResponse({"detail": "Token revoked"}, status_code=401)
```

The DB open/close is scoped to this single middleware check. It is one indexed primary-key lookup — acceptable for homelab scale.

---

## 7. API Layer Changes

**File:** `src/api/routers/auth.py`

### 7a. New response schema

Replace `TokenResponse` with:

```python
class LoginResponse(BaseModel):
    user_id: str
    role: str
    token_exp: int   # Unix timestamp — used by NiceGUI UI for client-side expiry guard
    token_type: str = "cookie"
```

### 7b. `login()` — set HttpOnly cookie, return `LoginResponse`

```python
@router.post("/auth/login", response_model=LoginResponse)
@limiter.limit("5/minute")
async def login(request: Request, data: LoginRequest, session: Session = Depends(get_session)) -> Response:
    token, token_exp, role = authenticate(data.email, data.password, session)
    user_id = decode_jwt(token)["sub"]
    response = JSONResponse({
        "user_id": user_id,
        "role": role,
        "token_exp": token_exp,
        "token_type": "cookie",
    })
    response.set_cookie(
        key="ht_access_token",
        value=token,
        httponly=True,
        samesite="strict",
        secure=settings.cookie_secure,
        path="/api",
        max_age=settings.jwt_expire_hours * 3600,
    )
    return response
```

### 7c. `logout()` — revoke server-side + clear cookie

```python
@router.post("/auth/logout", dependencies=[Depends(require_role(Role.Reader))])
async def logout(request: Request, session: Session = Depends(get_session)) -> Response:
    user_id = uuid.UUID(request.state.user_id)
    auth_service.revoke_tokens(user_id, session)
    response = JSONResponse({"detail": "Logged out"})
    response.delete_cookie(key="ht_access_token", path="/api")
    return response
```

---

## 8. Settings Change

**File:** `src/utils/settings.py`

Add one field:

```python
cookie_secure: bool = False   # set True if HTTPS is terminated at this host
```

Document in `.env.example`: `COOKIE_SECURE=false  # set true when serving over HTTPS`

---

## 9. UI Changes

**File:** `src/ui/pages/login.py`

JS fetch block changes:
1. Add `credentials: 'include'` to the `fetch` call options.
2. Remove `sessionStorage.setItem('access_token', data.access_token)` — cookie is set by the server.
3. Response body now returns `{user_id, role, token_exp}` (no `access_token`).

Python handler changes (inside `handle_login`):
- Remove: `nicegui_app.storage.user["access_token"] = token`
- Remove: `payload = decode_jwt(token)` (no token in JS)
- Store from response body:
  ```python
  nicegui_app.storage.user["role"] = result["role"]
  nicegui_app.storage.user["user_id"] = result["user_id"]
  nicegui_app.storage.user["token_exp"] = result["token_exp"]
  nicegui_app.storage.user["username"] = result.get("email", "")
  ```

**File:** `src/ui/components/auth_guard.py`

Replace `get_ui_role()` — no longer decodes a JWT (the token is an HttpOnly cookie, invisible to Python-side NiceGUI code):

```python
def get_ui_role() -> Optional[Role]:
    role_str = nicegui_app.storage.user.get("role")
    token_exp = nicegui_app.storage.user.get("token_exp", 0)
    if not role_str or datetime.now(timezone.utc).timestamp() >= token_exp:
        for key in ("role", "user_id", "token_exp", "username"):
            nicegui_app.storage.user.pop(key, None)
        return None
    try:
        return Role(role_str)
    except ValueError:
        return None
```

`redirect_if_unauthenticated()` changes:
- Replace `had_token = bool(nicegui_app.storage.user.get("access_token"))` with `had_token = bool(nicegui_app.storage.user.get("role"))`.
- Rest of the function is unchanged.

Any remaining `app.storage.user["access_token"]` references in `src/ui/` must be removed. Import of `decode_jwt` in `auth_guard.py` is removed; import in `login.py` is removed.

---

## 10. Files to Create / Modify

| File | Action | Purpose |
|---|---|---|
| `alembic/versions/018_add_user_token_version.py` | **Create** | `ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 1` |
| `src/models/user.py` | **Modify** | Add `token_version: int = Field(default=1)` to `User` |
| `src/utils/settings.py` | **Modify** | Add `cookie_secure: bool = False` |
| `src/utils/auth.py` | **Modify** | `create_jwt` appends `jti`, `iat`, `version`; `decode_jwt` validates new required claims |
| `src/repositories/user_repository.py` | **Modify** | Add `increment_token_version(session, user_id)` |
| `src/services/auth_service.py` | **Modify** | `authenticate` returns `(token, exp, role)`; `change_own_password` calls `increment_token_version`; add `revoke_tokens` |
| `src/api/routers/auth.py` | **Modify** | `login` sets cookie + returns `LoginResponse`; `logout` revokes + clears cookie; replace `TokenResponse` |
| `src/api/middleware/auth.py` | **Modify** | Read cookie or header; add token-version DB check after `decode_jwt` |
| `src/utils/settings.py` | (see above) | |
| `src/ui/pages/login.py` | **Modify** | `credentials: 'include'`, remove sessionStorage, store `role`/`user_id`/`token_exp` from response body |
| `src/ui/components/auth_guard.py` | **Modify** | `get_ui_role` reads storage role + exp; remove `decode_jwt` usage; update `redirect_if_unauthenticated` |

---

## 11. Validation

| Constraint | Test file |
|---|---|
| Logout invalidates token (version check fails) | `tests/unit/test_auth_service.py` |
| Password change invalidates all tokens | `tests/unit/test_auth_service.py` |
| Expired token still rejected (existing behaviour) | `tests/unit/test_auth_utils.py` |
| Missing `version` claim rejected | `tests/unit/test_auth_utils.py` |
| Cookie set on login (HttpOnly, SameSite=strict) | `tests/integration/test_auth_router.py` |
| Cookie cleared on logout | `tests/integration/test_auth_router.py` |
| Authorization-header fallback still works | `tests/integration/test_auth_router.py` |
| Middleware rejects stale version after logout | `tests/integration/test_auth_middleware.py` |
