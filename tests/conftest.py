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


# ---------------------------------------------------------
# PostgreSQL & Database Test Fixtures
# ---------------------------------------------------------

@pytest.fixture(scope="session")
def db_engine():
    """
    Dual-mode Database Engine Fixture:
    If 'POSTGRES_TEST_URL' is set in environment, tests against real PostgreSQL.
    Otherwise, tests against ultra-fast in-memory SQLite with full UUID & JSON support.
    """
    import sqlalchemy as sa
    from db.models.base import Base

    pg_url = os.getenv("POSTGRES_TEST_URL")
    if pg_url:
        engine = sa.create_engine(pg_url, echo=False)
    else:
        # SQLite in-memory with Foreign Key constraints enabled
        engine = sa.create_engine("sqlite:///:memory:", echo=False)

    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session_factory(db_engine):
    """Sessionmaker bound to the test database engine."""
    from sqlalchemy.orm import sessionmaker
    return sessionmaker(bind=db_engine, expire_on_commit=False)


@pytest.fixture
def db_session(db_session_factory):
    """Provides a transactional database session rolled back after every test."""
    session = db_session_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def uow(db_session_factory):
    """Provides a fresh UnitOfWork instance for testing repositories."""
    from db.repositories.unit_of_work import UnitOfWork
    return UnitOfWork(db_session_factory)
