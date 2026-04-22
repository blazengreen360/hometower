---
name: rfc-to-diff
description: Converts an Architect RFC in doc/rfc/ into a concrete, file-by-file implementation plan (models, migrations, repositories, services, routes, UI, tests) that Feature-Engineer can execute without re-deriving the design. Use when an RFC is APPROVED and the next step is implementation, when Feature-Engineer needs to tighten a vague RFC before coding, or when Architect wants to self-check RFC concreteness before publishing.
---

# rfc-to-diff

Bridges Architect → Feature-Engineer. RFCs are prose; code is diffs. This skill produces the checklist that maps one to the other.

## When to use

- PM has just received an APPROVED RFC and is about to invoke Feature-Engineer.
- Feature-Engineer starts a story and the RFC leaves file-level decisions implicit.
- Architect wants a self-review of RFC concreteness before publishing.

## Inputs

- Path to the RFC (e.g., `doc/rfc/RFC-HT-052-foo.md`).
- The current Architecture Map from `AGENTS.md` (assume it; do not re-derive).

## Output: the IMPLEMENTATION-PLAN block

Produce exactly this structure in chat. No file writes — this is a handoff artifact.

```
## Implementation Plan: <RFC id + title>

### 1. Data model
- models/<file>.py — ADD fields X, Y (types, defaults, constraints)
- models/types.py — ADD enum value Z (if applicable)

### 2. Migration
- alembic revision: "<message>"
- Ops: add_column / create_table / add_index / ...
- Backfill strategy: <none | SQL | multi-step>
- Rollback path: <op-by-op reverse>
- Online-safe? Y/N and why

### 3. Repository
- repositories/<file>.py — ADD functions: list_by_x(session, ...), ...
- session.flush(), never commit.

### 4. Domain (pure)
- domain/<file>.py — ADD pure-function signature (inputs → outputs, no I/O)

### 5. Service
- services/<file>.py — ADD orchestration: validate via domain → repo call → session.commit() → logger.info
- Errors: which IntegrityError / ValidationError branches map to which HTTPException

### 6. API routes
- api/routers/<file>.py — ADD endpoints:
  | Method | Path | response_model | Required role |
- Every route MUST have Depends(require_role(...))

### 7. UI
- ui/pages/<file>.py — ADD/MODIFY: <page change>
- ui/components/<file>.py — ADD/MODIFY: <component change>
- Canvas changes? → see canvas-bridge skill

### 8. Tests (Test-Automation-Engineer)
- tests/unit/domain/test_<x>.py — pure-function cases + boundary values
- tests/integration/test_<x>.py — happy path + RBAC negative + 409 conflict
- New fixture? Register the model in tests/conftest.py

### 9. Docs
- CHANGELOG.md — [Unreleased] entry
- If user-visible: relevant story in doc/stories/

### 10. Verification
- .venv/bin/python .github/skills/deterministic-review-tooling/scripts/run_review_gates.py
- If migration involved: bash .github/skills/migration-safety/scripts/check.sh <migration file>

### Risks / open questions for Architect
- <anything the RFC left ambiguous — do not proceed past this without resolution>
```

## Rules

- **Every section must have entries OR explicitly say "none — <reason>".** Empty sections are a smell that the RFC is underspecified.
- **Every new route line must name the required role.** A route without RBAC is a defect per AGENTS.md.
- **If any SQLModel schema is added**, verify all six classes exist: `Base`, table model, `Create`, `Update`, `Response`, `ResponseEnriched` (when joins exist).
- **If the RFC touches Device, DiagramLayout, or any versioned entity**, the Update schema must include `version: int` (optimistic locking).
- **If the RFC adds a new model**, the Migration section is mandatory and must be verified via the `migration-safety` skill.
- **If the RFC touches the canvas**, reference `canvas-bridge` and list the JS files that change.
- **No implementation details in the "Risks" section** — it's for design ambiguity only, not TODOs.

## What good looks like

A plan tight enough that Feature-Engineer can start editing files in order (1 → 10) without going back to the RFC except to resolve a listed risk. If in doubt, add more file paths — precision is the goal.

## What bad looks like

- "Add a service method" without naming the file or signature.
- "Handle errors appropriately" without listing which exceptions.
- "Update the UI" without naming components or pages.
- Missing the Migration section when the data model changed.
- Missing RBAC roles on new endpoints.

Reject the RFC back to Architect via PM if the plan cannot be filled without guessing.
