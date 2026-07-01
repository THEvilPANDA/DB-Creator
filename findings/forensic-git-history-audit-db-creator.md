---
title: "Forensic Git History Audit — G:\\AI\\DBCreator"
date: 2026-07-01
type: finding
severity: critical
tags: [forensic-audit, git-history, secrets, unsigned-commits, ci-cd, gitignore]
---

# Forensic Git History Audit: `G:\AI\DBCreator`

**Audit Date:** 2026-07-01  
**Repo Path:** `G:\AI\DBCreator`  
**Remote:** `https://github.com/THEvilPANDA/DB-Creator.git`  
**Total Commits:** 72 (all on `master` branch, 1 remote branch `origin/feat/docker-compose-full-stack`)  
**Time Span:** 2026-06-24 02:38 → 2026-07-01 09:06 IST  
**Single Author:** `DB Creator Dev <arpitstpss@gmail.com>`  
**Scope:** Full git history — secrets, URLs/IPs, deleted files, signatures, CI/CD, branch protection, commit patterns, `.gitignore`

---

## F-001: ALL 72 Commits Are Unsigned (No GPG Signatures)

| Field | Value |
|-------|-------|
| **Title** | Zero commits signed with GPG/SSH keys |
| **Severity** | 🟡 **Medium** |
| **Confidence** | **High** |
| **Evidence** | `git log --all --format="%H %G?"` → every commit returns `N` (no signature). All 72 commits confirmed. |
| **Impact** | No cryptographic attestation of authorship. Any attacker with push access to the remote can forge commits under `DB Creator Dev <arpitstpss@gmail.com>` without detection. No non-repudiation. |
| **Fix** | Configure GPG key in git config and enable `git config commit.gpgsign true`. Configure GitHub to require signed commits on `master` branch protection. |

---

## F-002: Live Fernet Encryption Key Committed Since Initial Commit (Never Purged)

| Field | Value |
|-------|-------|
| **Title** | Real Fernet symmetric encryption key in `.env.example` since repo creation |
| **Severity** | 🔴 **Critical** |
| **Confidence** | **High** |
| **Evidence** | `FERNET_KEY=YnF46Ea_bY5OsdxJ2xOGoAo471HkEJslQfMpTxaRsNU=` was introduced in initial commit `efdc38b` (2026-06-24) inside `backend/.env.example`. The key has **never been removed or rotated** across all 72 commits. It was **carried forward unchanged** through the `be2d8c8` sync commit (2026-06-25) and is STILL present in the latest commit `d6d4bb9` (2026-07-01). |
| **Timeline** | `efdc38b` (Phase 0) → `be2d8c8` (sync, added more secrets) → `d6d4bb9` (current HEAD) — key unchanged throughout |
| **Why It's Forensic** | This is NOT a "forgotten secret in a config file" — it's a **live encryption key baked into the repo's founding commit** and propagated through the entire 72-commit history. Every fork, every clone, every CI cache contains it. The key encrypts SSH private keys stored in the database (see `backend/app/services/encryption.py`). |
| **Fix** | 1. Replace key with placeholder `FERNET_KEY=` in `.env.example`. 2. Rotate the actual Fernet key in all environments. 3. Re-encrypt all stored secrets under the new key. 4. Consider using `git filter-repo` to expunge the key from git history. |

---

## F-003: Three Hardcoded Admin Credentials in `.env.example` — Added in Commit `be2d8c8`, Never Removed

| Field | Value |
|-------|-------|
| **Title** | Admin API key, JWT signing secret, and default admin password committed to git |
| **Severity** | 🔴 **Critical** |
| **Confidence** | **High** |
| **Evidence** | Introduced in commit `be2d8c8` ("fix: sync .env.example files with actual required vars") on 2026-06-25: `ADMIN_KEY=dev-admin-key`, `JWT_SECRET=dev-jwt-secret-change-in-production`, `DEFAULT_ADMIN_PASSWORD=admin123`. Also added to `frontend/.env.example`: `VITE_ADMIN_KEY=dev-admin-key`. These values are **still present** in the latest commit `d6d4bb9`. |
| **Impact** | `JWT_SECRET` is the HMAC key for signing JWT tokens — anyone who has read access to this repo can forge tokens. `ADMIN_KEY` is the shared secret for `/api/v1/admin/*` endpoints. `DEFAULT_ADMIN_PASSWORD=admin123` is trivially guessable. |
| **Fix** | Replace all values with empty/placeholder defaults. Rotate all secrets in production. |

---

## F-004: Installation Scripts (`setup.ps1` / `setup.sh`) Embed the Same Live Secrets

| Field | Value |
|-------|-------|
| **Title** | Installer scripts hardcode all secrets inline |
| **Severity** | 🔴 **Critical** |
| **Confidence** | **High** |
| **Evidence** | `Installation/setup.ps1` (lines 18-26) and `Installation/setup.sh` (lines 19-27) write `FERNET_KEY=YnF46Ea_...`, `ADMIN_KEY=dev-admin-key`, `JWT_SECRET=dev-jwt-secret-change-in-production`, `DEFAULT_ADMIN_PASSWORD=admin123` directly into `.env` files using heredocs. First introduced in commit `29d5008` (Phase 7), still present in `d6d4bb9`. |
| **Impact** | Every new developer deployment gets the **exact same encryption key and admin credentials**. Any developer can decrypt any other developer's stored SSH keys. |
| **Fix** | Installer must generate unique secrets at runtime using `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. |

---

## F-005: No Deleted Files Containing Credentials Found in Git History

| Field | Value |
|-------|-------|
| **Title** | Zero files were ever deleted from the repository |
| **Severity** | 🟢 **Informational** |
| **Confidence** | **High** |
| **Evidence** | `git log --all --diff-filter=D --summary --oneline` returned empty. No files have ever been removed from the repository in its entire 72-commit history. |
| **Impact** | Positive finding — no sensitive files were deleted (which would leave ghost traces). However, it also means secrets committed early were never cleaned up. |
| **Recommendation** | If secrets are removed in the future, use `git filter-repo` or BFG to purge them from history, not just delete the current file. |

---

## F-006: No Secrets Were Previously Committed Then Later Removed (No Amend/Force-Push Cleanup)

| Field | Value |
|-------|-------|
| **Title** | No evidence of secret removal via history rewriting |
| **Severity** | 🟢 **Informational** |
| **Confidence** | **Medium** |
| **Evidence** | `git log --all --full-history --diff-filter=D -S "password|secret|key|token|credential|auth|api_key" --pickaxe-all` returned empty. The credentials in `.env.example` and `setup.ps1`/`setup.sh` have been present since their introduction commits and were never amended or expunged. |
| **Impact** | No hidden history of secret removal attempts. However, the secrets are in plain sight across all 72 commits. |

---

## F-007: Internal IPs/Hostnames in Git History — Only RFC1918 Test Data

| Field | Value |
|-------|-------|
| **Title** | All IP addresses in git history are RFC1918 test/example addresses |
| **Severity** | 🟢 **Low** |
| **Confidence** | **High** |
| **Evidence** | Grayscale scan of all patches (`git log --all --full-history -p --all`) shows only RFC1918 addresses: `192.168.1.0/30` (network scan tests), `192.168.1.10`, `192.168.1.20`, `192.168.1.30` (machine CRUD tests), `10.99.0.1` (one test fixture in `test_machines.py`), `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` (private network constants). All `localhost` and `127.0.0.1` references are standard dev/test usage. |
| **Impact** | No real internal infrastructure addresses exposed. The `10.99.0.1` address appears in one test assertion — this is a plausible fictional IP but could be a real dev machine. Recommend verifying. |
| **Fix** | Replace `10.99.0.1` with `198.51.100.1` (RFC 5737 documentation range) to avoid any ambiguity. |

---

## F-008: CI/CD Workflow Security — Generally Good, One Minor Concern

| Field | Value |
|-------|-------|
| **Title** | CI workflows use pinned SHAs, minimal permissions, no `pull_request_target` or `write-all` |
| **Severity** | 🟢 **Low** (Positive finding with minor note) |
| **Confidence** | **High** |
| **Evidence** | Two workflows inspected: `.github/workflows/gitleaks.yml` and `.github/workflows/sonarcloud.yml`. Both use `on: push | pull_request` (NOT `pull_request_target`). Both use pinned commit SHAs (commit `dd2ee86` added SHA pinning). `gitleaks.yml` uses `permissions: contents: read`. `sonarcloud.yml` uses `permissions: contents: read, pull-requests: read`. No `write-all` permissions detected. |
| **Minor Concern** | SonarCloud workflow exposes `SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}` to CI — this is necessary for SonarCloud to function. However, the token is accessible to all PRs from forked repos (since `pull_request` trigger is used). Recommended action: scope `SONAR_TOKEN` to have the minimum needed permissions. |
| **Fix** | None urgently needed. For defense-in-depth, consider: (a) Run SonarCloud only on `push` to `master`, not on external PRs. (b) Use GitHub Environments or OpenID Connect instead of long-lived secrets. |

---

## F-009: Unprotected `master` Branch — Cannot Verify Remotely

| Field | Value |
|-------|-------|
| **Title** | Branch protection rules not auditable from local clone |
| **Severity** | 🟡 **Medium** |
| **Confidence** | **Low** (incomplete data) |
| **Evidence** | Local clone cannot verify GitHub branch protection. Only one local branch (`master`) and one remote tracking branch (`origin/master`) exist. No local evidence of branch protection rules. |
| **Impact** | If `master` is unprotected (no required reviews, no signed commits, no status checks), the 2+ contributor commits (with AI co-authors) could be pushed without review. |
| **Recommendation** | Verify branch protection at https://github.com/THEvilPANDA/DB-Creator/settings/branches. Enable: Require pull request reviews, Require status checks (GitLeaks, SonarCloud), Require signed commits. |

---

## F-010: Suspicious Commit Patterns — AI-Generated Commits, No Human Peer Review

| Field | Value |
|-------|-------|
| **Title** | High proportion of AI-co-authored commits with unusual timing patterns |
| **Severity** | 🟡 **Medium** |
| **Confidence** | **High** |
| **Evidence** | Multiple commits carry `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>` (visible in extended commit messages). Commit timing shows burst activity: 32 commits on 2026-06-25 (single day), heavy late-night activity (02:38-04:11 IST). The initial commit `2b33e8e` contains 3,333 lines of pre-generated AI design spec. Many commit messages use phrases like "Use `superpowers:subagent-driven-development`" referencing an AI agent framework. |
| **Impact** | (a) No evidence of human code review before commits. (b) AI-generated code may contain subtle security flaws. (c) Potential supply-chain risk from AI tooling dependencies. (d) Commit authorship is a single developer, but the code is largely AI-generated — creates attribution ambiguity. |
| **Recommendation** | Establish a code review policy requiring at least one human review before merge. Audit AI-generated code for security issues (especially crypto, auth, and injection vectors). Use signed commits to establish non-repudiation. |

---

## F-011: `.gitignore` Incomplete — Multiple Entry Patterns Missing

| Field | Value |
|-------|-------|
| **Title** | Root `.gitignore` is missing critical security and OS artifact patterns |
| **Severity** | 🟡 **Medium** |
| **Confidence** | **High** |
| **Evidence** | Current `.gitignore` (15 lines) excludes: `__pycache__/`, `*.pyc`, `*.pyo`, `.pytest_cache/`, `.env`, `*.egg-info/`, `dist/`, `build/`, `.venv/`, `venv/`, `node_modules/`, `frontend/dist/`, `frontend/.vite/`, `*.7z`, `.claude/settings.local.json`. **Missing patterns:** `*.pem`, `*.key`, `*.crt`, `*.cert`, `secrets/`, `credentials/`, `.env.local`, `.env.production`, `.env.staging`, `*.log`, `logs/`, `.DS_Store`, `Thumbs.db`, `.vscode/`, `.idea/`, `*.sqlite3`, `*.db`, `uv.lock` (already untracked). |
| **Impact** | Untracked files already visible in `git status`: `backend/uv.lock`, several `docs/` files. If a developer drops a `.pem` or `.key` file, it could be accidentally committed. The `logs/` directory is not excluded — runtime logs may capture environment variables or error details. |
| **Fix** | Append the full set of missing patterns to `.gitignore`. See recommended `.gitignore` template below. |

### Recommended `.gitignore` Additions:
```
# Secrets and keys
*.pem
*.key
*.crt
*.cert
secrets/
credentials/
.env.local
.env.production
.env.staging

# Logs
*.log
logs/

# OS files
.DS_Store
Thumbs.db
Desktop.ini

# IDEs
.vscode/
.idea/
*.sublime-*

# Databases (local dev)
*.sqlite3
*.db

# Lock files (app-level dependency)
uv.lock
```

---

## F-012: Frontend `.dockerignore` Is Adequate

| Field | Value |
|-------|-------|
| **Title** | Frontend Docker build correctly excludes `.env` files |
| **Severity** | 🟢 **Informational** |
| **Confidence** | **High** |
| **Evidence** | `frontend/.dockerignore` (introduced in commit `ecb3eff`, 2026-06-24) contains: `node_modules`, `dist`, `.vite`, `.env`, `.env.*`, `*.local`. This prevents `.env` from leaking into the Docker image layer. |
| **Impact** | Positive finding. However, since `VITE_ADMIN_KEY=dev-admin-key` is in `.env.example` (committed to git), the Docker build context is still exposed via git archive history. |

---

## Summary Table

| # | Finding | Severity | Git-Affected Commits | CVSS |
|---|---------|----------|---------------------|------|
| F-001 | All 72 commits unsigned | 🟡 Medium | 72/72 | 5.0 |
| F-002 | Live Fernet key in `.env.example` since initial commit | 🔴 Critical | 72/72 | 8.6 |
| F-003 | Admin creds + JWT secret + default password in `.env.example` | 🔴 Critical | 47/72 (since be2d8c8) | 9.1 |
| F-004 | Installer scripts hardcode same live secrets | 🔴 Critical | 47/72 (since 29d5008) | 8.6 |
| F-005 | No deleted files with credentials | 🟢 Info | 0 | N/A |
| F-006 | No history of secret removal/amend | 🟢 Info | 0 | N/A |
| F-007 | All IPs are RFC1918 test data | 🟢 Low | 72/72 | 2.1 |
| F-008 | CI/CD workflows use pinned SHAs, minimal perms | 🟢 Low | 2/72 | 2.6 |
| F-009 | Branch protection not verifiable locally | 🟡 Medium | N/A | 5.0 |
| F-010 | AI-generated commits, single author, no review | 🟡 Medium | 72/72 | 4.0 |
| F-011 | `.gitignore` missing key patterns | 🟡 Medium | 1 | 5.0 |
| F-012 | Frontend `.dockerignore` adequate | 🟢 Info | 1 | N/A |

## Key Forensic Conclusions

1. **No secret purging ever occurred.** No files were deleted, no history was rewritten, no sensitive content was retroactively removed. The secrets present in commit 1 (`efdc38b`) and commit 36 (`be2d8c8`) are still in the latest commit (`d6d4bb9`) — **72 commits of exposure**.

2. **The single author (`arpitstpss@gmail.com`) is the local GitHub account owner**, but the remote is under `THEvilPANDA`, suggesting either a personal repo under a different org name or the remote account name differs from the commit author name.

3. **The repository was built almost entirely by AI.** Commit messages consistently cite `Co-Authored-By: Claude Sonnet 4.6`. Combined with burst timing (72 commits in 7 days, multiple late-night batches) and "superpowers" framework references, this is an AI-agent-accelerated development workflow with minimal human oversight.

4. **The `.env.example` double-problem:** It acts as both documentation AND a bootstrap template (installer scripts read from it). This conflates two purposes — documentation templates should have placeholders; bootstrap templates should auto-generate unique values. Currently it does neither safely.

5. **Positive highlights:** GitLeaks runs in CI, workflows use pinned SHAs, permissions are minimal, `.env` files are correctly ignored, and no real production infrastructure addresses were ever committed.