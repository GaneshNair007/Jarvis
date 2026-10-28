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


class BaseIngestor:
    # Strict regex patterns for sensitive data redaction
    REDACTION_PATTERNS = [
        (re.compile(r"sk-[A-Za-z0-9_-]{20,}", re.IGNORECASE), "[REDACTED_API_KEY]"),
        (re.compile(r"ghp_[A-Za-z0-9]{36}", re.IGNORECASE), "[REDACTED_GITHUB_TOKEN]"),
        (re.compile(r"AKIA[0-9A-Z]{16}", re.IGNORECASE), "[REDACTED_AWS_KEY]"),
        (re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}", re.IGNORECASE), "[REDACTED_JWT]"),
        (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z ]*PRIVATE KEY-----", re.MULTILINE), "[REDACTED_PRIVATE_KEY]"),
        (re.compile(r'(?i)(password|secret|passwd|token)\s*[:=]\s*["\']?([^"\s\',;]{4,})["\']?'), r"\1: [REDACTED_SECRET]"),
        (re.compile(r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12}|(?:[0-9]{4}[ -]){3}[0-9]{4})\b"), "[REDACTED_CARD_NUMBER]"),
    ]

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
    def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 200) -> List[str]:
        """Split text into overlapping semantic passages."""
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start += chunk_size - overlap
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
