#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Rule:
    rule_id: str
    description: str
    pattern: str
    is_regex: bool = False


RULES_BY_FILE: dict[str, tuple[Rule, ...]] = {
    "AGENTS.md": (
        Rule(
            "dual-review-mandatory",
            "Requires two independent reviewer lanes against a passing gate report.",
            "two independent parallel `Code-Reviewer` lanes",
        ),
        Rule(
            "gate-report-evidence",
            "Requires exact gate command evidence.",
            "report the exact commands and pass/fail results",
        ),
        Rule(
            "ci-pass-required",
            "Blocks approval without a current-pipeline passing gate report.",
            "`Code-Reviewer` must not return `APPROVED` unless a current-pipeline `CI-Gatekeeper` report shows all three passed.",
        ),
        Rule(
            "requirements-sast",
            "Requires dependency SAST when requirements.txt is in scope.",
            "`pip-audit`",
        ),
        Rule(
            "reroute-invalid-review",
            "Requires PM to reject invalid review proof.",
            "PM must re-route review rather than accepting or summarizing it as approval.",
        ),
        Rule(
            "runtime-reference",
            "References the checked-in agent docs as the repo-local runtime surface.",
            "`.github/agents/*.agent.md` remain human-readable behavior references.",
        ),
    ),
    ".github/agents/ci-gatekeeper.agent.md": (
        Rule("trust-boundary", "Defines the gatekeeper trust boundary.", "## Trust Boundary"),
        Rule("mandatory-pytest", "Declares the pytest gate.", "docker compose exec api pytest"),
        Rule(
            "mandatory-mypy",
            "Declares the mypy gate.",
            "docker compose exec api mypy src/ --ignore-missing-imports",
        ),
        Rule("mandatory-build", "Declares the docker build gate.", "docker compose build"),
        Rule(
            "requirements-sast",
            "Requires dependency SAST for requirements changes.",
            ".venv/bin/python -m pip_audit -r requirements.txt",
        ),
        Rule(
            "build-review-bundle",
            "Uses deterministic scope metadata.",
            ".github/skills/deterministic-review-tooling/scripts/build_review_bundle.py",
        ),
        Rule(
            "scoped-review-bundle",
            "Requires the scoped review bundle command.",
            ".github/skills/deterministic-review-tooling/scripts/build_review_bundle.py --role ci-gatekeeper --file",
        ),
        Rule(
            "run-review-gates",
            "Uses the deterministic gate runner.",
            ".github/skills/deterministic-review-tooling/scripts/run_review_gates.py",
        ),
        Rule(
            "checkout-wide-gates",
            "Keeps mandatory gates checkout-wide.",
            "Always run `run_review_gates.py` checkout-wide.",
        ),
        Rule(
            "scoped-cyclomatic",
            "Limits cyclomatic scoring to in-scope implementation files.",
            "Cyclomatic complexity scoring — only on in-scope changed Python implementation files",
        ),
        Rule(
            "fail-closed",
            "Tells the gatekeeper to fail closed when evidence is incomplete.",
            r"fail closed",
            True,
        ),
    ),
    ".github/agents/code-reviewer.agent.md": (
        Rule(
            "gate-ownership",
            "Makes CI-Gatekeeper the owner of mandatory CI/static execution.",
            "You do not own the mandatory CI/static/SAST gate execution.",
        ),
        Rule(
            "ci-prerequisite",
            "Requires a current-pipeline CI gate report.",
            "current-pipeline `CI-Gatekeeper` report",
        ),
        Rule(
            "ci-pass-required",
            "Blocks approval without a passing gate report.",
            "must not return `APPROVED` unless",
        ),
        Rule(
            "semantic-rule",
            "Emphasizes semantic review over CI greenness.",
            "Passing CI is necessary, not sufficient",
        ),
        Rule(
            "independence-rule",
            "Makes each reviewer independent from the peer lane.",
            "## Independence Rule",
        ),
        Rule(
            "no-commit",
            "Forbids commit or push from the reviewer lane.",
            "Never commit or push",
        ),
    ),
    ".github/agents/project-manager.agent.md": (
        Rule(
            "review-pipeline-required",
            "Requires CI-Gatekeeper and both reviewer lanes for code diffs.",
            "For any code diff, never skip `CI-Gatekeeper` or the two independent `Code-Reviewer` lanes.",
        ),
        Rule(
            "pm-routed-handoffs",
            "Keeps review handoffs PM-routed.",
            "All arrows (`→`) represent PM-routed handoffs.",
        ),
        Rule(
            "gate-before-review",
            "Runs CI-Gatekeeper before semantic review.",
            "run CI-Gatekeeper before any reviewer lane",
        ),
        Rule(
            "dual-reviewers",
            "Runs both Code-Reviewer lanes against the passing gate report.",
            "run independent Code-Reviewer A and Code-Reviewer B in parallel against the current-pipeline PASS gate report",
        ),
        Rule(
            "closeout-block",
            "Blocks story closeout until both reviewers approve.",
            "do not close the story unless both reviewers return APPROVED",
        ),
    ),
    ".github/skills/deterministic-review-tooling/SKILL.md": (
        Rule(
            "policy-check-tool",
            "Documents the deterministic policy checker entrypoint.",
            ".venv/bin/python .github/skills/deterministic-review-tooling/scripts/check_review_policy.py",
        ),
        Rule(
            "review-bundle",
            "Documents the reviewer-mode deterministic review bundle.",
            ".venv/bin/python .github/skills/deterministic-review-tooling/scripts/build_review_bundle.py --reviewer-mode",
        ),
        Rule(
            "pm-upkeep",
            "Keeps the checker in the PM upkeep workflow.",
            "During `Project-Manager` or `pm-handoff` upkeep, run `scripts/check_review_policy.py`",
        ),
    ),
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _matches(text: str, rule: Rule) -> bool:
    if rule.is_regex:
        return re.search(rule.pattern, text, flags=re.MULTILINE) is not None
    return rule.pattern in text


def _check_file(root: Path, relative_path: str, rules: tuple[Rule, ...]) -> dict[str, object]:
    path = root / relative_path
    if not path.exists():
        return {
            "path": relative_path,
            "ok": False,
            "exists": False,
            "checks": [
                {
                    "id": rule.rule_id,
                    "description": rule.description,
                    "ok": False,
                    "reason": "file-missing",
                }
                for rule in rules
            ],
        }

    text = path.read_text(encoding="utf-8")
    checks = [
        {
            "id": rule.rule_id,
            "description": rule.description,
            "ok": _matches(text, rule),
        }
        for rule in rules
    ]
    return {
        "path": relative_path,
        "ok": all(check["ok"] is True for check in checks),
        "exists": True,
        "checks": checks,
    }


def _resolve_paths(raw: list[str] | None) -> tuple[list[str], list[str]]:
    selected = list(raw) if raw else list(RULES_BY_FILE.keys())
    unknown = [p for p in selected if p not in RULES_BY_FILE]
    return selected, unknown


def _build_summary(files: list[dict]) -> dict[str, int]:
    total = sum(len(f["checks"]) for f in files)
    failed = sum(1 for f in files for c in f["checks"] if c["ok"] is not True)
    return {
        "files_checked": len(files),
        "checks_total": total,
        "checks_failed": failed,
        "checks_passed": total - failed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check checked-in Hometower review policy docs for required review and scope clauses."
    )
    parser.add_argument(
        "--path",
        action="append",
        dest="paths",
        help="Optional relative path to limit the check to known policy files. Can be provided multiple times.",
    )
    args = parser.parse_args()

    selected, unknown = _resolve_paths(args.paths)
    if unknown:
        payload = {
            "tool": "deterministic-review-tooling/check_review_policy",
            "ok": False,
            "error": "unknown-path",
            "unknown_paths": unknown,
            "known_paths": sorted(RULES_BY_FILE.keys()),
        }
        sys.stdout.write(f"{json.dumps(payload, indent=2, sort_keys=True)}\n")
        return 2

    root = _repo_root()
    files = [_check_file(root, p, RULES_BY_FILE[p]) for p in selected]
    summary = _build_summary(files)
    payload = {
        "tool": "deterministic-review-tooling/check_review_policy",
        "workspace": str(root),
        "ok": summary["checks_failed"] == 0,
        "files": files,
        "summary": summary,
    }
    sys.stdout.write(f"{json.dumps(payload, indent=2, sort_keys=True)}\n")
    return 0 if summary["checks_failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
