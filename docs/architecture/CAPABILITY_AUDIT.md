# JARVIS Comprehensive Capability Audit

**Generated:** 2026-11-03  
**Total Modules Audited:** 206 Python files under `jarvis/`  

## 1. Executive Summary & Classification Methodology

This audit presents a strict, evidence-based inventory of all modules in the JARVIS codebase. Every module is evaluated based on direct AST import chains, reachability from FastAPI REST routes, CLI entrypoints, and autonomous runners, and test coverage.

### Classification Criteria:
- **ACTIVE (79 modules)**: Reachable from production entrypoints (`server.py`, `main.py`, `cli.py`, or mounted routers) and covered by automated test suites.
- **DORMANT (103 modules)**: Code exists but is either:
  - Tested only in unit test isolation without being reachable in production request flows (27 modules).
  - Reachable from entrypoints but has zero dedicated unit or integration tests (76 modules).
- **DEAD (20 modules)**: Unreachable from any production entrypoint AND has zero automated tests.
- **DUPLICATE (4 modules)**: Overlapping or redundant implementations of the same capability.

### Summary Statistics

| Classification | Module Count | Percentage |
| :--- | :--- | :--- |
| **ACTIVE** | 79 | 38.3% |
| **DORMANT** | 103 | 50.0% |
| **DEAD** | 20 | 9.7% |
| **DUPLICATE** | 4 | 1.9% |
| **TOTAL** | **206** | **100.0%** |

---

## 2. Complete Module Inventory

| Module | Capability Claimed | Imported By | Reachable From Route/Scheduler/Bot? | Code Path (file:function → file:function) | Tests | Coverage Status | Classification |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `jarvis/__init__.py` | JARVIS: Personal AI Operating System | None (Orphan) | NO | NOT REACHABLE (No prod invocation) | 0 tests | UNTESTED | `DEAD` |
| `jarvis/agents/__init__.py` | JARVIS Multi-Agent Fusion Workers — Planner, Researcher, Executor, Critic. | None (Orphan) | NO | NOT REACHABLE (No prod invocation) | 0 tests | UNTESTED | `DEAD` |
| `jarvis/agents/autonomous_workforce.py` | JARVIS Autonomous Multi-Agent Workforce Swarm | 2 prod files (`jarvis/api/routes_workforce.py`) | YES | jarvis/api/routes_workforce.py → autonomous_workforce.py | 2 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/agents/critic.py` | JARVIS Critic Agent (PWR-294 / PWR-295) | `jarvis/agents/__init__.py` | NO | NOT REACHABLE (No prod invocation) | 1 test suite(s) | TESTED | `DORMANT` |
| `jarvis/agents/executor.py` | JARVIS Executor Agent (PWR-292 / PWR-293) | `jarvis/agents/__init__.py` | NO | NOT REACHABLE (No prod invocation) | 1 test suite(s) | TESTED | `DORMANT` |
| `jarvis/agents/gsoc_scout.py` | JARVIS GSoC Contributor Scout & Open-Source Preparation Engine | `jarvis/api/routes_gsoc.py` | YES | jarvis/api/routes_gsoc.py → gsoc_scout.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/agents/hackathon_scout.py` | JARVIS Autonomous Hackathon & Opportunity Multi-Agent Workforce | `jarvis/api/routes_scout.py` | NO | NOT REACHABLE (No prod invocation) | 1 test suite(s) | TESTED | `DORMANT` |
| `jarvis/agents/planner.py` | JARVIS Planner Agent (PWR-288 / PWR-289) | `jarvis/agents/__init__.py` | NO | NOT REACHABLE (No prod invocation) | 1 test suite(s) | TESTED | `DORMANT` |
| `jarvis/agents/researcher.py` | JARVIS Researcher Agent (PWR-290 / PWR-291) | `jarvis/agents/__init__.py` | NO | NOT REACHABLE (No prod invocation) | 1 test suite(s) | TESTED | `DORMANT` |
| `jarvis/agents/ruflo_swarm.py` | JARVIS RuFlo Reactive Consensus & Multi-Agent Swarm Protocol | None (Orphan) | NO | NOT REACHABLE (No prod invocation) | 1 test suite(s) | TESTED | `DORMANT` |
| `jarvis/agents/swarm.py` | Multi-Agent Swarm and Sub-Agent Orchestration Framework (PWR-288 to PWR-307). | 2 prod files (`jarvis/agents/__init__.py`) | YES | jarvis/agents/__init__.py → swarm.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/agents/venture_scout.py` | JARVIS Venture Scout & AI Business Idea Matching Engine | `jarvis/api/routes_ventures.py` | YES | jarvis/api/routes_ventures.py → venture_scout.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/api/__init__.py` | FastAPI REST and WebSocket interfaces for JARVIS. | None (Orphan) | NO | NOT REACHABLE (No prod invocation) | 0 tests | UNTESTED | `DEAD` |
| `jarvis/api/routes/reflections.py` | FastAPI Routes for Reflection Engine, Capabilities, and Self-Improvement Backlog | 2 prod files (`jarvis/api/routes_reflections.py`) | YES | jarvis/api/routes_reflections.py → reflections.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/api/routes_assistants.py` | OpenAI Assistants API Drop-in Compatibility Route for Project Jarvis. | `jarvis/api/server.py` | YES | jarvis/api/server.py → routes_assistants.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/api/routes_browser.py` | Browser and Research API Routes. | `jarvis/api/server.py` | YES | jarvis/api/server.py → routes_browser.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/api/routes_career.py` | Career-Ops REST API Routes (PWR-328 to PWR-337). | `jarvis/api/server.py` | YES | jarvis/api/server.py → routes_career.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/api/routes_desktop.py` | JARVIS Desktop Worker REST API Routes | `jarvis/api/server.py` | YES | jarvis/api/server.py → routes_desktop.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/api/routes_grok.py` | OpenMausBot & Grok Bot API Endpoints for Project JARVIS. | `jarvis/api/server.py` | YES | routes_grok.py → Grok Harness | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/api/routes_gsoc.py` | JARVIS GSoC Preparation & Open-Source Contributor REST API Endpoints | `jarvis/api/server.py` | YES | jarvis/api/server.py → routes_gsoc.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/api/routes_integrations.py` | JARVIS Integrations REST API Routes | `jarvis/api/server.py` | YES | jarvis/api/server.py → routes_integrations.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/api/routes_memory.py` | JARVIS Memory Vault & Document Intelligence REST API Routes | `jarvis/api/server.py` | YES | jarvis/api/server.py → routes_memory.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/api/routes_ops.py` | JARVIS Operational Workflows REST API Routes. | `jarvis/api/server.py` | YES | jarvis/api/server.py → routes_ops.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/api/routes_reflections.py` | Compatibility Re-export for Reflections API Router | None (Orphan) | NO | NOT REACHABLE (No prod invocation) | 0 tests | UNTESTED | `DUPLICATE` (Duplicate of jarvis/api/routes/reflections.py) |
| `jarvis/api/routes_scout.py` | JARVIS Autonomous Hackathon & Opportunity Scout API Routes | None (Orphan) | NO | NOT REACHABLE (No prod invocation) | 0 tests | UNTESTED | `DEAD` |
| `jarvis/api/routes_search.py` | JARVIS Local Search API Routes. | `jarvis/api/server.py` | YES | jarvis/api/server.py → routes_search.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/api/routes_smart_home.py` | JARVIS Smart Home & Room Control REST API Routes. | `jarvis/api/server.py` | YES | jarvis/api/server.py → routes_smart_home.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/api/routes_tasks.py` | Task Engine API Endpoints. | 2 prod files (`jarvis/api/server.py`) | YES | routes_tasks.py → Goal/Task DAG | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/api/routes_ventures.py` | JARVIS Venture & Business Ideas REST API Endpoints | `jarvis/api/server.py` | YES | jarvis/api/server.py → routes_ventures.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/api/routes_voice.py` | JARVIS Voice REST API Routes | `jarvis/api/server.py` | YES | jarvis/api/server.py → routes_voice.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/api/routes_workforce.py` | JARVIS Autonomous Workforce & WhatsApp Dispatch API Endpoints | `jarvis/api/server.py` | YES | jarvis/api/server.py → routes_workforce.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/api/server.py` | JARVIS Production FastAPI Server | `app/main.py` | YES | api/server.py → FastAPI Route | 19 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/brain/__init__.py` | JARVIS Cognitive Core & Brain Architecture. | None (Orphan) | NO | NOT REACHABLE (No prod invocation) | 0 tests | UNTESTED | `DEAD` |
| `jarvis/brain/checkpointer.py` | JARVIS SQLite State Checkpointer | None (Orphan) | NO | NOT REACHABLE (No prod invocation) | 4 test suite(s) | TESTED | `DORMANT` |
| `jarvis/brain/errors.py` | JARVIS Brain Error Taxonomy and Recovery Classification | None (Orphan) | NO | NOT REACHABLE (No prod invocation) | 1 test suite(s) | TESTED | `DORMANT` |
| `jarvis/brain/memory/__init__.py` | Durable memory core package for JARVIS Brain. | None (Orphan) | NO | NOT REACHABLE (No prod invocation) | 0 tests | UNTESTED | `DEAD` |
| `jarvis/brain/memory/interfaces.py` | Abstract Base Classes & Interfaces for Brain Memory Subsystems. | 2 prod files (`jarvis/brain/memory/__init__.py`) | YES | jarvis/brain/memory/__init__.py → interfaces.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/brain/memory/models.py` | SQLAlchemy Declarative Models for Canonical Brain Memory Records. | `jarvis/brain/memory/repository.py` | YES | jarvis/brain/memory/repository.py → models.py | 1 test suite(s) | TESTED | `DUPLICATE` (Overlaps jarvis/db/models/memory.py and jarvis/memory/models.py) |
| `jarvis/brain/memory/repository.py` | SQLAlchemy SQLite Implementation of Canonical Memory Repository. | 2 prod files (`jarvis/brain/memory/__init__.py`) | YES | jarvis/brain/memory/__init__.py → repository.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/brain/memory/service.py` | Brain Memory Service: High-level orchestration of canonical memory records. | 2 prod files (`jarvis/brain/memory/__init__.py`) | YES | jarvis/brain/memory/__init__.py → service.py | 2 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/brain/schemas.py` | Strongly typed cognitive schemas, enums, and data models for JARVIS Brain. | 5 prod files (`jarvis/brain/__init__.py`) | YES | jarvis/brain/__init__.py → schemas.py | 2 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/brain/state.py` | JARVIS Unified Cognitive State Schema | 2 prod files (`jarvis/brain/errors.py`) | YES | jarvis/brain/errors.py → state.py | 4 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/browser/__init__.py` | JARVIS Browser Subsystem. | None (Orphan) | NO | NOT REACHABLE (No prod invocation) | 0 tests | UNTESTED | `DEAD` |
| `jarvis/browser/context_manager.py` | Browser Context Manager. | 5 prod files (`jarvis/browser/__init__.py`) | YES | jarvis/browser/__init__.py → context_manager.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/browser/evidence.py` | Browser Evidence Subsystem. | 3 prod files (`jarvis/browser/__init__.py`) | YES | jarvis/browser/__init__.py → evidence.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/browser/research_worker.py` | Deep Research Worker. | 2 prod files (`jarvis/browser/__init__.py`) | YES | jarvis/browser/__init__.py → research_worker.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/browser/search_wrapper.py` | Web Search Engine Wrapper. | 4 prod files (`jarvis/agents/executor.py`) | YES | jarvis/agents/executor.py → search_wrapper.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/browser/url_reader.py` | DOM Content Reader and Sanitizer. | 5 prod files (`jarvis/agents/executor.py`) | YES | jarvis/agents/executor.py → url_reader.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/business/__init__.py` | JARVIS Business & Grok Bot Playbook Module | None (Orphan) | NO | NOT REACHABLE (No prod invocation) | 0 tests | UNTESTED | `DEAD` |
| `jarvis/business/playbook_engine.py` | JARVIS Autonomous Business Playbook & Grok Bot Engine | 2 prod files (`jarvis/api/routes_ventures.py`) | YES | jarvis/api/routes_ventures.py → playbook_engine.py | 2 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/capabilities/__init__.py` | JARVIS Capabilities Package | None (Orphan) | NO | NOT REACHABLE (No prod invocation) | 0 tests | UNTESTED | `DEAD` |
| `jarvis/capabilities/models.py` | Capability Models and Maturity Levels | 3 prod files (`jarvis/capabilities/__init__.py`) | YES | jarvis/capabilities/__init__.py → models.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/capabilities/registry.py` | JARVIS Capability Registry | 3 prod files (`jarvis/capabilities/__init__.py`) | YES | jarvis/capabilities/__init__.py → registry.py | 2 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/capabilities/service.py` | Capability Service (Database Synchronization Layer) | `jarvis/capabilities/__init__.py` | NO | NOT REACHABLE (No prod invocation) | 0 tests | UNTESTED | `DEAD` |
| `jarvis/career/__init__.py` | Career-Ops Integration Subsystem (Part B and Powers PWR-328 to PWR-337). | None (Orphan) | NO | NOT REACHABLE (No prod invocation) | 0 tests | UNTESTED | `DEAD` |
| `jarvis/career/analytics.py` | Application Pipeline Tracker & Funnel Analytics (PWR-335). | `jarvis/career/service.py` | YES | jarvis/career/service.py → analytics.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/career/company_research.py` | Company Research Brief and Dossier Engine (PWR-332). | `jarvis/career/service.py` | YES | jarvis/career/service.py → company_research.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/career/contact_finder.py` | Contact Finder and Outreach Draft Engine (PWR-333). | `jarvis/career/service.py` | YES | jarvis/career/service.py → contact_finder.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/career/cover_letter.py` | Tailored Cover Letter Generator (PWR-331). | `jarvis/career/service.py` | YES | jarvis/career/service.py → cover_letter.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/career/email_draft.py` | Application Email Draft Engine (PWR-334). | `jarvis/career/service.py` | YES | jarvis/career/service.py → email_draft.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/career/form_autofill_agent.py` | JARVIS Autonomous Application Form Autofill & Opportunity Radar Agent | None (Orphan) | NO | NOT REACHABLE (No prod invocation) | 2 test suite(s) | TESTED | `DORMANT` |
| `jarvis/career/interview_prep.py` | Interview Preparation and Red-Flag Checker (PWR-336). | `jarvis/career/service.py` | YES | jarvis/career/service.py → interview_prep.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/career/models.py` | Data models for Career-Ops subsystem (PWR-328 to PWR-337). | 11 prod files (`jarvis/career/__init__.py`) | YES | jarvis/career/__init__.py → models.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/career/offer_analyzer.py` | Offer and Salary-Gap Analysis Engine (PWR-337). | `jarvis/career/service.py` | YES | jarvis/career/service.py → offer_analyzer.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/career/resume_generator.py` | Tailored ATS Resume Generator (PWR-330). | `jarvis/career/service.py` | YES | jarvis/career/service.py → resume_generator.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/career/scanner.py` | Job Scan and Fit Scoring Engine (PWR-329). | `jarvis/career/service.py` | YES | jarvis/career/service.py → scanner.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/career/service.py` | Career-Ops Service Layer (PWR-328). | 2 prod files (`jarvis/career/__init__.py`) | YES | jarvis/career/__init__.py → service.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/cli.py` | JARVIS Unified Command-Line Interface (CLI) | None (Orphan) | YES | entry → cli.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/computer/desktop_worker.py` | JARVIS Desktop Worker (See–Act–Verify Loop) | 3 prod files (`jarvis/agents/executor.py`) | YES | jarvis/agents/executor.py → desktop_worker.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/config.py` | JARVIS Centralized Configuration Module. | 33 prod files (`jarvis/api/routes_search.py`) | YES | jarvis/api/routes_search.py → config.py | 2 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/constants.py` | JARVIS Central Constants Module. | 6 prod files (`jarvis/api/server.py`) | YES | jarvis/api/server.py → constants.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/core/__init__.py` | Core orchestration, safety, routing, and audit modules for JARVIS. | `jarvis/graph/nodes.py` | YES | jarvis/graph/nodes.py → __init__.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/core/action_decorator.py` | ActionWeaver-inspired Action Decorator for Project Jarvis. | None (Orphan) | NO | NOT REACHABLE (No prod invocation) | 1 test suite(s) | TESTED | `DORMANT` |
| `jarvis/core/api_key_rotator.py` | JARVIS Multi-Account API Key Rotator & Resilient Cloud Gateway. | 4 prod files (`jarvis/core/config.py`) | YES | jarvis/core/config.py → api_key_rotator.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/core/audit.py` | JARVIS Cryptographic Hash-Chained Audit Ledger | 17 prod files (`jarvis/agents/executor.py`) | YES | jarvis/agents/executor.py → audit.py | 5 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/core/audit_logger.py` | JARVIS Audit Logger | None (Orphan) | NO | NOT REACHABLE (No prod invocation) | 0 tests | UNTESTED | `DEAD` |
| `jarvis/core/capability_guard.py` | JARVIS Capability Guard — Sprint 1 Trust Fix | None (Orphan) | NO | NOT REACHABLE (No prod invocation) | 0 tests | UNTESTED | `DEAD` |
| `jarvis/core/config.py` | JARVIS Core Configuration Substrate. | None (Orphan) | NO | NOT REACHABLE (No prod invocation) | 1 test suite(s) | TESTED | `DORMANT` |
| `jarvis/core/cost_governor.py` | JARVIS Cost Governor & Budget Controller | 2 prod files (`jarvis/api/server.py`) | YES | jarvis/api/server.py → cost_governor.py | 2 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/core/gemini_rotator.py` | JARVIS Gemini Multi-Account API Key Rotator (Compatibility Re-export). | `jarvis/core/model_router.py` | YES | jarvis/core/model_router.py → gemini_rotator.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/core/guards.py` | JARVIS Architecture Guards | `jarvis/cli.py` | YES | jarvis/cli.py → guards.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/core/intent_router.py` | JARVIS Fast Intent Router (Jev-Style Decision Engine). | None (Orphan) | NO | NOT REACHABLE (No prod invocation) | 1 test suite(s) | TESTED | `DORMANT` |
| `jarvis/core/logger.py` | JARVIS Structured Logging Module | 90 prod files (`jarvis/agents/autonomous_workforce.py`) | YES | jarvis/agents/autonomous_workforce.py → logger.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/core/mcp_client.py` | JARVIS Model Context Protocol (MCP) Client Substrate. | None (Orphan) | NO | NOT REACHABLE (No prod invocation) | 1 test suite(s) | TESTED | `DORMANT` |
| `jarvis/core/model_router.py` | JARVIS Policy-Aware Three-Tier Hybrid Model Router | 8 prod files (`jarvis/agents/critic.py`) | YES | jarvis/agents/critic.py → model_router.py | 10 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/core/notifier.py` | JARVIS Multi-Channel Alert & Dispatch Engine | 2 prod files (`jarvis/agents/hackathon_scout.py`) | NO | NOT REACHABLE (No prod invocation) | 1 test suite(s) | TESTED | `DORMANT` |
| `jarvis/core/obscura_browser.py` | JARVIS Obscura CDP & Stealth Web Perception Engine | 2 prod files (`jarvis/agents/hackathon_scout.py`) | NO | NOT REACHABLE (No prod invocation) | 1 test suite(s) | TESTED | `DORMANT` |
| `jarvis/core/openmaus_grok.py` | JARVIS OpenMausBot Integration: Grok Bot Engine & Multi-Agent Loopback Harness | `jarvis/api/routes_grok.py` | YES | jarvis/api/routes_grok.py → openmaus_grok.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/core/openrouter_client.py` | JARVIS OpenRouter Frontier Gateway Client. | `jarvis/core/model_router.py` | YES | jarvis/core/model_router.py → openrouter_client.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/core/orchestrator.py` | JARVIS Central Orchestration Engine | 5 prod files (`jarvis/api/routes_assistants.py`) | YES | jarvis/api/routes_assistants.py → orchestrator.py | 3 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/core/policy_engine.py` | JARVIS Policy Engine (4-Tier Evaluation) | `jarvis/agents/executor.py` | NO | NOT REACHABLE (No prod invocation) | 2 test suite(s) | TESTED | `DORMANT` |
| `jarvis/core/policy_gate.py` | JARVIS Deterministic Policy Gate & Approval Engine | 8 prod files (`jarvis/api/routes_browser.py`) | YES | jarvis/api/routes_browser.py → policy_gate.py | 7 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/core/power_binder.py` | JARVIS Dynamic Power Binder & Tool Schema Generator. | `jarvis/core/action_decorator.py` | NO | NOT REACHABLE (No prod invocation) | 2 test suite(s) | TESTED | `DORMANT` |
| `jarvis/core/power_registry.py` | JARVIS Central Power Registry | 3 prod files (`jarvis/api/server.py`) | YES | jarvis/api/server.py → power_registry.py | 3 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/core/privacy_gate.py` | JARVIS Privacy Gate & Data Loss Prevention (DLP) | 2 prod files (`jarvis/core/model_router.py`) | YES | jarvis/core/model_router.py → privacy_gate.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/core/repo_map.py` | Aider-Inspired Abstract Syntax Tree (AST) Repository Map Generator for Projec... | None (Orphan) | NO | NOT REACHABLE (No prod invocation) | 1 test suite(s) | TESTED | `DORMANT` |
| `jarvis/core/scheduler.py` | JARVIS Proactive Autonomous Background Scheduler | `jarvis/api/server.py` | YES | jarvis/api/server.py → scheduler.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/core/state.py` | JARVIS LangGraph State Definition | 2 prod files (`jarvis/graph/jarvis_graph.py`) | YES | jarvis/graph/jarvis_graph.py → state.py | 2 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/core/state_machine.py` | JARVIS Task Lifecycle State Machine | 2 prod files (`jarvis/api/routes_tasks.py`) | YES | jarvis/api/routes_tasks.py → state_machine.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/core/step_telemetry.py` | Chainlit-inspired Step Telemetry and Streaming Manager for Project Jarvis. | None (Orphan) | NO | NOT REACHABLE (No prod invocation) | 1 test suite(s) | TESTED | `DORMANT` |
| `jarvis/core/task_executor.py` | JARVIS Task Graph Executor (Async Parallel DAG Execution Engine) | 2 prod files (`jarvis/api/routes_tasks.py`) | YES | jarvis/api/routes_tasks.py → task_executor.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/core/task_graph.py` | JARVIS Task Graph Engine (DAG Schema V1 & Graph Topology) | 15 prod files (`jarvis/api/routes/reflections.py`) | YES | jarvis/api/routes/reflections.py → task_graph.py | 3 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/core/task_memory_writer.py` | JARVIS Task Memory Integration Layer | `jarvis/core/task_executor.py` | YES | jarvis/core/task_executor.py → task_memory_writer.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/core/task_reflection.py` | JARVIS Task Reflection Layer (Post-Goal Retrospective & Continuous Improvement) | `jarvis/core/task_executor.py` | YES | jarvis/core/task_executor.py → task_reflection.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/core/task_router.py` | JARVIS Task Router & Agent Assignment Layer (CEO & Department Model) | `jarvis/core/task_executor.py` | YES | jarvis/core/task_executor.py → task_router.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/core/task_scheduler.py` | JARVIS Task Scheduler (Priority Queue & Concurrency Controller) | `jarvis/core/task_executor.py` | YES | jarvis/core/task_executor.py → task_scheduler.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/core/task_verifier.py` | JARVIS Task Verification Layer (Quality, Functional, and Security Gates) | `jarvis/core/task_executor.py` | YES | jarvis/core/task_executor.py → task_verifier.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/core/validate_powers.py` | JARVIS Power Catalog Integrity Validator | None (Orphan) | NO | NOT REACHABLE (No prod invocation) | 1 test suite(s) | TESTED | `DORMANT` |
| `jarvis/core/visual_grounding.py` | JARVIS GUI Visual Grounding & Safe Desktop Control. | None (Orphan) | NO | NOT REACHABLE (No prod invocation) | 1 test suite(s) | TESTED | `DORMANT` |
| `jarvis/core/voice_stream.py` | JARVIS Voice Pipeline Substrate (Kokoro-TTS & Faster-Whisper Hooks). | None (Orphan) | NO | NOT REACHABLE (No prod invocation) | 1 test suite(s) | TESTED | `DORMANT` |
| `jarvis/core/web_recon.py` | JARVIS Web Reconnaissance & High-Density Opportunity Hunter | 3 prod files (`jarvis/agents/autonomous_workforce.py`) | YES | jarvis/agents/autonomous_workforce.py → web_recon.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/db/__init__.py` | JARVIS Database & Operational Brain Package | None (Orphan) | NO | NOT REACHABLE (No prod invocation) | 0 tests | UNTESTED | `DEAD` |
| `jarvis/db/events.py` | JARVIS Event Publishing & Reactive Event Bus | 5 prod files (`jarvis/db/__init__.py`) | YES | jarvis/db/__init__.py → events.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/db/models/__init__.py` | JARVIS Database Models Package | `jarvis/db/session.py` | YES | jarvis/db/session.py → __init__.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/db/models/agent.py` | SQLAlchemy 2.x Agent Model for JARVIS | 3 prod files (`jarvis/db/models/__init__.py`) | YES | jarvis/db/models/__init__.py → agent.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/db/models/artifact.py` | SQLAlchemy 2.x Artifact Model for JARVIS | 2 prod files (`jarvis/db/models/__init__.py`) | YES | jarvis/db/models/__init__.py → artifact.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/db/models/assignment.py` | SQLAlchemy 2.x Agent Assignment Model for JARVIS | 2 prod files (`jarvis/db/models/__init__.py`) | YES | jarvis/db/models/__init__.py → assignment.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/db/models/audit.py` | SQLAlchemy 2.x Audit Trail Model for JARVIS | 2 prod files (`jarvis/db/models/__init__.py`) | YES | jarvis/db/models/__init__.py → audit.py | 4 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/db/models/base.py` | SQLAlchemy 2.x Base and Universal Column Types for JARVIS | 17 prod files (`jarvis/db/models/__init__.py`) | YES | jarvis/db/models/__init__.py → base.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/db/models/department.py` | SQLAlchemy 2.x Department Model for JARVIS | `jarvis/db/models/__init__.py` | YES | jarvis/db/models/__init__.py → department.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/db/models/dependency.py` | SQLAlchemy 2.x Task Dependency Model for JARVIS | 3 prod files (`jarvis/db/models/__init__.py`) | YES | jarvis/db/models/__init__.py → dependency.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/db/models/execution.py` | SQLAlchemy 2.x Execution Model for JARVIS | 2 prod files (`jarvis/db/models/__init__.py`) | YES | jarvis/db/models/__init__.py → execution.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/db/models/goal.py` | SQLAlchemy 2.x Goal Model for JARVIS | 3 prod files (`jarvis/db/models/__init__.py`) | YES | jarvis/db/models/__init__.py → goal.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/db/models/knowledge.py` | SQLAlchemy 2.x Knowledge Graph Models for JARVIS | 2 prod files (`jarvis/db/models/__init__.py`) | YES | jarvis/db/models/__init__.py → knowledge.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/db/models/lifecycle.py` | SQLAlchemy 2.x Agent Lifecycle Model for JARVIS | 2 prod files (`jarvis/db/models/__init__.py`) | YES | jarvis/db/models/__init__.py → lifecycle.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/db/models/memory.py` | SQLAlchemy 2.x Memory Model for JARVIS | 3 prod files (`jarvis/db/models/__init__.py`) | YES | jarvis/db/models/__init__.py → memory.py | 5 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/db/models/opportunity.py` | SQLAlchemy 2.x Opportunity Model for JARVIS | 3 prod files (`jarvis/db/models/__init__.py`) | YES | jarvis/db/models/__init__.py → opportunity.py | 2 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/db/models/reflection.py` | SQLAlchemy 2.x Reflection Model for JARVIS | 2 prod files (`jarvis/db/models/__init__.py`) | YES | jarvis/db/models/__init__.py → reflection.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/db/models/schedule.py` | SQLAlchemy 2.x Schedule Model for JARVIS | 2 prod files (`jarvis/db/models/__init__.py`) | YES | jarvis/db/models/__init__.py → schedule.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/db/models/task.py` | SQLAlchemy 2.x Task and TaskGraph Models for JARVIS | 4 prod files (`jarvis/db/models/__init__.py`) | YES | jarvis/db/models/__init__.py → task.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/db/redis_state.py` | JARVIS Redis Real-Time Agent State Layer | 3 prod files (`jarvis/db/__init__.py`) | NO | NOT REACHABLE (No prod invocation) | 1 test suite(s) | TESTED | `DORMANT` |
| `jarvis/db/repositories/__init__.py` | JARVIS Repositories Package | `jarvis/capabilities/service.py` | NO | NOT REACHABLE (No prod invocation) | 0 tests | UNTESTED | `DEAD` |
| `jarvis/db/repositories/agent_repository.py` | JARVIS Agent Repository | 2 prod files (`jarvis/db/repositories/__init__.py`) | YES | jarvis/db/repositories/__init__.py → agent_repository.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/db/repositories/artifact_repository.py` | JARVIS Artifact Repository | 2 prod files (`jarvis/db/repositories/__init__.py`) | YES | jarvis/db/repositories/__init__.py → artifact_repository.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/db/repositories/assignment_repository.py` | JARVIS Agent Assignment Repository | 2 prod files (`jarvis/db/repositories/__init__.py`) | YES | jarvis/db/repositories/__init__.py → assignment_repository.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/db/repositories/audit_repository.py` | JARVIS Audit Repository | 2 prod files (`jarvis/db/repositories/__init__.py`) | YES | jarvis/db/repositories/__init__.py → audit_repository.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/db/repositories/base.py` | JARVIS Base Repository | 14 prod files (`jarvis/db/repositories/__init__.py`) | YES | jarvis/db/repositories/__init__.py → base.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/db/repositories/dependency_repository.py` | JARVIS Task Dependency Repository | 2 prod files (`jarvis/db/repositories/__init__.py`) | YES | jarvis/db/repositories/__init__.py → dependency_repository.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/db/repositories/execution_repository.py` | JARVIS Execution Repository | 2 prod files (`jarvis/db/repositories/__init__.py`) | YES | jarvis/db/repositories/__init__.py → execution_repository.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/db/repositories/goal_repository.py` | JARVIS Goal Repository | 2 prod files (`jarvis/db/repositories/__init__.py`) | YES | jarvis/db/repositories/__init__.py → goal_repository.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/db/repositories/graph_repository.py` | JARVIS Knowledge Graph Repository | 2 prod files (`jarvis/db/repositories/__init__.py`) | YES | jarvis/db/repositories/__init__.py → graph_repository.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/db/repositories/memory_repository.py` | JARVIS Memory Repository | 2 prod files (`jarvis/db/repositories/__init__.py`) | YES | jarvis/db/repositories/__init__.py → memory_repository.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/db/repositories/opportunity_repository.py` | JARVIS Opportunity Repository | 2 prod files (`jarvis/db/repositories/__init__.py`) | YES | jarvis/db/repositories/__init__.py → opportunity_repository.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/db/repositories/reflection_repository.py` | JARVIS Reflection Repository | 2 prod files (`jarvis/db/repositories/__init__.py`) | YES | jarvis/db/repositories/__init__.py → reflection_repository.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/db/repositories/scheduler_repository.py` | JARVIS Scheduler Repository | 2 prod files (`jarvis/db/repositories/__init__.py`) | YES | jarvis/db/repositories/__init__.py → scheduler_repository.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/db/repositories/task_repository.py` | JARVIS Task Repository | 2 prod files (`jarvis/db/repositories/__init__.py`) | YES | jarvis/db/repositories/__init__.py → task_repository.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/db/session.py` | JARVIS Database Engine and Session Management | 2 prod files (`jarvis/db/__init__.py`) | YES | jarvis/db/__init__.py → session.py | 5 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/db/unit_of_work.py` | JARVIS Unit of Work Pattern | 7 prod files (`jarvis/core/task_memory_writer.py`) | YES | jarvis/core/task_memory_writer.py → unit_of_work.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/graph/jarvis_graph.py` | No docstring | `jarvis/api/server.py` | YES | jarvis/api/server.py → jarvis_graph.py | 6 test suite(s) | TESTED | `DUPLICATE` (Overlaps graph/jarvis_graph.py) |
| `jarvis/graph/nodes.py` | No docstring | `jarvis/graph/jarvis_graph.py` | YES | jarvis/graph/jarvis_graph.py → nodes.py | 7 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/main.py` | JARVIS Unified CLI & Server Entry Point | None (Orphan) | YES | entry → main.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/memory/__init__.py` | Persistent 5-layer memory and SQLite WAL store for JARVIS. | None (Orphan) | NO | NOT REACHABLE (No prod invocation) | 0 tests | UNTESTED | `DEAD` |
| `jarvis/memory/correction_engine.py` | JARVIS User Correction Engine | `jarvis/api/routes_memory.py` | YES | jarvis/api/routes_memory.py → correction_engine.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/memory/document_rag.py` | JARVIS Document Intelligence & Local RAG System | 2 prod files (`jarvis/agents/researcher.py`) | YES | jarvis/agents/researcher.py → document_rag.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/memory/layers.py` | JARVIS 7-Layer Private Memory Vault Architecture | 3 prod files (`jarvis/api/routes_memory.py`) | YES | jarvis/api/routes_memory.py → layers.py | 2 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/memory/mem0_client.py` | JARVIS Mem0 Memory Client Adapter | 2 prod files (`jarvis/agents/researcher.py`) | YES | jarvis/agents/researcher.py → mem0_client.py | 2 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/memory/models.py` | JARVIS SQLAlchemy Database Schema & Persistence Models | 2 prod files (`jarvis/brain/memory/models.py`) | YES | jarvis/brain/memory/models.py → models.py | 1 test suite(s) | TESTED | `DUPLICATE` (Overlaps jarvis/brain/memory/models.py and jarvis/db/models/memory.py) |
| `jarvis/memory/store.py` | JARVIS SQLite WAL Database Store | 9 prod files (`jarvis/agents/gsoc_scout.py`) | YES | jarvis/agents/gsoc_scout.py → store.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/powers/__init__.py` | Power implementations categorized by operational domain. | 2 prod files (`jarvis/core/power_binder.py`) | YES | jarvis/core/power_binder.py → __init__.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/powers/automation_powers.py` | JARVIS Automation and Workflow Powers (PWR-271 to PWR-287) | `jarvis/powers/__init__.py` | YES | jarvis/powers/__init__.py → automation_powers.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/powers/browser_powers.py` | JARVIS Browser and Research Powers (PWR-013 to PWR-015, PWR-063 to PWR-067). | 4 prod files (`jarvis/api/routes_browser.py`) | YES | jarvis/api/routes_browser.py → browser_powers.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/powers/calendar_powers.py` | JARVIS Local Calendar Powers (PWR-041 to PWR-045). | 2 prod files (`jarvis/core/power_binder.py`) | YES | jarvis/core/power_binder.py → calendar_powers.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/powers/career_powers.py` | JARVIS Career-Ops Powers (PWR-328 to PWR-337). | 3 prod files (`jarvis/api/routes_career.py`) | YES | jarvis/api/routes_career.py → career_powers.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/powers/communication_powers.py` | JARVIS Communication Powers (PWR-202 to PWR-214). | `jarvis/powers/__init__.py` | YES | jarvis/powers/__init__.py → communication_powers.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/powers/desktop_powers.py` | JARVIS Desktop Computer Use Powers | `jarvis/powers/__init__.py` | YES | jarvis/powers/__init__.py → desktop_powers.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/powers/developer_powers.py` | JARVIS Developer Powers (PWR-025 to PWR-047, PWR-162 to PWR-178). | `jarvis/powers/__init__.py` | YES | jarvis/powers/__init__.py → developer_powers.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/powers/dictation_powers.py` | JARVIS Dictation & Text Processing Powers (PWR-050 to PWR-062) | `jarvis/powers/__init__.py` | YES | jarvis/powers/__init__.py → dictation_powers.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/powers/email_powers.py` | JARVIS Email Powers (PWR-051 to PWR-055). | 3 prod files (`jarvis/core/orchestrator.py`) | YES | jarvis/core/orchestrator.py → email_powers.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/powers/file_powers.py` | JARVIS File & Document Powers (PWR-082 to PWR-099) | 2 prod files (`jarvis/core/orchestrator.py`) | YES | jarvis/core/orchestrator.py → file_powers.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/powers/finance_powers.py` | JARVIS Finance and Market Powers (PWR-215 to PWR-236) | 2 prod files (`jarvis/core/orchestrator.py`) | YES | jarvis/core/orchestrator.py → finance_powers.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/powers/homeassistant_powers.py` | JARVIS Home Assistant Local REST Powers (PWR-238 to PWR-252). | 2 prod files (`jarvis/core/power_binder.py`) | YES | jarvis/core/power_binder.py → homeassistant_powers.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/powers/instant_powers.py` | JARVIS Instant Local Command Powers (PWR-027 to PWR-049) | `jarvis/powers/__init__.py` | YES | jarvis/powers/__init__.py → instant_powers.py | 2 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/powers/ironman_powers.py` | JARVIS Advanced Iron Man Powers (PWR-308 to PWR-327) | 2 prod files (`jarvis/core/orchestrator.py`) | YES | jarvis/core/orchestrator.py → ironman_powers.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/powers/it_admin_powers.py` | JARVIS IT Administration Powers (PWR-100 to PWR-126) | 3 prod files (`jarvis/api/server.py`) | YES | jarvis/api/server.py → it_admin_powers.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/powers/multiagent_powers.py` | JARVIS Multi-Agent Swarm Powers (PWR-288 to PWR-307) | `jarvis/powers/__init__.py` | YES | jarvis/powers/__init__.py → multiagent_powers.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/powers/networking_powers.py` | JARVIS Networking Powers (PWR-127 to PWR-143) | 2 prod files (`jarvis/core/orchestrator.py`) | YES | jarvis/core/orchestrator.py → networking_powers.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/powers/research_derived_powers.py` | JARVIS Research-Derived Powers (PWR-338 to PWR-355). | `jarvis/powers/__init__.py` | YES | jarvis/powers/__init__.py → research_derived_powers.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/powers/screen_powers.py` | JARVIS Screen & Window Powers (PWR-016 to PWR-026) | 2 prod files (`jarvis/powers/__init__.py`) | YES | jarvis/powers/__init__.py → screen_powers.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/powers/security_powers.py` | JARVIS Security and DLP Powers (PWR-144 to PWR-161, PWR-268 to PWR-287). | 2 prod files (`jarvis/core/orchestrator.py`) | YES | jarvis/core/orchestrator.py → security_powers.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/powers/smart_home_powers.py` | JARVIS Smart Home Powers (PWR-256 to PWR-269). | 3 prod files (`jarvis/api/routes_smart_home.py`) | YES | jarvis/api/routes_smart_home.py → smart_home_powers.py | 2 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/powers/voice_powers.py` | JARVIS Voice & Audio Interaction Powers (PWR-001 to PWR-005) | `jarvis/powers/__init__.py` | YES | jarvis/powers/__init__.py → voice_powers.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/powers/whatsapp_dispatcher.py` | JARVIS WhatsApp Dispatcher Power (PWR-338) | 3 prod files (`jarvis/agents/autonomous_workforce.py`) | YES | jarvis/agents/autonomous_workforce.py → whatsapp_dispatcher.py | 2 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/powers/youtube_powers.py` | JARVIS YouTube Creator Powers (PWR-237 to PWR-255) | 2 prod files (`jarvis/core/orchestrator.py`) | YES | jarvis/core/orchestrator.py → youtube_powers.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/reflection/__init__.py` | JARVIS Reflection Engine Package | 3 prod files (`jarvis/api/routes/reflections.py`) | YES | jarvis/api/routes/reflections.py → __init__.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/reflection/analyzer.py` | JARVIS Reflection Engine - Execution Analyzer | 3 prod files (`jarvis/reflection/__init__.py`) | YES | jarvis/reflection/__init__.py → analyzer.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/reflection/gap_detector.py` | JARVIS Reflection Engine - Capability Gap Detector | 2 prod files (`jarvis/reflection/__init__.py`) | YES | jarvis/reflection/__init__.py → gap_detector.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/reflection/improvement_generator.py` | JARVIS Reflection Engine - Improvement Generator | `jarvis/reflection/__init__.py` | YES | jarvis/reflection/__init__.py → improvement_generator.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/reflection/opportunity_detector.py` | JARVIS Reflection Engine - Opportunity Detector | `jarvis/reflection/__init__.py` | YES | jarvis/reflection/__init__.py → opportunity_detector.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/reflection/scorer.py` | JARVIS Reflection Engine - Constitution & Quality Scorer | `jarvis/reflection/__init__.py` | YES | jarvis/reflection/__init__.py → scorer.py | 0 tests | UNTESTED | `DORMANT` |
| `jarvis/routines/ops_workflows.py` | JARVIS Core Ops Workflows (Grok Bot Business Playbook & 200 AI Ideas Implemen... | 2 prod files (`jarvis/api/routes_ops.py`) | YES | jarvis/api/routes_ops.py → ops_workflows.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/search/hybrid_reranker.py` | LLM-Search & Elastic-Labs inspired Reciprocal Rank Fusion (RRF) Hybrid Reranker. | None (Orphan) | NO | NOT REACHABLE (No prod invocation) | 1 test suite(s) | TESTED | `DORMANT` |
| `jarvis/security/ten_layer_shield.py` | JARVIS 10-Layer Defense-in-Depth Security Suite (Ironclad Data Loss Preventio... | 11 prod files (`jarvis/agents/autonomous_workforce.py`) | YES | jarvis/agents/autonomous_workforce.py → ten_layer_shield.py | 3 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/self_improvement/__init__.py` | JARVIS Self-Improvement Package | None (Orphan) | NO | NOT REACHABLE (No prod invocation) | 0 tests | UNTESTED | `DEAD` |
| `jarvis/self_improvement/service.py` | JARVIS Self-Improvement Pipeline | 2 prod files (`jarvis/cli.py`) | YES | jarvis/cli.py → service.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/services/__init__.py` | JARVIS Services Package | None (Orphan) | NO | NOT REACHABLE (No prod invocation) | 0 tests | UNTESTED | `DEAD` |
| `jarvis/services/agent_service.py` | JARVIS Agent Workforce Service | `jarvis/services/__init__.py` | NO | NOT REACHABLE (No prod invocation) | 1 test suite(s) | TESTED | `DORMANT` |
| `jarvis/services/goal_service.py` | JARVIS Goal Service | 3 prod files (`jarvis/api/routes_tasks.py`) | YES | jarvis/api/routes_tasks.py → goal_service.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/services/memory_service.py` | JARVIS Memory Service | `jarvis/services/__init__.py` | NO | NOT REACHABLE (No prod invocation) | 0 tests | UNTESTED | `DEAD` |
| `jarvis/services/opportunity_service.py` | JARVIS Opportunity Service | `jarvis/services/__init__.py` | NO | NOT REACHABLE (No prod invocation) | 1 test suite(s) | TESTED | `DORMANT` |
| `jarvis/services/task_service.py` | JARVIS Task Service | `jarvis/services/__init__.py` | NO | NOT REACHABLE (No prod invocation) | 1 test suite(s) | TESTED | `DORMANT` |
| `jarvis/voice/__init__.py` | JARVIS Voice interaction pipeline (Wake word, STT, TTS, Full duplex audio). | None (Orphan) | NO | NOT REACHABLE (No prod invocation) | 0 tests | UNTESTED | `DEAD` |
| `jarvis/voice/pipeline.py` | JARVIS Full-Duplex Voice Pipeline (PWR-005) | `jarvis/api/routes_voice.py` | YES | jarvis/api/routes_voice.py → pipeline.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/voice/stt.py` | JARVIS Speech-to-Text (STT) Module (PWR-003) | 2 prod files (`jarvis/api/routes_voice.py`) | YES | jarvis/api/routes_voice.py → stt.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/voice/tts.py` | JARVIS Text-to-Speech (TTS) Module (PWR-004) | 3 prod files (`jarvis/api/routes_voice.py`) | YES | jarvis/api/routes_voice.py → tts.py | 2 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/voice/wake.py` | JARVIS Wake Word Detection (PWR-001 & PWR-002) | 3 prod files (`jarvis/api/routes_voice.py`) | YES | jarvis/api/routes_voice.py → wake.py | 1 test suite(s) | TESTED | `ACTIVE` |
| `jarvis/workflows/pr_workflow.py` | JARVIS Safe PR Workflow & Human Gatekeeper Engine | `jarvis/self_improvement/service.py` | YES | jarvis/self_improvement/service.py → pr_workflow.py | 1 test suite(s) | TESTED | `ACTIVE` |