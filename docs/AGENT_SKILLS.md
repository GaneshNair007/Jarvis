# JARVIS Development Agent Skills Registry

This document catalogues the curated development skills active in the JARVIS workspace.
These skills guide Antigravity agents during development, architectural review, testing, security audits, and code simplification.
They are strictly distinguished from JARVIS runtime powers (`PWR-001` through `PWR-355`).

---

## 1. Primary Software Engineering Lifecycle Pack

**Source**: [Addy Osmani's Agent-Skills](https://github.com/addyosmani/agent-skills)  
**License**: MIT  
**Scope**: Project-local (`.agents/skills/`)  

| Skill Name | Purpose | Anti-Rationalization Guard |
|---|---|---|
| `spec-driven-development` | Formalize requirements and interfaces before writing code | Stops jumping directly into coding without decomposed goals |
| `planning-and-task-breakdown` | Breaks down tasks into ordered, verifiable atomic steps | Prevents monolithic changes that break regressions |
| `test-driven-development` | Enforces Red-Green-Refactor test cycle | Forbids writing code before failing test proof is created |
| `security-and-hardening` | Audits input gates, secrets, and zero-trust policies | Prevents accidental PII/secret exposure and unvalidated inputs |
| `code-review-and-quality` | Multi-axis pre-merge code review | Verifies code against production readiness standards |
| `code-simplification` | Reduces cyclomatic complexity and nesting | Prevents over-engineering and unmaintainable code |

---

## 2. Security & Code Review Pack

**Source**: [Trail of Bits Skills](https://github.com/trailofbits/skills)  
**License**: Apache-2.0  
**Scope**: Project-local (`.agents/skills/`)  

| Skill Name | Purpose | Review Scope |
|---|---|---|
| `audit-context-building` | Builds dependency and assumption context before bug-hunting | Architectural boundaries, guarantees, and failure modes |
| `audit-prep-assistant` | Prepares codebases for security review with systematic checklists | Static analysis, dead code elimination, test coverage |

---

## 3. Web & Accessibility Review Pack

**Source**: [Vercel Agent Skills](https://github.com/vercel-labs/agent-skills)  
**License**: MIT  
**Scope**: Project-local (`.agents/skills/`)  

| Skill Name | Purpose | Target Component |
|---|---|---|
| `web-design-guidelines` | Evaluates UI against accessibility, typography, and UX standards | `dashboard/index.html` Glassmorphic HUD |

---

## 4. Project-Specific JARVIS Engineering Skills

**Source**: Local (`.agents/skills/`)  

| Skill Name | Trigger / Activation | Target Files |
|---|---|---|
| `jarvis-architecture` | System architecture, orchestrator routing, state machine | `jarvis/core/orchestrator.py`, `jarvis/graph/jarvis_graph.py` |
| `jarvis-policy-security` | Policy gate, approvals, DLP redaction, kill switch | `jarvis/core/policy_gate.py`, `jarvis/core/privacy_gate.py`, `jarvis/core/audit.py` |
| `jarvis-power-implementation` | Implementing, registering, and testing powers | `jarvis/powers/*.py`, `data/powers_catalog.json` |
| `jarvis-local-search` | Sub-5ms hybrid search, SQLite FTS5, ingestors | `search/local_search_engine.py`, `search/ingestors/*.py` |
| `jarvis-ci-verification` | Running Ruff, Pytest, coverage, and dependency audits | `.github/workflows/ci.yml`, `requirements-ci.txt` |

