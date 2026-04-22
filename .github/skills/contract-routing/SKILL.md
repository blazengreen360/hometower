---
name: contract-routing
description: Agent coordination contracts for Hometower — the full contract document model (what each agent produces/consumes), agent roster, and report/story lifecycle rules. Read this when you need to understand inter-agent handoffs, document routing, or archive procedures.
---

# contract-routing

PM routes all inter-agent communication via contract documents. Agents read inputs, produce outputs, return to PM.

## Contract Documents

| Document | Location | Producer | Consumer(s) |
|---|---|---|---|
| User Story | `doc/stories/HT-{id}.md` | Product-Owner | PM -> Architect |
| RFC Blueprint | `doc/rfc/RFC-HT-{id}-{slug}.md` | Architect | PM -> DB-Engineer, Backend-Engineer, Frontend-Engineer, UX-Designer |
| Bug Report | `doc/bugs/{report}.md` | QA-Orchestrator | PM -> QA-Fixer |
| Security Report | `doc/security/{report}.md` | Security-Orchestrator | PM -> QA-Fixer (tactical) / PM -> Backend-Engineer (structural) |
| Test Plan | Inline in RFC | Architect | PM -> Test-Automation-Engineer |
| Failing Tests | `tests/` | Test-Automation-Engineer | PM -> Backend/Frontend-Engineer |
| Gate Report | Structured format to PM | CI-Gatekeeper | PM -> Code-Reviewer A/B |
| Code Review Verdict | Structured format to PM | Code-Reviewer | PM (routes rejection to author) |
| Progress State | `doc/progress.md` | PM | PM (self — resume) |
| Engineering Tracker | `doc/tracker.md` | PM | PM (self — cross-pipeline) |
| Context Intern | Structured format to PM | Context-Intern | PM |
| Chaos Report | Structured format to PM | Chaos-Tester | PM -> QA-Fixer / Backend-Engineer |
| UX Audit | Structured format to PM | UX-Designer | PM -> Frontend-Engineer |
| Refactoring Result | Structured format to PM | Refactoring-Specialist | PM -> CI-Gatekeeper -> Code-Reviewer |

## Agent Roster

| Agent | Role | Produces | Consumes |
|---|---|---|---|
| Product-Owner | Requirements | Stories | User input |
| Project-Manager | Orchestration | Progress, tracker | All contracts |
| Context-Intern | Read-only recon | Context summaries | Source code, docs |
| Architect | System design | RFCs | Stories |
| DB-Engineer | Data layer | Models, repos, migrations | RFCs |
| Backend-Engineer | Application layer | Services, domain, API | RFCs, failing tests |
| Frontend-Engineer | Presentation | NiceGUI pages, JS | RFCs, failing tests |
| UX-Designer | UX audit | UX findings | RFCs, live UI |
| Refactoring-Specialist | Complexity reduction | Refactored code | PM-scoped files |
| Test-Automation-Engineer | Test creation | Failing tests | RFCs, test plans |
| QA-Orchestrator | Bug discovery | Bug reports | Source code |
| Bug-Finder | Parallel hunting | Findings -> QA-Orch | Source code |
| QA-Fixer | TDD remediation | Fixed code | Bug/security reports |
| Security-Orchestrator | Security audit | Security reports | Source code |
| Security-Auditor | STRIDE hunting | Findings -> Sec-Orch | Source code |
| CI-Gatekeeper | Deterministic gate execution | PASS/FAIL gate report | Any code diff |
| Code-Reviewer | Semantic review | Independent verdict | Code diff + gate report |
| User-Simulator | Exploratory E2E | Bug report | Live application |
| DevOps-Engineer | Infrastructure | Docker/infra changes | RFCs, migrations |
| Chaos-Tester | API fuzzing | Chaos report | Live API |

## Report & Story Lifecycle

**Stories**: Active in `doc/stories/`. On completion: `git mv doc/stories/HT-{id}.md doc/stories/done/` + update `doc/backlog.md`.

**Bug Reports**: Active in `doc/bugs/`. Archive on ALL_CLEAR: `git mv doc/bugs/{f}.md doc/bugs/completed/`.

**Security Reports**: Active in `doc/security/`. Archive after all closed + CR approved: `git mv doc/security/{f}.md doc/security/completed/`.

**Rules**:
- `git mv` only — never copy + delete
- Never archive on partial success (any OPEN/BLOCKED keeps it active)
- Never archive before Code-Reviewer APPROVED
