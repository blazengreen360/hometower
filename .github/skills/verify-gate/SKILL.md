---
name: verify-gate
description: Runs Hometower's pre-push quality gate (pytest, mypy, docker build) plus the architecture-boundary grep checks from AGENTS.md and reports a structured pass/fail snapshot. Use before declaring a task complete, before Code-Reviewer handoff, or whenever an agent needs to verify pytest, mypy, and layering (src/domain purity, src/ui → src/repositories, no print() calls) all pass.
---

# verify-gate

Machine-verified pre-push gate. Replaces ad-hoc `pytest` / `mypy` / grep invocations scattered across agents.

## When to use

- Feature-Engineer: after every red→green cycle before declaring the task done.
- QA-Fixer: before handing a fix to Code-Reviewer.
- Refactoring-Specialist: before and after each refactor to prove behavior preserved.
- Code-Reviewer: as the machine-verified portion of review.
- Project-Manager: as the pre-push gate.

## Run

```bash
bash .github/skills/verify-gate/scripts/run.sh
```

Flags:
- `--fast` — skip `docker compose build` (the slow step). Good for inner-loop work.
- `--tests <path>` — narrow pytest to one file. Default: full suite.
- `--no-docker` — run pytest + mypy on the host `.venv` instead of inside the container. Use when Docker is down.

The script prints a final block:

```
VERIFY-GATE RESULT:
  pytest:    PASS|FAIL
  mypy:      PASS|FAIL
  arch-grep: PASS|FAIL
  build:     PASS|FAIL|SKIPPED
  OVERALL:   PASS|FAIL
```

Exit code is non-zero iff any check failed.

## What arch-grep enforces

From `AGENTS.md` → Commands → "Architecture enforcement":

1. `src/domain/` must not import `sqlmodel`, `fastapi`, or `loguru` (pure-functions rule).
2. `src/ui/` must not import from `src.repositories` (layering rule).
3. No `print(` anywhere in `src/` outside `__pycache__` or test files (Loguru rule).

Any hit is a hard fail — these are zero-tolerance in AGENTS.md.

## Interpreting failures

- **arch-grep fail** → do not fix by deleting the grep hit blindly. The import usually signals the layer is doing work it shouldn't. Move the logic; don't paper over the check.
- **mypy fail on `Any`** → AGENTS.md bans `Any`. Use `Union` or a concrete type.
- **pytest fail on "fixture not found"** → a new model is probably not registered in `tests/conftest.py`.
- **build fail** → check `requirements.txt` drift vs. actual imports.

## Do not

- Do not run in `--fast` as the final pre-push check — PM's gate requires `docker compose build` to pass.
- Do not suppress failures with `|| true` or `--no-verify`. If the gate fails, fix the cause.
