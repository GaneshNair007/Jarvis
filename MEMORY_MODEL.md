# JARVIS Memory Data Model & Scoping Specification

## 1. Explicit Memory Taxonomies

To prevent unstructured string dumping and model hallucinations from contaminating long-term state, every memory record is categorized into one of six distinct functional categories:

| Category | Description | Authority Level | Example |
|---|---|---|---|
| **`preference`** | Explicit user-stated habits, operating constraints, or format choices | HIGH | "Always use dark theme in terminal outputs." |
| **`fact`** | Verified atomic assertions regarding projects, infrastructure, or environments | HIGH | "Production database operates on port 5432." |
| **`episode`** | Audited records of historical actions, tasks, outcomes, and errors | MEDIUM | "CI run 41176365979 failed due to missing PyYAML." |
| **`procedure`** | Versioned, multi-step runbooks or verified execution sequences | HIGH (when verified) | "Step 1: run ruff check, Step 2: pytest, Step 3: build" |
| **`document_reference`**| Pointer to an ingested document passage with SHA-256 and page citation | HIGH | "Section 4 of Security Manual defines Tier 2 rules." |
| **`hypothesis`** | Unverified model inferences, guesses, or temporary working theories | LOW | "The connection failure might be due to a DNS timeout." |

---

## 2. Source Classifications & Confidence

A model's self-reported confidence is not treated as a calibrated probability. Memory records maintain explicit provenance via `source_type`:

1. **`EXPLICIT_USER`** (Authority: 1.0): Direct user command (e.g., "Remember that project alpha uses Python 3.12").
2. **`VERIFIED_TOOL`** (Authority: 0.95): Directly observed and verified by an executing tool (e.g., exit code 0 from a compiler).
3. **`IMPORTED_DOCUMENT`** (Authority: 0.85): Extracted from a verified source document with known hash and path.
4. **`MODEL_INFERENCE`** (Authority: 0.50): Extracted or deduced by an LLM; tagged as `hypothesis` until verified by human or tool.

---

## 3. Canonical Schema Definition

```python
class CanonicalMemoryRecord:
    id: str  # UUID primary key (e.g., mem_1a2b3c4d)
    user_id: str  # Scoping identifier (e.g., "ganesh")
    project_id: Optional[str]  # Scoping identifier (e.g., "Jarvis")
    category: MemoryCategory  # preference, fact, episode, procedure, etc.
    content: str  # Clean text assertion or instruction
    source_type: MemorySourceType  # explicit_user, verified_tool, document, inference
    source_reference: Optional[str]  # Citation (e.g., "chat_turn:42", "file:doc.pdf#L10")
    evidence_references: List[str]  # SHA-256 hashes or audit log event IDs
    created_at: float  # Unix epoch timestamp
    updated_at: float  # Unix epoch timestamp
    valid_from: float  # Validity start epoch
    valid_until: Optional[float]  # Validity expiry epoch (None = indefinite)
    status: MemoryStatus  # active, superseded, contradicted, expired, deleted
    sensitivity: str  # public, internal, confidential, restricted
    retention_policy: str  # permanent, 30_days, 90_days, session_only
    supersedes_id: Optional[str]  # Pointer to previous memory ID replaced by this record
    extraction_model: Optional[str]  # Model tag that generated candidate, if any
    embedding_model: Optional[str]  # Embedding model used for vector indexing, if any
    metadata_json: Dict[str, Any]  # Arbitrary extensible key-value attributes
```

---

## 4. Multi-Tenant Scoping Boundaries

All queries, additions, updates, and deletions enforce strict partitioned scoping:
* A query for `user_id="ganesh"` and `project_id="Jarvis"` can access:
  1. Global facts for `user_id="ganesh"` with `project_id=None` (e.g., user preferences).
  2. Project-specific facts where `project_id="Jarvis"`.
* Cross-user access is strictly denied at the database repository query layer (`WHERE user_id = :user_id`).

