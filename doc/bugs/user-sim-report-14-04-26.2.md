# User Simulation Bug Report — 14 April 2026 (Run 2)

## Persona Summary
Marcus Chen, Intermediate Builder. Existing medium-size homelab inventory, performing routine admin operations across topology, inventory, settings, and data-management surfaces.

Simulation style: Real browser interaction via Chrome DevTools MCP against live app at http://localhost:8080 with authenticated Admin account.

## Session Scope
- Authentication and re-authentication flow
- Dashboard quick actions
- Topology controls and layout workflows
- Inventory search/filter and edit flows
- Settings: Users, Profile, Locations, Networks, Data
- IPAM page
- Workspaces page
- Map route

## Executive Summary
- Total issues: 7
- Critical: 0
- High: 4
- Medium: 3
- Low/UX: 0

Most affected areas: Settings forms, Data export flow, Topology layout rename flow.

## Issues (Prioritized)

### HIGH #1: Export JSON fails for authenticated Admin with generic alert
- Page: /settings/data
- Steps:
1. Log in as Admin.
2. Navigate to Settings -> Data.
3. Click Export JSON.
4. Observe browser alert: Export failed. Please check your session and try again.
- Expected: Successful JSON download for Admin (or actionable permission/session error details).
- Actual: Export fails despite valid authenticated admin session and provides generic, non-diagnostic alert.
- Impact: Core backup workflow is blocked.

### HIGH #2: Topology layout rename concatenates old and new names
- Page: /topology
- Steps:
1. Open Topology.
2. Enter Edit mode.
3. Click Rename layout.
4. Enter a new name like Lab-Primary-Topology-Name-With-Special_#01.
5. Click Rename.
- Expected: Saved layout name replaced with new name exactly.
- Actual: Value became My LayoutLab-Primary-Topology-Name-With-Special_#01 (old + new concatenated).
- Impact: Corrupt layout naming semantics; repeated renames can produce unreadable names.

### HIGH #3: /map route is exposed in nav but returns 404
- Page: /map
- Steps:
1. Navigate directly to /map.
2. Observe 404 page.
- Expected: Working map view or hidden feature gate.
- Actual: Route exists in navigation context but returns 404 Not Found.
- Impact: Broken major feature entry point and misleading navigation affordance.

### HIGH #4: Workspaces Last Modified column is raw ISO instead of human-readable
- Page: /workspaces
- Steps:
1. Navigate to /workspaces.
2. Observe Last Modified column values.
- Expected: Human-readable formatted timestamps consistent with HT-054 behavior.
- Actual: Raw ISO strings shown (for example 2026-04-12T23:11:18.073315Z).
- Impact: Readability regression and inconsistent table UX.

### MEDIUM #5: Create User dialog renders raw escaped backend validation payload
- Page: /settings/users
- Steps:
1. Click + Add User.
2. Leave username/email blank.
3. Enter password only.
4. Click Save.
- Expected: Clean inline validation copy per field.
- Actual: UI displays escaped backend payload list (JSON-like error dump) directly.
- Impact: Poor UX and information leakage of backend validation shape.

### MEDIUM #6: Add Location dialog renders raw escaped backend validation payload
- Page: /settings/locations
- Steps:
1. Click + Add Location.
2. Leave name blank.
3. Click Save.
- Expected: Friendly inline error (for example Name is required).
- Actual: Escaped backend validation list rendered directly.
- Impact: Same validation-surface quality and leakage issue as Users modal.

### MEDIUM #7: Profile password update has no visible validation feedback on invalid submission
- Page: /settings/profile
- Steps:
1. Enter current password value.
2. Enter too-short new password (abc) and matching confirm.
3. Click Update Password.
- Expected: Immediate visible validation message explaining constraints.
- Actual: No visible inline feedback in the form after submit.
- Impact: User uncertainty and repeated retries.

## Action Log
| Chapter | Route | Key interactions | Result |
|---|---|---|---|
| 1 | /login -> / | Login, dashboard load | Pass |
| 2 | /topology | Zoom in/out/fit/help, Edit mode toggle, Save layout, Rename layout | Rename defect found |
| 3 | /inventory | Search/filter, clear filters, open row edit, invalid save attempt, back navigation | Core flows accessible |
| 4 | /settings/users | Open create modal, required validation paths | Raw validation payload defect |
| 5 | /settings/profile | Password update invalid-path submission | Missing visible feedback |
| 6 | /settings/locations | Open create modal, empty-name validation | Raw validation payload defect |
| 7 | /settings/networks | Open create modal, empty-name validation | Friendly validation present |
| 8 | /settings/data | Export JSON action as Admin | Export failure defect |
| 9 | /ipam | Read-only panel load | Pass (no data state) |
| 10 | /workspaces | Table and action controls | Timestamp format defect |
| 11 | /map | Direct navigation | 404 defect |

## Coverage
| Page | Visited | Buttons/components exercised |
|---|---|---|
| /login | Yes | Email, Password, Log In |
| / | Yes | Add Device, View Inventory |
| /topology | Yes | Edit/Stop Editing, Save Layout, Rename Layout, Zoom In, Zoom Out, Fit to Screen, Help |
| /inventory | Yes | Search, type chips, orphan filter, clear filters, row edit link, row topology link, row delete affordance visibility |
| /inventory/edit/{id} | Yes | Back to Inventory, Open in Topology, Save Changes, Cancel |
| /settings/users | Yes | Add User, role selector, active checkbox, Save, Cancel |
| /settings/profile | Yes | Current/New/Confirm fields, Update Password |
| /settings/locations | Yes | Add Location modal fields, Save, Cancel |
| /settings/networks | Yes | Add Network modal fields, Save, Cancel |
| /settings/data | Yes | Export JSON, import card visibility |
| /ipam | Yes | Search, read-only cards |
| /workspaces | Yes | New Workspace button visibility, row links/actions visibility |
| /map | Yes | Direct route navigation |

## Notes
- This run exercised real browser controls and route transitions with authenticated state.
- Several issues are likely regressions from previously delivered UX-hardening stories (validation messaging and timestamp formatting).
