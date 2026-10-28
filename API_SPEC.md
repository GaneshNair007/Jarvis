# JARVIS Core API Specification (REST & WebSocket)

Base URL: `http://localhost:8000`

---

## 1. Core Chat & LangGraph Orchestration

### `POST /chat`
Executes the central LangGraph cognitive loop: `START -> memory_retrieval -> policy_check -> model_router -> memory_update -> END`.

**Request Body:**
```json
{
  "user_id": "ganesh",
  "message": "Remember that my preferred stack is Python FastAPI.",
  "task_type": "chat"
}
```

**Response (200 OK):**
```json
{
  "task_id": "tsk_6f2a938c10",
  "user_id": "ganesh",
  "response": "Understood. I will remember that: Remember that my preferred stack is Python FastAPI.",
  "reply": "Understood. I will remember that: Remember that my preferred stack is Python FastAPI.",
  "retrieved_memories": [],
  "model_route": "ollama/llama3.1",
  "risk_level": "low",
  "approval_required": false
}
```

---

## 2. Health & Telemetry

### `GET /health`
Returns health status of the JARVIS core daemon.

**Response (200 OK):**
```json
{
  "status": "healthy",
  "service": "jarvis-core",
  "version": "1.0.0",
  "timestamp": 1793223000.0
}
```

---

## 3. Task Lifecycle Engine

### `POST /tasks`
Triages, plans, and queues an autonomous task.

**Request Body:**
```json
{
  "intent": "Run security benchmark diagnostics",
  "user_id": "ganesh",
  "priority": "normal"
}
```

**Response (200 OK):**
```json
{
  "task_id": "tsk_42a819b0de",
  "status": "COMPLETED",
  "reply": "Task completed successfully."
}
```

### `GET /tasks`
Lists recent task state machine executions.

### `GET /tasks/{task_id}`
Retrieves lifecycle state, step execution, and artifacts for a specific task.

### `POST /tasks/{task_id}/cancel`
Cancels an active or queued task.

---

## 4. Long-Term Memory Vault (Mem0)

### `POST /memory/add`
Stores an explicit fact or inferred hypothesis in the private vault.

### `POST /memory/search`
Searches semantic memory nodes, directives, and user facts.

### `POST /memory/delete`
Deletes a memory node by ID.

### `POST /documents/ingest`
Ingests local PDF/Markdown/text document and produces indexed chunks.

### `POST /documents/query`
Executes RAG query over indexed documents with exact page-level citations.

---

## 5. Power Registry

### `GET /powers`
Lists operational capabilities from the 355-power catalog and initial power roster.

### `POST /powers/{power_id}/enable`
Enables a power by ID.

### `POST /powers/{power_id}/disable`
Disables a power by ID.

---

## 6. Audit & Safety

### `GET /audit`
Returns append-only SHA-256 audit ledger records with integrity verification.

### `POST /kill-switch`
Emergency software kill switch that immediately halts task execution and rejects incoming non-read requests.
