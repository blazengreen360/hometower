#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from scope_guard import load_files
from scope_policy import PROTECTED_PM_DOCS, dedupe_paths, evaluate_role_scope, normalize_repo_path, repo_root, supported_roles

RISK_MARKERS: tuple[str, ...] = ("auth", "middleware", "src/models/", "alembic/")


def run_git(root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=root, capture_output=True, text=True, check=False)


def git_changed_files(root: Path) -> list[str]:
    tracked = run_git(root, ["git", "diff", "--name-only", "--relative", "HEAD", "--"])
    tracked_files = tracked.stdout.splitlines() if tracked.returncode == 0 else []
    untracked_files = git_untracked_files(root)
    normalized = [normalize_repo_path(root, path) for path in tracked_files + untracked_files]
    return dedupe_paths([path for path in normalized if path])


def git_untracked_files(root: Path) -> list[str]:
    untracked = run_git(root, ["git", "ls-files", "--others", "--exclude-standard"])
    if untracked.returncode != 0:
        return []
    return untracked.stdout.splitlines()


def diff_changed_lines(root: Path, files: list[str]) -> dict[str, int]:
    if not files:
        return {}
    result = run_git(root, ["git", "diff", "--numstat", "--relative", "HEAD", "--", *files])
    changed: dict[str, int] = {}
    if result.returncode == 0:
        for raw_line in result.stdout.splitlines():
            parts = raw_line.split("\t")
            if len(parts) < 3:
                continue
            added_raw, deleted_raw, path = parts[0], parts[1], parts[-1]
            added = 0 if added_raw == "-" else int(added_raw)
            deleted = 0 if deleted_raw == "-" else int(deleted_raw)
            changed[normalize_repo_path(root, path)] = added + deleted
    return changed


def total_line_count(root: Path, relative_path: str) -> dict[str, int | bool | None]:
    path = root / relative_path
    if not path.exists():
        return {"exists": False, "total_lines": None}
    content = path.read_bytes()
    if not content:
        return {"exists": True, "total_lines": 0}
    total_lines = content.count(b"\n")
    if not content.endswith(b"\n"):
        total_lines += 1
    return {"exists": True, "total_lines": total_lines}


def review_tier(file_count: int, changed_lines: int, risky_paths: list[str], touches_alembic: bool) -> str:
    if risky_paths or touches_alembic or file_count > 10 or changed_lines > 400:
        return "DEEP"
    if file_count > 1 or changed_lines > 50:
        return "STANDARD"
    return "FAST-TRACK"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a deterministic JSON review bundle from the current worktree.")
    parser.add_argument("--file", action="append", default=[], dest="files")
    parser.add_argument("--files-from", action="append", default=[], dest="files_from", type=Path)
    parser.add_argument("--role", choices=supported_roles())
    parser.add_argument("--reviewer-mode", action="store_true")
    args = parser.parse_args()

    root = repo_root()
    explicit_files = load_files(root, args.files, args.files_from)
    changed_files = explicit_files if explicit_files else git_changed_files(root)
    active_role = "code-reviewer" if args.reviewer_mode else args.role
    advisory_violations: list[dict[str, str]] = []
    violations: list[dict[str, str]] = []
    if active_role is not None:
        role_findings = evaluate_role_scope(active_role, changed_files, ignore_read_only=args.reviewer_mode)
        if args.reviewer_mode:
            advisory_violations = role_findings
        else:
            violations = role_findings
    changed_line_map = diff_changed_lines(root, changed_files)
    untracked_files = {normalize_repo_path(root, path) for path in git_untracked_files(root)}
    line_counts: list[dict[str, int | bool | None | str]] = []
    for path in changed_files:
        totals = total_line_count(root, path)
        changed_lines = changed_line_map.get(path)
        if changed_lines is None and path in untracked_files and totals["exists"] is True:
            changed_lines = int(totals["total_lines"] or 0)
        elif changed_lines is None and totals["exists"] is True and explicit_files:
            changed_lines = int(totals["total_lines"] or 0)
        elif changed_lines is None:
            changed_lines = 0
        line_counts.append(
            {
                "path": path,
                "exists": totals["exists"],
                "total_lines": totals["total_lines"],
                "changed_lines": changed_lines,
            }
        )
    total_changed_lines = sum(int(item["changed_lines"]) for item in line_counts)
    touches_alembic = any(path.startswith("alembic/") for path in changed_files)
    touches_protected_pm_docs = any(path in PROTECTED_PM_DOCS for path in changed_files)
    risky_paths = [path for path in changed_files if any(marker in path for marker in RISK_MARKERS)]
    payload = {
        "tool": "deterministic-review-tooling/build_review_bundle",
        "ok": len(violations) == 0,
        "role": active_role,
        "reviewer_mode": args.reviewer_mode,
        "changed_files": changed_files,
        "line_counts": line_counts,
        "touches_alembic": touches_alembic,
        "touches_protected_pm_docs": touches_protected_pm_docs,
        "risky_paths": risky_paths,
        "recommended_review_tier": review_tier(
            len(changed_files), total_changed_lines, risky_paths, touches_alembic
        ),
        "scope_guard": {
            "ok": len(violations) == 0,
            "role": active_role,
            "files_checked": changed_files,
            "violations": violations,
        },
        "scope_advisories": {
            "mode": "analysis-only" if args.reviewer_mode else "none",
            "role": active_role,
            "violations": advisory_violations,
        },
        "summary": {
            "changed_file_count": len(changed_files),
            "total_changed_lines": total_changed_lines,
        },
    }
    sys.stdout.write(f"{json.dumps(payload, indent=2, sort_keys=True)}\n")
    return 0 if payload["ok"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
