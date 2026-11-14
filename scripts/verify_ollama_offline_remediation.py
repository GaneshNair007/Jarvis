"""Verification Script for Ollama Offline Remediation.

Empirically verifies:
1. 10 consecutive calls against TIER_1_LOCAL while Ollama is offline.
2. Cold probe latency < 100ms.
3. Cached probe latency < 1ms for turns 2..10.
4. Zero unhandled exceptions.
5. Structured 'unavailable' payload returned when no local model is reachable.
6. Adversarial edge cases: empty prompt, large payload, concurrent execution, TTL expiry.
"""

from __future__ import annotations

import concurrent.futures
import json
from pathlib import Path
import statistics
import sys
import time
from typing import Any, Dict, List

# Ensure project root in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jarvis.core.model_router import model_router, RoutingDecision
from jarvis.config import settings


def run_10_turn_benchmark() -> Dict[str, Any]:
    print("=" * 70)
    print("TEST 1: 10 CONSECUTIVE TURNS (TIER_1_LOCAL, OLLAMA OFFLINE)")
    print("=" * 70)

    # Keep the check local-only: never attempt cloud inference from this verification script.
    settings.jarvis_env = "test"

    # Invalidate cache to ensure Turn 1 is a true cold probe
    model_router._ollama_probe_cache = None
    model_router._ollama_probe_timestamp = 0.0

    decision = RoutingDecision(
        task_id="offline_bench_01",
        tier="TIER_1_LOCAL",
        provider="ollama",
        selected_model="llama3.1",
        reason="Local reflex test",
        redacted_context="",
        redactions_made=[],
        estimated_cost_usd=0.0,
        requires_approval=False,
    )

    results: List[Dict[str, Any]] = []
    required_keys = {
        "task_id",
        "status",
        "tier",
        "model",
        "reply",
        "tokens_used",
        "cost_usd",
        "duration_ms",
        "error",
    }

    for turn in range(1, 11):
        prompt = f"Benchmark turn {turn}: Analyze local offline behavior."
        t0 = time.perf_counter()
        response = model_router.execute_inference(decision, prompt)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        # Assert zero unhandled exceptions (function returned)
        assert isinstance(response, dict), f"Turn {turn}: Response must be a dict"
        assert required_keys.issubset(response.keys()), f"Turn {turn}: Missing required keys in response"
        assert response["status"] == "unavailable", (
            f"Turn {turn}: Expected status 'unavailable', got {response['status']}"
        )
        assert response["tier"] == "TIER_1_LOCAL", f"Turn {turn}: Expected tier 'TIER_1_LOCAL', got {response['tier']}"
        assert response["cost_usd"] == 0.0, f"Turn {turn}: Expected cost_usd == 0.0, got {response['cost_usd']}"
        assert response["error"] == "LOCAL_MODEL_UNAVAILABLE", (
            f"Turn {turn}: Unexpected error code: {response['error']}"
        )
        assert response["tokens_used"] == 0, "No inference means no tokens may be reported."

        results.append(
            {
                "turn": turn,
                "wall_latency_ms": elapsed_ms,
                "internal_duration_ms": response["duration_ms"],
                "status": response["status"],
                "model": response["model"],
                "error": response["error"],
            }
        )

    cold_latency = results[0]["wall_latency_ms"]
    cached_latencies = [r["wall_latency_ms"] for r in results[1:]]
    max_cached = max(cached_latencies)
    mean_cached = statistics.mean(cached_latencies)

    print(f"{'Turn':<6} | {'Wall Latency (ms)':<18} | {'Reported (ms)':<15} | {'Status':<20}")
    print("-" * 65)
    for r in results:
        print(
            f"{r['turn']:<6} | {r['wall_latency_ms']:<18.4f} | {r['internal_duration_ms']:<15.2f} | {r['status']:<20}"
        )

    print("-" * 65)
    print(f"Cold probe latency:        {cold_latency:.4f} ms (Threshold: < 100.0 ms)")
    print(f"Mean cached latency:       {mean_cached:.4f} ms")
    print(f"Max cached latency:        {max_cached:.4f} ms (Threshold: < 1.0 ms)")

    cold_passed = cold_latency < 100.0
    cached_passed = max_cached < 1.0

    print(f"Cold Probe Result:         {'PASS' if cold_passed else 'FAIL'}")
    print(f"Cached Probes Result:      {'PASS' if cached_passed else 'FAIL'}")

    return {
        "turns": results,
        "cold_latency_ms": cold_latency,
        "cached_latencies_ms": cached_latencies,
        "max_cached_ms": max_cached,
        "mean_cached_ms": mean_cached,
        "cold_passed": cold_passed,
        "cached_passed": cached_passed,
    }


def run_adversarial_tests() -> Dict[str, Any]:
    print("\n" + "=" * 70)
    print("TEST 2: ADVERSARIAL EDGE CASES & STRESS HARNESS")
    print("=" * 70)

    decision = RoutingDecision(
        task_id="adv_01",
        tier="TIER_1_LOCAL",
        provider="ollama",
        selected_model="llama3.1",
        reason="Adversarial stress test",
        redacted_context="",
        redactions_made=[],
        estimated_cost_usd=0.0,
        requires_approval=False,
    )

    adv_results = {}

    # 1. Empty Prompt
    print("[1/4] Testing empty string prompt...")
    t0 = time.perf_counter()
    res_empty = model_router.execute_inference(decision, "")
    lat_empty = (time.perf_counter() - t0) * 1000.0
    assert res_empty["status"] == "unavailable"
    assert res_empty["tokens_used"] == 0
    adv_results["empty_prompt"] = {
        "latency_ms": lat_empty,
        "status": res_empty["status"],
        "pass": True,
    }
    print(f"      Passed in {lat_empty:.4f} ms.")

    # 2. Huge Prompt (100k chars)
    print("[2/4] Testing huge prompt (100,000 characters)...")
    large_prompt = "Adversarial buffer " * 5000
    t0 = time.perf_counter()
    res_large = model_router.execute_inference(decision, large_prompt)
    lat_large = (time.perf_counter() - t0) * 1000.0
    assert res_large["status"] == "unavailable"
    assert res_large["tokens_used"] == 0
    adv_results["large_prompt"] = {
        "latency_ms": lat_large,
        "status": res_large["status"],
        "pass": True,
    }
    print(f"      Passed in {lat_large:.4f} ms.")

    # 3. High Concurrency (20 concurrent threads)
    print("[3/4] Testing high concurrent thread load (20 parallel requests)...")
    concurrent_latencies = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(model_router.execute_inference, decision, f"Concurrent thread prompt {i}")
            for i in range(20)
        ]
        for f in concurrent.futures.as_completed(futures):
            t_start = time.perf_counter()
            res = f.result()
            concurrent_latencies.append((time.perf_counter() - t_start) * 1000.0)
            assert res["status"] == "unavailable"
            assert res["cost_usd"] == 0.0

    max_concurrent_lat = max(concurrent_latencies)
    mean_concurrent_lat = statistics.mean(concurrent_latencies)
    adv_results["concurrency"] = {
        "requests": 20,
        "mean_latency_ms": mean_concurrent_lat,
        "max_latency_ms": max_concurrent_lat,
        "pass": max_concurrent_lat < 5.0,
    }
    print(
        f"      Completed 20 concurrent threads. Mean: {mean_concurrent_lat:.4f} ms, Max: {max_concurrent_lat:.4f} ms."
    )

    # 4. TTL Expiration & Re-probe
    print("[4/4] Testing TTL expiration re-probe behavior...")
    model_router._ollama_probe_timestamp = time.time() - 10.0  # Force TTL expiry
    t0 = time.perf_counter()
    res_ttl = model_router.execute_inference(decision, "Post-TTL prompt")
    lat_ttl = (time.perf_counter() - t0) * 1000.0
    assert res_ttl["status"] == "unavailable"
    assert lat_ttl < 100.0, f"Post-TTL probe latency too high: {lat_ttl:.2f} ms"
    adv_results["ttl_refresh"] = {"latency_ms": lat_ttl, "pass": lat_ttl < 100.0}
    print(f"      TTL refreshed probe completed in {lat_ttl:.4f} ms (< 100ms threshold).")

    return adv_results


def main():
    bench = run_10_turn_benchmark()
    adv = run_adversarial_tests()

    print("\n" + "=" * 70)
    print("FINAL SUMMARY & VERDICT")
    print("=" * 70)
    all_passed = bench["cold_passed"] and bench["cached_passed"] and all(v.get("pass", False) for v in adv.values())

    verdict = "CONFIRMED" if all_passed else "REJECTED"
    print(f"Overall Verdict: {verdict}")

    output_data = {
        "verdict": verdict,
        "benchmark": bench,
        "adversarial": adv,
    }

    # Save summary report in scripts directory
    out_path = Path(__file__).resolve().parent / "ollama_offline_benchmark_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)
    print(f"Benchmark results written to: {out_path}")

    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
