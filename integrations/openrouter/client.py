"""
OpenRouter Client for JARVIS.
Provides native access to OpenRouter's free router (openrouter/free) and free model ecosystem
(Gemma, Nemotron, LFM, Laguna, Cohere, etc.) with streaming, reasoning token extraction,
and automatic rate-limit fallback.
Reference: https://openrouter.ai/openrouter/free & https://github.com/mnfst/awesome-free-llm-apis
"""

import os
import time
import json
from typing import Dict, Any, List, Optional, AsyncIterator, Iterator
import httpx
from pydantic import BaseModel, Field

from jarvis.config import settings
from jarvis.core.logger import get_logger

logger = get_logger("openrouter_client")


class OpenRouterUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    reasoning_tokens: Optional[int] = 0
    cost: float = 0.0


class OpenRouterResponse(BaseModel):
    id: str
    model: str
    provider: Optional[str] = None
    content: str
    reasoning: Optional[str] = None
    usage: OpenRouterUsage
    fallback_used: bool = False
    raw: Dict[str, Any] = Field(default_factory=dict)


class OpenRouterClient:
    """High-performance OpenRouter client tailored for zero-cost and reasoning models."""

    DEFAULT_FREE_FALLBACKS = [
        "openrouter/free",
        "liquid/lfm-2.5-2.6b:free",
        "google/gemma-4-26b-a4b-it:free",
        "google/gemma-4-31b-it:free",
        "nvidia/nemotron-3.5-lightning:free",
        "cohere/north-mini-code:free",
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout: float = 45.0,
    ):
        self.api_key = api_key or getattr(settings, "openrouter_api_key", None) or os.environ.get("OPENROUTER_API_KEY", "")
        self.base_url = (base_url or getattr(settings, "openrouter_base_url", "https://openrouter.ai/api/v1")).rstrip("/")
        self.default_model = default_model or getattr(settings, "openrouter_default_model", "openrouter/free")
        self.timeout = timeout
        self._cached_free_models: List[str] = []
        self._cache_time: float = 0.0

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "HTTP-Referer": getattr(settings, "openrouter_site_url", "https://github.com/GaneshNair007/Jarvis"),
            "X-Title": getattr(settings, "openrouter_app_title", "JARVIS AI OS"),
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def get_free_models(self, force_refresh: bool = False) -> List[str]:
        """Queries the live OpenRouter catalog and returns all zero-cost models."""
        now = time.time()
        ttl = getattr(settings, "openrouter_models_cache_ttl_sec", 3600)
        if not force_refresh and self._cached_free_models and (now - self._cache_time < ttl):
            return self._cached_free_models

        try:
            http_timeout = getattr(settings, "openrouter_http_timeout_sec", 15.0)
            with httpx.Client(timeout=http_timeout) as client:
                res = client.get(f"{self.base_url}/models")
                if res.status_code == 200:
                    data = res.json().get("data", [])
                    free = [
                        m["id"]
                        for m in data
                        if m.get("id", "").endswith(":free")
                        or (
                            float(m.get("pricing", {}).get("prompt", 1)) == 0
                            and float(m.get("pricing", {}).get("completion", 1)) == 0
                        )
                    ]
                    if "openrouter/free" not in free:
                        free.append("openrouter/free")
                    self._cached_free_models = free
                    self._cache_time = now
                    return free
        except Exception as e:
            logger.warning("Failed to refresh live OpenRouter free catalog: %s", e)

        return self.DEFAULT_FREE_FALLBACKS

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_retries: int = 3,
        enable_fallbacks: bool = True,
    ) -> OpenRouterResponse:
        """
        Executes a chat completion call with automatic rate-limit retry and fallback pool.
        Extracts content, reasoning traces, and token usage metrics.
        """
        target_model = model or self.default_model
        candidate_models = [target_model]
        if enable_fallbacks:
            for fb in self.DEFAULT_FREE_FALLBACKS:
                if fb not in candidate_models:
                    candidate_models.append(fb)

        last_error = None
        for candidate in candidate_models:
            for attempt in range(max_retries):
                try:
                    payload = {
                        "model": candidate,
                        "messages": messages,
                        "provider": {
                            "data_collection": "allow",
                            "allow_fallbacks": True,
                        },
                    }
                    with httpx.Client(timeout=self.timeout) as client:
                        resp = client.post(
                            f"{self.base_url}/chat/completions",
                            headers=self._get_headers(),
                            json=payload,
                        )

                        if resp.status_code == 200:
                            data = resp.json()
                            choice = data.get("choices", [{}])[0]
                            msg = choice.get("message", {})
                            content = msg.get("content", "")
                            reasoning = msg.get("reasoning")
                            usage_data = data.get("usage", {})
                            token_details = usage_data.get("completion_tokens_details", {})
                            reasoning_tokens = token_details.get("reasoning_tokens")

                            usage = OpenRouterUsage(
                                prompt_tokens=usage_data.get("prompt_tokens", 0),
                                completion_tokens=usage_data.get("completion_tokens", 0),
                                total_tokens=usage_data.get("total_tokens", 0),
                                reasoning_tokens=reasoning_tokens,
                                cost=usage_data.get("cost", 0.0),
                            )

                            return OpenRouterResponse(
                                id=data.get("id", ""),
                                model=data.get("model", candidate),
                                provider=data.get("provider"),
                                content=content,
                                reasoning=reasoning,
                                usage=usage,
                                fallback_used=(candidate != target_model),
                                raw=data,
                            )

                        elif resp.status_code in (429, 502, 503, 504):
                            logger.warning(
                                "Model %s attempt %d returned HTTP %d: %s",
                                candidate,
                                attempt + 1,
                                resp.status_code,
                                resp.text[:180],
                            )
                            time.sleep(1.0 * (2 ** attempt))
                            continue
                        else:
                            last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                            logger.error("OpenRouter request failed for %s: %s", candidate, last_error)
                            break
                except Exception as e:
                    last_error = str(e)
                    logger.warning("OpenRouter exception on %s (attempt %d): %s", candidate, attempt + 1, e)
                    time.sleep(1.0)

        raise RuntimeError(f"OpenRouter free chat completion failed after trying candidates {candidate_models}. Last error: {last_error}")

    def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
    ) -> Iterator[Dict[str, Any]]:
        """
        Synchronous streaming generator yielding delta chunks.
        Extracts content deltas and final usage/reasoning metadata.
        """
        target_model = model or self.default_model
        payload = {
            "model": target_model,
            "messages": messages,
            "stream": True,
            "provider": {
                "data_collection": "allow",
                "allow_fallbacks": True,
            },
        }

        with httpx.Client(timeout=self.timeout) as client:
            with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._get_headers(),
                json=payload,
            ) as response:
                if response.status_code != 200:
                    err_body = response.read().decode("utf-8")
                    raise RuntimeError(f"OpenRouter streaming error {response.status_code}: {err_body}")

                for line in response.iter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[len("data: "):].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            yield chunk
                        except json.JSONDecodeError:
                            continue


# Global client instance
openrouter_client = OpenRouterClient()
