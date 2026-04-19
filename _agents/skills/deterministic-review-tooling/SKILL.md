---
name: deterministic-review-tooling
description: Deterministic Codex-local tooling for Hometower review enforcement. Use when you need JSON output for the mandatory review gates, or when you need to verify Project-Manager, CI-Gatekeeper, and Code-Reviewer skill docs still contain the required scope, trust-boundary, and approval-policy language.
---

# Deterministic Review Tooling

Use this repo-local skill when review evidence needs to be stable, machine-readable, and local to Codex behavior.

## Quick Start

Prefer the repo `.venv` from the repository root:

```bash
.venv/bin/python .agents/skills/deterministic-review-tooling/scripts/run_review_gates.py
.venv/bin/python .agents/skills/deterministic-review-tooling/scripts/check_review_policy.py
.venv/bin/python .agents/skills/deterministic-review-tooling/scripts/scope_guard.py --role backend-engineer --file src/services/device_service.py
.venv/bin/python .agents/skills/deterministic-review-tooling/scripts/build_review_bundle.py --role ci-gatekeeper
.venv/bin/python .agents/skills/deterministic-review-tooling/scripts/build_review_bundle.py --reviewer-mode
```

## Tools

- `scripts/run_review_gates.py`
  Runs the mandatory review gates from `AGENTS.md` in fixed order and emits JSON with exact command text, exit code, duration, and captured output hashes. If `requirements.txt` is in scope, it also runs dependency SAST via `pip-audit`.
- `scripts/check_review_policy.py`
  Verifies the local gatekeeper, reviewer, PM, and PM handoff skills still contain the required gate, trust-boundary, and terminal-scope clauses. Emits JSON pass/fail per file and rule.
- `scripts/scope_guard.py`
  Checks a proposed file list against Codex-local role boundaries and protected PM documents. Supports repeated `--file` arguments and `--files-from <path>`.
- `scripts/build_review_bundle.py`
  Builds a deterministic review bundle from explicit file inputs or the current worktree diff. Includes file list, line counts, risky-path flags, protected-doc detection, role-scope violations, and a recommended review tier.

## Usage Rules

- Keep usage local to repo Codex skills and repo-local enforcement.
- Do not point this bundle at `.github/`; it exists to harden Codex-local behavior.
- Treat script JSON as evidence, not as a replacement for reading the diff or following `AGENTS.md`.

## When To Use Which

- During `CI-Gatekeeper` work, run `scripts/build_review_bundle.py --role ci-gatekeeper` and `scripts/run_review_gates.py`, then cite the JSON output in the gate report. If `requirements.txt` is in scope, verify the gate JSON also contains the dependency audit entry.
- Before the matrix walk, `Code-Reviewer` can run `scripts/build_review_bundle.py --reviewer-mode` to summarize scope, risk markers, and review tier in one JSON payload.
- During `Project-Manager` or `pm-handoff` upkeep, run `scripts/check_review_policy.py` after editing gatekeeper, reviewer, or PM skill prompts.
- Before dispatching a terminal worker, `Project-Manager` can run `scripts/scope_guard.py --role <role>` on the intended file list to catch scope leaks early.
