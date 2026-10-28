from pathlib import Path
from typing import Dict, Any, List
from jarvis.core.state import JarvisState
from jarvis.memory.mem0_client import mem0_client
from core.model_router import ModelRouter
from core.policy import PolicyEngine
from jarvis.core.audit import audit_ledger

from jarvis.config import settings

router = ModelRouter()
policy = PolicyEngine()
memory = mem0_client

def memory_retrieval(state: JarvisState) -> Dict[str, Any]:
    memories = memory.search(
        state.get("user_input", ""),
        filters={"user_id": state.get("user_id", settings.jarvis_user_id)},
    )
    return {
        "retrieved_memories": [
            item["memory"] for item in memories if "memory" in item
        ]
    }

def policy_check(state: JarvisState) -> Dict[str, Any]:
    decision = policy.evaluate(
        user_input=state.get("user_input", ""),
        task_type=state.get("task_type", "chat"),
        memories=state.get("retrieved_memories", []),
    )
    return {
        "risk_level": decision.risk_level,
        "approval_required": decision.approval_required,
        "selected_tools": decision.allowed_tools,
    }

def model_router(state: JarvisState) -> Dict[str, Any]:
    if state.get("approval_required") and not state.get("approval_id"):
        return {
            "model_route": "policy_halt",
            "final_response": "Action halted: This operation requires explicit human cryptographic approval."
        }

    model = router.route(
        task_type=state.get("task_type", "chat"),
        sensitivity="private" if state.get("risk_level", "low") != "low" else "public",
    )

    prompt_path = settings.config_dir / "system_prompts" / "core_agent.md"
    system_prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else "You are JARVIS."

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "system",
            "content": "Relevant memory:\n" + "\n".join(state.get("retrieved_memories", [])),
        },
        {"role": "user", "content": state.get("user_input", "")},
    ]
    response = router.complete(model, messages)
    content = response["choices"][0]["message"]["content"]

    audit_ledger.record(
        actor="LangGraphModelRouter",
        action="INFERENCE_COMPLETE",
        target=model,
        payload={"task_id": state.get("task_id"), "input": state.get("user_input")},
        result="SUCCESS"
    )

    return {
        "model_route": model,
        "final_response": content,
    }

model_router_node = model_router

def memory_update(state: JarvisState) -> Dict[str, Any]:
    user_input = state.get("user_input", "")
    final_response = state.get("final_response", "")
    if user_input and final_response and not final_response.startswith("Action halted"):
        memory.add(
            [
                {"role": "user", "content": user_input},
                {"role": "assistant", "content": final_response},
            ],
            user_id=state.get("user_id", settings.jarvis_user_id),
        )
    return {}

__all__ = ["memory_retrieval", "policy_check", "model_router", "model_router_node", "memory_update"]
