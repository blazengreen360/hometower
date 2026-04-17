# HT-050 Post-Ship Bugfix — Container Resize Follow-Up

**Story/Bug:** HT-050 follow-up
**Started:** 17 April 2026
**Status:** In Progress

## Work Plan (CPM)
B1 reproduce container-resize bug -> B2 apply surgical frontend fix -> B3 rerun browser proof + canonical gate -> B4 formal scoped code review -> B5 close out follow-up

Critical path: B1 -> B2 -> B3 -> B4 -> B5
Parallelizable work remained intentionally minimal because the defect was frontend-local and live browser proof was the key acceptance signal before review.

## Bundle Progress
| # | Bundle | Agent | Status | Notes |
|---|---|---|---|---|
| B1 | Reproduce container resize bug | PM -> DevOps-Engineer / Context-Intern | Done | Reproduced on fresh runtime. The real defect was not generic child-node resize. It was compound/container resize behavior with children, including the exact one-container-one-child case the user reported. |
| B2 | Apply surgical frontend fix | PM -> QA-Fixer / Frontend-Engineer / Test-Automation-Engineer | Done | Final frontend fix removed child drift during compound resize, persisted width/height, split the resize bridge below file-cap limits, and added targeted unit plus browser regression coverage. |
| B3 | Verify bugfix | PM -> DevOps-Engineer / User-Simulator | Done | Live browser validation on the exact reported case passes: a single container with one child node expands and shrinks without child drift on all four axes, post-refresh geometry is sane, the focused unit suite passes, the deep browser proof passes in focused runs, and the canonical verify gate passed on current HEAD. |
| B4 | Formal review | PM -> Code-Reviewer | Blocked | Latest Code-Reviewer follow-up no longer indicates a product regression, but formal closeout is still blocked by two non-product items: the split resize-bridge files need to be included in the final git change set, and `tests/e2e/test_topology_canvas_deep.py` still shows a residual warm-run timing flake after two hardening retries. |
| B5 | Close-out bookkeeping | PM | Pending | Do not close until the review blockers above are either cleared or explicitly accepted by the user. |

## Decisions
- The bug was not a persistence failure: save/reload and history restore preserved incorrect post-resize dimensions exactly until the resize-path fix landed.
- The real defect was specific to resizing containers with children, including the exact one-container-one-child scenario the user reported.
- The final fix path stayed frontend-local and did not require reopening backend or data-model work.
- User-Simulator was the decisive signal: scripted proof lagged behind the user-reported reality until the one-sided anchor behavior was fixed.
- The product bug is now fixed in live browser validation and on the green canonical gate run.
- Remaining blockers are no longer product-behavior blockers. They are closeout blockers: a residual warm-run deep-test flake and the need to ensure the split resize-bridge files are included in the final git change set.

## Blockers
- Formal closeout is blocked by Code-Reviewer follow-ups, not by a known product regression.
- `tests/e2e/test_topology_canvas_deep.py` still shows a residual warm-run timing flake after two targeted hardening retries.
- The split resize-bridge files must be included in the final git change set so `src/ui/components/canvas_js_resize.py` does not depend on untracked modules in a clean checkout.
