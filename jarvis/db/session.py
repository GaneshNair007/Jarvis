"""
JARVIS Database Engine and Session Management
Supports production PostgreSQL and local-first SQLite fallback for RTX 4050 dev setups.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker, scoped_session

from jarvis.db.models.base import Base
from jarvis.core.logger import get_logger

logger = get_logger("db.session")

DEFAULT_SQLITE_PATH = "data/jarvis.db"


def get_database_url() -> str:
    """
    Returns connection URL from environment variable or defaults to local SQLite.
    Priority:
      1. JARVIS_DATABASE_URL
      2. DATABASE_URL
      3. sqlite:///data/jarvis.db
    """
    url = os.environ.get("JARVIS_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if url:
        # Standardize postgres:// to postgresql://
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url

    # Default to local-first SQLite
    Path(DEFAULT_SQLITE_PATH).parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DEFAULT_SQLITE_PATH}"


def create_db_engine(database_url: Optional[str] = None) -> sa.Engine:
    """Creates configured SQLAlchemy engine based on target database dialect."""
    url = database_url or get_database_url()
    is_sqlite = url.startswith("sqlite")

    connect_args = {}
    if is_sqlite:
        connect_args["check_same_thread"] = False

    engine = sa.create_engine(
        url,
        connect_args=connect_args,
        pool_pre_ping=True,
        echo=False,
    )
    logger.info(f"Initialized database engine for dialect '{engine.dialect.name}'.")
    return engine


# Default Global Engine & Session Factory
engine = create_db_engine()
SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
ScopedSession = scoped_session(SessionFactory)


def init_db(target_engine: Optional[sa.Engine] = None) -> None:
    """Initializes all registered database tables in target database."""
    eng = target_engine or engine
    Base.metadata.create_all(bind=eng)
    logger.info(f"Database schema initialized successfully on '{eng.dialect.name}'.")


def get_session() -> Generator[Session, None, None]:
    """Dependency injector yielding a transactional database session."""
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()


def create_test_engine(db_url: str = "sqlite:///:memory:") -> sa.Engine:
    """Helper creating isolated test engine with pre-created schema."""
    test_eng = sa.create_engine(
        db_url,
        connect_args={"check_same_thread": False} if db_url.startswith("sqlite") else {},
        pool_pre_ping=True,
    )
    Base.metadata.create_all(bind=test_eng)
    return test_eng
