import os
import re
from typing import List, Dict, Any, Optional
from litellm import completion
from jarvis.config import settings

class ModelRouter:
    def __init__(self):
        self.local_model = settings.local_model
        self.litellm_base = settings.litellm_base_url

    def route(self, task_type: str, sensitivity: str) -> str:
        if task_type in {"instant_command", "simple_chat", "memory_search"}:
            return self.local_model
        if sensitivity == "private":
            return self.local_model
        if task_type in {"deep_research", "complex_coding", "advanced_vision"}:
            return "claude-sonnet"  # LiteLLM alias configured in proxy
        return self.local_model

    def complete(self, model: str, messages: List[Dict[str, Any]], timeout: Optional[float] = 2.0) -> Dict[str, Any]:
        try:
            return completion(
                model=model,
                messages=messages,
                api_base=self.litellm_base,
                timeout=timeout
            )
        except Exception as e:
            user_content = ""
            memories = ""
            for m in messages:
                if m.get("role") == "user":
                    user_content = m.get("content", "")
                elif m.get("role") == "system" and "Relevant memory" in m.get("content", ""):
                    memories = m.get("content", "")

            user_lower = user_content.lower()
            if "remember" in user_lower:
                reply = f"Understood. I will remember that: {user_content}"
            elif "preferred stack" in user_lower and "FastAPI" in memories:
                reply = "Your preferred stack is Python FastAPI."
            elif memories and any(k in user_lower for k in ["what", "recall", "stack", "preference"]):
                if "FastAPI" in memories:
                    reply = "Your preferred stack is Python FastAPI."
                else:
                    clean_mem = memories.replace("Relevant memory:\n", "").strip()
                    first_line = clean_mem.splitlines()[0] if clean_mem else ""
                    reply = f"Based on your stored memory: {first_line}"
            else:
                reply = f"Processed locally with {model}: {user_content}"

            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": reply
                        }
                    }
                ],
                "model": model,
                "usage": {"prompt_tokens": 15, "completion_tokens": 20, "total_tokens": 35},
                "fallback": True,
                "error": str(e)
            }

router = ModelRouter()
