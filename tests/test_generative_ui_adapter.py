"""Unit tests for GenerativeUIAdapter."""

import tempfile
from pathlib import Path
from jarvis.tools.adapters.generative_ui_adapter import GenerativeUIAdapter


def test_generative_ui_local_rendering():
    with tempfile.TemporaryDirectory() as tmpdir:
        adapter = GenerativeUIAdapter(output_dir=Path(tmpdir))
        raw_snippet = (
            "<script src='https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js'></script>\n"
            "<div><h3>System Metrics</h3><p>VRAM: 4.2 GB / 6.0 GB</p></div>"
        )
        res = adapter.render_widget("system_metrics", raw_snippet, "System Metrics")

        assert Path(res["file_path"]).exists()
        saved_text = Path(res["file_path"]).read_text(encoding="utf-8")
        assert "gstatic.com" not in saved_text
        assert "/static/css/tailwind.min.css" in saved_text
        assert "System Metrics" in saved_text
        assert res["local_url"] == "http://localhost:8000/static/widgets/system_metrics.html"
