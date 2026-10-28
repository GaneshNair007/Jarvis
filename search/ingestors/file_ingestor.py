"""
JARVIS File Ingestor.
Ingests generic text files, CSV, TSV, JSON, and text logs.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from search.ingestors.base_ingestor import BaseIngestor


class FileIngestor(BaseIngestor):
    async def ingest_file(
        self,
        file_path: str,
        title: Optional[str] = None,
        source_type: str = "document",
    ) -> List[str]:
        """Ingest text file into search indices with chunking."""
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            raise IOError(f"Could not read file {file_path}: {e}")

        doc_title = title or path.stem.replace("_", " ").title()
        chunks = self.chunk_text(content, chunk_size=1500, overlap=200)

        ingested_ids = []
        for idx, chunk in enumerate(chunks):
            chunk_id = f"file:{path.stem}_{idx}" if len(chunks) > 1 else f"file:{path.stem}"
            chunk_title = f"{doc_title} (Part {idx + 1})" if len(chunks) > 1 else doc_title

            prov = self.build_provenance(
                file_path=str(path.resolve()),
                source_type=source_type,
                line_range=f"Chunk {idx + 1}/{len(chunks)}",
                extra={"extension": path.suffix, "total_chunks": len(chunks)},
            )

            success = await self.index_document(
                doc_id=chunk_id,
                title=chunk_title,
                content=chunk,
                source_type=source_type,
                source_url=f"file://{path.resolve()}",
                metadata={"file_name": path.name, "chunk_index": idx},
                provenance=prov,
            )
            if success:
                ingested_ids.append(chunk_id)

        return ingested_ids
