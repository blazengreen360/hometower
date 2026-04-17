# RFC: Topology History, Personal Drafts, Leave Guard, and Ghost Restore Foundation

**Story:** HT-072, HT-073, HT-074, HT-075 · **Status:** Draft · **Date:** 2026-04-14
**Author:** Architect

---

## 1. Overview

HT-072..HT-075 are one design surface, not four independent stories. The current implementation still treats `DiagramLayout` as both storage and user-facing workflow, and the topology page still assumes a mutable `layout_id`-centric canvas. That is incompatible with the agreed product model:

- `Topology` is the thing the user edits.
- `History` is explicit, immutable, and append-only.
- `Personal Draft` is private per user and is the only autosave target.
- Restore is topology-only, not an inventory rollback.

The lowest-rework path is:

1. Keep `diagram_layouts` as an internal mutable current-snapshot store for a topology.
2. Add a new immutable history table.
3. Add a new per-user draft table.
4. Introduce a topology-centric editor-state API so the UI no longer reconstructs canvas state from `devices + connections + layout` on the client.

Do **not** repurpose `diagram_layouts` as history. Current code mutates and cleans that table aggressively during autosave, undo, and device deletion; reusing it as immutable history would create avoidable HT-075 regressions.

---

## 2. Recommended Delivery Decomposition

### HT-072 must land

HT-072 should not ship as a pure label-swap. It must carry a thin shared foundation for HT-073..HT-075.

**Must-have in HT-072:**

- New `topology_history_entries` table.
- New `topology_personal_drafts` table.
- Explicit canonical current snapshot per topology, using existing `diagram_layouts` as the internal mutable store.
- New topology-centric editor-state orchestration (`latest saved snapshot + personal draft + metadata`).
- Topology page stops depending on `layout_id` as the primary route contract.
- Top toolbar changes from `Saved Layouts / Save Layout` to `Save Version / History`.
- History drawer lists versions newest-first and supports append-only restore.
- Autosave is rerouted immediately to the personal-draft API, even if the visible Draft chip is deferred to HT-073.
- Current JS globals stop being diagram-specific (`_htDiagramId`, `_htDiagramVersion`) and become working-copy specific.

**Why this is required in HT-072:**

- If autosave continues PATCHing `/api/diagrams/{id}`, HT-072 violates the agreed semantics on day one.
- If the UI keeps reconstructing topology state from live DB rows only, HT-072 history and HT-075 ghost restore will both be partial and misleading.

### HT-073 deferred work

- Visible `Draft` status chip beside the topology title.
- Resume copy and UI affordance that make it obvious the page is showing a personal draft instead of the latest saved version.
- Reader-specific proof that merely viewing a topology never creates a draft row.
- Save Version publish flow clears or rebases the active draft and clears the unsaved-draft indicator.

### HT-074 deferred work

- In-app three-choice leave modal: `Save Version`, `Discard`, `Cancel`.
- Browser-native `beforeunload` warning for tab close / hard unload.
- Shared navigation bridge for topology-page route changes from sidebar, breadcrumb, and browser history.
- Draft discard endpoint usage from the leave flow.

### HT-075 deferred work

- Ghost placeholder synthesis on restore.
- Restore summary banner with ghost counts and explanatory copy.
- Ghost detail panel actions: `Recreate as New Device`, `Map to Existing Device`.
- History-preserving deletion semantics: current snapshot and drafts may be cleaned, history entries may not.

### Recommendation

Implement HT-072 with the thin shared foundation. Do **not** implement HT-072 alone on top of the legacy mutable-layout flow.

---

## 3. Hidden Design Decisions (Parnas Test)

| Module | Hides |
|---|---|
| `src/models/topology_history.py` | How immutable saved topology checkpoints are persisted and version-numbered. |
| `src/models/topology_draft.py` | How private per-user draft state is keyed, versioned, and expired. |
| `src/services/topology_canvas_service.py` | How current snapshot, latest history, personal draft, and ghost synthesis combine into one renderable editor state. |
| `src/api/routers/topology_history.py` | The HTTP contract for save-version, history list, restore, draft autosave, and discard. |
| `src/ui/components/topology_layout_bar.py` | The topology toolbar interaction model, even though the file keeps its legacy name. |
| `src/ui/components/topology_leave_guard.py` | How NiceGUI route changes and browser leave events are intercepted from the topology page only. |
| `src/ui/components/device_detail_ghost.py` | How ghost-specific reconciliation actions are presented without contaminating the live-device panel. |

---

## 4. Data Model Changes

### 4.1 Keep `DiagramLayout` as an internal current-snapshot store

`src/models/diagram.py` remains in place, but its user-facing meaning changes:

- It is no longer a user-managed `Layout` or `View`.
- The topology editor reads and writes the topology's canonical current snapshot only.
- Extra legacy rows remain compatibility data and are not shown in the new UI.

### 4.2 Modify `Topology`

`src/models/topology.py`

```python
class Topology(TopologyBase, table=True):
    __tablename__ = "topologies"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_topology_workspace_name"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    current_diagram_id: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("diagram_layouts.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
```

**Rationale:** this makes the canonical current snapshot explicit without forcing a destructive rewrite of legacy `diagram_layouts` rows.

### 4.3 Add immutable history table

New file: `src/models/topology_history.py`

```python
class TopologyHistoryBase(SQLModel):
    version_number: int = Field(ge=1)
    cytoscape_json: dict[str, object] = Field(sa_column=Column(JSON))
    restored_from_history_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="topology_history_entries.id",
    )
    restore_summary: dict[str, object] = Field(
        default={},
        sa_column=Column(JSON),
    )


class TopologyHistoryEntry(TopologyHistoryBase, table=True):
    __tablename__ = "topology_history_entries"
    __table_args__ = (
        UniqueConstraint(
            "topology_id",
            "version_number",
            name="uq_topology_history_topology_version",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    topology_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("topologies.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    created_by_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    created_at: datetime = Field(default_factory=_utcnow)


class TopologyHistoryCreate(TopologyHistoryBase):
    topology_id: uuid.UUID
    created_by_id: uuid.UUID


class TopologyHistoryUpdate(SQLModel):
    version_number: int


class TopologyHistoryResponse(TopologyHistoryBase):
    id: uuid.UUID
    topology_id: uuid.UUID
    created_by_id: uuid.UUID
    created_at: datetime


class TopologyHistorySummary(SQLModel):
    id: uuid.UUID
    topology_id: uuid.UUID
    version_number: int
    created_at: datetime
    created_by_id: uuid.UUID
    restored_from_history_id: uuid.UUID | None = None
    is_current: bool = False
    ghost_count: int = 0
```

**Notes:**

- Immutable rows are insert-only.
- `restore_summary` is JSON so HT-075 can persist ghost counts and recovery outcomes without adding a second restore-log table.
- No route updates history rows after insert.

### 4.4 Add per-user draft table

New file: `src/models/topology_draft.py`

```python
class TopologyDraftBase(SQLModel):
    cytoscape_json: dict[str, object] = Field(sa_column=Column(JSON))
    based_on_history_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="topology_history_entries.id",
    )


class TopologyPersonalDraft(TopologyDraftBase, table=True):
    __tablename__ = "topology_personal_drafts"
    __table_args__ = (
        UniqueConstraint(
            "topology_id",
            "user_id",
            name="uq_topology_personal_draft_topology_user",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    topology_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("topologies.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    user_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    version: int = Field(default=1)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class TopologyDraftCreate(TopologyDraftBase):
    topology_id: uuid.UUID
    user_id: uuid.UUID


class TopologyDraftUpdate(SQLModel):
    cytoscape_json: dict[str, object]
    based_on_history_id: uuid.UUID | None = None
    version: int | None = None


class TopologyDraftResponse(TopologyDraftBase):
    id: uuid.UUID
    topology_id: uuid.UUID
    user_id: uuid.UUID
    version: int
    created_at: datetime
    updated_at: datetime


class TopologyDraftSummary(SQLModel):
    id: uuid.UUID
    topology_id: uuid.UUID
    version: int
    based_on_history_id: uuid.UUID | None = None
    updated_at: datetime
```

### 4.5 Add topology editor-state response model

Either in `src/models/topology_history.py` or a dedicated `src/models/topology_editor.py`:

```python
class TopologyEditorStateResponse(SQLModel):
    topology_id: uuid.UUID
    workspace_id: uuid.UUID
    current_diagram_id: uuid.UUID
    current_diagram_version: int
    effective_cytoscape_json: dict[str, object]
    latest_history: TopologyHistorySummary | None = None
    personal_draft: TopologyDraftSummary | None = None
    effective_source: str
    has_unsaved_changes: bool
    restore_summary: dict[str, object] = {}
```

### 4.6 Device status decision for HT-075

Do **not** add a new `DeviceStatus` in HT-072.

For HT-075, default recommendation is:

- Use existing `DeviceStatus.Planned` for `Recreate as New Device`.
- If Product insists on a visible `PendingReview` state, add that enum in HT-075 only and update every status consumer in one pass.

This avoids dragging a cross-cutting enum migration into HT-072.

**Alembic migration required — DevOps-Engineer migration review needed.**

---

## 5. Domain Logic

New file: `src/domain/topology_history.py`

Required pure functions:

```python
def normalize_cytoscape_json(cytoscape_json: dict[str, object]) -> dict[str, object]:
    ...


def topology_has_unsaved_changes(
    saved_json: dict[str, object],
    working_json: dict[str, object],
) -> bool:
    ...


def next_history_version_number(existing_latest: int | None) -> int:
    ...


def extract_missing_device_refs(
    cytoscape_json: dict[str, object],
    live_device_ids: set[str],
) -> list[dict[str, object]]:
    ...


def synthesize_ghost_placeholders(
    cytoscape_json: dict[str, object],
    live_device_ids: set[str],
) -> tuple[dict[str, object], dict[str, object]]:
    ...


def replace_ghost_with_live_device(
    cytoscape_json: dict[str, object],
    ghost_id: str,
    live_device_id: str,
) -> dict[str, object]:
    ...
```

**Important:** HT-075 ghost handling belongs in a new topology-history domain module, not in `src/domain/devices.py`. That file currently hides device-delete filtering logic for live views; it should not also hide restored-history ghost semantics.

---

## 6. Service Layer

### New service

New file: `src/services/topology_canvas_service.py`

```python
def get_editor_state(
    topology_id: uuid.UUID,
    user_id: uuid.UUID,
    role: Role,
    session: Session,
) -> TopologyEditorStateResponse:
    ...


def autosave_personal_draft(
    topology_id: uuid.UUID,
    user_id: uuid.UUID,
    data: TopologyDraftUpdate,
    session: Session,
) -> TopologyDraftResponse:
    ...


def discard_personal_draft(
    topology_id: uuid.UUID,
    user_id: uuid.UUID,
    session: Session,
) -> None:
    ...


def save_version(
    topology_id: uuid.UUID,
    user_id: uuid.UUID,
    data: TopologyDraftUpdate,
    session: Session,
) -> TopologyHistoryResponse:
    ...


def restore_history_entry(
    topology_id: uuid.UUID,
    history_id: uuid.UUID,
    user_id: uuid.UUID,
    session: Session,
) -> TopologyEditorStateResponse:
    ...


def recreate_ghost_as_device(
    topology_id: uuid.UUID,
    ghost_id: str,
    user_id: uuid.UUID,
    session: Session,
) -> TopologyEditorStateResponse:
    ...


def map_ghost_to_existing_device(
    topology_id: uuid.UUID,
    ghost_id: str,
    live_device_id: uuid.UUID,
    user_id: uuid.UUID,
    session: Session,
) -> TopologyEditorStateResponse:
    ...
```

### Service rules

- `get_editor_state` returns one already-resolved canvas payload. The UI stops fetching devices, connections, diagrams, and views separately.
- `autosave_personal_draft` is an upsert on `(topology_id, user_id)` and never mutates history.
- `save_version` does three writes in one transaction:
  1. update canonical current `DiagramLayout`
  2. insert immutable `TopologyHistoryEntry`
  3. delete or rebase caller's personal draft
- `restore_history_entry` does **not** mutate the restored history row. It copies its payload into the canonical current snapshot, inserts a new history row, then returns the resolved editor state.
- `recreate_ghost_as_device` and `map_ghost_to_existing_device` are topology-level reconciliation actions. They mutate current snapshot and, if present, the caller's draft. They do not rewrite prior history rows.

### Existing services that must change

- `src/services/diagram_service.py`
  - becomes compatibility-only for legacy `/api/diagrams` consumers.
  - stop using it from the topology page.
- `src/services/topology_service.py`
  - on topology create, create the empty canonical current `DiagramLayout` row and set `current_diagram_id`.
- `src/services/device_service.py`
  - device deletion may clean the canonical current snapshot and drafts.
  - device deletion must **not** mutate `topology_history_entries`.
- `src/services/canvas_undo_service.py`
  - stop sweeping `diagram_repository.get_all_layouts(session)`.
  - target the topology's canonical current snapshot only.
- `src/services/export_service.py`, `src/services/import_service.py`, `src/services/import_service_rows.py`
  - add export/import for history and personal drafts.

---

## 7. API Layer

### New endpoints

Add router file: `src/api/routers/topology_history.py`

| Method | Path | response_model | Required role |
|---|---|---|---|
| `GET` | `/api/topologies/{topology_id}/editor-state` | `TopologyEditorStateResponse` | `Reader` |
| `GET` | `/api/topologies/{topology_id}/history` | `PaginatedTopologyHistorySummary` | `Reader` |
| `POST` | `/api/topologies/{topology_id}/history` | `TopologyHistoryResponse` | `Contributor` |
| `POST` | `/api/topologies/{topology_id}/history/{history_id}/restore` | `TopologyEditorStateResponse` | `Contributor` |
| `PUT` | `/api/topologies/{topology_id}/draft` | `TopologyDraftResponse` | `Contributor` |
| `DELETE` | `/api/topologies/{topology_id}/draft` | none (`204`) | `Contributor` |
| `POST` | `/api/topologies/{topology_id}/ghosts/{ghost_id}/recreate` | `TopologyEditorStateResponse` | `Contributor` |
| `POST` | `/api/topologies/{topology_id}/ghosts/{ghost_id}/map` | `TopologyEditorStateResponse` | `Contributor` |

### Existing routers to modify

- `src/api/app.py`
  - include the new router.
- `src/api/routers/topologies.py`
  - no new topology CRUD semantics, but `TopologyResponse` must expose `current_diagram_id` for UI and ops visibility.
- `src/api/routers/diagrams.py`
  - keep for compatibility.
  - mark as legacy in module docstring.
- `src/api/routers/views.py`
  - keep for compatibility only, not for new topology-page callers.

### Contract rule

The topology page must consume `GET /editor-state` and the new history/draft endpoints exclusively after HT-072. Do not leave any primary-canvas path on `/api/diagrams` once HT-072 is complete.

---

## 8. UI Layer

### Core pages and components

#### `src/ui/pages/topology.py`

Before:

```python
render_layout_bar(token, user_role, topology_id=topology_id, initial_layout_id=initial_layout_id)
elements, saved_layout = await load_canvas_data(token, layout_id=layout_id, topology_id=topology_id)
```

After:

```python
render_layout_bar(token, user_role, topology_id=topology_id)
editor_state = await load_editor_state(token, topology_id=topology_id)
render_canvas(editor_state["elements"], editor_state["effective_cytoscape_json"])
```

Required changes:

- `layout_id` is no longer the primary query param.
- use topology-centric editor-state loading.
- render `Save Version` and `History` in the header.
- show restore summary banner when `restore_summary` is present.
- later in HT-073, show `Draft` chip when `has_unsaved_changes` is true.

#### `src/ui/components/topology_layout_bar.py`

Keep the file name, replace the contents.

Before: selector + `Save Layout` + rename + delete.

After: `Save Version` primary button + `History` secondary button + optional `Draft` chip.

This file already exists as the intended legacy seam. Reusing it minimizes rename churn.

#### `src/ui/components/topology_layout_api.py`

Replace `get_layouts()` with topology-history and draft helpers:

- `get_editor_state()`
- `get_history()`
- `save_version()`
- `restore_version()`
- `autosave_draft()`
- `discard_draft()`

#### `src/ui/components/topology_layout_dialogs.py`

Replace save-layout/delete-layout dialogs with:

- save-version confirmation dialog (only if needed)
- restore confirmation dialog
- HT-074 leave-page modal dialog helpers

#### `src/ui/pages/workspace_detail.py`

Before:

```python
layout_id = await ensure_layout(topo_id, _auth_headers())
ui.navigate.to(f"/topology?layout_id={layout_id}&topology_id={topo_id}&workspace_id={workspace_id}")
```

After:

```python
ui.navigate.to(f"/topology?topology_id={topo_id}&workspace_id={workspace_id}")
```

Also update delete copy from `canvas data` / `views` wording to `history and drafts` where relevant.

#### `src/ui/services/topology_data.py`

This file cannot stay device-and-connection driven.

Current behavior:

- fetch latest diagram
- fetch all devices
- fetch all connections
- filter live DB rows to the saved layout

New behavior:

- fetch `GET /api/topologies/{id}/editor-state`
- trust the backend-resolved `effective_cytoscape_json`
- do not discard unknown nodes, missing devices, or historical edges on the client

#### `src/ui/services/topology_data_helpers.py`

Required change:

- stop filtering unknown saved nodes as stale.
- preserve historical nodes and edges so HT-075 can synthesize ghosts.

Current incompatible behavior:

- `merge_saved_layout()` removes saved nodes not found in live inventory.

That must become ghost-aware instead of delete-aware.

### Canvas JS files that must change in HT-072

- `src/ui/components/canvas_js_autosave.py`
  - PATCH personal draft endpoint, not `/api/diagrams/{id}`.
- `src/ui/components/canvas_js_utils.py`
  - generalize diagram globals to working-copy globals.
- `src/ui/components/canvas_events.py`
  - replace `ht:save-layout` with `ht:save-version`.
  - stop button-text lookup for `Save Layout`.
- `src/ui/components/canvas_shortcuts.py`
  - Ctrl/Cmd+S must dispatch `ht:save-version`.
- `src/ui/components/canvas_container_unconvert.py`
  - stop direct diagram PATCH calls.

### HT-074-specific UI files

- `src/ui/components/app_shell.py`
- `src/ui/components/sidebar.py`
- `src/ui/components/breadcrumb.py`
- new `src/ui/components/topology_leave_guard.py`

These are required because topology-page internal navigation is currently triggered by Python `ui.navigate.to(...)`, which bypasses any page-local browser-only guard.

### HT-075-specific UI files

- `src/ui/components/device_detail_panel.py`
- new `src/ui/components/device_detail_ghost.py`
- `src/ui/components/canvas_styles.py`
- `src/ui/components/canvas_js_interactions.py`

Ghosts should follow the existing `draft` pattern: the shared panel routes by node kind, and ghost-specific actions stay isolated in their own module.

---

## 9. Migration and Backward-Compatibility Strategy

### 9.1 Database migration sequence

1. Create `topology_history_entries`.
2. Create `topology_personal_drafts`.
3. Add `topologies.current_diagram_id` nullable FK.
4. Backfill `current_diagram_id`:
   - if a topology has legacy diagram rows, choose the canonical row by `updated_at DESC, created_at DESC, id DESC`.
   - if a topology has none, create an empty `DiagramLayout` row and point `current_diagram_id` at it.
5. Leave non-canonical legacy `diagram_layouts` rows untouched but inaccessible from the new UI.

### 9.2 Legacy multi-layout handling

Do **not** auto-convert every legacy `DiagramLayout` row into history.

Reason:

- legacy named layouts represented alternate user-managed canvases, not ordered checkpoints.
- auto-backfilling all of them into history would mis-state product meaning and create false audit chronology.

Recommended behavior:

- choose one canonical current snapshot per topology.
- history starts empty unless a later explicit `Save Version` occurs.
- keep legacy extra rows available only for compatibility/admin tooling during the transition.

### 9.3 URL compatibility

For one release cycle, keep `/topology?layout_id=...` working:

- if `layout_id` is present and `topology_id` is missing, resolve the owning topology and redirect to canonical `/topology?topology_id=...&workspace_id=...`.

### 9.4 API compatibility

- keep `/api/diagrams` and `/api/topologies/{id}/views` during HT-072..HT-075 delivery.
- remove all topology-page callers first.
- deprecate the legacy routers only after no UI or test path depends on them.

### 9.5 Import/export compatibility

- export the new history and draft tables.
- keep exporting `diagram_layouts` as the canonical current snapshot / legacy compatibility payload.
- import of old payloads without history/drafts seeds only the canonical current snapshot.

---

## 10. High-Risk Edge Cases and Review Traps

1. **Autosave target mismatch**
   If HT-072 leaves autosave on `/api/diagrams/{id}`, shared history will still be polluted by background writes.

2. **Client-side stale-node filtering**
   `src/ui/services/topology_data_helpers.py` currently drops missing saved nodes. That makes HT-075 impossible unless replaced.

3. **Device deletion mutates all layouts today**
   `src/services/device_service.py` currently removes deleted devices from every `DiagramLayout`. History rows must be exempt.

4. **Undo service sweeps all layouts**
   `src/services/canvas_undo_service.py` also iterates every diagram layout. That must become current-snapshot scoped.

5. **History cannot rely on live DB edges only**
   The current topology loader reconstructs edges from `/api/connections`. Older saved topology states will not render faithfully if the loader stays DB-driven.

6. **NiceGUI internal navigation is Python-side**
   HT-074 is not solvable with a page-local `beforeunload` handler alone. Sidebar and breadcrumb navigation must be routed through a topology-aware navigation bridge.

7. **Working-copy version propagation**
   Existing JS assumes `_htDiagramVersion` is the mutable source of truth. New draft endpoints must return fresh versions on every successful autosave, save, restore, and discard path.

8. **Reader draft creation**
   `GET /editor-state` for Readers must never lazily create a draft row.

9. **No-history topology load**
   A topology with no history and no draft must render the canonical current snapshot or an empty canvas, not the full inventory auto-layout.

10. **Ghost vs draft naming collision**
   The codebase already uses `draft` nodes and has prior story language around stale `ghost draft nodes`. HT-075 ghost placeholders need distinct CSS classes and JS detection (`ghost`, not `draft`).

11. **Recreate-as-new status ambiguity**
   If HT-075 adds a new `DeviceStatus`, the blast radius includes IPAM, inventory badges, edit forms, and canvas styles. Either scope that explicitly or reuse `Planned`.

12. **Legacy tests are copy-sensitive**
   Many tests assert literal `Saved Layouts`, `Save Layout`, and `ht:save-layout`. HT-072 must update them together, not piecemeal.

---

## 11. Files to Create / Modify

| File | Action | Purpose |
|---|---|---|
| `src/models/topology.py` | Modify | Add `current_diagram_id`. |
| `src/models/topology_history.py` | Create | Immutable history table + response schemas. |
| `src/models/topology_draft.py` | Create | Per-user draft table + response schemas. |
| `src/models/export_schema.py` | Modify | Add history and draft export payloads. |
| `src/models/types.py` | Modify (HT-075 optional) | Add `PendingReview` only if Product requires it. |
| `src/repositories/diagram_repository.py` | Modify | Canonical current-snapshot lookups only. |
| `src/repositories/topology_repository.py` | Modify | Read/write `current_diagram_id`. |
| `src/repositories/topology_history_repository.py` | Create | History list/create/get-latest helpers. |
| `src/repositories/topology_draft_repository.py` | Create | Draft get/upsert/delete helpers. |
| `src/domain/topology_history.py` | Create | Pure diff/normalize/ghost helpers. |
| `src/services/topology_service.py` | Modify | Create canonical current snapshot when a topology is created. |
| `src/services/topology_canvas_service.py` | Create | Editor-state, autosave, save-version, restore, ghost reconciliation. |
| `src/services/diagram_service.py` | Modify | Reduce to legacy compatibility role. |
| `src/services/device_service.py` | Modify | Clean current snapshot and drafts only; preserve history. |
| `src/services/canvas_undo_service.py` | Modify | Stop mutating all diagram rows. |
| `src/services/export_service.py` | Modify | Export history + drafts. |
| `src/services/import_service.py` | Modify | Include history + drafts in import orchestration. |
| `src/services/import_service_rows.py` | Modify | Insert history + drafts during import. |
| `src/api/routers/topology_history.py` | Create | New topology history/draft endpoints. |
| `src/api/routers/topologies.py` | Modify | Expose `current_diagram_id` in responses if needed. |
| `src/api/routers/diagrams.py` | Modify | Mark legacy and keep compatibility only. |
| `src/api/routers/views.py` | Modify | Mark legacy and keep compatibility only. |
| `src/api/app.py` | Modify | Register new router. |
| `src/ui/pages/topology.py` | Modify | Topology-centric editor state, save version, history panel, restore banner. |
| `src/ui/pages/workspace_detail.py` | Modify | Open topology by `topology_id`, not `layout_id`. |
| `src/ui/components/topology_layout_bar.py` | Modify | Replace layout selector with Save Version / History controls. |
| `src/ui/components/topology_layout_api.py` | Modify | Editor-state/history/draft API helpers. |
| `src/ui/components/topology_layout_dialogs.py` | Modify | Save/restore/leave dialogs. |
| `src/ui/components/canvas_js_autosave.py` | Modify | Autosave drafts instead of diagrams. |
| `src/ui/components/canvas_js_utils.py` | Modify | Working-copy globals and payload normalization. |
| `src/ui/components/canvas_events.py` | Modify | `ht:save-version` bridge instead of `ht:save-layout`. |
| `src/ui/components/canvas_shortcuts.py` | Modify | Ctrl/Cmd+S saves a version. |
| `src/ui/components/canvas_container_unconvert.py` | Modify | Stop direct diagram PATCH calls. |
| `src/ui/components/canvas_styles.py` | Modify | Ghost placeholder styling. |
| `src/ui/components/device_detail_panel.py` | Modify | Route ghost selection to a dedicated panel. |
| `src/ui/components/device_detail_ghost.py` | Create | Ghost placeholder detail actions. |
| `src/ui/services/topology_data.py` | Modify | Replace DB-driven merge flow with editor-state loading. |
| `src/ui/services/topology_data_helpers.py` | Modify | Preserve missing historical nodes/edges; no stale-node pruning. |
| `src/ui/services/topology_layout.py` | Modify | Canonical topology entry helpers; remove `ensure_layout` semantics. |
| `src/ui/components/app_shell.py` | Modify (HT-074) | Navigation bridge hook. |
| `src/ui/components/sidebar.py` | Modify (HT-074) | Route topology-page navigation through the leave guard. |
| `src/ui/components/breadcrumb.py` | Modify (HT-074) | Route topology-page breadcrumb navigation through the leave guard. |
| `src/ui/components/topology_leave_guard.py` | Create (HT-074) | Leave-page modal + browser warning integration. |
| `tests/conftest.py` | Modify | Register new models for SQLite tests. |
| `tests/unit/test_diagram_service.py` | Modify | Legacy-service coverage adjustments. |
| `tests/integration/test_diagrams_patch.py` | Modify | Legacy endpoint compatibility only. |
| `tests/unit/test_topology_layout_bar_execution.py` | Modify | Save Version / History toolbar tests. |
| `tests/unit/test_topology_data_helpers.py` | Modify | Ghost-preserving merge rules. |
| `tests/e2e/test_topology_canvas_deep.py` | Modify | Save Version + draft/history flow. |
| `tests/e2e/test_stories_e2e.py` | Modify | Remove `Saved Layouts` / `Save Layout` assertions. |

---

## 12. Test Plan

### Unit tests

- `tests/unit/test_topology_history_domain.py`
  - `normalize_cytoscape_json`
  - dirty-state detection
  - version-number increment
  - ghost synthesis for missing devices
  - ghost-to-live replacement
- `tests/unit/test_topology_canvas_service.py`
  - editor-state source selection (`saved` vs `draft`)
  - save-version clears or rebases draft
  - restore is append-only
  - reader cannot autosave or restore
- `tests/unit/test_topology_layout_bar_execution.py`
  - `Save Version` visible only to editors
  - `History` visible to all roles
  - restore button hidden for Readers
- `tests/unit/test_topology_data_helpers.py`
  - missing nodes preserved as ghosts, not filtered out

### Integration tests

- `tests/integration/test_topology_history.py`
  - list history newest-first
  - save version creates immutable entry
  - restore creates new latest entry
  - reader RBAC on save/restore
- `tests/integration/test_topology_drafts.py`
  - autosave upsert by `(topology_id, user_id)`
  - draft privacy across two users
  - discard removes only caller's draft
- `tests/integration/test_topology_editor_state.py`
  - editor-state returns latest saved when no draft exists
  - editor-state returns caller draft when present
  - reader never gets draft creation side effects
- `tests/integration/test_topology_ghost_restore.py`
  - deleted devices become ghosts on restore
  - history rows remain unchanged after restore
  - recreate/map endpoints update current snapshot only

### E2E / Playwright

- open topology from workspace detail with no `layout_id`
- Save Version creates a new history row and marks it current
- autosave survives refresh for the same user and stays private from another user
- leaving with unsaved draft shows modal on sidebar/breadcrumb navigation and browser-native warning on tab close
- restoring an older version with deleted devices shows ghosts and banner, then supports one-by-one reconciliation

### Fixtures

Use existing fixtures from `tests/conftest.py`:

- `session`
- `client`
- `admin_token`
- `contributor_token`
- `reader_token`

Add new model registrations in `tests/conftest.py` for:

- `TopologyHistoryEntry`
- `TopologyPersonalDraft`

---

## 13. Final Recommendation

HT-072 should **not** be implemented in isolation on top of the legacy mutable-layout flow.

Ship HT-072 with a thin shared foundation:

- immutable history table
- per-user draft table
- topology-centric editor-state API
- autosave rerouted to drafts immediately
- canonical current snapshot per topology

Then deliver the visible draft UX in HT-073, the leave guard in HT-074, and ghost reconciliation in HT-075 without rewriting the storage or load path a second time.
