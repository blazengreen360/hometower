# Security-Orchestrator Findings Report: 11-04-26.2

**Date:** 12 April 2026
**Target:** Hometower Phase 1
**Auditors:** Security-Orchestrator + Security-Auditor lanes (STRIDE-per-element)
**Methodology:** STRIDE-per-element | DREAD Scoring | CWE Mandatory Mapping

---

## Lanes Dispatched
| Lane | STRIDE Element | Finding |
|---|---|---|
| L1 | Spoofing — Auth & Session | PASS (strong) |
| L2 | Tampering — Import pipeline | **FINDING: SEC-1104-01** |
| L3 | Repudiation — Logging | PASS |
| L4 | Information Disclosure | **FINDING: SEC-1104-02, SEC-1104-03** |
| L5 | Denial of Service — Rate Limits | **FINDING: SEC-1104-04** |
| L6 | Elevation of Privilege — RBAC/IDOR | **FINDING: SEC-1104-05** |

---

## Confirmed Findings

---

### SEC-1104-01 · HIGH
**STRIDE:** Tampering  
**CWE:** CWE-400 (Uncontrolled Resource Consumption)  
**File:** `src/api/routers/data_transfer.py` (Line 141)

**Title:** Raw SQLAlchemy `exc.orig` Leaked in HTTP 422 Response

**Description:**  
When a database `IntegrityError` occurs during the JSON import pipeline, the raw `exc.orig` object — which is the underlying database driver exception — is directly formatted into the HTTP response detail string:

```python
raise HTTPException(status_code=422, detail=f"Import failed: {exc.orig}")
```

PostgreSQL's driver exceptions include detailed schema information in their messages: table names, column names, constraint names, and in some driver versions, partial row data. This enables a malicious Admin user to perform **schema enumeration attacks** and learn internal database structure by submitting crafted import payloads designed to trigger specific foreign key or unique constraints.

**DREAD Score:** 6.0 / 10  
Damage: 5 | Reproducibility: 9 | Exploitability: 7 | Affected Users: 2 | Discoverability: 6

**Verify PoC:**
- Setup: Log in as Admin.
- Action: `POST /api/import?confirm=true` with a malformed JSON payload that references non-existent foreign keys.
- Expected: `422` with generic message `"Import failed: integrity error"`.
- Actual: `422` body includes PostgreSQL error string with table and constraint names.
- Negative Control: `POST /api/import?confirm=true` with a valid payload returns `200`.

**Remediation:** Replace with a sanitized static message:
```python
raise HTTPException(status_code=422, detail="Import failed: data integrity violation") from exc
```

---

### SEC-1104-02 · HIGH
**STRIDE:** Information Disclosure  
**CWE:** CWE-200 (Exposure of Sensitive Information)  
**File:** `src/api/routers/health.py` (Lines 29–52)

**Title:** Unauthenticated Health Endpoint Reveals Internal Application Version

**Description:**  
`GET /api/health` is correctly listed in `EXCLUDED_API_PATHS` and thus **requires no authentication**. The endpoint returns the exact `version` string (`__version__`). While version disclosure is not critical in isolation, for a self-hosted homelab tool, this is a high-value reconnaissance target. An unauthenticated scanner enumerating the network can:
1. Confirm Hometower is running on this host.
2. Identify the exact version.
3. Look up published CVEs for that specific version.

**DREAD Score:** 5.5 / 10  
Damage: 4 | Reproducibility: 10 | Exploitability: 8 | Affected Users: 1 | Discoverability: 10

**Remediation (two options):**
- **Option A (Recommended):** Move `/api/health` to require `Reader` role minimum. Update `EXCLUDED_API_PATHS` accordingly.
- **Option B:** Return `"version": "ok"` for unauthenticated requests, and the real version only when a valid token is present.

---

### SEC-1104-03 · MEDIUM
**STRIDE:** Information Disclosure  
**CWE:** CWE-497 (Exposure of System Data to Unauthorized User)  
**File:** `src/api/routers/system.py` (Line 41–43) + `src/services/system_service.py` (Line 39–41)

**Title:** DB Version String Revealed to All Authenticted Readers

**Description:**  
`GET /api/system/stats` returns `db_version` — the full PostgreSQL `SELECT version()` output string — to any user with `Reader` role. This string typically looks like:
```
PostgreSQL 16.2 on x86_64-pc-linux-gnu, compiled by gcc (Debian 12.2.0) 14.2.0, 64-bit
```

This exposes the exact PostgreSQL version, OS architecture, compiler version, and sometimes kernel details to all users, enabling targeted exploitation of known PostgreSQL version-specific CVEs.

**DREAD Score:** 5.0 / 10  
Damage: 5 | Reproducibility: 10 | Exploitability: 5 | Affected Users: 3 | Discoverability: 5

**Remediation:** Gate `db_version` and `db_size_bytes` behind `Role.Admin` (same as `users`). The current code already checks role for the `users` field — apply the same pattern to DB diagnostics.

---

### SEC-1104-04 · MEDIUM
**STRIDE:** Denial of Service  
**CWE:** CWE-770 (Allocation of Resources Without Limits)  
**File:** `src/api/middleware/rate_limit.py`, `src/api/routers/auth.py`

**Title:** Rate Limiting Applied Only to Login — All Other Endpoints Unthrottled

**Description:**  
The `@limiter.limit("5/minute")` decorator is correctly applied to `POST /api/auth/login`, defending against brute-force credential attacks. However, `slowapi` is **not applied** to any other endpoint. Expensive operations are fully unthrottled:
- `GET /api/export` — triggers a full DB dump on every call. A Contributor can hammer this in a loop.
- `DELETE /api/devices/{id}` — no limit.
- `POST /api/import?confirm=true` — reading 50MB payloads and executing TRUNCATE/INSERT on every request with no throttle. Admin-only but still a DoS vector.

**DREAD Score:** 5.0 / 10  
Damage: 5 | Reproducibility: 8 | Exploitability: 6 | Affected Users: 3 | Discoverability: 5

**Remediation:** Add rate limit decorators to the `export` and `import` endpoints at minimum:
```python
@limiter.limit("3/minute")  # export
@limiter.limit("1/minute")  # import
```

---

### SEC-1104-05 · HIGH
**STRIDE:** Elevation of Privilege / IDOR  
**CWE:** CWE-639 (Authorization Bypass Through User-Controlled Key)  
**File:** `src/services/diagram_service.py` (all mutating methods)

**Title:** Missing Workspace Ownership Check on DiagramLayout Mutations (Confirms BUG-1102-02)

**Description:**  
This finding validates the IDOR identified in report 11-04-26.2. Security-Auditor independently reproduced via STRIDE analysis:

`topology_service.py` correctly calls `_verify_workspace_ownership(workspace_id, owner_id, session)` before any mutation. In contrast, `diagram_service.py`'s `update()`, `delete()`, `partial_update()`, and `update_timestamp()` methods accept only a `layout_id` and perform zero ownership traversal. Since `DiagramLayout.topology_id` is nullable (see `src/models/diagram.py` Line 24), even a topology-scoped check would silently pass for orphaned legacy layouts.

**DREAD Score:** 8.0 / 10  
Damage: 8 | Reproducibility: 9 | Exploitability: 7 | Affected Users: 4 | Discoverability: 5

---

## Validated PASS Controls

| Control | Status | Evidence |
|---|---|---|
| JWT signature + `token_version` revocation | ✅ PASS | `auth.py` L66 — revocation checked per-request against DB |
| Password hashing (bcrypt rounds=12) | ✅ PASS | `auth.py` L14 |
| HttpOnly + SameSite=Strict cookie | ✅ PASS | `auth.py` L64–65 |
| Placeholder secret rejection at startup | ✅ PASS | `settings.py` L31–55 |
| CSP headers (with known weak `unsafe-inline`) | ✅ PASS\* | `security_headers.py` — `unsafe-inline` required by NiceGUI |
| CORS locked to `api_base_url` | ✅ PASS | `app.py` L83 |
| Login brute-force rate limiting | ✅ PASS | `auth.py` L39 |
| Storage secret auto-derivation | ✅ PASS | `settings.py` L60 |

---

## Routing

| ID | Severity | Route |
|---|---|---|
| SEC-1104-01 | HIGH | QA-Fixer (one-line fix in `data_transfer.py`) |
| SEC-1104-02 | HIGH | Architect decision required (scope: EXCLUDED_API_PATHS) |
| SEC-1104-03 | MEDIUM | QA-Fixer (`system.py` role gate) |
| SEC-1104-04 | MEDIUM | Feature-Engineer (add `@limiter.limit` decorators) |
| SEC-1104-05 | HIGH | QA-Fixer (ownership check in `diagram_service.py`) |
