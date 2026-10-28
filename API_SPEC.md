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

---

## 7. Integration Gateway Endpoints

Available at both root (`/integrations/...`) and versioned (`/api/v1/integrations/...`):

### `GET /integrations`
Lists all registered integrations, their categories, enabled status, connection status, and health.

### `GET /integrations/{integration_id}`
Retrieves detailed metadata for a specific integration.

### `POST /integrations/{integration_id}/connect`
Connects an integration, verifies credentials, and returns setup instructions if unconfigured.

### `POST /integrations/{integration_id}/disconnect`
Disconnects an active integration.

### `POST /integrations/{integration_id}/enable`
Enables an integration.

### `POST /integrations/{integration_id}/disable`
Disables an integration (local kill switch).

### `GET /integrations/{integration_id}/health`
Runs a live health check on the integration (`HEALTHY`, `DEGRADED`, `UNCONFIGURED`, `DISABLED`, `KILL_SWITCHED`).

### `GET /integrations/{integration_id}/powers`
Lists all powers declared under this integration.

### `POST /integrations/{integration_id}/powers/{power_id}/execute`
Executes an integration power with parameter validation, rate limiting, and frozen-hash approval verification.

### `POST /integrations/{integration_id}/powers/{power_id}/dry-run`
Simulates power execution without making changes, providing blast radius impact analysis and approval requirements.

### `GET /integrations/{integration_id}/audit`
Retrieves audit events filtered specifically for the target integration.

---

## 8. Local Search Brain Endpoints

Mounted at root (`/search/...`) and versioned (`/api/v1/search/...`):

### `POST /search/local`
Executes pure local keyword search via SQLite FTS5 (BM25 ranking + snippet generation).
- **Body**: `{"query": string, "limit"?: int, "source_type"?: string}`
- **Response**: `{ "query": string, "mode": "local", "latency_ms": float, "results": [ ... ], "citations": [ ... ] }`

### `POST /search/hybrid`
Executes hybrid local fusion (SQLite FTS5 + Meilisearch + Qdrant Ollama embeddings + RRF merger).
- **Body**: `{"query": string, "limit"?: int, "source_type"?: string}`
- **Response**: `{ "query": string, "mode": "hybrid", "latency_ms": float, "results": [ ... ], "citations": [ ... ] }`

### `POST /search/research`
Deep research orchestrator. Queries local index first; if local results are insufficient, triggers SearXNG web refresh, ingests fresh web results locally, and returns fused citations.
- **Body**: `{"query": string, "limit"?: int, "force_web_refresh"?: bool}`

### `POST /search/ingest/file`
Ingests a single text, markdown, or code document with sensitive-data redaction and deduplication.
- **Body**: `{"file_path": string, "source_type"?: string, "metadata"?: dict}`

### `POST /search/ingest/folder`
Recursively ingests all supported documents in a folder tree.
- **Body**: `{"folder_path": string, "source_type"?: string, "recursive"?: bool}`

### `POST /search/ingest/pdf`
Ingests a PDF document with page-level text extraction and chunking.
- **Body**: `{"file_path": string, "metadata"?: dict}`

### `POST /search/ingest/url`
Ingests article or web content with provenance URL.
- **Body**: `{"url": string, "title": string, "content": string, "metadata"?: dict}`

### `POST /search/ingest/repo`
Recursively indexes a local code repository while respecting `.gitignore`.
- **Body**: `{"repo_path": string, "repo_name"?: string, "respect_gitignore"?: bool}`

### `POST /search/reindex`
Incrementally reindexes all active SQLite documents into SQLite FTS5 and Meilisearch.

### `GET /search/status`
Returns live status, availability, and response latencies of SQLite FTS5, Meilisearch, Qdrant, Redis, and SearXNG.

### `GET /search/stats`
Returns total indexed documents, active documents, deleted documents, and document counts by source type.

### `GET /search/documents`
Lists paginated indexed documents (`limit`, `offset`, `source_type`).

### `GET /search/documents/{doc_id}`
Retrieves full document record, provenance metadata, and SHA-256 content hash.

### `DELETE /search/documents/{doc_id}`
Soft-deletes a document from SQLite archive, removes it from FTS5, Meilisearch, and Qdrant, and invalidates hot cache.

### `POST /search/cache/clear`
Flushes all cached search queries from Redis and memory.

### `GET /search/health`
Health check endpoint returning `{"status": "healthy", "engines": { ... }}`.


