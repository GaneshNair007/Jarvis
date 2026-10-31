"""
JARVIS LangGraph Node Implementations
PDF Spec: Pages 1-50 (Core Architectural Tenets) & Pages 420-429 (Build Order)

Node pipeline:
  memory_retrieval → policy_check → model_router → memory_update

Each node receives the full JarvisState TypedDict and returns a partial dict
that LangGraph merges back into state.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List

from jarvis.core.state import JarvisState
from jarvis.core.logger import get_logger

logger = get_logger("graph.nodes")

# ── Lazy imports to avoid circular deps at collection time ───────────────────

def _mem0():
    from jarvis.memory.mem0_client import mem0_client
    return mem0_client

def _router():
    from jarvis.core.model_router import model_router as _mr
    return _mr

def _policy():
    from jarvis.core.policy_engine import policy_engine
    return policy_engine

def _audit():
    from jarvis.core.audit import audit_ledger
    return audit_ledger

def _settings():
    from jarvis.config import settings
    return settings


# ── Node 1: memory_retrieval ─────────────────────────────────────────────────

def memory_retrieval(state: JarvisState) -> Dict[str, Any]:
    """
    Queries Mem0 long-term memory for context relevant to the current user input.
    Tier 0 action — always permitted, no approval required.
    """
    user_input: str = state.get("user_input", "")
    user_id: str = state.get("user_id") or _settings().jarvis_user_id

    retrieved: List[str] = []
    try:
        results = _mem0().search(
            query=user_input,
            filters={"user_id": user_id},
            limit=5,
        )
        # Mem0 returns a list of dicts with a "memory" key
        if isinstance(results, dict):
            results = results.get("results", [])
        retrieved = [
            item.get("memory", item.get("text", ""))
            for item in (results or [])
            if item
        ]
    except Exception as exc:
        logger.warning(f"memory_retrieval: mem0 search failed — {exc}")

    logger.debug(f"memory_retrieval: found {len(retrieved)} memories for user={user_id}")
    return {"retrieved_memories": retrieved}


# ── Node 2: policy_check ──────────────────────────────────────────────────────

def policy_check(state: JarvisState) -> Dict[str, Any]:
    """
    Runs the 4-tier JARVIS policy gate.
    Returns risk_level, tier, approval_required, and allowed_tools.
    If tier >= 2 and no approval_id present, sets approval_required=True.
    """
    user_input: str = state.get("user_input", "")
    task_type: str = state.get("task_type", "chat")
    memories: List[str] = state.get("retrieved_memories", [])

    decision = _policy().evaluate(
        user_input=user_input,
        task_type=task_type,
        memories=memories,
    )

    logger.info(
        f"policy_check: tier={decision.tier} risk={decision.risk_level} "
        f"approval_required={decision.approval_required}"
    )

    return {
        "risk_level": decision.risk_level,
        "policy_tier": decision.tier,
        "approval_required": decision.approval_required,
        "selected_tools": decision.allowed_tools,
        "policy_reason": decision.reason,
    }


# ── Node 3: model_router ──────────────────────────────────────────────────────

def model_router(state: JarvisState) -> Dict[str, Any]:
    """
    Routes inference to the correct model tier via LiteLLM gateway:
      BYPASS       → instant OS command (zero LLM overhead)
      TIER_1_LOCAL → Ollama local model
      TIER_2_PRIV  → private vLLM / OpenRouter
      TIER_3_CLOUD → frontier cloud (Claude / GPT / Gemini)

    If approval_required is True and no approval_id is present, halts execution.
    """
    # ── Policy halt guard ────────────────────────────────────────────────────
    if state.get("approval_required") and not state.get("approval_id"):
        policy_reason = state.get("policy_reason", "Action requires explicit approval.")
        logger.warning(f"model_router: halted — {policy_reason}")
        return {
            "model_route": "policy_halt",
            "final_response": f"⛔ Action halted: {policy_reason} This operation requires explicit human cryptographic approval.",
            "routing_reason": "policy_halt",
        }

    task_id: str = state.get("task_id") or f"tsk_{uuid.uuid4().hex[:8]}"
    user_input: str = state.get("user_input", "")
    risk_level: str = state.get("risk_level", "low")

    settings = _settings()
    router = _router()

    # ── Build routing request ────────────────────────────────────────────────
    try:
        from jarvis.core.model_router import RoutingRequest
        routing_req = RoutingRequest(
            task_id=task_id,
            user_intent=user_input,
            sensitivity_level=risk_level,
            attached_context="\n".join(state.get("retrieved_memories", [])),
        )
        decision = router.route(routing_req)
    except Exception as exc:
        logger.error(f"model_router: routing failed — {exc}")
        return {
            "model_route": "error",
            "final_response": f"Model routing error: {exc}",
        }

    # ── Execute inference ────────────────────────────────────────────────────
    start_ts = time.time()
    try:
        result = router.execute_inference(
            decision=decision,
            prompt=decision.redacted_context or user_input,
        )
        content = (
            result.get("choices", [{}])[0]
            .get("message", {})
            .get("content", str(result))
            if isinstance(result, dict)
            else str(result)
        )
    except Exception as exc:
        logger.error(f"model_router: inference failed — {exc}")
        content = f"Inference error: {exc}"

    duration_ms = round((time.time() - start_ts) * 1000, 2)

    # ── Audit log ────────────────────────────────────────────────────────────
    try:
        _audit().log_event(
            event_type="GRAPH_INFERENCE",
            task_id=task_id,
            power_id=getattr(decision, "selected_model", "unknown"),
            status="SUCCESS",
            inputs={"query": user_input, "tier": getattr(decision, "tier", "?")},
            outputs={"response_len": len(content), "duration_ms": duration_ms},
        )
    except Exception as exc:
        logger.warning(f"model_router: audit log failed — {exc}")

    logger.info(
        f"model_router: task={task_id} model={getattr(decision, 'selected_model', '?')} "
        f"tier={getattr(decision, 'tier', '?')} duration={duration_ms}ms"
    )

    return {
        "task_id": task_id,
        "model_route": getattr(decision, "tier", "unknown"),
        "selected_model": getattr(decision, "selected_model", "unknown"),
        "provider": getattr(decision, "provider", "unknown"),
        "final_response": content,
        "routing_reason": getattr(decision, "reason", ""),
        "duration_ms": duration_ms,
        "estimated_cost_usd": getattr(decision, "estimated_cost_usd", 0.0),
    }


# ── Node 4: memory_update ─────────────────────────────────────────────────────

def memory_update(state: JarvisState) -> Dict[str, Any]:
    """
    Writes the completed turn (user input + JARVIS response) back to Mem0.
    Skips write if the response was a policy halt or error.
    """
    user_input: str = state.get("user_input", "")
    final_response: str = state.get("final_response", "")
    user_id: str = state.get("user_id") or _settings().jarvis_user_id

    skip_phrases = ("⛔", "Action halted", "Inference error", "Model routing error")
    should_write = (
        bool(user_input)
        and bool(final_response)
        and not any(final_response.startswith(p) for p in skip_phrases)
    )

    if should_write:
        try:
            _mem0().add(
                messages=[
                    {"role": "user", "content": user_input},
                    {"role": "assistant", "content": final_response},
                ],
                user_id=user_id,
            )
            logger.debug(f"memory_update: wrote turn to mem0 for user={user_id}")
        except Exception as exc:
            logger.warning(f"memory_update: mem0 write failed — {exc}")

    return {"memory_written": should_write}


# ── Re-export ─────────────────────────────────────────────────────────────────
# Alias so existing code that does `from graph.nodes import model_router_node` works
model_router_node = model_router

__all__ = [
    "memory_retrieval",
    "policy_check",
    "model_router",
    "model_router_node",
    "memory_update",
]
