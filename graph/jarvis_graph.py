"""
JARVIS LangGraph Cognitive StateGraph
PDF Spec: Pages 420-429 — Reference Architecture & 8-Node State Machine

8-node cognitive execution loop:
  START -> perceive -> recall -> plan -> policy -> act -> verify -> reflect -> remember -> END

Conditional Routing:
  - recall -> policy (fast-path bypass) | plan (complex multi-step)
  - policy -> act (cleared) | END (Tier 3 policy halt)
  - verify -> reflect (self-correction & error diagnosis)
  - reflect -> plan / act (recoverable retries <= 3) | remember (complete / fatal)

Checkpointing:
  - PostgreSQL checkpointer via langgraph-checkpoint-postgres when POSTGRES_URL is set
  - SqliteCheckpointSaver backed by SQLite (WAL mode) as default local persistent checkpointer
  - MemorySaver fallback for in-memory testing
"""

from __future__ import annotations

import os
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from jarvis.core.state import JarvisState
from graph.nodes import (
    perceive,
    recall,
    plan,
    policy,
    act,
    verify,
    reflect,
    remember,
    memory_retrieval,
    policy_check,
    model_router,
    memory_update,
)
from jarvis.core.logger import get_logger

logger = get_logger("graph.jarvis_graph")


# ── Checkpointer Builder ─────────────────────────────────────────────────────


def _build_checkpointer():
    """
    Builds the checkpointer for the JARVIS StateGraph:
    1. PostgreSQL checkpointer if POSTGRES_URL or DATABASE_URL is set and reachable.
    2. SqliteCheckpointSaver for persistent, durable local state checkpointing.
    3. MemorySaver fallback if SQLite fails.
    """
    pg_url = os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL")
    if pg_url and pg_url.startswith(("postgres://", "postgresql://")):
        try:
            from langgraph.checkpoint.postgres import PostgresSaver  # type: ignore

            saver = PostgresSaver.from_conn_string(pg_url)
            saver.setup()
            logger.info("Using PostgreSQL checkpointer")
            return saver
        except Exception as exc:
            logger.warning(f"PostgreSQL checkpointer initialization failed — {exc}")

    try:
        from jarvis.brain.checkpointer import SqliteCheckpointSaver

        saver = SqliteCheckpointSaver()
        logger.info("Using SqliteCheckpointSaver default local checkpointer")
        return saver
    except Exception as exc:
        logger.warning(f"SqliteCheckpointSaver initialization failed, falling back to MemorySaver — {exc}")
        return MemorySaver()


# ── Conditional Edge Routing Helpers ─────────────────────────────────────────


def _after_recall(state: JarvisState) -> str:
    """
    Route decision after recall node:
    - If is_fast_path is True → bypass planner directly to policy.
    - Otherwise → plan.
    """
    if state.get("is_fast_path", False):
        logger.debug("Routing after recall: fast-path bypass to policy")
        return "policy"
    return "plan"


def _after_policy(state: JarvisState) -> str:
    """
    Route decision after policy node:
    - If Tier >= 3 (critical destructive / step-up auth required) and no approval token → END immediately.
    - Otherwise → act.
    """
    tier = state.get("policy_tier", 0)
    approval_required = state.get("approval_required", False)
    approval_id = state.get("approval_id")

    if approval_required and tier >= 3 and not approval_id:
        logger.warning("Routing after policy: Tier 3 halt without approval token")
        return "END_POLICY_HALT"
    return "act"


def _after_verify(state: JarvisState) -> str:
    """
    Route decision after verify node:
    - Transitions to reflect for error inspection and loop governance.
    """
    return "reflect"


def _after_reflect(state: JarvisState) -> str:
    """
    Route decision after reflect node:
    - If errors exist and reflection_count <= 3 and error is recoverable:
      - If TRANSIENT_NETWORK → retry act.
      - If INSUFFICIENT_EVIDENCE or other → replan.
    - Otherwise → remember.
    """
    errors = state.get("errors") or []
    reflection_count = state.get("reflection_count", 0)

    if errors and reflection_count <= 3:
        last_error = errors[-1] if isinstance(errors, list) and errors else {}
        is_recoverable = last_error.get("recoverable", False) if isinstance(last_error, dict) else False
        code = last_error.get("code") if isinstance(last_error, dict) else ""

        if is_recoverable:
            if code == "TRANSIENT_NETWORK":
                logger.info(f"Routing after reflect: retrying act (attempt {reflection_count}/3)")
                return "act"
            logger.info(f"Routing after reflect: replanning (attempt {reflection_count}/3)")
            return "plan"

    return "remember"


# ── Backward-Compatible Legacy Edge Helpers ──────────────────────────────────


def _after_policy_check(state: JarvisState) -> str:
    """Legacy helper for test compatibility."""
    tier = state.get("policy_tier", 0)
    approval_required = state.get("approval_required", False)
    approval_id = state.get("approval_id")

    if approval_required and tier >= 3 and not approval_id:
        return "END_POLICY_HALT"
    return "model_router"


def _after_model_router(state: JarvisState) -> str:
    """Legacy helper for test compatibility."""
    return "memory_update"


# ── Graph Builder ─────────────────────────────────────────────────────────────


def build_jarvis_graph(checkpointer=None):
    """
    Compile and return the 8-node JARVIS cognitive StateGraph.

    Pipeline:
      START -> perceive -> recall
        ↳ [fast-path] -> policy -> act -> verify -> reflect -> remember -> END
        ↳ [complex]   -> plan -> policy -> act -> verify -> reflect
                                ↳ [retry <= 3] -> plan / act
                                ↳ [complete / fatal] -> remember -> END

    Args:
        checkpointer: Optional pre-built checkpointer instance.

    Returns:
        Compiled LangGraph application.
    """
    if checkpointer is None:
        checkpointer = _build_checkpointer()

    graph = StateGraph(JarvisState)

    # ── Register all 8 Cognitive Nodes ───────────────────────────────────────
    graph.add_node("perceive", perceive)
    graph.add_node("recall", recall)
    graph.add_node("plan", plan)
    graph.add_node("policy", policy)
    graph.add_node("act", act)
    graph.add_node("verify", verify)
    graph.add_node("reflect", reflect)
    graph.add_node("remember", remember)

    # ── Backward-Compatible Node Aliases ─────────────────────────────────────
    graph.add_node("memory_retrieval", memory_retrieval)
    graph.add_node("policy_check", policy_check)
    graph.add_node("model_router", model_router)
    graph.add_node("memory_update", memory_update)

    # ── Cognitive Loop Edge Wiring ───────────────────────────────────────────
    graph.add_edge(START, "perceive")
    graph.add_edge("perceive", "recall")

    # Conditional: recall -> plan (complex) | policy (fast-path bypass)
    graph.add_conditional_edges(
        "recall",
        _after_recall,
        {
            "plan": "plan",
            "policy": "policy",
        },
    )

    # Static edge: plan -> policy
    graph.add_edge("plan", "policy")

    # Conditional: policy -> act | END (tier 3 halt)
    graph.add_conditional_edges(
        "policy",
        _after_policy,
        {
            "act": "act",
            "END_POLICY_HALT": END,
        },
    )

    # Static edge: act -> verify
    graph.add_edge("act", "verify")

    # Conditional: verify -> reflect
    graph.add_conditional_edges(
        "verify",
        _after_verify,
        {
            "reflect": "reflect",
        },
    )

    # Conditional: reflect -> plan | act | remember
    graph.add_conditional_edges(
        "reflect",
        _after_reflect,
        {
            "plan": "plan",
            "act": "act",
            "remember": "remember",
        },
    )

    # Static edge: remember -> END
    graph.add_edge("remember", END)

    return graph.compile(checkpointer=checkpointer)


# ── Singleton ─────────────────────────────────────────────────────────────────
_jarvis_graph = None


def get_jarvis_graph():
    global _jarvis_graph
    if _jarvis_graph is None:
        _jarvis_graph = build_jarvis_graph()
    return _jarvis_graph


# Backward-compatible alias
jarvis_graph = get_jarvis_graph

__all__ = [
    "build_jarvis_graph",
    "get_jarvis_graph",
    "jarvis_graph",
    "_after_policy_check",
    "_after_model_router",
    "_after_recall",
    "_after_policy",
    "_after_verify",
    "_after_reflect",
]
