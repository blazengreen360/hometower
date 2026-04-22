#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence


@dataclass(frozen=True)
class GateSpec:
    id: str
    argv: tuple[str, ...]
    display_command: str
    pass_exit_codes: tuple[int, ...] = (0,)
    kind: str = "gate"


def _argv_gate(
    gate_id: str,
    *argv: str,
    kind: str = "gate",
    pass_exit_codes: tuple[int, ...] = (0,),
) -> GateSpec:
    return GateSpec(gate_id, tuple(argv), shlex.join(argv), pass_exit_codes, kind)


def _shell_gate(
    gate_id: str,
    command: str,
    *,
    kind: str = "check",
    pass_exit_codes: tuple[int, ...] = (0,),
) -> GateSpec:
    return GateSpec(
        gate_id,
        ("bash", "-lc", f"set -o pipefail && {command}"),
        command,
        pass_exit_codes,
        kind,
    )


REVIEW_GATES: tuple[GateSpec, ...] = (
    _argv_gate("pytest", "docker", "compose", "exec", "api", "pytest"),
    _argv_gate(
        "coverage",
        "docker",
        "compose",
        "exec",
        "api",
        "pytest",
        "--cov=src",
        "--cov-fail-under=80",
    ),
    _argv_gate(
        "mypy",
        "docker",
        "compose",
        "exec",
        "api",
        "mypy",
        "src/",
        "--ignore-missing-imports",
    ),
    _argv_gate("build", "docker", "compose", "build"),
)

REQUIREMENTS_AUDIT_GATE = _argv_gate(
    "requirements_audit",
    ".venv/bin/python",
    "-m",
    "pip_audit",
    "-r",
    "requirements.txt",
)

BANDIT_GATE = _argv_gate(
    "bandit",
    "docker",
    "compose",
    "exec",
    "api",
    "bandit",
    "-r",
    "src/",
    "-ll",
    "-ii",
)

MIGRATION_SAFETY_COMMAND = 'bash .github/skills/migration-safety/scripts/check.sh "<file>"'
CYCLOMATIC_COMMAND = 'bash .github/skills/cyclomatic-scorer/scripts/score.sh "<file>"'

STATIC_CHECKS: tuple[GateSpec, ...] = (
    _shell_gate(
        "domain_purity",
        'grep -rn "from sqlmodel\\|from fastapi\\|from loguru" src/domain/ --include="*.py"',
        pass_exit_codes=(1,),
    ),
    _shell_gate(
        "ui_repo_isolation",
        'grep -rn "from src.repositories" src/ui/ --include="*.py"',
        pass_exit_codes=(1,),
    ),
    _shell_gate(
        "no_print",
        'grep -rn "print(" src/ --include="*.py" | grep -v test | grep -v __pycache__',
        pass_exit_codes=(1,),
    ),
    _shell_gate(
        "session_creation_containment",
        "find src/api src/services src/ui src/domain src/utils -type f -name \"*.py\" "
        "! -path \"src/utils/db.py\" ! -path \"src/api/app.py\" "
        "! -path \"src/api/middleware/auth.py\" "
        "-exec grep -nE \"with Session\\(|Session\\(engine\\)\" {} + "
        "| grep -vE '^[^:]+:[0-9]+:[[:space:]]*#'",
        pass_exit_codes=(1,),
    ),
    _shell_gate(
        "router_transaction_containment",
        'grep -rn "session.commit()\\|session.rollback()" src/api/routers/ --include="*.py" '
        '| grep -v test | grep -v __pycache__',
        pass_exit_codes=(1,),
    ),
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


def _changed_migration_files(paths: Sequence[str]) -> list[str]:
    return [path for path in paths if path.startswith("alembic/versions/") and path.endswith(".py")]


def _changed_python_impl_files(paths: Sequence[str]) -> list[str]:
    targets: list[str] = []
    for path in paths:
        path_obj = Path(path)
        if not path.endswith(".py"):
            continue
        if "tests" in path_obj.parts or path_obj.name.startswith("test_"):
            continue
        targets.append(path)
    return targets


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clip_output(value: str, limit: int) -> tuple[str, bool]:
    if len(value) <= limit:
        return value, False
    return value[:limit], True


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _run_gate(root: Path, spec: GateSpec, max_inline_chars: int) -> dict[str, object]:
    started_at = _utc_now()
    started = time.monotonic()
    try:
        result = subprocess.run(
            list(spec.argv),
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        stdout, stdout_truncated = _clip_output(result.stdout, max_inline_chars)
        stderr, stderr_truncated = _clip_output(result.stderr, max_inline_chars)
        finished_at = _utc_now()
        ok = result.returncode in spec.pass_exit_codes
        return {
            "id": spec.id,
            "kind": spec.kind,
            "command": spec.display_command,
            "cwd": str(root),
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_seconds": round(time.monotonic() - started, 3),
            "status": "passed" if ok else "failed",
            "ok": ok,
            "exit_code": result.returncode,
            "pass_exit_codes": list(spec.pass_exit_codes),
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
            "id": spec.id,
            "kind": spec.kind,
            "command": spec.display_command,
            "cwd": str(root),
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_seconds": round(time.monotonic() - started, 3),
            "status": "failed",
            "ok": False,
            "exit_code": None,
            "pass_exit_codes": list(spec.pass_exit_codes),
            "stdout": "",
            "stdout_sha256": _hash_text(""),
            "stdout_truncated": False,
            "stderr": message,
            "stderr_sha256": _hash_text(message),
            "stderr_truncated": False,
            "error": type(exc).__name__,
        }


def _skipped_result(
    root: Path,
    entry_id: str,
    kind: str,
    command: str,
    reason: str,
    *,
    files_checked: Sequence[str] = (),
) -> dict[str, object]:
    timestamp = _utc_now()
    empty_hash = _hash_text("")
    return {
        "id": entry_id,
        "kind": kind,
        "command": command,
        "cwd": str(root),
        "started_at": timestamp,
        "finished_at": timestamp,
        "duration_seconds": 0.0,
        "status": "skipped",
        "ok": True,
        "exit_code": None,
        "pass_exit_codes": [],
        "stdout": "",
        "stdout_sha256": empty_hash,
        "stdout_truncated": False,
        "stderr": "",
        "stderr_sha256": empty_hash,
        "stderr_truncated": False,
        "skip_reason": reason,
        "files_checked": list(files_checked),
        "results": [],
    }


def _run_group(
    root: Path,
    entry_id: str,
    kind: str,
    command: str,
    paths: Sequence[str],
    build_spec: Callable[[str], GateSpec],
    max_inline_chars: int,
    empty_reason: str,
) -> dict[str, object]:
    if not paths:
        return _skipped_result(root, entry_id, kind, command, empty_reason)

    results: list[dict[str, object]] = []
    duration_seconds = 0.0
    started_at: str | None = None
    finished_at: str | None = None
    for path in paths:
        result = _run_gate(root, build_spec(path), max_inline_chars)
        result["target"] = path
        results.append(result)
        duration_seconds += float(result["duration_seconds"])
        if started_at is None:
            started_at = str(result["started_at"])
        finished_at = str(result["finished_at"])

    empty_hash = _hash_text("")
    failed = any(result["status"] == "failed" for result in results)
    return {
        "id": entry_id,
        "kind": kind,
        "command": command,
        "cwd": str(root),
        "started_at": started_at or _utc_now(),
        "finished_at": finished_at or _utc_now(),
        "duration_seconds": round(duration_seconds, 3),
        "status": "failed" if failed else "passed",
        "ok": not failed,
        "exit_code": None,
        "pass_exit_codes": [],
        "stdout": "",
        "stdout_sha256": empty_hash,
        "stdout_truncated": False,
        "stderr": "",
        "stderr_sha256": empty_hash,
        "stderr_truncated": False,
        "files_checked": list(paths),
        "results": results,
    }


def _migration_safety_gate(relative_path: str) -> GateSpec:
    return _argv_gate(
        f"migration_safety:{relative_path}",
        "bash",
        ".github/skills/migration-safety/scripts/check.sh",
        relative_path,
    )


def _cyclomatic_gate(relative_path: str) -> GateSpec:
    return _argv_gate(
        f"cyclomatic_complexity:{relative_path}",
        "bash",
        ".github/skills/cyclomatic-scorer/scripts/score.sh",
        relative_path,
        kind="check",
    )


def _status_counts(entries: Sequence[dict[str, object]]) -> dict[str, int]:
    return {
        "total": len(entries),
        "passed": sum(1 for entry in entries if entry["status"] == "passed"),
        "failed": sum(1 for entry in entries if entry["status"] == "failed"),
        "skipped": sum(1 for entry in entries if entry["status"] == "skipped"),
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
    migration_files = _changed_migration_files(changed_files)
    cyclomatic_targets = _changed_python_impl_files(changed_files)

    commands = [_run_gate(root, gate, args.max_inline_chars) for gate in REVIEW_GATES]
    if include_requirements_audit:
        commands.append(_run_gate(root, REQUIREMENTS_AUDIT_GATE, args.max_inline_chars))
    else:
        commands.append(
            _skipped_result(
                root,
                REQUIREMENTS_AUDIT_GATE.id,
                "gate",
                REQUIREMENTS_AUDIT_GATE.display_command,
                "requirements.txt not in scope",
            )
        )
    commands.append(_run_gate(root, BANDIT_GATE, args.max_inline_chars))
    commands.append(
        _run_group(
            root,
            "migration_safety",
            "gate",
            MIGRATION_SAFETY_COMMAND,
            migration_files,
            _migration_safety_gate,
            args.max_inline_chars,
            "no migrations in diff",
        )
    )

    checks = [_run_gate(root, check, args.max_inline_chars) for check in STATIC_CHECKS]
    checks.append(
        _run_group(
            root,
            "cyclomatic_complexity",
            "check",
            CYCLOMATIC_COMMAND,
            cyclomatic_targets,
            _cyclomatic_gate,
            args.max_inline_chars,
            "no changed Python implementation files in diff",
        )
    )

    finished_at = _utc_now()
    all_entries = commands + checks
    summary = _status_counts(all_entries)

    payload: dict[str, object] = {
        "tool": "deterministic-review-tooling/run_review_gates",
        "workspace": str(root),
        "started_at": started_at,
        "finished_at": finished_at,
        "ok": summary["failed"] == 0,
        "changed_files": changed_files,
        "requirements_audit_required": include_requirements_audit,
        "migration_safety_required": bool(migration_files),
        "cyclomatic_targets": cyclomatic_targets,
        "gate_ids": [entry["id"] for entry in commands],
        "check_ids": [entry["id"] for entry in checks],
        "commands": commands,
        "checks": checks,
        "summary": {
            **summary,
            "commands": _status_counts(commands),
            "checks": _status_counts(checks),
        },
    }
    _write_json(payload, args.output)
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
