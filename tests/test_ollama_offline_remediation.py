"""Pytest test suite for Ollama offline failure remediation and latency compliance.

Verifies:
- Cold probe latency < 100ms when Ollama daemon is offline.
- Cached probe latency < 1ms across subsequent calls.
- Zero unhandled exceptions.
- Output schema conforms to structured offline_unavailable contract.
- Fallback guidance provided without crash.
"""

import time
from jarvis.core.model_router import model_router, RoutingDecision


def test_ollama_offline_10_consecutive_turns_latency():
    """Verify 10 consecutive turns against TIER_1_LOCAL with cold < 100ms and cached < 1ms."""
    # Force cold probe
    model_router._ollama_probe_cache = None
    model_router._ollama_probe_timestamp = 0.0

    decision = RoutingDecision(
        task_id="pytest_offline_turn_01",
        tier="TIER_1_LOCAL",
        provider="ollama",
        selected_model="llama3.1",
        reason="Local reflex pytest",
        redacted_context="",
        redactions_made=[],
        estimated_cost_usd=0.0,
        requires_approval=False,
    )

    latencies = []
    responses = []

    for turn in range(10):
        t0 = time.perf_counter()
        resp = model_router.execute_inference(decision, f"Test prompt {turn}")
        lat_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(lat_ms)
        responses.append(resp)

    # 1. Cold probe must be < 100ms
    assert latencies[0] < 100.0, f"Cold probe latency exceeded 100ms: {latencies[0]:.2f}ms"

    # 2. Subsequent cached probes must be < 1ms
    for i, lat in enumerate(latencies[1:], start=2):
        assert lat < 1.0, f"Turn {i} cached latency exceeded 1ms: {lat:.4f}ms"

    # 3. Output payload structure and zero unhandled exceptions
    for i, resp in enumerate(responses, start=1):
        assert resp["status"] == "offline_unavailable", f"Turn {i} invalid status: {resp['status']}"
        assert resp["tier"] == "TIER_1_LOCAL", f"Turn {i} invalid tier: {resp['tier']}"
        assert resp["cost_usd"] == 0.0, f"Turn {i} invalid cost: {resp['cost_usd']}"
        assert "ollama" in resp["model"].lower()
        assert "error" in resp and resp["error"] is not None
        assert "reply" in resp and len(resp["reply"]) > 0


def test_ollama_offline_adversarial_prompts():
    """Verify empty and oversized prompts succeed gracefully with offline_unavailable."""
    decision = RoutingDecision(
        task_id="pytest_adv_01",
        tier="TIER_1_LOCAL",
        provider="ollama",
        selected_model="llama3.1",
        reason="Adversarial prompt test",
        redacted_context="",
        redactions_made=[],
        estimated_cost_usd=0.0,
        requires_approval=False,
    )

    # Empty prompt
    resp_empty = model_router.execute_inference(decision, "")
    assert resp_empty["status"] == "offline_unavailable"
    assert resp_empty["tokens_used"] == 1

    # Large prompt (20,000 chars)
    large_prompt = "Hello World " * 1600
    resp_large = model_router.execute_inference(decision, large_prompt)
    assert resp_large["status"] == "offline_unavailable"
    assert resp_large["tokens_used"] == len(large_prompt) // 4
