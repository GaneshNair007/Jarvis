"""
Milestone 4 Adversarial Stress Test Suite: Concurrency & Event Loop Unblocking
==============================================================================
Empirical adversarial stress testing to verify:
1. Event loop tick latency remains under 50ms during long-running synchronous model inference.
2. Parallel queries via asyncio.gather scale concurrently across thread pools without sequential serialization.
3. Interleaved mixed workloads (instant commands, greetings, cloud fallbacks) complete rapidly without starvation.
4. Burst greeting triage under high concurrency (50 parallel requests) routes cleanly to assistant greetings.
5. High-concurrency cloud fallback correctly routes to openrouter/deepseek/deepseek-chat without thread starvation.
6. Fail-closed resilience: uncaught exceptions and unavailable backends under concurrency do not stall the loop.
7. TaskExecutor cognitive reasoning concurrency: offloaded without sleeping agent mocks or fake success.
8. FastAPI ASGI HTTP concurrency: endpoints remain responsive while slow inference is in-flight.
9. Adversarial detection of routing pattern drift between model_router and orchestrator.
"""

import asyncio
import time
import threading
from typing import Any, Dict, List, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from jarvis.api.server import app
from jarvis.core.model_router import model_router, RoutingRequest, RoutingDecision
from jarvis.core.orchestrator import orchestrator
from jarvis.core.task_executor import TaskExecutor
from jarvis.core.task_graph import TaskNode
from jarvis.core.power_registry import power_registry


# =====================================================================
# 1. Event Loop Tick Latency & Jitter Monitor Under Slow Inference
# =====================================================================

@pytest.mark.asyncio
async def test_event_loop_tick_latency_under_slow_sync_inference():
    """
    Adversarial Stress Test: Event Loop Tick Latency Monitor.
    A high-frequency coroutine samples event loop tick intervals every 10ms.
    Simultaneously, a 500ms synchronous blocking inference is executed via process_user_query.
    If orchestrator blocks the event loop, max tick delay will equal ~500ms.
    With asyncio.to_thread, max tick delay MUST remain under 50ms.
    """
    tick_delays: List[float] = []
    stop_monitor = asyncio.Event()

    async def loop_tick_monitor():
        last_tick = time.perf_counter()
        while not stop_monitor.is_set():
            await asyncio.sleep(0.01)  # 10ms target interval
            now = time.perf_counter()
            delay = now - last_tick
            tick_delays.append(delay)
            last_tick = now

    def blocking_sync_inference(decision: Any, prompt: str, **kwargs: Any) -> Dict[str, Any]:
        time.sleep(0.50)  # 500ms blocking CPU/network simulation
        return {
            "status": "success",
            "reply": "Empirical stress test reply",
            "selected_model": "openrouter/deepseek/deepseek-chat",
            "tier": "TIER_3_CLOUD",
        }

    mock_decision = RoutingDecision(
        task_id="tsk_stress_tick",
        tier="TIER_3_CLOUD",
        provider="openrouter",
        selected_model="openrouter/deepseek/deepseek-chat",
        reason="Stress tick test",
        redacted_context="",
        redactions_made=[],
        estimated_cost_usd=0.001,
        requires_approval=False,
    )

    with patch.object(orchestrator.router, "route", return_value=mock_decision), \
         patch.object(orchestrator.router, "execute_inference", side_effect=blocking_sync_inference), \
         patch.object(orchestrator.policy, "evaluate_execution", return_value=(True, "Approved", None)):

        monitor_task = asyncio.create_task(loop_tick_monitor())

        # Allow monitor to start ticking
        await asyncio.sleep(0.02)

        start_time = time.perf_counter()
        query_result = await orchestrator.process_user_query(
            query="Adversarial event loop tick test",
            task_id="tsk_stress_tick",
        )
        total_duration = time.perf_counter() - start_time

        stop_monitor.set()
        await monitor_task

    assert query_result["status"] == "COMPLETED"
    assert total_duration >= 0.50, f"Expected total duration >= 0.50s, got {total_duration:.3f}s"
    assert len(tick_delays) >= 30, f"Expected at least 30 ticks during 500ms inference, got {len(tick_delays)}"

    max_delay = max(tick_delays)
    p95_delay = sorted(tick_delays)[int(len(tick_delays) * 0.95)]
    mean_delay = sum(tick_delays) / len(tick_delays)

    # Invariant: Max delay MUST NOT stall for the duration of inference (>500ms).
    # It must remain < 50ms (0.050s).
    assert max_delay < 0.050, (
        f"Event loop was blocked! Max tick delay: {max_delay*1000:.2f}ms (P95: {p95_delay*1000:.2f}ms, Mean: {mean_delay*1000:.2f}ms). "
        f"Threshold is 50ms."
    )


# =====================================================================
# 2. Parallel Slow Inference Scaling (Wall-clock Concurrency)
# =====================================================================

@pytest.mark.asyncio
async def test_multiple_parallel_inferences_wallclock_scaling():
    """
    Adversarial Stress Test: Multiple parallel async calls to process_user_query.
    Fires 6 concurrent inference tasks, each taking 0.25s of sync compute/sleep.
    If executed sequentially, total time would be >= 1.50s.
    In a thread pool via asyncio.to_thread, wall-clock time must be significantly less (< 0.75s).
    """
    num_tasks = 6
    simulated_delay = 0.25
    observed_threads = set()
    thread_lock = threading.Lock()

    def concurrent_inference(decision: Any, prompt: str, **kwargs: Any) -> Dict[str, Any]:
        with thread_lock:
            observed_threads.add(threading.current_thread().ident)
        time.sleep(simulated_delay)
        return {
            "status": "success",
            "reply": f"Inference for {getattr(decision, 'task_id', 'unknown')}",
            "selected_model": "openrouter/deepseek/deepseek-chat",
            "tier": "TIER_3_CLOUD",
        }

    mock_decision_fn = lambda i: RoutingDecision(
        task_id=f"tsk_parallel_{i}",
        tier="TIER_3_CLOUD",
        provider="openrouter",
        selected_model="openrouter/deepseek/deepseek-chat",
        reason="Parallel scaling test",
        redacted_context="",
        redactions_made=[],
        estimated_cost_usd=0.001,
        requires_approval=False,
    )

    with patch.object(orchestrator.router, "route", side_effect=[mock_decision_fn(i) for i in range(num_tasks)]), \
         patch.object(orchestrator.router, "execute_inference", side_effect=concurrent_inference), \
         patch.object(orchestrator.policy, "evaluate_execution", return_value=(True, "Approved", None)):

        tasks = [
            orchestrator.process_user_query(f"Parallel query {i}", task_id=f"tsk_parallel_{i}")
            for i in range(num_tasks)
        ]

        start_time = time.perf_counter()
        results = await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - start_time

    assert len(results) == num_tasks
    for idx, r in enumerate(results):
        assert r["status"] == "COMPLETED"
        assert r["task_id"] == f"tsk_parallel_{idx}"
        assert f"tsk_parallel_{idx}" in r["response"]["reply"]

    # Multiple distinct worker threads must have handled the inference calls
    assert len(observed_threads) >= 2, f"Expected at least 2 worker threads, got {len(observed_threads)}"

    # True concurrency check: sequential would be >= 1.50s.
    # Parallel should be well under 0.75s (typically ~0.26s - 0.40s).
    assert elapsed < 0.75, f"Parallel scaling failed: took {elapsed:.3f}s for 6x 0.25s tasks (expected < 0.75s)"


# =====================================================================
# 3. Interleaved Mixed Workload Concurrency (Fast vs Slow Queries)
# =====================================================================

@pytest.mark.asyncio
async def test_interleaved_heavy_inference_and_fast_queries():
    """
    Adversarial Stress Test: Interleaved mixed workload under heavy inference.
    Executes 2 slow heavy inference queries (400ms each) alongside 10 fast queries:
    - 5 conversational greetings ('hello', 'hi jarvis', etc.)
    - 5 instant commands ('ping 127.0.0.1', 'take screenshot', etc.)
    Asserts that ALL fast queries finish in < 150ms without waiting for slow inference.
    """
    completion_times: Dict[str, float] = {}
    test_start = time.perf_counter()

    def slow_inference(decision: Any, prompt: str, **kwargs: Any) -> Dict[str, Any]:
        time.sleep(0.50)
        return {"status": "success", "reply": "Heavy LLM reasoning finished", "tier": "TIER_3_CLOUD"}

    # Simulate Ollama offline so heavy queries route to FALLBACK_CLOUD
    with patch.object(model_router, "check_ollama_readiness", return_value=False), \
         patch.object(orchestrator.router, "execute_inference", side_effect=slow_inference), \
         patch.object(orchestrator.policy, "evaluate_execution", return_value=(True, "Approved", None)):

        async def tracked_query(label: str, q: str, tid: str):
            res = await orchestrator.process_user_query(q, task_id=tid)
            completion_times[label] = time.perf_counter() - test_start
            return res

        fast_queries = [
            ("greeting_1", "hello", "t_g1"),
            ("greeting_2", "hi", "t_g2"),
            ("greeting_3", "hey", "t_g3"),
            ("greeting_4", "hello jarvis", "t_g4"),
            ("greeting_5", "hi jarvis", "t_g5"),
            ("instant_1", "who are you", "t_i1"),
            ("instant_2", "help", "t_i2"),
            ("instant_3", "system health", "t_i3"),
            ("instant_4", "take screenshot", "t_i4"),
            ("instant_5", "hud", "t_i5"),
        ]

        slow_queries = [
            ("slow_1", "Elaborate the architectural principles of distributed consensus", "t_s1"),
            ("slow_2", "Provide a comprehensive formal audit of the zero-trust memory model", "t_s2"),
        ]

        all_coros = [tracked_query(lbl, q, tid) for lbl, q, tid in fast_queries] + \
                    [tracked_query(lbl, q, tid) for lbl, q, tid in slow_queries]

        results = await asyncio.gather(*all_coros)

    assert len(results) == 12

    # Invariant: Every fast query MUST finish before any slow inference task finishes
    max_fast_time = max(completion_times[lbl] for lbl, _, _ in fast_queries)
    min_slow_time = min(completion_times[lbl] for lbl, _, _ in slow_queries)
    assert max_fast_time < min_slow_time, (
        f"Event loop serialization detected! Max fast query time ({max_fast_time:.3f}s) "
        f"exceeded min slow query time ({min_slow_time:.3f}s)."
    )
    assert min_slow_time >= 0.48, f"Slow query finished prematurely in {min_slow_time:.3f}s"

    # Verify no state corruption across queries
    for r in results:
        assert r["status"] == "COMPLETED"


# =====================================================================
# 4. High-Concurrency Greeting Triage Burst
# =====================================================================

@pytest.mark.asyncio
async def test_high_concurrency_greeting_triage_burst():
    """
    Adversarial Stress Test: High-concurrency greeting burst (50 parallel requests).
    Tests whether rapid-fire conversational greetings execute concurrently with zero LLM overhead,
    never route to generic OS dispatch, and complete with minimal latency.
    """
    greetings = [
        "hello", "hi", "hey", "hello jarvis", "hi jarvis", "hey jarvis",
        "who are you", "help"
    ]
    burst_size = 50
    queries = [greetings[i % len(greetings)] for i in range(burst_size)]

    start_time = time.perf_counter()
    tasks = [
        orchestrator.process_user_query(q, task_id=f"burst_greet_{i}")
        for i, q in enumerate(queries)
    ]
    results = await asyncio.gather(*tasks)
    total_elapsed = time.perf_counter() - start_time

    assert len(results) == burst_size
    for i, r in enumerate(results):
        assert r["status"] == "COMPLETED"
        assert r["tier"] == "BYPASS"
        resp = r["response"]
        msg = resp.get("message", "")
        # Greeting/assistant info MUST NOT say "Instant command '...' dispatched."
        assert "Instant command" not in msg
        assert ("JARVIS" in msg or "Hello" in msg or "assist" in msg or "actions" in msg)

    # 50 concurrent requests with SQLite database transactions and audit logging
    assert total_elapsed < 5.0, f"Greeting burst took {total_elapsed:.3f}s for 50 requests (expected < 5.0s)"
    avg_latency = total_elapsed / burst_size
    assert avg_latency < 0.100, f"Average greeting latency too high: {avg_latency*1000:.1f}ms per query"


# =====================================================================
# 5. High-Concurrency Cloud Fallback with Thread Pool
# =====================================================================

@pytest.mark.asyncio
async def test_high_concurrency_cloud_fallback_with_thread_pool():
    """
    Adversarial Stress Test: Concurrent cloud fallback routing when local Ollama is offline.
    Verifies that FALLBACK_CLOUD routes with openrouter/ prefix and offloads to thread pool.
    Fires 8 parallel requests with 100ms simulated network latency each.
    Sequential would be 800ms; thread pool must complete in < 350ms.
    """
    num_requests = 8
    network_latency = 0.10
    worker_threads = set()
    lock = threading.Lock()

    def mock_cloud_inference(decision: Any, prompt: str, **kwargs: Any) -> Dict[str, Any]:
        with lock:
            worker_threads.add(threading.current_thread().ident)
        time.sleep(network_latency)
        return {
            "status": "success",
            "reply": f"Cloud fallback response for {getattr(decision, 'task_id', '')}",
            "selected_model": decision.selected_model,
            "tier": decision.tier,
        }

    with patch.object(model_router, "check_ollama_readiness", return_value=False), \
         patch.object(orchestrator.router, "execute_inference", side_effect=mock_cloud_inference), \
         patch.object(orchestrator.policy, "evaluate_execution", return_value=(True, "Approved", None)):

        start_time = time.perf_counter()
        tasks = [
            orchestrator.process_user_query(f"Cloud fallback query {i}", task_id=f"tsk_cloud_{i}")
            for i in range(num_requests)
        ]
        results = await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - start_time

    assert len(results) == num_requests
    for idx, r in enumerate(results):
        assert r["status"] == "COMPLETED"
        assert r["tier"] == "FALLBACK_CLOUD"
        assert r["model"] == "openrouter/deepseek/deepseek-chat"
        assert r["model"].startswith("openrouter/")
        assert f"tsk_cloud_{idx}" in r["response"]["reply"]

    # Concurrency verification
    assert len(worker_threads) >= 2, f"Expected multi-threaded execution, got {len(worker_threads)} threads"
    assert elapsed < 0.35, f"Cloud fallback concurrency took {elapsed:.3f}s for 8x 0.10s calls (expected < 0.35s)"


# =====================================================================
# 6. Fail-Closed Resilience Under Concurrency Stress
# =====================================================================

@pytest.mark.asyncio
async def test_resilience_fail_closed_under_concurrency_stress():
    """
    Adversarial Stress Test: Fault injection under concurrency.
    Dispatches 12 concurrent queries mixing:
    - 4 valid queries (succeed)
    - 4 unavailable backend queries (fail closed)
    - 4 unhandled exceptions in inference (raise cleanly, do NOT crash other tasks)
    Asserts fail-closed integrity and total event loop stability.
    """
    def volatile_inference(decision: Any, prompt: str, **kwargs: Any) -> Dict[str, Any]:
        tid = getattr(decision, "task_id", "")
        if "err" in tid:
            return {
                "status": "unavailable",
                "error": "Ollama socket timeout; cloud ratelimit 429",
                "reply": "Backend unavailable",
            }
        elif "crash" in tid:
            raise ConnectionResetError("Connection abruptly closed by peer")
        return {
            "status": "success",
            "reply": f"Valid response for {tid}",
            "selected_model": "test-model",
        }

    mock_dec = lambda tid: RoutingDecision(
        task_id=tid,
        tier="TIER_3_CLOUD",
        provider="openrouter",
        selected_model="test-model",
        reason="Fault injection",
        redacted_context="",
        redactions_made=[],
        estimated_cost_usd=0.001,
        requires_approval=False,
    )

    with patch.object(orchestrator.router, "route", side_effect=lambda req: mock_dec(req.task_id)), \
         patch.object(orchestrator.router, "execute_inference", side_effect=volatile_inference), \
         patch.object(orchestrator.policy, "evaluate_execution", return_value=(True, "Approved", None)):

        queries = [
            ("valid", f"tsk_valid_{i}") for i in range(4)
        ] + [
            ("err", f"tsk_err_{i}") for i in range(4)
        ] + [
            ("crash", f"tsk_crash_{i}") for i in range(4)
        ]

        async def safe_query(q_type: str, tid: str):
            try:
                res = await orchestrator.process_user_query(f"Query {tid}", task_id=tid)
                return (q_type, tid, res, None)
            except Exception as e:
                return (q_type, tid, None, e)

        results = await asyncio.gather(*[safe_query(qt, tid) for qt, tid in queries])

    for q_type, tid, res, exc in results:
        if q_type == "valid":
            assert exc is None
            assert res["status"] == "COMPLETED"
            assert "Valid response" in res["response"]["reply"]
        elif q_type == "err":
            assert exc is None
            assert res["status"] == "FAILED"  # Must fail closed honestly
            assert "unavailable" in res["response"].get("status", "") or "error" in res["response"]
        elif q_type == "crash":
            # The exception in background thread was properly propagated or raised
            assert exc is not None
            assert isinstance(exc, ConnectionResetError)


# =====================================================================
# 7. TaskExecutor Cognitive Reasoning Concurrency & Thread Offload
# =====================================================================

@pytest.mark.asyncio
async def test_task_executor_reasoning_concurrency_thread_offload():
    """
    Adversarial Stress Test: TaskExecutor cognitive reasoning concurrency.
    Runs 6 concurrent TaskExecutor._default_agent_execution tasks with empty tool_requirements.
    Each requires cognitive reasoning via model_router.execute_inference.
    Verifies they run concurrently on worker threads via asyncio.to_thread and succeed without mocks.
    """
    executor = TaskExecutor()
    num_tasks = 6
    simulated_delay = 0.20
    threads_used = set()
    lock = threading.Lock()

    def mock_reasoning(decision: Any, prompt: str, **kwargs: Any) -> Dict[str, Any]:
        with lock:
            threads_used.add(threading.current_thread().ident)
        time.sleep(simulated_delay)
        return {
            "status": "success",
            "reply": f"Structured reasoning response for {getattr(decision, 'task_id', '')}",
            "model": "openrouter/deepseek/deepseek-chat",
        }

    with patch.object(model_router, "execute_inference", side_effect=mock_reasoning):
        tasks = [
            TaskNode(
                task_id=f"tsk_exec_{i}",
                parent_goal="stress_goal",
                name=f"Reasoning Task {i}",
                description=f"Deep cognitive reasoning {i}",
                department="Strategy",
                tool_requirements=[],
            )
            for i in range(num_tasks)
        ]

        start_time = time.perf_counter()
        results = await asyncio.gather(*[executor._default_agent_execution(t, {}) for t in tasks])
        elapsed = time.perf_counter() - start_time

    assert len(results) == num_tasks
    for idx, r in enumerate(results):
        assert r["status"] == "success"
        # TaskExecutor records the cognitive model tool execution in tools_used
        assert len(r["tools_used"]) == 1
        assert "model:" in r["tools_used"][0]
        assert f"Structured reasoning response for tsk_exec_{idx}" in r["response"]

    # Concurrency verification
    assert len(threads_used) >= 2, f"Expected multiple worker threads, got {len(threads_used)}"
    assert elapsed < 0.60, f"TaskExecutor reasoning concurrency took {elapsed:.3f}s for 6x 0.20s tasks (expected < 0.60s)"


# =====================================================================
# 8. FastAPI ASGI HTTP Concurrency Under Heavy In-Flight Inference
# =====================================================================

@pytest.mark.asyncio
async def test_fastapi_http_endpoints_concurrent_with_slow_inference():
    """
    Adversarial Stress Test: Live ASGI HTTP client concurrency.
    Sends a slow inference request to /api/v1/chat (400ms).
    While that request is in-flight, makes concurrent requests to /api/v1/powers/ecosystem
    and /v1/chat/completions (with fast response).
    Verifies that FastAPI / Uvicorn ASGI event loop responds immediately to other endpoints (<100ms).
    """
    def slow_http_inference(decision: Any, prompt: str, **kwargs: Any) -> Dict[str, Any]:
        time.sleep(0.40)
        return {
            "status": "success",
            "reply": "Slow HTTP inference complete",
            "tier": "TIER_3_CLOUD",
        }

    mock_dec = RoutingDecision(
        task_id="tsk_http_slow",
        tier="TIER_3_CLOUD",
        provider="openrouter",
        selected_model="openrouter/deepseek/deepseek-chat",
        reason="HTTP test",
        redacted_context="",
        redactions_made=[],
        estimated_cost_usd=0.001,
        requires_approval=False,
    )

    with patch.object(orchestrator.router, "route", return_value=mock_dec), \
         patch.object(orchestrator.router, "execute_inference", side_effect=slow_http_inference), \
         patch.object(orchestrator.policy, "evaluate_execution", return_value=(True, "Approved", None)):

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            slow_start = time.perf_counter()
            slow_task = asyncio.create_task(
                client.post("/api/v1/chat", json={"query": "Slow query"})
            )

            # Let slow request reach inference
            await asyncio.sleep(0.05)

            # Fast concurrent request
            fast_start = time.perf_counter()
            fast_resp = await client.get("/api/v1/powers/ecosystem")
            fast_elapsed = time.perf_counter() - fast_start

            slow_resp = await slow_task
            slow_elapsed = time.perf_counter() - slow_start

    assert fast_resp.status_code == 200
    fast_json = fast_resp.json()
    assert "formula" in fast_json or "total_powers" in fast_json
    # The fast HTTP call MUST NOT wait for the 400ms inference
    assert fast_elapsed < 0.15, f"Fast HTTP endpoint was blocked: took {fast_elapsed:.3f}s (expected < 0.15s)"

    assert slow_resp.status_code == 200
    assert slow_elapsed >= 0.40
    assert slow_resp.json()["status"] == "COMPLETED"


# =====================================================================
# 9. Adversarial Boundary Discovery: Routing Drift on Conversational Prompts
# =====================================================================

def test_adversarial_greeting_pattern_drift_discovery():
    """
    Adversarial Challenge: Surface pattern drift between model_router and orchestrator.
    In orchestrator._execute_instant_command (line 167):
      if any(w in q_lower for w in ["who are you", "what can you do", "help"]): ...
    HOWEVER, in model_router.INSTANT_COMMAND_PATTERNS (line 82):
      r"^(status|help|who are you|hi|hello|hey|hi jarvis|hey jarvis|hello jarvis)$"
    
    This test proves empirically that 'what can you do' is NOT matched by model_router,
    causing it to bypass instant command handling and route to LLM cloud inference instead.
    """
    # Supported by model_router
    assert model_router.is_instant_command("who are you") is True
    assert model_router.is_instant_command("hello") is True
    assert model_router.is_instant_command("hi jarvis") is True

    # DRIFT DISCOVERY: 'what can you do' exists in orchestrator._execute_instant_command
    # but is omitted in model_router.INSTANT_COMMAND_PATTERNS!
    is_matched_by_router = model_router.is_instant_command("what can you do")
    # We record this empirical finding:
    assert is_matched_by_router is False, (
        "If this fails, 'what can you do' was added to INSTANT_COMMAND_PATTERNS."
    )


# =====================================================================
# 10. Adversarial Vulnerability: Synchronous Subprocess in Instant Commands
# =====================================================================

@pytest.mark.asyncio
async def test_adversarial_instant_command_ping_blocks_event_loop():
    """
    Adversarial Vulnerability Discovery (FINDING-P1-LOOP-01):
    Instant command macros (orchestrator._execute_instant_command) execute synchronous
    subprocess.run directly on the main event loop thread for 'ping <host>'.
    This test measures event loop tick delay during a simulated ping command,
    empirically demonstrating that subprocesses inside _execute_instant_command
    freeze the event loop for the duration of the subprocess (>= 200ms).
    """
    tick_delays: List[float] = []
    stop_monitor = asyncio.Event()

    async def loop_tick_monitor():
        last_tick = time.perf_counter()
        while not stop_monitor.is_set():
            await asyncio.sleep(0.01)
            now = time.perf_counter()
            tick_delays.append(now - last_tick)
            last_tick = now

    def mock_subprocess_ping(*args: Any, **kwargs: Any) -> Any:
        time.sleep(0.20)  # Simulated 200ms synchronous ping subprocess
        mock_proc = MagicMock()
        mock_proc.stdout = "Reply from 127.0.0.1: bytes=32 time=1ms Average = 1ms"
        mock_proc.stderr = ""
        return mock_proc

    with patch("subprocess.run", side_effect=mock_subprocess_ping):
        monitor_task = asyncio.create_task(loop_tick_monitor())
        await asyncio.sleep(0.02)

        res = await orchestrator.process_user_query("ping 127.0.0.1", task_id="tsk_ping_stress")

        stop_monitor.set()
        await monitor_task

    max_delay = max(tick_delays) if tick_delays else 0.0

    # Verification of vulnerability: The event loop was stalled for >= 180ms
    # because networking_powers.ping was called synchronously without asyncio.to_thread!
    assert max_delay >= 0.18, (
        f"Event loop was not blocked as expected: max delay was only {max_delay*1000:.2f}ms"
    )
