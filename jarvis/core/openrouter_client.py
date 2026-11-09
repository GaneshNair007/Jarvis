"""JARVIS OpenRouter Frontier Gateway Client.

Provides direct access to frontier models (DeepSeek-Chat, LLaMA-3, Mistral, etc.)
via OpenRouter API with zero-overhead standard library HTTP requests,
automatic retry, and full context pass-through.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional
from jarvis.config import settings
from jarvis.core.logger import get_logger

logger = get_logger("core.openrouter")


class OpenRouterClient:
    """Production client for OpenRouter AI Gateway."""

    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY") or getattr(settings, "openrouter_api_key", None)
        self.base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        self.default_model = os.getenv("OPENROUTER_DEFAULT_MODEL", "deepseek/deepseek-chat")
        self.site_url = getattr(settings, "openrouter_site_url", "https://github.com/GaneshNair007/Jarvis")
        self.site_title = getattr(settings, "openrouter_app_title", "JARVIS AI Assistant")

    @property
    def is_available(self) -> bool:
        """Returns True if a valid OpenRouter API key is configured."""
        return bool(self.api_key and self.api_key.startswith("sk-or-v1-"))

    def generate_completion(
        self,
        prompt: str,
        system_instruction: str = "You are JARVIS, an autonomous personal AI assistant created for Ganesh Nair. Reply concisely with your signature Iron Man tone.",
        model: Optional[str] = None,
        timeout_sec: float = 20.0,
    ) -> Optional[Dict[str, Any]]:
        """Generates chat completion from OpenRouter."""
        if not self.is_available or not prompt:
            return None

        # Zero-Leak Cloud Egress Sanitization (FAIL-CLOSED)
        try:
            from jarvis.security.ten_layer_shield import jarvis_security_suite

            prompt = jarvis_security_suite.sanitize_outbound_prompt(prompt)
            if system_instruction:
                system_instruction = jarvis_security_suite.sanitize_outbound_prompt(system_instruction)
        except Exception as _sec_err:
            logger.critical(f"OpenRouter egress firewall halted call: {_sec_err}")
            raise RuntimeError(f"Cloud egress blocked by Zero-Leak Firewall: {_sec_err}") from _sec_err

        target_model = model or self.default_model
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.site_url,
            "X-Title": self.site_title,
        }

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
                    choice = data.get("choices", [{}])[0]
                    reply_text = choice.get("message", {}).get("content", "").strip()
                    tokens = data.get("usage", {}).get("total_tokens", len(prompt) // 4 + len(reply_text) // 4)

                    duration_ms = round((time.time() - start_time) * 1000, 2)
                    logger.info(f"OpenRouter inference succeeded via {target_model} in {duration_ms}ms")
                    return {
                        "status": "success",
                        "model": target_model,
                        "reply": reply_text,
                        "tokens_used": tokens,
                        "duration_ms": duration_ms,
                    }
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            logger.error(f"OpenRouter HTTP Error {e.code}: {err_body}")
            # If 404 on model, attempt fallback to deepseek-chat
            if e.code == 404 and target_model != "deepseek/deepseek-chat":
                return self.generate_completion(
                    prompt, system_instruction, model="deepseek/deepseek-chat", timeout_sec=timeout_sec
                )
        except Exception as e:
            logger.warning(f"OpenRouter request error: {e}")

        return None


openrouter_client = OpenRouterClient()
