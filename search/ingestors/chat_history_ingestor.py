"""
JARVIS Chat History Ingestor.
Ingests conversational transcripts, user queries, and agent answers
with turn-level provenance and intent classification.
"""

from typing import Any, Dict, List, Optional
from search.ingestors.base_ingestor import BaseIngestor


class ChatHistoryIngestor(BaseIngestor):
    async def ingest_chat_turn(
        self,
        session_id: str,
        turn_id: str,
        user_query: str,
        jarvis_reply: str,
        model_used: Optional[str] = None,
    ) -> bool:
        """Ingest a single conversational turn."""
        content = f"User: {user_query}\nJARVIS: {jarvis_reply}"
        doc_id = f"chat:{session_id}_{turn_id}"

        prov = self.build_provenance(
            source_type="chat_history",
            author="jarvis_conversation",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "model_used": model_used or "local_model",
            },
        )

        return await self.index_document(
            doc_id=doc_id,
            title=f"Chat: {user_query[:50]}...",
            content=content,
            source_type="chat_history",
            source_url=f"session://{session_id}#turn={turn_id}",
            metadata={"session_id": session_id, "model": model_used},
            provenance=prov,
        )
