---
name: git-conventions
description: Hometower's git commit conventions — scope-to-layer mapping and footer format for the Git-Committer agent. Read this when committing code or reviewing commit messages.
---

# git-conventions

## Commit Scope Mapping

Derive from the primary layer touched:

| Scope | Layer |
|---|---|
| `api` | Routers, middleware |
| `service` | Service layer |
| `domain` | Domain logic |
| `model` | SQLModel models, types |
| `repo` | Repositories |
| `ui` | NiceGUI pages, components, canvas, map |
| `auth` | Authentication, RBAC |
| `db` | Migrations, schema |
| `infra` | Docker, CI, config |
| `test` | Test infrastructure |
| `agent` | Agent instructions |

Multiple scopes: use highest-impact. Truly cross-cutting: omit scope.

## Footer Format

Always include audit trail and traceability:

```
Refs: HT-047
Audit: APPROVED
Complexity-Delta: reduced
```

If the commit closes a story/bug:
```
Closes: HT-047
Audit: APPROVED
Complexity-Delta: neutral
```

`Complexity-Delta` is extracted from the Code-Reviewer's verdict payload: `increased | neutral | reduced`.
