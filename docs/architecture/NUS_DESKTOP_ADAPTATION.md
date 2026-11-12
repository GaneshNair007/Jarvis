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
records actually stored in the local JARVIS database. This integration does
not connect a syllabus parser, a calendar account, Gmail, an external smart
home controller, or a screen Companion; those integrations require separate
credentials, configuration, and acceptance tests.

## Validation

Run:

    python -m pytest tests/test_workspace_service.py -q
    python -m pytest tests/test_model_router.py tests/test_orchestrator.py -q
    python -m ruff check jarvis/db/models/workspace.py jarvis/workspace jarvis/api/routes_workspace.py
    python -m ruff format --check jarvis/db/models/workspace.py jarvis/workspace jarvis/api/routes_workspace.py

The GitHub Actions checks on the pull request remain the authoritative
repository-level verification.
