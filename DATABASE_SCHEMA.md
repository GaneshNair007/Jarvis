# JARVIS Database Schema Specification

JARVIS supports both **PostgreSQL 16** (via `psycopg` in Docker Compose) and **SQLite** (for embedded offline environments). Schema management and migrations are handled via **Alembic**.

---

## 1. Tables Overview

| Table Name | Primary Key | Description |
| :--- | :--- | :--- |
| `users` | `id` (VARCHAR 64) | System owners and authorized operators |
| `conversations` | `id` (VARCHAR 64) | Chat session envelopes |
| `messages` | `id` (VARCHAR 64) | Conversation turns with token and model tracking |
| `tasks` | `id` (VARCHAR 64) | Asynchronous agent tasks and state transitions |
| `task_steps` | `id` (VARCHAR 64) | Individual agent action executions & artifacts |
| `task_events` | `id` (VARCHAR 64) | Real-time task telemetry stream |
| `approvals` | `id` (VARCHAR 64) | Cryptographic HMAC-SHA256 human authorization tokens |
| `audit_events` | `event_id` (VARCHAR 64) | Immutable SHA-256 hash-chained audit ledger |
| `powers` | `power_id` (VARCHAR 64) | Catalogued capability metadata & status |
| `memories` | `id` (VARCHAR 64) | 7-layer memory nodes with hypothesis tracking |
| `documents` | `id` (VARCHAR 64) | Ingested PDF/Markdown source files and SHA-256 digests |
| `document_chunks` | `id` (VARCHAR 64) | Page-referenced chunks with citations |
| `embeddings` | `id` (VARCHAR 64) | Dense vector representations for local RAG |

---

## 2. Table Schemas & Foreign Keys

### `users`
- `id`: VARCHAR(64) PK
- `username`: VARCHAR(128) UNIQUE NOT NULL
- `role`: VARCHAR(64) DEFAULT 'owner'
- `created_at`: FLOAT

### `conversations`
- `id`: VARCHAR(64) PK
- `user_id`: VARCHAR(64) FK -> `users.id`
- `title`: VARCHAR(256)
- `created_at`: FLOAT
- `updated_at`: FLOAT

### `messages`
- `id`: VARCHAR(64) PK
- `conversation_id`: VARCHAR(64) FK -> `conversations.id`
- `role`: VARCHAR(32) NOT NULL ('user', 'assistant', 'system')
- `content`: TEXT NOT NULL
- `model`: VARCHAR(64)
- `tokens`: INTEGER DEFAULT 0
- `created_at`: FLOAT

### `tasks`
- `id`: VARCHAR(64) PK
- `title`: VARCHAR(256) NOT NULL
- `status`: VARCHAR(32) DEFAULT 'NEW'
- `priority`: VARCHAR(16) DEFAULT 'P1'
- `power_id`: VARCHAR(64)
- `inputs`: TEXT
- `outputs`: TEXT
- `error`: TEXT
- `created_at`: FLOAT
- `updated_at`: FLOAT

### `task_steps`
- `id`: VARCHAR(64) PK
- `task_id`: VARCHAR(64) FK -> `tasks.id`
- `step_number`: INTEGER NOT NULL
- `agent`: VARCHAR(64) DEFAULT 'coordinator'
- `action`: VARCHAR(128) NOT NULL
- `status`: VARCHAR(32) DEFAULT 'PENDING'
- `artifact`: VARCHAR(256)
- `created_at`: FLOAT

### `task_events`
- `id`: VARCHAR(64) PK
- `task_id`: VARCHAR(64) FK -> `tasks.id`
- `event_type`: VARCHAR(64) NOT NULL
- `payload`: TEXT
- `timestamp`: FLOAT

### `approvals`
- `id`: VARCHAR(64) PK
- `task_id`: VARCHAR(64) NOT NULL
- `power_id`: VARCHAR(64) NOT NULL
- `action_summary`: TEXT NOT NULL
- `payload_hash`: VARCHAR(64) NOT NULL
- `token`: VARCHAR(256) NOT NULL
- `status`: VARCHAR(32) DEFAULT 'PENDING'
- `created_at`: FLOAT
- `expires_at`: FLOAT NOT NULL

### `audit_events`
- `event_id`: VARCHAR(64) PK
- `task_id`: VARCHAR(64)
- `user_id`: VARCHAR(64) DEFAULT 'ganesh'
- `actor`: VARCHAR(64) DEFAULT 'system'
- `action`: VARCHAR(128) NOT NULL
- `tool`: VARCHAR(64)
- `model`: VARCHAR(64)
- `input_hash`: VARCHAR(64)
- `output_hash`: VARCHAR(64)
- `policy_decision`: VARCHAR(64)
- `approval_id`: VARCHAR(64)
- `cost`: FLOAT DEFAULT 0.0
- `latency`: FLOAT DEFAULT 0.0
- `result`: VARCHAR(32) DEFAULT 'SUCCESS'
- `error`: TEXT
- `entry_hash`: VARCHAR(64) NOT NULL
- `prev_hash`: VARCHAR(64) NOT NULL
- `timestamp`: FLOAT

### `powers`
- `power_id`: VARCHAR(64) PK
- `name`: VARCHAR(128) NOT NULL
- `category`: VARCHAR(128) NOT NULL
- `description`: TEXT NOT NULL
- `enabled`: BOOLEAN DEFAULT TRUE
- `approval_required`: BOOLEAN DEFAULT FALSE
- `danger_level`: VARCHAR(32) DEFAULT 'low'
- `version`: VARCHAR(32) DEFAULT '1.0.0'

### `memories`
- `id`: VARCHAR(64) PK
- `user_id`: VARCHAR(64) DEFAULT 'ganesh'
- `layer`: VARCHAR(32) DEFAULT 'SEMANTIC'
- `content`: TEXT NOT NULL
- `is_hypothesis`: BOOLEAN DEFAULT FALSE
- `confidence`: FLOAT DEFAULT 1.0
- `evidence_count`: INTEGER DEFAULT 1
- `metadata_json`: TEXT
- `created_at`: FLOAT
- `updated_at`: FLOAT

### `documents`
- `id`: VARCHAR(64) PK
- `file_path`: VARCHAR(512) NOT NULL
- `file_name`: VARCHAR(256) NOT NULL
- `file_type`: VARCHAR(32) DEFAULT 'pdf'
- `sha256`: VARCHAR(64) UNIQUE NOT NULL
- `total_pages`: INTEGER DEFAULT 1
- `total_chunks`: INTEGER DEFAULT 0
- `file_size`: INTEGER DEFAULT 0
- `metadata_json`: TEXT
- `created_at`: FLOAT

### `document_chunks`
- `id`: VARCHAR(64) PK
- `doc_id`: VARCHAR(64) FK -> `documents.id`
- `page_number`: INTEGER DEFAULT 1
- `chunk_index`: INTEGER DEFAULT 0
- `content`: TEXT NOT NULL
- `metadata_json`: TEXT
- `created_at`: FLOAT

### `embeddings`
- `id`: VARCHAR(64) PK
- `source_id`: VARCHAR(64) NOT NULL
- `source_type`: VARCHAR(32) DEFAULT 'chunk'
- `vector_dims`: INTEGER DEFAULT 384
- `model`: VARCHAR(64) DEFAULT 'nomic-embed-text'
- `created_at`: FLOAT

---

## 3. Migration Commands

```bash
# Generate new migration
alembic revision --autogenerate -m "Add new column or table"

# Apply pending migrations
alembic upgrade head

# Rollback last migration
alembic downgrade -1
```
