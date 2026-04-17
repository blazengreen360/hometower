# RFC: Workspaces, Topologies, and Views — 3-Level Navigation Hierarchy

**Story:** HT-047
**Status:** Draft — awaiting Feature-Engineer implementation
**Date:** 2026-04-12
**Author:** Architect

---

## 1. Overview

HT-047 introduces a 3-level organisational hierarchy for diagrams:

```
Workspace  (user-scoped organiser group)
  └── Topology  (a subject, e.g. "Home Lab")
        └── View  (a canvas perspective — the existing DiagramLayout)
```

Today `DiagramLayout` is a flat global list. This RFC adds `Workspace` and `Topology` as new entities, then links `DiagramLayout` to a `Topology` via a new `topology_id` FK. The UI refers to `DiagramLayout` as "View"; the internal model name stays `DiagramLayout` to avoid a risky table rename.

Devices remain global inventory — Views are manually-curated canvas perspectives that reference devices but do not own them.

**Hidden design decisions (Parnas test):**
- `src/models/workspace.py` hides the Workspace schema — if we later add `description` or `icon`, only this file changes.
- `src/models/topology.py` hides the Topology schema — if we later add `topology_type` or `description`, only this file changes.
- `src/domain/workspaces.py` hides name validation rules — if we add profanity filtering or length constraints, only this file changes.
- `src/repositories/workspace_repository.py` hides the query strategy — if we later add full-text search or pagination changes, only this file changes.
- `src/services/workspace_service.py` hides the "auto-create defaults" orchestration — if we change the trigger (migration vs. first-access), only this file changes.

---

## 2. Data Model Changes

### 2.1 New file: `src/models/workspace.py`

```
WorkspaceBase(SQLModel):
    name: str           — Field(min_length=1, max_length=255)

Workspace(WorkspaceBase, table=True):
    __tablename__ = "workspaces"
    id: uuid.UUID       — Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID — Field(foreign_key="users.id")
    created_at: datetime
    updated_at: datetime

WorkspaceCreate(SQLModel):
    name: str           — Field(min_length=1, max_length=255)

WorkspaceUpdate(SQLModel):
    name: Optional[str] — Field(default=None, min_length=1, max_length=255)

WorkspaceResponse(WorkspaceBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    topology_count: int = 0
    created_at: datetime
    updated_at: datetime

WorkspaceSummary(SQLModel):
    id: uuid.UUID
    name: str
    topology_count: int = 0
    last_modified: datetime     — max(workspace.updated_at, latest topology.updated_at)

PaginatedWorkspaceSummary(SQLModel):
    items: list[WorkspaceSummary]
    total: int
    page: int
    limit: int
```

**Constraints:**
- `UniqueConstraint("owner_id", "name", name="uq_workspace_owner_name")` — a user cannot have two workspaces with the same name.
- `owner_id` FK to `users.id` with `ON DELETE CASCADE` — when a user is deleted, their workspaces are cleaned up.

### 2.2 New file: `src/models/topology.py`

```
TopologyBase(SQLModel):
    name: str           — Field(min_length=1, max_length=255)
    tags: list[str]     — Field(sa_column=Column(JSON), default=[])

Topology(TopologyBase, table=True):
    __tablename__ = "topologies"
    id: uuid.UUID       — Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID — Field(foreign_key="workspaces.id", ondelete="CASCADE")
    created_at: datetime
    updated_at: datetime

TopologyCreate(SQLModel):
    name: str           — Field(min_length=1, max_length=255)
    tags: list[str]     — Field(default=[])

TopologyUpdate(SQLModel):
    name: Optional[str] — Field(default=None, min_length=1, max_length=255)
    tags: Optional[list[str]] = None

TopologyResponse(TopologyBase):
    id: uuid.UUID
    workspace_id: uuid.UUID
    view_count: int = 0
    created_at: datetime
    updated_at: datetime

TopologySummary(SQLModel):
    id: uuid.UUID
    name: str
    tags: list[str]
    view_count: int = 0
    last_modified: datetime

PaginatedTopologySummary(SQLModel):
    items: list[TopologySummary]
    total: int
    page: int
    limit: int
```

**Constraints:**
- `UniqueConstraint("workspace_id", "name", name="uq_topology_workspace_name")` — no duplicate topology names within a workspace.
- `workspace_id` FK to `workspaces.id` with `ON DELETE CASCADE`.

### 2.3 Modified file: `src/models/diagram.py`

Add `topology_id` to the `DiagramLayout` table model:

```
DiagramLayout — add:
    topology_id: Optional[uuid.UUID] — Field(
        default=None,
        foreign_key="topologies.id",
        sa_column_kwargs={"ondelete": "CASCADE"},
    )
```

- `topology_id` is nullable during migration (existing rows have no topology yet). After the backfill migration (023), all rows will have a value. Future `DiagramLayoutCreate` will require `topology_id`.
- `ON DELETE CASCADE`: deleting a Topology deletes all its Views (DiagramLayouts). Devices in global inventory are never touched.
- Add index `ix_diagram_layouts_topology_id` on `(topology_id)`.

Add `topology_id` to `DiagramLayoutCreate`:

```
DiagramLayoutCreate — add:
    topology_id: Optional[uuid.UUID] = None
```

Nullable for backward compat with existing canvas autosave endpoint. Service layer will reject `None` for new creation flows (via the workspace/topology routers) while preserving compat for `/api/diagrams/` autosave.

Add `topology_id` to `DiagramLayoutResponse` and `DiagramLayoutSummary`:

```
DiagramLayoutResponse — add:
    topology_id: Optional[uuid.UUID] = None

DiagramLayoutSummary — add:
    topology_id: Optional[uuid.UUID] = None
```

### 2.4 Cascade summary

```
User  --[ON DELETE CASCADE]--> Workspace
Workspace --[ON DELETE CASCADE]--> Topology
Topology  --[ON DELETE CASCADE]--> DiagramLayout (View)
```

Devices are global — never cascaded from any of these entities.

---

## 3. Migration Plan

Three migrations, applied in order. All are additive (no destructive changes).

### Migration 021 — `021_create_workspaces.py`

**Revises:** `020`

1. **Create table `workspaces`:**
   - `id` UUID PK, NOT NULL, default `gen_random_uuid()`
   - `name` VARCHAR(255) NOT NULL
   - `owner_id` UUID NOT NULL, FK → `users.id` ON DELETE CASCADE
   - `created_at` TIMESTAMP WITH TIME ZONE NOT NULL, default `now()`
   - `updated_at` TIMESTAMP WITH TIME ZONE NOT NULL, default `now()`
2. **Create unique constraint:** `uq_workspace_owner_name` on `(owner_id, name)`.
3. **Create index:** `ix_workspaces_owner_id` on `(owner_id)`.

```python
def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE",
                                name="fk_workspaces_owner_id"),
        sa.UniqueConstraint("owner_id", "name", name="uq_workspace_owner_name"),
    )
    op.create_index("ix_workspaces_owner_id", "workspaces", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_workspaces_owner_id", table_name="workspaces")
    op.drop_table("workspaces")
```

### Migration 022 — `022_create_topologies.py`

**Revises:** `021`

1. **Create table `topologies`:**
   - `id` UUID PK, NOT NULL
   - `name` VARCHAR(255) NOT NULL
   - `workspace_id` UUID NOT NULL, FK → `workspaces.id` ON DELETE CASCADE
   - `tags` JSON, default `'[]'`
   - `created_at` TIMESTAMP WITH TIME ZONE NOT NULL
   - `updated_at` TIMESTAMP WITH TIME ZONE NOT NULL
2. **Create unique constraint:** `uq_topology_workspace_name` on `(workspace_id, name)`.
3. **Create index:** `ix_topologies_workspace_id` on `(workspace_id)`.

```python
def upgrade() -> None:
    op.create_table(
        "topologies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tags", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"],
                                ondelete="CASCADE",
                                name="fk_topologies_workspace_id"),
        sa.UniqueConstraint("workspace_id", "name",
                            name="uq_topology_workspace_name"),
    )
    op.create_index("ix_topologies_workspace_id", "topologies", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_topologies_workspace_id", table_name="topologies")
    op.drop_table("topologies")
```

### Migration 023 — `023_add_topology_id_to_diagram_layouts.py`

**Revises:** `022`

Three-phase migration:

1. **Add column** — `diagram_layouts.topology_id` UUID NULL, FK → `topologies.id` ON DELETE CASCADE.
2. **Backfill** — For each distinct user who owns diagram layouts (determined by cross-referencing creation metadata or, since `diagram_layouts` currently has no `owner_id`, assign all existing layouts to the first admin user):
   - Insert one "Default Workspace" row into `workspaces` for each user.
   - Insert one "Default Topology" row into `topologies` for that workspace.
   - `UPDATE diagram_layouts SET topology_id = <default_topology_id> WHERE topology_id IS NULL`.
3. **Create index** — `ix_diagram_layouts_topology_id` on `(topology_id)`.

**Important backfill note:** The current `DiagramLayout` has no `owner_id` or user association. The backfill assigns ALL existing diagram layouts to a single "Default Workspace" owned by the first admin user (the one created at startup from `ADMIN_EMAIL`). This is safe because the current system is effectively single-user (no workspace concept existed). Users can reorganise after migration.

```python
def upgrade() -> None:
    # Phase 1: add nullable column
    op.add_column(
        "diagram_layouts",
        sa.Column("topology_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_diagram_layouts_topology_id",
        "diagram_layouts", "topologies",
        ["topology_id"], ["id"],
        ondelete="CASCADE",
    )

    # Phase 2: backfill — create Default Workspace + Topology for admin,
    # assign all orphan layouts
    conn = op.get_bind()

    # Find the first admin user
    admin = conn.execute(sa.text(
        "SELECT id FROM users WHERE role = 'Admin' ORDER BY created_at LIMIT 1"
    )).fetchone()

    if admin is not None:
        admin_id = admin[0]
        ws_id = conn.execute(sa.text(
            "INSERT INTO workspaces (id, name, owner_id) "
            "VALUES (gen_random_uuid(), 'Default Workspace', :owner_id) "
            "RETURNING id"
        ), {"owner_id": admin_id}).fetchone()[0]

        topo_id = conn.execute(sa.text(
            "INSERT INTO topologies (id, name, workspace_id) "
            "VALUES (gen_random_uuid(), 'Default Topology', :ws_id) "
            "RETURNING id"
        ), {"ws_id": ws_id}).fetchone()[0]

        conn.execute(sa.text(
            "UPDATE diagram_layouts SET topology_id = :topo_id "
            "WHERE topology_id IS NULL"
        ), {"topo_id": topo_id})

    # Phase 3: index
    op.create_index(
        "ix_diagram_layouts_topology_id", "diagram_layouts", ["topology_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_diagram_layouts_topology_id", table_name="diagram_layouts")
    op.drop_constraint(
        "fk_diagram_layouts_topology_id", "diagram_layouts", type_="foreignkey"
    )
    op.drop_column("diagram_layouts", "topology_id")
    # Note: Default Workspace/Topology rows remain but are harmless
```

**DevOps-Engineer migration review required** — new FK on a production table + data backfill in same transaction.

---

## 4. Domain Layer

### 4.1 New file: `src/domain/workspaces.py`

Pure Python, stdlib-only. No SQLModel, no FastAPI, no I/O.

**`validate_workspace_name(name: str) -> str`**
- Strip whitespace, reject empty string after strip.
- Reject names longer than 255 characters.
- Return the stripped name.

**`validate_topology_name(name: str) -> str`**
- Same rules as `validate_workspace_name`. Separate function for independent evolution.
- Return the stripped name.

**`validate_view_name(name: str) -> str`**
- Same rules. Validates the display name for DiagramLayout when created through the Views flow.
- Return the stripped name.

Each function raises `ValueError` with a descriptive message on failure. The service layer catches `ValueError` and maps to `HTTPException(400)`.

**Rationale for three separate functions:** Even though the logic is identical today, the Parnas principle dictates that each entity's validation rules should be independently evolvable. Workspace names may later require uniqueness across the org (Phase 2), topology names may gain type-specific constraints, and view names may need to avoid reserved words.

---

## 5. Repository Layer

### 5.1 New file: `src/repositories/workspace_repository.py`

All functions follow the existing `diagram_repository.py` pattern: receive a `Session`, return model instances, never raise HTTP exceptions.

**`create(session, workspace: Workspace) -> Workspace`**
- `session.add()`, `session.flush()`, `session.refresh()`, return.

**`get_by_id(session, workspace_id: uuid.UUID) -> Workspace | None`**
- `session.get(Workspace, workspace_id)`.

**`get_by_owner(session, owner_id: uuid.UUID, page: int, limit: int) -> tuple[list[Workspace], int]`**
- `SELECT * FROM workspaces WHERE owner_id = ? ORDER BY updated_at DESC` with pagination.
- Returns `(items, total_count)`.

**`get_by_owner_and_name(session, owner_id: uuid.UUID, name: str) -> Workspace | None`**
- Used for duplicate-name checks before create/rename.

**`update(session, workspace: Workspace) -> Workspace`**
- Same pattern as `diagram_repository.update`.

**`delete(session, workspace: Workspace) -> None`**
- `session.delete()`, `session.flush()`. CASCADE handles children.

**`count_topologies(session, workspace_id: uuid.UUID) -> int`**
- `SELECT COUNT(*) FROM topologies WHERE workspace_id = ?`.
- Used to populate `topology_count` in responses.

### 5.2 New file: `src/repositories/topology_repository.py`

**`create(session, topology: Topology) -> Topology`**

**`get_by_id(session, topology_id: uuid.UUID) -> Topology | None`**

**`get_by_workspace(session, workspace_id: uuid.UUID, page: int, limit: int) -> tuple[list[Topology], int]`**
- `SELECT * FROM topologies WHERE workspace_id = ? ORDER BY updated_at DESC` with pagination.

**`get_by_workspace_and_name(session, workspace_id: uuid.UUID, name: str) -> Topology | None`**
- Duplicate-name check.

**`update(session, topology: Topology) -> Topology`**

**`delete(session, topology: Topology) -> None`**

**`count_views(session, topology_id: uuid.UUID) -> int`**
- `SELECT COUNT(*) FROM diagram_layouts WHERE topology_id = ?`.

### 5.3 Modified file: `src/repositories/diagram_repository.py`

**Add: `get_by_topology(session, topology_id: uuid.UUID, page: int, limit: int) -> tuple[list[DiagramLayout], int]`**
- `SELECT * FROM diagram_layouts WHERE topology_id = ? ORDER BY updated_at DESC` with pagination.

**Add: `count_by_topology(session, topology_id: uuid.UUID) -> int`**
- `SELECT COUNT(*) FROM diagram_layouts WHERE topology_id = ?`.

Existing functions (`create`, `get_by_id`, `get_all`, `update`, `delete`) are unchanged — they remain for backward compatibility with the existing `/api/diagrams/` endpoints.

---

## 6. Service Layer

### 6.1 New file: `src/services/workspace_service.py`

**`create(owner_id: uuid.UUID, data: WorkspaceCreate, session: Session) -> Workspace`**
- Validate name via `domain.workspaces.validate_workspace_name`.
- Check uniqueness via `workspace_repository.get_by_owner_and_name`; raise 409 if duplicate.
- Persist, commit, log, return.

**`get_or_create_default(owner_id: uuid.UUID, session: Session) -> Workspace`**
- Look for a workspace named "Default Workspace" owned by `owner_id`.
- If not found: create it, also create a "Default Topology" inside it.
- Return the workspace.
- Called on first navigation to `/workspaces` when user has zero workspaces.

**`get_by_id(workspace_id: uuid.UUID, owner_id: uuid.UUID, session: Session) -> Workspace`**
- Fetch by ID, verify `owner_id` matches. Raise 404 if not found or not owned.

**`get_all(owner_id: uuid.UUID, session: Session, page: int, limit: int) -> tuple[list[Workspace], int]`**
- Delegates to `workspace_repository.get_by_owner`.

**`rename(workspace_id: uuid.UUID, owner_id: uuid.UUID, data: WorkspaceUpdate, session: Session) -> Workspace`**
- Validate name, check uniqueness, update, commit.

**`delete(workspace_id: uuid.UUID, owner_id: uuid.UUID, session: Session) -> None`**
- Verify ownership. Delete workspace (CASCADE handles topologies and views).
- Log the deletion.

### 6.2 New file: `src/services/topology_service.py`

**`create(workspace_id: uuid.UUID, owner_id: uuid.UUID, data: TopologyCreate, session: Session) -> Topology`**
- Verify workspace exists and is owned by caller.
- Validate name via `domain.workspaces.validate_topology_name`.
- Check uniqueness within workspace.
- Persist, commit, log, return.

**`get_by_id(topology_id: uuid.UUID, owner_id: uuid.UUID, session: Session) -> Topology`**
- Fetch by ID, verify ownership by joining through workspace. Raise 404 if not found or not owned.

**`get_by_workspace(workspace_id: uuid.UUID, owner_id: uuid.UUID, session: Session, page: int, limit: int) -> tuple[list[Topology], int]`**
- Verify workspace ownership first, then delegate to `topology_repository.get_by_workspace`.

**`rename(topology_id: uuid.UUID, owner_id: uuid.UUID, data: TopologyUpdate, session: Session) -> Topology`**
- Validate, check uniqueness, update, commit.

**`update_tags(topology_id: uuid.UUID, owner_id: uuid.UUID, tags: list[str], session: Session) -> Topology`**
- Verify ownership, update `tags` JSON array, commit.

**`delete(topology_id: uuid.UUID, owner_id: uuid.UUID, session: Session) -> None`**
- Verify ownership. Delete (CASCADE handles views). Log.

### 6.3 Modified file: `src/services/diagram_service.py`

**`create()` — extend:**
- Accept optional `topology_id`. When provided, validate that the topology exists via `topology_repository.get_by_id`.
- Set `layout.topology_id = topology_id`.
- The existing autosave path (called from `/api/diagrams/`) may omit `topology_id` for backward compat.

**`get_by_topology(topology_id: uuid.UUID, session: Session, page: int, limit: int) -> tuple[list[DiagramLayout], int]`**
- New method. Delegates to `diagram_repository.get_by_topology`.

No changes to `update`, `partial_update`, `delete`, or `update_timestamp` — they operate on `DiagramLayout` by ID regardless of topology.

### 6.4 Ownership verification pattern

All workspace/topology service methods that take `owner_id` verify that the requesting user owns the resource. This is enforced at the service layer, not the repository layer, so that:
- Repositories remain generic query functions.
- The ownership check is testable in isolation.
- Phase 2 (LT-004) can extend the check to include team membership without modifying the repository.

---

## 7. API Contracts

### 7.1 New file: `src/api/routers/workspaces.py`

**Router prefix:** `/workspaces`, **tags:** `["workspaces"]`

| Method | Path | Auth | Request Body | Response | Status | Description |
|---|---|---|---|---|---|---|
| `GET` | `/` | Reader | — | `PaginatedWorkspaceSummary` | 200 | List caller's workspaces |
| `POST` | `/` | Contributor | `WorkspaceCreate` | `WorkspaceResponse` | 201 | Create workspace |
| `GET` | `/{workspace_id}` | Reader | — | `WorkspaceResponse` | 200 | Get workspace detail |
| `PATCH` | `/{workspace_id}` | Contributor | `WorkspaceUpdate` | `WorkspaceResponse` | 200 | Rename workspace |
| `DELETE` | `/{workspace_id}` | Admin | — | — | 204 | Delete workspace + cascade |

**Query params for `GET /`:**
- `page: int = 1` (ge=1)
- `limit: int = 50` (ge=1, le=100)
- `search: Optional[str] = None` — case-insensitive `ILIKE` on `name`.

**Auto-default behavior:** `GET /` checks if the caller has zero workspaces; if so, calls `workspace_service.get_or_create_default(owner_id)` before returning results.

**Ownership:** All endpoints filter by `owner_id` extracted from the JWT. A user never sees another user's workspaces.

### 7.2 New file: `src/api/routers/topologies.py`

**Router prefix:** `/workspaces/{workspace_id}/topologies`, **tags:** `["topologies"]`

| Method | Path | Auth | Request Body | Response | Status | Description |
|---|---|---|---|---|---|---|
| `GET` | `/` | Reader | — | `PaginatedTopologySummary` | 200 | List topologies in workspace |
| `POST` | `/` | Contributor | `TopologyCreate` | `TopologyResponse` | 201 | Create topology |

**Standalone topology routes (prefix `/topologies`):**

| Method | Path | Auth | Request Body | Response | Status | Description |
|---|---|---|---|---|---|---|
| `GET` | `/{topology_id}` | Reader | — | `TopologyResponse` | 200 | Get topology detail |
| `PATCH` | `/{topology_id}` | Contributor | `TopologyUpdate` | `TopologyResponse` | 200 | Rename / update tags |
| `DELETE` | `/{topology_id}` | Admin | — | — | 204 | Delete topology + cascade |

**Query params for `GET /` (nested):**
- `page`, `limit`, `search` — same as workspaces.

### 7.3 New file: `src/api/routers/views.py`

**Router prefix:** `/topologies/{topology_id}/views`, **tags:** `["views"]`

| Method | Path | Auth | Request Body | Response | Status | Description |
|---|---|---|---|---|---|---|
| `GET` | `/` | Reader | — | `PaginatedDiagramSummary` | 200 | List views in topology |
| `POST` | `/` | Contributor | `DiagramLayoutCreate` | `DiagramLayoutResponse` | 201 | Create view |

**Standalone view routes:** Use the existing `/api/diagrams/{id}` endpoints for GET/PATCH/PUT/DELETE of individual views. No duplication.

The `POST /topologies/{topology_id}/views/` endpoint sets `topology_id` from the path param, overriding any value in the body. This ensures views are always created within a topology context.

### 7.4 Modified file: `src/api/app.py`

Register new routers:

```python
from src.api.routers.workspaces import router as workspaces_router
from src.api.routers.topologies import (
    nested_router as topologies_nested_router,
    standalone_router as topologies_standalone_router,
)
from src.api.routers.views import router as views_router

app.include_router(workspaces_router, prefix="/api")
app.include_router(topologies_nested_router, prefix="/api")
app.include_router(topologies_standalone_router, prefix="/api")
app.include_router(views_router, prefix="/api")
```

### 7.5 Backward compatibility

The existing `/api/diagrams/` endpoints remain fully functional:
- `GET /api/diagrams/` — returns all diagram layouts (now includes `topology_id` in responses).
- `POST /api/diagrams/` — still works without `topology_id` for canvas autosave.
- `PUT/PATCH/DELETE /api/diagrams/{id}` — unchanged.

The new `/api/topologies/{id}/views/` endpoints are the recommended creation path going forward.

---

## 8. UI Pages

### 8.1 New file: `src/ui/pages/workspaces.py`

**Route:** `/workspaces`

- Page title: "Workspaces"
- Breadcrumb: `Workspaces` (root level, no parent)
- "New Workspace" button: top-right, primary action, >= 44px height.
- Table columns: Name (clickable link to `/workspaces/{id}`), Topologies (count), Last Modified, Actions (overflow menu: Rename, Delete).
- Search input: visible when > 10 rows, filters by name client-side.
- Empty state: auto-created "Default Workspace" (via service call on page load).
- Rename action: opens dialog with name input, calls `PATCH /api/workspaces/{id}`.
- Delete action: confirmation dialog warning that all topologies and views will be deleted, calls `DELETE /api/workspaces/{id}`.

### 8.2 New file: `src/ui/pages/workspace_detail.py`

**Route:** `/workspaces/{workspace_id}`

- Page title: workspace name
- Breadcrumb: `Workspaces > {workspace name}`
- "New Topology" button: top-right, primary action.
- Table columns: Name, Views (count), Tags (pill badges), Last Modified, Actions (Open, Rename, Delete, Tag).
- "Open" navigates to `/workspaces/{wid}/topologies/{tid}`.
- "Tag" action: opens dialog to edit the `tags` JSON array.
- Delete confirmation warns about cascading view deletion.
- Search input: visible when > 10 rows.

### 8.3 New file: `src/ui/pages/topology_detail.py`

**Route:** `/workspaces/{workspace_id}/topologies/{topology_id}`

- Page title: topology name
- Breadcrumb: `Workspaces > {workspace name} > {topology name}`
- "New View" button: top-right, primary action.
- Table columns: Name, Last Modified, Actions (Open, Rename, Delete).
- "Open" navigates to `/topology/{view_id}` (existing View Designer route from HT-048).
- "New View" dialog: prompts for name, calls `POST /api/topologies/{tid}/views/` with empty `cytoscape_json: {"elements": {"nodes": [], "edges": []}}`.
- Delete confirmation: warns that canvas data will be deleted but devices in inventory are unaffected.
- Search input: visible when > 10 rows.

### 8.4 Breadcrumb component

**New file: `src/ui/components/breadcrumb.py`**

A reusable breadcrumb component that accepts a list of `(label, route)` tuples and renders them as clickable links separated by ">". Used by all three new pages.

```python
def render_breadcrumb(crumbs: list[tuple[str, str]]) -> None:
    """Render a breadcrumb bar. Each crumb is (label, route)."""
    ...
```

### 8.5 Modified file: `src/ui/components/sidebar.py`

Update `_NAV_ITEMS` to replace "Topology" with "Workspaces":

```python
_NAV_ITEMS = [
    {"label": "Dashboard", "route": "/", "icon": "dashboard"},
    {"label": "Workspaces", "route": "/workspaces", "icon": "workspaces"},
    {"label": "Inventory", "route": "/inventory", "icon": "inventory_2"},
    {"label": "Map", "route": "/map", "icon": "map", "disabled": "true"},
]
```

The old `/topology` route continues to work (it's the View Designer for a specific view) but is no longer a top-level nav item. Users reach it via Workspaces > Workspace > Topology > Open View.

### 8.6 Dialog components

**New file: `src/ui/components/dialogs/name_dialog.py`**

A reusable "enter a name" dialog used for Create Workspace, Create Topology, Create View, Rename Workspace, Rename Topology. Accepts a title, placeholder, optional current value (for rename), and a callback.

This avoids duplicating dialog logic across three pages.

---

## 9. File List

| File | Action | Purpose |
|---|---|---|
| `src/models/workspace.py` | CREATE | Workspace model + Pydantic schemas |
| `src/models/topology.py` | CREATE | Topology model + Pydantic schemas |
| `src/models/diagram.py` | MODIFY | Add `topology_id` to DiagramLayout, DiagramLayoutCreate, DiagramLayoutResponse, DiagramLayoutSummary |
| `src/domain/workspaces.py` | CREATE | Pure validation: `validate_workspace_name`, `validate_topology_name`, `validate_view_name` |
| `src/repositories/workspace_repository.py` | CREATE | CRUD for Workspace |
| `src/repositories/topology_repository.py` | CREATE | CRUD for Topology |
| `src/repositories/diagram_repository.py` | MODIFY | Add `get_by_topology`, `count_by_topology` |
| `src/services/workspace_service.py` | CREATE | Workspace orchestration + auto-default |
| `src/services/topology_service.py` | CREATE | Topology orchestration |
| `src/services/diagram_service.py` | MODIFY | Extend `create` with `topology_id`; add `get_by_topology` |
| `src/api/routers/workspaces.py` | CREATE | Workspace CRUD endpoints |
| `src/api/routers/topologies.py` | CREATE | Topology CRUD endpoints (nested + standalone) |
| `src/api/routers/views.py` | CREATE | View list/create under topology |
| `src/api/app.py` | MODIFY | Register new routers |
| `src/ui/pages/workspaces.py` | CREATE | Workspace list page |
| `src/ui/pages/workspace_detail.py` | CREATE | Topology table for one workspace |
| `src/ui/pages/topology_detail.py` | CREATE | Views table for one topology |
| `src/ui/components/breadcrumb.py` | CREATE | Reusable breadcrumb component |
| `src/ui/components/dialogs/name_dialog.py` | CREATE | Reusable name input dialog |
| `src/ui/components/sidebar.py` | MODIFY | Replace "Topology" nav item with "Workspaces" |
| `alembic/versions/021_create_workspaces.py` | CREATE | Workspaces table |
| `alembic/versions/022_create_topologies.py` | CREATE | Topologies table |
| `alembic/versions/023_add_topology_id_to_diagram_layouts.py` | CREATE | Add topology_id FK + backfill |
| `tests/unit/test_workspaces_domain.py` | CREATE | Domain validation tests |
| `tests/unit/test_workspace_service.py` | CREATE | Workspace service tests |
| `tests/unit/test_topology_service.py` | CREATE | Topology service tests |
| `tests/integration/test_workspaces.py` | CREATE | Workspace API integration tests |
| `tests/integration/test_topologies.py` | CREATE | Topology API integration tests |
| `tests/integration/test_views.py` | CREATE | View list/create API integration tests |

**File size estimate:** All new source files target < 150 lines. The largest will be the service files (~120 lines each) and the UI pages (~150 lines each). None should approach the 250-line soft limit.

---

## 10. Dependency Graph

```
Level 0 (already exists):
  ├─ src/models/types.py
  ├─ src/models/user.py
  ├─ src/models/diagram.py
  └─ src/utils/db.py

Level 1 (depends only on Level 0):
  ├─ alembic/versions/021_create_workspaces.py
  ├─ src/models/workspace.py
  └─ src/domain/workspaces.py            ← pure validation, no deps

Level 2 (depends on Level 1):
  ├─ alembic/versions/022_create_topologies.py
  ├─ src/models/topology.py
  └─ src/repositories/workspace_repository.py

Level 3 (depends on Level 2):
  ├─ alembic/versions/023_add_topology_id_to_diagram_layouts.py
  ├─ src/repositories/topology_repository.py
  ├─ src/repositories/diagram_repository.py  ← add get_by_topology
  └─ src/services/workspace_service.py

Level 4 (depends on Level 3):
  ├─ src/services/topology_service.py
  ├─ src/services/diagram_service.py         ← extend create
  └─ src/models/diagram.py                   ← add topology_id fields

Level 5 (depends on Level 4):
  ├─ src/api/routers/workspaces.py
  ├─ src/api/routers/topologies.py
  ├─ src/api/routers/views.py
  └─ src/api/app.py                          ← register routers

Level 6 (depends on Level 5, parallel tracks):
  ├─ tests/unit/test_workspaces_domain.py    ← TDD write-first at Level 1
  ├─ tests/unit/test_workspace_service.py
  ├─ tests/unit/test_topology_service.py
  ├─ tests/integration/test_workspaces.py
  ├─ tests/integration/test_topologies.py
  └─ tests/integration/test_views.py

Level 7 (depends on Level 5 — UI parallel track):
  ├─ src/ui/components/breadcrumb.py
  ├─ src/ui/components/dialogs/name_dialog.py
  ├─ src/ui/pages/workspaces.py
  ├─ src/ui/pages/workspace_detail.py
  ├─ src/ui/pages/topology_detail.py
  └─ src/ui/components/sidebar.py            ← nav update
```

**Critical path:** migrations (021-023) --> models --> domain --> repositories --> services --> routers --> UI pages.

**Parallelization opportunities:**
- Domain validation tests (Level 1) can be written TDD-style before the function bodies.
- UI pages (Level 7) can begin once the API contract (Level 5) is stable, in parallel with integration tests.
- Breadcrumb and dialog components (Level 7) have no API dependency and can be built immediately.

---

## 11. Non-Goals (reaffirmed from HT-047)

- **No sharing of Workspaces, Topologies, or Views between users.** Phase 2 / LT-004 introduces team access control. This story is single-user organisational grouping only.
- **No workspace-level RBAC beyond existing system roles.** Admin/Contributor/Reader apply system-wide; no per-workspace role overrides.
- **No canvas thumbnail previews.** Future delighter — would require server-side Cytoscape rendering or client-side screenshot capture.
- **No drag-and-drop reordering of rows.** Tables are sorted by `updated_at DESC`. Manual ordering is a future delighter.
- **No Topology or View duplication/clone.** Future story. Clone would require deep-copying `cytoscape_json` and optionally the device references within it.
- **No migration to make `topology_id` NOT NULL.** The column stays nullable to preserve backward compat with the existing `/api/diagrams/` autosave flow. A future cleanup migration can enforce NOT NULL once all creation paths go through the workspace hierarchy.

---

## 12. Validation

| Constraint | Test |
|---|---|
| `validate_workspace_name` rejects empty/whitespace-only | `test_workspaces_domain.py::test_empty_name_rejected` |
| `validate_workspace_name` strips whitespace | `test_workspaces_domain.py::test_name_stripped` |
| `validate_topology_name` rejects empty | `test_workspaces_domain.py::test_topology_empty_name` |
| `validate_view_name` rejects empty | `test_workspaces_domain.py::test_view_empty_name` |
| `POST /api/workspaces/` creates workspace for caller | `test_workspaces.py::test_create_workspace` |
| `POST /api/workspaces/` with duplicate name → 409 | `test_workspaces.py::test_duplicate_name_rejected` |
| `GET /api/workspaces/` returns only caller's workspaces | `test_workspaces.py::test_list_own_workspaces_only` |
| `GET /api/workspaces/` with zero workspaces auto-creates default | `test_workspaces.py::test_auto_create_default` |
| `PATCH /api/workspaces/{id}` renames workspace | `test_workspaces.py::test_rename_workspace` |
| `DELETE /api/workspaces/{id}` cascades to topologies and views | `test_workspaces.py::test_delete_cascades` |
| `DELETE /api/workspaces/{id}` by non-owner → 404 | `test_workspaces.py::test_delete_not_owned` |
| `POST /api/workspaces/{id}/topologies/` creates topology | `test_topologies.py::test_create_topology` |
| `POST` with duplicate topology name in workspace → 409 | `test_topologies.py::test_duplicate_name_rejected` |
| `GET /api/workspaces/{id}/topologies/` lists topologies | `test_topologies.py::test_list_topologies` |
| `PATCH /api/topologies/{id}` renames topology | `test_topologies.py::test_rename_topology` |
| `PATCH /api/topologies/{id}` updates tags | `test_topologies.py::test_update_tags` |
| `DELETE /api/topologies/{id}` cascades to views | `test_topologies.py::test_delete_cascades_views` |
| `POST /api/topologies/{id}/views/` creates view with topology_id | `test_views.py::test_create_view` |
| `GET /api/topologies/{id}/views/` lists views for topology | `test_views.py::test_list_views` |
| Existing `POST /api/diagrams/` still works without topology_id | `test_views.py::test_backward_compat_autosave` |
| Migration 023 backfill assigns all orphan layouts to default topology | `test_views.py::test_migration_backfill` |
| `GET /api/workspaces/?search=foo` filters by name | `test_workspaces.py::test_search_filter` |
| All source files <= 250 lines | `find src/ -name "*.py" ! -path "*/tests/*" \| xargs wc -l` |
| Type check | `docker compose exec api mypy src/ --ignore-missing-imports` |
| All tests pass | `docker compose exec api pytest` |
| Images build clean | `docker compose build` |

---

## 13. Security Boundaries

- **Ownership isolation:** Every workspace is scoped to `owner_id`. Service-layer methods verify `workspace.owner_id == caller_id` before any read or write. A user cannot access, modify, or delete another user's workspaces, topologies, or views. The 404 response (not 403) prevents enumeration.
- **CASCADE safety:** Deleting a workspace cascades through topologies to views. The DB enforces this via FK constraints. Device records in global inventory are never touched — no FK from devices to workspaces/topologies.
- **UUID path params:** All IDs are UUIDs, resistant to enumeration.
- **RBAC:** Workspace/topology creation requires `Contributor`. Deletion requires `Admin`. Read requires `Reader`. These mirror the existing device endpoint RBAC pattern.
- **Name validation:** Input names are validated via Pydantic `min_length=1, max_length=255` and domain-layer strip + reject-empty. No SQL injection risk — all queries use parameterized statements via SQLModel.
- **No PII introduced.** Workspace/topology names are user-chosen labels. `owner_id` is already present in the JWT; no new PII fields.

---

## 14. Open Risks

1. **`topology_id` nullable on `diagram_layouts`.** Existing autosave creates layouts without a topology context. Until all UI flows route through the workspace hierarchy, some layouts may have `topology_id = NULL`. Mitigation: the `GET /api/workspaces/` auto-default flow ensures users always have a workspace/topology to assign to. A future cleanup migration can enforce NOT NULL once confirmed safe.

2. **Backfill assigns all layouts to first admin.** If multiple users existed pre-migration (unlikely for v1 homelabs, but possible), all their layouts end up under the admin's Default Workspace. Mitigation: acceptable for Phase 1 single-user scope. Users can reassign layouts manually. Phase 2 will add proper multi-user layout ownership.

3. **Cascade delete is irreversible.** Deleting a workspace destroys all topologies and views. Mitigation: UI shows confirmation dialog with explicit warning. Only Admins can delete. No soft-delete in v1; future story may add trash/undo.

4. **Search is client-side for <= 100 rows, server-side ILIKE for larger sets.** The `search` query param on list endpoints uses `ILIKE '%term%'` which does not use indexes. Mitigation: homelab users typically have < 20 workspaces/topologies. If this becomes a bottleneck, add `pg_trgm` GIN indexes in a future migration.
