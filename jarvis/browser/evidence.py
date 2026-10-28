"""Browser Evidence Subsystem.

Captures webpage screenshots, computes SHA-256 cryptographic checksums,
persists artifacts in the artifact vault, and logs receipts to the audit ledger.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any, Optional

from playwright.sync_api import Page

from jarvis.config import settings
from jarvis.core.audit import audit_ledger
from jarvis.core.logger import get_logger

logger = get_logger("browser.evidence")


class EvidenceStore:
    """Stores visual and textual receipts of browser automation actions."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or (settings.jarvis_artifact_dir / "screenshots")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def capture_screenshot(
        self,
        page: Page,
        task_id: str = "general",
        full_page: bool = False,
        audit: bool = True,
    ) -> dict[str, Any]:
        """Captures a screenshot, computes its SHA-256 hash, and logs the receipt.

        Args:
            page: Active Playwright Page instance.
            task_id: Associated task identifier.
            full_page: Whether to capture the entire scrollable height.
            audit: Whether to write an immutable receipt to the AuditLedger.

        Returns:
            dict: Metadata including file_path, sha256, url, title, and timestamp.
        """
        current_url = page.url or "about:blank"
        page_title = page.title() or "Untitled"
        timestamp = int(time.time() * 1000)

        # Capture PNG bytes directly into memory
        png_bytes = page.screenshot(full_page=full_page)
        sha256_hash = hashlib.sha256(png_bytes).hexdigest()

        # Deterministic filename: timestamp_hashprefix.png
        filename = f"{timestamp}_{sha256_hash[:12]}.png"
        file_path = self.output_dir / filename

        with open(file_path, "wb") as f:
            f.write(png_bytes)

        logger.info(f"Captured screenshot evidence for '{current_url}' -> {file_path.name} (SHA-256: {sha256_hash[:8]}...)")

        evidence_record = {
            "task_id": task_id,
            "url": current_url,
            "title": page_title,
            "file_path": str(file_path.resolve()),
            "sha256": sha256_hash,
            "size_bytes": len(png_bytes),
            "timestamp": timestamp,
        }

        if audit:
            audit_ledger.record(
                actor="browser_worker",
                action="screenshot_evidence",
                target=current_url,
                payload={"sha256": sha256_hash, "file": file_path.name, "task_id": task_id},
                result="SUCCESS",
            )

        return evidence_record
