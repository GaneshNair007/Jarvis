"""OpenAI Assistants API Drop-in Compatibility Route for Project Jarvis.

Enables standard OpenAI client SDKs, gpt-assistants-api-ui, and third-party dashboards
to communicate directly with JARVIS via standard /v1/threads and /v1/runs endpoints
while routing execution through local models, persistent memory, and deterministic policy gates.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from jarvis.core.logger import get_logger
from jarvis.core.orchestrator import orchestrator

logger = get_logger("api.assistants")

router = APIRouter(prefix="/v1", tags=["OpenAI Assistants API Compatibility"])

# In-memory session store for threads, messages, and runs (backed by SQLite on commit)
_THREADS: Dict[str, Dict[str, Any]] = {}
_MESSAGES: Dict[str, List[Dict[str, Any]]] = {}
_RUNS: Dict[str, Dict[str, Any]] = {}
_ASSISTANTS: Dict[str, Dict[str, Any]] = {
    "asst_jarvis_core": {
        "id": "asst_jarvis_core",
        "object": "assistant",
        "created_at": int(time.time()),
        "name": "JARVIS AI OS",
        "description": "Local-first autonomous personal operating system",
        "model": "qwen2.5-coder",
        "instructions": "You are JARVIS, an autonomous private AI assistant.",
        "tools": [{"type": "code_interpreter"}, {"type": "file_search"}],
    }
}


# ─── Pydantic Schemas ─────────────────────────────────────────────────────────


class CreateThreadRequest(BaseModel):
    messages: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None


class CreateMessageRequest(BaseModel):
    role: str = "user"
    content: str
    metadata: Optional[Dict[str, Any]] = None


class CreateRunRequest(BaseModel):
    assistant_id: Optional[str] = "asst_jarvis_core"
    model: Optional[str] = None
    instructions: Optional[str] = None


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/assistants")
def list_assistants():
    return {
        "object": "list",
        "data": list(_ASSISTANTS.values()),
        "first_id": "asst_jarvis_core",
        "last_id": "asst_jarvis_core",
        "has_more": False,
    }


@router.post("/threads")
def create_thread(req: Optional[CreateThreadRequest] = None):
    thread_id = f"thread_{uuid.uuid4().hex[:12]}"
    now = int(time.time())
    thread_obj = {
        "id": thread_id,
        "object": "thread",
        "created_at": now,
        "metadata": req.metadata if req else {},
    }
    _THREADS[thread_id] = thread_obj
    _MESSAGES[thread_id] = []

    if req and req.messages:
        for m in req.messages:
            msg_id = f"msg_{uuid.uuid4().hex[:12]}"
            _MESSAGES[thread_id].append(
                {
                    "id": msg_id,
                    "object": "thread.message",
                    "created_at": now,
                    "thread_id": thread_id,
                    "role": m.get("role", "user"),
                    "content": [{"type": "text", "text": {"value": m.get("content", "")}}],
                }
            )

    return thread_obj


@router.get("/threads/{thread_id}")
def get_thread(thread_id: str):
    if thread_id not in _THREADS:
        raise HTTPException(status_code=404, detail="Thread not found")
    return _THREADS[thread_id]


@router.post("/threads/{thread_id}/messages")
def create_message(thread_id: str, req: CreateMessageRequest):
    if thread_id not in _THREADS:
        raise HTTPException(status_code=404, detail="Thread not found")

    msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    msg_obj = {
        "id": msg_id,
        "object": "thread.message",
        "created_at": int(time.time()),
        "thread_id": thread_id,
        "role": req.role,
        "content": [{"type": "text", "text": {"value": req.content}}],
        "metadata": req.metadata or {},
    }
    _MESSAGES[thread_id].append(msg_obj)
    return msg_obj


@router.get("/threads/{thread_id}/messages")
def list_messages(thread_id: str):
    if thread_id not in _THREADS:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {
        "object": "list",
        "data": _MESSAGES.get(thread_id, []),
        "has_more": False,
    }


@router.post("/threads/{thread_id}/runs")
async def create_run(thread_id: str, req: Optional[CreateRunRequest] = None):
    if thread_id not in _THREADS:
        raise HTTPException(status_code=404, detail="Thread not found")

    run_id = f"run_{uuid.uuid4().hex[:12]}"
    now = int(time.time())

    # Get the latest user message
    messages = _MESSAGES.get(thread_id, [])
    user_messages = [m for m in messages if m["role"] == "user"]
    user_query = ""
    if user_messages:
        content_block = user_messages[-1].get("content", [{}])[0]
        user_query = content_block.get("text", {}).get("value", "")

    # Execute through Jarvis Orchestrator
    orchestrator_result = await orchestrator.process_user_query(
        query=user_query or "Hello Jarvis",
        task_id=run_id,
    )

    assistant_reply = orchestrator_result.get("outputs", {}).get(
        "response", "Operation completed by Jarvis Orchestrator."
    )
    if isinstance(assistant_reply, dict):
        assistant_reply = assistant_reply.get("message", str(assistant_reply))

    # Append assistant reply to thread
    reply_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    _MESSAGES[thread_id].append(
        {
            "id": reply_msg_id,
            "object": "thread.message",
            "created_at": int(time.time()),
            "thread_id": thread_id,
            "role": "assistant",
            "content": [{"type": "text", "text": {"value": str(assistant_reply)}}],
        }
    )

    run_obj = {
        "id": run_id,
        "object": "thread.run",
        "created_at": now,
        "thread_id": thread_id,
        "assistant_id": (req.assistant_id if req else None) or "asst_jarvis_core",
        "status": "completed",
        "model": orchestrator_result.get("model", "qwen2.5-coder"),
    }
    _RUNS[run_id] = run_obj
    return run_obj


@router.get("/threads/{thread_id}/runs/{run_id}")
def get_run(thread_id: str, run_id: str):
    if run_id not in _RUNS:
        raise HTTPException(status_code=404, detail="Run not found")
    return _RUNS[run_id]


# ─── Standard OpenAI Endpoints (/v1/models & /v1/chat/completions) ───────────


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "jarvis-core"
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    stream: Optional[bool] = False


@router.get("/models")
def list_models():
    """Drop-in OpenAI /v1/models endpoint."""
    return {
        "object": "list",
        "data": [
            {
                "id": "jarvis-core",
                "object": "model",
                "created": 1700000000,
                "owned_by": "jarvis-os",
                "permission": [],
                "root": "jarvis-core",
                "parent": None,
            },
            {
                "id": "qwen2.5-coder:3b",
                "object": "model",
                "created": 1700000000,
                "owned_by": "ollama",
                "permission": [],
                "root": "qwen2.5-coder:3b",
                "parent": None,
            },
            {
                "id": "llama3.2:3b",
                "object": "model",
                "created": 1700000000,
                "owned_by": "ollama",
                "permission": [],
                "root": "llama3.2:3b",
                "parent": None,
            },
        ],
    }


@router.post("/chat/completions")
async def chat_completions(req: ChatCompletionRequest):
    """Drop-in OpenAI /v1/chat/completions endpoint mapped to Jarvis Orchestrator."""
    user_query = req.messages[-1].content if req.messages else "Hello"
    orchestrator_result = await orchestrator.process_user_query(
        query=user_query,
        task_id=f"chat_{uuid.uuid4().hex[:8]}",
    )
    resp_data = orchestrator_result.get("response", {})
    if isinstance(resp_data, dict):
        reply_text = (
            resp_data.get("reply")
            or resp_data.get("message")
            or resp_data.get("text")
            or resp_data.get("content")
            or str(resp_data)
        )
    else:
        reply_text = str(resp_data)

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": req.model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": str(reply_text),
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": len(user_query.split()),
            "completion_tokens": len(str(reply_text).split()),
            "total_tokens": len(user_query.split()) + len(str(reply_text).split()),
        },
    }
