"""JARVIS Generative UI Adapter.

Renders interactive HTML artifacts and UI components locally for independent
display on the JARVIS local dashboard without relying on IDE embeds.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional


class GenerativeUIAdapter:
    """Renders and manages standalone HTML UI widgets."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or (Path.cwd() / "web" / "static" / "widgets")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def render_widget(
        self, widget_id: str, html_content: str, title: str = "Widget"
    ) -> Dict[str, Any]:
        """Sanitizes HTML content, replaces external gstatic CDN with local CSS, and saves artifact."""
        # Replace external gstatic Tailwind CDN with local stylesheet
        sanitized_html = re.sub(
            r'<script[^>]*src=["\']https://www.gstatic.com/antigravity/[^"\']*["\'][^>]*></script>',
            '<link rel="stylesheet" href="/static/css/tailwind.min.css">',
            html_content,
            flags=re.IGNORECASE,
        )

        # Wrap in standard standalone HTML container if not already full document
        if "<html" not in sanitized_html.lower():
            full_html = (
                f"<!DOCTYPE html>\n"
                f"<html lang='en'>\n"
                f"<head>\n"
                f"  <meta charset='UTF-8'>\n"
                f"  <title>{title}</title>\n"
                f"  <link rel='stylesheet' href='/static/css/tailwind.min.css'>\n"
                f"</head>\n"
                f"<body class='bg-slate-900 text-slate-100 p-4 font-sans'>\n"
                f"  <div class='border border-slate-700 rounded-xl p-4 bg-slate-800 shadow-lg'>\n"
                f"    {sanitized_html}\n"
                f"  </div>\n"
                f"</body>\n"
                f"</html>"
            )
        else:
            full_html = sanitized_html

        artifact_file = self.output_dir / f"{widget_id}.html"
        artifact_file.write_text(full_html, encoding="utf-8")

        return {
            "widget_id": widget_id,
            "file_path": str(artifact_file.resolve()),
            "local_url": f"http://localhost:8000/static/widgets/{widget_id}.html",
            "byte_size": len(full_html),
        }
