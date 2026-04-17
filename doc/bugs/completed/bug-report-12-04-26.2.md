# Bug Report 12-04-26.2

## Executive Summary
| Severity | Count |
|---|---|
| Critical | 3 |
| High | 7 |
| Medium | 7 |
| Low | 3 |
| **Total** | **20** |

Pipeline Verdict: OPEN — 20 findings open.

### Top 3 risks
1. **BUG-TOPO-001 — Autosave race causing lost/overwritten diagram state (Critical)**
2. **BUG-TOPO-004 — Draft publish ID-replacement rollback edge-case leaves orphaned edges (Critical)**
3. **BUG-TOPO-007 — Container unconvert deletes children without safe transactional confirmation (Critical)**

## Prioritized Findings
| ID | Sev | Score | Title | File:Line | Routing |
|---|---|---|---|---|---|
| BUG-TOPO-001 | Critical | 23 | Autosave race causing lost/overwritten diagram state | src/ui/components/canvas_js_utils.py#L1 | DevOps-Engineer / QA-Fixer |
| BUG-TOPO-002 | High | 20 | beforeunload uses _htFlushAutosave synchronously but uses fetch keepalive incorrectly | src/ui/components/canvas_js_utils.py#L1 | QA-Fixer |
| BUG-TOPO-003 | High | 20 | _htAutosaveTimer global races (multiple timers) lead to missed saves | src/ui/components/* | QA-Fixer |
| BUG-TOPO-004 | Critical | 24 | Publish ID-replacement rollback can leave duplicate/orphan edges | src/ui/components/canvas_draft_publish.py#L1 | QA-Fixer |
| BUG-TOPO-005 | High | 19 | _htPublishDraft promotes connections only after re-adding node — race with concurrent promotes | src/ui/components/canvas_draft_publish.py#L1 | QA-Fixer |
| BUG-TOPO-006 | High | 18 | Drag-reparent PATCH uses GET then PATCH without version retry — TOCTOU | src/ui/components/canvas_container_events.py#L1 | Architect -> Feature-Engineer |
| BUG-TOPO-007 | Critical | 22 | Unconvert container removes descendants/edges in DOM without server-side coordination | src/ui/components/canvas_container_events.py#L1 | Architect -> Feature-Engineer |
| BUG-TOPO-008 | Medium | 14 | _htEscapeHtml used inconsistently; some server data already escaped (double-escape) | src/ui/services/topology_data.py#L1 | QA-Fixer |
| BUG-TOPO-009 | Medium | 13 | Context menu "nearest node" heuristic uses distance threshold in pixels which is brittle on zoom/pan | src/ui/components/canvas_js.py#L1 | UX / QA-Fixer |
| BUG-TOPO-010 | Medium | 12 | _htEventsWired gating may still double-bind if edit toggle raced across pages | src/ui/pages/topology.py#L1 | QA-Fixer |
| BUG-TOPO-011 | High | 18 | Draft publish when API down: draft node keeps draft-error class but rollback logic may not restore edges properly | src/ui/components/canvas_draft_publish.py#L1 | QA-Fixer |
| BUG-TOPO-012 | Medium | 11 | _htDraftCount / badge can go negative or stale when nodes removed programmatically without badge refresh | src/ui/components/canvas_draft.py#L1 | QA-Fixer |
| BUG-TOPO-013 | Low | 8 | Ctrl+A / keyboard shortcuts don't guard activeElement leading to unintended actions when typing | src/ui/components/canvas_shortcuts.py#L1 | QA-Fixer |
| BUG-TOPO-014 | High | 17 | Edge delete (cxttap) uses raw_label from data and may show unescaped text in confirm dialogs | src/ui/components/canvas_js_helpers.py#L1 | QA-Fixer |
| BUG-TOPO-015 | Medium | 12 | applyLayoutPositions silently ignores nodes not present (deleted devices) but does not surface warnings | src/ui/components/canvas_js_utils.py#L1 | QA-Fixer |
| BUG-TOPO-016 | Low | 7 | Native contextmenu nearest-node selection stores window._htLastCtxX/Y globally (privacy leak) | src/ui/components/canvas_js.py#L1 | Low / Privacy Review |
| BUG-TOPO-017 | Low | 6 | Draft form popover may render off-screen near viewport edges (clipping) | src/ui/components/canvas_draft_form.py#L1 | UX |
| BUG-TOPO-018 | Medium | 13 | _createAssociation allows creating draft-edge between a draft and published device but _htPromoteConnections ignores edges still marked draft_edge after publish | src/ui/components/canvas_js_helpers.py#L1 | QA-Fixer |
| BUG-TOPO-019 | High | 19 | Edit toggle deadlocks behind draft-confirmation backdrop under rapid toggling | src/ui/components/topology_edit_toggle.py#L42 | QA-Fixer |
| BUG-TOPO-020 | Medium | 12 | Draft-node tooltip probes invalid `/api/devices/draft-*` IDs, causing persistent 422 error spam | src/ui/components/canvas_tooltip.py#L19 | QA-Fixer |

## Details

### BUG-TOPO-001 — Autosave race causing lost/overwritten diagram state (Critical)
- **File:** src/ui/components/canvas_js_utils.py
- **Trigger:** Rapid drag/multiple UI actions schedule debounced autosaves while manual save or another autosave is in-flight; server-side `version` based update may cause last-writer-wins or rejected PATCH.
- **Root Cause / Failure Mode:** Autosave uses single global timer `window._htAutosaveTimer` and `_htFlushAutosave()` issues a PATCH with current `window._htDiagramVersion`. Multiple flushes can run concurrently if code paths clear/set timer incorrectly; there is no concurrency control, no optimistic retry on 409, and `keepalive` is used but may not complete for large payloads. The client updates `_htDiagramVersion` only on success; failed saves are silent (no rollback or user-visible error).
- **Reproduction steps:**
  1. Open topology in edit mode with an active layout.
  2. Rapidly drag several nodes (firing many `dragfree` events) while simultaneously clicking Save Layout.
  3. Observe in network tab multiple PATCH calls with the same `version` or near-simultaneous requests; later save may silently fail to persist some positions.
- **Expected:** Version conflicts either retried or surfaced to user; last-change wins only with clear user feedback and server returns new version atomically.
- **Actual:** Some moves are lost or overwritten; no user-visible error when PATCH fails due to version mismatch.
- **Suggested fix:** Serialize autosave requests: mark `_htAutosaveInFlight` and queue a single pending flush that retries on 409 with an exponential backoff and refetch of latest diagram version. On conflict, surface a non-modal warning explaining concurrent edits. Consider using ETag/If-Match semantics.

---

### BUG-TOPO-002 — beforeunload uses _htFlushAutosave synchronously but uses fetch keepalive incorrectly (High)
- **File:** src/ui/components/canvas_js_utils.py
- **Root cause:** `beforeunload` handler calls `_htFlushAutosave()` which uses `fetch(..., keepalive: true)` but the function is async and there's no guarantee the PATCH completes before unload; browsers limit keepalive size and may drop large JSON.
- **Reproduction:** Create large diagram (many nodes/edges), trigger window close/unload while edits pending, and check server: PATCH may not complete.
- **Expected:** Critical edits are preserved; or user prompted to wait if save is pending.
- **Suggested fix:** On beforeunload, if there is pending save and payload is large, block unload with confirm (navigator.sendBeacon could be used for small payloads, or disable large autosaves on unload and show prompt). Also measure payload size and avoid keepalive for >64KB.

---

### BUG-TOPO-003 — _htAutosaveTimer global races (High)
- **Files:** src/ui/components/canvas_js.py, canvas_container_events.py, canvas_draft_events.py, device_detail_draft.py
- **Root cause:** Multiple code paths clear/set `window._htAutosaveTimer` independently; complex flows (convert/unconvert/collapse/move/publish) repeatedly clear and set timers without a single debounce helper leading to lost resets or runaway timers.
- **Reproduction:** Trigger container collapse then immediate drag/position change and then unconvert; timers may be set multiple times and flush order becomes nondeterministic.
- **Suggested fix:** Centralize autosave scheduling into a helper `scheduleAutosave()` that replaces the timer safely (returns cancel handle) and guards against multiple callers.

---

### BUG-TOPO-004 — Publish ID-replacement rollback can leave duplicate/orphan edges (Critical)
- **File:** src/ui/components/canvas_draft_publish.py
- **Root cause:** Publish flow removes draft node and then re-adds node with server id; if verification fails (`cy.getElementById(newId).length !== 1`) code re-adds draft node and then re-adds connected edges from captured `connectedEdges`. However if any of the `connectedEdges` referenced published nodes whose IDs collide with existing edges, or if some edges were already promoted concurrently, the re-add path may create duplicate edges or leave orphan edges because it blindly re-adds previous edge `data` without checking for existing elements or maintaining edge IDs.
- **Reproduction:** Publish a draft connected to published device while concurrently another tab publishes the other draft / promotes the same connection; or simulate server error after node removal but before add; observe duplicate edges or missing/incorrect edges.
- **Expected:** Rollback should restore exact prior state deterministically and avoid duplicate edges; edge IDs should be kept stable or deduplicated.
- **Suggested fix:** When rolling back, instead of unconditionally re-adding edges, check for existing element IDs before `cy.add`. Use stable temporary edge ids and map them back. Also perform a two-phase publish: create server node first (POST), create server connections, then remove local draft and add server node/edges — or wrap operations in server transaction where possible.

---

### BUG-TOPO-005 — _htPublishDraft promotes connections only after re-adding node — race with concurrent promotes (High)
- **File:** src/ui/components/canvas_draft_publish.py
- **Root cause:** `_htPromoteConnections` iterates `node.connectedEdges()` after the newly-added node exists; but it checks `if (window._htIsDraft(src) || window._htIsDraft(tgt)) return;` which will skip promotion if other connected draft(s) exist. If other publishes occur concurrently, some promotes may be missed or create duplicate server connections.
- **Repro:** Publish draft A (connected to published B) and concurrently publish draft C which also connects to B; promotions interleave and result in missing connections or duplicates.
- **Fix:** Promote connections server-side as part of publish endpoint or use a deterministic promotion queue with server-acknowledged mapping. Ensure idempotent connection creation (upsert) on server.

---

### BUG-TOPO-006 — Drag-reparent PATCH uses GET then PATCH without version retry — TOCTOU (High)
- **File:** src/ui/components/canvas_container_events.py
- **Root cause:** On `dragfree`, client does GET `/api/devices/{id}` to read `version` then PATCH with that version. If the device was updated between GET and PATCH, server will likely return 409 or reject; client code does not handle 409, retries, or surface a conflict to user.
- **Repro:** Open same device in two tabs; in tab A edit device to increment version; in tab B drag device into container -> PATCH will fail silently resulting in inconsistent UI vs server.
- **Suggested fix:** Handle 409 responses: fetch latest version and retry or surface conflict dialog letting user choose overwrite/refresh.

---

### BUG-TOPO-007 — Unconvert container removes descendants/edges in DOM without server-side coordination (Critical)
- **File:** src/ui/components/canvas_container_events.py
- **Root cause:** `ht:node-unconvert-container` `doUnconvert()` removes descendant edges and nodes purely client-side then strips container class. There is no server-side delete or user-visible audit; if those child nodes represent published devices, this will remove them from the user's view (and if autosave runs will persist layout deletion), potentially losing layout placements for published devices silently.
- **Repro:** Have a container with published child devices, unconvert it (confirm), observe children removed from view; autosave runs and persists a layout without those nodes.
- **Expected:** If converting removes published nodes from view, there must be explicit server-side operation such as update layout or a clear audit trail. At minimum the UI should warn clearly that published devices will be removed from view and offer a safe preview or require the user to use the 'Remove from View' flow which engages `ht:node-remove-from-view` with its dialog.
- **Suggested fix:** Prevent unconvert from removing published child nodes silently. If intention is to remove from view, call the same flow that removes and records the change; if the nodes are published devices, require separate confirmation and treat as layout edit persisted through the diagrams API explicitly (with version handling).

---

### BUG-TOPO-008 — _htEscapeHtml used inconsistently; double-escape risk (Medium)
- **File:** src/ui/services/topology_data.py
- **Root cause:** Server-side `load_canvas_data` applies `html.escape()` to device names, IPs etc. Then client-side code also calls `_htEscapeHtml` when building draft nodes or re-rendering — double-escaping may result in `&amp;lt;` appearing. Conversely, some client usages rely on `raw_name` for unescaped values; inconsistent handling risks XSS or visible entities.
- **Repro:** Create a device with name containing `& < >` and inspect label in canvas; check whether it's double-escaped depending on code path (published vs draft).
- **Suggested fix:** Standardize: server should return raw fields (unescaped) and the client must be responsible for escaping when injecting into innerHTML. Remove server-side HTML escaping from `load_canvas_data` (or mark fields `escaped_label` vs `raw_name`) and ensure clients escape exactly once when rendering.

---

### BUG-TOPO-009 — Context menu nearest-node heuristic brittle with zoom/pan (Medium)
- **File:** src/ui/components/canvas_js.py
- **Root cause:** Native `contextmenu` fallback computes nearest node by comparing rendered coordinates to `rx, ry` without compensating for CSS scaling or high-DPI; also threshold `>30` pixels is fixed and not scaled by `cy.zoom()`.
- **Repro:** Zoom canvas in/out and right-click near a node; context menu may fail to appear or attach to wrong node.
- **Suggested fix:** Use `n.renderedPosition()` vs client coordinates corrected by devicePixelRatio and consider scaling threshold by `1/zoom` or using `cy.renderer().projectIntoViewport` APIs.

---

### BUG-TOPO-010 — _htEventsWired gating may double-bind if toggled across rapid edit toggle transitions (Medium)
- **File:** src/ui/pages/topology.py
- **Root cause:** `on_enter_edit` sets `if(!window._htEventsWired && window._htInitEventHandlers){ window._htInitEventHandlers(...); window._htEventsWired=true; }` but if two enter-edit calls race (e.g., user rapidly toggles or two tabs), event handler may be partially wired or execute twice because `_htInitEventHandlers` closure returns early if `typeof window._htInitEventHandlers !== 'undefined'` at top but event function defines handlers inside that closure; edge cases can still lead to double-binding.
- **Repro:** Rapidly toggle edit mode twice; observe duplicate notifications or duplicate event behavior.
- **Suggested fix:** Move `window._htEventsWired` guard and binding responsibility entirely inside `_htInitEventHandlers`, and ensure idempotent event listener registration (use named handlers and `removeEventListener` before add).

---

### BUG-TOPO-011 — Draft publish when API down: inconsistent rollback and missing edge reattachment (High)
- **File:** src/ui/components/canvas_draft_publish.py
- **Root cause:** On failed publish the `catch` path adds `draft-error` class to `node` variable which may refer to the removed node if removal succeeded earlier; if `node` was removed prior to failure, the `catch` handler will error when calling `node.addClass(...)` or will not re-add edges properly.
- **Repro:** Simulate server error during POST `/api/devices/` (network down) and try to publish; check console errors and verify draft node state and edges.
- **Suggested fix:** Delay removing the draft node until after server confirms success. Alternatively, keep a locked local copy and only swap elements on confirmed server response. Ensure `catch` path checks `node.length` and re-adds edges idempotently.

---

### BUG-TOPO-012 — _htDraftCount / badge can go stale when nodes removed programmatically (Medium)
- **File:** src/ui/components/canvas_draft.py
- **Root cause:** Badge update relies on manual calls to `_htUpdateDraftBadge()` sprinkled across event handlers; some flows remove draft nodes (e.g., rollback paths, remove-from-view) but may not call the badge update resulting in stale UI count or negative/zero misdisplay.
- **Repro:** Publish a draft or remove draft via custom path and observe badge not updating until a further action triggers `_htUpdateDraftBadge()`.
- **Suggested fix:** Make badge a reactive calculation or subscribe to mutation events on `_cy` to update badge when `.draft` class changes. Always call `_htUpdateDraftBadge()` after any code path that changes draft nodes.

---

### BUG-TOPO-013 — Keyboard shortcuts can trigger while typing in inputs (Low)
- **File:** src/ui/components/canvas_shortcuts.py
- **Root cause:** Global shortcuts (Ctrl+S, Ctrl+A, Delete, etc.) do not check `document.activeElement` to avoid firing when user is typing in an input/textarea.
- **Repro:** Focus an input in the device detail panel and press Ctrl+A or Delete — the canvas handler may intercept and cause unexpected behavior.
- **Suggested fix:** In global shortcut handlers, early-return when `document.activeElement` is an input/textarea/select or has `contenteditable`.

---

### BUG-TOPO-014 — Edge delete confirmation uses raw_label unescaped (High)
- **File:** src/ui/components/canvas_js_helpers.py
- **Root cause:** `_deleteAssociation` builds `edgePrompt` using `edgeLabel` and concatenates into `confirm` without consistently escaping; although `_escapeHtml` is used in some places, confirm path uses `edgeLabel` unescaped in the `window.confirm` fallback branch.
- **Repro:** Create a connection with label containing `'<script>'` or HTML; open delete confirm and observe displayed content or console. (Note: confirm dialogs render text only, but Quasar dialog uses `message` which may accept HTML depending on component config.)
- **Suggested fix:** Always pass escaped text to UI dialogs and use `textContent`/safe APIs not `innerHTML`.

---

### BUG-TOPO-015 — applyLayoutPositions silently ignores nodes not present (Medium)
- **File:** src/ui/components/canvas_js_utils.py
- **Root cause:** `applyLayoutPositions` loops saved `nodes` and sets positions if `node.length` but otherwise does nothing. When layout references deleted device IDs, user may be unaware nodes were omitted and layout looks different with no warning.
- **Repro:** Load layout saved earlier, delete some devices in inventory, reload layout; nodes missing silently.
- **Suggested fix:** Return or log a warning listing missing IDs and surface a small UI toast: "X devices in layout missing from inventory".

---

### BUG-TOPO-016 — Native contextmenu stores window._htLastCtxX/Y globally (Low)
- **File:** src/ui/components/canvas_js.py
- **Root cause:** `container.addEventListener('contextmenu', ... )` sets global coordinates `window._htLastCtxX/_htLastCtxY` that persist and may leak position info to other scripts.
- **Repro:** Right-click and inspect `window._htLastCtxX` values.
- **Suggested fix:** Use local scope variables or store in a namespaced ephemeral object and clear after menu close.

---

### BUG-TOPO-017 — Draft form popover can render off-screen near viewport edges (Low)
- **File:** src/ui/components/canvas_draft_form.py
- **Root cause:** Draft form is positioned based on drop `screenX/screenY` without clipping logic.
- **Repro:** Drop from palette near right/bottom edges; form may be clipped.
- **Suggested fix:** Compute viewport dimensions and adjust popover position to keep it within bounds.

---

### BUG-TOPO-018 — _createAssociation + _htPromoteConnections can miss promoting some draft edges (Medium)
- **File:** src/ui/components/canvas_js_helpers.py, src/ui/components/canvas_draft_publish.py
- **Root cause:** Draft-edge creation and promotion is spread across client code; `_createAssociation` may create a draft-edge and `_htPromoteConnections` assumes `edge.data('draft_edge')` truthy and that both endpoints are published. If promotion timing interleaves, promotions may be skipped.
- **Repro:** Create draft A connected to published B, publish A while server slow, check connection promotion; or publish A and B in quick succession.
- **Suggested fix:** Make connection promotion idempotent and server-driven, or mark edges with stable temporary ids and query server for pending promotions until confirmed. Add retries and deduplication checks on client add.

---

### BUG-TOPO-019 — Edit toggle deadlocks behind draft-confirmation backdrop under rapid toggling (High)
- **File:** src/ui/components/topology_edit_toggle.py
- **Trigger:** Rapidly click Edit/Stop Editing while drafts are present on the canvas.
- **Root cause:** Exiting edit mode with drafts opens a new modal dialog each time (`dlg.open()`), and repeated toggles can stack/leave backdrop interception active. Subsequent clicks on the toggle are blocked by `.q-dialog__backdrop`.
- **Repro (Playwright MCP, 13 Apr 2026):**
  1. Open `/topology` with a diagram containing drafts.
  2. Enter edit mode.
  3. Trigger 40 rapid toggle clicks.
  4. Observe repeated click timeouts and pointer interception by dialog backdrop.
- **Expected:** At most one draft-warning dialog; toggle remains interactive after close/cancel.
- **Actual:** Toggle deadlocks under backdrop interception; 19/40 clicks missed across repeated runs.
- **Suggested fix:** Add single-instance dialog guard + disable toggle while dialog is open; clear stale dialog/backdrop before opening another.

---

### BUG-TOPO-020 — Draft-node tooltip probes invalid `/api/devices/draft-*` IDs, causing persistent 422 error spam (Medium)
- **File:** src/ui/components/canvas_tooltip.py
- **Trigger:** Hover over draft nodes and synthetic draft IDs under heavy interaction.
- **Root cause:** Tooltip handler fetches `/api/devices/{nodeId}?include=services` for every node hover without checking whether node is a draft. Draft IDs are not valid UUID device IDs on the API route.
- **Repro (Playwright MCP, 13 Apr 2026):**
  1. Add/keep multiple draft nodes on the canvas.
  2. Move cursor across draft nodes (or run stress interactions that cause hover events).
  3. Observe repeated `GET /api/devices/draft-*` requests returning 422.
- **Expected:** Draft nodes should skip service tooltip fetch or use local draft-safe behavior.
- **Actual:** Repeated 422 responses and console error spam.
- **Suggested fix:** Guard tooltip fetch with `nodeId.startsWith('draft-')` / `evt.target.data('draft')` and short-circuit.

---

## Playwright MCP Stress Addendum (13 Apr 2026)

Dynamic stress testing was run four times against isolated workspace/topology/layout sets. The runs confirm both existing findings and newly discovered defects.

### Reproducibility Metrics

| Run | Toggle misses (/40) | Context menu failures (/35) | Diagram PATCH 409s (/20) | Console errors |
|---|---:|---:|---:|---:|
| 1 | 19 | 29 | 19 | 23 |
| 2 | 19 | 21 | 19 | 23 |
| 3 | 19 | 23 | 19 | 23 |
| 4 | 19 | 32 | 19 | 23 |

### Existing Findings Confirmed Dynamically

- **BUG-TOPO-001** confirmed: concurrent diagram saves consistently produce conflict-heavy patterns (19/20 conflict responses) with no user-facing conflict notification.
- **BUG-TOPO-009** confirmed: right-click context-menu association workflow drops events at high rates under stress (21-32 failures out of 35 attempts).

### Additional Runtime Evidence Captured

- Repeated 409 responses on `PATCH /api/diagrams/{id}` during concurrent save lane.
- Repeated 422 responses on draft hover probes: `GET /api/devices/draft-*`.
- Console error stream remained non-zero in all stress runs due to unresolved 409/422 paths.

---

## Duplicate Merge Log
| Kept | Merged | Reason |
|---|---|---|
| BUG-TOPO-004 | BUG-TOPO-011 | Both relate to publish rollback/edge reattachment; kept BUG-TOPO-004 as canonical publish rollback issue. |

## Lane Coverage Status
| Lane | ODC | Findings | Status | Notes |
|---|---|---|---|---|
| lane-1 | Timing/Concurrency | BUG-TOPO-001,002,003,019 | OPEN | Autosave + beforeunload + edit-toggle deadlock. |
| lane-2 | Assignment/State (Draft lifecycle) | BUG-TOPO-004,005,011,012,018 | OPEN | Draft publish + badge + rollback issues. |
| lane-3 | Checking (Services) | BUG-TOPO-014,015,020 | OPEN | Delete dialogs, silent ignores, draft tooltip API misuse. |
| lane-4 | Timing/Serialization | BUG-TOPO-006 | OPEN | TOCTOU on reparent. |
| lane-5 | Function (Auth/RBAC) | - | N/A | No RBAC-specific holes found in static scan. |
| lane-6 | Integrity | BUG-TOPO-007 | OPEN | Container unconvert removes published children silently. |
| lane-7 | Documentation (Logs) | BUG-TOPO-016 | OPEN | Minor privacy/leak. |
| lane-8 | Interface (Architecture) | BUG-TOPO-010,008 | OPEN | Event wiring/idempotency and escaping inconsistencies. |
| lane-9 | Algorithm (Canvas UI) | BUG-TOPO-009,017,013 | OPEN | UX/shortcut/contextmenu issues (stress-reproduced). |
| lane-10| Algorithm (Domain) | BUG-TOPO-015 | OPEN | applyLayoutPositions missing-ID handling. |


---

### Next steps / Handoff
- Route high/critical findings (BUG-TOPO-001,002,003,004,005,006,007,011,014,019) to `QA-Fixer` for tactical patches and unit tests.
- Route BUG-TOPO-020 to `QA-Fixer` as a low-risk, high-noise frontend/API guard fix.
- Route container/transactional issues (BUG-TOPO-006,007) and publish architecture (BUG-TOPO-004,005) to `Architect -> Feature-Engineer` for design of safe server-side flows.
- I can open smaller PRs for low/medium fixes (badge update, keyboard guard, contextmenu threshold, draft tooltip guard) if you want — confirm preferred targets.


*Report generated by QA-Orchestrator. Evidence and code pointers came from static scan of `src/ui/components/*` and `src/ui/services/topology_data.py`.*
