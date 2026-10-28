"""
JARVIS Document Intelligence & Local RAG System
Implements local-first document parsing (PDF, Markdown, TXT),
semantic chunking, vector indexing (TF-IDF / cosine similarity),
and exact-citation retrieval (Document name, page number, chunk ID, SHA-256).
"""

import hashlib
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from jarvis.memory.store import db_store
from jarvis.core.logger import get_logger
from jarvis.core.audit import audit_ledger

logger = get_logger("document_rag")

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

class DocumentRAG:
    """Manages document ingestion, chunking, indexing, and verifiable citation retrieval."""

    def __init__(self):
        self.store = db_store

    def _compute_sha256(self, content_bytes: bytes) -> str:
        """Computes SHA-256 checksum for byte content."""
        return hashlib.sha256(content_bytes).hexdigest()

    def _chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """Splits long text into overlapping sliding chunks."""
        text = text.strip()
        if not text:
            return []
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= len(text):
                break
            start += chunk_size - overlap
        return chunks

    def ingest_file(self, file_path: Union[str, Path], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Ingests a local file (PDF, TXT, MD, etc.), extracts pages and chunks,
        and saves them into the database with exact page references.
        """
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Document file not found at: {path}")

        file_bytes = path.read_bytes()
        sha256 = self._compute_sha256(file_bytes)
        file_size = len(file_bytes)
        file_type = path.suffix.lower().lstrip(".") or "txt"
        file_name = path.name

        # Check if already ingested (idempotency check)
        existing = self.store.get_document_by_hash(sha256)
        if existing:
            logger.info("Document already ingested (hash: %s): %s", sha256[:8], file_name)
            return existing

        doc_id = f"doc_{uuid.uuid4().hex[:12]}"
        chunks: List[Dict[str, Any]] = []
        total_pages = 1

        if file_type == "pdf" and HAS_PYMUPDF:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            total_pages = len(doc)
            chunk_global_idx = 0
            for page_idx in range(total_pages):
                page = doc[page_idx]
                page_num = page_idx + 1
                page_text = page.get_text("text") or ""
                page_chunks = self._chunk_text(page_text)
                for c_idx, chunk_content in enumerate(page_chunks):
                    chunk_id = f"{doc_id}_p{page_num}_{c_idx}"
                    chunks.append({
                        "id": chunk_id,
                        "doc_id": doc_id,
                        "page_number": page_num,
                        "chunk_index": chunk_global_idx,
                        "content": chunk_content,
                        "metadata": {"page": page_num, "sub_chunk": c_idx}
                    })
                    chunk_global_idx += 1
            doc.close()
        else:
            # Plain text / Markdown / other textual formats
            try:
                text = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                text = file_bytes.decode("latin-1", errors="replace")

            text_chunks = self._chunk_text(text)
            for c_idx, chunk_content in enumerate(text_chunks):
                chunk_id = f"{doc_id}_p1_{c_idx}"
                chunks.append({
                    "id": chunk_id,
                    "doc_id": doc_id,
                    "page_number": 1,
                    "chunk_index": c_idx,
                    "content": chunk_content,
                    "metadata": {"chunk_idx": c_idx}
                })

        # Save document record
        self.store.save_document(
            doc_id=doc_id,
            file_path=str(path),
            file_name=file_name,
            file_type=file_type,
            sha256=sha256,
            total_pages=total_pages,
            total_chunks=len(chunks),
            file_size=file_size,
            metadata=metadata or {}
        )

        # Save chunks
        if chunks:
            self.store.save_chunks(chunks)

        audit_ledger.record(
            actor="DocumentRAG",
            action="DOCUMENT_INGEST",
            target=str(path),
            payload={"doc_id": doc_id, "file_name": file_name, "pages": total_pages, "chunks": len(chunks)},
            result="INGESTED"
        )

        logger.info("Ingested document %s (%s): %d pages, %d chunks", file_name, doc_id, total_pages, len(chunks))

        return {
            "id": doc_id,
            "file_name": file_name,
            "file_path": str(path),
            "file_type": file_type,
            "sha256": sha256,
            "total_pages": total_pages,
            "total_chunks": len(chunks),
            "file_size": file_size
        }

    def ingest_text(self, content: str, title: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Ingests arbitrary raw text as a virtual document."""
        content_bytes = content.encode("utf-8")
        sha256 = self._compute_sha256(content_bytes)

        existing = self.store.get_document_by_hash(sha256)
        if existing:
            return existing

        doc_id = f"doc_{uuid.uuid4().hex[:12]}"
        text_chunks = self._chunk_text(content)
        chunks = []
        for c_idx, chunk_content in enumerate(text_chunks):
            chunk_id = f"{doc_id}_p1_{c_idx}"
            chunks.append({
                "id": chunk_id,
                "doc_id": doc_id,
                "page_number": 1,
                "chunk_index": c_idx,
                "content": chunk_content,
                "metadata": {"chunk_idx": c_idx}
            })

        self.store.save_document(
            doc_id=doc_id,
            file_path=f"virtual://{title}",
            file_name=title,
            file_type="text",
            sha256=sha256,
            total_pages=1,
            total_chunks=len(chunks),
            file_size=len(content_bytes),
            metadata=metadata or {}
        )

        if chunks:
            self.store.save_chunks(chunks)

        return {
            "id": doc_id,
            "file_name": title,
            "file_path": f"virtual://{title}",
            "file_type": "text",
            "sha256": sha256,
            "total_pages": 1,
            "total_chunks": len(chunks),
            "file_size": len(content_bytes)
        }

    def query_documents(
        self,
        query: str,
        top_k: int = 5,
        doc_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes semantic RAG query across document chunks, returning ranked excerpts
        with exact file path, page number, chunk ID, and SHA-256 provenance.
        """
        query_clean = query.strip()
        if not query_clean:
            return {"query": query, "citations": [], "answer": "Empty query provided.", "total_chunks_searched": 0}

        # Retrieve chunks to search
        if doc_id:
            chunks = self.store.get_chunks_for_doc(doc_id)
            doc_info = self.store.get_document(doc_id)
            file_path = doc_info["file_path"] if doc_info else "unknown"
            file_name = doc_info["file_name"] if doc_info else "unknown"
            sha256 = doc_info["sha256"] if doc_info else ""
            for c in chunks:
                c["file_path"] = file_path
                c["file_name"] = file_name
                c["sha256"] = sha256
        else:
            chunks = self.store.get_all_chunks(limit=2000)

        if not chunks:
            return {
                "query": query,
                "citations": [],
                "answer": "No indexed documents found in the memory vault.",
                "total_chunks_searched": 0
            }

        corpus = [c["content"] for c in chunks]

        # Use TF-IDF vectorizer for semantic lexical matching
        try:
            vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
            tfidf_matrix = vectorizer.fit_transform(corpus)
            query_vec = vectorizer.transform([query_clean])
            sim_scores = cosine_similarity(query_vec, tfidf_matrix).flatten()
        except Exception as e:
            logger.warning("Vectorization fallback due to: %s", e)
            # Fallback substring scoring
            sim_scores = np.array([
                1.0 if query_clean.lower() in c.lower() else 0.0 for c in corpus
            ])

        # Rank indices by highest similarity
        ranked_indices = np.argsort(sim_scores)[::-1]
        top_indices = [idx for idx in ranked_indices if sim_scores[idx] > 0.0][:top_k]

        citations: List[Dict[str, Any]] = []
        synthesized_excerpts: List[str] = []

        for idx in top_indices:
            ch = chunks[idx]
            score = float(sim_scores[idx])
            citation = {
                "chunk_id": ch["id"],
                "doc_id": ch["doc_id"],
                "file_name": ch.get("file_name", "unknown"),
                "file_path": ch.get("file_path", "unknown"),
                "page_number": ch.get("page_number", 1),
                "score": round(score, 4),
                "sha256": ch.get("sha256", ""),
                "excerpt": ch["content"]
            }
            citations.append(citation)
            synthesized_excerpts.append(
                f"[Doc: {citation['file_name']}, Page: {citation['page_number']}, Score: {citation['score']}]\n\"{citation['excerpt']}\""
            )

        if citations:
            answer = f"Found {len(citations)} relevant citations matching query '{query}':\n\n" + "\n\n".join(synthesized_excerpts)
        else:
            answer = f"No matching passages found for '{query}' in the {len(chunks)} indexed document chunks."

        audit_ledger.record(
            actor="DocumentRAG",
            action="DOCUMENT_QUERY",
            target=doc_id or "ALL_DOCS",
            payload={"query": query, "top_k": top_k, "retrieved_citations": len(citations)},
            result="SUCCESS"
        )

        return {
            "query": query,
            "citations": citations,
            "answer": answer,
            "total_chunks_searched": len(chunks)
        }

    def delete_document(self, doc_id: str) -> bool:
        """Deletes a document and its cascading chunks from the vault."""
        return self.store.delete_document(doc_id)

    def list_documents(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Lists all ingested documents."""
        return self.store.list_documents(limit=limit)

# Singleton Document RAG Instance
document_rag = DocumentRAG()
