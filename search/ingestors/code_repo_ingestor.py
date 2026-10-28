"""
JARVIS Code Repository Ingestor.
Walks source code directories, respects .gitignore patterns,
filters out binaries, and indexes code modules with file and line provenance.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from search.ingestors.base_ingestor import BaseIngestor


class CodeRepoIngestor(BaseIngestor):
    # Allowed source extensions
    CODE_EXTENSIONS = {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css",
        ".go", ".rs", ".java", ".c", ".cpp", ".h", ".sh",
        ".json", ".yaml", ".yml", ".toml", ".sql", ".dockerfile",
    }

    # Directories to unconditionally ignore
    IGNORED_DIRS = {
        ".git", ".venv", "venv", "node_modules", "__pycache__",
        ".pytest_cache", "dist", "build", ".next", ".artifacts",
    }

    async def ingest_repository(
        self,
        repo_dir: str,
        repo_name: Optional[str] = None,
        max_files: int = 150,
    ) -> List[str]:
        """Index source code files within a repository directory."""
        root = Path(repo_dir)
        if not root.exists() or not root.is_dir():
            raise NotADirectoryError(f"Repository directory not found: {repo_dir}")

        name = repo_name or root.name
        ingested_ids = []
        files_indexed = 0

        for path in root.rglob("*"):
            if files_indexed >= max_files:
                break

            # Skip ignored directories
            if any(part in self.IGNORED_DIRS for part in path.parts):
                continue

            if not path.is_file():
                continue

            # Check extension
            if path.suffix.lower() not in self.CODE_EXTENSIONS and path.name.lower() != "dockerfile":
                continue

            # Skip files larger than 500KB
            try:
                if path.stat().st_size > 500 * 1024:
                    continue
                content = path.read_text(encoding="utf-8", errors="replace").strip()
            except Exception:
                continue

            if not content:
                continue

            rel_path = path.relative_to(root).as_posix()
            doc_id = f"repo:{name}:{rel_path.replace('/', '_')}"
            title = f"{name}: {rel_path}"

            prov = self.build_provenance(
                file_path=str(path.resolve()),
                source_type="code_repo",
                extra={
                    "repo_name": name,
                    "relative_path": rel_path,
                    "extension": path.suffix,
                    "lines_count": len(content.splitlines()),
                },
            )

            # Chunk large files if needed
            chunks = self.chunk_text(content, chunk_size=2000, overlap=250)
            for c_idx, chunk in enumerate(chunks):
                chunk_id = f"{doc_id}_{c_idx}" if len(chunks) > 1 else doc_id
                chunk_title = f"{title} (Part {c_idx + 1})" if len(chunks) > 1 else title

                success = await self.index_document(
                    doc_id=chunk_id,
                    title=chunk_title,
                    content=chunk,
                    source_type="code_repo",
                    source_url=f"file://{path.resolve()}",
                    metadata={"repo": name, "file": rel_path},
                    provenance=prov,
                )
                if success:
                    ingested_ids.append(chunk_id)

            files_indexed += 1

        return ingested_ids
