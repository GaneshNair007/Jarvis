"""
JARVIS Browser Page Ingestor.
Ingests visited and approved web pages, DOM extractions, and articles
with URL provenance, page title, and clean text representation.
"""

import hashlib
from typing import Any, Dict, List, Optional
from search.ingestors.base_ingestor import BaseIngestor


class BrowserPageIngestor(BaseIngestor):
    async def ingest_page(
        self,
        url: str,
        title: str,
        html_or_text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Ingest a visited/approved browser page."""
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:12]
        chunks = self.chunk_text(html_or_text, chunk_size=1500, overlap=200)

        ingested_ids = []
        for idx, chunk in enumerate(chunks):
            doc_id = f"web:{url_hash}_{idx}" if len(chunks) > 1 else f"web:{url_hash}"
            page_title = f"{title} (Part {idx + 1})" if len(chunks) > 1 else title

            prov = self.build_provenance(
                source_type="browser_page",
                extra={
                    "target_url": url,
                    "chunk_index": idx,
                    "total_chunks": len(chunks),
                },
            )

            success = await self.index_document(
                doc_id=doc_id,
                title=page_title,
                content=chunk,
                source_type="browser_page",
                source_url=url,
                metadata=metadata or {},
                provenance=prov,
            )
            if success:
                ingested_ids.append(doc_id)

        return ingested_ids
