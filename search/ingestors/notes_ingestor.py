"""
JARVIS Notes Ingestor.
Ingests personal notes (Obsidian, Notion, Apple Notes exports, or local markdown)
with tags, folders, and modification metadata.
"""

from typing import Any, Dict, List, Optional
from search.ingestors.base_ingestor import BaseIngestor


class NotesIngestor(BaseIngestor):
    async def ingest_note(
        self,
        note_id: str,
        title: str,
        body: str,
        tags: Optional[List[str]] = None,
        notebook: Optional[str] = None,
    ) -> bool:
        """Ingest personal knowledge note."""
        doc_id = f"note:{note_id}"
        tag_str = f"Tags: {', '.join(tags)}\n" if tags else ""
        nb_str = f"Notebook: {notebook}\n" if notebook else ""
        content = f"{tag_str}{nb_str}\n{body}"

        prov = self.build_provenance(
            source_type="markdown_notes",
            extra={"note_id": note_id, "notebook": notebook, "tags": tags or []},
        )

        return await self.index_document(
            doc_id=doc_id,
            title=title,
            content=content,
            source_type="markdown_notes",
            source_url=f"note://{notebook or 'default'}/{note_id}",
            metadata={"tags": tags or [], "notebook": notebook},
            provenance=prov,
        )
