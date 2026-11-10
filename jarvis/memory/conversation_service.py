"""
JARVIS Conversational Multi-Turn Memory Service
Provides persistent session management, message threading, and dialogue history
retrieval backed by SQLAlchemy (SQLite/PostgreSQL) using the Conversation and Message models.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import desc

from jarvis.config import settings
from jarvis.core.logger import get_logger
from jarvis.memory.models import Base, Conversation, Message, User, get_db_engine, init_db

logger = get_logger("memory.conversation_service")


class ConversationService:
    """Persistent Conversational Memory Service using SQLAlchemy."""

    def __init__(self, engine=None, session_factory=None):
        self.engine = engine or get_db_engine()
        init_db(self.engine)
        self.session_factory = session_factory or sessionmaker(bind=self.engine, expire_on_commit=False)
        self._ensure_primary_user()

    def _ensure_primary_user(self, user_id: Optional[str] = None, username: Optional[str] = None) -> User:
        """Guarantees the foreign key referenced User exists in the database."""
        uid = user_id or getattr(settings, "jarvis_user_id", "ganesh") or "ganesh"
        uname = username or getattr(settings, "jarvis_user_name", "Ganesh Nair") or "Ganesh Nair"

        session: Session = self.session_factory()
        try:
            user = session.query(User).filter_by(id=uid).first()
            if not user:
                user = User(
                    id=uid,
                    username=uname,
                    role="owner",
                    created_at=time.time(),
                )
                session.add(user)
                session.commit()
            return user
        finally:
            session.close()

    def get_or_create_conversation(
        self,
        conversation_id: str,
        title: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieves existing conversation by ID or atomically creates a new thread.
        """
        uid = user_id or getattr(settings, "jarvis_user_id", "ganesh") or "ganesh"
        self._ensure_primary_user(user_id=uid)

        session: Session = self.session_factory()
        try:
            conv = session.query(Conversation).filter_by(id=conversation_id).first()
            now = time.time()
            if not conv:
                conv = Conversation(
                    id=conversation_id,
                    user_id=uid,
                    title=title or "Default Session",
                    created_at=now,
                    updated_at=now,
                )
                session.add(conv)
                session.commit()
                logger.info(f"Created new conversation session: {conversation_id}")

            return {
                "id": conv.id,
                "user_id": conv.user_id,
                "title": conv.title,
                "created_at": conv.created_at,
                "updated_at": conv.updated_at,
            }
        finally:
            session.close()

    def append_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        model: Optional[str] = None,
        tokens: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Appends a user, assistant, or system message to the specified conversation thread.
        """
        self.get_or_create_conversation(conversation_id)

        msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        now = time.time()

        session: Session = self.session_factory()
        try:
            msg = Message(
                id=msg_id,
                conversation_id=conversation_id,
                role=role.strip().lower(),
                content=content,
                model=model,
                tokens=tokens,
                created_at=now,
            )
            session.add(msg)

            conv = session.query(Conversation).filter_by(id=conversation_id).first()
            if conv:
                conv.updated_at = now

            session.commit()
            logger.debug(f"Saved message {msg_id} ({role}) in conversation {conversation_id}")

            return {
                "id": msg.id,
                "conversation_id": msg.conversation_id,
                "role": msg.role,
                "content": msg.content,
                "model": msg.model,
                "tokens": msg.tokens,
                "created_at": msg.created_at,
            }
        finally:
            session.close()

    def get_recent_context(
        self,
        conversation_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Fetches the most recent turns for conversation_id in chronological order.
        Returns a list of dicts: [{'role': ..., 'content': ...}, ...] suitable for LLM context injection.
        """
        session: Session = self.session_factory()
        try:
            # Query the latest N messages, then reverse to chronological order
            messages = (
                session.query(Message)
                .filter_by(conversation_id=conversation_id)
                .order_by(desc(Message.created_at))
                .limit(limit)
                .all()
            )
            chronological = list(reversed(messages))

            return [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "model": m.model,
                    "tokens": m.tokens,
                    "created_at": m.created_at,
                }
                for m in chronological
            ]
        finally:
            session.close()

    def format_context_for_prompt(
        self,
        conversation_id: str,
        limit: int = 10,
    ) -> str:
        """
        Formats recent turns into a coherent dialogue transcript string for LLM prompting.
        """
        history = self.get_recent_context(conversation_id, limit=limit)
        if not history:
            return ""

        lines = ["Recent Dialogue History:"]
        for turn in history:
            speaker = "User" if turn["role"] == "user" else ("Assistant" if turn["role"] == "assistant" else "System")
            lines.append(f"{speaker}: {turn['content']}")
        return "\n".join(lines)

    def clear_conversation(self, conversation_id: str) -> bool:
        """Removes all messages from the specified conversation."""
        session: Session = self.session_factory()
        try:
            session.query(Message).filter_by(conversation_id=conversation_id).delete()
            session.commit()
            return True
        except Exception as e:
            logger.error(f"Error clearing conversation {conversation_id}: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def list_conversations(self, user_id: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Lists active conversations ordered by updated_at descending."""
        session: Session = self.session_factory()
        try:
            query = session.query(Conversation)
            if user_id:
                query = query.filter_by(user_id=user_id)
            convs = query.order_by(desc(Conversation.updated_at)).limit(limit).all()

            results = []
            for c in convs:
                count = session.query(Message).filter_by(conversation_id=c.id).count()
                results.append({
                    "id": c.id,
                    "title": c.title,
                    "user_id": c.user_id,
                    "message_count": count,
                    "created_at": c.created_at,
                    "updated_at": c.updated_at,
                })
            return results
        finally:
            session.close()


conversation_service = ConversationService()
