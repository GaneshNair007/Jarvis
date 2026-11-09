"""
JARVIS Model -> Humanizer -> PDF Pipeline.

Turns raw model output (markdown) into a natural-sounding, well-typeset PDF:

    model text -> humanize_text() -> render_markdown_to_pdf() -> TrustResult

The humanizer applies deterministic local rewrites (no network, no LLM) that
strip stock AI phrasing so documents read like a person wrote them. The PDF
renderer uses ReportLab and verifies its own output with pypdf (page count,
text presence) before claiming success (First Law: No Evidence, No Claim).
"""

from __future__ import annotations

import hashlib
import io
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jarvis.core.evidence import Evidence, TrustResult
from jarvis.core.logger import get_logger

logger = get_logger("doc_pipeline")

# --------------------------------------------------------------------------- #
# Humanizer                                                                    #
# --------------------------------------------------------------------------- #

# Order matters: longer/more specific phrases first.
_AI_PHRASES: List[Tuple[str, str]] = [
    (r"\bIt(?:'s| is) important to (?:note|remember|understand) that\s*", ""),
    (r"\bIt(?:'s| is) worth noting that\s*", ""),
    (r"\bIn today's fast-paced world,?\s*", "These days, "),
    (r"\bIn the (?:ever-changing|rapidly evolving) (?:world|landscape)[^,]*,?\s*", ""),
    (r"\bDelve into\b", "Look at"),
    (r"\bdelve into\b", "look at"),
    (r"\bdelve deeper\b", "go deeper"),
    (r"\bunlock the (?:full )?potential of\b", "get more out of"),
    (r"\bleverage\b", "use"),
    (r"\bleveraging\b", "using"),
    (r"\butilize\b", "use"),
    (r"\butilizing\b", "using"),
    (r"\bfoster(?:s|ed|ing)?\b", "build"),
    (r"\bcultivate\b", "grow"),
    (r"\bseamless(?:ly)?\b", "smooth"),
    (r"\brobust\b", "solid"),
    (r"\bcomprehensive\b", "complete"),
    (r"\bgroundbreaking\b", "new"),
    (r"\bstate-of-the-art\b", "modern"),
    (r"\bcutting-edge\b", "latest"),
    (r"\bgame-changing\b", "big"),
    (r"\btransformative\b", "useful"),
    (r"\bMoreover,\s*", "Also, "),
    (r"\bFurthermore,\s*", "Also, "),
    (r"\bAdditionally,\s*", "And, "),
    (r"\bIn conclusion,\s*", ""),
    (r"\bTo sum up,?\s*", ""),
    (r"\bAt the end of the day,?\s*", ""),
    (r"\bWhen it comes to\b", "For"),
    (r"\bplays a (?:vital|crucial|key) role in\b", "matters for"),
    (r"\ba myriad of\b", "a lot of"),
    (r"\ba plethora of\b", "plenty of"),
    (r"\btestament to\b", "proof of"),
    (r"\bnavigat(?:e|ing) the complexities of\b", "handle"),
    (r"\bin the realm of\b", "in"),
    (r"\bpar(?:t|adigm) shift\b", "big change"),
    (r"\bholistic\b", "whole"),
    (r"\bpivotal\b", "key"),
    (r"\bmeticulous(?:ly)?\b", "careful"),
    (r"\boptimal\b", "best"),
    (r"\bfacilitate\b", "help"),
    (r"\bendeavor(?:s|ed)? to\b", "try to"),
    (r"\bprioritiz(?:e|es|ed)\b", "put first"),
    (r"\bsynerg(?:y|ies)\b", "teamwork"),
    (r"\bempower(?:s|ed)?\b", "help"),
    (r"\binnovative\b", "new"),
    (r"\bexemplif(?:y|ies|ied)\b", "show"),
    (r"\bsubsequently\b", "then"),
    (r"\bconsequently\b", "so"),
    (r"\bnonetheless\b", "still"),
    (r"\bHere's the thing[,:]\s*", ""),
    (r"\bAs an AI (?:language )?model[^.]*\.\s*", ""),
    (r"\bI hope (?:this|that) helps[^.]*\.\s*", ""),
    (r"\bLet me know if you (?:have|need) any[^.]*\.\s*", ""),
]

_AI_FILLER_LINES = re.compile(
    r"^\s*(?:Sure[.!]?|Absolutely[.!]?|Of course[.!]?|Great question[.!]?|"
    r"Certainly[.!]?|Happy to help[.!]?)\s*$",
    re.IGNORECASE,
)


def humanize_text(text: str) -> str:
    """Deterministically rewrites stock AI phrasing into natural language.

    Purely local and reversible-free: same input always yields same output.
    """
    if not text:
        return ""

    out = text
    # Strip line-leading chat fillers ("Sure! Here's ..." -> "Here's ...").
    out = re.sub(
        r"^(?:Sure|Absolutely|Of course|Great question|Certainly|Happy to help)[.!]\s*",
        "",
        out,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    for pattern, replacement in _AI_PHRASES:
        out = re.sub(pattern, replacement, out, flags=re.IGNORECASE)

    lines = out.splitlines()
    cleaned: List[str] = []
    for line in lines:
        if _AI_FILLER_LINES.match(line):
            continue
        # Collapse runs of 3+ exclamation/question marks to one.
        line = re.sub(r"([!?])\1{2,}", r"\1", line)
        # Collapse " — " em-dash chains people overuse into a comma.
        line = re.sub(r"\s*—\s*", ", ", line)
        # Fix double spaces / space-before-punctuation from deletions.
        line = re.sub(r"[ \t]{2,}", " ", line)
        line = re.sub(r"\s+([,.;:])", r"\1", line)
        cleaned.append(line)
    out = "\n".join(cleaned)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip() + ("\n" if text.endswith("\n") else "")


# --------------------------------------------------------------------------- #
# Markdown -> ReportLab renderer                                               #
# --------------------------------------------------------------------------- #


def _inline_markup(text: str) -> str:
    """Converts markdown inline syntax to ReportLab paragraph markup."""
    t = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", t)
    t = re.sub(r"`([^`]+)`", r'<font face="Courier">\1</font>', t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", t)
    return t


def _markdown_to_flowables(markdown_text: str) -> List[Any]:
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Spacer, ListFlowable, ListItem, Preformatted

    styles = {
        "h1": ParagraphStyle(
            "h1", fontName="Helvetica-Bold", fontSize=18, leading=23, spaceAfter=6, spaceBefore=10, textColor="#10243a"
        ),
        "h2": ParagraphStyle(
            "h2", fontName="Helvetica-Bold", fontSize=14, leading=18, spaceAfter=5, spaceBefore=9, textColor="#183b57"
        ),
        "h3": ParagraphStyle(
            "h3", fontName="Helvetica-Bold", fontSize=11.5, leading=15, spaceAfter=4, spaceBefore=7, textColor="#234b6b"
        ),
        "body": ParagraphStyle(
            "body", fontName="Helvetica", fontSize=10.5, leading=15, spaceAfter=6, textColor="#1a1a1a"
        ),
        "bullet": ParagraphStyle("bullet", fontName="Helvetica", fontSize=10.5, leading=15, textColor="#1a1a1a"),
        "code": ParagraphStyle(
            "code",
            fontName="Courier",
            fontSize=9,
            leading=12,
            backColor="#f2f4f6",
            borderPadding=6,
            spaceAfter=6,
            textColor="#222222",
        ),
    }

    flow: List[Any] = []
    lines = markdown_text.splitlines()
    i = 0
    paragraph_buf: List[str] = []
    bullet_buf: List[str] = []
    code_buf: List[str] = []
    in_code = False

    def flush_paragraph() -> None:
        if paragraph_buf:
            joined = " ".join(paragraph_buf)
            flow.append(Paragraph(_inline_markup(joined), styles["body"]))
            paragraph_buf.clear()

    def flush_bullets() -> None:
        if bullet_buf:
            items = [ListItem(Paragraph(_inline_markup(b), styles["bullet"])) for b in bullet_buf]
            flow.append(ListFlowable(items, bulletType="bullet", start="•", leftIndent=14, bulletFontSize=9))
            flow.append(Spacer(1, 4))
            bullet_buf.clear()

    while i < len(lines):
        line = lines[i]

        if line.strip().startswith("```"):
            flush_paragraph()
            flush_bullets()
            if in_code:
                flow.append(Preformatted("\n".join(code_buf), styles["code"]))
                code_buf.clear()
                in_code = False
            else:
                in_code = True
            i += 1
            continue

        if in_code:
            code_buf.append(line)
            i += 1
            continue

        if not line.strip():
            flush_paragraph()
            flush_bullets()
            i += 1
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            flush_paragraph()
            flush_bullets()
            level = min(len(heading.group(1)), 3)
            style = styles[f"h{level}"]
            flow.append(Paragraph(_inline_markup(heading.group(2).strip()), style))
            i += 1
            continue

        bullet = re.match(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$", line)
        if bullet:
            flush_paragraph()
            bullet_buf.append(bullet.group(1).strip())
            i += 1
            continue

        if re.match(r"^\s*>\s?", line):
            flush_bullets()
            paragraph_buf.append(re.sub(r"^\s*>\s?", "", line))
            i += 1
            continue

        paragraph_buf.append(line.strip())
        i += 1

    if in_code and code_buf:
        flow.append(Preformatted("\n".join(code_buf), styles["code"]))
    flush_paragraph()
    flush_bullets()

    if not flow:
        from reportlab.platypus import Paragraph

        flow.append(Paragraph("(empty document)", styles["body"]))
    return flow


def _footer(canvas: Any, doc: Any) -> None:
    from reportlab.lib.units import mm

    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor("#6b7c8c")
    canvas.drawString(18 * mm, 10 * mm, "Generated by JARVIS")
    canvas.drawRightString(192 * mm, 10 * mm, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()


def render_markdown_to_pdf(markdown_text: str, output_path: Path, title: str = "JARVIS Report") -> Dict[str, Any]:
    """Renders markdown to a PDF file. Returns {path, pages, sha256, bytes}."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        title=title,
        author="JARVIS",
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    flow = _markdown_to_flowables(markdown_text)
    doc.build(flow, onFirstPage=_footer, onLaterPages=_footer)

    raw = output_path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    pages = _pdf_page_count(raw)
    return {"path": str(output_path), "pages": pages, "sha256": sha, "bytes": len(raw)}


def _pdf_page_count(raw: bytes) -> int:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(raw))
        return len(reader.pages)
    except Exception as exc:  # pragma: no cover - pypdf installed
        logger.warning(f"pypdf page count failed: {exc}")
        return 0


def _pdf_contains_text(raw: bytes, needle: str) -> bool:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(raw))
        text = " ".join((page.extract_text() or "") for page in reader.pages)
        return needle.lower() in text.lower()
    except Exception:  # pragma: no cover
        return False


# --------------------------------------------------------------------------- #
# End-to-end pipeline (PWR-316)                                                #
# --------------------------------------------------------------------------- #


class DocPipeline:
    """Model output -> humanized markdown -> verified PDF -> TrustResult."""

    def humanize(self, text: str) -> Dict[str, Any]:
        """PWR-316a: strips stock AI phrasing. Returns before/after stats."""
        humanized = humanize_text(text)
        cliche_hits = sum(1 for pat, _ in _AI_PHRASES if re.search(pat, text))
        return {
            "power_id": "PWR-316",
            "humanized": humanized,
            "input_chars": len(text),
            "output_chars": len(humanized),
            "cliches_removed": cliche_hits,
        }

    def model_to_pdf(
        self,
        model_text: str,
        output_dir: Optional[Path] = None,
        title: str = "JARVIS Report",
        humanize: bool = True,
    ) -> TrustResult:
        """PWR-316: full pipeline. Returns TrustResult; success only if the PDF
        exists on disk, parses, has >= 1 page, and contains the document text."""
        started = time.time()
        if not (model_text or "").strip():
            ev = Evidence(
                source="doc_pipeline.model_to_pdf",
                data={"status": "rejected", "reason": "empty_model_output"},
                timestamp=started,
            )
            return TrustResult.fail(evidence=ev, description="empty model output")

        try:
            text = humanize_text(model_text) if humanize else model_text
            out_dir = Path(output_dir) if output_dir else Path("artifacts") / "reports"
            stamp = time.strftime("%Y%m%d_%H%M%S")
            safe_title = re.sub(r"[^A-Za-z0-9_-]+", "_", title)[:40] or "report"
            out_path = out_dir / f"{safe_title}_{stamp}.pdf"

            info = render_markdown_to_pdf(text, out_path, title=title)
            raw = Path(info["path"]).read_bytes()

            # Needle = first meaningful line with markdown markers stripped,
            # since the PDF renders "Title", not "# Title".
            first_line = next((ln for ln in text.split("\n") if ln.strip()), "")
            needle = re.sub(r"^#+\s*", "", first_line).strip().strip("*`- ").strip()
            checks = {
                "file_exists": Path(info["path"]).is_file(),
                "pages_ge_1": info["pages"] >= 1,
                "parses_text": _pdf_contains_text(raw, needle[:40]) if needle else True,
                "sha256_present": bool(info["sha256"]),
            }
            all_ok = all(checks.values())
            duration_ms = round((time.time() - started) * 1000, 2)
            ev = Evidence(
                source="doc_pipeline.model_to_pdf",
                data={
                    "status": "success" if all_ok else "verification_failed",
                    "path": info["path"],
                    "pages": info["pages"],
                    "sha256": info["sha256"],
                    "bytes": info["bytes"],
                    "humanized": humanize,
                    "checks": checks,
                    "duration_ms": duration_ms,
                },
                timestamp=time.time(),
            )
            if all_ok:
                logger.info("model_to_pdf ok: %s (%s pages)", info["path"], info["pages"])
                return TrustResult.success(
                    evidence=ev,
                    description=f"PDF written and verified: {info['path']} ({info['pages']} pages)",
                )
            return TrustResult.fail(evidence=ev, description=f"PDF verification failed: {checks}")
        except Exception as exc:
            ev = Evidence(
                source="doc_pipeline.model_to_pdf",
                data={"status": "error", "error": str(exc)},
                timestamp=time.time(),
            )
            return TrustResult.fail(evidence=ev, description=f"pipeline error: {exc}")


doc_pipeline = DocPipeline()
