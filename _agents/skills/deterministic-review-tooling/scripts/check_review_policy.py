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
    ".agents/skills/ci-gatekeeper/SKILL.md": (
        Rule("mandatory-pytest", "Declares the pytest gate.", "docker compose exec api pytest"),
        Rule(
            "mandatory-mypy",
            "Declares the mypy gate.",
            "docker compose exec api mypy src/ --ignore-missing-imports",
        ),
        Rule("mandatory-build", "Declares the docker build gate.", "docker compose build"),
        Rule("requirements-sast", "Requires dependency SAST for requirements changes.", ".venv/bin/python -m pip_audit -r requirements.txt"),
        Rule("build-review-bundle", "Uses deterministic scope metadata.", ".agents/skills/deterministic-review-tooling/scripts/build_review_bundle.py"),
        Rule("scoped-review-bundle", "Requires the scoped review bundle command.", ".agents/skills/deterministic-review-tooling/scripts/build_review_bundle.py --role ci-gatekeeper --file"),
        Rule("run-review-gates", "Uses the deterministic gate runner.", ".agents/skills/deterministic-review-tooling/scripts/run_review_gates.py"),
        Rule("checkout-wide-gates", "Keeps mandatory gates checkout-wide.", "keep `run_review_gates.py` checkout-wide"),
        Rule("session-comment-ignore", "Ignores comment-only session grep hits.", "grep -vE '^[^:]+:[0-9]+:[[:space:]]*#'"),
        Rule("scoped-cyclomatic", "Limits cyclomatic scoring to in-scope implementation files.", "Run cyclomatic scoring only on in-scope changed Python implementation files"),
        Rule("fail-closed", "Tells the gatekeeper to fail closed when evidence is incomplete.", r"fail closed", True),
    ),
    ".agents/skills/code-reviewer/SKILL.md": (
        Rule("ci-prerequisite", "Requires a current-pipeline CI gate report.", "current-pipeline `CI-Gatekeeper` report"),
        Rule("ci-pass-required", "Blocks approval without a passing gate report.", "must not return `APPROVED` unless"),
        Rule("trust-boundary", "Defines the reviewer trust boundary.", "## Trust Boundary"),
        Rule("semantic-rule", "Emphasizes semantic review over CI greenness.", "Passing CI is necessary, not sufficient"),
        Rule("review-bundle", "Points the reviewer at the deterministic review bundle.", ".agents/skills/deterministic-review-tooling/scripts/build_review_bundle.py --reviewer-mode"),
        Rule("independence-rule", "Makes each reviewer independent from the peer lane.", "## Independence Rule"),
        Rule("no-initial-commit", "Forbids commit during the initial review pass.", "Do not commit during the initial review pass."),
    ),
    ".agents/skills/project-manager/SKILL.md": (
        Rule("handoff-addendum", "Contains the review handoff addenda.", "### Review Handoff Addenda"),
        Rule(
            "ci-gatekeeper-mandatory",
            "Makes CI-Gatekeeper mandatory before Code-Reviewer.",
            "`CI-Gatekeeper` is mandatory before semantic review",
        ),
        Rule(
            "dual-review-mandatory",
            "Requires two independent reviewer lanes before closeout.",
            "Two independent parallel `Code-Reviewer` lanes are mandatory before closeout",
        ),
        Rule(
            "reject-invalid-gate",
            "Rejects invalid gate reports without exact evidence.",
            "Do not accept a passing gate report unless it includes exact commands and pass/fail results for all three mandatory gates",
        ),
        Rule(
            "requirements-sast",
            "Requires dependency SAST evidence when requirements.txt is in scope.",
            "If the diff touches `requirements.txt`, the gatekeeper handoff must also require dependency SAST via `.venv/bin/python -m pip_audit -r requirements.txt`.",
        ),
        Rule(
            "explicit-file-list",
            "Requires an explicit reviewed file list for broader checkouts.",
            "If the checkout is broader than the ticket, the gatekeeper handoff must include the exact reviewed file list",
        ),
        Rule(
            "scoped-gatekeeper-bundle",
            "Requires the scoped CI-Gatekeeper bundle command.",
            ".venv/bin/python .agents/skills/deterministic-review-tooling/scripts/build_review_bundle.py --role ci-gatekeeper --file <path> [...]",
        ),
        Rule(
            "checkout-wide-gates",
            "Keeps mandatory gates checkout-wide.",
            "Use that scoped bundle for diff-relative checks only. Keep the mandatory gates checkout-wide.",
        ),
        Rule(
            "reject-invalid-approval",
            "Rejects closeout without two approvals and a passing gate report.",
            "Do not accept story closeout unless both `Code-Reviewer` lanes explicitly reviewed semantics against a passing current-pipeline gatekeeper report and both independently returned `APPROVED`.",
        ),
        Rule(
            "reroute-invalid-gate",
            "Routes incomplete gate reviews back immediately.",
            "If the gatekeeper omits gate evidence, returns a paraphrase, or reports an interrupted gate, route the gate lane back immediately as invalid.",
        ),
        Rule(
            "policy-check-tool",
            "Points PM at the deterministic policy checker.",
            ".agents/skills/deterministic-review-tooling/scripts/check_review_policy.py",
        ),
    ),
    ".agents/skills/pm-handoff/SKILL.md": (
        Rule("gatekeeper-addendum", "Contains the CI-Gatekeeper prompt addendum.", "### CI-Gatekeeper Prompt Addendum"),
        Rule("reviewer-addendum", "Contains the Code-Reviewer prompt addendum.", "### Code-Reviewer Prompt Addendum"),
        Rule("mandatory-pytest", "Declares the pytest review gate.", "docker compose exec api pytest"),
        Rule(
            "mandatory-mypy",
            "Declares the mypy review gate.",
            "docker compose exec api mypy src/ --ignore-missing-imports",
        ),
        Rule("mandatory-build", "Declares the docker build review gate.", "docker compose build"),
        Rule("requirements-sast", "Declares dependency SAST for requirements changes.", ".venv/bin/python -m pip_audit -r requirements.txt"),
        Rule(
            "explicit-file-list",
            "Requires an explicit reviewed file list for broader checkouts.",
            "If the checkout is broader than the ticket, include the exact reviewed file list in the gate prompt.",
        ),
        Rule(
            "scoped-gatekeeper-bundle",
            "Requires the scoped CI-Gatekeeper bundle command.",
            ".venv/bin/python .agents/skills/deterministic-review-tooling/scripts/build_review_bundle.py --role ci-gatekeeper --file <path> [...]",
        ),
        Rule(
            "checkout-wide-gates",
            "Keeps mandatory gates checkout-wide.",
            "Use that scoped bundle for diff-relative checks only. Keep the mandatory gates checkout-wide.",
        ),
        Rule("trust-boundary", "Contains the prompt trust boundary block.", "Trust Boundary:"),
        Rule("ci-prerequisite", "Binds semantic review to a gate report.", "Trust the current-pipeline `CI-Gatekeeper` report for mandatory gate truth."),
        Rule("independent-lane", "Makes each reviewer lane independent.", "You are one of two independent parallel review lanes."),
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
        description="Check Codex-local PM/reviewer skill docs for required review and scope policy clauses."
    )
    parser.add_argument(
        "--path",
        action="append",
        dest="paths",
        help="Optional relative path to limit the check to known skill files. Can be provided multiple times.",
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
