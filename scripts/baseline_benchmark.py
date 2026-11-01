"""JARVIS Phase 0 Baseline Benchmark Script.

Measures latency, cost per request, and memory recall accuracy across:
1. Fast-path instant command execution
2. Memory retrieval (canonical + Mem0)
3. Hybrid RRF search reranking
4. Memory isolation & precision (honest 'unknown' on absent facts)
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import statistics
import sys
import time
from typing import Any, Dict
import uuid

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jarvis.core.orchestrator import orchestrator
from jarvis.brain.memory.service import brain_memory_service
from jarvis.brain.schemas import MemoryCategory
from jarvis.search.hybrid_reranker import fuse_lexical_and_semantic


async def benchmark_instant_command(n_iterations: int = 10) -> Dict[str, Any]:
    latencies = []
    for _ in range(n_iterations):
        t0 = time.perf_counter()
        res = await orchestrator.process_user_query("System health")
        lat = (time.perf_counter() - t0) * 1000
        latencies.append(lat)
        assert res["status"] == "COMPLETED"

    return {
        "operation": "instant_command (fast-path bypass)",
        "iterations": n_iterations,
        "mean_ms": round(statistics.mean(latencies), 2),
        "median_ms": round(statistics.median(latencies), 2),
        "p95_ms": round(statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies), 2),
        "min_ms": round(min(latencies), 2),
        "max_ms": round(max(latencies), 2),
        "cost_usd": 0.0,
    }


def benchmark_memory_recall() -> Dict[str, Any]:
    test_user_a = f"bench_user_a_{uuid.uuid4().hex[:6]}"
    test_user_b = f"bench_user_b_{uuid.uuid4().hex[:6]}"

    # Ground truth facts: (search_query, content)
    facts = [
        ("Python", "User prefers Python 3.12 over Rust"),
        ("PostgreSQL", "Production database is local PostgreSQL"),
        ("RTX 4050", "Hardware accelerator is NVIDIA RTX 4050 6GB"),
        ("Antigravity", "Primary IDE is Antigravity"),
        ("Linux container", "Deployed target is self-hosted Linux container"),
    ]

    for query, content in facts:
        brain_memory_service.store_memory(
            user_id=test_user_a,
            content=content,
            category=MemoryCategory.FACT,
            metadata={"query": query},
        )

    # 1. Recall Test (User A should retrieve own facts)
    recalled_count = 0
    t0 = time.perf_counter()
    for query, content in facts:
        results = brain_memory_service.search_memories(user_id=test_user_a, query=query)
        if any(content in r.content for r in results):
            recalled_count += 1
    recall_duration_ms = (time.perf_counter() - t0) * 1000

    # 2. Cross-User Isolation Test (User B must NOT see User A's facts)
    leakage_count = 0
    for query, _ in facts:
        results = brain_memory_service.search_memories(user_id=test_user_b, query=query)
        if len(results) > 0:
            leakage_count += 1

    # 3. Honest 'Unknown' Test (Querying facts never stored)
    unknown_queries = ["favorite_crypto", "home_wifi_password", "satellite_frequency"]
    honest_unknown_count = 0
    for q in unknown_queries:
        results = brain_memory_service.search_memories(user_id=test_user_a, query=q)
        if len(results) == 0:
            honest_unknown_count += 1

    return {
        "operation": "memory_recall_accuracy",
        "stored_facts": len(facts),
        "recalled_facts": recalled_count,
        "recall_accuracy_pct": round((recalled_count / len(facts)) * 100, 1),
        "mean_recall_lat_ms": round(recall_duration_ms / len(facts), 2),
        "cross_user_leakage": leakage_count,
        "honest_unknown_rate_pct": round((honest_unknown_count / len(unknown_queries)) * 100, 1),
    }


def benchmark_hybrid_rrf_reranker(n_iterations: int = 50) -> Dict[str, Any]:
    lexical = [{"id": f"doc_{i}", "score": 100 - i} for i in range(20)]
    semantic = [{"id": f"doc_{19 - i}", "score": 1.0 - (i * 0.05)} for i in range(20)]

    latencies = []
    for _ in range(n_iterations):
        t0 = time.perf_counter()
        fuse_lexical_and_semantic(lexical, semantic, limit=10)
        latencies.append((time.perf_counter() - t0) * 1000)

    return {
        "operation": "hybrid_rrf_reranker",
        "iterations": n_iterations,
        "mean_us": round(statistics.mean(latencies) * 1000, 2),
        "median_us": round(statistics.median(latencies) * 1000, 2),
    }


async def run_full_baseline():
    print("=" * 60)
    print("JARVIS PHASE 0 BASELINE BENCHMARK")
    print("=" * 60)

    # 1. Instant command latency
    fast_path = await benchmark_instant_command(n_iterations=10)
    print(f"Fast-path Instant Command Latency: {fast_path['mean_ms']} ms (Cost: $0.00)")

    # 2. Memory recall
    memory_res = benchmark_memory_recall()
    print(
        f"Memory Recall Accuracy: {memory_res['recall_accuracy_pct']}% ({memory_res['recalled_facts']}/{memory_res['stored_facts']})"
    )
    print(f"Cross-user Leakage: {memory_res['cross_user_leakage']} leaks")
    print(f"Honest Unknown Rate: {memory_res['honest_unknown_rate_pct']}%")
    print(f"Mean Memory Search Latency: {memory_res['mean_recall_lat_ms']} ms")

    # 3. Hybrid RRF Reranker
    rrf_res = benchmark_hybrid_rrf_reranker(n_iterations=50)
    print(f"Hybrid RRF Reranker Latency: {rrf_res['mean_us']} µs")

    report = {
        "fast_path": fast_path,
        "memory_benchmark": memory_res,
        "hybrid_rrf": rrf_res,
    }

    with open("docs/BASELINE_BENCHMARK.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("\nSaved baseline report to docs/BASELINE_BENCHMARK.json")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_full_baseline())
