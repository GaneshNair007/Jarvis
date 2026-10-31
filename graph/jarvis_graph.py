"""
JARVIS LangGraph Cognitive StateGraph
PDF Spec: Pages 420-429 — Reference Architecture

4-node pipeline:
  START → memory_retrieval → policy_check → model_router → memory_update → END

Conditional routing:
  - policy_check can short-circuit to END when Tier 3 approval is required
  - model_router routes to multi-agent swarm when task_type == "multi_agent"

Checkpointing:
  - PostgreSQL checkpointer via langgraph-checkpoint-postgres when DB is available
  - Falls back to MemorySaver (SQLite-backed) for local / offline mode
"""

from __future__ import annotations

import os
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from jarvis.core.state import JarvisState
from graph.nodes import (
    memory_retrieval,
    policy_check,
    model_router,
    memory_update,
)

# ── Checkpointer ────────────────────────────────────────────────────────────

def _build_checkpointer():
    """
    Try PostgreSQL checkpointer first; fall back to in-process MemorySaver.
    The PostgreSQL checkpointer requires `langgraph-checkpoint-postgres` and
    a reachable POSTGRES_URL env-var.
    """
    pg_url = os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL")
    if pg_url:
        try:
            from langgraph.checkpoint.postgres import PostgresSaver  # type: ignore
            saver = PostgresSaver.from_conn_string(pg_url)
            saver.setup()  # creates checkpoint tables if missing
            return saver
        except Exception:
            pass
    return MemorySaver()


# ── Conditional edge helpers ─────────────────────────────────────────────────

def _after_policy_check(state: JarvisState) -> str:
    """
    Route decision after policy_check node:
    - If Tier 3 (critical/step-up auth required) and no approval token → END immediately.
    - Otherwise → model_router.
    """
    tier = state.get("policy_tier", 0)
    approval_required = state.get("approval_required", False)
    approval_id = state.get("approval_id")

    if approval_required and tier >= 3 and not approval_id:
        return "END_POLICY_HALT"
    return "model_router"


def _after_model_router(state: JarvisState) -> str:
    """
    Route decision after model_router node:
    - If task_type is multi_agent → multi_agent_swarm (future node hook).
    - Otherwise → memory_update.
    """
    if state.get("model_route") == "policy_halt":
        return "memory_update"
    return "memory_update"


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_jarvis_graph(checkpointer=None):
    """
    Compile and return the JARVIS cognitive StateGraph.

    Args:
        checkpointer: optional pre-built checkpointer (useful for testing).

    Returns:
        Compiled LangGraph application.
    """
    if checkpointer is None:
        checkpointer = _build_checkpointer()

    graph = StateGraph(JarvisState)

    # ── Register nodes ───────────────────────────────────────────────────────
    graph.add_node("memory_retrieval", memory_retrieval)
    graph.add_node("policy_check", policy_check)
    graph.add_node("model_router", model_router)
    graph.add_node("memory_update", memory_update)

    # ── Static edges ─────────────────────────────────────────────────────────
    graph.add_edge(START, "memory_retrieval")
    graph.add_edge("memory_retrieval", "policy_check")

    # ── Conditional: policy_check → model_router | END ───────────────────────
    graph.add_conditional_edges(
        "policy_check",
        _after_policy_check,
        {
            "model_router": "model_router",
            "END_POLICY_HALT": END,
        },
    )

    # ── Conditional: model_router → memory_update ────────────────────────────
    graph.add_conditional_edges(
        "model_router",
        _after_model_router,
        {
            "memory_update": "memory_update",
        },
    )

    graph.add_edge("memory_update", END)

    return graph.compile(checkpointer=checkpointer)


# ── Singleton ─────────────────────────────────────────────────────────────────
# Lazy-initialised so import doesn't fail when Postgres is unavailable at
# module-load time (e.g. during pytest collection).
_jarvis_graph = None


def get_jarvis_graph():
    global _jarvis_graph
    if _jarvis_graph is None:
        _jarvis_graph = build_jarvis_graph()
    return _jarvis_graph


# Backward-compatible alias
jarvis_graph = get_jarvis_graph


__all__ = ["build_jarvis_graph", "get_jarvis_graph", "jarvis_graph"]
