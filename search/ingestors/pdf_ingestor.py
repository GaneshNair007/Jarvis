"""
JARVIS PDF Ingestor.
Extracts page-by-page text from PDF documents using PyMuPDF (fitz),
binding every chunk to its exact page number and document provenance.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from search.ingestors.base_ingestor import BaseIngestor


class PDFIngestor(BaseIngestor):
    async def ingest_pdf(
        self,
        file_path: str,
        title: Optional[str] = None,
    ) -> List[str]:
        """Ingest PDF document with page-specific provenance."""
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"PDF not found: {file_path}")

        doc_title = title or path.stem.replace("_", " ").title()
        ingested_ids = []

        try:
            import fitz  # PyMuPDF
            doc = fitz.open(str(path))
            total_pages = len(doc)

            for page_num in range(total_pages):
                page = doc[page_num]
                text = page.get_text().strip()
                if not text:
                    continue

                page_chunks = self.chunk_text(text, chunk_size=1200, overlap=150)
                for chunk_idx, chunk in enumerate(page_chunks):
                    doc_id = f"pdf:{path.stem}_p{page_num + 1}_c{chunk_idx}"
                    chunk_title = f"{doc_title} (Page {page_num + 1})"

                    prov = self.build_provenance(
                        file_path=str(path.resolve()),
                        source_type="pdf",
                        page_number=page_num + 1,
                        extra={
                            "total_pages": total_pages,
                            "chunk_index": chunk_idx,
                            "file_name": path.name,
                        },
                    )

                    success = await self.index_document(
                        doc_id=doc_id,
                        title=chunk_title,
                        content=chunk,
                        source_type="pdf",
                        source_url=f"file://{path.resolve()}#page={page_num + 1}",
                        metadata={"page": page_num + 1, "doc_name": path.name},
                        provenance=prov,
                    )
                    if success:
                        ingested_ids.append(doc_id)

            doc.close()

        except ImportError:
            # Fallback if fitz is absent
            content = path.read_text(encoding="utf-8", errors="replace")
            doc_id = f"pdf:{path.stem}"
            prov = self.build_provenance(file_path=str(path.resolve()), source_type="pdf")
            success = await self.index_document(
                doc_id=doc_id,
                title=doc_title,
                content=content,
                source_type="pdf",
                source_url=f"file://{path.resolve()}",
                provenance=prov,
            )
            if success:
                ingested_ids.append(doc_id)

        return ingested_ids
