#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

GateCommand = tuple[str, tuple[str, ...]]

REVIEW_GATES: tuple[GateCommand, ...] = (
    ("pytest", ("docker", "compose", "exec", "api", "pytest")),
    (
        "mypy",
        ("docker", "compose", "exec", "api", "mypy", "src/", "--ignore-missing-imports"),
    ),
    ("build", ("docker", "compose", "build")),
)

REQUIREMENTS_AUDIT_GATE: GateCommand = (
    "requirements_audit",
    (".venv/bin/python", "-m", "pip_audit", "-r", "requirements.txt"),
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _run_git(root: Path, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(args), cwd=root, capture_output=True, text=True, check=False)


def _git_changed_files(root: Path) -> list[str]:
    tracked = _run_git(root, ("git", "diff", "--name-only", "--relative", "HEAD", "--"))
    tracked_files = tracked.stdout.splitlines() if tracked.returncode == 0 else []
    untracked = _run_git(root, ("git", "ls-files", "--others", "--exclude-standard"))
    untracked_files = untracked.stdout.splitlines() if untracked.returncode == 0 else []
    ordered: list[str] = []
    seen: set[str] = set()
    for path in tracked_files + untracked_files:
        normalized = path.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)
    return ordered


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clip_output(value: str, limit: int) -> tuple[str, bool]:
    if len(value) <= limit:
        return value, False
    return value[:limit], True


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _run_gate(root: Path, gate_id: str, command: Sequence[str], max_inline_chars: int) -> dict[str, object]:
    started_at = _utc_now()
    started = time.monotonic()
    try:
        result = subprocess.run(
            list(command),
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        stdout, stdout_truncated = _clip_output(result.stdout, max_inline_chars)
        stderr, stderr_truncated = _clip_output(result.stderr, max_inline_chars)
        finished_at = _utc_now()
        return {
            "id": gate_id,
            "command": shlex.join(command),
            "cwd": str(root),
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_seconds": round(time.monotonic() - started, 3),
            "ok": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout": stdout,
            "stdout_sha256": _hash_text(result.stdout),
            "stdout_truncated": stdout_truncated,
            "stderr": stderr,
            "stderr_sha256": _hash_text(result.stderr),
            "stderr_truncated": stderr_truncated,
        }
    except OSError as exc:
        finished_at = _utc_now()
        message = str(exc)
        return {
            "id": gate_id,
            "command": shlex.join(command),
            "cwd": str(root),
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_seconds": round(time.monotonic() - started, 3),
            "ok": False,
            "exit_code": None,
            "stdout": "",
            "stdout_sha256": _hash_text(""),
            "stdout_truncated": False,
            "stderr": message,
            "stderr_sha256": _hash_text(message),
            "stderr_truncated": False,
            "error": type(exc).__name__,
        }


def _write_json(payload: dict[str, object], output_path: Path | None) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(f"{rendered}\n", encoding="utf-8")
    sys.stdout.write(f"{rendered}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Hometower mandatory review gates with JSON output.")
    parser.add_argument(
        "--max-inline-chars",
        type=int,
        default=12000,
        help="Maximum number of stdout/stderr characters to inline per command.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to also write the JSON payload.",
    )
    args = parser.parse_args()

    root = _repo_root()
    started_at = _utc_now()
    changed_files = _git_changed_files(root)
    include_requirements_audit = "requirements.txt" in changed_files
    gates: list[GateCommand] = list(REVIEW_GATES)
    if include_requirements_audit:
        gates.append(REQUIREMENTS_AUDIT_GATE)
    commands = [_run_gate(root, gate_id, command, args.max_inline_chars) for gate_id, command in gates]
    finished_at = _utc_now()
    passed = sum(1 for command in commands if command["ok"] is True)
    failed = len(commands) - passed

    payload: dict[str, object] = {
        "tool": "deterministic-review-tooling/run_review_gates",
        "workspace": str(root),
        "started_at": started_at,
        "finished_at": finished_at,
        "ok": failed == 0,
        "changed_files": changed_files,
        "requirements_audit_required": include_requirements_audit,
        "commands": commands,
        "summary": {
            "total": len(commands),
            "passed": passed,
            "failed": failed,
        },
    }
    _write_json(payload, args.output)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
