"""
JARVIS Base Document Ingestor.
Provides privacy redaction (API keys, passwords, private keys, tokens),
semantic chunking, provenance generation, and multi-index synchronization.
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from jarvis.core.audit import audit_ledger
from jarvis.constants import INGESTION_REDACTION_PATTERNS
from jarvis.config import settings


class BaseIngestor:
    # Strict regex patterns for sensitive data redaction
    REDACTION_PATTERNS = INGESTION_REDACTION_PATTERNS

    def __init__(self, local_engine, semantic_engine=None, meili_engine=None):
        self.local_engine = local_engine
        self.semantic_engine = semantic_engine
        self.meili_engine = meili_engine

    @classmethod
    def redact_sensitive_data(cls, text: str) -> str:
        """Strip secrets, credentials, tokens, and private keys."""
        cleaned = text
        for pattern, replacement in cls.REDACTION_PATTERNS:
            cleaned = pattern.sub(replacement, cleaned)
        return cleaned

    @staticmethod
    def chunk_text(
        text: str,
        chunk_size: Optional[int] = None,
        overlap: Optional[int] = None,
    ) -> List[str]:
        """Split text into overlapping semantic passages."""
        effective_chunk_size = chunk_size if chunk_size is not None else settings.ingest_chunk_size
        effective_overlap = overlap if overlap is not None else settings.ingest_chunk_overlap

        if len(text) <= effective_chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = min(start + effective_chunk_size, len(text))
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start += effective_chunk_size - effective_overlap
        return chunks

    @staticmethod
    def build_provenance(
        file_path: Optional[str] = None,
        source_type: str = "document",
        author: Optional[str] = None,
        page_number: Optional[int] = None,
        line_range: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Construct provenance record for verifiable citations."""
        prov = {
            "source_type": source_type,
            "file_path": file_path,
            "author": author or "system",
            "page_number": page_number,
            "line_range": line_range,
        }
        if file_path and Path(file_path).exists():
            stat = Path(file_path).stat()
            prov["size_bytes"] = stat.st_size
            prov["last_modified"] = stat.st_mtime
        if extra:
            prov.update(extra)
        return prov

    async def index_document(
        self,
        doc_id: str,
        title: str,
        content: str,
        source_type: str,
        source_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        provenance: Optional[Dict[str, Any]] = None,
        permissions: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Unified multi-index push:
        1. Redact secrets
        2. SQLite FTS5 keyword index + documents table
        3. Meilisearch instant search (if online)
        4. Qdrant semantic vector index (if online)
        5. Write audit entry
        """
        safe_content = self.redact_sensitive_data(content)
        safe_title = self.redact_sensitive_data(title)

        # 1. SQLite FTS5 Indexing
        ingested = self.local_engine.ingest(
            doc_id=doc_id,
            title=safe_title,
            content=safe_content,
            source_type=source_type,
            source_url=source_url,
            metadata=metadata,
            provenance=provenance,
            permissions=permissions,
        )
        if not ingested:
            return False  # duplicate content hash

        # 2. Meilisearch Instant Indexing (optional/async)
        if self.meili_engine:
            try:
                await self.meili_engine.index_document(
                    doc_id=doc_id,
                    title=safe_title,
                    content=safe_content,
                    source_type=source_type,
                    source_url=source_url,
                    metadata=metadata,
                )
            except Exception:
                pass

        # 3. Qdrant Semantic Vector Indexing (optional/async)
        if self.semantic_engine:
            try:
                await self.semantic_engine.upsert(
                    doc_id=doc_id,
                    title=safe_title,
                    text=safe_content,
                    source_type=source_type,
                    url=source_url,
                    metadata=metadata,
                )
            except Exception:
                pass

        # 4. Append to cryptographic audit ledger
        audit_ledger.record(
            actor="ingestor",
            action="SEARCH_INDEX_INGEST",
            target=doc_id,
            payload={
                "doc_id": doc_id,
                "title": safe_title,
                "source_type": source_type,
                "content_hash": hashlib.sha256(safe_content.encode()).hexdigest(),
            },
            result="SUCCESS",
        )
        return True
