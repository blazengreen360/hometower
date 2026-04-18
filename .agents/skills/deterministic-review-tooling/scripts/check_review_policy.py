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
    ".agents/skills/code-reviewer/SKILL.md": (
        Rule("mandatory-pytest", "Declares the pytest review gate.", "docker compose exec api pytest"),
        Rule(
            "mandatory-mypy",
            "Declares the mypy review gate.",
            "docker compose exec api mypy src/ --ignore-missing-imports",
        ),
        Rule("mandatory-build", "Declares the docker build review gate.", "docker compose build"),
        Rule("trust-boundary", "Defines the reviewer trust boundary.", "## Trust Boundary"),
        Rule(
            "fail-closed",
            "Tells the reviewer to fail closed when evidence is incomplete.",
            r"fail closed",
            True,
        ),
        Rule(
            "deterministic-gate-tool",
            "Points the reviewer at the deterministic gate runner.",
            ".agents/skills/deterministic-review-tooling/scripts/run_review_gates.py",
        ),
    ),
    ".agents/skills/project-manager/SKILL.md": (
        Rule("handoff-addendum", "Contains the mandatory review handoff addendum.", "### Mandatory Review Handoff Addendum"),
        Rule("mandatory-pytest", "Declares the pytest review gate.", "docker compose exec api pytest"),
        Rule(
            "mandatory-mypy",
            "Declares the mypy review gate.",
            "docker compose exec api mypy src/ --ignore-missing-imports",
        ),
        Rule("mandatory-build", "Declares the docker build review gate.", "docker compose build"),
        Rule(
            "reject-invalid-approval",
            "Rejects approvals without exact gate evidence.",
            "Do not accept `APPROVED` unless the reviewer reports exact commands and pass/fail results for all three mandatory gates.",
        ),
        Rule(
            "reroute-invalid-review",
            "Routes incomplete reviews back immediately.",
            "If the reviewer omits gate evidence, returns a paraphrase, or reports an interrupted gate, route the review back immediately as invalid.",
        ),
        Rule(
            "policy-check-tool",
            "Points PM at the deterministic policy checker.",
            ".agents/skills/deterministic-review-tooling/scripts/check_review_policy.py",
        ),
    ),
    ".agents/skills/pm-handoff/SKILL.md": (
        Rule("reviewer-addendum", "Contains the Code-Reviewer prompt addendum.", "### Code-Reviewer Prompt Addendum"),
        Rule("mandatory-pytest", "Declares the pytest review gate.", "docker compose exec api pytest"),
        Rule(
            "mandatory-mypy",
            "Declares the mypy review gate.",
            "docker compose exec api mypy src/ --ignore-missing-imports",
        ),
        Rule("mandatory-build", "Declares the docker build review gate.", "docker compose build"),
        Rule("trust-boundary", "Contains the prompt trust boundary block.", "Trust Boundary:"),
        Rule(
            "forbidden-files",
            "Protects PM-owned progress files from worker edits.",
            "Forbidden files: doc/progress.md, doc/tracker.md, doc/backlog.md.",
        ),
        Rule(
            "policy-check-tool",
            "Points handoff authors at the deterministic policy checker.",
            ".agents/skills/deterministic-review-tooling/scripts/check_review_policy.py",
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check Codex-local PM/reviewer skill docs for required review and scope policy clauses."
    )
    parser.add_argument(
        "--path",
        action="append",
        dest="paths",
        help="Optional relative path to limit the check to known skill files. Can be provided multiple times.",
    )
    args = parser.parse_args()

    selected_paths = tuple(args.paths) if args.paths else tuple(RULES_BY_FILE.keys())
    unknown_paths = [path for path in selected_paths if path not in RULES_BY_FILE]
    if unknown_paths:
        payload = {
            "tool": "deterministic-review-tooling/check_review_policy",
            "ok": False,
            "error": "unknown-path",
            "unknown_paths": unknown_paths,
            "known_paths": sorted(RULES_BY_FILE.keys()),
        }
        sys.stdout.write(f"{json.dumps(payload, indent=2, sort_keys=True)}\n")
        return 2

    root = _repo_root()
    files = [_check_file(root, relative_path, RULES_BY_FILE[relative_path]) for relative_path in selected_paths]
    total_checks = sum(len(file_result["checks"]) for file_result in files)
    failed_checks = sum(
        1
        for file_result in files
        for check in file_result["checks"]
        if check["ok"] is not True
    )
    payload = {
        "tool": "deterministic-review-tooling/check_review_policy",
        "workspace": str(root),
        "ok": failed_checks == 0,
        "files": files,
        "summary": {
            "files_checked": len(files),
            "checks_total": total_checks,
            "checks_failed": failed_checks,
            "checks_passed": total_checks - failed_checks,
        },
    }
    sys.stdout.write(f"{json.dumps(payload, indent=2, sort_keys=True)}\n")
    return 0 if failed_checks == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
