# Bug Report — E2E Deep Hunt (2026-04-13)

## QA Remediation Ledger

| Bug ID | Status | Root Cause (1 sentence) | Fix (lines) | Tests Added |
|---|---|---|---|---|
| BUG-001 | FIXED | `cy.autounselectify(true)` in view-mode init and `VIEW_MODE_JS` globally locks all nodes to `selectable: false`, causing `nodes().select()` and `nodes().unselect()` in Ctrl+A / Escape shortcut handlers to silently no-op. | 8 | 2 (unit test assertions updated) |
| TEST-BUG-001 | FIXED | `api()` helper in `test_deep_hunt.py` calls `json.loads(resp.read())` on 204 No Content responses; empty body raises `json.JSONDecodeError`. | 3 | — |
| TEST-BUG-003 | FIXED | `test_stories_e2e.py` edge query uses wrong Cytoscape field name `conn_type` instead of `connection_type`, causing all edge types to read as `'unknown'`. | 1 | — |
| CANVAS-NODES-LEFTOVER | ROUTED_ELSEWHERE | Two `draft-{UUID}` nodes left from prior test sessions persist in the autosaved Cytoscape layout with `selected: true` + `selectable: false` inconsistent state; canvas should flush orphaned draft nodes on load. | — | — |

**Pipeline Verdict: ALL_CLEAR** — 3 fixed, 1 routed elsewhere (CANVAS-NODES-LEFTOVER → Architect for data-consistency RFC).

---

## Discovery Method

Comprehensive Playwright E2E deep hunt: `tests/e2e/test_deep_hunt.py` (69 assertions, 16 test functions) running against a live Docker stack.

Also used: `tests/e2e/test_stories_e2e.py` baseline suite (34 tests).

---

## BUG-001 — Ctrl+A / Escape Canvas Shortcuts Broken

**Severity**: High (broken core canvas UX)

**Affected files**:
- `src/ui/components/canvas_js.py` (init)
- `src/ui/components/canvas_mode.py` (`VIEW_MODE_JS`)
- `src/ui/components/canvas_shortcuts.py` (unchanged after final fix)

### 5-Whys Root Cause

1. Ctrl+A fires; `window._cy.nodes().select()` selects 0 of 2 nodes → shortcut appears broken
2. `nodes().select()` is a no-op → because all nodes have `selectable: false`
3. Nodes have `selectable: false` → because `cy.autounselectify(true)` was called at canvas init and in `VIEW_MODE_JS`
4. `autounselectify(true)` was added to prevent selection halos in view mode (aesthetic intent)
5. **Root cause**: Cytoscape.js `autounselectify(true)` also prevents programmatic `select()` and `unselect()` — the side-effect was not anticipated. Per-element `selectify()` cannot override the global `autounselectify` flag in this Cytoscape.js version.

### Fix Applied

Removed `cy.autounselectify(true)` from `canvas_js.py` init and removed `autounselectify(true)` from `VIEW_MODE_JS`. In view mode, `autoungrabify(true)` and `boxSelectionEnabled(false)` still prevent drag-and-drop edits. Nodes remain interactively selectable in view mode (clicking shows selection halo), which is acceptable UX — the detail panel still opens via `tap` events and write operations are blocked by `HT_READONLY` checks.

Updated two unit tests that previously asserted `autounselectify(true)` was present:
- `tests/unit/test_canvas_js_view_mode.py::test_autounselectify_not_set_after_init`
- `tests/unit/test_canvas_mode.py::TestViewModeJs::test_view_mode_autounselectify_not_set`

### Regression Test

```
Playwright shortcut verification (manual):
  Ctrl+A: 2/2 selected — PASS
  Escape: 0 selected  — PASS
  Ctrl+A after Escape: 2/2 selected — PASS
  Escape after pre-select: 0 selected — PASS
```

Full unit/integration suite: **1222 passed, 4 pre-existing T-002 failures, 0 regressions**.

---

## TEST-BUG-001 — `api()` Helper Crashes on 204 No Content

**File**: `tests/e2e/test_deep_hunt.py`
**Trigger**: `DELETE /api/devices/{id}` returns 204 with empty body.

**Fix**:
```python
raw = resp.read()
return json.loads(raw) if raw else {"__status": resp.status}
```

---

## TEST-BUG-003 — Wrong Cytoscape Edge Field Name in E2E Test

**File**: `tests/e2e/test_stories_e2e.py` (line ~150)

**Old**: `e.data('conn_type') || e.data('type') || 'unknown'`
**Fix**: `e.data('connection_type') || e.data('type') || 'unknown'`

Canvas uses `connection_type` (set in `src/ui/services/topology_data.py`).

---

## CANVAS-NODES-LEFTOVER — Orphaned Draft Nodes in Autosave (Routed)

**Observation**: Two `draft-{UUID}` nodes from prior API test runs persist in the autosaved Cytoscape layout across browser sessions. One node is in inconsistent state (`selected: true`, `selectable: false`), likely because `autounselectify(true)` was called AFTER the node was selected by stencil-drop code.

**Impact**: Clutters the canvas for the default topology between test sessions. Also triggered the shortcut investigation that found BUG-001.

**Route**: Architect — should the autosave prune pure-draft nodes (never published to DB) from the saved layout JSON on page load? Or should stencil-drop ensure draft nodes respect `autounselectify` state at creation time?
