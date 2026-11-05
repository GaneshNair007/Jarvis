"""
Model -> Humanizer -> PDF pipeline verification.

Proves: deterministic humanization of stock AI phrasing, real ReportLab PDF
generation verified by pypdf (page count + text extraction + sha256), and
TrustResult-backed success/failure (First Law).
"""

import hashlib
import re
from pathlib import Path

from jarvis.core.doc_pipeline import DocPipeline, humanize_text, render_markdown_to_pdf
from jarvis.core.evidence import TrustResult


SAMPLE_MODEL_OUTPUT = """\
# Quarterly Summary

Sure! Here's the summary you asked for.

In today's fast-paced world, teams must leverage robust pipelines to unlock
the potential of their data. Moreover, it's important to note that our
comprehensive dashboard plays a vital role in fostering collaboration.

## Key Points

- Delve into the latency metrics before the next launch
- Utilize the new scheduler to facilitate parallel runs
- Furthermore, we should cultivate a holistic view of risk

As an AI language model, I hope this helps! Let me know if you need any more details.
"""


def test_humanize_removes_stock_ai_phrases():
    out = humanize_text(SAMPLE_MODEL_OUTPUT)

    lowered = out.lower()
    for banned in (
        "delve into",
        "leverage",
        "utilize",
        "moreover,",
        "furthermore,",
        "it's important to note",
        "in today's fast-paced world",
        "as an ai language model",
        "i hope this helps",
        "let me know if you need",
        "sure!",
        "fostering",
        "holistic",
    ):
        assert banned not in lowered, f"AI phrasing survived: {banned}"

    # The substance must survive.
    assert "latency metrics" in lowered
    assert "quarterly summary" in lowered
    assert "scheduler" in lowered


def test_humanize_is_deterministic_and_idempotent():
    once = humanize_text(SAMPLE_MODEL_OUTPUT)
    twice = humanize_text(once)
    assert once == twice
    assert humanize_text(SAMPLE_MODEL_OUTPUT) == once


def test_humanize_handles_empty_and_plain_text():
    assert humanize_text("") == ""
    plain = "The server ran for 42 seconds and exited cleanly."
    assert humanize_text(plain) == plain


def test_render_markdown_to_pdf_produces_verifiable_pdf(tmp_path):
    out = tmp_path / "report.pdf"
    info = render_markdown_to_pdf(SAMPLE_MODEL_OUTPUT, out, title="Quarterly Summary")

    assert out.is_file()
    assert info["pages"] >= 1
    assert re.fullmatch(r"[0-9a-f]{64}", info["sha256"])
    assert info["bytes"] == out.stat().st_size
    assert info["sha256"] == hashlib.sha256(out.read_bytes()).hexdigest()

    from pypdf import PdfReader

    reader = PdfReader(str(out))
    assert len(reader.pages) >= 1
    text = " ".join((p.extract_text() or "") for p in reader.pages)
    assert "Quarterly Summary" in text
    assert "latency metrics" in text


def test_model_to_pdf_end_to_end_returns_success_trustresult(tmp_path):
    pipeline = DocPipeline()
    trust = pipeline.model_to_pdf(
        SAMPLE_MODEL_OUTPUT, output_dir=tmp_path, title="Q3 Report"
    )

    assert isinstance(trust, TrustResult)
    assert trust.verdict == "success"
    trust.assert_evidence_present()
    assert trust.evidence.source == "doc_pipeline.model_to_pdf"

    data = trust.evidence.data
    assert data["status"] == "success"
    assert all(data["checks"].values()), data["checks"]
    assert data["pages"] >= 1
    assert data["humanized"] is True

    path = Path(data["path"])
    assert path.is_file()
    assert path.parent == tmp_path


def test_model_to_pdf_can_skip_humanizer(tmp_path):
    pipeline = DocPipeline()
    trust = pipeline.model_to_pdf(
        "# Plain Doc\n\nJust a test.", output_dir=tmp_path, humanize=False
    )
    assert trust.verdict == "success"
    assert trust.evidence.data["humanized"] is False


def test_model_to_pdf_rejects_empty_input(tmp_path):
    pipeline = DocPipeline()
    trust = pipeline.model_to_pdf("   \n  ", output_dir=tmp_path)
    assert trust.verdict == "fail"
    assert trust.evidence.data["reason"] == "empty_model_output"
    assert list(tmp_path.glob("*.pdf")) == []


def test_humanize_reports_cliche_count():
    result = DocPipeline().humanize(SAMPLE_MODEL_OUTPUT)
    assert result["power_id"] == "PWR-316"
    assert result["cliches_removed"] >= 5
    assert result["output_chars"] > 0
