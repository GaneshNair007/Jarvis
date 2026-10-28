# JARVIS Database Schema

JARVIS uses a local-first SQLite database running in **WAL (Write-Ahead Logging)** mode with strict referential integrity.

---

## 1. Storage Location
- **Path**: `data/jarvis.db`
- **Journal Mode**: `WAL`
- **Synchronous Flag**: `NORMAL`
- **Foreign Keys**: `ON`

---

## 2. Table Definitions

### 2.1 `memory_nodes`
Stores persistent nodes across all 5 cognitive layers:
- `RAW`: Unedited transcripts and raw event streams
- `SEMANTIC`: Extracted facts, user preferences, and knowledge entities
- `EPISODIC`: Conversation turns, temporal session memories, and episodic context
- `WORKING`: Intermediate task scratchpads and active goal trees
- `DIRECTIVE`: Immutable user rules, policy constraints, and standing operational orders

```sql
CREATE TABLE IF NOT EXISTS memory_nodes (
    id TEXT PRIMARY KEY,
    layer TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mem_layer ON memory_nodes(layer);
```

### 2.2 `tasks`
Maintains lifecycle state for multi-step autonomous plans and background tasks:

```sql
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT NOT NULL,
    plan_json TEXT,
    current_step INTEGER DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_task_status ON tasks(status);
```

### 2.3 `audit_entries` (Mirrored in `data/logs/audit.jsonl`)
Tamper-evident cryptographically chained SHA-256 ledger:

```sql
CREATE TABLE IF NOT EXISTS audit_entries (
    entry_hash TEXT PRIMARY KEY,
    prev_hash TEXT NOT NULL,
    timestamp REAL NOT NULL,
    event_type TEXT NOT NULL,
    task_id TEXT NOT NULL,
    power_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    status TEXT NOT NULL,
    inputs TEXT NOT NULL,
    outputs TEXT NOT NULL,
    details TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_task ON audit_entries(task_id);
```
