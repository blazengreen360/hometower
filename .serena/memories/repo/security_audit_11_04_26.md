# Security Audit Summary — 11 April 2026

**Report**: `doc/security/findings-report-11-04-26.1.md`

## Critical Findings (URGENT FIX REQUIRED)

1. **Hardcoded SECRET_KEY in .env** (CWE-798)
   - Repo commits JWT signing secret "dev_secret_key_for_local_development_only_32b"
   - Enables JWT forgery → instant Admin impersonation
   - FIX: Remove .env from git; provision via environment/secret manager

2. **No Workspace Scoping on Read Endpoints** (CWE-639)
   - Reader role returns ALL devices, connections, diagrams, locations, tags, services globally
   - No workspace_id filtering in repositories
   - Enables complete cross-tenant data exfiltration
   - FIX: Add workspace_id to all models; thread through service/repository queries

3. **Default Admin Credentials in .env** (CWE-798)
   - ADMIN_PASSWORD=changeme_on_first_boot in repo
   - Enables first-boot admin login if not rotated
   - FIX: Remove from repo; implement one-time bootstrap flow

## High Findings

- DB password hardcoded with default "secret" (CWE-798)
- Stateless JWT with no logout/revocation (CWE-613)
- Device names rendered unescaped in Cytoscape JS (CWE-79 XSS)
- Connection labels in dialogs without escaping (CWE-79 XSS)
- JWT tokens in sessionStorage (not HttpOnly) (CWE-522)

## Medium Findings

- Server-rendered UI labels with unescaped user input (CWE-79)
- Database missing uniqueness constraints on Connection, Service, CustomField, Tag (CWE-362)
- Export endpoint returns unredacted sensitive fields (CWE-213)
- System stats endpoint accessible to Reader (info disclosure)

## Clear Lanes

- SQL injection: no unsafe queries found
- RBAC bypass: all endpoints have require_role guards
- Plaintext secrets in logs: none found
- Supply chain CVEs: no matches in NVD/GitHub Advisory

## Routing

- **Tactical (Line-level code fixes)**: QA-Fixer → XSS escaping, export redaction, constraints
- **Structural (Design rework)**: Architect → workspace scoping, JWT revocation, key separation
- **Infrastructure**: DevOps-Engineer → secret provisioning, .env management

## Blocking Phase 2

Workspace scoping (Finding 9.1) is architectural; moving to multi-workspace without fixing data access control is high-risk.

## Next Steps

1. Archive this report to doc/security/completed/ after ALL findings reach terminal state (FIXED/ACCEPTED/ROUTED)
2. Do not deploy to production before secret rotation + workspace scoping mitigations
3. Add integration tests verifying cross-workspace isolation post-fix
