"""
JARVIS SQLAlchemy Database Schema & Persistence Models
Supports PostgreSQL in Docker Compose and SQLite for local development.
Defines:
  - users, conversations, messages
  - tasks, task_steps, task_events
  - approvals, audit_events, powers
  - memories, documents, document_chunks, embeddings
"""

import os
import time
from typing import Optional
from sqlalchemy import (
    create_engine, Column, String, Integer, Float, Text, Boolean, DateTime, ForeignKey, JSON
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from jarvis.config import settings

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(String(64), primary_key=True)
    username = Column(String(128), unique=True, nullable=False)
    role = Column(String(64), default="owner")
    created_at = Column(Float, default=time.time)

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.id"), nullable=False)
    title = Column(String(256), default="New Session")
    created_at = Column(Float, default=time.time)
    updated_at = Column(Float, default=time.time)

class Message(Base):
    __tablename__ = "messages"
    id = Column(String(64), primary_key=True)
    conversation_id = Column(String(64), ForeignKey("conversations.id"), nullable=False)
    role = Column(String(32), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    model = Column(String(64), nullable=True)
    tokens = Column(Integer, default=0)
    created_at = Column(Float, default=time.time)

class Task(Base):
    __tablename__ = "tasks"
    id = Column(String(64), primary_key=True)
    title = Column(String(256), nullable=False)
    status = Column(String(32), default="NEW")
    priority = Column(String(16), default="P1")
    power_id = Column(String(64), nullable=True)
    inputs = Column(Text, nullable=True)
    outputs = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(Float, default=time.time)
    updated_at = Column(Float, default=time.time)

class TaskStep(Base):
    __tablename__ = "task_steps"
    id = Column(String(64), primary_key=True)
    task_id = Column(String(64), ForeignKey("tasks.id"), nullable=False)
    step_number = Column(Integer, nullable=False)
    agent = Column(String(64), default="coordinator")
    action = Column(String(128), nullable=False)
    status = Column(String(32), default="PENDING")
    artifact = Column(String(256), nullable=True)
    created_at = Column(Float, default=time.time)

class TaskEvent(Base):
    __tablename__ = "task_events"
    id = Column(String(64), primary_key=True)
    task_id = Column(String(64), ForeignKey("tasks.id"), nullable=False)
    event_type = Column(String(64), nullable=False)
    payload = Column(Text, nullable=True)
    timestamp = Column(Float, default=time.time)

class Approval(Base):
    __tablename__ = "approvals"
    id = Column(String(64), primary_key=True)
    task_id = Column(String(64), nullable=False)
    power_id = Column(String(64), nullable=False)
    action_summary = Column(Text, nullable=False)
    payload_hash = Column(String(64), nullable=False)
    token = Column(String(256), nullable=False)
    status = Column(String(32), default="PENDING")
    created_at = Column(Float, default=time.time)
    expires_at = Column(Float, nullable=False)

class AuditEvent(Base):
    __tablename__ = "audit_events"
    event_id = Column(String(64), primary_key=True)
    task_id = Column(String(64), nullable=True)
    user_id = Column(String(64), default="ganesh")
    actor = Column(String(64), default="system")
    action = Column(String(128), nullable=False)
    tool = Column(String(64), nullable=True)
    model = Column(String(64), nullable=True)
    input_hash = Column(String(64), nullable=True)
    output_hash = Column(String(64), nullable=True)
    policy_decision = Column(String(64), nullable=True)
    approval_id = Column(String(64), nullable=True)
    cost = Column(Float, default=0.0)
    latency = Column(Float, default=0.0)
    result = Column(String(32), default="SUCCESS")
    error = Column(Text, nullable=True)
    entry_hash = Column(String(64), nullable=True)
    prev_hash = Column(String(64), nullable=True)
    timestamp = Column(Float, default=time.time)

class Power(Base):
    __tablename__ = "powers"
    power_id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    category = Column(String(128), nullable=False)
    description = Column(Text, nullable=False)
    enabled = Column(Boolean, default=True)
    approval_required = Column(Boolean, default=False)
    danger_level = Column(String(32), default="low")
    version = Column(String(32), default="1.0.0")

class Memory(Base):
    __tablename__ = "memories"
    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), default="ganesh")
    layer = Column(String(32), default="SEMANTIC")
    content = Column(Text, nullable=False)
    is_hypothesis = Column(Boolean, default=False)
    confidence = Column(Float, default=1.0)
    evidence_count = Column(Integer, default=1)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(Float, default=time.time)
    updated_at = Column(Float, default=time.time)

class Document(Base):
    __tablename__ = "documents"
    id = Column(String(64), primary_key=True)
    file_path = Column(String(512), nullable=False)
    file_name = Column(String(256), nullable=False)
    file_type = Column(String(32), default="pdf")
    sha256 = Column(String(64), unique=True, nullable=False)
    total_pages = Column(Integer, default=1)
    total_chunks = Column(Integer, default=0)
    file_size = Column(Integer, default=0)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(Float, default=time.time)

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id = Column(String(64), primary_key=True)
    doc_id = Column(String(64), ForeignKey("documents.id"), nullable=False)
    page_number = Column(Integer, default=1)
    chunk_index = Column(Integer, default=0)
    content = Column(Text, nullable=False)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(Float, default=time.time)

class Embedding(Base):
    __tablename__ = "embeddings"
    id = Column(String(64), primary_key=True)
    source_id = Column(String(64), nullable=False)
    source_type = Column(String(32), default="chunk")
    vector_dims = Column(Integer, default=384)
    model = Column(String(64), default="nomic-embed-text")
    created_at = Column(Float, default=time.time)

def get_db_engine():
    """Returns SQLAlchemy engine connecting to configured database_url or SQLite fallback."""
    db_url = settings.database_url
    if db_url and "postgres" in db_url:
        return create_engine(db_url, echo=False)
    # Default to local SQLite database
    sqlite_path = settings.db_path.parent / "jarvis_orm.db"
    return create_engine(f"sqlite:///{sqlite_path}", echo=False)

def init_db(engine=None):
    """Creates all database tables."""
    eng = engine or get_db_engine()
    Base.metadata.create_all(bind=eng)
    return eng
