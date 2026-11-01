"""Pytest configuration and common fixtures."""

import os
import sys
from pathlib import Path
import pytest

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set test environment
os.environ["JARVIS_ENV"] = "test"
os.environ["JARVIS_SECRET_KEY"] = "test_secret_key_32_bytes_long_ok"


@pytest.fixture(autouse=True)
def isolate_test_audit_ledger(tmp_path, monkeypatch):
    """
    Autouse fixture ensuring complete audit ledger test isolation.
    Redirects settings.audit_log_path and the audit_ledger singleton
    to a unique temporary file per test function.
    Prevents tests from mutating or corrupting data/logs/audit.jsonl.
    """
    from jarvis.config import settings
    from jarvis.core.audit import audit_ledger, AuditLedger

    test_audit_path = tmp_path / "test_audit.jsonl"
    monkeypatch.setattr(settings, "audit_log_path", test_audit_path)
    monkeypatch.setattr(audit_ledger, "log_path", test_audit_path)
    monkeypatch.setattr(audit_ledger, "last_hash", AuditLedger.GENESIS_HASH)
    yield test_audit_path
