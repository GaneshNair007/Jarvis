"""
JARVIS File & Document Powers (PWR-082 to PWR-099)
Read, write, search, compare, archive, and analyse files including
PDF, CSV, Excel, JSON, and general filesystem operations.
"""

from __future__ import annotations

import csv
import difflib
import hashlib
import json
import os
import shutil
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional


class FilePowers:
    """File and document manipulation powers for JARVIS."""

    # ------------------------------------------------------------------ #
    #  PWR-082 — Read File                                                #
    # ------------------------------------------------------------------ #
    @staticmethod
    def read_file(path: str) -> Dict[str, Any]:
        """PWR-082: Read a text file safely and return its content."""
        try:
            p = Path(path)
            if not p.exists():
                return {"power_id": "PWR-082", "status": "error", "message": f"File not found: {path}"}
            if not p.is_file():
                return {"power_id": "PWR-082", "status": "error", "message": f"Not a file: {path}"}
            size = p.stat().st_size
            # Guard against accidentally reading huge files into memory
            if size > 50 * 1024 * 1024:  # 50 MB
                return {
                    "power_id": "PWR-082",
                    "status": "error",
                    "message": f"File too large ({size:,} bytes). Use a streaming approach.",
                }
            content = p.read_text(encoding="utf-8", errors="replace")
            return {
                "power_id": "PWR-082",
                "status": "success",
                "path": str(p.resolve()),
                "size_bytes": size,
                "lines": content.count("\n") + 1,
                "content": content,
            }
        except Exception as e:
            return {"power_id": "PWR-082", "status": "error", "message": f"Failed to read file: {e}"}

    # ------------------------------------------------------------------ #
    #  PWR-083 — Write File                                               #
    # ------------------------------------------------------------------ #
    @staticmethod
    def write_file(path: str, content: str) -> Dict[str, Any]:
        """PWR-083: Write text content to a file.

        If the file already exists the response includes approval_required=True
        so the caller can confirm before overwriting.
        """
        try:
            p = Path(path)
            overwrite = p.exists()
            if overwrite:
                return {
                    "power_id": "PWR-083",
                    "status": "pending",
                    "approval_required": True,
                    "message": f"File already exists: {path}. Confirm overwrite.",
                    "path": str(p.resolve()),
                }
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return {
                "power_id": "PWR-083",
                "status": "success",
                "path": str(p.resolve()),
                "bytes_written": len(content.encode("utf-8")),
            }
        except Exception as e:
            return {"power_id": "PWR-083", "status": "error", "message": f"Failed to write file: {e}"}

    # ------------------------------------------------------------------ #
    #  PWR-084 — PDF Extract Text                                         #
    # ------------------------------------------------------------------ #
    @staticmethod
    def pdf_extract_text(path: str) -> Dict[str, Any]:
        """PWR-084: Extract text from a PDF file.

        Tries PyMuPDF (fitz) first, falls back to a basic subprocess call.
        """
        try:
            p = Path(path)
            if not p.exists():
                return {"power_id": "PWR-084", "status": "error", "message": f"File not found: {path}"}

            # ---- Try PyMuPDF ----
            try:
                import fitz  # type: ignore[import-untyped]

                doc = fitz.open(str(p))
                pages: List[str] = []
                for page in doc:
                    pages.append(page.get_text())
                doc.close()
                full_text = "\n".join(pages)
                return {
                    "power_id": "PWR-084",
                    "status": "success",
                    "engine": "pymupdf",
                    "path": str(p.resolve()),
                    "pages": len(pages),
                    "text": full_text,
                }
            except ImportError:
                pass

            # ---- Fallback: try pdfminer.six ----
            try:
                from pdfminer.high_level import extract_text as _extract  # type: ignore[import-untyped]

                text = _extract(str(p))
                return {
                    "power_id": "PWR-084",
                    "status": "success",
                    "engine": "pdfminer",
                    "path": str(p.resolve()),
                    "text": text,
                }
            except ImportError:
                pass

            return {
                "power_id": "PWR-084",
                "status": "error",
                "message": "No PDF library available. Install PyMuPDF (`pip install pymupdf`) or pdfminer.six.",
            }
        except Exception as e:
            return {"power_id": "PWR-084", "status": "error", "message": f"PDF extraction failed: {e}"}

    # ------------------------------------------------------------------ #
    #  PWR-085 — PDF Search                                               #
    # ------------------------------------------------------------------ #
    @staticmethod
    def pdf_search(path: str, query: str) -> Dict[str, Any]:
        """PWR-085: Search within a PDF for a text query."""
        try:
            p = Path(path)
            if not p.exists():
                return {"power_id": "PWR-085", "status": "error", "message": f"File not found: {path}"}

            try:
                import fitz  # type: ignore[import-untyped]

                doc = fitz.open(str(p))
                matches: List[Dict[str, Any]] = []
                for page_num, page in enumerate(doc, start=1):
                    text = page.get_text()
                    if query.lower() in text.lower():
                        # Find line-level matches
                        for line_no, line in enumerate(text.splitlines(), start=1):
                            if query.lower() in line.lower():
                                matches.append({"page": page_num, "line": line_no, "text": line.strip()})
                doc.close()
                return {
                    "power_id": "PWR-085",
                    "status": "success",
                    "path": str(p.resolve()),
                    "query": query,
                    "match_count": len(matches),
                    "matches": matches[:100],  # cap results
                }
            except ImportError:
                return {
                    "power_id": "PWR-085",
                    "status": "error",
                    "message": "PyMuPDF not installed. Run `pip install pymupdf`.",
                }
        except Exception as e:
            return {"power_id": "PWR-085", "status": "error", "message": f"PDF search failed: {e}"}

    # ------------------------------------------------------------------ #
    #  PWR-086 — CSV Summary                                              #
    # ------------------------------------------------------------------ #
    @staticmethod
    def csv_summary(path: str) -> Dict[str, Any]:
        """PWR-086: Produce summary statistics for a CSV file."""
        try:
            p = Path(path)
            if not p.exists():
                return {"power_id": "PWR-086", "status": "error", "message": f"File not found: {path}"}

            with open(p, newline="", encoding="utf-8-sig", errors="replace") as f:
                reader = csv.reader(f)
                rows = list(reader)

            if not rows:
                return {"power_id": "PWR-086", "status": "success", "path": str(p.resolve()), "rows": 0, "columns": 0}

            headers = rows[0]
            data_rows = rows[1:]

            # Simple dtype inference
            dtypes: Dict[str, str] = {}
            for col_idx, col_name in enumerate(headers):
                sample_vals = [r[col_idx] for r in data_rows[:100] if col_idx < len(r) and r[col_idx].strip()]
                if all(_is_numeric(v) for v in sample_vals) and sample_vals:
                    dtypes[col_name] = "numeric"
                else:
                    dtypes[col_name] = "text"

            head = [dict(zip(headers, r)) for r in data_rows[:5]]

            return {
                "power_id": "PWR-086",
                "status": "success",
                "path": str(p.resolve()),
                "rows": len(data_rows),
                "columns": len(headers),
                "headers": headers,
                "dtypes": dtypes,
                "head": head,
            }
        except Exception as e:
            return {"power_id": "PWR-086", "status": "error", "message": f"CSV summary failed: {e}"}

    # ------------------------------------------------------------------ #
    #  PWR-087 — CSV Query / Filter                                       #
    # ------------------------------------------------------------------ #
    @staticmethod
    def csv_query(path: str, filter_col: str, filter_val: str) -> Dict[str, Any]:
        """PWR-087: Filter CSV rows where filter_col matches filter_val."""
        try:
            p = Path(path)
            if not p.exists():
                return {"power_id": "PWR-087", "status": "error", "message": f"File not found: {path}"}

            with open(p, newline="", encoding="utf-8-sig", errors="replace") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames is None:
                    return {"power_id": "PWR-087", "status": "error", "message": "CSV has no headers."}
                if filter_col not in reader.fieldnames:
                    return {
                        "power_id": "PWR-087",
                        "status": "error",
                        "message": f"Column '{filter_col}' not found. Available: {reader.fieldnames}",
                    }
                matches = [
                    row for row in reader if row.get(filter_col, "").strip().lower() == filter_val.strip().lower()
                ]

            return {
                "power_id": "PWR-087",
                "status": "success",
                "path": str(p.resolve()),
                "filter": {filter_col: filter_val},
                "match_count": len(matches),
                "rows": matches[:200],
            }
        except Exception as e:
            return {"power_id": "PWR-087", "status": "error", "message": f"CSV query failed: {e}"}

    # ------------------------------------------------------------------ #
    #  PWR-088 — Excel Summary                                            #
    # ------------------------------------------------------------------ #
    @staticmethod
    def excel_summary(path: str) -> Dict[str, Any]:
        """PWR-088: Produce a summary of an Excel workbook (sheet names, shapes)."""
        try:
            p = Path(path)
            if not p.exists():
                return {"power_id": "PWR-088", "status": "error", "message": f"File not found: {path}"}

            try:
                import openpyxl  # type: ignore[import-untyped]

                wb = openpyxl.load_workbook(str(p), read_only=True, data_only=True)
                sheets_info: List[Dict[str, Any]] = []
                for name in wb.sheetnames:
                    ws = wb[name]
                    sheets_info.append(
                        {
                            "name": name,
                            "rows": ws.max_row,
                            "columns": ws.max_column,
                        }
                    )
                wb.close()
                return {
                    "power_id": "PWR-088",
                    "status": "success",
                    "path": str(p.resolve()),
                    "sheet_count": len(sheets_info),
                    "sheets": sheets_info,
                }
            except ImportError:
                return {
                    "power_id": "PWR-088",
                    "status": "error",
                    "message": "openpyxl not installed. Run `pip install openpyxl`.",
                }
        except Exception as e:
            return {"power_id": "PWR-088", "status": "error", "message": f"Excel summary failed: {e}"}

    # ------------------------------------------------------------------ #
    #  PWR-089 — JSON Query                                               #
    # ------------------------------------------------------------------ #
    @staticmethod
    def json_query(path: str, jmespath_expr: Optional[str] = None) -> Dict[str, Any]:
        """PWR-089: Read and optionally query a JSON file with a JMESPath expression."""
        try:
            p = Path(path)
            if not p.exists():
                return {"power_id": "PWR-089", "status": "error", "message": f"File not found: {path}"}

            data = json.loads(p.read_text(encoding="utf-8"))

            if jmespath_expr:
                try:
                    import jmespath as jmp  # type: ignore[import-untyped]

                    result = jmp.search(jmespath_expr, data)
                    return {
                        "power_id": "PWR-089",
                        "status": "success",
                        "path": str(p.resolve()),
                        "expression": jmespath_expr,
                        "result": result,
                    }
                except ImportError:
                    return {
                        "power_id": "PWR-089",
                        "status": "error",
                        "message": "jmespath not installed. Run `pip install jmespath`. Returning raw data.",
                        "data": data,
                    }
            else:
                return {
                    "power_id": "PWR-089",
                    "status": "success",
                    "path": str(p.resolve()),
                    "data": data,
                }
        except json.JSONDecodeError as e:
            return {"power_id": "PWR-089", "status": "error", "message": f"Invalid JSON: {e}"}
        except Exception as e:
            return {"power_id": "PWR-089", "status": "error", "message": f"JSON query failed: {e}"}

    # ------------------------------------------------------------------ #
    #  PWR-090 — File Search                                              #
    # ------------------------------------------------------------------ #
    @staticmethod
    def file_search(directory: str, pattern: str) -> Dict[str, Any]:
        """PWR-090: Search for files by name/glob pattern in a directory tree."""
        try:
            d = Path(directory)
            if not d.is_dir():
                return {"power_id": "PWR-090", "status": "error", "message": f"Not a directory: {directory}"}

            matches = sorted(str(m.resolve()) for m in d.rglob(pattern))
            return {
                "power_id": "PWR-090",
                "status": "success",
                "directory": str(d.resolve()),
                "pattern": pattern,
                "match_count": len(matches),
                "matches": matches[:500],
            }
        except Exception as e:
            return {"power_id": "PWR-090", "status": "error", "message": f"File search failed: {e}"}

    # ------------------------------------------------------------------ #
    #  PWR-091 — File Info                                                #
    # ------------------------------------------------------------------ #
    @staticmethod
    def file_info(path: str) -> Dict[str, Any]:
        """PWR-091: Return metadata for a file (size, modified, type, SHA-256 hash)."""
        try:
            p = Path(path)
            if not p.exists():
                return {"power_id": "PWR-091", "status": "error", "message": f"Path not found: {path}"}

            stat = p.stat()
            sha256 = ""
            if p.is_file() and stat.st_size < 100 * 1024 * 1024:  # hash files < 100 MB
                h = hashlib.sha256()
                with open(p, "rb") as f:
                    for chunk in iter(lambda: f.read(65536), b""):
                        h.update(chunk)
                sha256 = h.hexdigest()

            import time as _time

            return {
                "power_id": "PWR-091",
                "status": "success",
                "path": str(p.resolve()),
                "is_file": p.is_file(),
                "is_dir": p.is_dir(),
                "size_bytes": stat.st_size,
                "modified": _time.ctime(stat.st_mtime),
                "created": _time.ctime(stat.st_ctime),
                "suffix": p.suffix,
                "sha256": sha256,
            }
        except Exception as e:
            return {"power_id": "PWR-091", "status": "error", "message": f"File info failed: {e}"}

    # ------------------------------------------------------------------ #
    #  PWR-092 — File Compare                                             #
    # ------------------------------------------------------------------ #
    @staticmethod
    def file_compare(path1: str, path2: str) -> Dict[str, Any]:
        """PWR-092: Compare two text files and return a unified diff."""
        try:
            p1, p2 = Path(path1), Path(path2)
            for pp in (p1, p2):
                if not pp.is_file():
                    return {"power_id": "PWR-092", "status": "error", "message": f"File not found: {pp}"}

            lines1 = p1.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            lines2 = p2.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            diff = list(difflib.unified_diff(lines1, lines2, fromfile=str(p1), tofile=str(p2)))
            identical = len(diff) == 0

            return {
                "power_id": "PWR-092",
                "status": "success",
                "path1": str(p1.resolve()),
                "path2": str(p2.resolve()),
                "identical": identical,
                "diff_lines": len(diff),
                "diff": "".join(diff[:500]),
            }
        except Exception as e:
            return {"power_id": "PWR-092", "status": "error", "message": f"File compare failed: {e}"}

    # ------------------------------------------------------------------ #
    #  PWR-093 — Zip Archive                                              #
    # ------------------------------------------------------------------ #
    @staticmethod
    def zip_archive(paths: List[str], output: str) -> Dict[str, Any]:
        """PWR-093: Create a zip archive from a list of file/folder paths."""
        try:
            out = Path(output)
            out.parent.mkdir(parents=True, exist_ok=True)
            added: List[str] = []
            with zipfile.ZipFile(str(out), "w", zipfile.ZIP_DEFLATED) as zf:
                for item in paths:
                    ip = Path(item)
                    if ip.is_file():
                        zf.write(str(ip), ip.name)
                        added.append(ip.name)
                    elif ip.is_dir():
                        for child in ip.rglob("*"):
                            if child.is_file():
                                arcname = str(child.relative_to(ip.parent))
                                zf.write(str(child), arcname)
                                added.append(arcname)
            return {
                "power_id": "PWR-093",
                "status": "success",
                "archive": str(out.resolve()),
                "files_added": len(added),
                "entries": added[:100],
            }
        except Exception as e:
            return {"power_id": "PWR-093", "status": "error", "message": f"Zip archive failed: {e}"}

    # ------------------------------------------------------------------ #
    #  PWR-094 — Zip Extract                                              #
    # ------------------------------------------------------------------ #
    @staticmethod
    def zip_extract(archive: str, destination: str) -> Dict[str, Any]:
        """PWR-094: Extract a zip archive to a destination directory."""
        try:
            a = Path(archive)
            if not a.is_file():
                return {"power_id": "PWR-094", "status": "error", "message": f"Archive not found: {archive}"}

            dest = Path(destination)
            dest.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(str(a), "r") as zf:
                names = zf.namelist()
                zf.extractall(str(dest))
            return {
                "power_id": "PWR-094",
                "status": "success",
                "archive": str(a.resolve()),
                "destination": str(dest.resolve()),
                "files_extracted": len(names),
                "entries": names[:100],
            }
        except Exception as e:
            return {"power_id": "PWR-094", "status": "error", "message": f"Zip extract failed: {e}"}

    # ------------------------------------------------------------------ #
    #  PWR-095 — File Rename                                              #
    # ------------------------------------------------------------------ #
    @staticmethod
    def file_rename(old_path: str, new_path: str) -> Dict[str, Any]:
        """PWR-095: Rename / move a file."""
        try:
            src = Path(old_path)
            if not src.exists():
                return {"power_id": "PWR-095", "status": "error", "message": f"Source not found: {old_path}"}
            dst = Path(new_path)
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
            return {
                "power_id": "PWR-095",
                "status": "success",
                "old_path": str(src),
                "new_path": str(dst.resolve()),
            }
        except Exception as e:
            return {"power_id": "PWR-095", "status": "error", "message": f"File rename failed: {e}"}

    # ------------------------------------------------------------------ #
    #  PWR-096 — File Copy                                                #
    # ------------------------------------------------------------------ #
    @staticmethod
    def file_copy(src: str, dst: str) -> Dict[str, Any]:
        """PWR-096: Copy a file or directory."""
        try:
            s, d = Path(src), Path(dst)
            if not s.exists():
                return {"power_id": "PWR-096", "status": "error", "message": f"Source not found: {src}"}
            d.parent.mkdir(parents=True, exist_ok=True)
            if s.is_dir():
                shutil.copytree(str(s), str(d))
            else:
                shutil.copy2(str(s), str(d))
            return {
                "power_id": "PWR-096",
                "status": "success",
                "source": str(s.resolve()),
                "destination": str(d.resolve()),
            }
        except Exception as e:
            return {"power_id": "PWR-096", "status": "error", "message": f"File copy failed: {e}"}

    # ------------------------------------------------------------------ #
    #  PWR-097 — File Delete                                              #
    # ------------------------------------------------------------------ #
    @staticmethod
    def file_delete(path: str) -> Dict[str, Any]:
        """PWR-097: Delete a file (requires approval)."""
        try:
            p = Path(path)
            if not p.exists():
                return {"power_id": "PWR-097", "status": "error", "message": f"Path not found: {path}"}
            return {
                "power_id": "PWR-097",
                "status": "pending",
                "approval_required": True,
                "path": str(p.resolve()),
                "is_dir": p.is_dir(),
                "message": f"Confirm deletion of {'directory' if p.is_dir() else 'file'}: {p.resolve()}",
            }
        except Exception as e:
            return {"power_id": "PWR-097", "status": "error", "message": f"File delete failed: {e}"}

    # ------------------------------------------------------------------ #
    #  PWR-098 — Directory Tree                                           #
    # ------------------------------------------------------------------ #
    @staticmethod
    def directory_tree(path: str, depth: int = 3) -> Dict[str, Any]:
        """PWR-098: List directory contents as a tree structure."""
        try:
            root = Path(path)
            if not root.is_dir():
                return {"power_id": "PWR-098", "status": "error", "message": f"Not a directory: {path}"}

            lines: List[str] = [str(root.resolve())]
            _walk_tree(root, lines, prefix="", depth=depth, max_items=500)
            return {
                "power_id": "PWR-098",
                "status": "success",
                "path": str(root.resolve()),
                "depth": depth,
                "tree": "\n".join(lines),
            }
        except Exception as e:
            return {"power_id": "PWR-098", "status": "error", "message": f"Directory tree failed: {e}"}

    # ------------------------------------------------------------------ #
    #  PWR-099 — Disk Usage by Folder                                     #
    # ------------------------------------------------------------------ #
    @staticmethod
    def disk_usage_by_folder(path: str) -> Dict[str, Any]:
        """PWR-099: Analyse disk usage for immediate sub-folders of the given path."""
        try:
            root = Path(path)
            if not root.is_dir():
                return {"power_id": "PWR-099", "status": "error", "message": f"Not a directory: {path}"}

            folders: List[Dict[str, Any]] = []
            total = 0
            for entry in sorted(root.iterdir()):
                if entry.is_dir():
                    size = _dir_size(entry)
                    folders.append({"name": entry.name, "size_bytes": size, "size_human": _human_size(size)})
                    total += size
                elif entry.is_file():
                    total += entry.stat().st_size

            folders.sort(key=lambda x: x["size_bytes"], reverse=True)
            return {
                "power_id": "PWR-099",
                "status": "success",
                "path": str(root.resolve()),
                "total_size_bytes": total,
                "total_size_human": _human_size(total),
                "folders": folders[:100],
            }
        except Exception as e:
            return {"power_id": "PWR-099", "status": "error", "message": f"Disk usage analysis failed: {e}"}


# ===================================================================== #
#  Module-level helpers                                                  #
# ===================================================================== #


def _is_numeric(val: str) -> bool:
    """Check if a string looks numeric."""
    try:
        float(val.replace(",", ""))
        return True
    except (ValueError, AttributeError):
        return False


def _walk_tree(directory: Path, lines: List[str], prefix: str, depth: int, max_items: int) -> None:
    """Recursively build a directory tree representation."""
    if depth <= 0 or len(lines) >= max_items:
        return
    try:
        entries = sorted(directory.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
    except PermissionError:
        lines.append(f"{prefix}[permission denied]")
        return

    count = len(entries)
    for i, entry in enumerate(entries):
        if len(lines) >= max_items:
            lines.append(f"{prefix}... (truncated)")
            return
        connector = "└── " if i == count - 1 else "├── "
        suffix = "/" if entry.is_dir() else ""
        lines.append(f"{prefix}{connector}{entry.name}{suffix}")
        if entry.is_dir():
            extension = "    " if i == count - 1 else "│   "
            _walk_tree(entry, lines, prefix + extension, depth - 1, max_items)


def _dir_size(path: Path) -> int:
    """Calculate total size of a directory."""
    total = 0
    try:
        for f in path.rglob("*"):
            if f.is_file():
                try:
                    total += f.stat().st_size
                except OSError:
                    pass
    except PermissionError:
        pass
    return total


def _human_size(nbytes: int) -> str:
    """Convert bytes to human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(nbytes) < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024  # type: ignore[assignment]
    return f"{nbytes:.1f} PB"


file_powers = FilePowers()
