---
name: jarvis-ci-verification
description: Runs and audits JARVIS local and remote CI/CD quality pipelines. Use when preparing code for push or PR, troubleshooting pipeline failures, checking Ruff linting and formatting, running full test suites, or auditing dependencies.
---

# JARVIS CI/CD Quality & Verification Protocol

## Principles
1. **Zero Fake Passes**: Never use `continue-on-error`, `|| true`, weakened assertions, or test deletions to turn CI green.
2. **Deterministic Quality Gates**: Code must pass Ruff check, Ruff format, Pytest, and dependency audits.
3. **Local Pre-Flight Checks**: Always run checks locally before creating commits or pull requests.

## Local Verification Commands
1. **Linting Check**:
   ```powershell
   python -m ruff check .
   ```
2. **Formatting Check**:
   ```powershell
   python -m ruff format --check .
   ```
3. **Automated Test Suite with Coverage**:
   ```powershell
   python -m pytest tests --strict-config --strict-markers --cov=. --cov-config=.coveragerc --cov-report=term-missing --cov-fail-under=74
   ```
4. **Dependency Security Audit**:
   ```powershell
   python -m pip_audit -r requirements.txt --ignore-vuln CVE-2026-112940 --ignore-vuln CVE-2026-112913 --ignore-vuln CVE-2026-112907 --ignore-vuln CVE-2026-112938 --ignore-vuln CVE-2026-112936 --ignore-vuln CVE-2026-112910 --ignore-vuln CVE-2026-112909 --ignore-vuln CVE-2026-112911 --ignore-vuln CVE-2026-112939 --ignore-vuln CVE-2026-112915 --ignore-vuln CVE-2026-112935 --ignore-vuln CVE-2026-112912 --ignore-vuln CVE-2026-112908
   ```

## Merge Gate
GitHub Actions enforces the `Required CI` job aggregating:
- `quality` (Ruff lint and format)
- `tests` (Python 3.11 and 3.12 matrices on Linux)
- `dependencies` (pip-audit with explicit exceptions)
- `docker` (API and Dashboard container builds)
- `frontend` (Static dashboard assets)

