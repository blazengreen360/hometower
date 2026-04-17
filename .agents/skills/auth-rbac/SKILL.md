---
name: auth-rbac
description: Hometower's authentication and RBAC model — three roles (Admin/Contributor/Reader), permission matrix, JWT flow, bcrypt passwords, token revocation via token_version, optimistic locking. Read this when working on auth, middleware, role checks, or any endpoint security.
---

# auth-rbac

## Roles

Three roles: `Admin` > `Contributor` > `Reader`

| Operation | Reader | Contributor | Admin |
|---|---|---|---|
| View devices, topologies, history, workspaces | Y | Y | Y |
| Create/edit devices, connections, topologies | - | Y | Y |
| Delete devices, connections | - | Y | Y |
| Manage users, system settings | - | - | Y |
| Enter edit mode on canvas | - | Y | Y |

## Auth Flow

- Passwords: bcrypt via `passlib` — `src/utils/auth.py` (`hash_password()`, `verify_password()`)
- Sessions: JWT via `python-jose` — enforced in `src/api/middleware/auth.py`
- Token revocation: increment `User.token_version` to invalidate all existing tokens
- First admin: seeded from `ADMIN_EMAIL` + `ADMIN_PASSWORD` in `.env` on first boot

## Route Protection

Every endpoint must have `Depends(require_role(Role.X))`:
- Read ops: `Role.READER`
- Write ops: `Role.CONTRIBUTOR`
- Admin ops: `Role.ADMIN`

No unprotected routes. Ever.

## Concurrency

Optimistic locking via `version` field on `Device` + `DiagramLayout`. Client sends current `version`; service rejects stale updates.
