#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scope_policy import dedupe_paths, evaluate_role_scope, normalize_repo_path, repo_root, supported_roles


def load_files(root: Path, direct_files: list[str], files_from: list[Path]) -> list[str]:
    paths = [normalize_repo_path(root, path) for path in direct_files]
    for source in files_from:
        for line in source.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped:
                paths.append(normalize_repo_path(root, stripped))
    return dedupe_paths(paths)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check role/file scope boundaries with deterministic JSON output.")
    parser.add_argument("--role", required=True, choices=supported_roles())
    parser.add_argument("--file", action="append", default=[], dest="files")
    parser.add_argument("--files-from", action="append", default=[], dest="files_from", type=Path)
    args = parser.parse_args()

    root = repo_root()
    files = load_files(root, args.files, args.files_from)
    violations = evaluate_role_scope(args.role, files)
    payload = {
        "tool": "deterministic-review-tooling/scope_guard",
        "ok": len(violations) == 0,
        "role": args.role,
        "files_checked": files,
        "violations": violations,
    }
    sys.stdout.write(f"{json.dumps(payload, indent=2, sort_keys=True)}\n")
    return 0 if payload["ok"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
