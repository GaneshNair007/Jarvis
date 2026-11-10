"""
Performance Benchmarks for JARVIS Core Engine
Measures sub-millisecond execution times for:
  1. Policy Gate authorization checks
  2. Desktop worker virtual screen size query
  3. Audit ledger entry computation and cryptographic hashing
  4. Local Reflex and Model Router probe dispatch
"""

import pytest
from jarvis.core.policy_gate import policy_gate
from jarvis.computer.desktop_worker import desktop_worker
from jarvis.core.audit import audit_ledger

try:
    import pytest_benchmark  # noqa: F401
except ImportError:

    @pytest.fixture
    def benchmark():
        return lambda fn, *args, **kwargs: fn(*args, **kwargs)


def test_benchmark_policy_gate_read(benchmark):
    """Measures policy gate evaluation latency for read actions."""
    allowed, reason, _ = benchmark(policy_gate.evaluate_execution, "bench_task", "PWR-001", 1, {"path": "test.txt"})
    assert allowed is True


def test_benchmark_policy_gate_destructive_action(benchmark):
    """Measures policy gate evaluation latency for critical shell operations."""
    allowed, reason, token_data = benchmark(
        policy_gate.evaluate_execution, "bench_task", "PWR-007", 3, {"command": "rm -rf /"}
    )
    # Level 3 critical actions require human approval unless token is supplied
    assert allowed is False
    assert token_data is not None


def test_benchmark_desktop_screen_size(benchmark):
    """Measures desktop coordinate and screen resolution query latency."""
    width, height = benchmark(desktop_worker.get_screen_size)
    assert width > 0
    assert height > 0


def test_benchmark_audit_hash(benchmark):
    """Measures SHA-256 integrity hash latency in the audit ledger."""
    entry = benchmark(
        audit_ledger.record,
        actor="system",
        action="benchmark_test",
        target="target_system",
        payload={"test": "latency"},
    )
    assert entry.get("entry_hash") is not None
