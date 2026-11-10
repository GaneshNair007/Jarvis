"""JARVIS FreeLLMAPI Gateway Client.

Provides direct access to 299+ free AI models via the local FreeLLMAPI gateway
running at http://localhost:3001 with zero token cost and OpenAI compatibility.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional
from jarvis.core.logger import get_logger

logger = get_logger("core.freellmapi")

DEFAULT_FREELLMAPI_KEY = "freellmapi-bbe4d824646ec4bca5903eeb1060d788eec976b612e2b48a"
DEFAULT_FREELLMAPI_URL = "http://localhost:3001/v1"


class FreeLLMAPIClient:
    """Production client for local FreeLLMAPI Gateway."""

    def __init__(self):
        self.api_key = os.getenv("FREELLMAPI_KEY", DEFAULT_FREELLMAPI_KEY)
        self.base_url = os.getenv("FREELLMAPI_BASE_URL", DEFAULT_FREELLMAPI_URL).rstrip("/")
        self.default_model = os.getenv("FREELLMAPI_DEFAULT_MODEL", "auto")
        self._cached_available: Optional[bool] = None
        self._last_probe_time: float = 0.0

    @property
    def is_available(self) -> bool:
        """Checks if the local FreeLLMAPI router at localhost:3001 is active."""
        now = time.time()
        if self._cached_available is not None and (now - self._last_probe_time) < 10.0:
            return self._cached_available

        try:
            req = urllib.request.Request(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                self._cached_available = (resp.status == 200)
        except Exception:
            self._cached_available = False

        self._last_probe_time = now
        return self._cached_available

    def generate_completion(
        self,
        prompt: str,
        system_instruction: str = "You are JARVIS, an autonomous personal AI assistant created for Ganesh Nair. Reply concisely with precision, citations, and actionable guidance.",
        model: Optional[str] = None,
        timeout_sec: float = 20.0,
    ) -> Optional[Dict[str, Any]]:
        """Generates chat completion from local FreeLLMAPI."""
        if not prompt:
            return None

        # Zero-Leak Cloud Egress Sanitization (FAIL-CLOSED)
        try:
            from jarvis.security.ten_layer_shield import jarvis_security_suite
            prompt = jarvis_security_suite.sanitize_outbound_prompt(prompt)
            if system_instruction:
                system_instruction = jarvis_security_suite.sanitize_outbound_prompt(system_instruction)
        except Exception as _sec_err:
            logger.critical(f"FreeLLMAPI egress firewall halted call: {_sec_err}")
            raise RuntimeError(f"Cloud egress blocked by Zero-Leak Firewall: {_sec_err}") from _sec_err

        candidate_models = [model or self.default_model, "qwen/qwen3.8-27b", "gpt-oss-20b", "deepseek/deepseek-chat"]
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        start = time.time()
        for cand in candidate_models:
            payload = json.dumps({
                "model": cand,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 1024,
                "temperature": 0.3,
            }).encode("utf-8")

            try:
                req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    reply = data["choices"][0]["message"]["content"]
                    tokens_used = data.get("usage", {}).get("total_tokens", len(prompt) // 4 + len(reply) // 4)
                    duration_ms = round((time.time() - start) * 1000, 2)
                    return {
                        "reply": reply,
                        "model": data.get("model", cand),
                        "tokens_used": tokens_used,
                        "duration_ms": duration_ms,
                        "provider": "freellmapi",
                    }
            except Exception as e:
                logger.debug(f"FreeLLMAPI candidate {cand} failed: {e}; trying fallback model.")

        return None


freellmapi_client = FreeLLMAPIClient()

__all__ = ["FreeLLMAPIClient", "freellmapi_client"]
