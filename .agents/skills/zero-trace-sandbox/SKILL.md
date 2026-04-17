---
name: zero-trace-sandbox
description: Safely wipes the Postgres database and recreates the schema to satisfy the User Simulator's zero-trace teardown protocol.
---

# zero-trace-sandbox

Satisfies the "Zero-Trace" parameter for the `User-Simulator` by completely destroying all mock topology data generated during the 6-month E2E simulations without harming the docker container state.

## When to use

- **User-Simulator**: As your absolute final step (Phase 5) after producing your JSON report payload.

## Run

```bash
bash .agents/skills/zero-trace-sandbox/scripts/rollback.sh
```

## How it works
It executes `alembic downgrade base` to execute all downgrade scripts, completely dropping all tables. Then it runs `alembic upgrade head` to recreate the pristine, empty schema ready for the next run.
