Canvas Interaction UX Audit

QA Remediation Ledger

| Bug ID | Status | Root Cause (1 sentence) | Fix (lines) | Tests Added |
|---|---|---|---|---|
| HT077-QA-01 | FIXED | Reparent dispatch only treated ID-prefix drafts as local, so nodes marked as drafts in canonical node data or CSS class could fall through to the published API path. | 7 | 0 |
| HT077-QA-02 | FIXED | The right-click interaction bridge opened write actions before aligning the active node selection and detail-panel target to the clicked node. | 13 | 0 |
| HT077-QA-03 | FIXED | Convert-to-container mutated local Cytoscape state but relied on deferred autosave instead of flushing the personal-draft write from the same mutation site. | 3 | 1 |
| HT077-QA-04 | FIXED | The DOM contextmenu readonly guard returned before suppressing the native browser menu. | 1 | 0 |

Pipeline verdict: PARTIAL_SUCCESS

The four 21 Apr 2026 current-head proof failures are fixed and verified. Broader HT-077 audit items and proof gaps in this report remain open for separate validation.

Current UX Risks
Risk 1 — Container drags freely on first click (critical)
Location: canvas_container_drag_events.py:430-433

dragfree has an unconditional early-return for isContainerNode:


if (origin && origin.isContainerNode) {
    _htFinalizeDragNode(nodeId, true);
    return;   // ← no selectedAtPointerdown guard
}
Child nodes require selectedAtPointerdown = true before a reparent is allowed. Container nodes have no such gate. A user who clicks on the container edge or its interior background area (missing the child) will immediately drag the container (and all children) on first contact. This is the reported symptom.

Risk 2 — Selection normalization races with Cytoscape's own tap/select processing
Location: canvas_container_drag_events.py:349, canvas_js_interactions.py:100-101

_htNormalizeSelectionForContainerDrag(node) is called inside cy.on('pointerdown') — before Cytoscape has committed the tap/select state update. This means the normalization sees pre-tap selection. If the user had container A selected and clicks on a child of container B, the normalization runs on a stale selection set and may corrupt which nodes are marked for drag ownership.

Risk 3 — Container grow during drag is never reversed on snap-back
Location: canvas_container_actions.py:242-275

_htGrowContainerForDraggedChild applies parent.style('width') and parent.position() inline during a drag event. If the child is snapped back (because isSelectedForReparent was false), the container retains its grown dimensions and shifted center — the container has been visually corrupted without any move actually completing.

Risk 4 — No in-flight visual feedback for reparent vs. detach outcome
Location: _htResolveDetachAwareDropParent in canvas_container_drag_events.py:274-300

The decision of "will reparent into X", "will stay in current container", or "will detach to top-level" is made silently at drop time. There is no highlight on the prospective target container, no "will detach" indicator when the center-point exits the 4px boundary. Users have zero in-flight signal before releasing the mouse.

Risk 5 — Multi-selected node drag snaps back all nodes except the primary grab
Location: canvas_container_drag_events.py:386-474

cy.on('pointerdown', 'node') records ownership only for the node under the pointer. When Cytoscape fires dragfree on each node in a multi-drag, all nodes without ownership records fall into:


var isSelectedForReparent = !!(ownership && ownership.ownershipFrozen && ownership.selectedAtPointerdown);
// ownership is null for non-primary nodes → isSelectedForReparent = false → snap-back
Only the primary grabbed node survives. Box-select + drag of multiple nodes will visually snap back all nodes except the one actually clicked.

Risk 6 — Drag-to-detach has no distance threshold or confirmation
Location: canvas_container_drag_events.py:274-300 and canvas_container_actions.py:232-240

A child node dragged so that its center-point is 5px outside the 4px tolerance window silently detaches and triggers an API call. There is no minimum displacement, no undo prompt, and no confirmation. The interaction contract for delete nodes requires a confirmation dialog; detach — an equally significant structural change — has none.

Risk 7 — Context menu position is stale for cxttap-originated events
Location: canvas_context_menu.py:60, canvas_js_interactions.py:122-129

Both cxttap (Cytoscape) and the DOM contextmenu handler dispatch ht:context-menu-request but position the menu at window._htLastCtxX/Y — a mousemove-tracked stale coordinate. For cxttap the actual event position (evt.renderedPosition) is available but ignored. On trackpads where right-click is a two-finger tap, the menu renders at the last mouse position, not the tap position.

Risk 8 — Context menu proximity logic picks the nearest center-point, not the nearest visible area
Location: canvas_js_interactions.py:143-158

The DOM contextmenu fallback uses Euclidean distance to all node center points. A right-click in the middle of a large empty container will pick a child node whose center is close, rather than the container the user actually right-clicked on. The threshold of 30px rendered pixels is too coarse when nodes are small or zoomed out.

Risk 9 — cxttap/contextmenu double-fire dedup is fragile (50ms window)
Location: canvas_js_interactions.py:39-43

_htCtxMenuBridgeHandled is reset after 50ms. On slow systems or with right-drag micro-movement, both events can fire within the window, showing two menus, or the flag can expire before the second event arrives, showing the menu twice.

Risk 10 — View→edit mode transition can race with an active drag
Location: canvas_container_drag_events.py:489-496, canvas_mode.py:11-12

ht:mode-transition is dispatched synchronously inside htSetViewMode(). If a dragfree event is mid-execution when the mode changes, _htCancelContainerDrag clears _htContainerDragOrigin and _htContainerPointerOwnership while dragfree's closure still holds references to those structures. The finalization path may attempt to snap back a node whose origin record has already been deleted.

Recommended Interaction Contract
Layer 0 — Intentionality Gate (applies to all interactive gestures)
Any drag gesture that changes graph structure (reparent, detach, move-container) requires the acting node to have been explicitly selected before the drag begins (selectedAtPointerdown = true).

First click on any node or container: select it, open detail panel, do NOT initiate a drag.
Second click / click on already-selected: no-op (or open rename inline-edit if UX decides).
Drag on unselected node: Cytoscape fires the drag, but on dragfree snap back to origin with no side effects. This rule applies uniformly to containers and to leaf nodes.
This one rule eliminates Risk 1 and defines the interaction budget clearly.

Layer 1 — Selection
Gesture	Result
Single tap/click — node or container	Select, deselect others, open right-rail panel
Single tap — canvas background	Deselect all, close right-rail panels
Shift+click — node	Add to selection; start edge-association source
Box drag — canvas background	Multi-select
Click on already-selected, no drag	Deselect (or open inline edit — pick one, not both)
Layer 2 — Move (position-only, no structural change)
Gesture	Result
Drag selected leaf node	Move node; no parent change if drop stays inside same container
Drag selected container	Move container + all children as a unit; no child reparent
Multi-drag (box select + drag)	All selected nodes move; ownership records set for every selected node at grab-start, not just the primary
Contract: Move never changes parent field. Move is committed to autosave on dragend.

Layer 3 — Reparent / Detach (structural change, selection-gated)
Gesture	Condition	Result
Drag selected leaf to inside a different container	Node center inside new container bounds, ≥ 20px model-space displacement	Reparent into new container
Drag selected leaf to outside all containers	Node center outside origin container bounds by ≥ 20px	Detach to top-level
Drag selected leaf stays within origin container		Position update only
Drag container	N/A	Container never reparents via drag — only via context menu "Move into container"
Visual contract during drag:

Prospective target container gets .ht-drop-target class (highlight ring).
When node center exits parent bounds, parent gets .ht-will-detach class (warning indicator).
Indicator updates live on drag tick, not just on dragfree.
Layer 4 — Container-specific gestures
Gesture	Target	Result
Click	Container background (no child under pointer)	Select container
Click	Child node inside container	Select child only; container NOT selected or moved
Drag	Selected container	Move container + children; no reparent
Drag	Selected child	Move child within container; container grows only if child exits padding zone
Right-click	Container background	Context menu scoped to container (Collapse/Expand, Convert to Node)
Right-click	Child node	Context menu scoped to child (Start Association, Remove from container, Delete)
Layer 5 — Readonly mode
autoungrabify(true) prevents all node drabs — no snap-back needed.
Taps still emit ht:node-selected for panel display.
Context menu suppressed globally (if (window.HT_READONLY) return). ✓ (already implemented)
Edge Cases To Cover
Container with zero children — a converted-empty container should be draggable on first click (no children to confuse hit detection). The selectedAtPointerdown gate must still apply.

Child dragged to sibling container — both the source container detach and target container reparent must be a single atomic API call, not two separate calls that can partially succeed.

Drag of a container that is itself a child of another container — _htResolveDropParent must correctly identify the grandparent container as a candidate without treating the moving container as its own valid parent.

Mode switch during active drag — _htCancelContainerDrag must only run AFTER dragfree has fully resolved. Safeguard: set a _htDragInProgress flag on grab, clear on dragfree/dragend; if mode changes while flag is set, defer cancel to the next dragfree.

Undo of a container-move — moving a container should not create a separate undo entry per child node. The entire container-move must be one undo entry covering both parent and all descendant positions.

Collapsed container drag — if a container is collapsed (children hidden), dragging it must not trigger child drag/dragfree events for the hidden children. Verify Cytoscape fires no events on hidden elements.

Resize handle vs. drag handle conflict — the resize overlay (ht-node-resize-overlay) lives at z-index: 8; the canvas canvas at default stacking. Clicking on a resize handle must not trigger node selection or drag initiation.

cxttap + DOM contextmenu both fire on right-click — the 50ms dedup window must be extended or replaced with a flag-flip pattern (_htCtxMenuBridgeHandled = true on first event, cleared in requestAnimationFrame after both events have fired).

Touch / pen input — pointerId is stored but never used to reject spurious events. A second-finger touch during a drag should cancel the current gesture, not corrupt the ownership map.

Draft node in a container reparented via drag — draft nodes use _htCommitLocalReparent (local only, no API); published nodes use _htRequestPublishedReparent (API). Mixed selection (one draft + one published child) during a multi-drag must not attempt API reparent for the draft node.

Implementation Guidance
The five highest-priority changes, ordered by blast radius:

1. Apply selectedAtPointerdown gate uniformly to containers (canvas_container_drag_events.py:430-433) — Remove the isContainerNode early-return. Let the same !isSelectedForReparent → snapBack path apply. Containers should snap back on an unintentional first-grab just like leaf nodes.

2. Move _htNormalizeSelectionForContainerDrag out of pointerdown into grab (canvas_container_drag_events.py:349) — grab fires after Cytoscape has settled selection state. This eliminates the race condition in Risk 2.

3. Record ownership for all selected nodes at grab-time, not only the primary pointer-down node (canvas_container_drag_events.py:342-364) — Inside cy.on('grab', 'node'), iterate cy.$('node:selected') and populate _htContainerPointerOwnership for each, copying the primary node's selectedAtPointerdown: true. This fixes Risk 5.

4. Add live drop-target CSS classes during drag — In cy.on('drag', 'node'), after the container-growth RAF, resolve the prospective parent and add .ht-drop-target to it; remove the class from all other containers. Add .ht-will-detach to the origin container when center-point exits bounds. Remove all indicator classes in dragfree and on Escape cancel. This addresses Risk 4 and Risk 6.

5. Fix context menu position for cxttap (canvas_js_interactions.py:122-129) — Pass evt.renderedPosition (or evt.originalEvent.clientX/Y) into the ht:context-menu-request detail so the menu renders where the user right-clicked, not at a stale mousemove coordinate.

For the context menu hit-testing fix (Risk 8): change the proximity algorithm to test whether the click landed inside a node's rendered bounding box before falling back to center-point distance. This correctly attributes container-area right-clicks to the container, not to the nearest child center.


{
  "status": "SUCCESS",
  "artifacts_produced": ["UX audit document — review only, no code modified"],
  "verified_against_gate": false,
  "blocker_details": null,
  "follow_up_required": true
}
Current UX Risks
Reviewed canvas_js_interactions.py (line 22), canvas_container_drag_events.py (line 320), canvas_container_actions.py (line 242), canvas_context_menu.py (line 10), topology.py (line 80), and ran focused unit suites (153 passing). The code is internally guarded, but the UX contract is still too implicit and too late-bound.

First-click gating happens after motion begins. Move capture starts on canvas_js_interactions.py (line 98), parent growth can happen during canvas_container_drag_events.py (line 366), and the “you were not preselected” rejection happens only on canvas_container_drag_events.py (line 435). That is why first-click child gestures can still feel like they moved the wrong thing before snapping back.
Gesture ownership is inferred retroactively instead of claimed deterministically. Ownership is stored on raw pointerdown at canvas_container_drag_events.py (line 342), then descendant collisions are cleaned up only at release at canvas_container_drag_events.py (line 393). That is fragile for parent-with-children moves.
Selection normalization happens at drag time, not selection time. _htNormalizeSelectionForContainerDrag lives at canvas_container_drag_events.py (line 9) and is invoked on pointerdown/dragstart/drag, not when selection changes. So the canvas can sit in an ambiguous parent+child selection state until movement starts.
Containers have no explicit move affordance. Selected state is just a slightly thicker border in canvas_styles.py (line 111), compounds are styled the same broad way at canvas_styles.py (line 161), and editability simply grabify()s nodes in canvas_js_interactions.py (line 11). There is no premium distinction between “selected”, “move container”, and “interact with child”.
Context-menu targeting is too permissive. The fallback handler on canvas_js_interactions.py (line 131) picks the nearest node within 30px at canvas_js_interactions.py (line 156), and right-click does not first align visible selection to the menu target at canvas_js_interactions.py (line 122). In a dense canvas, that is not intentional enough for write actions.
Readonly right-click is inconsistent. The menu listener exits immediately at canvas_context_menu.py (line 10), while the container fallback returns before preventDefault() at canvas_js_interactions.py (line 131). That can devolve into a dead gesture or browser-native context menu instead of product-defined behavior.
Tentative child drags mutate parent geometry live in canvas_container_actions.py (line 242), but cancel/snapback restores only the node in canvas_container_drag_events.py (line 82) and canvas_container_drag_events.py (line 302). A rejected gesture can still leave the parent feeling stretched or unstable.
Reparent vs detach intent is invisible. Resolution is heuristic-only in canvas_container_drag_events.py (line 176), canvas_container_drag_events.py (line 209), and canvas_container_drag_events.py (line 274), with no target highlight or pre-drop preview. Users cannot predict “stay”, “move into container”, or “detach”.
Recommended Interaction Contract

View mode: select, open details, pan, zoom, fit. No move, resize, association, reparent, detach, or write context actions.
Edit mode: first click is always selection-only. Movement starts only if the item was already selected at pointerdown and drag distance exceeds 5px.
Mixed ancestor/descendant selection is illegal. Normalize immediately on selection change, not on drag. Clicking a child clears selected ancestors. Clicking a container move handle clears selected descendants. Multi-select may contain siblings or disjoint branches, never both a container and its own descendants.
A node/container must look “armed” before it can move. Use a stronger selected state, and show container move affordance only when that container is selected.
Container drag should require an explicit handle or header zone. The container body should not own move gestures.
Child nodes own gestures inside their own bounds. Resize handles outrank move. Container move handle outranks body hit areas.
Dragging a selected container moves the entire subtree as one locked group. Child parentage must not change, child relative offsets must stay unchanged, and parent drag must never trigger child detach/reparent logic.
Dragging a selected child inside its current container repositions it only. No reparent occurs unless a target container is explicitly highlighted.
Reparent rule: the only valid drop target is the deepest valid container whose content bounds contain the dragged node center. No proximity-only or overlap-only write fallback.
Detach rule: detach only when the dragged child starts selected, leaves the origin container bounds, has no highlighted target at release, and drops beyond the 5px drag threshold. Preserve rendered screen position on detach.
Right-click on a node should select that node first if it is not already the active target. Right-click on background should open a canvas menu or nothing; it must never guess the nearest node.
Readonly context menu should be consistent: either a read-only app menu (Open details, Center, Enter Edit Mode for editors) or no menu at all, but never the browser menu.
Edge Cases To Cover

Unselected child inside a selected parent: first pointer cycle selects child only; parent does not move; parent bounds do not change.
Selected child dragged <5px: no move, no reparent, no detach, no autosave, no parent growth.
Parent drag with children: descendants remain attached; no descendant dragfree path can detach them.
Child dragged outside origin then back in before release: release inside origin keeps parent and clears any preview target.
Nested containers: deepest valid target wins; self/descendant cycles are impossible.
Box-select or Ctrl/Cmd-select that includes ancestor+descendant: normalized immediately before any further gesture.
Cancel via Escape, pointercancel, mode toggle, or pagehide: restore node position, parent id, parent preview size, highlight state, and selection.
Optimistic reparent failure/409: same full restore as cancel, including selection and parent geometry.
Right-click on unselected node, selected node, background near a node, and readonly canvas all behave deterministically.
Resize handles vs container move handle: resize wins; body click still only selects.
Ghost, locked, and collapsed nodes/containers never expose hidden write paths.
Implementation Guidance

Keep this in the existing JS bridge, not Python orchestration: canvas_js_interactions.py (line 22), canvas_container_drag_events.py (line 3), canvas_context_menu.py (line 6), canvas_styles.py (line 92), canvas_mode.py (line 8).
Promote eligibility checks earlier. No _htBeginMoveGesture, no _htMaybeGrowContainerForDraggedChild, and no live parent mutation until the gesture is confirmed eligible.
Replace the current loose maps with one explicit gesture state machine: idle, select_only, move_leaf, move_container, reparent_preview, resize, context_menu.
Reuse the existing overlay root #ht-node-resize-overlay to render a selected-container move handle and drop-target previews. That fits the current Cytoscape + NiceGUI architecture cleanly.
During active container move, temporarily make descendants non-interactive and restore them on finish/cancel.
Remove nearest-node context-menu fallback for write actions. Use exact Cytoscape hit-testing only.
Treat parent growth as preview state, not committed state. Any preview geometry must have a guaranteed rollback path on cancel, failed reparent, or first-click rejection.
Add E2E tests for the contract, especially “first click on child after parent was selected”, “parent drag never detaches child”, “cancel restores parent preview size”, and “readonly right-click never leaks browser menu”.
{
  "status": "SUCCESS",
  "artifacts_produced": [],
  "verified_against_gate": false,
  "blocker_details": null,
  "follow_up_required": false
}

## 21 Apr 2026 Current-Head Bug Hunt Addendum

### Confirmed Current-Head Bugs

1. `Remove from container` fails live with an invalid payload error.
  - Repro: open a topology in edit mode, right-click a child node inside a container, choose `Remove from container`.
  - Expected: the child detaches to top level, stays at its current absolute position, and the parent link is cleared.
  - Actual: the app shows `Action failed: Invalid reparent action payload` and the node remains parented after reload.
  - Evidence: `artifacts/user-sim/ht077-remove-from-container-invalid-payload-20260421.png`.
  - Impact: this breaks a core HT-077 acceptance path and blocks closeout.

2. Context-menu write actions can target a node different from the actively selected node.
  - Repro: select node A so the side panel shows A, right-click a different node B, then run `Convert to Container`.
  - Expected: either the right-click first aligns selection to B before allowing the write action, or the action applies only to the active selection target.
  - Actual: the action applies to B while the visible selection and side panel remain on A.
  - Evidence: `artifacts/user-sim/ht077-selection-mismatch-context-action-20260421.png`.
  - Impact: this violates the intended selection-first interaction contract and creates a high risk of accidental structural edits.

### Source-Level Defects / Proof Gaps Found On Current Head

3. Convert-to-container persistence still appears to rely on later side effects rather than a guaranteed persistence path.
  - Source signal: the convert handler mutates local container state but does not itself schedule autosave or another explicit persistence trigger.
  - Risk: a convert action may look successful and then disappear on refresh if no later autosave-triggering gesture occurs.
  - Classification: unresolved known bug until disproven live.

4. Readonly DOM `contextmenu` fallback returns before `preventDefault()`.
  - Source signal: in readonly mode the handler exits early before suppressing the native browser menu.
  - Risk: readonly canvas right-click behavior can leak the browser context menu instead of consistent app behavior.
  - Classification: unresolved known bug until disproven live.

5. Multi-node structural reparent/detach atomicity is still unproven.
  - Source signal: dragfree resolves structural updates node-by-node, not as an all-or-nothing grouped operation.
  - Risk: a mixed draft/published multi-selection could partially commit on failure.
  - Classification: proof gap requiring focused failure-path validation.

6. Real-event context-menu dedup robustness remains under-verified.
  - Source signal: dedup uses an id + eventId key with a short cleanup window, but this addendum did not include cross-device timing stress.
  - Risk: duplicate menus may still surface under trackpad vs mouse timing variance.
  - Classification: proof gap requiring live right-click stress validation.


