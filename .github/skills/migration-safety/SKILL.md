---
name: migration-safety
description: Audits an Alembic migration file for online-safety, rollback completeness, and backfill correctness before it ships. Use whenever DevOps-Engineer generates or hand-writes an alembic/versions/ file, when an Architect RFC involves a schema change, or before Code-Reviewer approves a PR that touches migrations. Runs a static scan for HIGH/MEDIUM/LOW risk patterns (NOT NULL without server_default, non-concurrent indexes, empty downgrades, missing ondelete, inline sa.Enum).
---

# migration-safety

Schema changes are the hardest thing to roll back. This skill catches common foot-guns before they reach prod.

## Migration Principles

- **Reversible**: `downgrade()` is required and should genuinely reverse `upgrade()`
- **Additive First**: prefer add/backfill/enforce over destructive one-shot changes
- **Idempotent by Design**: migrations should be safe to inspect, rerun conceptually, and reason about under deployment retries

## When to use

- Right after `alembic revision --autogenerate` — autogenerate is good at diffs, bad at safety.
- As part of DevOps-Engineer's standard handoff.
- Code-Reviewer gates any PR touching `alembic/versions/` on a clean report from this skill.

## Run

```bash
bash .claude/skills/migration-safety/scripts/check.sh alembic/versions/<file>.py
```

Flags risky patterns and prints a pass/fail with line numbers. Exit non-zero if any HIGH-severity issue is present.

## Static checks

**HIGH severity (block merge):**
- `add_column(..., nullable=False)` without a `server_default` — rewrites the table, blocks writes on large tables.
- `alter_column(...)` changing `type_=` — often forces a full table rewrite and exclusive lock.
- `drop_column` / `drop_table` with an empty or `pass`-only `downgrade()` — irreversible in prod.
- `create_index` on a hot table (`devices`, `connections`, `diagram_layouts`) without `postgresql_concurrently=True`.
- `op.execute("UPDATE ...")` without an accompanying batching/locking comment.

**MEDIUM (warn, require a justification comment):**
- `ForeignKey` without explicit `ondelete=` (default is RESTRICT — may not match intent).
- `UniqueConstraint` added on an existing table without a pre-check that data already satisfies it.
- Inline `sa.Enum(...)` instead of referencing `src/models/types.py` — drifts from canonical enums.

**LOW (informational):**
- Revision docstring fewer than 4 words.

## Human checklist (not automatable — always review)

1. **Backfill strategy for new NOT NULL columns**
   - Revision N: add nullable + `server_default`.
   - Revision N+1: backfill in code or a data migration.
   - Revision N+2: flip to NOT NULL, drop default.
2. **Rollback was actually tested** — run `alembic downgrade -1` against a copy of prod schema.
3. **Locks** — `ALTER TABLE` acquires `ACCESS EXCLUSIVE` in Postgres. For hot tables, prefer `CREATE INDEX CONCURRENTLY` and split into multiple migrations.
4. **Data-loss irreversibility** — column/table drops cannot be undone once deployed. Double-confirm.
5. **Enums** — Postgres enum values cannot be removed. Adding is safe; renaming/removing requires a new type + data migration.
6. **Test coverage** — a test in `tests/` touches the new/changed columns so schema/code drift fails CI.

## Do not

- Do not combine unrelated schema changes in one revision — each should be atomic.
- Do not hand-edit an already-deployed migration. Write a new one.
- Do not rely on `--autogenerate` for data migrations — it only sees schema diffs.
