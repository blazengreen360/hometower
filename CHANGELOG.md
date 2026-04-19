# Changelog

All notable changes to Hometower will be documented in this file.

## [Unreleased]

### Fixed — HT-082 dashboard owner-scope hardening

- Closed the dashboard legacy-schema compatibility path so All Workspaces falls back to owned current-diagram membership instead of dropping owner scoping when `Device.owner_id` is unavailable.
- Added cross-owner legacy regressions for repository and API dashboard summaries, and split dashboard/canvas helper code so the cited source files stay under the 250-line project cap without changing shipped HT-082 behavior.
- Hardened owner-scoped device repository reads against legacy no-`Device.owner_id` schemas, restricted device placement/orphan lookups to current topology layouts, and split the device domain Cytoscape helpers into a separate pure module to restore file-cap compliance.

### Added — HT-081 data table enhancements and pagination

- Standardized the Workspaces, workspace-detail Topologies, and Settings Users pages on a shared NiceGUI table pattern with client-side search, sorting, pagination defaults, and consistent HT-080 table chrome.
- Added shared table helper wiring plus focused execution coverage for real search-handler registration and the Settings Users row-action event path, keeping browser-local timestamp formatting aligned with the existing HT-054 convention.

### Changed — HT-080 UI premiumization and component consistency

- Added shared page, card, button, banner, and table primitives in `src/ui/design/primitives.py` and expanded the theme token set in `src/ui/design/tokens.py` so typography, spacing, and semantic actions now resolve through one global UI specification.
- Reworked the app shell plus first-class surfaces across dashboard, workspaces, workspace detail, login/access-denied, IPAM, settings pages, inventory tables, and the dedicated inventory editor to use the shared HT-080 visual language instead of page-local styling.
- Standardized destructive/secondary/primary action treatments in shared dialogs and detail panels, and removed remaining hardcoded hex colors from `src/ui` component files outside the design-token layer.
- Normalized supporting topology/canvas helpers to read semantic colors from the theme system, keeping UI chrome and canvas affordances aligned across light, dark, and midnight themes.

### Added — HT-087 quick wins

- Added a new topology Auto-Layout toolbar action that runs an animated Cytoscape layout and persists the resulting node positions through the existing draft/autosave path.
- Device notes now render sanitized markdown in read mode while preserving raw markdown editing in the existing device detail workflow.
- The inventory page now exposes one-click CSV export for the current filtered rows, including Name, Status, Type, IP, MAC, Location, and Notes, with spreadsheet-formula prefix hardening.
- Device detail views now expose dense SSH, HTTP, and HTTPS quick-connect actions when an IP address is present.

### Added — HT-050 node and container drag resize

- Added edit-mode-only resize handles for topology nodes and containers through a new canvas overlay bridge, with corner proportional resize, edge-only dimension resize, minimum-size clamping, and compound/container child-bounds enforcement.
- Persisted resized dimensions through existing topology autosave/save/history flows by serializing inline Cytoscape `style.width` and `style.height` into the existing canvas JSON path and restoring them on reload and history restore.
- Fixed the topology history restore dialog flow so the restore confirmation is no longer blocked by an overlapping history-dialog backdrop, and added focused unit, integration, and browser proof coverage for resize persistence and restore behavior.

### Fixed — HT-050 nested container clamp regression

- Corrected compound/container minimum-size enforcement when resizing a nested container or a parent container with children, so shrink attempts now clamp against child bounds plus directional padding instead of allowing undersized persisted layouts.
- Tightened the resize baseline to prefer persisted inline `style.width` / `style.height` values for compound nodes, and added focused unit plus deep browser-proof coverage for nested-container clamp behavior.

### Fixed — HT-050 container child-drift during resize

- Corrected compound/container one-sided resize math so the non-dragged interior edge remains visually pinned and child nodes no longer slide with the container during expand or shrink operations.
- Added focused browser-proof coverage for the exact user-reported case: one container with one child node now resizes cleanly across all four axes and remains sane after refresh.
- Hardened the deep browser-proof harness for HT-050 with stronger post-login readiness checks and longer nested-container settle waits so the direct-run canvas proof is more reliable during local verification.

### Fixed — HT-068 reliable JSON export from Settings

- Settings -> Data export now completes successfully for authenticated Admin and Contributor users through the existing credentialed `/api/export` download path, without redirecting to `/login` or showing stale-session failure copy on successful exports.
- Reader users now see the export action as unavailable/disabled with clear role guidance, and failed export responses surface explicit session/permission/server messaging instead of the old generic browser-alert path.
- Added focused proof coverage for the shipped export behavior in `tests/unit/test_settings_data_page.py`, `tests/unit/test_settings_pages_execution.py`, `tests/integration/test_export.py`, and direct-run browser proof `tests/e2e/test_export_clickpath.py`.

### Fixed — HT-008 map first-load rendering stability

- Hardened Leaflet map bootstrap in `src/ui/components/map_view.py` with post-mount size invalidation retries so `/map` no longer initializes against a transient 0x0 container during NiceGUI layout settle.
- Added scoped Leaflet image guards (`#ht-map-canvas .leaflet-tile/.leaflet-marker-icon/.leaflet-marker-shadow { max-width: none !important; }`) to prevent Tailwind base `img { max-width: 100% }` from collapsing map tiles/markers on first load.
- Added HT-008 regression coverage in `tests/integration/test_runtime_ui_routes.py` to lock both the Leaflet image-size guard and post-layout invalidate retry behavior.

### Added — HT-075 restore history safely when inventory devices were deleted

- Added domain mapping functions in `src/domain/topology_history.py` to synthesize ghost placeholders for connected devices that were deleted from inventory prior to current history restore.
- Implemented `Recreate as New Device` and `Map to Existing Device` workflows to safely reintegrate ghost placeholders back into active topology layouts.
- Added `ghost_detail_panel.py` and dedicated styling to safely expose disconnected legacy references.

### Added — HT-074 leave-page protection for unsaved topology changes

- Added contributor/admin discard-draft API support with `DELETE /api/topologies/{topology_id}/personal-draft` in `src/api/routers/topology_editor.py`, `src/services/topology_editor_service.py`, `src/services/topology_editor_draft_service.py`, and `src/models/topology_personal_draft.py`; discard now removes only the caller's draft row and returns explicit discard metadata.
- Added topology-only in-app leave guard script in `src/ui/components/topology_leave_guard.py` and wired it from `src/ui/pages/topology.py` so internal navigation attempts can branch to `Save Version`, `Discard`, or `Cancel` while preserving native `beforeunload` warnings for hard unload.
- Added a topology-aware navigation bridge for sidebar and breadcrumb routes in `src/ui/components/sidebar.py` and `src/ui/components/breadcrumb.py`, routing topology-page internal navigation through `window.htNavigateWithGuard(...)` while preserving existing navigation behavior on non-topology pages.
- Added focused HT-074 coverage for discard endpoint semantics, no-prompt clean-path checks, leave-guard role gating, and navigation bridge behavior in `tests/integration/test_topology_editor.py`, `tests/unit/test_topology_leave_guard.py`, and `tests/unit/test_ui_navigation_components.py`.

### Fixed — HT-074 internal navigation leave-guard precedence

- Resolved the live sidebar/breadcrumb text-click race by propagating guard data attributes onto visible click targets in `src/ui/components/sidebar.py` and `src/ui/components/breadcrumb.py`, and by taking early `pointerdown` ownership in `src/ui/components/topology_leave_guard.py` so the custom `Save Version / Discard / Cancel` modal opens before native unload prompts on guarded internal navigation.
- Internal topology navigation initiated from sidebar/breadcrumb now executes through client-side click handlers (`js_handler`) in `src/ui/components/sidebar.py` and `src/ui/components/breadcrumb.py`, so guard interception happens immediately on the client before any route-unload attempt.
- Sidebar and breadcrumb guard attributes are now emitted as explicit quoted data attributes, and the leave-guard click capture path now resolves targets from text nodes/composed paths before matching `[data-ht-guard-nav]`, preventing topology sidebar text-click races from reaching competing navigation handlers before the modal opens.
- Hardened `src/ui/components/topology_leave_guard.py` by removing brittle runtime role-order gating, reusing the guarded proceed path for clean internal navigation, and stopping click propagation during guarded anchor interception to prevent competing route handlers from racing ahead of the modal.
- Updated autosave unload fallback in `src/ui/components/canvas_js_autosave_runtime.py` to honor `window._htLeaveGuardBypassOnce`, preserving native beforeunload for hard unloads while avoiding native prompts during intentional in-app guarded transitions.
- Added focused regressions in `tests/unit/test_ui_navigation_components.py`, `tests/unit/test_topology_leave_guard.py`, `tests/unit/test_ui_canvas.py`, and `tests/unit/nicegui_fakes.py` for guarded client-nav bridge wiring, modal-first interception semantics, and autosave bypass behavior.

### Added — HT-073 personal topology drafts with autosave UX

- Added explicit unsaved-draft metadata across topology editor contracts: `has_unsaved_changes` now flows through `TopologyEditorStateResponse`, personal-draft autosave responses, and save-version/restore responses in `src/models/topology_editor.py`, `src/models/topology_personal_draft.py`, `src/services/topology_editor_draft_service.py`, and `src/services/topology_editor_history_service.py`.
- Implemented server-side unsaved detection by comparing a caller's personal draft against the topology's latest saved snapshot in `src/services/topology_editor_common.py` and `src/services/topology_editor_draft_service.py`, preserving HT-072 history append-only semantics and keeping autosave isolated from history creation.
- Reworked the topology Draft status indicator to match HT-073 semantics: the chip now represents unsaved personal-draft state (not `.draft` node counts), with state synchronized from editor-state load, autosave responses, and save/restore flows via `src/ui/components/canvas_draft.py`, `src/ui/components/canvas_js_autosave.py`, `src/ui/components/topology_layout_bar.py`, `src/ui/services/topology_data_support.py`, `src/ui/pages/topology.py`, and `src/ui/pages/topology_page_support.py`.
- Added HT-073-focused proof coverage for draft resume/unsaved semantics, reader no-side-effect behavior, save-version publishing of active drafts, and per-user draft privacy in `tests/integration/test_topology_editor.py`, `tests/unit/test_topology_editor_draft_service.py`, `tests/unit/test_topology_data.py`, `tests/unit/test_canvas_draft.py`, `tests/unit/test_ui_canvas.py`, and `tests/unit/test_topology_layout_bar_execution.py`.

### Fixed — HT-072 topology toolbar browser semantics

- Updated topology header controls in `src/ui/components/topology_layout_bar.py` so the primary user-facing workflow is explicit `Save Version` + `History`, with restore moved behind the History interaction flow.
- Fixed History selector restore routing in `src/ui/components/topology_layout_bar.py` by normalizing real select payload shapes (id, label, and index payloads) back to canonical history entry IDs before restore calls.
- Removed the `Version name` save modal friction from HT-072 by making the primary `Save Version` button execute a direct checkpoint save with server-generated naming when no explicit name is provided; restore confirmation remains deliberate.
- Added stronger execution coverage in `tests/unit/test_topology_layout_bar_execution.py` to assert `History` is rendered as a primary toolbar action and legacy `Save Layout` wording is not present.
- Added HT-072 targeted regressions in `tests/unit/test_topology_layout_bar_execution.py`, `tests/integration/test_topology_editor.py`, and new browser script `tests/e2e/test_topology_history_restore_flow.py` to cover selection + append-only restore from the live History UI.
- Updated browser regression checks to HT-072 semantics in `tests/e2e/test_stories_e2e.py`, `tests/e2e/test_deep_hunt.py`, and `tests/e2e/test_topology_canvas_deep.py`.

### Added — HT-072 topology history + personal drafts foundation

- Added topology-centric persistence foundation for immutable history and per-user drafts: `Topology.current_diagram_id` in `src/models/topology.py`, new `TopologyHistoryEntry` + `TopologyPersonalDraft` models in `src/models/topology_history_entry.py` and `src/models/topology_personal_draft.py`, API schemas in `src/models/topology_editor.py`, and Alembic migration `alembic/versions/025_topology_history_and_personal_drafts.py` with backfill of current pointers and legacy history rows.
- Added dedicated repositories/services/routers for HT-072 workflows: `src/repositories/topology_history_repository.py`, `src/repositories/topology_personal_draft_repository.py`, `src/services/topology_editor_common.py`, `src/services/topology_editor_draft_service.py`, `src/services/topology_editor_history_service.py`, façade `src/services/topology_editor_service.py`, and new routes in `src/api/routers/topology_editor.py` mounted in `src/api/app.py` (`/editor-state`, `/history`, `/personal-draft`, `/save-version`, `/history/{id}/restore`).
- Switched topology UI loading and save flows to topology-centric contracts: editor-state loading path in `src/ui/services/topology_data.py`, topology page bootstrap/state wiring in `src/ui/pages/topology.py`, workspace navigation updates in `src/ui/pages/workspace_detail.py`, and history toolbar semantics (`History`, `Save Version`, restore) in `src/ui/components/topology_layout_bar.py`, `src/ui/components/topology_layout_api.py`, and `src/ui/components/topology_layout_dialogs.py`.
- Rerouted canvas save plumbing from diagram PATCH autosave to personal-draft autosave (`PUT /api/topologies/{id}/personal-draft`) in `src/ui/components/canvas_js_autosave.py`, `src/ui/components/canvas_js_utils.py`, and container unconvert persistence in `src/ui/components/canvas_container_unconvert.py`; updated keyboard/event bridge names to `ht:save-version` in `src/ui/components/canvas_shortcuts.py` and `src/ui/components/canvas_events.py`.
- Added/updated coverage for new behavior in `tests/integration/test_topology_editor.py`, `tests/integration/test_rbac_coverage.py`, `tests/unit/test_topology_layout_bar_execution.py`, `tests/unit/test_topology_data.py`, `tests/unit/test_workspace_pages_execution.py`, `tests/unit/test_canvas_shortcuts.py`, `tests/unit/test_canvas_js_view_mode.py`, and `tests/unit/test_ui_canvas.py`.

### Added — HT-031 inventory bulk actions

- Implemented inventory multi-select batch workflows using existing per-device API endpoints (no new backend bulk endpoints): add tag, remove common tag, set location, and bulk delete with connection preflight skip behavior in `src/ui/pages/inventory_bulk_actions.py`, `src/ui/pages/inventory_bulk_toolbar.py`, `src/ui/pages/inventory_bulk_handlers.py`, and `src/ui/pages/inventory_page_controller.py`.
- Refactored `src/ui/pages/inventory.py` to a thin route wrapper delegating to the controller, preserving auth guard behavior while isolating page orchestration logic.
- Updated inventory table rendering to support native NiceGUI multiple selection in contributor/admin mode, keep reader mode non-selectable, and preserve in-place delete event emission in `src/ui/pages/inventory_table.py`.
- Added pure domain helper `get_common_tags(...)` for intersection-based remove-tag options and updated tag chip loading to return toolbar option payloads in `src/domain/inventory.py` and `src/ui/pages/inventory_filters.py`.
- Added bulk delete confirmation dialog and expanded HT-031 coverage in `tests/unit/test_inventory_bulk_actions.py`, `tests/unit/test_inventory_page_execution.py`, `tests/unit/test_inventory_helpers.py`, `tests/unit/test_inventory_domain.py`, and `tests/unit/nicegui_fakes.py`.

### Fixed — HT-054 human-readable hierarchy timestamps in workspace pages

- Added shared UI timestamp helpers in `src/ui/utils/formatting.py` and exported them via `src/ui/utils/__init__.py` so hierarchy pages format `last_modified` consistently.
- `/workspaces` and `/workspaces/{id}` now render `Last Modified` as `MMM D, YYYY, h:mm A`, show `\u2014` fallback for missing/null values, and expose the original ISO timestamp on hover via `q-tooltip` in `src/ui/pages/workspaces.py` and `src/ui/pages/workspace_detail.py`.
- Added focused HT-054 unit coverage for the shared formatter and both page consumers in `tests/unit/test_ui_formatting.py` and `tests/unit/test_workspace_pages_execution.py`.

### Fixed — HT-055 validation feedback in create and rename dialogs

- Refactored the shared name dialog in `src/ui/components/dialogs/name_dialog.py` so submit handlers return an inline error string (or `None` for close), enabling required-name and duplicate-name feedback without silently closing the dialog.
- Workspace and topology create/rename flows now map API `409` responses to entity-specific inline errors while preserving existing non-409 negative toast behavior and existing success toasts in `src/ui/pages/workspaces.py` and `src/ui/pages/workspace_detail.py`.
- View rename in the topology layout bar now uses the shared name dialog and returns the inline duplicate error `A view with this name already exists.` on API `409`, while keeping existing success/non-409 toast behavior in `src/ui/components/topology_layout_bar.py`.
- View save/create now shows inline required-name and duplicate-name feedback in the save dialog, keeps the dialog open on those validation errors, clears inline error state on input change, preserves non-409 toast behavior, and keeps success-close + success toast behavior via `src/ui/components/topology_layout_bar.py` and `src/ui/components/topology_layout_dialogs.py`.
- Added focused execution coverage for dialog error transitions and no-close duplicate handling in `tests/unit/test_name_dialog_execution.py`, `tests/unit/test_workspace_pages_execution.py`, and `tests/unit/test_topology_layout_bar_execution.py`.

### Added — HT-032 canvas undo/redo with HT-051 T-001 remove-from-view integration

- Added canvas undo API contracts and orchestration for published device snapshot delete/restore flows: new API schemas in `src/models/canvas_undo.py`, layout snapshot helpers in `src/domain/devices.py`, transactional restore/delete service in `src/services/canvas_undo_service.py`, and new contributor-only routes `POST /api/devices/{id}/canvas-delete` + `POST /api/devices/{id}/restore` in `src/api/routers/device_sub_routes.py`.
- Added per-session client-side undo/redo stack engine with 50-entry cap, redo invalidation, local/API execution split, move batching hooks, undo state events, and toolbar state sync in `src/ui/components/canvas_undo.py` and `src/ui/components/topology_undo_bar.py`.
- Rewired topology canvas write producers to undo-aware paths: dragstart/dragend move batching (`src/ui/components/canvas_js_interactions.py`), published edge create/delete bridge (`src/ui/components/canvas_js_helpers.py`), published node delete bridge (`src/ui/components/canvas_events.py`), and remove-from-view local undo snapshot path (`src/ui/components/canvas_draft_events.py`).
- Added Python-side undo action execution bridge in `src/ui/components/canvas_undo_handlers.py` and topology page wiring/reset hooks in `src/ui/pages/topology.py`, replacing direct published-canvas JS fetch mutations with Python/API-mediated operations.
- Integrated detail panels into the same undo stack: editable row callback injection in `src/ui/components/device_panel_helpers.py`, PATCH-backed device field/status undo entry creation in `src/ui/components/device_detail_panel.py`, and stack-aware connection delete routing in `src/ui/components/connection_detail_panel.py`.
- Added targeted HT-032 coverage across unit, integration, execution, and browser-proof scopes: `tests/unit/test_canvas_undo.py`, `tests/unit/test_topology_undo_bar_execution.py`, `tests/unit/test_device_detail_panel_execution.py`, `tests/unit/test_connection_detail_panel_execution.py`, `tests/integration/test_canvas_undo_api.py`, `tests/e2e/test_topology_canvas_undo_redo.py`, plus updates to `tests/unit/test_domain_devices.py`, `tests/unit/test_canvas_shortcuts.py`, and `tests/unit/test_ui_canvas.py`.

### Added — HT-024 read-only IPAM view

- Added dedicated IPAM backend stack with shared enums and response models (`src/models/types.py`, `src/models/ipam.py`), pure IPv4 classification/render builders (`src/domain/ipam.py`), batch membership repository helper (`src/repositories/network_repository.py`), read-only orchestration service (`src/services/ipam_service.py`), and Reader-gated API routes (`src/api/routers/ipam.py`) wired into `src/api/app.py`.
- Added authenticated `/ipam` UI with lazy per-network detail loading, visible-network client-side search, conflict-aware navigation to `/topology?device_id={id}`, and dedicated modular components/services (`src/ui/pages/ipam.py`, `src/ui/components/ipam_stats_row.py`, `src/ui/components/ipam_grid.py`, `src/ui/components/ipam_block_summary.py`, `src/ui/services/ipam_data.py`, `src/ui/services/ipam_search.py`).
- Added IPAM semantic theme tokens (`ipam_used`, `ipam_free`, `ipam_gateway`, `ipam_conflict`, `ipam_reserved`) across all themes in `src/ui/design/tokens.py`, plus navigation/app registration for `/ipam` in `src/ui/components/sidebar.py` and `src/main.py`.
- Added HT-024 test coverage for domain, service, search, page execution, and API integration (`tests/unit/test_ipam_domain.py`, `tests/unit/test_ipam_service.py`, `tests/unit/test_ipam_search.py`, `tests/unit/test_ipam_page_execution.py`, `tests/integration/test_ipam_api.py`) and updated existing nav/design/fake UI coverage.

### Added — HT-022 networks/vlans/subnets end-to-end delivery

- Added first-class network inventory support across backend layers: `Network` + `DeviceNetwork` models, pure validation domain (`src/domain/networks.py`), repository and service orchestration, Alembic migration `024_create_networks_and_device_networks.py`, and router wiring for `/api/networks` plus `/api/devices/{id}/networks` membership endpoints.
- Extended enriched device reads with `include=networks` and batched network membership hydration in `src/services/device_enrichment_service.py` and related API contracts.
- Extended import/export schema and flows to include `networks` and `device_networks` while preserving backward compatibility for legacy payloads.
- Added Settings network management UX: new page `src/ui/pages/settings_networks.py`, reusable modal `src/ui/components/network_modal.py`, sidebar navigation entry, and app registration.
- Added topology network filtering UX: network summaries loader, network filter panel (`src/ui/components/topology_network_panel.py`), and canvas overlay/highlight bridge (`src/ui/components/canvas_network_overlay.py`) with matching Cytoscape style classes.
- Added device detail network membership management section with attach/detach controls in `src/ui/components/device_detail_networks_section.py` and panel integration.
- Hid deprecated `DeviceType.VLAN`/`DeviceType.Subnet` from creation affordances while preserving edit compatibility for legacy records via `src/ui/components/device_type_options.py` and consumers in palette/help/editor surfaces.
- Added/updated focused coverage in `tests/integration/test_networks_api.py`, `tests/integration/test_export.py`, `tests/integration/test_import.py`, `tests/unit/test_networks_domain.py`, `tests/unit/test_network_service.py`, `tests/unit/test_topology_data.py`, `tests/unit/test_inventory_helpers.py`, `tests/unit/test_settings_pages_execution.py`, `tests/unit/test_canvas_network_overlay.py`, `tests/unit/test_canvas_zoom.py`, and `tests/unit/test_device_type_options.py`.

### Fixed — HT-022 review remediation pass

- Topology network highlighting now supports multi-select active network sets in `src/ui/components/topology_network_panel.py` and overlays stacked per-node network indicators through the upgraded bridge in `src/ui/components/canvas_network_overlay.py` plus overlay container wiring in `src/ui/components/canvas.py`.
- Network PATCH now rejects nulls for required fields (`name`, `cidr`, `color`) with HTTP 400 and maps non-unique integrity errors to non-conflict responses in `src/services/network_service.py`.
- Integration test stability improved by removing hardcoded network-name collisions in `tests/integration/test_networks_api.py` and `tests/integration/test_export.py`.
- File-size violations resolved by splitting import row writes into `src/services/import_service_rows.py`, moving topology network summary fetching to `src/ui/services/topology_network_summaries.py`, and trimming `src/ui/pages/inventory.py`.
- Import pre-write validation now enforces standalone network semantic validity (VLAN/CIDR/gateway) via `src/services/import_validation.py` and `src/services/import_service.py`.
- Network chip text now uses theme tokenized on-accent color instead of hardcoded white in `src/ui/components/device_detail_networks_section.py` and `src/ui/pages/inventory_table.py`.

### Fixed — HT-063 canvas initialization robustness and layout restoration

- Canvas init now waits for two stable `requestAnimationFrame` size checks before creating Cytoscape, avoiding early init against still-settling grid/flex container dimensions.
- First-load topologies now run a COSE distribution path when no saved node positions exist, while saved layouts use persisted `_positioned` metadata instead of `(0,0)` heuristics so nodes intentionally anchored at the origin stay in place.
- Saved pan/zoom is now preserved when only newly added nodes need placement; unpositioned nodes move into a right-side overflow column and `cy.fit()` runs only when no saved viewport exists.
- Collapsed container styling now replays in a dedicated recovery pass even if layout initialization falls back after an error.
- Saved layout payloads now prune orphaned `draft-*` nodes and draft edges before canvas init and silently persist the cleaned layout back through the diagram PATCH path without surfacing a toast.
- Added focused HT-063 regressions in `tests/unit/test_ui_canvas.py`, `tests/unit/test_topology_data.py`, and `tests/unit/test_topology_data_helpers.py`.

### Fixed — HT-062 topology toggle and interaction hardening

- The topology Edit / Stop Editing toggle now locks while the draft-confirmation dialog is open, applies a visible disabled state, ignores stacked clicks, and resumes normal behavior after the dialog closes.
- Topology page entry and page teardown now reset the client-side `_htEventsWired` guard so edit-mode event wiring is re-established exactly once after revisiting the page.
- Draft-node hover tooltips now skip `/api/devices/draft-*` fetches and render the static copy `Unpublished draft — publish to save` instead.
- Node tap handling is now consolidated through a single canvas interaction path while preserving shift-tap association flow in edit mode.
- Desktop right-click handling now uses a short-lived flag bridge to deduplicate back-to-back `cxttap` and native `contextmenu` events, preventing duplicate context-menu opens.

### Fixed — HT-060 safe container unconvert and reparent coordination

- Published topology nodes now carry `version` end-to-end from initial load, stencil placement, duplicate, and draft publish so client-side optimistic writes stay aligned with the existing device PATCH contract.
- The canvas drop dispatcher now forwards `inventoryDeviceVersion` into `ht:stencil-drop` as `deviceVersion`, preserving optimistic-lock metadata for published stencil placements.
- Container reparent now uses node-data-first optimistic locking with up to three PATCH attempts, refreshes on 409 only, keeps draft-node reparent layout-local, and snaps failed published drags back to their origin with the RFC toast copy.
- Convert-to-node now previews direct and nested removals using RFC copy, blocks while the View is unsaved or autosave is in flight, patches the diagram layout before mutating Cytoscape, refreshes the stencil panel after success, and avoids scheduling a second autosave for the already-persisted mutation.

### Fixed — HT-059 draft publish atomic rollback and ID safety

- Guarded `window._htDraftId` at both definition and palette-drop use so draft nodes always get a `draft-...` ID even if script load order varies.
- Draft publish now snapshots the pre-publish graph, verifies node and edge `cy.add()` collection lengths during replacement, and rolls back to the original draft node plus connected edges when verified replacement fails.
- If rollback cannot fully restore the draft snapshot, the canvas now raises a persistent reload banner with corruption guidance instead of failing silently.
- Publish API failures now keep the draft node and connected edges in place and leave the draft visibly marked with `draft-error` alongside a persistent retry/reload notification.
- Draft-edge promotion now treats `draft-edge-...` IDs as local draft edges and skips duplicate promotion when an equivalent persisted connection is already present on the canvas.
- Draft publish now waits for async edge promotion to settle before forcing the final autosave flush, and prunes stale local draft duplicates after promotion so 409/non-OK duplicate responses converge to a single persisted edge without further user input.
- Added focused HT-059 regressions in `tests/unit/test_canvas_draft.py` and `tests/unit/test_ui_canvas.py`.

### Fixed — HT-058 autosave conflict visibility and serialization

- Centralized topology autosave scheduling behind a shared `window.scheduleAutosave(...)` helper so canvas drag, draft edits, remove-from-view, container collapse/unconvert, and stencil placement no longer hand-roll competing `_htAutosaveTimer` state.
- `src/ui/components/canvas_js_utils.py` now serializes autosave PATCH requests with one in-flight operation at a time, queues one pending flush while a save is active, and retries transient failures with exponential backoff before surfacing an actionable warning toast.
- Autosave conflicts now raise a persistent reload prompt with the story copy `Your layout was modified elsewhere — reload to sync` and suspend further autosaves until reload.
- Oversized pending autosaves now trigger the standard browser unload confirmation instead of silently relying on `keepalive` during tab close.
- Normal autosave PATCH requests no longer force `keepalive`; unload-safe delivery now uses a dedicated final-send path while retry backoff tracks actual request activity so closing the tab does not create a silent loss window.
- Split the injected canvas JS into dedicated autosave and interaction helper modules so `src/ui/components/canvas_js.py` and `src/ui/components/canvas_js_utils.py` both remain within the 250-line cap without changing the accepted HT-058 scheduler/serialization approach.
- Added focused HT-058 regressions in `tests/unit/test_ui_canvas.py` and `tests/unit/test_stencils_panel.py` covering the shared scheduler, serialized flush queue, conflict/failure notices, retry hooks, and unload guard path.

### Fixed — HT-061 inventory delete action and mobile drawer accessibility

- Inventory row delete actions now emit a direct in-page `inventory_delete` event from the table slot so the confirmation dialog opens reliably without query-string navigation; the dialog still loads placement counts before delete confirmation.
- The mobile navigation drawer now starts closed at narrow widths and exposes an explicit header menu opener so the backdrop no longer blocks inventory interactions on load while remaining dismissible after intentional open.
- Added regression coverage in `tests/unit/test_inventory_helpers.py`, `tests/unit/test_inventory_page_execution.py`, `tests/unit/test_ui_navigation_components.py`, and the focused Playwright proof script `tests/e2e/test_bug_inv_001_clickpath.py`.

### Fixed — HT-064 endpoint hardening and tactical security regressions

- `src/api/routers/health.py` now keeps `/api/health` public for liveness probes while only returning `version`, database state, and uptime to callers with a currently valid DB-backed token (cookie first, Bearer fallback, stale/inactive tokens downgraded to the public body).
- `src/api/routers/system.py` now limits `db_version` and `db_size_bytes` to Admin responses while Reader and Contributor callers continue to receive inventory counts.
- `src/api/routers/data_transfer.py` now rate-limits `GET /api/export` to `3/minute` and `POST /api/import` to `1/minute` using the existing slowapi limiter; the generic import integrity-error response remains unchanged.
- Added HT-064 regressions in `tests/integration/test_health.py`, `tests/integration/test_system_stats.py`, `tests/integration/test_export.py`, `tests/integration/test_import.py`, and `tests/unit/test_ui_canvas.py`, including proof that the edge-delete prompt still escapes raw labels.

### Fixed — JWT stale-privilege persistence after role/deactivation changes

- `src/api/middleware/auth.py` now derives `request.state.role` from the DB-backed `User` record (not the JWT role claim) and rejects inactive users from DB state.
- `src/services/user_service.py` now increments `token_version` in `update_user(...)` when `role` or `is_active` actually changes, invalidating previously issued JWTs after demotion/deactivation.
- Added middleware regressions in `tests/unit/test_auth_middleware.py` for DB-role authority over stale claims and inactive-user rejection with matching token version.
- Rewrote stale-claim-dependent HTTP coverage in `tests/integration/test_users.py` to assert old Admin tokens lose authority after demotion and deactivation.
- Added service-layer regressions in `tests/unit/test_user_service.py` for token-version bump/no-bump behavior and explicit last-admin business-rule coverage.

### Fixed — HT-067 import/export topology snapshot parity

- `src/models/export_schema.py` now carries `workspaces`, `topologies`, and `ExportedDiagramLayout.topology_id/version` in the backup wire format (with backward-compatible defaults for legacy payloads).
- `src/services/export_service.py` now exports workspace/topology container records and preserves diagram `topology_id` + `version` fields.
- `src/services/import_service.py` now restores `workspaces` then `topologies` before `diagram_layouts`, preventing topology-bound layout imports from failing with integrity errors.
- Added repository export helpers in `src/repositories/workspace_repository.py` and `src/repositories/topology_repository.py`.
- Extended integration coverage in `tests/integration/test_import.py` and `tests/integration/test_export.py` to lock the new snapshot shape and topology-scoped round-trip behavior.

### Fixed — HT-067 topology bridge singleton safety on revisit

- Added a window-scoped init guard to `CONTEXT_MENU_JS` in `src/ui/components/canvas_context_menu.py` so topology page revisits do not register duplicate document listeners for `ht:context-menu-request` and `mousemove`.
- Added JS-string regression coverage in `tests/unit/test_topology_bridge_guards.py` for the context-menu, device-detail, and connection-detail bridge singleton guards.

### Added — HT-066 router non-starvation regression proof

- Added an integration regression in `tests/integration/test_health.py` that holds `GET /api/devices/` open inside a patched synchronous service call and proves `GET /api/health` still completes through the ASGI app before the slow router request is released.

### Fixed — Diagram read ownership scope hardening (HT-053 blocker)

- `GET /api/diagrams/` and `GET /api/diagrams/{id}` now enforce owner-scoped reads through the topology→workspace ownership chain for topology-backed layouts.
- Diagram read endpoints now pass caller `owner_id` into service methods; repository owner-scoped read queries were added for list/get and topology-filtered list paths.
- Added integration coverage for cross-user isolation so one contributor cannot list or fetch another contributor's topology-backed diagrams.

### Fixed — QA Remediation: bug-report-13-04-26.1 (11 tactical fixes)

- **BUG-003**: Auth middleware now defensively parses JWT `version` claim instead of raw `int()` cast — returns 401 on malformed claims (was 500).
- **BUG-004**: Import endpoint no longer leaks DB IntegrityError internals (`exc.orig`) to clients or logs raw exception — returns generic "data integrity violation" message.
- **BUG-006**: `ConnectionUpdate` now validates self-loop (`source_id == target_id`) — consistent with `ConnectionBase`.
- **BUG-008**: Canvas autosave now handles non-OK fetch responses: logs 409 conflicts, dispatches `ht:autosave-conflict` event, and includes `.catch()` for network errors.
- **BUG-009**: `LocationUpdate.name` now enforces `min_length=1` and rejects whitespace-only strings — consistent with `LocationBase`.
- **BUG-010**: `ConnectionUpdate.label` now enforces `max_length=255` — consistent with `ConnectionBase`.
- **BUG-012**: `create_user()` no longer logs email in cleartext — logs `user_id` instead.
- **BUG-014**: Context menu deduplication guard prevents double `ht:context-menu-request` dispatch from concurrent `cxttap` + native `contextmenu` handlers.
- **BUG-015**: `validate_ip()` now strips whitespace before validation.
- **BUG-016**: `validate_mac()` now strips whitespace before validation.
- **BUG-017**: Removed dead `ht:node-context` custom event dispatch (zero consumers).

### Fixed — Topology canvas context menu and association reliability

- Added a native `contextmenu` fallback handler in `src/ui/components/canvas_js.py` so right-click context actions still open even when Cytoscape `cxttap` is not emitted by the browser/platform input path.
- Association flow in edit mode now reliably starts from right-click menu usage because the custom context menu is consistently dispatched.
- Updated draft-node visual style in `src/ui/components/canvas_styles.py` to avoid the blurred look on newly added items (`opacity: 1`, clearer draft label text, larger draft font size).
- Added regression assertions in `tests/unit/test_canvas_js_view_mode.py` and `tests/unit/test_design_system.py`.

### Fixed — DeviceUpdate empty name validation gap (BUG-01 / bug-report-12-04-26.1)

- **Root cause**: `DeviceUpdate.name` was `Optional[str] = Field(max_length=255)` with no `min_length=1` and no `validate_name` validator. `PATCH /api/devices/{id}` with `{"name": ""}` wrote an empty string to the DB, causing `GET /api/devices/` to crash with HTTP 500 (Pydantic `ValidationError` in response serialization — silently swallowed by `BaseHTTPMiddleware`).
- **Fix**: Added `min_length=1` to the `DeviceUpdate.name` field and added a `validate_name` validator that rejects empty/whitespace-only strings. Consistent with the equivalent validator in `DeviceBase`.
- **File changed**: `src/models/device.py`
- **Tests**: 1228 passing, 0 failures (existing `test_devices_validation.py` suite covers the fixed path).

### Fixed — Canvas Shortcuts Ctrl+A / Escape (BUG-001)

- **Root cause**: `cy.autounselectify(true)` in `canvas_js.py` init and `VIEW_MODE_JS` globally locked all nodes to `selectable: false`, causing `nodes().select()` and `nodes().unselect()` to silently no-op in both view and edit mode after any deselect interaction.
- **Fix**: Removed `autounselectify(true)` from canvas init and `VIEW_MODE_JS`. View mode continues to prevent drag edits via `autoungrabify(true)` and disables box selection via `boxSelectionEnabled(false)`. Write shortcuts remain blocked by `HT_READONLY`. Nodes are now interactively selectable in view mode (showing selection halos on click), which is correct UX for inspecting the topology.
- **Tests**: Updated `tests/unit/test_canvas_js_view_mode.py` and `tests/unit/test_canvas_mode.py` to assert `autounselectify(true)` is intentionally absent, preventing regression.
- **E2E test fixes**: Fixed `tests/e2e/test_deep_hunt.py` `api()` helper to handle 204 No Content responses; fixed `tests/e2e/test_stories_e2e.py` edge field name from `conn_type` to `connection_type`.

### Added — Inventory Stencils Panel (HT-049)

- **Stencils panel**: Collapsible "Inventory" panel in edit mode showing all published devices. Sits alongside the device type palette in the left sidebar.
- **Search & filter**: Case-insensitive name search and DeviceType dropdown filter for quick device lookup.
- **Drag-to-canvas**: Drag a published device from the stencil panel onto the Cytoscape canvas to place it. Creates a real (non-draft) node with correct shape/styling and triggers autosave.
- **Placed indicator**: Already-placed devices are greyed out with a "Placed" badge and cannot be re-dragged. Removing a device from the canvas re-enables it in the stencil list.
- **Virtual scrolling**: IntersectionObserver-based batch rendering for inventories with 100+ devices.
- **Collapse toggle**: Panel header toggle to collapse the stencil panel to a 36px bar, freeing canvas width.
- **Live state sync**: `ht:stencil-placed` and `ht:stencil-refresh` events keep panel placed-state in sync with canvas operations (including "Remove from View").

### Added — Un-container (HT-046)

- **Context menu**: "Convert to Node" option appears on container nodes; "Convert to Container" and "Collapse/Expand" are now hidden for non-container nodes.
- **Un-convert handler**: `ht:node-unconvert-container` event in `canvas_container_events.py` removes all descendant nodes and their connected edges from the canvas, strips container styling, and triggers autosave. Shows a confirmation dialog when children exist; converts silently when empty.

### Added — Device Containers Remaining (HT-021)

- **Service enrichment**: `?include=children` and `?include=ancestors` now populate `children` and `parent_chain` fields on single-device enriched responses.
- **Export schema**: `ExportedDevice` includes `parent_id` field; exports now capture parent-child relationships.
- **Import service**: Added `_validate_device_parent_refs()` validation; devices are topologically sorted before insertion so parents are created before children; `parent_id` is passed through in the `Device()` constructor.
- **Domain**: Added `topological_sort_devices()` (Kahn's algorithm) to `src/domain/export.py` with cycle detection.

### Fixed — Code-Reviewer Findings (12-04-26)

- **File size (import_service.py)**: Extracted `validate_device_location_refs()`, `validate_device_parent_refs()`, and `ImportPayloadValidationError` from `src/services/import_service.py` (251→222 lines) into new `src/services/import_validation.py`. Updated all imports in `data_transfer.py` router and unit tests.
- **Regression test**: Added `TestIncludeLocationWithSort` in `tests/integration/test_devices_include.py` — verifies `?include=location&sort=name` and `?include=location&sort=-name` produce correctly ordered enriched responses.

### Fixed — Code-Reviewer Findings (Bug Report 11-04-26.1 Remediation)

- **Domain purity (F1)**: Moved `require_role()` from `src/domain/rbac.py` to `src/api/dependencies/rbac.py`; domain layer now contains only pure `ROLE_HIERARCHY` and `can_perform()` with zero FastAPI/logging imports. Updated all 11 router imports and test imports.
- **File size (F2)**: Extracted dialog UI definitions from `src/ui/components/topology_layout_bar.py` (261→240 lines) into `src/ui/components/topology_layout_dialogs.py`.
- **Autosave test coverage (F3)**: Added `TestCanvasAutosaveTemplate` class in `tests/unit/test_ui_canvas.py` — verifies `_htFlushAutosave` definition, dragfree debounce timer, `beforeunload` listener, and `keepalive: true` in fetch.

### Fixed — Autosave Drag Positions (BUG-1101-03)

- `src/ui/components/canvas_js.py` — added debounced autosave (800ms) on `dragfree` events: positions are persisted to the server via `PATCH /api/diagrams/{id}` without requiring manual Save Layout. Added `beforeunload` handler to flush pending saves on tab close. Autosave is gated behind `!window.HT_READONLY` and only fires when a layout is selected.
- `src/ui/components/topology_layout_bar.py` — synced diagram ID and version to JS globals (`window._htDiagramId`, `window._htDiagramVersion`) on layout select/save/rename/delete; manual Save and Rename now read the latest version from JS to avoid conflicts with autosave.

### Fixed — Canvas JS Bugs (BUG-1101-08, BUG-1101-26)

- `src/ui/components/canvas_js.py` — gated the `cy.on('tap', 'node', ...)` handler behind `window.HT_READONLY` so it only dispatches `ht:node-selected` for read-only users; write-mode tap is now handled exclusively in `canvas_events.py` (BUG-1101-08: eliminates duplicate-handler double-fire).
- `src/ui/components/canvas_events.py` — extended the write-mode `cy.on('tap', 'node', ...)` handler to dispatch `ht:node-selected` on normal clicks (no edge source, no shift), making it the single canonical handler for write sessions; also guarded the node-delete success path with an `el.length > 0` check before calling `.remove()`, logging a console warning when the element is absent (BUG-1101-26).

### Fixed — QA Remediation (Bug Report 11-04-26.1)

- `src/services/system_service.py` (new), `src/api/routers/system.py`, `src/api/routers/health.py`, `tests/unit/test_system_service.py` (new) — extracted all direct SQL from `system.py` and `health.py` routers into `system_service.py` (BUG-14, BUG-24): `get_entity_counts()`, `get_user_count()`, `get_db_diagnostics()`, `check_db_connectivity()`. Routers now delegate to service layer with zero inline queries.

- `src/models/export_schema.py`, `src/services/export_service.py`, `src/services/import_service.py`, `src/api/routers/data_transfer.py`, `tests/integration/test_import.py` — restored full services export/import round-trip by adding `ExportedService` and `ExportedServiceDependency` wire models, including `services` and `service_dependencies` in export assembly, importing services/dependencies in FK-safe order, extending table clearing to include `service_dependencies` + `services`, and adding pre-validation that each `device.location_id` exists in payload locations (422 on dangling references).
- `src/repositories/diagram_repository.py`, `src/services/diagram_service.py`, `tests/unit/test_diagram_service.py` — hardened diagram writes against race conditions by locking target rows with `SELECT ... FOR UPDATE` in `update()`, `partial_update()`, `delete()`, and `update_timestamp()`, and added `IntegrityError` handling (`rollback` + HTTP 409) for diagram create/update/write commits with regression tests for stale-version conflicts and rollback behavior.
- `src/services/device_service.py`, `src/services/connection_service.py`, `src/services/location_service.py`, `src/services/service_service.py`, `tests/unit/test_write_service_integrity_handling.py`, `tests/unit/test_service_service.py` — added missing commit guards (`try/except IntegrityError`) with explicit `session.rollback()` on update/create write paths, mapped unmapped integrity failures to clean `HTTPException(500, "Internal database error")`, and changed dependency removal to return 404 for missing edges while logging successful removal only when a row is actually deleted.
- `src/domain/rbac.py`, `src/services/auth_service.py`, `tests/unit/test_domain_rbac.py` — fixed invalid JWT role-claim coercion to deny with HTTP 403 (instead of bubbling enum `ValueError` as 500), added warning telemetry for invalid role claims with optional `user_id`, and removed email addresses from authentication WARNING/INFO logs (failed login, disabled account login, first-boot admin seed).
- `src/models/connection.py`, `alembic/versions/019_add_connection_self_loop_check.py`, `src/models/device.py`, `src/models/user.py`, `src/models/location.py`, `tests/integration/test_connections_validation.py`, `tests/integration/test_devices_validation.py`, `tests/integration/test_users.py`, `tests/integration/test_locations.py` — closed validation gaps by enforcing connection no-self-loop at Pydantic + DB layers, adding `DeviceUpdate.ip` validator parity, adding username/email validators for user create/update models, rejecting punctuation-only location rows, and normalizing whitespace-only location racks to `None`.

### Fixed — Code-Reviewer Findings (SEC-1.1 / SEC-4.4 follow-up)

- **Auth transport mismatch (F1)**: `LoginResponse` now includes `access_token` in the JSON body alongside the HttpOnly cookie. Login page JS passes the token to Python; `app.storage.user` stores it server-side for NiceGUI httpx calls. Removed `window._htToken` XSS vector from `settings_data.py`; export fetch uses `credentials: 'include'` instead.
- **Password change atomicity (F2)**: `change_own_password()` in `auth_service.py` now performs `update` + `increment_token_version` in a single `session.commit()` call.
- **Secret defaults fail-closed (F3)**: Placeholder SECRET_KEY/ADMIN_PASSWORD now raise `ValueError` by default. `DEV_MODE=true` env var opts into warn-only behavior for local development.
- **cookie_secure default (F4)**: `cookie_secure` defaults to `True` (production-safe). Local dev requires `COOKIE_SECURE=false` in `.env`.
- **File length (F5)**: Extracted JS helpers from `canvas_events.py` (283→190 lines) into `canvas_js_helpers.py`. Inlined `_get_layouts` wrapper in `topology_layout_bar.py` (253→248 lines).

### Added — SEC-1.1 / SEC-4.4: JWT Revocation & HttpOnly Cookie Auth

- `alembic/versions/018_add_user_token_version.py` — migration adds `token_version INTEGER NOT NULL DEFAULT 1` to `users` table.
- `src/models/user.py` — `token_version: int = Field(default=1)` added to `User`.
- `src/utils/settings.py` — `cookie_secure: bool = False` setting added for HTTPS deployments.
- `src/repositories/user_repository.py` — `increment_token_version(session, user_id)` atomically increments `token_version`, invalidating all prior JWTs for that user.
- `src/services/auth_service.py` — `authenticate` now returns `tuple[str, int, str]` (token, expiry_unix, role); `change_own_password` calls `increment_token_version` post-commit; new `revoke_tokens(user_id, session)` helper.
- `src/utils/auth.py` — `create_jwt` auto-appends `jti` (UUID4) and `iat`; `decode_jwt` validates all 5 required claims: `sub`, `role`, `jti`, `iat`, `version`.
- `src/api/middleware/auth.py` — Cookie-first token extraction (`ht_access_token`), Bearer header fallback; DB version check on every request; rejects revoked tokens with 401.
- `src/api/routers/auth.py` — Login sets HttpOnly `ht_access_token` cookie (path=`/api`, samesite=strict); logout revokes token version + deletes cookie; `LoginResponse` schema replaces bare `access_token` body.
- `src/ui/pages/login.py` — Removed `sessionStorage.setItem('access_token')`; fetch now uses `credentials: 'include'`; stores `role`, `user_id`, `token_exp` in NiceGUI storage.
- `src/ui/components/auth_guard.py` — Removed `decode_jwt` dependency; reads `role` and `token_exp` from NiceGUI storage for UI-side auth gate.
- `src/ui/components/canvas_events.py` — All 5 Cytoscape event fetch calls migrated from sessionStorage Bearer header to `credentials: 'include'`.
- `src/ui/components/canvas_tooltip.py` — Tooltip fetch migrated from sessionStorage Bearer header to `credentials: 'include'`.
- `tests/unit/test_jwt_revocation.py` — 20 new unit tests covering token creation, claim validation, version increment, revocation, and password-change invalidation.
- `tests/integration/test_jwt_revocation_integration.py` — 13 new integration tests covering login cookie flow, versioned revocation, Bearer fallback, and logout.

### Changed — test infrastructure

- `tests/conftest.py` — New `admin_user` fixture returns the backing `User` object; `admin_token` now depends on `admin_user`. Middleware engine patching (`_auth_mw.engine = test_engine`) added to `client` fixture. All token fixtures (`admin_token`, `contributor_token`, `reader_token`) backed by real DB users with `version` in JWT payload.
- `tests/integration/test_auth.py` — `TestLogin` now asserts `LoginResponse` fields (`user_id`, `role`, `token_exp`, `token_type`) and the `ht_access_token` cookie.
- `tests/integration/test_change_password.py` — `pw_token` fixture includes `version` claim.
- `tests/integration/test_import.py` — `test_preserves_original_uuids` and `test_replaces_all_existing_data` include `admin_user` in import payload so the backing user survives truncation; added `_user_as_payload(user)` helper.
- `tests/integration/test_users.py` — `_token_for()` includes `version` claim; `test_last_admin_delete_returns_400` downgrades `other_admin` to Reader in DB after minting its JWT so exactly one admin remains in the count.
- `tests/unit/test_auth_guard.py` — Storage mock keys updated from `access_token` to `role`/`token_exp`.

### Added — HT-027 Phase 1: Theme Engine Core

- `src/ui/design/tokens.py` — Added `THEMES` dict with three palettes: `dark` ("Control Room"), `light` ("Blueprint"), `midnight` ("Cyberdeck"). Added `STATIC_CSS_VARS` dict with structural tokens (`--ht-radius-*`, `--ht-transition-*`, `--ht-font-*`). All existing `COLOR_*` constants preserved as backward-compatible aliases pointing to dark theme values.
- `src/ui/design/theme_engine.py` — New module. `build_css_var_dict(theme_name)` builds merged CSS var dict. `get_initial_theme_css(theme_name)` returns `<style id="ht-theme">` block for zero-FOUC server-side injection. `get_theme_js_helpers()` returns idempotent `<script>` block defining `window.htApplyThemeVars` and `window._htThemeColors`. `apply_theme_to_client(theme_name)` pushes CSS var updates to the browser without page reload.
- `src/ui/components/canvas_styles.py` — Added `build_theme_style_json(theme_name)` that constructs a Cytoscape style array from theme palette values. `CANVAS_STYLE_JS` preserved as backward-compatible alias (dark theme).
- `src/ui/components/canvas.py` — Added `window.updateCyTheme(stylesJson)` JS global for runtime canvas theme switching. Canvas background now uses `var(--ht-bg-base)` CSS var. `render_canvas()` reads session theme and passes themed styles to Cytoscape init.
- `src/ui/components/app_shell.py` — Injects `get_initial_theme_css()` and `get_theme_js_helpers()` on every authenticated page. Added theme switcher (Dark / Light / Midnight) to user dropdown menu. `_handle_theme_change()` persists theme to `app.storage.user['theme']`, pushes CSS vars via `apply_theme_to_client()`, and re-applies Cytoscape styles via `updateCyTheme`. All `COLOR_*` f-string expressions replaced with `var(--ht-*)` CSS custom properties. Header height changed to 48px per spec. Session-expiry overlay reads colours from CSS vars at overlay construction time. Added `_GLOBAL_CSS` with font-family baseline, fade-in animation, and nav-item hover rule.
- `src/ui/pages/login.py` — Injects dark theme CSS vars and font links. Body and card styles use `var(--ht-*)` references.
- `tests/unit/test_design_system.py` — 67 unit tests covering all new theme engine functionality.
- `src/ui/components/canvas_js.py` — New module extracted from canvas.py. Contains Cytoscape initialization JS template.
- `src/ui/components/sidebar.py` — New module extracted from app_shell.py. Contains sidebar navigation items, render functions, and toggle logic.

### Changed — HT-027 Phase 2: CSP Compliance & Refactoring

- `src/ui/design/theme_engine.py` — Removed external Google Fonts link injection. Theme engine now produces CSS-only output compatible with strict CSP.
- `src/ui/design/tokens.py` — Font CSS vars (`--ht-font-body`, `--ht-font-mono`) now use system font stacks with graceful fallbacks instead of requiring external font loading.
- `src/ui/components/canvas.py` — Reduced from 265 to 61 lines; JS template extracted to `canvas_js.py`.
- `src/ui/components/app_shell.py` — Reduced from 299 to 202 lines; sidebar extracted to `sidebar.py`.
- `tests/unit/test_design_system.py` — Added CSP regression test (`test_no_external_font_links`) and system font stack validation.
- `pytest.ini` — Added `--ignore=tests/e2e` to default pytest run (Playwright not available in Docker container).

### Fixed

- `src/models/diagram.py`, `src/api/routers/diagrams.py`, `src/services/diagram_service.py`, `src/ui/components/topology_layout_bar.py`, `tests/integration/test_diagrams_patch.py`, `tests/integration/test_diagrams.py` — made diagram write preconditions explicit: `DiagramLayoutUpdate.version` is required, `DiagramLayoutResponse` now includes `version`, PUT/PATCH enforce optimistic-lock checks on every write (missing version returns 422, stale version returns 409), and topology UI PATCH calls now send the current `version`.
- `src/models/device.py`, `src/services/device_service.py`, `src/ui/pages/device_edit.py`, `src/ui/components/inventory_edit_modal.py`, `src/ui/components/device_panel_helpers.py`, `src/ui/components/device_detail_panel.py`, `tests/integration/test_devices.py`, `tests/integration/test_devices_validation.py`, `tests/integration/test_device_status.py`, `tests/integration/test_rbac_coverage.py`, `tests/unit/test_device_status.py`, `tests/unit/test_device_detail_duplicate.py` — made device PATCH `version` mandatory, enforced unconditional version checks in service update flow, and updated UI/test callers to send version preconditions.
- `src/models/location.py`, `src/services/location_service.py`, `tests/integration/test_locations.py` — hardened location PATCH validation by rejecting negative/empty `row` values regardless of PATCH payload shape and validating effective rack row state before commit, preventing invalid row persistence on row-only PATCH requests.

- `src/models/device.py`, `src/services/device_service.py`, `tests/integration/test_devices.py`, `alembic/versions/013_add_device_version.py` — added device optimistic locking (`version` column + optional PATCH precondition); stale version updates now return HTTP 409.
- `src/models/diagram.py`, `src/services/diagram_service.py`, `tests/integration/test_diagrams.py`, `alembic/versions/014_add_diagram_version.py` — added diagram optimistic locking for PUT updates with HTTP 409 conflict on stale version.
- `src/models/connection.py`, `tests/unit/test_connection_cascade_delete.py`, `alembic/versions/015_add_cascade_to_connections.py` — enforced `ON DELETE CASCADE` on connection device FKs as defense-in-depth.
- `src/models/location.py`, `tests/unit/test_location_parent_name_uniqueness.py`, `alembic/versions/016_add_location_name_unique.py` — enforced location sibling-name uniqueness at DB/model level.
- `src/repositories/*.py` mutating methods + service-layer write paths — moved transaction ownership from repositories to services (`flush` in repositories, `commit` in services) to restore atomicity and fixture rollback isolation.
- `tests/unit/test_repository_transaction_atomicity.py` — added regression proving failed multi-step operations now roll back cleanly when an error occurs before commit.

- `src/services/import_service.py` — `_is_postgres()` now catches only `(AttributeError, TypeError)` so unexpected runtime DB errors propagate; import now validates each location via `LocationCreate` before insert so invalid geo bounds are rejected.
- `src/models/location.py` — added `row` validator: trims whitespace, rejects empty row strings, and rejects negative numeric rack rows.
- `src/services/user_service.py` + `src/cli.py` — added `reset_password_by_email(...)` service and refactored CLI reset-password to route through service layer instead of direct repository calls.
- `src/ui/components/canvas_js.py` — added `window._htThemeUpdating` guard in `updateCyTheme` to prevent re-entrant style application during rapid theme switching.
- Investigations closed: NiceGUI `app.storage.user` confirmed session-cookie keyed (no cross-user process bleed), and `src/services/device_service.py` logs confirmed to not include device IP values.

- Topology editing UX restored: node click now reliably opens the right-side device detail editor panel again, including inline property editing controls.
- Topology association discoverability improved: right-click context menu now exposes the `Start Association` action via the same event channel used by the canvas context menu overlay.
- Inventory editing flow redesigned: action column now opens a dedicated editor route at `/inventory/edit/{device_id}` with `Save Changes` and `Open in Topology` actions.
- Blank topology canvas: NiceGUI's `.nicegui-content` wrapper had `flex: 0 1 auto`, collapsing the `#cy` container to zero height. Added flex overrides in `app_shell.py` for `.q-page` and `.nicegui-content` to propagate height through the full layout chain.
- Inventory type/tag filter chips now respond to clicks — replaced `chip.on("click", ...)` with `ui.chip(on_click=...)` to integrate properly with Quasar QChip event handling
- Inventory table update uses direct `rows =` assignment plus `.update()` to trigger NiceGUI reactivity instead of in-place `rows[:] =` which bypassed the property setter
- Tag chip toggle in `inventory_helpers.py` migrated to same `on_click=` pattern for consistency
- Topology deep-link routing fixed: visiting `/topology?device_id={id}` now waits for Cytoscape initialization, selects the target node, centers the viewport, and dispatches `ht:node-selected` so the right-side detail panel opens automatically.
- Topology action callbacks now execute in active client context for connection and layout dialogs: save/rename/delete handlers no longer use detached task wrappers, preventing stale UI state after successful API updates.

### Changed — Topology UX Improvements

- Full-width canvas: removed left palette sidebar; topology canvas now spans full viewport width
- Zoom limits: Cytoscape.js canvas now clamps zoom between 0.1× and 5× (prevents infinite zoom)
- Type filter chips: floating overlay shows toggle chips for device types present in the current data; toggling hides/shows matching nodes on the canvas
- Node click behavior: clicking a device node opens the right-side detail/editor panel; Shift+click is reserved for association source selection
- Layout bar clarity: dropdown relabeled "Saved Layouts" with placeholder text; Save button relabeled "Save Layout"
- Removed NiceGUI version from About page
- Extracted canvas tooltip JS into `src/ui/components/canvas_tooltip.py` (canvas.py now 244 lines)

### Added — HT-026 App Shell + Dashboard + HT-038 Graceful Session Expiry

#### App Shell (HT-026)
- `src/ui/components/app_shell.py` — `app_shell(title, current_route, breadcrumb)` context manager: persistent `ui.header()` + `ui.left_drawer()`, sidebar nav with active-item highlight, collapsible drawer (preference persisted in session storage), Admin-only Users link, user-menu dropdown (Change Password + Logout). Also injects HT-038 session-expiry JS interceptor on every authenticated page.
- `src/ui/pages/dashboard.py` — new dashboard page at `/`; stat cards (devices, connections, locations, tags), Recent Activity (last 5 devices by `updated_at`), quick-action buttons; empty-state when no devices exist
- `src/repositories/device_repository.py` — `get_all()` gains `sort: str | None` parameter; valid sort keys: `name`, `-name`, `updated_at`, `-updated_at`, `created_at`, `-created_at`; invalid values silently fall back to default
- `src/services/device_service.py` — `get_all()` passes `sort` through to repository
- `src/api/routers/devices.py` — `GET /api/devices` gains `?sort=` query parameter
- `src/ui/pages/login.py` — redirect after login now goes to `/` (was `/topology`); HT-038 expired-session banner on `?expired=1`; `?next=` param validated server-side and used for post-login redirect; stores `username` (email) in session storage
- `src/main.py` — registers dashboard page

#### Page migrations (all authenticated pages now wrapped in `app_shell`)
- `src/ui/pages/topology.py` — wrapped in `app_shell`; removed per-page topbar and `_logout` function
- `src/ui/pages/inventory.py` — wrapped in `app_shell`
- `src/ui/pages/settings_locations.py` — wrapped in `app_shell`
- `src/ui/pages/settings_users.py` — wrapped in `app_shell`
- `src/ui/pages/settings_data.py` — wrapped in `app_shell`
- `src/ui/pages/settings_profile.py` — wrapped in `app_shell`
- `src/ui/pages/settings_about.py` — wrapped in `app_shell`

#### Session expiry (HT-038)
- `src/ui/components/auth_guard.py` — `safe_next_path(path) -> str | None` validates redirect paths against open-redirect; `redirect_if_unauthenticated(current_path=None)` distinguishes expired-token from absent-token, adds `?expired=1&next=` when applicable
- Session-expiry fetch interceptor (in `app_shell.py`) wraps `window.fetch`, detects 401 from `/api/*`, shows full-screen "Your session has expired" overlay with Sign In button, deduplicates overlays, redirects with `?expired=1&next={pathname}`

#### Tests
- `tests/unit/test_auth_guard.py` — unit tests for `safe_next_path` (9 cases) and `redirect_if_unauthenticated` (6 cases)
- `tests/unit/test_app_shell.py` — unit tests for session-expiry JS content (9 checks) and nav/settings item structure (6 checks)
- `tests/integration/test_devices_sort.py` — integration tests for all sort key variants + invalid fallback + backward compat (9 tests)

### Added — HT-023 Services (name, port, URL, protocol, status per device)
- `src/models/types.py` — `ServiceProtocol` enum (`http`, `https`, `tcp`, `udp`, `other`) and `ServiceStatus` enum (`running`, `stopped`, `unknown`)
- `src/models/service.py` — `Service` + `ServiceDependency` SQLModel tables; `ServiceCreate`, `ServiceUpdate`, `ServiceResponse` schemas
- `alembic/versions/012_create_services_and_dependencies.py` — creates `services` table (FK to devices, unique index on `device_id, LOWER(name)`) and `service_dependencies` table (composite PK, CHECK self-dependency guard)
- `src/domain/services.py` — pure functions: `validate_port(port)` (1–65535), `validate_no_dependency_cycle(service_id, depends_on_id, existing_edges)` (BFS cycle detection)
- `src/repositories/service_repository.py` — full CRUD + dependency edge queries + batch `get_by_device_ids()`
- `src/services/service_service.py` — orchestrates CRUD, port validation, name uniqueness (409), cycle detection (400), IntegrityError handling
- `src/api/routers/services.py` — `GET /api/services`, `GET/PATCH/DELETE /api/services/{id}`, dependency sub-routes `POST /api/services/{id}/dependencies`, `DELETE /api/services/{id}/dependencies/{dep_id}`
- `src/api/routers/device_sub_routes.py` — added `POST /api/devices/{id}/services` and `GET /api/devices/{id}/services`
- `src/models/device.py` — `DeviceResponseEnriched` gains optional `services` field; `?include=services` supported
- `src/ui/components/canvas.py` — Cytoscape node hover tooltip shows service names + status dots (green/red/grey)
- `src/ui/pages/inventory_helpers.py` — Services count column in inventory table
- Tests: `tests/unit/test_domain_services.py`, `tests/integration/test_services_api.py`, `tests/integration/test_service_dependencies.py`

### Added — HT-020 Search and Filter Inventory
- `src/domain/search.py` — `parse_query(raw) -> ParsedQuery` structured search parser; operators: `type:`, `ip:`, `tag:`, `os:`, `location:`, `status:`, `service:`; `to_sql_like(glob)` converts `*` to SQL `%` with proper escaping; unknown operators fall through to free text
- `src/repositories/device_repository.py` — `search(session, parsed, page, limit)` builds dynamic SQLAlchemy filters from `ParsedQuery`; supports JOIN for tag/service/location operators; wildcard via `ILIKE` with escape char
- `src/api/routers/devices.py` — `GET /api/devices` gains `?q=` query parameter for structured search
- `src/ui/pages/inventory.py` — search bar now submits `q` parameter to API for server-side filtering
- Tests: `tests/unit/test_domain_search.py`, `tests/integration/test_device_search.py`

### Added — HT-025 Self-Service Password Change + First-Boot Credential Hardening
- `src/domain/auth.py` — pure function `validate_password_strength(password) -> None`; raises `ValueError` if len < 8
- `src/services/auth_service.py` — `change_own_password(user_id, current, new, session)` service function; else-branch in `create_first_admin_if_needed` logs warning when `ADMIN_PASSWORD` is set in `.env` after first boot
- `src/api/routers/auth.py` — `PATCH /api/auth/me/password` (requires auth, body `{current_password, new_password}`, returns 204)
- `src/ui/pages/settings_profile.py` — password-change form page at `/settings/profile`
- `src/cli.py` — refactored to use `validate_password_strength` (eliminates duplication)
- `src/services/user_service.py` — refactored `create_user` and `update_user` to call `validate_password_strength`
- `.env.example` — added clarifying comment on `ADMIN_PASSWORD` line
- `tests/unit/test_domain_auth.py`, `tests/unit/test_auth_service_change_password.py`, `tests/integration/test_change_password.py`

### Added — HT-035 About / System Info Page
- `src/api/routers/system.py` — `GET /api/system/stats`; returns inventory counts + DB diagnostics; user count Admin-only
- `src/api/app.py` — registers `system_router`
- `src/ui/pages/settings_about.py` — system info page at `/settings/about`: Application, Runtime, Database, Inventory Summary
- `tests/integration/test_system_stats.py`

### Added — HT-040 Canvas Zoom & Fit Controls
- `src/ui/components/canvas_zoom.py` — `inject_zoom_controls()` injects floating +/−/⊡ button group into canvas container via JS; Cytoscape `cy.zoom()` and `cy.fit(undefined, 40)` wired via `window._cy`
- `src/ui/pages/topology.py` — calls `inject_zoom_controls()` after `render_canvas()`
- `tests/unit/test_canvas_zoom.py`

### Added — HT-041 Device Duplication (Clone)
- `src/domain/devices.py` — `generate_copy_name(original_name, existing_names) -> str`: pure collision-aware name generator
- `src/repositories/device_repository.py` — `get_all_names(session) -> list[str]`
- `src/ui/components/device_detail_duplicate.py` — `duplicate_device(token, device)` helper: fetches names, generates copy name, POSTs new device, copies tags and custom fields
- `src/ui/components/device_detail_panel.py` — Duplicate button (Contributor/Admin only) in panel header; calls `duplicate_device` and switches panel to new device
- `tests/unit/test_domain_device_copy_name.py`, `tests/integration/test_device_duplicate.py`

### Added — HT-039 Device Status Field
- `src/models/types.py` — `DeviceStatus` enum: `Active`, `Offline`, `Maintenance`, `Planned`, `Decommissioned`
- `src/models/device.py` — `status: DeviceStatus = Field(default=DeviceStatus.Active)` on `DeviceBase`; `status: Optional[DeviceStatus] = None` on `DeviceUpdate`
- `alembic/versions/011_add_device_status.py` — adds `status VARCHAR NOT NULL DEFAULT 'Active'` column; safe for existing data
- `src/services/device_service.py` — `create()` now passes `status` from `DeviceCreate` to the `Device` model
- `src/ui/services/topology_data.py` — node data includes `status` field for canvas CSS selector styles
- `src/ui/components/canvas.py` — Cytoscape status-based node styles (Offline: opacity 0.5, Maintenance: orange border, Planned: dashed border, Decommissioned: opacity 0.3); edge styles by `ConnectionType`; edge tap dispatches `ht:edge-selected`; background tap dispatches `ht:canvas-bg-click`; `window.applyLayoutPositions()` helper
- `src/ui/components/device_detail_panel.py` — Status section with `ui.select` dropdown (Contributor/Admin) or read-only label (Reader); bridge JS hides panel on edge-selected / bg-click events
- `src/ui/pages/inventory_helpers.py` — Status column with `<q-badge>` colour coding in inventory table

### Added — HT-029 Diagram Layout Management
- `src/models/diagram.py` — `DiagramLayoutUpdate(SQLModel)` with optional `name` + `cytoscape_json` fields
- `src/services/diagram_service.py` — `partial_update()` method: updates only provided (non-None) fields
- `src/api/routers/diagrams.py` — `PATCH /api/diagrams/{id}` endpoint; requires Contributor role; returns `DiagramLayoutResponse`
- `src/ui/components/topology_layout_bar.py` — layout selector dropdown, save/rename/delete dialogs using `show_toast` for feedback
- `src/ui/pages/topology.py` — topbar now uses `render_layout_bar` instead of hard-coded "Save Layout" button; `_save_layout` function removed (superseded by layout bar)

### Added — HT-030 Connection Detail Editing UI
- `src/ui/components/connection_detail_panel.py` — new panel shown on edge click: displays source/target names, type dropdown and label input (Contributor/Admin) or read-only info (Reader); Save calls `PATCH /api/connections/{id}`; Delete with confirmation calls `DELETE`; canvas edge updated in real time
- `src/ui/components/canvas.py` — edge type CSS styles (WiFi: dashed, Fibre: thick, iSCSI/NFS: dotted, VM: dashed purple, selected: amber highlight); edge tap dispatches `ht:edge-selected`
- `src/ui/pages/topology.py` — right column renders both `device_detail_panel` and `connection_detail_panel`; panels hide each other via JS events

### Added — HT-039 / HT-029 / HT-030 Tests
- `tests/unit/test_device_status.py` — enum values, model defaults, Optional update field
- `tests/integration/test_device_status.py` — API create/patch/get with all status values; invalid status → 422
- `tests/integration/test_diagrams_patch.py` — PATCH name-only, json-only, both fields; 404; RBAC; 422 on empty name
- `tests/unit/test_connection_edge_styles.py` — edge style mapping dict covers all 7 `ConnectionType` values

### Added — HT-028 UX Design Specification
- `doc/design/site-map.md` — page hierarchy, route table, navigation flows (9 pages, breadcrumb schema)
- `doc/design/app-shell.md` — header bar, collapsible sidebar, responsive breakpoints, ARIA landmarks
- `doc/design/pages.md` — ASCII wireframes for all 9 pages (Topology, Inventory, Device Detail, Map, Settings, Login, etc.)
- `doc/design/components.md` — 12 reusable NiceGUI component specs with code snippets (toast, sidebar, table, badges, modals, etc.)
- `doc/design/interactions.md` — animation catalogue, state machines for canvas/panels, keyboard shortcut table, loading skeleton patterns
- `doc/design/themes.md` — 3 themes (Control Room dark, Clean Light, Midnight OLED) with 40+ design token tables each; WCAG 2.1 AA contrast verification

### Added — HT-034 Health Check Endpoint + HT-036 Toast Notification System
- `src/__version__.py` — single source of truth for the application version string (`1.0.0`)
- `src/api/routers/health.py` — `GET /api/health` public endpoint: returns `status`, `version`, `database`, and `uptime_seconds`; executes `SELECT 1` to verify DB connectivity; responds HTTP 200 when healthy, HTTP 503 when the database is unreachable
- `src/api/middleware/auth.py` — `/api/health` added to `EXCLUDED_API_PATHS` (no JWT required)
- `src/api/app.py` — health router registered under `/api` prefix; removed the old stub `GET /health` endpoint
- `docker-compose.yml` — Docker healthcheck added to the `api` service (`curl -f http://localhost:8080/api/health`, 30s interval, 10s timeout, 3 retries, 40s start period)
- `src/ui/components/toast.py` — `show_toast(type, title, description?, duration_ms?)` function wrapping `ui.notify()` for consistent top-right notifications across all four types (success/error/warning/info); default duration 4000 ms; close button always enabled
- `tests/unit/test_health.py` — version string format tests + uptime tracking tests
- `tests/integration/test_health.py` — healthy/unhealthy endpoint response tests, DB failure simulation (mock session.exec → 503), no-auth enforcement test
- `tests/unit/test_toast.py` — show_toast parameter tests for all 4 types, default/custom duration, message content, positioning

### Fixed
- `src/ui/pages/dashboard.py`, `src/ui/pages/settings_locations.py`, `src/ui/pages/settings_users.py`, `src/ui/pages/inventory.py`, `src/ui/components/device_detail_panel.py` — normalized internal `httpx` collection endpoint calls to slash-terminated routes (`/api/devices/`, `/api/connections/`, `/api/locations/`, `/api/tags/`, `/api/users/`) to prevent NiceGUI catch-all 404 interception when FastAPI routes require trailing slashes.
- Added dashboard trailing-slash regression coverage: `tests/unit/test_dashboard_page.py` (fail-first URL wiring assertion) and `tests/integration/test_dashboard_data_endpoints.py` (slash-terminated dashboard endpoint requests return 200).
- **Bundle C+D Code-Reviewer Remediation**
- `src/services/service_service.py` — `update()` now catches `IntegrityError` on commit races, rolls back, and returns HTTP 409 (`Service already exists on this device`) instead of leaking 500.
- `src/ui/components/device_detail_duplicate.py` — duplication name lookup now paginates `GET /api/devices/` across pages (limit=1000) before `generate_copy_name`, preventing missed collisions beyond the first page.
- `src/repositories/tag_repository.py`, `src/repositories/custom_field_repository.py`, `src/repositories/service_repository.py` — added `get_by_device_ids(...)` batch fetch methods; `src/services/device_service.py` now uses batched enrichment for `include=tags,custom_fields,services` to eliminate per-device N+1 loops.
- `src/models/service_dependency.py` + `alembic/versions/012_create_services_and_dependencies.py` — added DB self-dependency guard `ck_service_dep_no_self_ref` (`service_id <> depends_on_id`) with explicit downgrade drop.
- `src/services/service_service.py` — `add_dependency()` now translates DB integrity failures for self-dependency into HTTP 400 and duplicate edges into HTTP 409.
- Added fail-first regressions and coverage in `tests/unit/test_service_service.py`, `tests/unit/test_device_detail_duplicate.py`, `tests/unit/test_device_service_enrichment.py`, `tests/unit/test_domain_device_copy_name.py`, and `tests/integration/test_services_api.py`.

- `tests/integration/test_auth.py` — updated `test_health_endpoint_accessible_without_token` to call `/api/health` (replaces removed `/health` stub)
- `tests/integration/test_rbac_coverage.py` — excluded `/api/health` from the "every route must have require_role" RBAC coverage audit
- `src/ui/components/connection_detail_panel.py` — replaced unsafe JS f-string interpolation for connection id/type/label with `json.dumps()`-backed JS builders (`_build_cy_edge_remove_js`, `_build_cy_edge_update_js`) before `ui.run_javascript()` calls, preventing quote-break and script injection via user-controlled values.
- `tests/unit/test_connection_detail_panel.py` — added regression test covering single quotes, double quotes, and script-like label/id content to verify generated Cytoscape JS uses safe serialized values.

### Fixed — Bundle A+B Code-Reviewer Remediation
- `src/api/routers/data_transfer.py` — import now performs bounded read (`MAX_IMPORT_BYTES + 1`) before size check, closing the memory-exhaustion path and returning 413 for oversize uploads.
- `src/ui/pages/settings_data.py` — export now uses authenticated `fetch()` download with bearer token from `window._htToken` seeded from NiceGUI storage on page load.
- `src/ui/pages/settings_data.py` — upload content normalization now supports bytes and file-like payloads and rejects unreadable/empty payloads with explicit UI errors.
- `src/repositories/user_repository.py` + `src/services/user_service.py` — last-admin deletion guard now uses row-locking role count (`count_by_role_for_update`) to avoid concurrent double-delete race.
- `src/ui/pages/settings_users.py` — delete table event now uses an async handler that awaits confirmation flow instead of dropping a coroutine.
- `src/domain/export.py` + `src/services/export_service.py` — export domain no longer imports SQLModel table models; mapping into `Exported*` schema types now occurs in service layer.
- `src/ui/components/canvas_shortcuts.py` — fit shortcut now uses guarded `window._cy.fit()` to prevent `ReferenceError`.
- `src/ui/pages/settings_locations.py` — reduced file length to comply with the 250-line cap.
- `tests/unit/test_data_transfer_router.py` + `tests/unit/test_settings_data_page.py` — added regression tests for bounded import reads and upload-byte extraction behavior.

### Added — HT-013 Import from JSON
- `src/domain/export.py` — `topological_sort_locations(locations)` pure function: Kahn's algorithm sorts locations so every parent precedes its children; raises `ValueError("circular_location_reference")` on cycles
- `src/services/import_service.py` — `import_full_snapshot(session, payload)` TRUNCATE-then-INSERT restore: clears all tables (TRUNCATE CASCADE on PostgreSQL, individual DELETEs on SQLite), then inserts in forward-dependency order (users → locations → tags → devices → connections → device_tags → custom_fields → diagram_layouts); sentinel bcrypt hash for imported users (no `password_hash` in export)
- `src/api/routers/data_transfer.py` — `POST /api/import` with `require_role(Role.Admin)`; requires `?confirm=true`; 50 MB file cap (413); 400 on malformed JSON or unsupported version; 422 on Pydantic or DB integrity error; returns count summary dict
- `src/ui/pages/settings_data.py` — Admin-only Import section with `ui.upload`, disabled-until-file-selected Import button, and "Type CONFIRM" confirmation dialog
- `tests/unit/test_import_domain.py` — 10 unit tests: version validation, topological sort (flat, hierarchy, cycle, external parent, multiple roots)
- `tests/integration/test_import.py` — 16 integration tests: RBAC (Admin 200, Contributor/Reader 403, unauth 401), confirm guard, malformed JSON, unknown version, invalid schema, 50 MB limit, UUID preservation, data replacement, round-trip export→import→export

### Added — HT-016 Canvas Keyboard Shortcuts
- `src/ui/components/canvas_shortcuts.py` — `inject_canvas_shortcuts()` injects `keydown` handler: Delete/Backspace (delete selected), Ctrl+D (duplicate), Ctrl+A (select all), Escape (deselect + close panel), Ctrl+Z (undo last drag), Ctrl+S (save layout), F (fit); `activeElement` guard prevents shortcuts from firing in text inputs
- `src/ui/components/canvas.py` — dragfree handler captures undo entry into `window._htUndoStack = {nodeId, prev, next}` before updating `_htNodePositions`
- `src/ui/components/canvas_events.py` — `ht:save-layout` listener clicks the topbar Save Layout button; `ht:close-panel` listener hides `#ht-detail-panel`
- `src/ui/pages/topology.py` — `inject_canvas_shortcuts()` called after `render_canvas()`
- `tests/unit/test_canvas_shortcuts.py` — 15 unit tests: JS content assertions (keydown, activeElement guard, all 7 shortcuts, write guards), `inject_canvas_shortcuts` mocked call verification

### Added — HT-012 Export to JSON
- `src/models/export_schema.py` — Pydantic-only export wire format: `ExportedDevice`, `ExportedConnection`, `ExportedLocation`, `ExportedTag`, `ExportedDeviceTag`, `ExportedCustomField`, `ExportedDiagramLayout`, `ExportedUser` (no `password_hash`), and `ExportSchema` envelope with `version`/`exported_at`
- `src/domain/export.py` — pure mapping functions: `build_export_envelope()` (sorts all collections by `created_at` for deterministic output), `validate_export_version()`, private `_map_*` helpers; `EXPORT_VERSION = "1.0"`, `SUPPORTED_VERSIONS = {"1.0"}`
- `src/services/export_service.py` — `build_full_export(session)` assembles snapshot from all repositories and delegates to domain layer
- `src/api/routers/data_transfer.py` — `GET /api/export` with `require_role(Role.Contributor)`; returns `StreamingResponse` with `Content-Disposition: attachment; filename="hometower-export-YYYY-MM-DD.json"`
- `src/ui/pages/settings_data.py` — NiceGUI page at `/settings/data`; Export button triggers browser download; Import section (Admin-only placeholder for HT-013)
- `tests/unit/test_export_domain.py` — 21 unit tests: envelope properties, sort ordering, `ExportedUser` password exclusion, field mapping correctness, `validate_export_version`
- `tests/integration/test_export.py` — 13 integration tests: RBAC (Contributor 200, Reader 403, unauth 401), `Content-Disposition` header, JSON structure, `password_hash` never in response

### Changed — HT-012 Export to JSON
- `src/repositories/tag_repository.py` — added `get_all(session) -> list[Tag]` and `get_all_device_tags(session) -> list[DeviceTag]`
- `src/repositories/custom_field_repository.py` — added `get_all(session) -> list[CustomField]`
- `src/repositories/device_repository.py` — added `get_all_for_export(session) -> list[Device]` (unbounded, for export use)
- `src/repositories/connection_repository.py` — added `get_all_for_export(session) -> list[Connection]` (unbounded, for export use)
- `src/repositories/diagram_repository.py` — added `get_all_for_export(session) -> list[DiagramLayout]` (unbounded, for export use)
- `src/api/app.py` — registered `data_transfer_router` at `/api` prefix
- `src/main.py` — registered `settings_data` NiceGUI page

### Added — HT-019 Admin User Panel + HT-017 Password Reset CLI
- `src/services/user_service.py` — user CRUD service with guards: 422 short password, 409 duplicate email, 400 self-delete, 400 last-admin-delete, 404 not found
- `src/api/routers/users.py` — Admin-only `/api/users/` CRUD router (GET list, POST create, GET by ID, PATCH update, DELETE with self-delete guard)
- `src/ui/pages/settings_users.py` — Admin-only NiceGUI user management page at `/settings/users`; table with create/edit modal and delete confirmation dialog; self-delete button disabled via `is_self` row flag
- `src/cli.py` — break-glass `reset-password` CLI (`python -m src.cli reset-password --username EMAIL [--password NEWPASS]`); uses getpass for interactive entry; exits 1 on user-not-found or short password
- `tests/unit/test_user_service.py` — 17 unit tests covering all service guards
- `tests/unit/test_cli.py` — 7 unit tests for CLI subcommand and entry point
- `tests/integration/test_users.py` — 16 integration tests: full CRUD flow, RBAC 403, guards (409 dup email, 422 short password, 400 self-delete, 400 last-admin, 404 not found)

### Changed — HT-019 Admin User Panel + HT-017 Password Reset CLI
- `src/repositories/user_repository.py` — added `count_by_role(session, role)` for last-admin guard
- `src/api/app.py` — registered `users_router` at `/api` prefix
- `src/main.py` — registered `settings_users` NiceGUI page

### Added — HT-011 RBAC Enforcement Audit + UI Enforcement
- `src/ui/components/auth_guard.py` — `get_ui_role()`, `redirect_if_unauthenticated()`, `redirect_if_insufficient_role(minimum)` helpers; centralises JWT decode and role check for all NiceGUI pages
- `src/ui/pages/access_denied.py` — minimal `/403` Access Denied page; shown when `redirect_if_insufficient_role` redirects
- `tests/integration/test_rbac_coverage.py` — parametrized test asserting every `/api/` route (except login) carries a `_rbac_protected` dependency; 18 Reader-403 enforcement tests for all Contributor+/Admin+ write endpoints

### Changed — HT-011 RBAC Enforcement Audit + UI Enforcement
- `src/domain/rbac.py` — `require_role()` closure now sets `dependency._rbac_protected = True`; machine-readable marker for coverage test
- `src/api/routers/auth.py` — `POST /api/auth/logout` now has `dependencies=[Depends(require_role(Role.Reader))]`; audit-driven explicit minimum role declaration
- `src/ui/pages/login.py` — stores `role` and `user_id` from decoded JWT in `nicegui_app.storage.user` after successful login
- `src/ui/pages/topology.py` — replaced inline `jose.jwt` decode with `auth_guard` helpers; `window.HT_READONLY = true` injected for Readers; context menu JS guards on `HT_READONLY`; palette hidden for Readers (replaced with "Read-only" label)
- `src/ui/pages/inventory.py` — replaced inline token check with `redirect_if_unauthenticated()`
- `src/ui/pages/settings_locations.py` — replaced inline token check with `redirect_if_unauthenticated()` + `redirect_if_insufficient_role(Role.Contributor)`
- `src/ui/components/canvas.py` — Cytoscape write-action event handlers (drag commit, context menu, palette drop, edge draw) gated on `!window.HT_READONLY`
- `tests/unit/test_domain_rbac.py` — added `test_require_role_dependency_has_marker` test

### Fixed — Code-Reviewer Remediation (HT-006/007/010 bundle)
- **ARCH-001**: Removed direct repository coupling from device router by moving tag/custom-field/connections sub-routes into `src/api/routers/device_sub_routes.py`; `src/api/routers/devices.py` now contains device CRUD only.
- **ARCH-002**: Added `connection_service.get_connections_for_device()` and routed `GET /api/devices/{id}/connections` through service layer (no router→repository calls).
- **DATA-003**: Replaced race-prone check-then-insert in `tag_repository.attach_to_device()` with atomic `ON CONFLICT DO NOTHING` upsert (dialect-aware for PostgreSQL/SQLite).
- **DATA-004**: `tag_service.create()` and `tag_service.update()` now translate `sqlalchemy.exc.IntegrityError` duplicate-name races into HTTP 409 (`Tag name already exists`).
- **DATA-005**: `custom_field_service.create()` and `custom_field_service.update()` now translate `IntegrityError` key-collision races into HTTP 409 (`Custom field key already exists for this device`).
- **SIZE-006**: Split oversized `src/api/routers/devices.py` by extracting sub-routes; file now under 250 lines.
- **SIZE-007**: Split `src/ui/components/device_detail_sections.py` into focused modules (`device_detail_tags_section.py`, `device_detail_custom_fields_section.py`, `device_detail_connections_section.py`) with a compatibility facade.
- **SIZE-008**: Extracted inline edit helper from `src/ui/components/device_detail_panel.py` into `src/ui/components/device_panel_helpers.py` to keep panel file under 250 lines.
- **SIZE-009**: Extracted inventory row/table/tag-chip logic into `src/ui/pages/inventory_helpers.py`; `src/ui/pages/inventory.py` now remains under 250 lines.
- **REVIEW-R2-010**: Inventory tag chip filtering now stores UUIDs (not strings) in `state["tag_ids"]` via UUID normalization in `src/ui/pages/inventory_helpers.py`, restoring tag intersection behavior in `filter_devices`.
- **REVIEW-R2-011**: Device detail panel now fetches devices with `include=location,tags,custom_fields` in `src/ui/components/device_detail_panel.py`, so the Location section renders `location_name` correctly.
- **REVIEW-R2-012**: Updated stale include regression expectations in `tests/integration/test_devices_include.py` to assert populated tags for `?include=location,tags`, and added targeted tag-filter regressions in `tests/unit/test_inventory_helpers.py` and `tests/unit/test_inventory_domain.py`.
- Added fail-first regression tests for race-to-500 paths in `tests/integration/test_tags.py` and `tests/integration/test_custom_fields.py` (IntegrityError → 409 translation).

### Added — HT-010 Device Detail Panel (UI)
- `src/ui/components/device_detail_panel.py` — main panel shell: `render_detail_panel(token, user_role)` sets up the right-side panel, registers `panel_select` socket event listener, fetches device via `GET /api/devices/{id}?include=tags,custom_fields`, renders Identity / Location / Notes / Tags / Custom Fields / Connections sections; inline editing of name, IP, MAC, OS, notes for Contributors; RBAC via `user_role in {"Admin","Contributor"}`; security-first: device_id UUID validated before API call, data always re-fetched from API (never trusted from JS event)
- `src/ui/components/device_detail_sections.py` — `render_tags_section` (colored chips, ×-detach, add-tag dropdown), `render_custom_fields_section` (key:value rows with inline edit/delete, add-field form), `render_connections_section` (neighbor links navigating to `/topology?device_id={id}`)

### Changed — HT-010 Device Detail Panel (UI)
- `src/ui/components/device_detail.py` — replaced 80-line JS-only placeholder with a 3-line thin redirect importing `render_detail_panel` from `device_detail_panel.py` (preserves backward-compatible import for topology page)
- `src/ui/pages/topology.py` — decodes JWT role after token check, passes `token` and `user_role` to `render_detail_panel(token, user_role)`
- `src/ui/pages/inventory.py` — `_build_rows` now shows actual tag names (`", ".join(t.name for t in d.tags)`); `_load_devices` uses `include=location,tags`; tag chip filter bar added below device-type chips (fetched from `GET /api/tags`); `_clear_filters` resets tag chip state

### Added — HT-007 Custom Fields for Devices
- `src/models/custom_field.py` — `CustomFieldBase`, `CustomField`, `CustomFieldCreate`, `CustomFieldUpdate`, `CustomFieldResponse` SQLModel schemas; `validate_key` strips whitespace and rejects empty-after-strip keys
- `alembic/versions/010_create_custom_fields.py` — creates `custom_fields` table with `ix_custom_fields_device_key_lower` composite unique index on `(device_id, LOWER(key))`; CASCADE on `device_id` FK
- `src/repositories/custom_field_repository.py` — `create`, `get_by_id`, `get_by_device` (ordered by created_at ASC), `get_by_device_and_key_normalized` (WHERE LOWER(key)=?), `update`, `delete`
- `src/services/custom_field_service.py` — CRUD orchestration; 409 on per-device duplicate key (case-insensitive), 404 on missing device, 404 on cf not belonging to specified device
- `tests/integration/test_custom_fields.py` — 31 integration tests covering CRUD, 409 duplicate key, case-insensitive collision, same key on different devices (OK), 404 wrong device, key stripping, whitespace-only key 422, `?include=custom_fields` enrichment, combined `?include=tags,custom_fields`, `GET /api/devices/{id}/connections` (empty, source, target, 404)
- `tests/unit/test_inventory_domain.py` — extended `TestNormalizeCustomFieldKey` with 4 additional cases

### Changed — HT-007 Custom Fields for Devices
- `src/models/device.py` — `DeviceResponseEnriched` gains `custom_fields: list[CustomFieldResponse] = []` field
- `src/services/device_service.py` — `get_all_enriched` and `get_by_id_enriched` handle `"custom_fields"` in include set via `custom_field_repository.get_by_device`
- `src/repositories/connection_repository.py` — added `get_by_device(session, device_id)` returning connections where source_id OR target_id matches, ordered by created_at ASC
- `src/api/routers/devices.py` — added `GET/POST /api/devices/{id}/custom-fields`, `PATCH/DELETE /api/devices/{id}/custom-fields/{cf_id}`, `GET /api/devices/{id}/connections` sub-routes
- `tests/conftest.py` — imports `CustomField` to register with `SQLModel.metadata` for test DB table creation

### Added — HT-006 Tag System for Devices
- `src/models/tag.py` — `TagBase`, `Tag`, `TagCreate`, `TagUpdate`, `TagResponse`, `TagWithCountResponse`, `DeviceTag` SQLModel schemas; `_HEX_COLOR_PATTERN` validator on `color` field
- `alembic/versions/009_create_tags_and_device_tags.py` — creates `tags` table with `ix_tags_name_lower` case-insensitive unique index and `device_tags` join table with composite PK and CASCADE on both FKs
- `src/repositories/tag_repository.py` — `create`, `get_by_id`, `get_by_name_normalized` (LOWER match), `get_all_with_counts` (LEFT JOIN + COUNT), `update`, `delete`, `attach_to_device` (idempotent check-then-insert), `detach_from_device`, `get_by_device`
- `src/services/tag_service.py` — Tag CRUD + attach/detach orchestration; 409 on duplicate name, 404 on missing tag/device
- `src/api/routers/tags.py` — `GET/POST /api/tags/`, `GET/PATCH/DELETE /api/tags/{tag_id}`
- `tests/integration/test_tags.py` — 38 integration tests covering CRUD, attach/detach, idempotency, 409 duplicate, device_count in list response, `?include=tags` enrichment, cascade delete
- `tests/unit/test_inventory_domain.py` — extended with `TestNormalizeTagName`, `TestNormalizeCustomFieldKey`, `TestValidateHexColor`, `TestFilterDevicesTagFilter` (30 new assertions replacing old stub tests)

### Changed — HT-006 Tag System for Devices
- `src/domain/inventory.py` — added `normalize_tag_name`, `normalize_custom_field_key`, `validate_hex_color` pure functions; added `HasId` Protocol; `FilterableDevice` Protocol gains `tags: Sequence[HasId]`; implemented tag filter in `filter_devices` (OR-within-set, device without tags fails when tag_ids non-empty)
- `src/models/device.py` — `DeviceResponseEnriched` gains `tags: list[TagResponse] = []` field
- `src/services/device_service.py` — `get_all_enriched` handles `"tags"` in include set; added `get_by_id_enriched` for single-device enriched fetch
- `src/api/routers/devices.py` — added `DeviceTagAttach` schema; `GET /{device_id}` accepts `?include=` param returning `DeviceResponseEnriched`; added `GET/POST /api/devices/{id}/tags` and `DELETE /api/devices/{id}/tags/{tag_id}` sub-routes
- `src/api/app.py` — registered `tags_router` with prefix `/api`
- `tests/conftest.py` — imports `Tag`, `DeviceTag` to register with `SQLModel.metadata` for test DB table creation

### Added — HT-009 Inventory List View
- `src/domain/inventory.py` — pure `filter_devices(devices, search, types, tag_ids)` with AND-across-categories, OR-within-set semantics; tag filter stubbed for HT-006
- `src/ui/pages/inventory.py` — NiceGUI `/inventory` page: 200ms debounced search, DeviceType chip filter bar, virtual-scroll `ui.table`, row-click navigates to `/topology?device_id={id}`, empty state with "Clear filters" button
- `tests/unit/test_inventory_domain.py` — 20 unit tests covering all filter combos, input immutability, order preservation, and tag-stub no-crash
- `tests/integration/test_devices_include.py` — 10 integration tests for `?include=location` enriched endpoint and backward compatibility

### Changed — HT-009 Inventory List View
- `src/repositories/device_repository.py` — added `get_all_with_location(session, page, limit)` performing LEFT JOIN onto `locations`; returns `(Device, location_name)` pairs + total
- `src/services/device_service.py` — added `get_all_enriched(session, page, limit, include)` method; routes to join query when `'location' in include`
- `src/api/routers/devices.py` — `GET /api/devices/` gains `?include=` param; returns `PaginatedDeviceResponseEnriched` when include is non-empty; limit cap raised from 100 → 1000
- `src/main.py` — registered `/inventory` page

### Added — HT-005 Location Management
- `src/models/location.py` — `LocationBase`, `Location`, `LocationCreate`, `LocationUpdate`, `LocationResponse`, `LocationResponseWithAncestors` SQLModel schemas
- `src/domain/locations.py` — pure domain functions: `validate_location_fields()`, `detect_cycle()`, `validate_location_deletable()`
- `src/repositories/location_repository.py` — CRUD + `get_ancestors`, `get_devices_at_location`, `get_parent_map`
- `src/services/location_service.py` — create/get/list/update/delete with full validation, cycle detection, and deletion guard
- `src/api/routers/locations.py` — `POST/GET /api/locations/`, `GET/PATCH/DELETE /api/locations/{id}` with RBAC
- `src/ui/pages/settings_locations.py` — settings page at `/settings/locations` with table, create/edit modal, delete confirmation
- `alembic/versions/007_create_locations_table.py` — creates `locations` table with `location_type` PG enum and self-referential FK
- `alembic/versions/008_add_location_id_to_devices.py` — adds nullable `location_id` FK to `devices` (ON DELETE RESTRICT)
- `src/ui/design/tokens.py` — added `FONT_MONO`, `DEVICE_TYPE_COLORS`, `DEVICE_TYPE_ICONS` constants
- `tests/unit/test_locations_domain.py` — 29 unit tests for all domain pure functions
- `tests/integration/test_locations.py` — 25 integration tests for Location CRUD endpoints

### Changed
- `src/models/device.py` — added `location_id: Optional[uuid.UUID]` to `DeviceBase` and `DeviceUpdate`; added `DeviceResponseEnriched` and `PaginatedDeviceResponseEnriched` (used by HT-009)
- `src/services/device_service.py` — added `_assert_location_exists()` helper; `create()` and `update()` now validate `location_id` exists when provided
- `src/api/app.py` — registered `locations_router` at `/api`
- `tests/unit/test_domain_devices.py` — replaced obsolete CRITICAL-002 guard tests (`TestDeviceCreateNoLocationId`) with positive `TestDeviceLocationId` assertions

### Fixed
- **REVIEW-R2-001**: Location deletion now rejects parent locations that still have child locations with HTTP 400 (`Location has child locations. Reassign or delete them first.`) before any DB-level constraint behavior
- **REVIEW-R2-002**: Inventory page filter wiring now updates visible rows correctly on both debounced search input and DeviceType chip toggles
- **REVIEW-R2-003**: Inventory table now includes device icon column, tags placeholder column, and IP clipboard copy affordance
- **REVIEW-R2-004**: `src/domain/inventory.py` no longer imports `DeviceResponseEnriched`; filtering now uses a protocol-based domain contract to preserve domain-layer purity
- **REVIEW-HT005-HT009-001**: Registered `/settings/locations` page by importing `src/ui/pages/settings_locations` in `src/main.py`
- **REVIEW-HT005-HT009-002**: Inventory auth now reads `access_token` from `app.storage.user` to match login/topology token storage and prevent false `/login` redirects
- **REVIEW-HT005-HT009-003**: Location PATCH now validates `parent_id` existence and returns HTTP 404 (`Parent location not found`) instead of surfacing a 500
- **REVIEW-HT005-HT009-004**: Settings Locations UI no longer relies on missing client-side role state for write controls; RBAC enforcement remains server-side
- **REVIEW-HT005-HT009-005**: `LocationResponseWithAncestors.ancestors` now uses `Field(default_factory=list)` to avoid mutable default state
- **REVIEW-HT005-HT009-006**: Extracted create/edit location modal into `src/ui/components/location_modal.py`, reducing `src/ui/pages/settings_locations.py` below 250 lines
- **REVIEW-HT005-HT009-007**: Added integration regression test for PATCH with non-existent `parent_id` to verify controlled 4xx behavior
- **REVIEW-R4-001**: Settings Locations UI now explicitly sends null for incompatible fields on type transitions (rack→geo clears rack/row/parent_id; geo→rack clears lat/lng)
- **INFRA-001**: Pinned `mypy>=1.8.0,<1.20.0` in `requirements.txt` to avoid mypyc segfault in mypy 1.20.0
- **BUG-E2E-001**: Added FastAPI root redirect `GET /` → `/login` to prevent 404 on first navigation
- **BUG-E2E-002**: Topology save now upserts Autosave behavior (UI checks existing layouts and uses `PUT /api/diagrams/{id}` when present); added diagrams update endpoint/service
- **BUG-E2E-003**: Canvas node delete handler now surfaces API delete failures with user-visible error alerts instead of silent no-op
- **BUG-E2E-004**: Connection creation now rejects duplicate device pairs (including reverse direction) with HTTP 409
- **REVIEW-HIGH-001**: Added DB-level uniqueness for unordered connection pairs via Alembic migration `006` functional unique index (`LEAST/GREATEST`) and mapped constraint races to HTTP 409 in connection service
- **BUG-E2E-006**: Login password field now submits on Enter via `keydown.enter` binding
- **BUG-E2E-007**: Device IP validation now supports both IPv4 and IPv6 using Python `ipaddress`
- **BUG-E2E-008**: Enforced `notes` max length of 5000 on both `DeviceBase` and `DeviceUpdate`
- **CRITICAL-001**: `diagram_service.update_timestamp()` now calls `diagram_repository.update()` instead of `create()` — prevents duplicate layouts on autosave
- **CRITICAL-002**: Removed orphaned `location_id` field from `Device` model — Alembic migration 005 drops the column
- **CRITICAL-003 / SEC-001**: `decode_jwt()` now validates `sub` and `role` claims exist — malformed tokens return 401 instead of crashing with 500
- **SEC-002**: Added rate limiting to `POST /api/auth/login` — 5 requests/minute per IP via `slowapi`
- **HIGH-005**: Canvas data loader now logs warnings on non-200 API responses and handles network errors gracefully
- **HIGH-006**: Connection PATCH now validates `source_id`/`target_id` updates for device existence, self-loops, and duplicate pair conflicts (400/409)
- **HIGH-008 / SEC-006**: Cytoscape JSON validator rejects payloads exceeding 5MB
- **MEDIUM-009**: Topology canvas loader now paginates devices and connections across all pages (limit 100/page) to avoid silent truncation
- **MEDIUM-010**: Authentication success log with user metadata moved from INFO to DEBUG to reduce plaintext PII exposure in production logs

### Security
- **SEC-004**: Dockerfile now runs as non-root `appuser` (addgroup/adduser + USER directive)
- **SEC-005**: CORS middleware configured with explicit allowed origins from `api_base_url`
- **SEC-007**: Content-Security-Policy, X-Content-Type-Options, X-Frame-Options, Referrer-Policy headers added via `SecurityHeadersMiddleware`
- **SEC-008**: Cytoscape.js CDN script tag includes Subresource Integrity (SRI) hash

### Added
- `src/api/middleware/rate_limit.py` — `slowapi` rate limiter instance
- `src/api/middleware/security_headers.py` — CSP + security response headers
- `src/repositories/diagram_repository.py` — explicit `update()` method
- `alembic/versions/005_drop_device_location_id.py` — drops `location_id` column
- `slowapi>=0.1.9` added to `requirements.txt`
- 9 new tests covering all audit fixes

### Added — Inventory Stencils Panel (HT-049)

- **Stencils panel**: Collapsible "Inventory" panel on the left sidebar in edit mode — drag published devices from inventory onto the canvas view.
- **Device search + type filter**: Real-time search by device name and dropdown filter by `DeviceType`.
- **Placed indicator**: Already-placed devices are greyed out with a "Placed" badge and cannot be dragged again (duplicate prevention).
- **Stencil drop handler**: `ht:stencil-drop` event creates a real (non-draft) Cytoscape node at the drop position and triggers autosave.
- **Canvas drop extension**: Drop handler in `canvas_js.py` distinguishes between palette drops (draft) and inventory stencil drops (published).
- **Refresh on remove**: When a device is removed from the canvas via "Remove from View", the stencils panel refreshes its placed state.
- **New files**: `stencils_panel.py`, `stencils_panel_js.py`, `test_stencils_panel.py` (25 unit tests).

### Fixed — Stencils Panel Review Findings (HT-049)

- **Live placed-state tracking**: Panel now consumes `ht:stencil-placed` and `ht:stencil-refresh` events to update badges and greying in real time without page reload.
- **Collapse/expand toggle**: Panel header includes a chevron button that collapses the panel to a 36px bar, freeing canvas width. CSS transition for smooth animation.
- **Virtual scroll**: Device rows are now rendered client-side via JS with IntersectionObserver-based batch loading (50-row batches) for 100+ device inventories.
- **Design token compliance**: Replaced all hardcoded `rgba()` colors with `color-mix(in srgb, var(--ht-*) %, transparent)` in stencils panel and topology draft badge.
- **Test coverage**: Added 22 new tests covering event consumers, virtual scroll, collapse logic, design token usage, and filter+placed interaction (47 total).

### Added — Inventory Device Deletion with Orphan Indicator (HT-052)

- **Cascade delete**: Deleting a device from inventory now cascade-deletes all its connections and removes it from every View's `cytoscape_json` (nodes and associated edges).
- **Placements endpoint**: `GET /api/devices/{id}/placements` returns the list of Views containing a device (view name, topology name).
- **Placed IDs endpoint**: `GET /api/devices/placed-ids` returns all device UUIDs that appear in at least one View (batch orphan detection).
- **Orphan badge**: Devices not placed on any View show a link_off icon in the inventory table with tooltip "Not placed on any View".
- **Orphan filter**: "Orphaned only" checkbox in the inventory filter bar restricts the table to unplaced devices.
- **Delete button**: Red trash icon in inventory table actions column (Contributor/Admin only) with confirmation dialog.
- **Confirmation dialog**: Shows affected Views list; requires typing device name for devices placed on ≥3 Views.
- **Domain pure functions**: `filter_device_from_cytoscape_json()` and `device_in_cytoscape_json()` in `src/domain/devices.py`.
- **Repository helpers**: `connection_repository.delete_by_device()`, `diagram_repository.get_all_layouts()`.
- **DevicePlacement model**: Response schema for placement data in `src/models/device.py`.

### Changed — HT-052

- **Removed connection-count block on delete**: `validate_device_deletable()` removed from domain layer; connections now cascade instead of blocking deletion.
- **Children still block deletion**: `validate_device_no_children()` remains enforced — devices with children cannot be deleted.

### Added — Diagram-first Device Creation with Draft State (HT-051)

- **Draft form on palette drop**: Dragging a device type onto the canvas opens a floating popover form (Name, Type, IP, MAC, OS, Notes) instead of immediately creating an inventory record.
- **Draft nodes**: Submitted form adds a dashed-border "⚠ Draft" node to the canvas, stored only in `cytoscape_json` — no database record until explicitly published.
- **Draft connections**: Edges between draft endpoints are local-only (no API call); edges are promoted to real connections when both endpoints are published.
- **Publish flow**: Right-click → "Publish to Inventory" or click "Publish" in the detail sidebar to POST the device to the API and swap the draft ID for the real UUID.
- **Draft detail sidebar**: Selecting a draft node shows an editable panel with all draft fields and a Publish button.
- **Draft counter badge**: Header shows a badge with the number of unpublished draft nodes; updates on edit-mode entry and node mutations.
- **Draft-aware context menu**: Published nodes show "Remove from View"; draft nodes show "Publish to Inventory" and "Delete Draft".
- **Keyboard guard**: Delete/Backspace only removes draft nodes; published nodes require right-click removal.
- **Opt-in device loading**: `load_canvas_data` now fetches only devices referenced in the saved layout instead of all devices, improving load performance.
- **Draft persistence**: Draft elements survive page reload via `cytoscape_json` serialisation in the diagram layout.
- **New modules**: `canvas_draft.py`, `canvas_draft_form.py`, `canvas_draft_publish.py`, `device_detail_draft.py`.

### Fixed — HT-051 Code Review Findings

- **Publish ID replacement**: Replaced fragile `node.data('id', newId)` with verified remove/re-add flow that captures draft state, removes the node, re-adds with server UUID, asserts resolvability, and rolls back on failure.
- **Opt-in loading edge case**: Distinguished "no layout" (load all devices) from "layout with zero published IDs" (load zero published devices) using explicit `has_layout` flag.
- **Draft type field editable**: Removed disabled state from the type input in the draft form; users can now edit the pre-filled type. Added type field to the draft detail panel with automatic shape update on change.
- **File size extraction**: Extracted `ht:node-remove-from-view` and `ht:node-publish` handlers into `canvas_draft_events.py`; extracted context menu IIFE into `canvas_context_menu.py`. All files now ≤ 250 lines.
- **JS-safe serialization**: Replaced manual string escaping with `json.dumps()` for all values interpolated into JavaScript in `device_detail_draft.py`.
- **Draft edge extraction**: `_extract_draft_elements` now also captures edges with `draft_edge` flag (not just `draft-` prefix).
- **New modules**: `canvas_draft_events.py`, `canvas_context_menu.py`.

### Changed — Collapse Views into Topology (HT-057)

- **Direct canvas entry**: Clicking a Topology name or "Open" in the Topologies table navigates straight to the canvas — the intermediate Views table is removed.
- **Breadcrumb**: Canvas page shows `Workspaces > {workspace name} > {topology name}` when entered from a workspace.
- **`layout_id` query param**: `/topology?layout_id={id}&topology_id={tid}&workspace_id={wid}` loads a specific DiagramLayout.
- **Old route redirect**: `/workspaces/{wid}/topologies/{tid}` auto-resolves the layout and redirects to the canvas (bookmarks/back-button preserved).
- **Auto-create guard**: If a topology has no DiagramLayout, one is created automatically on first access.

### Removed — HT-057

- **`topology_detail.py`**: Views table page deleted.
- **`view_count`**: Removed from `TopologyResponse`, `TopologySummary`, topology service, and the Topologies table UI column.

### Added — View Designer Mode Toggle (HT-048)

- **View-only default**: Topology canvas now opens in view-only mode for ALL users (pan/zoom only). Contributors and Admins see an "Edit" / "Stop Editing" toggle to enter edit mode on demand. Readers never see the toggle.
- **New module** `src/ui/components/canvas_mode.py` — JS constants for `htSetViewMode()` / `htSetEditMode()` Cytoscape interaction transitions.
- **New module** `src/ui/components/topology_edit_toggle.py` — RBAC-gated Edit/Stop Editing button with draft-device warning dialog (HT-051 forward hook).
- **Deferred event wiring**: Cytoscape write event handlers are now wired lazily on first edit-mode entry instead of eagerly at canvas init, reducing accidental mutation risk.
- **Autosave guard**: `_htFlushAutosave` no-ops when `HT_READONLY` is true, preventing spurious PATCH calls in view mode.
- **Write-action guards**: All canvas mutation handlers (association, delete, duplicate, palette drop) now check `HT_READONLY` to prevent writes after exiting edit mode.

### Added — Workspaces, Topologies & Views (HT-047)

- **3-level hierarchy**: Workspace → Topology → View organises diagrams. New models: `Workspace` (owner-scoped), `Topology` (workspace-scoped); existing `DiagramLayout` gains `topology_id` FK.
- **API**: `GET/POST /api/workspaces/`, `GET/POST /api/workspaces/{id}/topologies/`, `GET/POST /api/topologies/{id}/views/`, plus standalone PATCH/DELETE for each entity.
- **UI pages**: `/workspaces`, `/workspaces/{id}`, `/workspaces/{wid}/topologies/{tid}` with table views, breadcrumb navigation, and create/rename/delete dialogs.
- **Navigation**: Sidebar updated — "Topology" replaced with "Workspaces" as the entry point.
- **Migrations**: 021 (workspaces table), 022 (topologies table), 023 (add topology_id to diagram_layouts + backfill).
- **Auto-default**: First visit to `/workspaces` creates a "Default Workspace" with a "Default Topology" for the current user.

### Fixed — Container class not restored on canvas reload

- `src/ui/services/topology_data_helpers.py` — `merge_saved_layout()` now merges CSS classes (e.g. `container`, `collapsed`) from saved Cytoscape layouts back onto API-rebuilt elements, fixing empty containers losing their context menu options after page reload.

### Added — Un-container (HT-046)

- **Context menu**: "Convert to Node" option appears on container nodes; "Convert to Container" and "Collapse/Expand" are now hidden for non-container nodes.
- **Un-convert handler**: `ht:node-unconvert-container` event in `canvas_container_events.py` removes all descendant nodes and their connected edges from the canvas, strips container styling, and triggers autosave. Shows a confirmation dialog when children exist; converts silently when empty.

### Added — Device Containers Remaining (HT-021)

- **Service enrichment**: `?include=children` and `?include=ancestors` now populate `children` and `parent_chain` fields on single-device enriched responses.
- **Export schema**: `ExportedDevice` includes `parent_id` field; exports now capture parent-child relationships.
- **Import service**: Added `_validate_device_parent_refs()` validation; devices are topologically sorted before insertion so parents are created before children; `parent_id` is passed through in the `Device()` constructor.
- **Domain**: Added `topological_sort_devices()` (Kahn's algorithm) to `src/domain/export.py` with cycle detection.

### Fixed — Code-Reviewer Findings (12-04-26)

- **File size (import_service.py)**: Extracted `validate_device_location_refs()`, `validate_device_parent_refs()`, and `ImportPayloadValidationError` from `src/services/import_service.py` (251→222 lines) into new `src/services/import_validation.py`. Updated all imports in `data_transfer.py` router and unit tests.
- **Regression test**: Added `TestIncludeLocationWithSort` in `tests/integration/test_devices_include.py` — verifies `?include=location&sort=name` and `?include=location&sort=-name` produce correctly ordered enriched responses.

### Fixed — Code-Reviewer Findings (Bug Report 11-04-26.1 Remediation)

- **Domain purity (F1)**: Moved `require_role()` from `src/domain/rbac.py` to `src/api/dependencies/rbac.py`; domain layer now contains only pure `ROLE_HIERARCHY` and `can_perform()` with zero FastAPI/logging imports. Updated all 11 router imports and test imports.
- **File size (F2)**: Extracted dialog UI definitions from `src/ui/components/topology_layout_bar.py` (261→240 lines) into `src/ui/components/topology_layout_dialogs.py`.
- **Autosave test coverage (F3)**: Added `TestCanvasAutosaveTemplate` class in `tests/unit/test_ui_canvas.py` — verifies `_htFlushAutosave` definition, dragfree debounce timer, `beforeunload` listener, and `keepalive: true` in fetch.

### Fixed — Autosave Drag Positions (BUG-1101-03)

- `src/ui/components/canvas_js.py` — added debounced autosave (800ms) on `dragfree` events: positions are persisted to the server via `PATCH /api/diagrams/{id}` without requiring manual Save Layout. Added `beforeunload` handler to flush pending saves on tab close. Autosave is gated behind `!window.HT_READONLY` and only fires when a layout is selected.
- `src/ui/components/topology_layout_bar.py` — synced diagram ID and version to JS globals (`window._htDiagramId`, `window._htDiagramVersion`) on layout select/save/rename/delete; manual Save and Rename now read the latest version from JS to avoid conflicts with autosave.

### Fixed — Canvas JS Bugs (BUG-1101-08, BUG-1101-26)

- `src/ui/components/canvas_js.py` — gated the `cy.on('tap', 'node', ...)` handler behind `window.HT_READONLY` so it only dispatches `ht:node-selected` for read-only users; write-mode tap is now handled exclusively in `canvas_events.py` (BUG-1101-08: eliminates duplicate-handler double-fire).
- `src/ui/components/canvas_events.py` — extended the write-mode `cy.on('tap', 'node', ...)` handler to dispatch `ht:node-selected` on normal clicks (no edge source, no shift), making it the single canonical handler for write sessions; also guarded the node-delete success path with an `el.length > 0` check before calling `.remove()`, logging a console warning when the element is absent (BUG-1101-26).

### Fixed — QA Remediation (Bug Report 11-04-26.1)

- `src/services/system_service.py` (new), `src/api/routers/system.py`, `src/api/routers/health.py`, `tests/unit/test_system_service.py` (new) — extracted all direct SQL from `system.py` and `health.py` routers into `system_service.py` (BUG-14, BUG-24): `get_entity_counts()`, `get_user_count()`, `get_db_diagnostics()`, `check_db_connectivity()`. Routers now delegate to service layer with zero inline queries.

- `src/models/export_schema.py`, `src/services/export_service.py`, `src/services/import_service.py`, `src/api/routers/data_transfer.py`, `tests/integration/test_import.py` — restored full services export/import round-trip by adding `ExportedService` and `ExportedServiceDependency` wire models, including `services` and `service_dependencies` in export assembly, importing services/dependencies in FK-safe order, extending table clearing to include `service_dependencies` + `services`, and adding pre-validation that each `device.location_id` exists in payload locations (422 on dangling references).
- `src/repositories/diagram_repository.py`, `src/services/diagram_service.py`, `tests/unit/test_diagram_service.py` — hardened diagram writes against race conditions by locking target rows with `SELECT ... FOR UPDATE` in `update()`, `partial_update()`, `delete()`, and `update_timestamp()`, and added `IntegrityError` handling (`rollback` + HTTP 409) for diagram create/update/write commits with regression tests for stale-version conflicts and rollback behavior.
- `src/services/device_service.py`, `src/services/connection_service.py`, `src/services/location_service.py`, `src/services/service_service.py`, `tests/unit/test_write_service_integrity_handling.py`, `tests/unit/test_service_service.py` — added missing commit guards (`try/except IntegrityError`) with explicit `session.rollback()` on update/create write paths, mapped unmapped integrity failures to clean `HTTPException(500, "Internal database error")`, and changed dependency removal to return 404 for missing edges while logging successful removal only when a row is actually deleted.
- `src/domain/rbac.py`, `src/services/auth_service.py`, `tests/unit/test_domain_rbac.py` — fixed invalid JWT role-claim coercion to deny with HTTP 403 (instead of bubbling enum `ValueError` as 500), added warning telemetry for invalid role claims with optional `user_id`, and removed email addresses from authentication WARNING/INFO logs (failed login, disabled account login, first-boot admin seed).
- `src/models/connection.py`, `alembic/versions/019_add_connection_self_loop_check.py`, `src/models/device.py`, `src/models/user.py`, `src/models/location.py`, `tests/integration/test_connections_validation.py`, `tests/integration/test_devices_validation.py`, `tests/integration/test_users.py`, `tests/integration/test_locations.py` — closed validation gaps by enforcing connection no-self-loop at Pydantic + DB layers, adding `DeviceUpdate.ip` validator parity, adding username/email validators for user create/update models, rejecting punctuation-only location rows, and normalizing whitespace-only location racks to `None`.

### Fixed — Code-Reviewer Findings (SEC-1.1 / SEC-4.4 follow-up)

- **Auth transport mismatch (F1)**: `LoginResponse` now includes `access_token` in the JSON body alongside the HttpOnly cookie. Login page JS passes the token to Python; `app.storage.user` stores it server-side for NiceGUI httpx calls. Removed `window._htToken` XSS vector from `settings_data.py`; export fetch uses `credentials: 'include'` instead.
- **Password change atomicity (F2)**: `change_own_password()` in `auth_service.py` now performs `update` + `increment_token_version` in a single `session.commit()` call.
- **Secret defaults fail-closed (F3)**: Placeholder SECRET_KEY/ADMIN_PASSWORD now raise `ValueError` by default. `DEV_MODE=true` env var opts into warn-only behavior for local development.
- **cookie_secure default (F4)**: `cookie_secure` defaults to `True` (production-safe). Local dev requires `COOKIE_SECURE=false` in `.env`.
- **File length (F5)**: Extracted JS helpers from `canvas_events.py` (283→190 lines) into `canvas_js_helpers.py`. Inlined `_get_layouts` wrapper in `topology_layout_bar.py` (253→248 lines).

### Added — SEC-1.1 / SEC-4.4: JWT Revocation & HttpOnly Cookie Auth

- `alembic/versions/018_add_user_token_version.py` — migration adds `token_version INTEGER NOT NULL DEFAULT 1` to `users` table.
- `src/models/user.py` — `token_version: int = Field(default=1)` added to `User`.
- `src/utils/settings.py` — `cookie_secure: bool = False` setting added for HTTPS deployments.
- `src/repositories/user_repository.py` — `increment_token_version(session, user_id)` atomically increments `token_version`, invalidating all prior JWTs for that user.
- `src/services/auth_service.py` — `authenticate` now returns `tuple[str, int, str]` (token, expiry_unix, role); `change_own_password` calls `increment_token_version` post-commit; new `revoke_tokens(user_id, session)` helper.
- `src/utils/auth.py` — `create_jwt` auto-appends `jti` (UUID4) and `iat`; `decode_jwt` validates all 5 required claims: `sub`, `role`, `jti`, `iat`, `version`.
- `src/api/middleware/auth.py` — Cookie-first token extraction (`ht_access_token`), Bearer header fallback; DB version check on every request; rejects revoked tokens with 401.
- `src/api/routers/auth.py` — Login sets HttpOnly `ht_access_token` cookie (path=`/api`, samesite=strict); logout revokes token version + deletes cookie; `LoginResponse` schema replaces bare `access_token` body.
- `src/ui/pages/login.py` — Removed `sessionStorage.setItem('access_token')`; fetch now uses `credentials: 'include'`; stores `role`, `user_id`, `token_exp` in NiceGUI storage.
- `src/ui/components/auth_guard.py` — Removed `decode_jwt` dependency; reads `role` and `token_exp` from NiceGUI storage for UI-side auth gate.
- `src/ui/components/canvas_events.py` — All 5 Cytoscape event fetch calls migrated from sessionStorage Bearer header to `credentials: 'include'`.
- `src/ui/components/canvas_tooltip.py` — Tooltip fetch migrated from sessionStorage Bearer header to `credentials: 'include'`.
- `tests/unit/test_jwt_revocation.py` — 20 new unit tests covering token creation, claim validation, version increment, revocation, and password-change invalidation.
- `tests/integration/test_jwt_revocation_integration.py` — 13 new integration tests covering login cookie flow, versioned revocation, Bearer fallback, and logout.

### Changed — test infrastructure

- `tests/conftest.py` — New `admin_user` fixture returns the backing `User` object; `admin_token` now depends on `admin_user`. Middleware engine patching (`_auth_mw.engine = test_engine`) added to `client` fixture. All token fixtures (`admin_token`, `contributor_token`, `reader_token`) backed by real DB users with `version` in JWT payload.
- `tests/integration/test_auth.py` — `TestLogin` now asserts `LoginResponse` fields (`user_id`, `role`, `token_exp`, `token_type`) and the `ht_access_token` cookie.
- `tests/integration/test_change_password.py` — `pw_token` fixture includes `version` claim.
- `tests/integration/test_import.py` — `test_preserves_original_uuids` and `test_replaces_all_existing_data` include `admin_user` in import payload so the backing user survives truncation; added `_user_as_payload(user)` helper.
- `tests/integration/test_users.py` — `_token_for()` includes `version` claim; `test_last_admin_delete_returns_400` downgrades `other_admin` to Reader in DB after minting its JWT so exactly one admin remains in the count.
- `tests/unit/test_auth_guard.py` — Storage mock keys updated from `access_token` to `role`/`token_exp`.

### Added — HT-027 Phase 1: Theme Engine Core

- `src/ui/design/tokens.py` — Added `THEMES` dict with three palettes: `dark` ("Control Room"), `light` ("Blueprint"), `midnight` ("Cyberdeck"). Added `STATIC_CSS_VARS` dict with structural tokens (`--ht-radius-*`, `--ht-transition-*`, `--ht-font-*`). All existing `COLOR_*` constants preserved as backward-compatible aliases pointing to dark theme values.
- `src/ui/design/theme_engine.py` — New module. `build_css_var_dict(theme_name)` builds merged CSS var dict. `get_initial_theme_css(theme_name)` returns `<style id="ht-theme">` block for zero-FOUC server-side injection. `get_theme_js_helpers()` returns idempotent `<script>` block defining `window.htApplyThemeVars` and `window._htThemeColors`. `apply_theme_to_client(theme_name)` pushes CSS var updates to the browser without page reload.
- `src/ui/components/canvas_styles.py` — Added `build_theme_style_json(theme_name)` that constructs a Cytoscape style array from theme palette values. `CANVAS_STYLE_JS` preserved as backward-compatible alias (dark theme).
- `src/ui/components/canvas.py` — Added `window.updateCyTheme(stylesJson)` JS global for runtime canvas theme switching. Canvas background now uses `var(--ht-bg-base)` CSS var. `render_canvas()` reads session theme and passes themed styles to Cytoscape init.
- `src/ui/components/app_shell.py` — Injects `get_initial_theme_css()` and `get_theme_js_helpers()` on every authenticated page. Added theme switcher (Dark / Light / Midnight) to user dropdown menu. `_handle_theme_change()` persists theme to `app.storage.user['theme']`, pushes CSS vars via `apply_theme_to_client()`, and re-applies Cytoscape styles via `updateCyTheme`. All `COLOR_*` f-string expressions replaced with `var(--ht-*)` CSS custom properties. Header height changed to 48px per spec. Session-expiry overlay reads colours from CSS vars at overlay construction time. Added `_GLOBAL_CSS` with font-family baseline, fade-in animation, and nav-item hover rule.
- `src/ui/pages/login.py` — Injects dark theme CSS vars and font links. Body and card styles use `var(--ht-*)` references.
- `tests/unit/test_design_system.py` — 67 unit tests covering all new theme engine functionality.
- `src/ui/components/canvas_js.py` — New module extracted from canvas.py. Contains Cytoscape initialization JS template.
- `src/ui/components/sidebar.py` — New module extracted from app_shell.py. Contains sidebar navigation items, render functions, and toggle logic.

### Changed — HT-027 Phase 2: CSP Compliance & Refactoring

- `src/ui/design/theme_engine.py` — Removed external Google Fonts link injection. Theme engine now produces CSS-only output compatible with strict CSP.
- `src/ui/design/tokens.py` — Font CSS vars (`--ht-font-body`, `--ht-font-mono`) now use system font stacks with graceful fallbacks instead of requiring external font loading.
- `src/ui/components/canvas.py` — Reduced from 265 to 61 lines; JS template extracted to `canvas_js.py`.
- `src/ui/components/app_shell.py` — Reduced from 299 to 202 lines; sidebar extracted to `sidebar.py`.
- `tests/unit/test_design_system.py` — Added CSP regression test (`test_no_external_font_links`) and system font stack validation.
- `pytest.ini` — Added `--ignore=tests/e2e` to default pytest run (Playwright not available in Docker container).

### Fixed

- `src/models/diagram.py`, `src/api/routers/diagrams.py`, `src/services/diagram_service.py`, `src/ui/components/topology_layout_bar.py`, `tests/integration/test_diagrams_patch.py`, `tests/integration/test_diagrams.py` — made diagram write preconditions explicit: `DiagramLayoutUpdate.version` is required, `DiagramLayoutResponse` now includes `version`, PUT/PATCH enforce optimistic-lock checks on every write (missing version returns 422, stale version returns 409), and topology UI PATCH calls now send the current `version`.
- `src/models/device.py`, `src/services/device_service.py`, `src/ui/pages/device_edit.py`, `src/ui/components/inventory_edit_modal.py`, `src/ui/components/device_panel_helpers.py`, `src/ui/components/device_detail_panel.py`, `tests/integration/test_devices.py`, `tests/integration/test_devices_validation.py`, `tests/integration/test_device_status.py`, `tests/integration/test_rbac_coverage.py`, `tests/unit/test_device_status.py`, `tests/unit/test_device_detail_duplicate.py` — made device PATCH `version` mandatory, enforced unconditional version checks in service update flow, and updated UI/test callers to send version preconditions.
- `src/models/location.py`, `src/services/location_service.py`, `tests/integration/test_locations.py` — hardened location PATCH validation by rejecting negative/empty `row` values regardless of PATCH payload shape and validating effective rack row state before commit, preventing invalid row persistence on row-only PATCH requests.

- `src/models/device.py`, `src/services/device_service.py`, `tests/integration/test_devices.py`, `alembic/versions/013_add_device_version.py` — added device optimistic locking (`version` column + optional PATCH precondition); stale version updates now return HTTP 409.
- `src/models/diagram.py`, `src/services/diagram_service.py`, `tests/integration/test_diagrams.py`, `alembic/versions/014_add_diagram_version.py` — added diagram optimistic locking for PUT updates with HTTP 409 conflict on stale version.
- `src/models/connection.py`, `tests/unit/test_connection_cascade_delete.py`, `alembic/versions/015_add_cascade_to_connections.py` — enforced `ON DELETE CASCADE` on connection device FKs as defense-in-depth.
- `src/models/location.py`, `tests/unit/test_location_parent_name_uniqueness.py`, `alembic/versions/016_add_location_name_unique.py` — enforced location sibling-name uniqueness at DB/model level.
- `src/repositories/*.py` mutating methods + service-layer write paths — moved transaction ownership from repositories to services (`flush` in repositories, `commit` in services) to restore atomicity and fixture rollback isolation.
- `tests/unit/test_repository_transaction_atomicity.py` — added regression proving failed multi-step operations now roll back cleanly when an error occurs before commit.

- `src/services/import_service.py` — `_is_postgres()` now catches only `(AttributeError, TypeError)` so unexpected runtime DB errors propagate; import now validates each location via `LocationCreate` before insert so invalid geo bounds are rejected.
- `src/models/location.py` — added `row` validator: trims whitespace, rejects empty row strings, and rejects negative numeric rack rows.
- `src/services/user_service.py` + `src/cli.py` — added `reset_password_by_email(...)` service and refactored CLI reset-password to route through service layer instead of direct repository calls.
- `src/ui/components/canvas_js.py` — added `window._htThemeUpdating` guard in `updateCyTheme` to prevent re-entrant style application during rapid theme switching.
- Investigations closed: NiceGUI `app.storage.user` confirmed session-cookie keyed (no cross-user process bleed), and `src/services/device_service.py` logs confirmed to not include device IP values.

- Topology editing UX restored: node click now reliably opens the right-side device detail editor panel again, including inline property editing controls.
- Topology association discoverability improved: right-click context menu now exposes the `Start Association` action via the same event channel used by the canvas context menu overlay.
- Inventory editing flow redesigned: action column now opens a dedicated editor route at `/inventory/edit/{device_id}` with `Save Changes` and `Open in Topology` actions.
- Blank topology canvas: NiceGUI's `.nicegui-content` wrapper had `flex: 0 1 auto`, collapsing the `#cy` container to zero height. Added flex overrides in `app_shell.py` for `.q-page` and `.nicegui-content` to propagate height through the full layout chain.
- Inventory type/tag filter chips now respond to clicks — replaced `chip.on("click", ...)` with `ui.chip(on_click=...)` to integrate properly with Quasar QChip event handling
- Inventory table update uses direct `rows =` assignment plus `.update()` to trigger NiceGUI reactivity instead of in-place `rows[:] =` which bypassed the property setter
- Tag chip toggle in `inventory_helpers.py` migrated to same `on_click=` pattern for consistency
- Topology deep-link routing fixed: visiting `/topology?device_id={id}` now waits for Cytoscape initialization, selects the target node, centers the viewport, and dispatches `ht:node-selected` so the right-side detail panel opens automatically.
- Topology action callbacks now execute in active client context for connection and layout dialogs: save/rename/delete handlers no longer use detached task wrappers, preventing stale UI state after successful API updates.

### Changed — Topology UX Improvements

- Full-width canvas: removed left palette sidebar; topology canvas now spans full viewport width
- Zoom limits: Cytoscape.js canvas now clamps zoom between 0.1× and 5× (prevents infinite zoom)
- Type filter chips: floating overlay shows toggle chips for device types present in the current data; toggling hides/shows matching nodes on the canvas
- Node click behavior: clicking a device node opens the right-side detail/editor panel; Shift+click is reserved for association source selection
- Layout bar clarity: dropdown relabeled "Saved Layouts" with placeholder text; Save button relabeled "Save Layout"
- Removed NiceGUI version from About page
- Extracted canvas tooltip JS into `src/ui/components/canvas_tooltip.py` (canvas.py now 244 lines)

### Added — HT-026 App Shell + Dashboard + HT-038 Graceful Session Expiry

#### App Shell (HT-026)
- `src/ui/components/app_shell.py` — `app_shell(title, current_route, breadcrumb)` context manager: persistent `ui.header()` + `ui.left_drawer()`, sidebar nav with active-item highlight, collapsible drawer (preference persisted in session storage), Admin-only Users link, user-menu dropdown (Change Password + Logout). Also injects HT-038 session-expiry JS interceptor on every authenticated page.
- `src/ui/pages/dashboard.py` — new dashboard page at `/`; stat cards (devices, connections, locations, tags), Recent Activity (last 5 devices by `updated_at`), quick-action buttons; empty-state when no devices exist
- `src/repositories/device_repository.py` — `get_all()` gains `sort: str | None` parameter; valid sort keys: `name`, `-name`, `updated_at`, `-updated_at`, `created_at`, `-created_at`; invalid values silently fall back to default
- `src/services/device_service.py` — `get_all()` passes `sort` through to repository
- `src/api/routers/devices.py` — `GET /api/devices` gains `?sort=` query parameter
- `src/ui/pages/login.py` — redirect after login now goes to `/` (was `/topology`); HT-038 expired-session banner on `?expired=1`; `?next=` param validated server-side and used for post-login redirect; stores `username` (email) in session storage
- `src/main.py` — registers dashboard page

#### Page migrations (all authenticated pages now wrapped in `app_shell`)
- `src/ui/pages/topology.py` — wrapped in `app_shell`; removed per-page topbar and `_logout` function
- `src/ui/pages/inventory.py` — wrapped in `app_shell`
- `src/ui/pages/settings_locations.py` — wrapped in `app_shell`
- `src/ui/pages/settings_users.py` — wrapped in `app_shell`
- `src/ui/pages/settings_data.py` — wrapped in `app_shell`
- `src/ui/pages/settings_profile.py` — wrapped in `app_shell`
- `src/ui/pages/settings_about.py` — wrapped in `app_shell`

#### Session expiry (HT-038)
- `src/ui/components/auth_guard.py` — `safe_next_path(path) -> str | None` validates redirect paths against open-redirect; `redirect_if_unauthenticated(current_path=None)` distinguishes expired-token from absent-token, adds `?expired=1&next=` when applicable
- Session-expiry fetch interceptor (in `app_shell.py`) wraps `window.fetch`, detects 401 from `/api/*`, shows full-screen "Your session has expired" overlay with Sign In button, deduplicates overlays, redirects with `?expired=1&next={pathname}`

#### Tests
- `tests/unit/test_auth_guard.py` — unit tests for `safe_next_path` (9 cases) and `redirect_if_unauthenticated` (6 cases)
- `tests/unit/test_app_shell.py` — unit tests for session-expiry JS content (9 checks) and nav/settings item structure (6 checks)
- `tests/integration/test_devices_sort.py` — integration tests for all sort key variants + invalid fallback + backward compat (9 tests)

### Added — HT-023 Services (name, port, URL, protocol, status per device)
- `src/models/types.py` — `ServiceProtocol` enum (`http`, `https`, `tcp`, `udp`, `other`) and `ServiceStatus` enum (`running`, `stopped`, `unknown`)
- `src/models/service.py` — `Service` + `ServiceDependency` SQLModel tables; `ServiceCreate`, `ServiceUpdate`, `ServiceResponse` schemas
- `alembic/versions/012_create_services_and_dependencies.py` — creates `services` table (FK to devices, unique index on `device_id, LOWER(name)`) and `service_dependencies` table (composite PK, CHECK self-dependency guard)
- `src/domain/services.py` — pure functions: `validate_port(port)` (1–65535), `validate_no_dependency_cycle(service_id, depends_on_id, existing_edges)` (BFS cycle detection)
- `src/repositories/service_repository.py` — full CRUD + dependency edge queries + batch `get_by_device_ids()`
- `src/services/service_service.py` — orchestrates CRUD, port validation, name uniqueness (409), cycle detection (400), IntegrityError handling
- `src/api/routers/services.py` — `GET /api/services`, `GET/PATCH/DELETE /api/services/{id}`, dependency sub-routes `POST /api/services/{id}/dependencies`, `DELETE /api/services/{id}/dependencies/{dep_id}`
- `src/api/routers/device_sub_routes.py` — added `POST /api/devices/{id}/services` and `GET /api/devices/{id}/services`
- `src/models/device.py` — `DeviceResponseEnriched` gains optional `services` field; `?include=services` supported
- `src/ui/components/canvas.py` — Cytoscape node hover tooltip shows service names + status dots (green/red/grey)
- `src/ui/pages/inventory_helpers.py` — Services count column in inventory table
- Tests: `tests/unit/test_domain_services.py`, `tests/integration/test_services_api.py`, `tests/integration/test_service_dependencies.py`

### Added — HT-020 Search and Filter Inventory
- `src/domain/search.py` — `parse_query(raw) -> ParsedQuery` structured search parser; operators: `type:`, `ip:`, `tag:`, `os:`, `location:`, `status:`, `service:`; `to_sql_like(glob)` converts `*` to SQL `%` with proper escaping; unknown operators fall through to free text
- `src/repositories/device_repository.py` — `search(session, parsed, page, limit)` builds dynamic SQLAlchemy filters from `ParsedQuery`; supports JOIN for tag/service/location operators; wildcard via `ILIKE` with escape char
- `src/api/routers/devices.py` — `GET /api/devices` gains `?q=` query parameter for structured search
- `src/ui/pages/inventory.py` — search bar now submits `q` parameter to API for server-side filtering
- Tests: `tests/unit/test_domain_search.py`, `tests/integration/test_device_search.py`

### Added — HT-025 Self-Service Password Change + First-Boot Credential Hardening
- `src/domain/auth.py` — pure function `validate_password_strength(password) -> None`; raises `ValueError` if len < 8
- `src/services/auth_service.py` — `change_own_password(user_id, current, new, session)` service function; else-branch in `create_first_admin_if_needed` logs warning when `ADMIN_PASSWORD` is set in `.env` after first boot
- `src/api/routers/auth.py` — `PATCH /api/auth/me/password` (requires auth, body `{current_password, new_password}`, returns 204)
- `src/ui/pages/settings_profile.py` — password-change form page at `/settings/profile`
- `src/cli.py` — refactored to use `validate_password_strength` (eliminates duplication)
- `src/services/user_service.py` — refactored `create_user` and `update_user` to call `validate_password_strength`
- `.env.example` — added clarifying comment on `ADMIN_PASSWORD` line
- `tests/unit/test_domain_auth.py`, `tests/unit/test_auth_service_change_password.py`, `tests/integration/test_change_password.py`

### Added — HT-035 About / System Info Page
- `src/api/routers/system.py` — `GET /api/system/stats`; returns inventory counts + DB diagnostics; user count Admin-only
- `src/api/app.py` — registers `system_router`
- `src/ui/pages/settings_about.py` — system info page at `/settings/about`: Application, Runtime, Database, Inventory Summary
- `tests/integration/test_system_stats.py`

### Added — HT-040 Canvas Zoom & Fit Controls
- `src/ui/components/canvas_zoom.py` — `inject_zoom_controls()` injects floating +/−/⊡ button group into canvas container via JS; Cytoscape `cy.zoom()` and `cy.fit(undefined, 40)` wired via `window._cy`
- `src/ui/pages/topology.py` — calls `inject_zoom_controls()` after `render_canvas()`
- `tests/unit/test_canvas_zoom.py`

### Added — HT-041 Device Duplication (Clone)
- `src/domain/devices.py` — `generate_copy_name(original_name, existing_names) -> str`: pure collision-aware name generator
- `src/repositories/device_repository.py` — `get_all_names(session) -> list[str]`
- `src/ui/components/device_detail_duplicate.py` — `duplicate_device(token, device)` helper: fetches names, generates copy name, POSTs new device, copies tags and custom fields
- `src/ui/components/device_detail_panel.py` — Duplicate button (Contributor/Admin only) in panel header; calls `duplicate_device` and switches panel to new device
- `tests/unit/test_domain_device_copy_name.py`, `tests/integration/test_device_duplicate.py`

### Added — HT-039 Device Status Field
- `src/models/types.py` — `DeviceStatus` enum: `Active`, `Offline`, `Maintenance`, `Planned`, `Decommissioned`
- `src/models/device.py` — `status: DeviceStatus = Field(default=DeviceStatus.Active)` on `DeviceBase`; `status: Optional[DeviceStatus] = None` on `DeviceUpdate`
- `alembic/versions/011_add_device_status.py` — adds `status VARCHAR NOT NULL DEFAULT 'Active'` column; safe for existing data
- `src/services/device_service.py` — `create()` now passes `status` from `DeviceCreate` to the `Device` model
- `src/ui/services/topology_data.py` — node data includes `status` field for canvas CSS selector styles
- `src/ui/components/canvas.py` — Cytoscape status-based node styles (Offline: opacity 0.5, Maintenance: orange border, Planned: dashed border, Decommissioned: opacity 0.3); edge styles by `ConnectionType`; edge tap dispatches `ht:edge-selected`; background tap dispatches `ht:canvas-bg-click`; `window.applyLayoutPositions()` helper
- `src/ui/components/device_detail_panel.py` — Status section with `ui.select` dropdown (Contributor/Admin) or read-only label (Reader); bridge JS hides panel on edge-selected / bg-click events
- `src/ui/pages/inventory_helpers.py` — Status column with `<q-badge>` colour coding in inventory table

### Added — HT-029 Diagram Layout Management
- `src/models/diagram.py` — `DiagramLayoutUpdate(SQLModel)` with optional `name` + `cytoscape_json` fields
- `src/services/diagram_service.py` — `partial_update()` method: updates only provided (non-None) fields
- `src/api/routers/diagrams.py` — `PATCH /api/diagrams/{id}` endpoint; requires Contributor role; returns `DiagramLayoutResponse`
- `src/ui/components/topology_layout_bar.py` — layout selector dropdown, save/rename/delete dialogs using `show_toast` for feedback
- `src/ui/pages/topology.py` — topbar now uses `render_layout_bar` instead of hard-coded "Save Layout" button; `_save_layout` function removed (superseded by layout bar)

### Added — HT-030 Connection Detail Editing UI
- `src/ui/components/connection_detail_panel.py` — new panel shown on edge click: displays source/target names, type dropdown and label input (Contributor/Admin) or read-only info (Reader); Save calls `PATCH /api/connections/{id}`; Delete with confirmation calls `DELETE`; canvas edge updated in real time
- `src/ui/components/canvas.py` — edge type CSS styles (WiFi: dashed, Fibre: thick, iSCSI/NFS: dotted, VM: dashed purple, selected: amber highlight); edge tap dispatches `ht:edge-selected`
- `src/ui/pages/topology.py` — right column renders both `device_detail_panel` and `connection_detail_panel`; panels hide each other via JS events

### Added — HT-039 / HT-029 / HT-030 Tests
- `tests/unit/test_device_status.py` — enum values, model defaults, Optional update field
- `tests/integration/test_device_status.py` — API create/patch/get with all status values; invalid status → 422
- `tests/integration/test_diagrams_patch.py` — PATCH name-only, json-only, both fields; 404; RBAC; 422 on empty name
- `tests/unit/test_connection_edge_styles.py` — edge style mapping dict covers all 7 `ConnectionType` values

### Added — HT-028 UX Design Specification
- `doc/design/site-map.md` — page hierarchy, route table, navigation flows (9 pages, breadcrumb schema)
- `doc/design/app-shell.md` — header bar, collapsible sidebar, responsive breakpoints, ARIA landmarks
- `doc/design/pages.md` — ASCII wireframes for all 9 pages (Topology, Inventory, Device Detail, Map, Settings, Login, etc.)
- `doc/design/components.md` — 12 reusable NiceGUI component specs with code snippets (toast, sidebar, table, badges, modals, etc.)
- `doc/design/interactions.md` — animation catalogue, state machines for canvas/panels, keyboard shortcut table, loading skeleton patterns
- `doc/design/themes.md` — 3 themes (Control Room dark, Clean Light, Midnight OLED) with 40+ design token tables each; WCAG 2.1 AA contrast verification

### Added — HT-034 Health Check Endpoint + HT-036 Toast Notification System
- `src/__version__.py` — single source of truth for the application version string (`1.0.0`)
- `src/api/routers/health.py` — `GET /api/health` public endpoint: returns `status`, `version`, `database`, and `uptime_seconds`; executes `SELECT 1` to verify DB connectivity; responds HTTP 200 when healthy, HTTP 503 when the database is unreachable
- `src/api/middleware/auth.py` — `/api/health` added to `EXCLUDED_API_PATHS` (no JWT required)
- `src/api/app.py` — health router registered under `/api` prefix; removed the old stub `GET /health` endpoint
- `docker-compose.yml` — Docker healthcheck added to the `api` service (`curl -f http://localhost:8080/api/health`, 30s interval, 10s timeout, 3 retries, 40s start period)
- `src/ui/components/toast.py` — `show_toast(type, title, description?, duration_ms?)` function wrapping `ui.notify()` for consistent top-right notifications across all four types (success/error/warning/info); default duration 4000 ms; close button always enabled
- `tests/unit/test_health.py` — version string format tests + uptime tracking tests
- `tests/integration/test_health.py` — healthy/unhealthy endpoint response tests, DB failure simulation (mock session.exec → 503), no-auth enforcement test
- `tests/unit/test_toast.py` — show_toast parameter tests for all 4 types, default/custom duration, message content, positioning

### Fixed
- `src/ui/pages/dashboard.py`, `src/ui/pages/settings_locations.py`, `src/ui/pages/settings_users.py`, `src/ui/pages/inventory.py`, `src/ui/components/device_detail_panel.py` — normalized internal `httpx` collection endpoint calls to slash-terminated routes (`/api/devices/`, `/api/connections/`, `/api/locations/`, `/api/tags/`, `/api/users/`) to prevent NiceGUI catch-all 404 interception when FastAPI routes require trailing slashes.
- Added dashboard trailing-slash regression coverage: `tests/unit/test_dashboard_page.py` (fail-first URL wiring assertion) and `tests/integration/test_dashboard_data_endpoints.py` (slash-terminated dashboard endpoint requests return 200).
- **Bundle C+D Code-Reviewer Remediation**
- `src/services/service_service.py` — `update()` now catches `IntegrityError` on commit races, rolls back, and returns HTTP 409 (`Service already exists on this device`) instead of leaking 500.
- `src/ui/components/device_detail_duplicate.py` — duplication name lookup now paginates `GET /api/devices/` across pages (limit=1000) before `generate_copy_name`, preventing missed collisions beyond the first page.
- `src/repositories/tag_repository.py`, `src/repositories/custom_field_repository.py`, `src/repositories/service_repository.py` — added `get_by_device_ids(...)` batch fetch methods; `src/services/device_service.py` now uses batched enrichment for `include=tags,custom_fields,services` to eliminate per-device N+1 loops.
- `src/models/service_dependency.py` + `alembic/versions/012_create_services_and_dependencies.py` — added DB self-dependency guard `ck_service_dep_no_self_ref` (`service_id <> depends_on_id`) with explicit downgrade drop.
- `src/services/service_service.py` — `add_dependency()` now translates DB integrity failures for self-dependency into HTTP 400 and duplicate edges into HTTP 409.
- Added fail-first regressions and coverage in `tests/unit/test_service_service.py`, `tests/unit/test_device_detail_duplicate.py`, `tests/unit/test_device_service_enrichment.py`, `tests/unit/test_domain_device_copy_name.py`, and `tests/integration/test_services_api.py`.

- `tests/integration/test_auth.py` — updated `test_health_endpoint_accessible_without_token` to call `/api/health` (replaces removed `/health` stub)
- `tests/integration/test_rbac_coverage.py` — excluded `/api/health` from the "every route must have require_role" RBAC coverage audit
- `src/ui/components/connection_detail_panel.py` — replaced unsafe JS f-string interpolation for connection id/type/label with `json.dumps()`-backed JS builders (`_build_cy_edge_remove_js`, `_build_cy_edge_update_js`) before `ui.run_javascript()` calls, preventing quote-break and script injection via user-controlled values.
- `tests/unit/test_connection_detail_panel.py` — added regression test covering single quotes, double quotes, and script-like label/id content to verify generated Cytoscape JS uses safe serialized values.

### Fixed — Bundle A+B Code-Reviewer Remediation
- `src/api/routers/data_transfer.py` — import now performs bounded read (`MAX_IMPORT_BYTES + 1`) before size check, closing the memory-exhaustion path and returning 413 for oversize uploads.
- `src/ui/pages/settings_data.py` — export now uses authenticated `fetch()` download with bearer token from `window._htToken` seeded from NiceGUI storage on page load.
- `src/ui/pages/settings_data.py` — upload content normalization now supports bytes and file-like payloads and rejects unreadable/empty payloads with explicit UI errors.
- `src/repositories/user_repository.py` + `src/services/user_service.py` — last-admin deletion guard now uses row-locking role count (`count_by_role_for_update`) to avoid concurrent double-delete race.
- `src/ui/pages/settings_users.py` — delete table event now uses an async handler that awaits confirmation flow instead of dropping a coroutine.
- `src/domain/export.py` + `src/services/export_service.py` — export domain no longer imports SQLModel table models; mapping into `Exported*` schema types now occurs in service layer.
- `src/ui/components/canvas_shortcuts.py` — fit shortcut now uses guarded `window._cy.fit()` to prevent `ReferenceError`.
- `src/ui/pages/settings_locations.py` — reduced file length to comply with the 250-line cap.
- `tests/unit/test_data_transfer_router.py` + `tests/unit/test_settings_data_page.py` — added regression tests for bounded import reads and upload-byte extraction behavior.

### Added — HT-013 Import from JSON
- `src/domain/export.py` — `topological_sort_locations(locations)` pure function: Kahn's algorithm sorts locations so every parent precedes its children; raises `ValueError("circular_location_reference")` on cycles
- `src/services/import_service.py` — `import_full_snapshot(session, payload)` TRUNCATE-then-INSERT restore: clears all tables (TRUNCATE CASCADE on PostgreSQL, individual DELETEs on SQLite), then inserts in forward-dependency order (users → locations → tags → devices → connections → device_tags → custom_fields → diagram_layouts); sentinel bcrypt hash for imported users (no `password_hash` in export)
- `src/api/routers/data_transfer.py` — `POST /api/import` with `require_role(Role.Admin)`; requires `?confirm=true`; 50 MB file cap (413); 400 on malformed JSON or unsupported version; 422 on Pydantic or DB integrity error; returns count summary dict
- `src/ui/pages/settings_data.py` — Admin-only Import section with `ui.upload`, disabled-until-file-selected Import button, and "Type CONFIRM" confirmation dialog
- `tests/unit/test_import_domain.py` — 10 unit tests: version validation, topological sort (flat, hierarchy, cycle, external parent, multiple roots)
- `tests/integration/test_import.py` — 16 integration tests: RBAC (Admin 200, Contributor/Reader 403, unauth 401), confirm guard, malformed JSON, unknown version, invalid schema, 50 MB limit, UUID preservation, data replacement, round-trip export→import→export

### Added — HT-016 Canvas Keyboard Shortcuts
- `src/ui/components/canvas_shortcuts.py` — `inject_canvas_shortcuts()` injects `keydown` handler: Delete/Backspace (delete selected), Ctrl+D (duplicate), Ctrl+A (select all), Escape (deselect + close panel), Ctrl+Z (undo last drag), Ctrl+S (save layout), F (fit); `activeElement` guard prevents shortcuts from firing in text inputs
- `src/ui/components/canvas.py` — dragfree handler captures undo entry into `window._htUndoStack = {nodeId, prev, next}` before updating `_htNodePositions`
- `src/ui/components/canvas_events.py` — `ht:save-layout` listener clicks the topbar Save Layout button; `ht:close-panel` listener hides `#ht-detail-panel`
- `src/ui/pages/topology.py` — `inject_canvas_shortcuts()` called after `render_canvas()`
- `tests/unit/test_canvas_shortcuts.py` — 15 unit tests: JS content assertions (keydown, activeElement guard, all 7 shortcuts, write guards), `inject_canvas_shortcuts` mocked call verification

### Added — HT-012 Export to JSON
- `src/models/export_schema.py` — Pydantic-only export wire format: `ExportedDevice`, `ExportedConnection`, `ExportedLocation`, `ExportedTag`, `ExportedDeviceTag`, `ExportedCustomField`, `ExportedDiagramLayout`, `ExportedUser` (no `password_hash`), and `ExportSchema` envelope with `version`/`exported_at`
- `src/domain/export.py` — pure mapping functions: `build_export_envelope()` (sorts all collections by `created_at` for deterministic output), `validate_export_version()`, private `_map_*` helpers; `EXPORT_VERSION = "1.0"`, `SUPPORTED_VERSIONS = {"1.0"}`
- `src/services/export_service.py` — `build_full_export(session)` assembles snapshot from all repositories and delegates to domain layer
- `src/api/routers/data_transfer.py` — `GET /api/export` with `require_role(Role.Contributor)`; returns `StreamingResponse` with `Content-Disposition: attachment; filename="hometower-export-YYYY-MM-DD.json"`
- `src/ui/pages/settings_data.py` — NiceGUI page at `/settings/data`; Export button triggers browser download; Import section (Admin-only placeholder for HT-013)
- `tests/unit/test_export_domain.py` — 21 unit tests: envelope properties, sort ordering, `ExportedUser` password exclusion, field mapping correctness, `validate_export_version`
- `tests/integration/test_export.py` — 13 integration tests: RBAC (Contributor 200, Reader 403, unauth 401), `Content-Disposition` header, JSON structure, `password_hash` never in response

### Changed — HT-012 Export to JSON
- `src/repositories/tag_repository.py` — added `get_all(session) -> list[Tag]` and `get_all_device_tags(session) -> list[DeviceTag]`
- `src/repositories/custom_field_repository.py` — added `get_all(session) -> list[CustomField]`
- `src/repositories/device_repository.py` — added `get_all_for_export(session) -> list[Device]` (unbounded, for export use)
- `src/repositories/connection_repository.py` — added `get_all_for_export(session) -> list[Connection]` (unbounded, for export use)
- `src/repositories/diagram_repository.py` — added `get_all_for_export(session) -> list[DiagramLayout]` (unbounded, for export use)
- `src/api/app.py` — registered `data_transfer_router` at `/api` prefix
- `src/main.py` — registered `settings_data` NiceGUI page

### Added — HT-019 Admin User Panel + HT-017 Password Reset CLI
- `src/services/user_service.py` — user CRUD service with guards: 422 short password, 409 duplicate email, 400 self-delete, 400 last-admin-delete, 404 not found
- `src/api/routers/users.py` — Admin-only `/api/users/` CRUD router (GET list, POST create, GET by ID, PATCH update, DELETE with self-delete guard)
- `src/ui/pages/settings_users.py` — Admin-only NiceGUI user management page at `/settings/users`; table with create/edit modal and delete confirmation dialog; self-delete button disabled via `is_self` row flag
- `src/cli.py` — break-glass `reset-password` CLI (`python -m src.cli reset-password --username EMAIL [--password NEWPASS]`); uses getpass for interactive entry; exits 1 on user-not-found or short password
- `tests/unit/test_user_service.py` — 17 unit tests covering all service guards
- `tests/unit/test_cli.py` — 7 unit tests for CLI subcommand and entry point
- `tests/integration/test_users.py` — 16 integration tests: full CRUD flow, RBAC 403, guards (409 dup email, 422 short password, 400 self-delete, 400 last-admin, 404 not found)

### Changed — HT-019 Admin User Panel + HT-017 Password Reset CLI
- `src/repositories/user_repository.py` — added `count_by_role(session, role)` for last-admin guard
- `src/api/app.py` — registered `users_router` at `/api` prefix
- `src/main.py` — registered `settings_users` NiceGUI page

### Added — HT-011 RBAC Enforcement Audit + UI Enforcement
- `src/ui/components/auth_guard.py` — `get_ui_role()`, `redirect_if_unauthenticated()`, `redirect_if_insufficient_role(minimum)` helpers; centralises JWT decode and role check for all NiceGUI pages
- `src/ui/pages/access_denied.py` — minimal `/403` Access Denied page; shown when `redirect_if_insufficient_role` redirects
- `tests/integration/test_rbac_coverage.py` — parametrized test asserting every `/api/` route (except login) carries a `_rbac_protected` dependency; 18 Reader-403 enforcement tests for all Contributor+/Admin+ write endpoints

### Changed — HT-011 RBAC Enforcement Audit + UI Enforcement
- `src/domain/rbac.py` — `require_role()` closure now sets `dependency._rbac_protected = True`; machine-readable marker for coverage test
- `src/api/routers/auth.py` — `POST /api/auth/logout` now has `dependencies=[Depends(require_role(Role.Reader))]`; audit-driven explicit minimum role declaration
- `src/ui/pages/login.py` — stores `role` and `user_id` from decoded JWT in `nicegui_app.storage.user` after successful login
- `src/ui/pages/topology.py` — replaced inline `jose.jwt` decode with `auth_guard` helpers; `window.HT_READONLY = true` injected for Readers; context menu JS guards on `HT_READONLY`; palette hidden for Readers (replaced with "Read-only" label)
- `src/ui/pages/inventory.py` — replaced inline token check with `redirect_if_unauthenticated()`
- `src/ui/pages/settings_locations.py` — replaced inline token check with `redirect_if_unauthenticated()` + `redirect_if_insufficient_role(Role.Contributor)`
- `src/ui/components/canvas.py` — Cytoscape write-action event handlers (drag commit, context menu, palette drop, edge draw) gated on `!window.HT_READONLY`
- `tests/unit/test_domain_rbac.py` — added `test_require_role_dependency_has_marker` test

### Fixed — Code-Reviewer Remediation (HT-006/007/010 bundle)
- **ARCH-001**: Removed direct repository coupling from device router by moving tag/custom-field/connections sub-routes into `src/api/routers/device_sub_routes.py`; `src/api/routers/devices.py` now contains device CRUD only.
- **ARCH-002**: Added `connection_service.get_connections_for_device()` and routed `GET /api/devices/{id}/connections` through service layer (no router→repository calls).
- **DATA-003**: Replaced race-prone check-then-insert in `tag_repository.attach_to_device()` with atomic `ON CONFLICT DO NOTHING` upsert (dialect-aware for PostgreSQL/SQLite).
- **DATA-004**: `tag_service.create()` and `tag_service.update()` now translate `sqlalchemy.exc.IntegrityError` duplicate-name races into HTTP 409 (`Tag name already exists`).
- **DATA-005**: `custom_field_service.create()` and `custom_field_service.update()` now translate `IntegrityError` key-collision races into HTTP 409 (`Custom field key already exists for this device`).
- **SIZE-006**: Split oversized `src/api/routers/devices.py` by extracting sub-routes; file now under 250 lines.
- **SIZE-007**: Split `src/ui/components/device_detail_sections.py` into focused modules (`device_detail_tags_section.py`, `device_detail_custom_fields_section.py`, `device_detail_connections_section.py`) with a compatibility facade.
- **SIZE-008**: Extracted inline edit helper from `src/ui/components/device_detail_panel.py` into `src/ui/components/device_panel_helpers.py` to keep panel file under 250 lines.
- **SIZE-009**: Extracted inventory row/table/tag-chip logic into `src/ui/pages/inventory_helpers.py`; `src/ui/pages/inventory.py` now remains under 250 lines.
- **REVIEW-R2-010**: Inventory tag chip filtering now stores UUIDs (not strings) in `state["tag_ids"]` via UUID normalization in `src/ui/pages/inventory_helpers.py`, restoring tag intersection behavior in `filter_devices`.
- **REVIEW-R2-011**: Device detail panel now fetches devices with `include=location,tags,custom_fields` in `src/ui/components/device_detail_panel.py`, so the Location section renders `location_name` correctly.
- **REVIEW-R2-012**: Updated stale include regression expectations in `tests/integration/test_devices_include.py` to assert populated tags for `?include=location,tags`, and added targeted tag-filter regressions in `tests/unit/test_inventory_helpers.py` and `tests/unit/test_inventory_domain.py`.
- Added fail-first regression tests for race-to-500 paths in `tests/integration/test_tags.py` and `tests/integration/test_custom_fields.py` (IntegrityError → 409 translation).

### Added — HT-010 Device Detail Panel (UI)
- `src/ui/components/device_detail_panel.py` — main panel shell: `render_detail_panel(token, user_role)` sets up the right-side panel, registers `panel_select` socket event listener, fetches device via `GET /api/devices/{id}?include=tags,custom_fields`, renders Identity / Location / Notes / Tags / Custom Fields / Connections sections; inline editing of name, IP, MAC, OS, notes for Contributors; RBAC via `user_role in {"Admin","Contributor"}`; security-first: device_id UUID validated before API call, data always re-fetched from API (never trusted from JS event)
- `src/ui/components/device_detail_sections.py` — `render_tags_section` (colored chips, ×-detach, add-tag dropdown), `render_custom_fields_section` (key:value rows with inline edit/delete, add-field form), `render_connections_section` (neighbor links navigating to `/topology?device_id={id}`)

### Changed — HT-010 Device Detail Panel (UI)
- `src/ui/components/device_detail.py` — replaced 80-line JS-only placeholder with a 3-line thin redirect importing `render_detail_panel` from `device_detail_panel.py` (preserves backward-compatible import for topology page)
- `src/ui/pages/topology.py` — decodes JWT role after token check, passes `token` and `user_role` to `render_detail_panel(token, user_role)`
- `src/ui/pages/inventory.py` — `_build_rows` now shows actual tag names (`", ".join(t.name for t in d.tags)`); `_load_devices` uses `include=location,tags`; tag chip filter bar added below device-type chips (fetched from `GET /api/tags`); `_clear_filters` resets tag chip state

### Added — HT-007 Custom Fields for Devices
- `src/models/custom_field.py` — `CustomFieldBase`, `CustomField`, `CustomFieldCreate`, `CustomFieldUpdate`, `CustomFieldResponse` SQLModel schemas; `validate_key` strips whitespace and rejects empty-after-strip keys
- `alembic/versions/010_create_custom_fields.py` — creates `custom_fields` table with `ix_custom_fields_device_key_lower` composite unique index on `(device_id, LOWER(key))`; CASCADE on `device_id` FK
- `src/repositories/custom_field_repository.py` — `create`, `get_by_id`, `get_by_device` (ordered by created_at ASC), `get_by_device_and_key_normalized` (WHERE LOWER(key)=?), `update`, `delete`
- `src/services/custom_field_service.py` — CRUD orchestration; 409 on per-device duplicate key (case-insensitive), 404 on missing device, 404 on cf not belonging to specified device
- `tests/integration/test_custom_fields.py` — 31 integration tests covering CRUD, 409 duplicate key, case-insensitive collision, same key on different devices (OK), 404 wrong device, key stripping, whitespace-only key 422, `?include=custom_fields` enrichment, combined `?include=tags,custom_fields`, `GET /api/devices/{id}/connections` (empty, source, target, 404)
- `tests/unit/test_inventory_domain.py` — extended `TestNormalizeCustomFieldKey` with 4 additional cases

### Changed — HT-007 Custom Fields for Devices
- `src/models/device.py` — `DeviceResponseEnriched` gains `custom_fields: list[CustomFieldResponse] = []` field
- `src/services/device_service.py` — `get_all_enriched` and `get_by_id_enriched` handle `"custom_fields"` in include set via `custom_field_repository.get_by_device`
- `src/repositories/connection_repository.py` — added `get_by_device(session, device_id)` returning connections where source_id OR target_id matches, ordered by created_at ASC
- `src/api/routers/devices.py` — added `GET/POST /api/devices/{id}/custom-fields`, `PATCH/DELETE /api/devices/{id}/custom-fields/{cf_id}`, `GET /api/devices/{id}/connections` sub-routes
- `tests/conftest.py` — imports `CustomField` to register with `SQLModel.metadata` for test DB table creation

### Added — HT-006 Tag System for Devices
- `src/models/tag.py` — `TagBase`, `Tag`, `TagCreate`, `TagUpdate`, `TagResponse`, `TagWithCountResponse`, `DeviceTag` SQLModel schemas; `_HEX_COLOR_PATTERN` validator on `color` field
- `alembic/versions/009_create_tags_and_device_tags.py` — creates `tags` table with `ix_tags_name_lower` case-insensitive unique index and `device_tags` join table with composite PK and CASCADE on both FKs
- `src/repositories/tag_repository.py` — `create`, `get_by_id`, `get_by_name_normalized` (LOWER match), `get_all_with_counts` (LEFT JOIN + COUNT), `update`, `delete`, `attach_to_device` (idempotent check-then-insert), `detach_from_device`, `get_by_device`
- `src/services/tag_service.py` — Tag CRUD + attach/detach orchestration; 409 on duplicate name, 404 on missing tag/device
- `src/api/routers/tags.py` — `GET/POST /api/tags/`, `GET/PATCH/DELETE /api/tags/{tag_id}`
- `tests/integration/test_tags.py` — 38 integration tests covering CRUD, attach/detach, idempotency, 409 duplicate, device_count in list response, `?include=tags` enrichment, cascade delete
- `tests/unit/test_inventory_domain.py` — extended with `TestNormalizeTagName`, `TestNormalizeCustomFieldKey`, `TestValidateHexColor`, `TestFilterDevicesTagFilter` (30 new assertions replacing old stub tests)

### Changed — HT-006 Tag System for Devices
- `src/domain/inventory.py` — added `normalize_tag_name`, `normalize_custom_field_key`, `validate_hex_color` pure functions; added `HasId` Protocol; `FilterableDevice` Protocol gains `tags: Sequence[HasId]`; implemented tag filter in `filter_devices` (OR-within-set, device without tags fails when tag_ids non-empty)
- `src/models/device.py` — `DeviceResponseEnriched` gains `tags: list[TagResponse] = []` field
- `src/services/device_service.py` — `get_all_enriched` handles `"tags"` in include set; added `get_by_id_enriched` for single-device enriched fetch
- `src/api/routers/devices.py` — added `DeviceTagAttach` schema; `GET /{device_id}` accepts `?include=` param returning `DeviceResponseEnriched`; added `GET/POST /api/devices/{id}/tags` and `DELETE /api/devices/{id}/tags/{tag_id}` sub-routes
- `src/api/app.py` — registered `tags_router` with prefix `/api`
- `tests/conftest.py` — imports `Tag`, `DeviceTag` to register with `SQLModel.metadata` for test DB table creation

### Added — HT-009 Inventory List View
- `src/domain/inventory.py` — pure `filter_devices(devices, search, types, tag_ids)` with AND-across-categories, OR-within-set semantics; tag filter stubbed for HT-006
- `src/ui/pages/inventory.py` — NiceGUI `/inventory` page: 200ms debounced search, DeviceType chip filter bar, virtual-scroll `ui.table`, row-click navigates to `/topology?device_id={id}`, empty state with "Clear filters" button
- `tests/unit/test_inventory_domain.py` — 20 unit tests covering all filter combos, input immutability, order preservation, and tag-stub no-crash
- `tests/integration/test_devices_include.py` — 10 integration tests for `?include=location` enriched endpoint and backward compatibility

### Changed — HT-009 Inventory List View
- `src/repositories/device_repository.py` — added `get_all_with_location(session, page, limit)` performing LEFT JOIN onto `locations`; returns `(Device, location_name)` pairs + total
- `src/services/device_service.py` — added `get_all_enriched(session, page, limit, include)` method; routes to join query when `'location' in include`
- `src/api/routers/devices.py` — `GET /api/devices/` gains `?include=` param; returns `PaginatedDeviceResponseEnriched` when include is non-empty; limit cap raised from 100 → 1000
- `src/main.py` — registered `/inventory` page

### Added — HT-005 Location Management
- `src/models/location.py` — `LocationBase`, `Location`, `LocationCreate`, `LocationUpdate`, `LocationResponse`, `LocationResponseWithAncestors` SQLModel schemas
- `src/domain/locations.py` — pure domain functions: `validate_location_fields()`, `detect_cycle()`, `validate_location_deletable()`
- `src/repositories/location_repository.py` — CRUD + `get_ancestors`, `get_devices_at_location`, `get_parent_map`
- `src/services/location_service.py` — create/get/list/update/delete with full validation, cycle detection, and deletion guard
- `src/api/routers/locations.py` — `POST/GET /api/locations/`, `GET/PATCH/DELETE /api/locations/{id}` with RBAC
- `src/ui/pages/settings_locations.py` — settings page at `/settings/locations` with table, create/edit modal, delete confirmation
- `alembic/versions/007_create_locations_table.py` — creates `locations` table with `location_type` PG enum and self-referential FK
- `alembic/versions/008_add_location_id_to_devices.py` — adds nullable `location_id` FK to `devices` (ON DELETE RESTRICT)
- `src/ui/design/tokens.py` — added `FONT_MONO`, `DEVICE_TYPE_COLORS`, `DEVICE_TYPE_ICONS` constants
- `tests/unit/test_locations_domain.py` — 29 unit tests for all domain pure functions
- `tests/integration/test_locations.py` — 25 integration tests for Location CRUD endpoints

### Changed
- `src/models/device.py` — added `location_id: Optional[uuid.UUID]` to `DeviceBase` and `DeviceUpdate`; added `DeviceResponseEnriched` and `PaginatedDeviceResponseEnriched` (used by HT-009)
- `src/services/device_service.py` — added `_assert_location_exists()` helper; `create()` and `update()` now validate `location_id` exists when provided
- `src/api/app.py` — registered `locations_router` at `/api`
- `tests/unit/test_domain_devices.py` — replaced obsolete CRITICAL-002 guard tests (`TestDeviceCreateNoLocationId`) with positive `TestDeviceLocationId` assertions

### Fixed
- **REVIEW-R2-001**: Location deletion now rejects parent locations that still have child locations with HTTP 400 (`Location has child locations. Reassign or delete them first.`) before any DB-level constraint behavior
- **REVIEW-R2-002**: Inventory page filter wiring now updates visible rows correctly on both debounced search input and DeviceType chip toggles
- **REVIEW-R2-003**: Inventory table now includes device icon column, tags placeholder column, and IP clipboard copy affordance
- **REVIEW-R2-004**: `src/domain/inventory.py` no longer imports `DeviceResponseEnriched`; filtering now uses a protocol-based domain contract to preserve domain-layer purity
- **REVIEW-HT005-HT009-001**: Registered `/settings/locations` page by importing `src/ui/pages/settings_locations` in `src/main.py`
- **REVIEW-HT005-HT009-002**: Inventory auth now reads `access_token` from `app.storage.user` to match login/topology token storage and prevent false `/login` redirects
- **REVIEW-HT005-HT009-003**: Location PATCH now validates `parent_id` existence and returns HTTP 404 (`Parent location not found`) instead of surfacing a 500
- **REVIEW-HT005-HT009-004**: Settings Locations UI no longer relies on missing client-side role state for write controls; RBAC enforcement remains server-side
- **REVIEW-HT005-HT009-005**: `LocationResponseWithAncestors.ancestors` now uses `Field(default_factory=list)` to avoid mutable default state
- **REVIEW-HT005-HT009-006**: Extracted create/edit location modal into `src/ui/components/location_modal.py`, reducing `src/ui/pages/settings_locations.py` below 250 lines
- **REVIEW-HT005-HT009-007**: Added integration regression test for PATCH with non-existent `parent_id` to verify controlled 4xx behavior
- **REVIEW-R4-001**: Settings Locations UI now explicitly sends null for incompatible fields on type transitions (rack→geo clears rack/row/parent_id; geo→rack clears lat/lng)
- **INFRA-001**: Pinned `mypy>=1.8.0,<1.20.0` in `requirements.txt` to avoid mypyc segfault in mypy 1.20.0
- **BUG-E2E-001**: Added FastAPI root redirect `GET /` → `/login` to prevent 404 on first navigation
- **BUG-E2E-002**: Topology save now upserts Autosave behavior (UI checks existing layouts and uses `PUT /api/diagrams/{id}` when present); added diagrams update endpoint/service
- **BUG-E2E-003**: Canvas node delete handler now surfaces API delete failures with user-visible error alerts instead of silent no-op
- **BUG-E2E-004**: Connection creation now rejects duplicate device pairs (including reverse direction) with HTTP 409
- **REVIEW-HIGH-001**: Added DB-level uniqueness for unordered connection pairs via Alembic migration `006` functional unique index (`LEAST/GREATEST`) and mapped constraint races to HTTP 409 in connection service
- **BUG-E2E-006**: Login password field now submits on Enter via `keydown.enter` binding
- **BUG-E2E-007**: Device IP validation now supports both IPv4 and IPv6 using Python `ipaddress`
- **BUG-E2E-008**: Enforced `notes` max length of 5000 on both `DeviceBase` and `DeviceUpdate`
- **CRITICAL-001**: `diagram_service.update_timestamp()` now calls `diagram_repository.update()` instead of `create()` — prevents duplicate layouts on autosave
- **CRITICAL-002**: Removed orphaned `location_id` field from `Device` model — Alembic migration 005 drops the column
- **CRITICAL-003 / SEC-001**: `decode_jwt()` now validates `sub` and `role` claims exist — malformed tokens return 401 instead of crashing with 500
- **SEC-002**: Added rate limiting to `POST /api/auth/login` — 5 requests/minute per IP via `slowapi`
- **HIGH-005**: Canvas data loader now logs warnings on non-200 API responses and handles network errors gracefully
- **HIGH-006**: Connection PATCH now validates `source_id`/`target_id` updates for device existence, self-loops, and duplicate pair conflicts (400/409)
- **HIGH-008 / SEC-006**: Cytoscape JSON validator rejects payloads exceeding 5MB
- **MEDIUM-009**: Topology canvas loader now paginates devices and connections across all pages (limit 100/page) to avoid silent truncation
- **MEDIUM-010**: Authentication success log with user metadata moved from INFO to DEBUG to reduce plaintext PII exposure in production logs

### Security
- **SEC-004**: Dockerfile now runs as non-root `appuser` (addgroup/adduser + USER directive)
- **SEC-005**: CORS middleware configured with explicit allowed origins from `api_base_url`
- **SEC-007**: Content-Security-Policy, X-Content-Type-Options, X-Frame-Options, Referrer-Policy headers added via `SecurityHeadersMiddleware`
- **SEC-008**: Cytoscape.js CDN script tag includes Subresource Integrity (SRI) hash

### Added
- `src/api/middleware/rate_limit.py` — `slowapi` rate limiter instance
- `src/api/middleware/security_headers.py` — CSP + security response headers
- `src/repositories/diagram_repository.py` — explicit `update()` method
- `alembic/versions/005_drop_device_location_id.py` — drops `location_id` column
- `slowapi>=0.1.9` added to `requirements.txt`
- 9 new tests covering all audit fixes

### Fixed
- Canvas: replaced non-existent `cy.renderedToModel()` with manual zoom/pan coordinate conversion in drop handler — fixes all palette drag-drop device creation
- Canvas: bounded retry for Cytoscape CDN race condition (max 50 attempts × 100ms)
- Canvas: fixed 0-height `#cy` container by overriding NiceGUI `.row` align-items with stretch + absolute-fill wrapper
- Device service: wired `validate_mac()` in create and update paths — MAC addresses now normalized to uppercase


### Added
- HT-004: Device-to-device connections
  - `src/models/connection.py` — `Connection`, `ConnectionCreate`, `ConnectionUpdate`, `ConnectionResponse` SQLModel models (UUID PK, FK to devices.id for source and target)
  - `src/domain/connections.py` — pure function `validate_no_self_loop()` (raises ValueError on source==target)
  - `src/repositories/connection_repository.py` — full CRUD + paginated/filtered `get_all()` + `count_by_device()` (counts where device is source OR target)
  - `src/services/connection_service.py` — `create`, `get_by_id`, `get_all`, `update`, `delete` with self-loop and device-existence validation
  - `src/api/routers/connections.py` — `GET/POST /api/connections/`, `GET/PATCH/DELETE /api/connections/{id}` (Contributor writes, Reader reads; source_id/target_id filter params)
  - `alembic/versions/004_create_connections_table.py` — `connections` table with PG_UUID/PG_ENUM, FKs, no-self-loop CHECK constraint, indexes, `updated_at` trigger
  - Wired `_count_device_connections()` in `device_service.py` to use `connection_repository.count_by_device()` — device with active connections now blocked from deletion (HTTP 400)
  - `src/ui/pages/topology.py` — `_load_canvas_data()` now fetches connections from `GET /api/connections/` and builds Cytoscape edge elements
  - `src/ui/components/canvas.py` — added `addEdgeToCanvas()` helper; shift+click two nodes to draw a connection (POST /api/connections/); right-click edge to delete
  - `docker-compose.yml` — added `./tests` and `./alembic` bind mounts so new files are live-reflected without rebuilding
  - 19 new tests (2 unit + 17 integration); all 109 tests pass; mypy zero errors; build clean

- HT-003: Basic Topology Canvas with Drag-Drop
  - `src/models/diagram.py` — `DiagramLayout`, `DiagramLayoutCreate`, `DiagramLayoutResponse`, `DiagramLayoutSummary`, `PaginatedDiagramSummary` SQLModel models (UUID PK, JSON column for Cytoscape state)
  - `src/repositories/diagram_repository.py` — `create`, `get_by_id`, `get_all`, `delete`
  - `src/services/diagram_service.py` — orchestrates diagram CRUD with HTTP 404 guards
  - `src/api/routers/diagrams.py` — `GET/POST /api/diagrams/`, `GET/DELETE /api/diagrams/{id}` (Contributor creates, Reader reads, Admin deletes)
  - `alembic/versions/003_create_diagram_layouts_table.py` — `diagram_layouts` table with JSONB column
  - `src/ui/components/canvas.py` — Cytoscape.js 3.28.1 canvas component (CDN), drag events, context menu, palette drop handler, preset/cose layout
  - `src/ui/components/device_palette.py` — HTML5 drag-and-drop palette sidebar with all DeviceType cards
  - `src/ui/components/device_detail.py` — right-side detail panel, listens for `ht:node-selected` custom event
  - `src/ui/pages/topology.py` — NiceGUI `/topology` page with auth guard, three-column layout, Save Layout button
  - `src/ui/design/tokens.py` — added `DEVICE_SHAPES` mapping all 13 `DeviceType` values → Cytoscape shape strings
  - 13 new integration tests; all 90 tests pass; mypy zero errors


  - `src/models/device.py` — `Device`, `DeviceCreate`, `DeviceUpdate`, `DeviceResponse` SQLModel models (UUID PK, MAC format validator)
  - `src/domain/devices.py` — pure functions: `validate_mac()`, `validate_ip()`, `validate_device_deletable()`
  - `src/repositories/device_repository.py` — full CRUD + paginated `get_all()` + `count()`
  - `src/services/device_service.py` — `create`, `get_by_id`, `get_all`, `update`, `delete` with domain validation
  - `src/api/routers/devices.py` — `POST/GET/PATCH/DELETE /api/devices/` with RBAC (Contributor writes, Reader reads)
  - `alembic/versions/002_create_devices_table.py` — `devices` table + `device_type` enum + indexes + `updated_at` trigger
  - 31 new tests (17 unit + 14 integration); all 69 tests pass

- HT-001: User authentication and session management
  - First-boot admin creation from `ADMIN_EMAIL` / `ADMIN_PASSWORD` env vars
  - JWT login via `POST /api/auth/login` (HS256, 24h expiry)
  - Stateless logout via `POST /api/auth/logout`
  - `AuthMiddleware` for JWT decode and `request.state` injection
  - `src/domain/rbac.py` — `can_perform()` and `require_role()` dependency
  - `src/models/user.py` — `User`, `UserCreate`, `UserUpdate`, `UserResponse` SQLModel models
  - `src/models/types.py` — `DeviceType`, `ConnectionType`, `Role`, `LocationType` enums
  - `src/repositories/user_repository.py` — full CRUD + count
  - `src/services/auth_service.py` — `authenticate()`, `create_first_admin_if_needed()`
  - `src/utils/auth.py` — bcrypt helpers, JWT create/decode
  - `src/utils/settings.py` — Pydantic settings from `.env`
  - `src/utils/logger.py` — Loguru singleton
  - `src/utils/db.py` — SQLModel engine, `get_session()` FastAPI dependency
  - `src/ui/pages/login.py` — NiceGUI login page at `/login`
  - `src/ui/design/tokens.py` — design system constants
  - Alembic migration `001_initial_schema.py` — `users` table, enum, index, trigger
  - Full project scaffolding: `Dockerfile`, `docker-compose.yml`, `alembic.ini`, `.env.example`
  - Unit tests for RBAC domain functions
  - Integration tests for auth endpoints and middleware

### Fixed
- Topology canvas initialization race with dynamically injected Cytoscape CDN script
  - `src/ui/components/canvas.py` now retries `initCanvas(...)` until `window.cytoscape` is available and the `#cy` container has non-zero dimensions before creating the graph instance
  - `src/ui/components/canvas.py` now uses absolute fill positioning for `#cy` (`top/right/bottom/left: 0`) to prevent flex wrapper height-chain collapse
- Topology canvas visibility regression (0px height)
  - `src/ui/pages/topology.py` now forces the three-column body row to use `flex-wrap: nowrap` and `align-items: stretch`, and sets `min-height: 0` on the canvas column
  - `src/ui/components/canvas.py` now wraps `#cy` in an absolute-fill container while `#cy` uses `width: 100%; height: 100%` to keep non-zero dimensions even if Cytoscape mutates inline styles
