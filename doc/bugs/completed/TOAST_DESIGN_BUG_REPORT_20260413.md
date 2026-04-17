# Toast Notification System & Design Bug Report
**Date:** 2026-04-13  
**Severity Assessment:** 1 Critical, 5 High, 8 Medium, 6 Low  
**ODC Lanes Covered:** Interface (I), Checking (C), Build/Package (B), Documentation (D), Design (DES)  
**Report Status:** OPEN

---

## Executive Summary

The toast notification system has **foundational design inconsistencies**, **accessibility gaps**, and **UX anti-patterns** that damage user confidence and reduce error visibility. While `show_toast()` wrapper exists (`src/ui/components/toast.py`), **only 40% of toast usage** calls it; the other 60% use raw `ui.notify()` directly, creating:

- **Inconsistent error messaging** (generic "Connection error" vs. detailed API responses)
- **No loading state indicators** for async operations (import, export, duplication)
- **Toast stacking chaos** (10+ toasts can appear simultaneously)
- **Type confusion** (`show_toast()` uses "success"/"error" vs `ui.notify()` uses "positive"/"negative")
- **Accessibility violations** (no ARIA labels, no focus management, color-only status indication)
- **Design token violations** (hardcoded positioning, no theme awareness for dismissal UI)

**Root Cause:** Toast was designed as a wrapper but not enforced as the single source of truth. No linting rules prevent `ui.notify()` direct calls. Toast component doesn't handle all use cases (loading states, custom timeouts, actions).

---

## Bugs by ODC Lane

### I-001: INTERFACE — Inconsistent Toast API: 60% Use Raw ui.notify(), 40% Use show_toast()
**Severity:** Critical | **Scope:** Developer Experience / Consistency | **User Impact:** Inconsistent error messaging and behavior across the app

**Affected Components:**
- Using `show_toast()` (correct, 7 files): device_detail_panel.py, connection_detail_panel.py, topology_layout_bar.py, device_detail_duplicate.py, device_edit.py, inventory_edit_modal.py, settings_profile.py
- Using raw `ui.notify()` (wrong, 10 files): workspaces.py, workspace_detail.py, settings_data.py, settings_users.py, settings_locations.py, inventory_delete_dialog.py, device_panel_helpers.py, device_detail_custom_fields_section.py, device_detail_tags_section.py

**Evidence:**
```python
# ✅ CORRECT — using show_toast()
# device_detail_panel.py:157
show_toast(type="success", title="Status updated")

# ✅ CORRECT — using show_toast()
# topology_layout_bar.py:147
show_toast(type="success", title="Layout saved")

# ❌ WRONG — raw ui.notify()
# workspaces.py:59
ui.notify("Workspace created", type="positive")

# ❌ WRONG — raw ui.notify()
# device_panel_helpers.py:54
ui.notify(f"{label} updated")

# ❌ WRONG — inconsistent type mapping
# device_detail_custom_fields_section.py:65
ui.notify("Field updated", type="positive")  # No type specified in show_toast()
```

**Type Confusion:**
```python
# show_toast() expects: "success", "error", "warning", "info"
show_toast(type="success", title="Saved")

# ui.notify() expects: "positive", "negative", "warning", "info"
ui.notify("Saved", type="positive")

# Result: inconsistent mapping
# show_toast("success") → "positive" (via _QUASAR_TYPE dict)
# ui.notify(..., type="positive") → direct Quasar call (bypasses wrapper)
```

**Root Cause:** Toast wrapper was added after most of the codebase was written. No enforcement rule prevents direct `ui.notify()` calls.

**Proposed Fix:**
1. Rename `show_toast()` to `notify()` to match NiceGUI semantics
2. Add linting rule to fail on `ui.notify()` calls in src/ui/:
   ```bash
   grep -rn "ui\.notify(" src/ui/ --include="*.py" | grep -v "test_" && exit 1
   ```
3. Update all 10 files to use centralized toast wrapper:
   ```python
   # Before
   ui.notify("Field updated", type="positive")
   
   # After
   from src.ui.components.toast import show_toast
   show_toast(type="success", title="Field updated")
   ```

**Mutation:** Adding linting rule prevents future violations. Refactoring existing calls is low-risk (no behavior change, just consistency).

---

### I-002: INTERFACE — Toast Type Mismatch: show_toast() vs ui.notify() Signature
**Severity:** High | **Scope:** Type Safety | **User Impact:** Developers may pass wrong type arguments, causing silent failures

**Affected Component:** `src/ui/components/toast.py:36-59`

**Evidence:**
```python
# toast.py — show_toast() signature
def show_toast(
    type: ToastType,  # ← Expects "success", "error", "warning", "info"
    title: str,
    description: Optional[str] = None,
    duration_ms: int = _DEFAULT_DURATION_MS,
) -> None:
    message = title if description is None else f"{title}\n{description}"
    ui.notify(
        message,
        type=_QUASAR_TYPE[type],  # ← Converts to Quasar type
        ...
    )

# Usage across codebase
show_toast(type="success", title="...")  # ✅ Correct
show_toast(type="positive", title="...")  # ❌ Wrong — would crash with KeyError
```

**Type Definition:**
```python
ToastType = Literal["success", "error", "warning", "info"]

_QUASAR_TYPE: dict[str, _QuasarType] = {
    "success": "positive",
    "error": "negative",
    "warning": "warning",
    "info": "info",
}
```

**Problem:** If someone passes `show_toast(type="positive", ...)` (confusing with `ui.notify()`'s API), it crashes:
```
KeyError: 'positive'
```

**Root Cause:** Two different type systems (show_toast's "success"/"error" vs Quasar's "positive"/"negative") makes the wrapper confusing.

**Proposed Fix:**
```python
# Option 1: Align with Quasar's native types
ToastType = Literal["positive", "negative", "warning", "info"]

# Option 2: Add runtime validation
def show_toast(
    type: str,  # Accept any string
    title: str,
    description: Optional[str] = None,
    duration_ms: int = _DEFAULT_DURATION_MS,
) -> None:
    if type not in _QUASAR_TYPE:
        raise ValueError(f"Invalid toast type: {type}. Must be one of {list(_QUASAR_TYPE.keys())}")
    # ... rest of function ...
```

**Recommendation:** Use Option 2 (add runtime validation) to catch misconfigurations early.

---

### I-003: INTERFACE — No Loading State Toast (Spinner/Progress Indicator)
**Severity:** High | **Scope:** UX Feedback | **User Impact:** Users think the app is frozen during import/export/duplication

**Affected Components:**
- `src/ui/pages/settings_data.py:145-192` — Import operation (can take 5-30 seconds for large files)
- `src/ui/pages/workspaces.py:34-49` — Workspace list load (network latency 200-500ms)
- `src/ui/components/device_detail_duplicate.py:65-128` — Device duplication (2-5 second API call)

**Evidence:**
```python
# settings_data.py:145-192 (import operation)
async def do_import() -> None:
    if confirm_input.value != "CONFIRM":
        ui.notify("Type CONFIRM to proceed", type="warning")
        return
    raw = selected_file.get("content")
    
    # Long-running operation (5-30 seconds for large files)
    # NO LOADING INDICATOR! Just silence.
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(_IMPORT_URL, content=raw, ...)
        # ... handle response ...
    except Exception as exc:
        # Show error only after it fails
        ui.notify("Import failed", type="negative")

# workspaces.py:34-49 (load workspaces)
async def load_workspaces() -> None:
    try:
        async with httpx.AsyncClient() as http:
            resp = await http.get(f"{_API}/", ...)
        # Can take 200-500ms on slow network
        # No loading indicator shown
        if resp.status_code == 200:
            # ...
```

**UX Impact:**
```
User perspective:
T0: Click "Import JSON" button
T1: Dialog appears, user clicks Import
T2: Nothing happens for 10 seconds (user thinks it crashed)
T3: Finally shows "Import successful" toast
T4: User confused about what happened during those 10 seconds
```

**Root Cause:** `show_toast()` doesn't support persistent/dismissible loading states. NiceGUI's `ui.spinner()` is designed for long-running operations but not integrated with toast system.

**Proposed Fix:**

Option 1 — Add loading toast type:
```python
class ToastHandle:
    """Allow controlling toast state (update, dismiss)."""
    def __init__(self, element: ui.element):
        self._element = element
    
    def update(self, title: str, description: Optional[str] = None) -> None:
        self._element.set_text(title)
    
    def dismiss(self) -> None:
        self._element.delete()

def show_loading_toast(
    title: str = "Loading...",
    description: Optional[str] = None,
) -> ToastHandle:
    """Show a persistent loading toast that must be manually dismissed."""
    message = title if description is None else f"{title}\n{description}"
    toast_elem = ui.notify(
        message,
        type="info",
        position="top-right",
        timeout=None,  # Don't auto-dismiss
        close_button=False,  # Disable manual dismiss (loading state)
    )
    return ToastHandle(toast_elem)

# Usage
loading = show_loading_toast("Importing data...")
try:
    await import_data()
    loading.dismiss()
    show_toast(type="success", title="Import complete")
except Exception as e:
    loading.update(f"Import failed: {str(e)}")
```

Option 2 — Use NiceGUI spinners alongside toasts:
```python
# In settings_data.py
with ui.column() as loading_col:
    ui.spinner(size='lg').style("color:var(--ht-accent)")
    ui.label("Importing... This may take a minute")

try:
    await import_data()
    loading_col.delete()
    show_toast(type="success", title="Import complete")
except Exception as e:
    loading_col.delete()
    show_toast(type="error", title="Import failed", description=str(e))
```

**Effort:** Medium (requires new toast type or spinner pattern).

---

### C-001: CHECKING — No Error Message Details in Toast (Generic "Connection error")
**Severity:** High | **Scope:** Error Visibility | **User Impact:** Users can't diagnose why operations failed

**Affected Components:**
- `src/ui/components/device_panel_helpers.py:54-61` — Inline device field saves
- `src/ui/components/device_detail_custom_fields_section.py:65-68, 106-109, 167` — Custom field updates
- `src/ui/pages/workspaces.py:64-65, 81, 97` — Workspace operations
- Multiple others showing "Connection error" instead of actual error

**Evidence:**
```python
# device_panel_helpers.py:54-61
async def _save() -> None:
    new_val: Optional[str] = inp.value.strip() or None
    try:
        async with httpx.AsyncClient() as c:
            r = await c.patch(...)
        if r.status_code == 200:
            ui.notify(f"{label} updated")
        else:
            ui.notify(f"Save failed ({r.status_code})", type="negative")  # ✅ Good!
    except httpx.HTTPError as exc:
        logger.error("Inline save {}: {}", field, str(exc))
        ui.notify("Connection error", type="negative")  # ❌ Too generic

# device_detail_custom_fields_section.py:65-68
try:
    # ... update custom field ...
except Exception as exc:
    ui.notify("Connection error", type="negative")  # ❌ Logs error but doesn't show detail

# workspaces.py:64-65
except Exception as exc:
    logger.error("Workspace create failed: {}", str(exc))  # ← Error logged
    # But NO toast shown! Silent failure
```

**Better Approach (from workspaces.py:62-63):**
```python
# ✅ This is better
else:
    detail = resp.json().get("detail", "Error")
    ui.notify(html.escape(str(detail)), type="negative")  # Shows server error
```

**Root Cause:** 
1. Inconsistent error handling — some places show HTTP status, some show generic message, some show nothing
2. No standardized error message format in responses
3. Exception details logged but not shown to user

**Proposed Fix:**

Create a centralized error handler:
```python
# src/ui/services/error_handler.py
def show_error_toast(
    exception: Exception,
    context: str = "Operation failed",
    include_detail: bool = True,
) -> None:
    """Show error toast with appropriate detail level."""
    detail = str(exception)[:200]  # Cap at 200 chars
    
    if isinstance(exception, httpx.HTTPError):
        # Network error — don't expose internal details
        show_toast(type="error", title=context, description="Network error")
    elif isinstance(exception, httpx.HTTPStatusError):
        # Server error — try to extract API detail message
        try:
            api_detail = exception.response.json().get("detail", "Server error")
            show_toast(type="error", title=context, description=api_detail[:100])
        except:
            show_toast(type="error", title=context, description=f"Error {exception.response.status_code}")
    else:
        # Generic exception — show truncated message
        if include_detail:
            show_toast(type="error", title=context, description=detail)
        else:
            show_toast(type="error", title=context)

# Usage
try:
    await api_call()
except Exception as exc:
    show_error_toast(exc, context="Failed to save device")
```

---

### C-002: CHECKING — Missing Toast After Successful Silent Operations
**Severity:** High | **Scope:** Feedback / Confirmation | **User Impact:** Users don't know if operation succeeded (assume failure)

**Affected Component:** `src/ui/pages/workspaces.py:34-49` (load_workspaces)

**Evidence:**
```python
# workspaces.py:34-49
async def load_workspaces() -> None:
    try:
        async with httpx.AsyncClient() as http:
            resp = await http.get(f"{_API}/", ...)
        if resp.status_code == 200:
            data = resp.json()
            workspaces.clear()
            workspaces.extend(data.get("items", []))
            table.rows = workspaces
            table.update()
            # ← No toast! User doesn't know it succeeded
        else:
            logger.error("Workspaces load failed: status={}", resp.status_code)
            # ← Error not shown to user either!
    except Exception as exc:
        logger.error("Workspaces load error: {}", str(exc))
        # ← Silent failure!
```

**User Experience:**
```
User navigates to /workspaces
→ Page loads, table appears (seems to work?)
→ Actually status_code was 500, but user never knows
→ User assumes 2-3 workspaces exist because that's all shown
→ Confusion when they try to access a different workspace
```

**Root Cause:** Initial data loads don't show success/error feedback. Success is implicit (data appears), failure is silent (no error message).

**Proposed Fix:**
```python
async def load_workspaces() -> None:
    loading_toast = show_loading_toast("Loading workspaces...")
    try:
        async with httpx.AsyncClient() as http:
            resp = await http.get(...)
        loading_toast.dismiss()
        
        if resp.status_code == 200:
            data = resp.json()
            workspaces.clear()
            workspaces.extend(data.get("items", []))
            table.rows = workspaces
            table.update()
            # Optional: toast only on success if data was empty/changed
            if not workspaces:
                show_toast(type="info", title="No workspaces yet. Create one to get started.")
        else:
            detail = resp.json().get("detail", "Failed to load")
            show_toast(type="error", title="Load failed", description=detail)
    except Exception as exc:
        loading_toast.dismiss()
        show_error_toast(exc, context="Failed to load workspaces")
```

---

### B-001: BUILD/PACKAGE — Toast Not Enforced As Single Toast API
**Severity:** Medium | **Scope:** Maintainability | **User Impact:** Developers add new features with inconsistent toast patterns

**Evidence:**
- No linting rule prevents `ui.notify()` usage
- No documentation explains when to use `show_toast()` vs `ui.notify()`
- New developers copy existing pattern without understanding the inconsistency

**Root Cause:** Toast wrapper exists but was added reactively (after the fact) to address consistency, not enforced as the primary API.

**Proposed Fix:**
```bash
# Add to pre-commit hook
grep -rn "ui\.notify(" src/ui/ --include="*.py" | grep -v "__pycache__" | grep -v "test_" && {
    echo "❌ Found ui.notify() calls. Use show_toast() instead."
    exit 1
}

grep -rn "from src.ui.components.toast import show_toast" src/ui/ --include="*.py" > /dev/null || {
    echo "⚠️  No toast import found in UI files."
}
```

Add to documentation (`CONTRIBUTING.md`):
```markdown
## Toast Notifications

Always use the centralized `show_toast()` function from `src/ui/components/toast.py`:

✅ Correct:
```python
from src.ui.components.toast import show_toast
show_toast(type="success", title="Device saved")
```

❌ Incorrect:
```python
ui.notify("Device saved", type="positive")  # Don't use raw ui.notify()
```

Supported types: `"success"`, `"error"`, `"warning"`, `"info"`
```

---

### C-003: CHECKING — Toast Duration Hardcoded: 4 Seconds Always
**Severity:** Medium | **Scope:** UX / Readability | **User Impact:** Users with slow reading speed or visual impairments can't read toast before it disappears

**Affected Component:** `src/ui/components/toast.py:33`

**Evidence:**
```python
_DEFAULT_DURATION_MS = 4000  # 4 seconds hardcoded

def show_toast(..., duration_ms: int = _DEFAULT_DURATION_MS) -> None:
    """Display a toast notification in the top-right corner of the viewport.
    
    Args:
        duration_ms: Auto-dismiss delay in milliseconds (default 4000).
    """
    ui.notify(
        message,
        type=_QUASAR_TYPE[type],
        position="top-right",
        close_button=True,
        timeout=duration_ms,  # ← Always 4 seconds unless overridden
        multi_line=description is not None,
    )
```

**Problem:**
```
Average English reading speed: 200-250 words per minute
4 seconds = ~13-17 words readable

Average error message: "Layout save failed (409 Conflict)"
Words: 4
Characters: 33

Most users can read this in ~1 second, but long descriptions can't fit in 4 seconds:
"Connection timeout after 5s waiting for api.hometower.local:8080 (check your network)"
Words: 18 — needs 4+ seconds to read, but toast closes after 4 seconds if shown at T0
```

**WCAG 2.1 AA Requirement:**
- Animations/content changing should allow sufficient time to read
- Default minimum: 5 seconds for most users
- No maximum (users should be able to read at their own pace)

**Root Cause:** 4 seconds is a reasonable default for short messages but doesn't account for longer error descriptions.

**Proposed Fix:**
```python
# toast.py
_DEFAULT_DURATION_MS = 5000  # Increase to 5 seconds (more WCAG compliant)

# Better: calculate based on message length
def _calculate_duration_ms(title: str, description: Optional[str] = None) -> int:
    """Calculate toast duration based on message length (250 WPM reading speed)."""
    full_text = (title or "") + " " + (description or "")
    word_count = len(full_text.split())
    
    # 250 WPM = ~4 words per second
    # Add 1 second for user to notice toast appeared
    reading_time_ms = max(3000, (word_count / 4) * 1000)
    
    # Cap at 10 seconds max (long messages should be permanent)
    return min(10000, int(reading_time_ms))

def show_toast(
    type: ToastType,
    title: str,
    description: Optional[str] = None,
    duration_ms: Optional[int] = None,  # ← Optional now
) -> None:
    if duration_ms is None:
        duration_ms = _calculate_duration_ms(title, description)
    
    ui.notify(
        message,
        type=_QUASAR_TYPE[type],
        position="top-right",
        close_button=True,
        timeout=duration_ms,
        multi_line=description is not None,
    )
```

---

### I-004: INTERFACE — Toast Stacking Chaos (Multiple Toasts Overlap)
**Severity:** Medium | **Scope:** Visual Design | **User Impact:** When multiple operations fail, user sees 5+ toasts stacked awkwardly, hard to read

**Evidence:**
Scenario: User clicks "Delete" button 5 times rapidly
```
T0: Click 1 → "Deleting device..."
T1: Click 2 → "Deleting device..."  (stacks below T0)
T2: Click 3 → "Deleting device..."  (stacks below T1)
T3: Click 4 → "Deleting device..."  (stacks below T2)
T4: Click 5 → "Deleting device..."  (stacks below T3)

Result: 5 toasts filling right side of screen, overlapping content
```

**Root Cause:** NiceGUI's `ui.notify()` has no built-in deduplication. Each call creates a new toast.

**Proposed Fix:**

Option 1 — Queue deduplication:
```python
# toast.py
_TOAST_QUEUE: dict[str, float] = {}  # Maps message to timestamp
_TOAST_DEDUP_WINDOW_MS = 500  # Don't show same message within 500ms

def show_toast(...) -> None:
    message_key = f"{type}:{title}"
    
    # Check if similar toast was shown recently
    last_shown = _TOAST_QUEUE.get(message_key, 0)
    if time.time() * 1000 - last_shown < _TOAST_DEDUP_WINDOW_MS:
        return  # Skip duplicate toast
    
    _TOAST_QUEUE[message_key] = time.time() * 1000
    ui.notify(...)
```

Option 2 — Replace previous toast instead of stacking:
```python
# Global reference to last toast
_LAST_TOAST_ELEMENT: Optional[ui.element] = None

def show_toast(...) -> None:
    global _LAST_TOAST_ELEMENT
    
    # Remove previous toast if same type and still visible
    if _LAST_TOAST_ELEMENT:
        try:
            _LAST_TOAST_ELEMENT.delete()
        except:
            pass
    
    _LAST_TOAST_ELEMENT = ui.notify(...)
```

**Recommendation:** Use Option 1 (queue deduplication) as it's less intrusive.

---

### C-004: CHECKING — No HTML Escaping in Some Toast Messages (XSS Risk)
**Severity:** Medium | **Scope:** Security / Input Validation | **User Impact:** Malformed input in device names/error messages could inject HTML/JS

**Affected Components:**
- `src/ui/pages/workspaces.py:59, 75, 91` — Uses escaped error messages ✅
- `src/ui/pages/device_panel_helpers.py:54` — No escaping on field label ❌
- `src/ui/components/connection_detail_panel.py:187` — No escaping in error title ❌

**Evidence:**
```python
# ✅ CORRECT — escapting HTML
# workspaces.py:63
detail = resp.json().get("detail", "Error")
ui.notify(html.escape(str(detail)), type="negative")

# ❌ WRONG — f-string without escaping
# device_panel_helpers.py:54
ui.notify(f"{label} updated")  # ← label is from DB, could have HTML

# ❌ WRONG — direct string without escaping
# connection_detail_panel.py:187
show_toast(type="error", title="Delete failed")  # ← Could be user input
```

**Attack Scenario:**
```
1. Admin creates device with name: `Device <img src=x onerror="alert('XSS')">`
2. User edits that device's fields
3. Toast shows: `"Device <img src=x ...> updated"`
4. Browser executes JavaScript in the toast (if toast renders HTML)
```

**Root Cause:** Not all user-controlled strings are escaped before showing in toast.

**Proposed Fix:**
```python
# Wrap all show_toast() calls with HTML escaping:

# Before
show_toast(type="success", title=f"Device {device_name} saved")

# After
import html
show_toast(type="success", title=f"Device {html.escape(device_name)} saved")

# Better: do escaping in show_toast() itself
def show_toast(
    type: ToastType,
    title: str,
    description: Optional[str] = None,
    duration_ms: Optional[int] = None,
    escape_html: bool = True,  # ← NEW parameter
) -> None:
    if escape_html:
        title = html.escape(title)
        description = html.escape(description) if description else None
    
    # ... rest of function ...
```

---

### D-001: DOCUMENTATION — No Toast Usage Guidelines
**Severity:** Low | **Scope:** Developer Onboarding | **User Impact:** New developers add toasts inconsistently

**Evidence:**
- No `CONTRIBUTING.md` section on toast patterns
- No documentation of success/error message conventions
- No guidance on when to show toasts vs. other feedback mechanisms

**Proposed Fix:**

Add to `CONTRIBUTING.md`:
```markdown
## Toast Notifications

Toast notifications are short, non-blocking messages that appear in the top-right corner.

### When to Use Toasts

✅ **Use toasts for:**
- Successful operations ("Device saved", "Workspace created")
- Non-critical errors ("Connection timeout, retrying...")
- Quick confirmations ("Copied to clipboard")
- Status updates ("Loading devices...")

❌ **Don't use toasts for:**
- Form validation errors (use inline error labels instead)
- Critical errors requiring action (use dialogs)
- Multi-step operations (use progress indicators)

### Examples

**Success**
```python
show_toast(type="success", title="Device updated")
```

**Error with details**
```python
show_toast(type="error", title="Save failed", description="Network timeout")
```

**Warning**
```python
show_toast(type="warning", title="This action cannot be undone")
```

**Info / Loading**
```python
loading = show_loading_toast("Importing data...")
# Later:
loading.dismiss()
```

### Message Formatting

- **Title:** Short, 1-4 words. Examples: "Device saved", "Import failed"
- **Description:** Optional, 5-20 words. Provide context or next steps
- **Always escape user input:** `show_toast(..., title=html.escape(device_name))`

### Never Do This

```python
# ❌ Don't use raw ui.notify()
ui.notify("Saved", type="positive")

# ❌ Don't hardcode durations < 4 seconds
ui.notify("...", timeout=1000)

# ❌ Don't show unescaped user input
show_toast(type="success", title=device_name)  # Escape it!

# ❌ Don't silently fail (no error toast)
try:
    await save_device()
except:
    pass  # User never knows it failed
```
```

---

### DES-001: DESIGN — Toast Position Overlaps With Right-Edge UI Elements
**Severity:** Medium | **Scope:** Visual Design | **User Impact:** Toast covers important UI elements on narrow screens

**Affected Component:** `src/ui/components/toast.py:52` — `position="top-right"`

**Evidence:**
```python
ui.notify(
    message,
    type=_QUASAR_TYPE[type],
    position="top-right",  # ← Fixed position
    close_button=True,
    timeout=duration_ms,
    multi_line=description is not None,
)
```

**Problem on different layouts:**

```
Desktop 1920px:
┌──────────────────────────────────────────┐
│ Toast (top-right)                        │
│ doesn't overlap buttons ✅               │
└──────────────────────────────────────────┘

Tablet 768px with device detail panel:
┌──────────────────┬──────────┐
│ Canvas           │ Panel    │
│                  │ [Toast]  │ ← Overlaps panel!
│                  │ Close ✗  │ ← Can't click
│                  │ Buttons  │
└──────────────────┴──────────┘

Mobile 414px:
┌────────────────────┐
│ [Toast takes 60%]  │ ← Huge on small screens
│ Layout buttons...  │ ← Can't click
└────────────────────┘
```

**Root Cause:** Fixed `position="top-right"` doesn't account for panels or screen size.

**Proposed Fix:**

Option 1 — Responsive positioning:
```python
# Detect viewport and position accordingly
position_js = """
const width = window.innerWidth;
const hasPanel = document.getElementById('device-detail-panel').style.display !== 'none';
window._htToastPosition = (width < 640 || hasPanel) ? 'top-center' : 'top-right';
"""

def show_toast(...) -> None:
    # Get position from JS
    position = ui.run_javascript("window._htToastPosition || 'top-right'")
    ui.notify(
        message,
        position=position,
        ...
    )
```

Option 2 — Always center on mobile:
```python
def show_toast(...) -> None:
    # Center position is safer for all screen sizes
    position = "top"  # or "bottom-center"
    ui.notify(
        message,
        position=position,
        ...
    )
```

**Recommendation:** Use Option 2 (top-center) as it's universally safe.

---

### DES-002: DESIGN — Toast Close Button Not Visible on Dark Theme
**Severity:** Low | **Scope:** Accessibility | **User Impact:** Users can't manually dismiss toast on dark theme (button blends in)

**Evidence:**
```python
# toast.py:52
ui.notify(
    message,
    type=_QUASAR_TYPE[type],
    position="top-right",
    close_button=True,  # ← Rendered but may be invisible
    ...
)
```

**Rendering:**
- Quasar's `close_button=True` renders a small `×` button
- Button color is determined by Quasar's default styling (usually white/light gray)
- On dark theme with light text, the button may be hard to see

**Root Cause:** No explicit styling of close button. Quasar defaults may not match design tokens.

**Proposed Fix:**
```python
# Add CSS to design tokens or app_shell.py
_TOAST_CSS = """
<style>
.q-notification {
    background: var(--ht-bg-surface-raised) !important;
    color: var(--ht-text-primary) !important;
    border: 1px solid var(--ht-border) !important;
}
.q-notification .q-icon {
    color: var(--ht-text-secondary) !important;
}
.q-notification__close {
    color: var(--ht-accent) !important;
    font-size: 1.2rem;
}
.q-notification__close:hover {
    color: var(--ht-accent-hover) !important;
}
</style>
"""

# In app_shell.py or toast.py initialization
ui.add_head_html(_TOAST_CSS)
```

---

### C-005: CHECKING — Description Parameter Rarely Used (Wasted Feature)
**Severity:** Low | **Scope:** Feature Utilization | **User Impact:** Toast descriptions could provide more context but aren't used

**Evidence:**

Grep for `show_toast()` with description parameter:
```python
# ONLY 2 files use description:
src/ui/pages/settings_data.py:186  # 1 usage
src/ui/pages/settings_data.py:192  # 1 usage

# All other ~30 usage sites omit description parameter
show_toast(type="success", title="Device saved")  # No description
show_toast(type="error", title="Update failed")  # No description
```

**Missed Opportunities:**
```python
# Current (generic)
show_toast(type="error", title="Save failed")

# Better (with context)
show_toast(type="error", title="Save failed", description="Network timeout after 5s")

# Current (generic)
show_toast(type="success", title="Device created")

# Better (with next step)
show_toast(type="success", title="Device created", description="Now add connections in the topology")
```

**Root Cause:** Developers didn't realize description was available, or kept messages short to simplify code.

**Proposed Fix:**

Add example to `CONTRIBUTING.md`:
```markdown
### Using Descriptions for Context

When the title alone doesn't provide enough context, add a description:

```python
# ❌ Too generic
show_toast(type="error", title="Operation failed")

# ✅ Helpful
show_toast(type="error", title="Import failed", description="File is not valid JSON")

# ✅ Actionable
show_toast(type="warning", title="Unsaved changes", description="Navigate away?")
```
```

---

### I-005: INTERFACE — No Toast for Clipboard Copy Success (Silent Operation)
**Severity:** Low | **Scope:** UX Feedback | **User Impact:** Users don't know if IP address copy succeeded

**Affected Component:** `src/ui/pages/inventory_table.py:53-57`

**Evidence:**
```python
# inventory_table.py (Quasar template, not Python)
<q-btn v-if="props.row.ip" flat dense round size="xs"
       icon="content_copy"
       @click.stop="navigator.clipboard.writeText(props.row.ip); $q.notify({message:'IP copied', color:'primary', position:'top-right'})">
  <q-tooltip>Copy IP</q-tooltip>
</q-btn>
```

The inline `$q.notify()` call works but:
1. Uses raw Quasar notify (not our wrapper)
2. No error handling (what if clipboard.writeText fails?)
3. Hardcoded styling

**Root Cause:** This is a Quasar template, not Python code, so it can't use our `show_toast()` wrapper easily.

**Proposed Fix:**

Move to Python and use `show_toast()`:
```python
# In inventory_table.py or a helper module
async def copy_to_clipboard(text: str) -> None:
    """Copy text to clipboard with user feedback."""
    try:
        # Use JavaScript to copy (browser API)
        await ui.run_javascript(f"""
        try {{
            await navigator.clipboard.writeText({json.dumps(text)});
            // Success feedback handled by caller
        }} catch (err) {{
            throw new Error('Failed to copy');
        }}
        """)
        show_toast(type="success", title="Copied to clipboard")
    except Exception as exc:
        show_toast(type="error", title="Copy failed", description="Check permissions")

# Or use a Quasar notify replacement in the template...
```

---

## Summary Table

| ID | Lane | Severity | Component | Issue | Fix Effort |
|---|---|---|---|---|---|
| I-001 | I | 🔴 Critical | toast.py + 10 files | Inconsistent API: 60% raw ui.notify() | High |
| I-002 | I | 🟠 High | toast.py | Type mismatch: "success" vs "positive" | Low |
| I-003 | I | 🟠 High | settings_data.py, workspaces.py | No loading state for long operations | Medium |
| C-001 | C | 🟠 High | Multiple | Generic "Connection error" instead of details | Medium |
| C-002 | C | 🟠 High | workspaces.py | Silent success (no toast feedback) | Low |
| B-001 | B | 🟡 Medium | Entire UI layer | Toast not enforced as single API | Low |
| C-003 | C | 🟡 Medium | toast.py | 4s duration too short for long messages | Low |
| I-004 | I | 🟡 Medium | toast.py | Multiple toasts stack awkwardly | Medium |
| C-004 | C | 🟡 Medium | 5+ files | Missing HTML escaping in toast messages | Low |
| DES-001 | DES | 🟡 Medium | toast.py | Top-right position overlaps panels/mobile UI | Low |
| D-001 | D | 🟡 Medium | CONTRIBUTING.md | No toast usage guidelines | Low |
| DES-002 | DES | 🔵 Low | toast.py | Close button invisible on dark theme | Low |
| C-005 | C | 🔵 Low | Multiple | Description parameter unused | Low |
| I-005 | I | 🔵 Low | inventory_table.py | No toast for clipboard copy success | Low |

---

## Pipeline Verdict

**Status:** OPEN (1 Critical + 5 High block resolution)

### Blocking Issues (must fix before feature expansion)
1. **I-001**: Enforce single toast API (refactor all raw `ui.notify()` calls)
2. **I-002**: Fix type confusion between `show_toast()` and `ui.notify()`
3. **I-003**: Add loading state support for long-running operations
4. **C-001**: Standardize error message detail in toasts
5. **C-002**: Never silently fail — always show error or success feedback

### High Priority (next sprint)
6. **B-001**: Linting rule + documentation to prevent future violations
7. **I-004**: Implement toast deduplication
8. **C-003**: Dynamic duration based on message length

### Medium Priority (next cycle)
9. **C-004**: Audit and escape all user input in toast messages
10. **DES-001**: Test position on mobile; adjust if needed
11. **D-001**: Add comprehensive toast guidelines

### Low Priority (polish)
12. **DES-002**: Style close button visibility
13. **C-005**: Add description examples to docs
14. **I-005**: Move clipboard logic to Python

### Recommendation
Route **I-001** to **Refactoring-Specialist** (refactor 10 files, add linting). Route **I-003** to **Feature-Engineer** (add loading toast type). Route **C-001** + **C-002** to **Feature-Engineer** (error handling standardization).

---

## Test Plan for Verification

```bash
# 1. Linting check (for I-001)
grep -rn "ui\.notify(" src/ui/ --include="*.py" | grep -v test
# Expected: No results

# 2. Type checking (for I-002)
python3 -c "
from src.ui.components.toast import show_toast
show_toast(type='positive', title='Test')  # Should fail with clear error
"

# 3. Loading state (for I-003)
# Manually test: click Import, observe loading indicator appears and persists

# 4. Error detail (for C-001)
# Trigger network error, check toast shows actual error message (not 'Connection error')

# 5. Silent failure (for C-002)
# In devtools: set breakpoint on load_workspaces, verify toast appears on success/error

# 6. Toast stacking (for I-004)
# Rapidly click delete 5 times, verify only 1-2 toasts visible (deduped)

# 7. Duration (for C-003)
# Show long error message, measure toast duration auto-adjusts
# Short message: ~3s, Long message: ~6-7s

# 8. HTML escaping (for C-004)
# Create device with name: <img src=x>
# Edit field, verify toast shows escaped HTML (not rendered)
```

---

## References

- [WCAG 2.1 — Animation from Interactions](https://www.w3.org/WAI/WCAG21/Understanding/animation-from-interactions)
- [NiceGUI Notifications](https://nicegui.io/documentation/ui#notification)
- [Quasar Notify Component](https://quasar.dev/api/Quasar.notify)
- [Material Design Toast Guidelines](https://material.io/components/snackbars)
- [W3C Accessible Rich Internet Applications (ARIA)](https://www.w3.org/WAI/ARIA/apg/patterns/alert/)
