---
name: data-model
description: Hometower's complete data model — all entities, tables, key fields, foreign keys, and the entity hierarchy. Read this when working with models, repositories, migrations, or any code that touches the database schema.
---

# data-model

Current persistence uses `diagram_layouts` as the canvas-state store. Until HT-072..HT-075 redesign ships, treat `DiagramLayout` and `/views` as legacy implementation details; canonical user-facing model is Workspace / Topology / History with personal drafts.

## Entities

| Entity | Table | Key Fields |
|---|---|---|
| Device | `devices` | `id` (UUID PK), `name`, `type` (DeviceType), `status` (DeviceStatus), `ip`, `mac`, `os`, `notes`, `location_id` (FK), `parent_id` (FK self-ref), `version`, `created_at`, `updated_at` |
| Connection | `connections` | `id` (UUID PK), `source_id` (FK), `target_id` (FK), `type` (ConnectionType), `label` |
| Location | `locations` | `id` (UUID PK), `name`, `type` (LocationType), `lat`, `lng`, `rack`, `row`, `parent_id` (FK self-ref) |
| Tag | `tags` | `id` (UUID PK), `name`, `color` |
| DeviceTag | `device_tags` | `device_id` (FK PK), `tag_id` (FK PK) |
| CustomField | `custom_fields` | `id` (UUID PK), `device_id` (FK), `key`, `value` |
| User | `users` | `id` (UUID PK), `username`, `email`, `password_hash`, `role` (Role), `is_active`, `token_version`, `created_at`, `updated_at` |
| DiagramLayout | `diagram_layouts` | `id` (UUID PK), `name`, `topology_id` (FK), `cytoscape_json` (JSON), `version`, `created_at`, `updated_at` |
| Service | `services` | `id` (UUID PK), `device_id` (FK CASCADE), `name`, `port`, `protocol` (ServiceProtocol), `url`, `status` (ServiceStatus), `notes` |
| ServiceDependency | `service_dependencies` | `service_id` (FK PK CASCADE), `depends_on_id` (FK PK CASCADE), self-ref check |
| Workspace | `workspaces` | `id` (UUID PK), `owner_id` (FK), `name` (unique/owner), `created_at`, `updated_at` |
| Topology | `topologies` | `id` (UUID PK), `workspace_id` (FK), `name` (unique/workspace), `tags` (JSON), `created_at`, `updated_at` |

## Entity Hierarchy

```
Workspace (owner_id -> User)
  └── Topology (workspace_id -> Workspace)
    └── DiagramLayout (legacy canvas store -> History/Draft transition)

Device (global — not workspace-scoped)
  ├── parent_id -> Device (self-ref containers)
  ├── location_id -> Location
  ├── DeviceTag -> Tag
  ├── CustomField
  ├── Service
  │   └── ServiceDependency -> Service
  └── Connection (source_id / target_id)
```

## Enums (all in `src/models/types.py`)

`DeviceType`, `ConnectionType`, `Role`, `LocationType`, `DeviceStatus`, `ServiceProtocol`, `ServiceStatus`
