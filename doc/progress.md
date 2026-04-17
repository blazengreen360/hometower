# HT-050 Post-Ship Bugfix — Container Resize Clamp Regression

**Story/Bug:** HT-050 follow-up
**Started:** 17 April 2026
**Status:** In Progress

## Work Plan (CPM)
B1 reproduce nested-container resize bug -> B2 apply surgical clamp fix in canvas resize path -> B3 rerun browser proof + canonical gate -> B4 formal scoped code review -> B5 close out follow-up

Critical path: B1 -> B2 -> B3 -> B4 -> B5
Parallelizable work is intentionally minimal because the defect is already narrowed to the container clamp logic in the resize bridge, and live browser proof is the key acceptance signal before review.

## Bundle Progress
| # | Bundle | Agent | Status | Notes |
|---|---|---|---|---|
| B1 | Reproduce container resize bug | PM -> DevOps-Engineer / Context-Intern | Done | Reproduced on fresh runtime. Child-node resize inside a container behaved correctly, but container clamp enforcement failed for both nested containers and parent containers with children. Example: nested container minimum should have clamped to `122x100` but shrank to `90x92`; parent container minimum should have clamped to `558.556x321.218` but shrank to `510.556x297.218`. Persistence correctly preserved the wrong undersized dimensions, so the bug is in clamp logic rather than save/reload. |
| B2 | Apply surgical clamp fix | PM -> Frontend-Engineer | Pending | Fix container/compound minimum-size enforcement in `src/ui/components/canvas_js_resize.py` and add focused regression coverage for nested container shrink attempts. |
| B3 | Verify bugfix | PM -> DevOps-Engineer | Pending | Rerun focused browser proof for nested container and parent-container clamp behavior, then rerun canonical verify-gate. |
| B4 | Formal review | PM -> Code-Reviewer | Pending | Review only the HT-050 bugfix allowlist so unrelated worktree drift does not block closure. |
| B5 | Close-out bookkeeping | PM | Pending | Update progress/tracker memory and close the follow-up once the bugfix is verified and approved. |

## Decisions
- The bug is not a persistence failure: save/reload and history restore preserved the incorrect post-resize dimensions exactly.
- The defect is specific to resizing containers with children (nested container or parent container), not ordinary child nodes placed inside a container.
- The narrowest likely code scope is `src/ui/components/canvas_js_resize.py` plus targeted regression coverage.

## Blockers
- No active blockers. Root area is identified and ready for a targeted fix bundle.
