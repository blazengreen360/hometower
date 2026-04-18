---
name: pm-handoff
description: Use when the main agent or Project-Manager needs to delegate Hometower work to Codex subagents. Covers when to keep work local vs spawn `worker` or `explorer`, how to scope handoffs, how to parallelize safely, and how results must return through PM.
---

> Read this after `AGENTS.md` and the `project-manager` skill when a task needs Codex subagent delegation.

## Goal

Keep orchestration in the main agent while using Codex subagents surgically:
- `explorer` for bounded read-only reconnaissance
- `worker` for bounded implementation, remediation, or verification bundles

Every handoff returns to PM. No lateral routing except the explicit exemptions in `AGENTS.md`.

## Hard Rules

1. PM stays on the critical path. Do not hand off orchestration itself.
2. Use the fewest subagents needed. Small or tightly coupled work stays local.
3. Never delegate the immediate blocking step if you have no other productive local work.
4. Never duplicate work between the main agent and a subagent.
5. Every subagent gets a bounded scope, a success definition, and a verification target.
6. Every result returns to PM before the next dispatch.
7. Only these roles may fan out laterally:
   - `Code-Reviewer -> Git-Committer`
   - `QA-Orchestrator -> Bug-Finder`
   - `Security-Orchestrator -> Security-Auditor / Architect`

## Decision Matrix

### Keep It Local

Do the work in the main agent when:
- the next action is blocked on that result
- the task is tiny or easier than explaining it
- the task is tightly coupled to ongoing edits in the same files
- the result needs nuanced orchestration judgment more than execution

### Spawn `explorer`

Use `explorer` for read-only, sharply scoped questions such as:
- finding the files and symbols that implement a workflow
- tracing callers, imports, or route ownership
- comparing two implementations or summarizing a narrow area
- extracting current contracts before planning a patch
- scoping a bug before assigning a fixer

Good explorer outputs:
- concrete file paths
- short architecture summaries
- answer to one bounded question
- risk list or likely edit surface

Do not use `explorer` for code changes.

### Spawn `worker`

Use `worker` for bounded execution such as:
- implementing one feature slice
- fixing one bug in a clear write scope
- adding focused tests
- running a review bundle with structured output
- performing user simulation or verification

Good worker outputs:
- changed files
- verification results
- structured handshake for PM

## Critical Path Method

Before spawning:
1. Identify the serial chain that determines completion.
2. Keep the current blocking step local unless parallel side work exists.
3. Delegate only sidecar or disjoint bundles that materially advance the pipeline.

Example:
- Local now: inspect the failing route and decide whether this is frontend or backend.
- Parallel sidecar: explorer maps impacted files while worker prepares a focused test bundle.

## Prompt Design

### Explorer Prompt Shape

Use this for read-only reconnaissance:

```text
You are helping Project-Manager with bounded read-only reconnaissance.

Question:
[single concrete question]

Scope:
- [file or directory]
- [specific symbol, route, or workflow]

Constraints:
- Read-only. Do not edit files.
- Stay inside the requested scope.
- Prefer exact file paths and symbol names.

Return:
- Findings
- Files inspected
- Recommended next agent or owner
```

### Worker Prompt Shape

Use this for execution bundles:

```text
You are executing one bounded bundle for Project-Manager.

Context:
[what the user wants and why]

Ownership:
- You own: [exact files or module slice]
- You are not alone in the codebase. Do not revert others' edits.

Task:
[specific deliverable]

Constraints:
- Follow AGENTS.md and the relevant skill.
- Stay within your ownership boundary.
- Verify the change with [tests / gate / browser / review].

Return:
- status
- artifacts_produced
- verification summary
- blocker_details
- follow_up_required
```

## Ownership Rules

For every `worker`:
- assign a disjoint write set whenever parallel workers are used
- name the owning layer: UI, API, service, repo, tests, infra
- tell the worker not to revert unrelated edits
- tell the worker to adapt to existing in-flight changes if needed

If two bundles want the same files, serialize them unless one can be narrowed further.

## Parallel Patterns

Safe parallel examples:
- two `explorer` questions in separate code areas
- backend `worker` and frontend `worker` with disjoint write scopes after RFC contract is clear
- implementation `worker` plus independent verification `worker`
- QA-Orchestrator lane fan-out to Bug-Finder

Unsafe examples:
- two workers editing the same router or page
- frontend and backend in parallel when the API contract is still ambiguous
- delegating a task and then immediately redoing it locally

## Waiting And Reuse

- Do not call `wait_agent` by reflex.
- After spawning, do useful non-overlapping local work first.
- Wait only when the next critical-path step truly depends on the result.
- Reuse an existing agent only when the new task depends on its current context.
- Close finished agents once their result is integrated.

## PM Handoff Checklist

Before spawn:
- request classified
- critical path identified
- correct role chosen: local vs `explorer` vs `worker`
- scope and ownership defined
- success criteria defined

After return:
- inspect the result against the ask
- update `doc/progress.md` if this is active pipeline work
- decide next route using OODA
- capture out-of-scope follow-ups in `doc/tracker.md`

## Suggested Hometower Patterns

### New Feature

- `Architect` worker for RFC
- `DB-Engineer` worker if schema changes
- `Test-Automation-Engineer` worker for failing tests
- parallel `Backend-Engineer` and `Frontend-Engineer` workers only after contract clarity
- `User-Simulator` worker
- `Code-Reviewer` worker

### Known Bug

- local triage or `explorer` if location is still fuzzy
- `QA-Fixer` worker
- `User-Simulator` worker
- `Code-Reviewer` worker

### Bug Discovery

- `QA-Orchestrator` worker
- internal exempt fan-out to `Bug-Finder` explorers
- PM routes resulting report onward

### Security Audit

- `Security-Orchestrator` worker
- internal exempt fan-out to `Security-Auditor` explorers and `Architect` if needed
- PM routes remediation

## Escalate Instead Of Delegating

Pause and ask the user when:
- the change would alter auth/RBAC semantics and intent is unclear
- the same flow failed twice in verification
- there are conflicting results on the critical path
- hidden risk makes a “reasonable assumption” unsafe
