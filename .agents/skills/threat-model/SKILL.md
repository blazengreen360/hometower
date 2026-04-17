---
name: threat-model
description: Hometower's security threat model — architecture trust boundaries, known previously-fixed vulnerabilities, and STRIDE threat lanes mapped to specific files. Read this when performing security audits or reviewing auth/data-handling code.
---

# threat-model

## Architecture Security Boundaries

```
Browser (untrusted)
    |
    +-- JWT in sessionStorage (accessible to XSS)
    +-- Cytoscape.js canvas (renders user-supplied labels)
    +-- Leaflet.js map (renders location names in popups)
    |
    v
FastAPI (trust boundary -- JWT + RBAC enforcement)
    |
    +-- src/api/middleware/auth.py -- JWT decode + role check
    +-- src/api/routers/ -- Depends(require_role(...))
    |
    v
Service Layer (trusted -- owns transactions)
    |
    v
PostgreSQL (trusted -- constraints are last line of defense)
```

**Key trust boundaries:**
1. Browser -> API: JWT validation, input sanitization, RBAC
2. API -> Service: delegation only (no direct DB access from routers)
3. Service -> DB: parameterized queries (no SQL injection)
4. DB -> API response: no password hashes or secrets in response schemas
5. DB -> UI render: HTML escaping before embedding in JS/HTML

## Known Previously-Fixed Vulnerabilities

Regression checklist — verify fixes still hold and new code doesn't reintroduce:

| Finding | CWE | What to Check |
|---|---|---|
| Hardcoded `SECRET_KEY` in `.env` | CWE-798 | `.env` in `.gitignore`? New hardcoded secrets? |
| Stateless JWT (no revocation) | CWE-613 | `token_version` checked on decode? New endpoints bypass? |
| Device names unescaped in Cytoscape | CWE-79 | `html.escape()`/`_escapeHtml()` on all user labels? New labels without escaping? |
| Connection labels in `confirm()` dialogs | CWE-79 | `_escapeHtml()` in all dialog messages? |
| Missing DB uniqueness constraints | CWE-362 | New models without unique constraints? |
| Email logged on auth failure | CWE-532 | New log statements with user-supplied PII? |

## STRIDE Threat Lanes (file targets)

| Lane | STRIDE | Target Files | Hunt For |
|---|---|---|---|
| JWT Auth | Tampering/Spoofing | `src/utils/auth.py`, `src/api/middleware/auth.py` | Algorithm confusion, expired token accepted, `token_version` bypass, short secret key |
| Plaintext Leaks | Info Disclosure | All `logger.*` calls across `src/` | Device IPs/MACs in error logs, JWT payloads in debug, emails in auth failure, stack traces |
| Stored XSS | Elevation | `canvas*.py`, `topology_data.py`, `map_view.py`, `ui.label()` calls | Unescaped strings in `ui.run_javascript()`, `innerHTML`, Cytoscape/Leaflet labels without sanitization |
| RBAC Bypass | Elevation/Spoofing | All `src/api/routers/*.py` | Missing `Depends(require_role(...))`, wrong role level, IDOR on device IDs |
| Secret Lifecycle | Info Disclosure | `src/utils/auth.py`, `src/utils/settings.py`, `.env`, `docker-compose.yml` | Passwords in API responses, bcrypt hash outside User model, key reuse |
| SQL Injection | Tampering | `src/repositories/`, any `session.execute()`/`session.exec()` | f-string SQL, `.text()` with interpolation, unparameterized user strings |
| Export/Backup Auth | Info Disclosure | `src/api/routers/data_transfer.py`, `src/services/export_service.py` | Export callable by Reader, exported JSON with `password_hash`, secrets in custom fields |
| Geo/Leaflet Injection | Tampering | `src/ui/components/map_view.py` | Location names in popup HTML without escaping, `innerHTML` with user content |
| DB Integrity | Tampering | All `src/models/*.py` | Missing UNIQUE, missing `ondelete="CASCADE"`, missing CheckConstraint for self-refs |
| Supply Chain | Mixed | `requirements.txt`, `Dockerfile`, `docker-compose.yml` | Known CVEs, EOL versions, missing integrity checks |

## Security Orchestrator Lane Assignments

| Lane | STRIDE | Boundary |
|---|---|---|
| lane-1 | Tampering/Spoofing | JWT Auth. Browser->API. |
| lane-2 | Info Disclosure | Plaintext leaks. App->Logs. |
| lane-3 | Elevation | SQLi & Pydantic. API->DB. |
| lane-4 | Info Disclosure | Secret lifecycle. Bcrypt/JWT/`.env`. |
| lane-5 | Spoofing/Elevation | RBAC bypass. All routers + `rbac.py`. |
| lane-6 | Tampering | XSS. Canvas + map. DB->UI render. |
| lane-7 | Tampering | SQLModel integrity. DB constraints. |
| lane-8 | Info Disclosure | Backup/Export. API->External. |
| lane-9 | Elevation | RBAC wildcard. Reader data exposure. |
| lane-10 | Mixed | Supply chain & infra. Docker/deps. |
