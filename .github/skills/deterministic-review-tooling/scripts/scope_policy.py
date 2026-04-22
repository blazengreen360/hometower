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


def matches_any_rule(path: str, rules: tuple[str, ...]) -> bool:
    return any(matches_rule(path, rule) for rule in rules)


def first_matching_rule(path: str, rules: tuple[str, ...]) -> str | None:
    return next((rule for rule in rules if matches_rule(path, rule)), None)


def violation(path: str, rule: str, message: str) -> dict[str, str]:
    return {
        "path": path,
        "rule": rule,
        "message": message,
    }


def is_read_only_violation(policy: RolePolicy, ignore_read_only: bool) -> bool:
    return policy.read_only and not ignore_read_only


def evaluate_path_scope(
    role: str,
    path: str,
    policy: RolePolicy,
    ignore_read_only: bool,
) -> dict[str, str] | None:
    if not is_in_repo(path):
        return violation(
            path,
            "repo-local-only",
            "Path resolves outside the repository root.",
        )
    if is_read_only_violation(policy, ignore_read_only):
        return violation(
            path,
            "read-only-role",
            f"Role `{role}` is read-only in this scope checker.",
        )
    if policy.block_protected_pm_docs and matches_any_rule(path, PROTECTED_PM_DOCS):
        return violation(
            path,
            "protected-pm-doc",
            "Spawned subagents must not modify PM-owned progress documents.",
        )
    if policy.allowed_prefixes and not matches_any_rule(path, policy.allowed_prefixes):
        allowed = ", ".join(policy.allowed_prefixes)
        return violation(
            path,
            "role-allowlist",
            f"Role `{role}` is limited to: {allowed}.",
        )
    blocked_rule = first_matching_rule(path, policy.blocked_prefixes)
    if blocked_rule is not None:
        return violation(
            path,
            "role-blocklist",
            f"Role `{role}` must not modify paths under `{blocked_rule}`.",
        )
    return None


def evaluate_role_scope(role: str, files: list[str], ignore_read_only: bool = False) -> list[dict[str, str]]:
    policy = ROLE_POLICIES[resolve_role(role)]
    violations: list[dict[str, str]] = []
    for path in files:
        path_violation = evaluate_path_scope(role, path, policy, ignore_read_only)
        if path_violation is not None:
            violations.append(path_violation)
    return violations
