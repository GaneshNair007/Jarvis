# Nūs Desktop concepts adapted into JARVIS

This integration adapts selected product and workflow concepts from
[potlakai/nus-desktop](https://github.com/potlakai/nus-desktop) and its MIT
license, without importing its Electron application or its cloud-provider
runtime.

## What was adapted

- A personal workspace for courses, deadlines, tasks, and goals.
- A deterministic deadline and grade-weight-aware daily ranking model.
- A capture inbox where notes, facts, ideas, and task proposals remain pending
  until the owner reviews them.
- A daily briefing that explains why each item is prioritized.

The urgency bands and explainable ranking are adapted from the public
Nūs Desktop deterministic ranking workflow. The JARVIS implementation is
native Python and is covered by the upstream MIT notice in
licenses/NUS-DESKTOP-MIT.txt.

## What was deliberately not copied

- Electron, the Nūs Desktop renderer, or its SQL.js database runtime.
- Anthropic Claude or Gemini as mandatory providers.
- Any provider key requirement that would displace JARVIS's local Ollama-first
  configuration.
- The Nūs academic data model verbatim. JARVIS uses its existing SQLAlchemy
  UUID/JSON types, session factory, and database initialization.

## API

The router is exposed at both /workspace and /api/v1/workspace:

- GET/POST /courses
- GET/POST /assignments
- GET/POST /tasks
- POST /tasks/{task_id}/complete
- GET/POST /captures
- POST /captures/{capture_id}/review
- GET /briefing/today

New captures are pending by default. Approving a note, fact, or idea promotes it
to the existing durable memory table; approving a task proposal creates a
workspace task. Dismissal stores no memory or task.

## Reliability boundaries

Deadline ranking is deterministic and does not depend on an LLM. A capture is
not memory until a review action commits it. The briefing only summarizes
records actually stored in the local JARVIS database.

The local career pipeline is a tracker, not a live job-search feed. Each entry
has an evidence status: missing source URL, placeholder example URL, or saved
URL not yet live-verified. New internship/hackathon discovery uses the live
browser-search provider and returns unavailable when that provider fails.
Discovery links are not described as confirmed openings until the destination
page has been fetched and checked.

Public smart-home routes use the Home Assistant REST adapter only. They require
HASS_URL/HASS_TOKEN, a reachable controller, and a state readback before
reporting device-control success. The old SmartHomePowers class remains an
explicit in-memory demo; multi-device scenes and voice-to-device dispatch are
disabled in public routes until their individual actions can be verified.

Deep research no longer turns search snippets or synthetic HTML into citations.
A citation requires successful navigation and extracted page text. Reports
show FAILED or PARTIAL when the requested source count was not verified.

A Quartr connector is not enabled by this patch. Quartr's ChatGPT connector
and a local JARVIS process are separate runtimes; JARVIS needs an officially
documented API/MCP endpoint and credentials or an explicit export/import
workflow before it can call Quartr directly. Do not copy ChatGPT connector
tokens into JARVIS configuration.

Gmail sync, calendar access, a screen Companion, and other external accounts
still require their own credentials, adapters, and acceptance tests.

## Validation

Run:

    python -m pytest tests/test_workspace_service.py -q
    python -m pytest tests/test_model_router.py tests/test_orchestrator.py -q
    python -m ruff check jarvis/db/models/workspace.py jarvis/workspace jarvis/api/routes_workspace.py
    python -m ruff format --check jarvis/db/models/workspace.py jarvis/workspace jarvis/api/routes_workspace.py

The GitHub Actions checks on the pull request remain the authoritative
repository-level verification.
