"""
Automated verification tests for Cryptographic Audit Ledger.
"""

from jarvis.core.audit import audit_ledger

def test_audit_logging_and_chain_integrity():
    # Log 3 events
    audit_ledger.log_event("TEST_EVENT_1", "task_1", "PWR-001", "SUCCESS", {"input": 1}, {"output": 1})
    audit_ledger.log_event("TEST_EVENT_2", "task_2", "PWR-016", "SUCCESS", {"input": 2}, {"output": 2})
    audit_ledger.log_event("TEST_EVENT_3", "task_3", "PWR-100", "SUCCESS", {"input": 3}, {"output": 3})

    valid, count, msg = audit_ledger.verify_integrity()
    assert valid
    assert count >= 3
