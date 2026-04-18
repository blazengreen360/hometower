# HT-082 Progress — Dashboard Revamp And Power Widgets

**Story:** HT-082 (L)
**Started:** 18 April 2026
**Status:** In Progress

## Work Plan (CPM)
B1 implement a backend dashboard aggregate endpoint + model + tests -> B2 implement the premium dashboard UI against that aggregate contract + focused UI tests -> B3 run mandatory live user validation on dashboard widgets, filtering, and navigation -> B4 formal code review with mandatory gates and local commit on approval -> B5 close out story bookkeeping

Critical path: B1 -> B2 -> B3 -> B4 -> B5
Parallelizable work is intentionally limited: the backend contract must settle before the frontend lane finalizes the dashboard widget wiring, but UI styling/component extraction can begin once the response shape is clear.

## Decisive Proof
- Dashboard `/` renders a balanced overview with real aggregate data from a single dashboard summary contract rather than scatter-gather page fetches.
- Power widget supports `All` vs workspace filtering without a full page reload.
- Inventory/status widgets navigate to pre-filtered `/inventory`.
- Recent activity shows the latest relevant changes and links to the resource.
- Mandatory review gates pass: `docker compose exec api pytest`, `docker compose exec api mypy src/ --ignore-missing-imports`, `docker compose build`.
- Code-Reviewer returns a valid verdict with exact gate evidence, then commits locally via Git-Committer.

## Bundle Progress
| # | Bundle | Agent | Status | Notes |
|---|---|---|---|---|
| B1 | Backend aggregate contract + tests | PM -> Backend-Engineer | Pending | Build a single dashboard summary endpoint/service contract with efficient aggregate queries and recent-activity payload. |
| B2 | Dashboard UI revamp + focused tests | PM -> Frontend-Engineer | Pending | Rebuild `/` against the aggregate endpoint with premium widget cards, workspace-aware power card, inventory/status drill-through, and recent-activity links. |
| B3 | Mandatory live validation | PM -> User-Simulator | Pending | Validate dashboard load, power workspace switching, inventory drill-through, and recent activity link behavior in the browser. |
| B4 | Formal review + local commit | PM -> Code-Reviewer | Pending | Review scoped diff, rerun mandatory gates in the review run, and commit locally if APPROVED. |
| B5 | Close-out bookkeeping | PM | Pending | Update changelog, backlog, story archive, tracker if needed, and clear progress state after approval. |

## Decisions
- No Architect lane up front: the story already fixes the dashboard direction and the most efficient path is a direct backend aggregate contract plus frontend implementation.
- The backend should own aggregation so the NiceGUI page does not issue multiple independent collection calls on load.
- Recent activity should start with the simplest reliable sources already in the data model: recent devices and recent topology history/version events, then normalize them into one dashboard activity list.

## Blockers
- None.
