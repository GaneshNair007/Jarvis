"""JARVIS FreeLLMAPI Local Gateway Client.

Provides direct access to 299+ free AI models (DeepSeek, Qwen, LLaMA, etc.)
via the local FreeLLMAPI router running at http://localhost:3001 with zero-overhead
standard library HTTP requests, automatic health-check detection, and fail-safe fallbacks.
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


class FreeLLMAPIClient:
    """Production client for local FreeLLMAPI multi-model router."""

    def __init__(self):
        self.base_url = os.getenv("FREELLMAPI_BASE_URL", "http://localhost:3001/v1")
        self.api_key = os.getenv("FREELLMAPI_KEY", "")
        self.default_model = os.getenv("FREELLMAPI_DEFAULT_MODEL", "auto")
        self._is_online_cache: Optional[bool] = None
        self._last_health_check: float = 0.0

    @property
    def is_available(self) -> bool:
        """Checks if the local FreeLLMAPI router on port 3001 is reachable."""
        now = time.time()
        if self._is_online_cache is not None and (now - self._last_health_check) < 10.0:
            return self._is_online_cache

        try:
            req = urllib.request.Request(
                f"{self.base_url.rstrip('/')}/models",
                headers={"User-Agent": "Jarvis-Agent/1.0"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                self._is_online_cache = resp.status in (200, 401)
        except Exception:
            self._is_online_cache = False

        self._last_health_check = now
        return self._is_online_cache

    def generate_completion(
        self,
        prompt: str,
        system_instruction: str = "You are JARVIS, an autonomous personal AI assistant created for Ganesh Nair. Reply concisely.",
        model: Optional[str] = None,
        timeout_sec: float = 15.0,
    ) -> Optional[Dict[str, Any]]:
        """Generates chat completion from the local FreeLLMAPI router."""
        if not prompt:
            return None

        # Zero-Leak Cloud Egress Sanitization (FAIL-CLOSED)
        try:
            from jarvis.security.ten_layer_shield import jarvis_security_suite

            prompt = jarvis_security_suite.sanitize_outbound_prompt(prompt)
            if system_instruction:
                system_instruction = jarvis_security_suite.sanitize_outbound_prompt(system_instruction)
        except Exception as sec_err:
            logger.critical(f"FreeLLMAPI egress firewall halted call: {sec_err}")
            raise RuntimeError(f"Cloud egress blocked by Zero-Leak Firewall: {sec_err}") from sec_err

        target_model = model or self.default_model
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Jarvis-Agent/1.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = json.dumps(
            {
                "model": target_model,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 1024,
            }
        ).encode("utf-8")

        start_time = time.time()
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    choices = data.get("choices", [])
                    reply_text = choices[0].get("message", {}).get("content", "").strip() if choices else ""
                    tokens = data.get("usage", {}).get("total_tokens", len(prompt) // 4 + len(reply_text) // 4)
                    duration_ms = round((time.time() - start_time) * 1000, 2)
                    routed_model = data.get("model", target_model)

                    logger.info(f"FreeLLMAPI inference succeeded via {routed_model} in {duration_ms}ms")
                    return {
                        "status": "success",
                        "model": routed_model,
                        "reply": reply_text,
                        "tokens_used": tokens,
                        "duration_ms": duration_ms,
                    }
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            logger.warning(f"FreeLLMAPI HTTP Error {e.code}: {err_body}")
        except Exception as e:
            logger.warning(f"FreeLLMAPI request error: {e}")

        return None


freellmapi_client = FreeLLMAPIClient()
