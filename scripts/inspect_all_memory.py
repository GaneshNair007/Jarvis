"""
JARVIS Complete Memory Vault & Cognitive Layer Deep Inspection
Dumps and audits all 7 cognitive layers + Document RAG citations.
"""

import sys
import json
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from jarvis.memory.layers import memory_manager
from jarvis.memory.document_rag import document_rag
from jarvis.memory.store import db_store
from jarvis.core.audit import audit_ledger

def inspect_all():
    print("=" * 85)
    print("      JARVIS PRIVATE MEMORY VAULT: 7-LAYER COGNITIVE AUDIT & RAG INSPECTION")
    print("=" * 85)

    # 1. Global Storage Telemetry
    stats = memory_manager.get_storage_stats()
    print("\n[+] GLOBAL VAULT STORAGE TELEMETRY:")
    print(f"    - SQLite Database:      {stats['db_path']}")
    print(f"    - Database Size:        {stats['db_size_kb']} KB")
    print(f"    - Audit Log Size:       {stats['audit_log_size_bytes']} bytes")
    print(f"    - Total Memory Nodes:   {stats['total_memory_nodes']}")
    print(f"    - Layer Distribution:   {stats['layers']}")
    print(f"    - Indexed Documents:    {stats['total_documents']} documents ({stats['total_chunks']} chunks)")
    print(f"    - User Corrections:     {stats['total_corrections']}")
    print(f"    - Tasks Logged:         {stats['total_tasks']}")

    # 2. Inspect DIRECTIVE Layer
    print("\n" + "-" * 85)
    print("  [LAYER 1/7] DIRECTIVE LAYER (Standing Orders, Immutable Rules, Promoted Corrections)")
    print("-" * 85)
    directives = memory_manager.recall(layer="DIRECTIVE", limit=20)
    print(f"  Total Directives Stored: {len(directives)}")
    for idx, d in enumerate(directives, 1):
        meta = d.get("metadata", {})
        rule_name = meta.get("rule_name") or meta.get("origin") or "STANDING_RULE"
        priority = meta.get("priority", "NORMAL")
        print(f"  {idx}. [{rule_name} | Priority: {priority}] (Node: {d['id']})")
        print(f"     Text: \"{d['content']}\"")

    # 3. Inspect SEMANTIC Layer (Facts vs Hypotheses)
    print("\n" + "-" * 85)
    print("  [LAYER 2/7] SEMANTIC LAYER (Facts, Inferred Hypotheses, Profile & Knowledge)")
    print("-" * 85)
    semantic_nodes = memory_manager.recall(layer="SEMANTIC", limit=20)
    print(f"  Total Semantic Nodes: {len(semantic_nodes)}")
    for idx, s in enumerate(semantic_nodes, 1):
        hypo_label = "HYPOTHESIS" if s["is_hypothesis"] else "VERIFIED_FACT"
        print(f"  {idx}. [{hypo_label}] Confidence: {s['confidence']:.2f} | Evidence Count: {s['evidence_count']} (Node: {s['id']})")
        print(f"     Content: \"{s['content']}\"")

    # 4. Inspect EPISODIC & RAW Layers
    print("\n" + "-" * 85)
    print("  [LAYERS 3 & 4/7] EPISODIC & RAW LAYERS (Transcripts, Conversations, Task Traces)")
    print("-" * 85)
    episodic_nodes = memory_manager.recall(layer="EPISODIC", limit=10)
    raw_nodes = memory_manager.recall(layer="RAW", limit=10)
    print(f"  Episodic Records: {len(episodic_nodes)} | Raw Logs: {len(raw_nodes)}")
    for idx, ep in enumerate(episodic_nodes[:5], 1):
        print(f"  {idx}. [EPISODIC] (Node: {ep['id']}) Updated: {ep.get('updated_at')}")
        print(f"     Content: {ep['content'][:120]}...")

    # 5. Inspect PROCEDURAL, WORKING & CAPTURE Layers
    print("\n" + "-" * 85)
    print("  [LAYERS 5, 6 & 7/7] PROCEDURAL, WORKING & CAPTURE LAYERS")
    print("-" * 85)
    proc_nodes = memory_manager.recall(layer="PROCEDURAL", limit=10)
    work_nodes = memory_manager.recall(layer="WORKING", limit=10)
    cap_nodes = memory_manager.recall(layer="CAPTURE", limit=10)
    print(f"  Procedural Skills: {len(proc_nodes)} | Working Scratchpad: {len(work_nodes)} | Capture Events: {len(cap_nodes)}")
    for p in proc_nodes:
        print(f"    - [PROCEDURAL] (Node: {p['id']}) {p['content']}")
    for w in work_nodes:
        print(f"    - [WORKING] (Node: {w['id']}) {w['content']}")

    # 6. User Corrections Audit
    print("\n" + "-" * 85)
    print("  USER CORRECTIONS REGISTRY (Standing Operational Overrides)")
    print("-" * 85)
    corrections = db_store.list_corrections(limit=10)
    print(f"  Total Active Corrections: {len(corrections)}")
    for idx, c in enumerate(corrections, 1):
        print(f"  {idx}. Correction ID: {c['id']} | Scope: {c['scope']} | Status: {c['status']}")
        print(f"     User Quote:      \"{c['user_quote']}\"")
        print(f"     New Instruction: \"{c['new_instruction']}\"")

    # 7. Document Intelligence RAG Ingestion & Citation Queries
    print("\n" + "-" * 85)
    print("  DOCUMENT INTELLIGENCE RAG: CITATION QUERY VERIFICATION")
    print("-" * 85)
    docs = db_store.list_documents(limit=5)
    print(f"  Ingested Documents in Vault: {len(docs)}")
    for d in docs:
        print(f"    - Doc ID: {d['id']} | File: {d['file_name']} | Pages: {d['total_pages']} | Chunks: {d['total_chunks']} | SHA-256: {d['sha256'][:16]}...")

    queries_to_test = [
        "HMAC approval tokens",
        "Global Kill Switch hotkey",
        "Policy Gate and Cost Governor"
    ]

    for q in queries_to_test:
        print(f"\n  >> RAG Query: '{q}'")
        res = document_rag.query_documents(query=q, top_k=2)
        if res["citations"]:
            for c_idx, cit in enumerate(res["citations"], 1):
                print(f"     Citation {c_idx}:")
                print(f"       File:   {cit['file_name']}")
                print(f"       Page:   Page {cit['page_number']} (Exact Citation)")
                print(f"       Score:  {cit['score']}")
                print(f"       Chunk:  {cit['chunk_id']}")
                print(f"       Text:   \"{cit['excerpt'].strip()}\"")
        else:
            print("     No matching citation found.")

    # 8. Cryptographic Hash Chain Verification
    print("\n" + "-" * 85)
    print("  CRYPTOGRAPHIC AUDIT CHAIN VERIFICATION")
    print("-" * 85)
    valid, verified_count, message = audit_ledger.verify_integrity()
    print(f"  Status:             {'[PASSED] 100% Tamper-Evident Chain Intact' if valid else '[FAILED] Integrity Violated'}")
    print(f"  Total Blocks:       {verified_count} cryptographically signed entries")
    print(f"  Verification Note:  {message}")
    print("=" * 85)

if __name__ == "__main__":
    inspect_all()
