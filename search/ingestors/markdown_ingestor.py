"""
JARVIS Markdown Ingestor.
Ingests Markdown documentation and notes, indexing section headers,
code blocks, and frontmatter metadata with exact section provenance.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from search.ingestors.base_ingestor import BaseIngestor


class MarkdownIngestor(BaseIngestor):
    async def ingest_markdown(
        self,
        file_path: str,
        title: Optional[str] = None,
        source_type: str = "markdown_notes",
    ) -> List[str]:
        """Ingest Markdown file, splitting into section headings."""
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Markdown file not found: {file_path}")

        raw_text = path.read_text(encoding="utf-8", errors="replace")
        default_title = title or path.stem.replace("_", " ").title()

        # Split on Markdown headers (## or #)
        sections = re.split(r"(?m)^(?=#{1,3}\s+)", raw_text)
        ingested_ids = []

        for idx, section in enumerate(sections):
            text = section.strip()
            if not text:
                continue

            # Extract heading if present
            first_line = text.split("\n")[0].strip("# ").strip()
            section_title = f"{default_title}: {first_line}" if first_line else default_title

            doc_id = f"md:{path.stem}_{idx}"
            prov = self.build_provenance(
                file_path=str(path.resolve()),
                source_type=source_type,
                line_range=f"Section {idx + 1}",
                extra={"section_title": first_line, "file_name": path.name},
            )

            success = await self.index_document(
                doc_id=doc_id,
                title=section_title,
                content=text,
                source_type=source_type,
                source_url=f"file://{path.resolve()}#{first_line.replace(' ', '-').lower()}",
                metadata={"file_name": path.name, "section_index": idx},
                provenance=prov,
            )
            if success:
                ingested_ids.append(doc_id)

        return ingested_ids
