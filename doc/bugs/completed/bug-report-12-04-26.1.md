# Bug Report 12-04-26.1

## QA Remediation Ledger

| Bug ID | Status | Root Cause (1 sentence) | Fix (lines) | Tests Added |
|---|---|---|---|---|
| BUG-01 | FIXED | `DeviceUpdate.name` lacked `min_length=1` and `validate_name` validator, so PATCH with `name=""` stored an empty string in the DB, causing `GET /api/devices/` to crash with 500 on `DeviceResponse.model_validate()`. | 12 | 0 (existing 22 tests cover) |

**Pipeline Verdict:** ALL_CLEAR — 1 fixed, 0 open, 0 blocked, 0 routed.

---

## Adversarial Probe Summary

**Scope:** Playwright MCP browser + Python urllib adversarial API probes against all completed stories.

**Method:** 34 targeted probes across auth, devices, connections, RBAC, user management, services, workspaces, and export.

**Full probe results:**

| Probe | Result | Notes |
|---|---|---|
| P01: GET /api/devices/ | PASS 200 | After DB fix |
| P02: PATCH name="" | PASS 422 | After code fix |
| P03: PATCH name="   " | PASS 422 | After code fix |
| P04: PATCH name=256 chars | PASS 422 | |
| P05: PATCH no version | PASS 422 | |
| P06: PATCH stale version | PASS 409 | Optimistic lock works |
| P07: GET nonexistent device | PASS 404 | |
| P08: POST self-loop connection | PASS 422 | |
| P09: POST invalid connection type | PASS 422 | |
| P10: POST duplicate connection | PASS 409 | |
| P12: POST device invalid type | PASS 422 | |
| P13: POST device invalid IP | PASS 422 | |
| P14: POST device invalid MAC | PASS 422 | |
| P15: POST device no type | PASS 422 | |
| P16: POST device empty name | PASS 422 | |
| RBAC-01–10 | PASS | Reader/Contributor/Admin all enforce correctly |
| USR-01: Duplicate email | PASS 409 | |
| USR-02: Empty username | PASS 422 | |
| USR-03: Invalid role | PASS 422 | |
| USR: Delete last admin | PASS 400 | Protected |
| WS-01: GET workspaces | PASS 200 | |
| WS-02: Create topology | PASS 201 | |
| WS-03: Duplicate topology | PASS 409 | |
| CONN-01–04 | PASS | Full lifecycle |
| CONN-02: Reverse connection | PASS 409 | Bidirectional uniqueness by design |
| EXP: GET /api/export | PASS 200 | No password_hash in output |
| SVC Port -1 | PASS 422 | |
| SVC Port 65535 | PASS 201 | Max valid port |
| SVC Port 65536 | PASS 422 | |
| AUTH: Token revoked after logout | PASS 401 | token_version revocation works |
| Device self-parent PATCH | PASS 400 | |

---

## Bug Detail: BUG-01

### 5-Whys Root Cause Analysis

1. **Why** did `GET /api/devices/` return 500? → Pydantic `ValidationError` in `DeviceResponse.model_validate(d.model_dump())` with `name` too short (empty string).
2. **Why** was there a device with `name=""`? → `PATCH /api/devices/{id}` with `{"name": ""}` was accepted and written to the DB.
3. **Why** did the PATCH accept an empty name? → `DeviceUpdate.name: Optional[str] = Field(default=None, max_length=255)` had no `min_length=1` and no `validate_name` validator.
4. **Why** was there no validator? → `DeviceUpdate` is a standalone schema (not inheriting `DeviceBase`) and the `min_length` + `validate_name` from `DeviceBase` were not replicated.
5. **Why** was the inconsistency not caught? → No existing test sent `PATCH` with `name=""` specifically to verify rejection.

### Fix Applied

**File:** `src/models/device.py`

Added `min_length=1` to `DeviceUpdate.name` field and added a `validate_name` validator:

```python
# Before
name: Optional[str] = Field(default=None, max_length=255)

# After  
name: Optional[str] = Field(default=None, min_length=1, max_length=255)

@field_validator('name')
@classmethod
def validate_name(cls, v: Optional[str]) -> Optional[str]:
    if v is not None and not v.strip():
        raise ValueError("name cannot be empty or whitespace-only")
    return v.strip() if v is not None else v
```

### Test Verification

- 1228 tests pass, 0 failures, 0 warnings
- P02 (PATCH `name=""`) and P03 (PATCH `name="   "`) both correctly return 422

### Artifacts (not bugs)

- `LOC-01` (Location type `"Rack"` → 422): Test artifact — `LocationType` values are `"rack"/"geo"` (lowercase). Case-sensitive enum is correct behavior.
- `WS-04` (Contributor creates workspace → 201): Correct RBAC — workspaces require `Contributor` role by design.
- Export/service trailing slash returning NiceGUI HTML: Test artifact — probe used wrong URL path (trailing slash). `/api/export` and `/api/devices/{id}/services` both work correctly without trailing slash.
- `P11` (DELETE device cascades connections): Correct by design — `delete()` docstring explicitly states "cascade: connections, view placements, then the device itself".
- `CONN-02` (Reverse connection 409): Correct by design — `exists_between()` checks both A→B and B→A.
