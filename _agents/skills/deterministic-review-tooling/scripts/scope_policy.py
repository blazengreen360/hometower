#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath


PROTECTED_PM_DOCS: tuple[str, ...] = (
    "doc/progress.md",
    "doc/tracker.md",
    "doc/backlog.md",
)


@dataclass(frozen=True)
class RolePolicy:
    read_only: bool = False
    block_protected_pm_docs: bool = True
    allowed_prefixes: tuple[str, ...] = ()
    blocked_prefixes: tuple[str, ...] = ()


ROLE_POLICIES: dict[str, RolePolicy] = {
    "architect": RolePolicy(allowed_prefixes=("doc/rfc/",)),
    "chaos-tester": RolePolicy(allowed_prefixes=("scripts/", "tests/")),
    "ci-gatekeeper": RolePolicy(read_only=True),
    "code-reviewer": RolePolicy(read_only=True),
    "project-manager": RolePolicy(
        block_protected_pm_docs=False,
        allowed_prefixes=("doc/", "CHANGELOG.md", "vscode/memory"),
    ),
    "backend-engineer": RolePolicy(blocked_prefixes=("src/ui/",)),
    "frontend-engineer": RolePolicy(
        blocked_prefixes=("src/models/", "src/repositories/", "alembic/")
    ),
    "db-engineer": RolePolicy(allowed_prefixes=("src/models/", "src/repositories/", "alembic/")),
    "devops-engineer": RolePolicy(
        allowed_prefixes=("docker-compose.yml", "Dockerfile", ".env.example", "scripts/", "doc/deployment/")
    ),
    "user-simulator": RolePolicy(read_only=True),
    "qa-bug-finder": RolePolicy(read_only=True),
    "qa-orchestrator": RolePolicy(
        allowed_prefixes=("doc/bugs/",),
        blocked_prefixes=("doc/bugs/completed/",),
    ),
    "qa-remediation": RolePolicy(),
    "security-auditor": RolePolicy(read_only=True),
    "security-orchestrator": RolePolicy(
        allowed_prefixes=("doc/security/",),
        blocked_prefixes=("doc/security/completed/",),
    ),
    "test-automation-engineer": RolePolicy(allowed_prefixes=("tests/",)),
    "ux-designer": RolePolicy(allowed_prefixes=("src/ui/", "tests/", "doc/design/")),
    "refactoring-specialist": RolePolicy(),
}


ROLE_ALIASES: dict[str, str] = {
    "Bug-Finder": "qa-bug-finder",
    "bug-finder": "qa-bug-finder",
    "QA-Fixer": "qa-remediation",
    "qa-fixer": "qa-remediation",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def supported_roles() -> tuple[str, ...]:
    return tuple(sorted(set(ROLE_POLICIES) | set(ROLE_ALIASES)))


def resolve_role(role: str) -> str:
    return ROLE_ALIASES.get(role, role)


def normalize_repo_path(root: Path, raw_path: str) -> str:
    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        try:
            return candidate.resolve(strict=False).relative_to(root).as_posix()
        except ValueError:
            return candidate.as_posix()
    normalized = PurePosixPath(raw_path).as_posix()
    if normalized.startswith("./"):
        return normalized[2:]
    return normalized


def dedupe_paths(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            ordered.append(path)
    return ordered


def matches_rule(path: str, rule: str) -> bool:
    if rule.endswith("/"):
        return path.startswith(rule)
    return path == rule


def is_in_repo(path: str) -> bool:
    return not Path(path).is_absolute() and not path.startswith("../")


def evaluate_role_scope(role: str, files: list[str], ignore_read_only: bool = False) -> list[dict[str, str]]:
    policy = ROLE_POLICIES[resolve_role(role)]
    violations: list[dict[str, str]] = []
    for path in files:
        if not is_in_repo(path):
            violations.append(
                {
                    "path": path,
                    "rule": "repo-local-only",
                    "message": "Path resolves outside the repository root.",
                }
            )
            continue
        if policy.read_only and not ignore_read_only:
            violations.append(
                {
                    "path": path,
                    "rule": "read-only-role",
                    "message": f"Role `{role}` is read-only in this scope checker.",
                }
            )
            continue
        if policy.block_protected_pm_docs and any(matches_rule(path, rule) for rule in PROTECTED_PM_DOCS):
            violations.append(
                {
                    "path": path,
                    "rule": "protected-pm-doc",
                    "message": "Spawned subagents must not modify PM-owned progress documents.",
                }
            )
            continue
        if policy.allowed_prefixes and not any(matches_rule(path, rule) for rule in policy.allowed_prefixes):
            allowed = ", ".join(policy.allowed_prefixes)
            violations.append(
                {
                    "path": path,
                    "rule": "role-allowlist",
                    "message": f"Role `{role}` is limited to: {allowed}.",
                }
            )
            continue
        blocked_rule = next((rule for rule in policy.blocked_prefixes if matches_rule(path, rule)), None)
        if blocked_rule is not None:
            violations.append(
                {
                    "path": path,
                    "rule": "role-blocklist",
                    "message": f"Role `{role}` must not modify paths under `{blocked_rule}`.",
                }
            )
    return violations
