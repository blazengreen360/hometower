# Bug Report 12-04-26.3

**Date:** 12 April 2026
**Target:** Inventory page stress test (`/inventory`)
**Orchestrator:** QA-Fixer (Playwright MCP)
**Methodology:** High-frequency UI interaction stress + mobile viewport interaction probes

## Executive Summary

| Severity | Count |
|---|---|
| Critical | 0 |
| High | 2 |
| Medium | 0 |
| Low | 0 |
| **Total** | **2** |

**Pipeline Verdict:** OPEN — 2 findings open.

### Top Risks
1. **BUG-INV-001**: Inventory delete action does not trigger confirmation flow, effectively blocking deletion from the inventory table.
2. **BUG-INV-002**: Mobile drawer backdrop remains active and intercepts taps, blocking inventory actions and causing accidental route changes.

## Prioritized Findings

| ID | Sev | Title | File:Line | Routing |
|---|---|---|---|---|
| BUG-INV-001 | High | Delete button in inventory rows is non-functional | `src/ui/pages/inventory_table.py:75` | QA-Fixer |
| BUG-INV-002 | High | Mobile drawer backdrop blocks inventory interactions | `src/ui/components/sidebar.py:39` | UX-Designer + QA-Fixer |

---

## BUG-INV-001 — Delete button in inventory rows is non-functional (High)

- **Area:** Inventory table row actions
- **Trigger condition:** Click any row-level delete icon in `/inventory`

### Reproduction
1. Log in as admin user.
2. Open `/inventory`.
3. Click a row `delete` icon in Actions.
4. Wait 3-12 seconds.

### Expected
- Confirm dialog opens.
- Placement lookup request runs (`GET /api/devices/{id}/placements`).
- User can cancel or confirm deletion.

### Actual
- No confirm dialog appears.
- No placement lookup request is fired.
- No delete request is fired.

### Evidence
- Stress script result: `dialogVisible=false` after waiting 12s.
- Request listener result: `placementsRequests=0`, `deleteRequests=0` after click.

### Suspected Root Cause
The row action emits `delete-device` via `$parent.$emit(...)` from the table slot template. Under current Quasar/NiceGUI slot context this event path does not appear to reach the listener attached in `inventory_page`.

### Suggested Fix Direction
- Replace fragile parent emission with a reliable row action channel already known to work in NiceGUI table slots.
- Add a focused UI integration test for delete click -> placements API call -> dialog visible.

---

## BUG-INV-002 — Mobile drawer backdrop blocks inventory interactions (High)

- **Area:** App shell sidebar/drawer on mobile viewport
- **Trigger condition:** Open `/inventory` on narrow viewport (390x844)

### Reproduction
1. Set viewport to 390x844.
2. Log in.
3. Open `/inventory`.
4. Attempt to tap row actions (e.g., edit link) or interact with content.

### Expected
- Inventory content is tappable by default.
- Drawer backdrop is absent unless drawer is explicitly opened.

### Actual
- `.q-drawer__backdrop` is present and visible immediately.
- Backdrop intercepts pointer events; row action clicks time out.
- Taps can route unexpectedly to other pages while backdrop remains visible.

### Evidence
- Playwright click timeout indicates pointer interception by `.q-drawer__backdrop`.
- Probe snapshot: backdrop remains visible before and after backdrop click attempts.

### Suspected Root Cause
`ui.left_drawer(value=expanded)` initializes from persisted desktop preference without a mobile guard (`show-if-above`/conditional default closed), causing overlay mode to remain active on page load in mobile width.

### Suggested Fix Direction
- Force drawer closed by default on mobile breakpoints.
- Keep persisted expansion behavior only for desktop widths.
- Add mobile UI regression test asserting row action clickability on `/inventory`.

---

## Execution Notes
- Desktop stress (search/chip/sort/scroll spam) did not produce console errors.
- Failures above are reliably reproducible and user-visible.
