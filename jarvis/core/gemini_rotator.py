"""JARVIS Gemini Multi-Account API Key Rotator.

Distributes inference requests across up to three independent Google Gemini Pro / Flash
developer accounts to maximize free-tier throughput and eliminate rate-limit throttling (HTTP 429).
Supports seamless fallback when keys are unconfigured.
"""

from __future__ import annotations

import itertools
import os
import time
from typing import Any, Dict, List, Optional
from jarvis.config import settings
from jarvis.core.logger import get_logger

logger = get_logger("core.gemini_rotator")


class GeminiKeyRotator:
    """Manages load-balanced rotation across multiple Gemini developer accounts."""

    def __init__(self):
        # Collect keys from environment or settings
        raw_keys = [
            os.getenv("GEMINI_KEY_ACCOUNT_1") or os.getenv("GEMINI_KEY_1") or getattr(settings, "gemini_api_key", None),
            os.getenv("GEMINI_KEY_ACCOUNT_2") or os.getenv("GEMINI_KEY_2"),
            os.getenv("GEMINI_KEY_ACCOUNT_3") or os.getenv("GEMINI_KEY_3"),
            os.getenv("GEMINI_API_KEY"),
        ]
        # De-duplicate while preserving order
        seen = set()
        self.valid_keys: List[str] = []
        for k in raw_keys:
            if k and k.strip() and k not in seen:
                seen.add(k)
                self.valid_keys.append(k.strip())

        self.key_cycle = itertools.cycle(self.valid_keys) if self.valid_keys else None
        logger.info(f"GeminiKeyRotator initialized with {len(self.valid_keys)} active account key(s).")

    @property
    def is_available(self) -> bool:
        """Returns True if at least one valid Gemini API key is configured."""
        return len(self.valid_keys) > 0

    def get_next_key(self) -> Optional[str]:
        """Cycles to the next available account key."""
        if not self.key_cycle:
            return None
        return next(self.key_cycle)

    def generate_chat_completion(
        self,
        prompt: str,
        system_instruction: str = "You are JARVIS, an autonomous personal AI assistant.",
        model: str = "gemini-2.0-flash",
    ) -> Optional[Dict[str, Any]]:
        """
        Calls Gemini API with automatic rotation on HTTP 429 (Rate Limit).
        Uses google-genai or httpx / urllib fallback.
        """
        if not self.is_available:
            return None

        import urllib.request
        import json

        attempts = len(self.valid_keys)
        start_time = time.time()

        for _ in range(attempts):
            api_key = self.get_next_key()
            if not api_key:
                break

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
            payload = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}],
                "systemInstruction": {"parts": [{"text": system_instruction}]},
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1024},
            }).encode("utf-8")

            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=12.0) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        text = (
                            data.get("candidates", [{}])[0]
                            .get("content", {})
                            .get("parts", [{}])[0]
                            .get("text", "")
                        )
                        return {
                            "status": "success",
                            "model": f"google/{model}",
                            "reply": text,
                            "duration_ms": round((time.time() - start_time) * 1000, 2),
                        }
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    logger.warning(f"Gemini API rate-limit (429) hit on key {api_key[:6]}... Cycling to next account.")
                    continue
                else:
                    logger.error(f"Gemini API HTTP Error {e.code}: {e.read().decode('utf-8', errors='ignore')}")
                    break
            except Exception as e:
                logger.warning(f"Gemini connection error: {e}")
                break

        return None


gemini_rotator = GeminiKeyRotator()

