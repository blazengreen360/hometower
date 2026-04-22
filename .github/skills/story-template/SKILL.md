---
name: story-template
description: Canonical story structure for Hometower. Use when writing a new story (Product-Owner) or validating story completeness before dispatching implementation agents (Project-Manager). A story that fails the completeness checklist must be returned to Product-Owner before any implementation agent is invoked.
---

# story-template

Every story in `doc/stories/HT-[id].md` must follow this structure. Completeness is validated by PM in Phase 4 before any implementation agent is dispatched. Incomplete stories produce wasted RFC work and ambiguous implementations — fix them at authoring time, not review time.

## File Naming

```
doc/stories/HT-[id].md          # active
doc/stories/done/HT-[id].md     # archived on completion
```

## Canonical Template

```markdown
# HT-[id]: [Title — imperative verb + noun phrase, ≤60 chars]

**Status:** [Backlog | Ready | In Progress | Done]
**MoSCoW:** [Must | Should | Could | Won't]
**Kano:** [Basic | Performance | Delighter] — [one sentence on why]
**Phase:** [1 (Hometower) | 2 (LightTower)]
**Size:** [XS | S | M | L | XL]
**Depends on:** [HT-id, or "none"]

## Job-to-be-Done

As a [specific user role], I want to [concrete goal] so that [measurable outcome].

> Rule: one sentence. No "and". If you need "and", split into two stories.

## Context

[2–4 sentences. What exists today, what is broken or missing, and why this story is the right fix now. No solution language here — that belongs in the Architect RFC.]

## Acceptance Criteria

Each criterion: Given [precondition], when [action], then [observable outcome].
Every criterion must be independently verifiable. No criterion should require reading another criterion to understand.

- [ ] AC-1: Given [precondition], when [action or event], then [specific, observable outcome].
- [ ] AC-2: Given [precondition], when [action or event], then [specific, observable outcome].
- [ ] AC-N: ...

> Checklist: every AC must name a concrete UI state, API response, DB record, or error message.
> "Works correctly" is not an AC. "Returns HTTP 409 with body `{"error": "name_conflict"}`" is.

## Non-Goals

Explicitly list what this story does NOT cover. Forces scope discipline and prevents reviewers from expanding scope.

- [Out of scope item 1]
- [Out of scope item 2]

> Rule: at least one non-goal. If none come to mind, you haven't thought hard enough about scope creep.

## Business Invariants

Constraints that must remain true before and after this story ships. These become Code-Reviewer blockers if violated.

- [Invariant 1 — e.g. "Existing device IDs must not change"]
- [Invariant 2]

## Test Hints

Explicit pointers for Test-Automation-Engineer. These are not the full test plan — they are the high-value paths that must have coverage.

- [Key positive case: what the happy path looks like]
- [Key negative case: what should fail and how]
- [Edge case worth testing: boundary condition or concurrent operation]
- [Regression risk: what adjacent behavior could break]

## Notes for Architect / Engineer

[Optional. Pre-existing design decisions, known implementation constraints, or context that would save the Architect from re-deriving it. Do not prescribe the full solution — that belongs in the RFC. Do write down any hard constraints the Architect must respect.]
```

---

## Completeness Checklist (PM validates before dispatching Architect)

Project-Manager must verify every item before the story is eligible for implementation dispatch. Return to Product-Owner if any item fails.

| # | Check | Pass Condition |
|---|---|---|
| 1 | Title ≤ 60 chars, imperative verb | e.g. "Add VLAN tagging to topology canvas", not "VLAN stuff" |
| 2 | Status is "Ready" | Not "Backlog" — PO must explicitly mark ready |
| 3 | MoSCoW is set | Must / Should / Could / Won't |
| 4 | Size is set | XS–XL — informs PM capacity planning |
| 5 | JTBD has one role, one goal, one outcome | No compound sentences |
| 6 | At least 3 ACs in Given/When/Then form | Each independently verifiable |
| 7 | Every AC names a concrete observable | No "works correctly", "displays properly", "handles error" |
| 8 | At least one non-goal is listed | Prevents scope creep at review time |
| 9 | Business invariants listed | At least one; informs Code-Reviewer blockers |
| 10 | Test hints present | At least: one positive, one negative, one edge case |
| 11 | Dependencies declared | Either named HT-ids or "none" — never left blank |

---

## Size Guide

| Size | Story Points | Typical Scope |
|---|---|---|
| XS | 1 | Single file change, no new routes or models, no migration |
| S | 2–3 | 2–4 files, one new endpoint or model field, no migration |
| M | 5 | New feature with 1–2 new models, migration, service + UI |
| L | 8 | Multi-service feature, significant UI, new RFC required |
| XL | 13+ | Architectural change — must be decomposed before scheduling |

> XL stories must be decomposed before they enter a sprint. If you accept an XL story as-is, PM will refuse to plan it.

---

## Status Transitions

```
Backlog → Ready       PO: story passes completeness checklist, no blocking dependencies
Ready → In Progress   PM: story dispatched to Architect or first implementation agent
In Progress → Done    PM: both Code-Reviewer lanes APPROVED, story archived to done/
Done → (reopened)     PM: regression found — reopen as a new bug story, do not undo archival
```

---

## Anti-Patterns

These patterns indicate a story is not ready. Return to PO.

| Anti-pattern | Why it fails | Fix |
|---|---|---|
| "As a user" (no role) | Reviewers cannot verify RBAC or scope | Name the role: "admin", "contributor", "reader" |
| AC: "The feature works" | Untestable | Replace with a specific observable state |
| No non-goals | Scope will expand during review | Add at least one explicit exclusion |
| ACs reference each other | Order-dependent, fragile | Each AC must be independently verifiable |
| Size = XL accepted | Unpredictable sprint impact | Decompose into ≤L stories first |
| Dependencies left blank | PM cannot sequence work | Explicitly write "none" or list HT-ids |
| Context describes solution | Architects will skip RFC | Context = what exists today and why it's wrong; solution = RFC |
