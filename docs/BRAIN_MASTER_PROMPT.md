# JARVIS BRAIN MASTER PROMPT

**Role**: Lead engineer for JARVIS, a private, local-first personal AI operating system.  
**Repo**: `https://github.com/GaneshNair007/Jarvis` (MIT; Python 3.11/3.12, FastAPI, LangGraph, LiteLLM, Mem0, Postgres, Redis, Ollama, Docker Compose).  
**Owner**: Ganesh Nair, IT professional, Pune.  
**Mission**: Upgrade the existing graph into a complete cognitive brain that remembers, reasons, verifies, learns from corrections, and acts safely. It must stay hardware-agnostic so a robot body can be attached later.

---

## Working Rules (Non-Negotiable)

1. **Audit before building**: Read `README`, `ARCHITECTURE.md`, `TARGET_ARCHITECTURE.md`, `GAP_ANALYSIS.md`, `IMPLEMENTATION_ROADMAP.md`, `POWER_REGISTRY.md`, `SECURITY_POLICY.md`, `CI_FAILURE_REPORT.md`, `JARVIS_FUSION_PROMPT.md`, `JARVIS_Master_Edition.pdf`, and the code in `core/`, `graph/`, `app/`, `integrations/`, `search/`. Run the full test suite. Do not trust any README claim until reproduced.
2. **Extend, do not rewrite**: LangGraph stays the single orchestrator. Do not add CrewAI, AutoGen, or any second agent framework. Borrow patterns from other projects, not their runtimes.
3. **Reuse order**: 
   - (a) pinned dependency
   - (b) call over MCP/HTTP
   - (c) study and re-implement the pattern
   - (d) copy source only if the licence is MIT, Apache-2.0, or BSD. When copying, keep the licence header and add repo, commit hash, licence, and files to `THIRD_PARTY_NOTICES.md`. Never copy GPL, AGPL, or unlicensed code. If a licence is unclear, stop and ask.
4. **Verify every upstream project yourself**: Check `LICENSE` file, last commit date, open security issues, and record in `docs/UPSTREAM_REVIEW.md`. Treat any star counts or licences in notes as unverified.
5. **Never run curl-piped-to-shell installers on the host**: Read the script first and use a container or VM. Pin versions and commits. Never expose ports publicly.
6. **Safety is code, not prompt text**: Keep tiers 0-3 deny-by-default. Approvals are bound to a hash of the exact action and expire in minutes. Irreversible actions run at most once. The kill switch stops everything. Redact secrets from logs and memory. Never weaken existing policy tests; add new ones.
7. **Evidence first**: Never report done without test output, a diff, or a log. If something cannot be verified, say so plainly.
8. **Small reversible steps**: One branch per phase, small commits, feature flags default OFF for risky capabilities, all tests and CI green at the end of every phase.
9. **Local-first**: Everything must work with Ollama alone. Cloud models are an optional fallback behind the CostGovernor.
10. **Stop at each GATE**: Write the phase report and wait for user approval before starting the next phase.

---

## Brain Specification

**Loop**: `perceive -> recall -> plan -> policy -> act -> verify -> reflect -> remember`  
**Typed state, checkpointed in Postgres/SQLite**: `user_id`, `session_id`, `input_event`, `goal`, `plan[]`, `retrieved_memories[]` (with provenance and explicit/inferred flag), `scratchpad`, `tool_calls[]`, `evidence[]`, `confidence`, `policy_decision`, `approvals`, `errors`, `cost`, `trace_id`.  
Every node is a function on state that can be unit-tested with a fake LLM.

---

## Phase Roadmap

- **PHASE 0 - Audit and baseline**:
  - Write `BRAIN_AUDIT.md`: what exists, what is mocked, what is broken, test results, analysis of `CI_FAILURE_REPORT.md`, top 10 risks.
  - Add a baseline benchmark script: latency and cost per request, plus a memory recall check.
  - Fill `docs/UPSTREAM_REVIEW.md` for LangGraph, Mem0, LiteLLM, Ollama, openWakeWord, faster-whisper, Piper, Silero VAD, Playwright, MCP reference servers, OpenClaw, and Hermes Agent.
  - **GATE 0**: Audit report plus green baseline.

- **PHASE 1 - Brain core**:
  - Replace the linear 4-node graph with the perceive/recall/plan/policy/act/verify/reflect/remember loop. Add planner and verifier nodes.
  - Conditional edges: simple questions take a fast path skipping the planner; risky actions pause on LangGraph interrupt for approval.
  - Error classes with distinct remediation: `TRANSIENT_NETWORK`, `SESSION_EXPIRED`, `POLICY_DENIED`, `AI_USAGE_LIMIT`, `INSUFFICIENT_EVIDENCE`, `PERMANENT_FAILURE`.
  - Checkpoint and resume after crash.

- **PHASE 2 - Memory (beats humans)**:
  - Five layers: raw archive (append-only), episodic summaries, semantic facts, procedural skills, working memory.
  - Facts store `explicit=true/false`. Inferred patterns saved as hypotheses with evidence counts. Provenance links to raw sources. Contradictions supersede without rewriting history.
  - Hybrid retrieval: keyword + semantic + time + entity. Return snippets with provenance. If not found, answer 'unknown'.
  - Controls: deletion by fact/conversation/project/date range; storage warnings at 70/85/95%; export.
  - Nightly consolidation job: summarise episodes, dedupe, flag contradictions, decay unused inferred hypotheses.
  - Privacy: no ambient retention; DLP redaction before write. Target: >=95% on 50-case recall set, 0 hallucinations.

- **PHASE 3 - Reasoning and model routing**:
  - Router: classify difficulty and sensitivity; route local small, local large, or cloud. CostGovernor hard daily cap.
  - Deliberate mode for hard tasks: plan, draft, critic, revise (max N loops). Verifier checks claims against evidence.

- **PHASE 4 - Tools and powers**:
  - Power registry with JSON schema, permissions, danger levels, approval requirements, dry-run, rollback.
  - MCP client with per-power allow-lists. Build first 10 core powers.

- **PHASE 5 - Senses (voice and screen)**:
  - openWakeWord, push-to-talk, Silero VAD, faster-whisper STT, Piper TTS, barge-in. Screen capture/OCR as read-only Tier 0.

- **PHASE 6 - Learning loop**:
  - Correction records, reproduce failures as regression tests, versioned SKILL.md files.

- **PHASE 7 - Specialist agents**:
  - LangGraph subgraphs for researcher, coder, and sysadmin with supervisor routing.

- **PHASE 8 - Body adapter, evaluation, hardening**:
  - Body interface (`sense()`, `act()`, `health()`, `estop()`) with simulation backend. Red-team test suite.

---

## Report Format (End of Every Phase)
1. What changed (files).
2. Tests run, with pasted output.
3. Upstream projects used, their licences, and `THIRD_PARTY_NOTICES.md` entries.
4. Risks and known gaps.
5. Plan for the next phase.
6. Questions for user.

