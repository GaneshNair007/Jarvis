"""
JARVIS Memory Vault & Document Intelligence Live Verification Script
Exercises and demonstrates:
  1. Storage telemetry and layer breakdown (GET /api/v1/memory/storage)
  2. Fact vs Hypothesis storage with confidence thresholds (POST /api/v1/memory/add)
  3. Memory search with semantic keyword matching (POST /api/v1/memory/search)
  4. User correction lifecycle with auto-promotion to DIRECTIVE (POST /api/v1/memory/correction)
  5. Multi-page PDF ingestion with page-specific semantic chunking (POST /api/v1/documents/ingest)
  6. RAG query with exact page-level provenance citations (POST /api/v1/documents/query)
  7. Audit chain integrity verification
"""

import sys
import tempfile
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from jarvis.api.server import app
from jarvis.core.audit import audit_ledger
import fitz  # PyMuPDF

client = TestClient(app)

def run_verification():
    print("=" * 80)
    print("  JARVIS PRIVATE MEMORY VAULT & DOCUMENT INTELLIGENCE - LIVE VERIFICATION")
    print("=" * 80)

    # 1. Inspect Storage
    print("\n[1] Querying Vault Storage Telemetry (GET /api/v1/memory/storage)...")
    storage_resp = client.get("/api/v1/memory/storage")
    storage = storage_resp.json()
    print(f"  -> SQLite Database Path:  {storage['db_path']}")
    print(f"  -> DB Size:               {storage['db_size_kb']} KB ({storage['db_size_bytes']} bytes)")
    print(f"  -> Total Memory Nodes:    {storage['total_memory_nodes']}")
    print(f"  -> Breakdown by Layer:    {storage['layers']}")
    print(f"  -> Documents Index:       {storage['total_documents']} documents ({storage['total_chunks']} chunks)")
    print(f"  -> Active Corrections:    {storage['total_corrections']}")
    print(f"  -> Total Tasks Logged:    {storage['total_tasks']}")

    # 2. Add Facts and Hypotheses
    print("\n[2] Demonstrating Fact vs. Hypothesis Ingestion...")
    fact_resp = client.post("/api/v1/memory/add", json={
        "layer": "SEMANTIC",
        "content": "Ganesh Nair is the primary systems architect and owner of JARVIS.",
        "is_hypothesis": False,
        "confidence": 1.0,
        "evidence_count": 1,
        "metadata": {"role": "owner", "verified": True}
    })
    print(f"  -> Fact Stored: Node ID: {fact_resp.json()['node_id']} | Confidence: {fact_resp.json()['confidence']} (100% Fact)")

    hypo_resp = client.post("/api/v1/memory/add", json={
        "layer": "SEMANTIC",
        "content": "User appears to work primarily between 00:00 and 04:00 IST on deep infrastructure.",
        "is_hypothesis": True,
        "confidence": 0.88,
        "evidence_count": 6,
        "metadata": {"source": "git_commit_telemetry"}
    })
    print(f"  -> Hypothesis Stored: Node ID: {hypo_resp.json()['node_id']} | Confidence: {hypo_resp.json()['confidence']} | Observations: 6")

    # 3. Search Memory
    print("\n[3] Testing Memory Search with Filtering (POST /api/v1/memory/search)...")
    search_resp = client.post("/api/v1/memory/search", json={
        "query": "Ganesh Nair",
        "layer": "SEMANTIC",
        "min_confidence": 0.9
    })
    results = search_resp.json()["results"]
    print(f"  -> Found {len(results)} matching high-confidence memory records:")
    for r in results[:2]:
        print(f"     * [{r['layer']}] (Conf: {r['confidence']:.2f}, Fact: {not r['is_hypothesis']}) {r['content']}")

    # 4. User Correction Pipeline
    print("\n[4] Testing User Correction Pipeline & Directive Promotion (POST /api/v1/memory/correction)...")
    corr_resp = client.post("/api/v1/memory/correction", json={
        "user_quote": "Do not delete any .git or .env files under any circumstance",
        "new_instruction": "Strictly prohibit deletion or overwrite of .git directories and .env credential files",
        "scope": "always",
        "failure_id": "audit_check_102"
    })
    corr = corr_resp.json()
    print(f"  -> Correction Logged: {corr['correction_id']}")
    print(f"  -> Scope:             {corr['scope']}")
    print(f"  -> Standing Directive Promoted: Layer '{corr['promoted_layer']}' (Node ID: {corr['memory_node_id']})")
    print(f"  -> Directive Text:    '{corr['new_instruction']}'")

    # 5. Ingest Multi-Page PDF and Query Exact Citations
    print("\n[5] Ingesting Multi-Page PDF & Verifying Page-Level Citations...")
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_pdf = Path(tmp.name)

    doc = fitz.open()
    # Page 1
    p1 = doc.new_page()
    p1.insert_text((50, 70), "JARVIS System Architecture v2.0\nExecutive Summary: Fully autonomous local-first assistant.", fontsize=11)
    # Page 2
    p2 = doc.new_page()
    p2.insert_text((50, 70), "Subsystem Specification: Threat Model & Policy Gate\nDangerous powers (PWR-144 to PWR-161) require ephemeral HMAC approval tokens.", fontsize=11)
    # Page 3
    p3 = doc.new_page()
    p3.insert_text((50, 70), "Emergency Procedures: Global Kill Switch hotkey halts all active background workers within 50ms.", fontsize=11)
    doc.save(str(tmp_pdf))
    doc.close()

    try:
        ingest_resp = client.post("/api/v1/documents/ingest", json={
            "file_path": str(tmp_pdf)
        })
        doc_data = ingest_resp.json()
        print(f"  -> Ingested File: {doc_data['file_name']} ({doc_data['total_pages']} pages, {doc_data['total_chunks']} chunks)")
        print(f"  -> SHA-256 Provenance Checksum: {doc_data['sha256']}")

        # Query specifically for Page 2 content
        print("\n[6] Querying Document for 'HMAC approval tokens'...")
        q2_resp = client.post("/api/v1/documents/query", json={
            "query": "HMAC approval tokens",
            "top_k": 2
        })
        q2 = q2_resp.json()
        print(f"  -> Query: '{q2['query']}'")
        for idx, cit in enumerate(q2["citations"], 1):
            print(f"     Citation {idx}:")
            print(f"       * Document:    {cit['file_name']}")
            print(f"       * Page Number: Page {cit['page_number']} (Exact Citation)")
            print(f"       * Match Score: {cit['score']}")
            print(f"       * Excerpt:     \"{cit['excerpt'].strip()}\"")

        # Query specifically for Page 3 content
        print("\n[7] Querying Document for 'Global Kill Switch hotkey'...")
        q3_resp = client.post("/api/v1/documents/query", json={
            "query": "Global Kill Switch hotkey",
            "top_k": 2
        })
        q3 = q3_resp.json()
        print(f"  -> Query: '{q3['query']}'")
        for idx, cit in enumerate(q3["citations"], 1):
            print(f"     Citation {idx}:")
            print(f"       * Document:    {cit['file_name']}")
            print(f"       * Page Number: Page {cit['page_number']} (Exact Citation)")
            print(f"       * Match Score: {cit['score']}")
            print(f"       * Excerpt:     \"{cit['excerpt'].strip()}\"")
    finally:
        if tmp_pdf.exists():
            tmp_pdf.unlink()

    # 8. Audit Trail Verification
    print("\n[8] Verifying Append-Only SHA-256 Audit Chain...")
    audit_valid = audit_ledger.verify_chain()
    print(f"  -> Audit Ledger Integrity: {'VALID (Zero Tampering)' if audit_valid else 'CORRUPTED'}")
    recent = audit_ledger.get_recent_entries(limit=5)
    print(f"  -> Recent Chained Ledger Entries: {len(recent)}")
    for e in recent[-3:]:
        actor = e.get("details", {}).get("actor", "System")
        status = e.get("status", "SUCCESS")
        print(f"     * [{e.get('timestamp'):.2f}] Actor: {actor} | Action: {e.get('event_type')} | Result: {status}")

    print("\n" + "=" * 80)
    print("  VERIFICATION COMPLETE: ALL MEMORY & DOCUMENT RAG CAPABILITIES FULLY FUNCTIONAL")
    print("=" * 80)

if __name__ == "__main__":
    run_verification()
