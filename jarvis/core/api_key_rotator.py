"""
JARVIS Multi-Account API Key Rotator & Resilient Cloud Gateway.

Orchestrates multi-account API key multiplexing across Google Gemini (Pro/Flash)
and OpenRouter developer accounts to maximize free-tier throughput, eliminate
rate-limit bottlenecks (HTTP 429), and provide zero-financial-cost continuous reasoning.
"""

from __future__ import annotations

import itertools
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from jarvis.config import settings
from jarvis.core.logger import get_logger

logger = get_logger("core.api_key_rotator")


class KeyHealth:
    """Tracks performance, usage metrics, and rate-limiting health per API key."""

    def __init__(self, key: str, provider: str = "generic"):
        self.key = key.strip()
        self.provider = provider
        self.total_requests: int = 0
        self.successful_requests: int = 0
        self.rate_limit_429_count: int = 0
        self.error_count: int = 0
        self.consecutive_failures: int = 0
        self.cooldown_until: float = 0.0
        self.last_used_timestamp: float = 0.0
        self.created_at: float = time.time()

    @property
    def redacted_key(self) -> str:
        """Safe display string masking the secret."""
        if len(self.key) <= 8:
            return "***"
        return f"{self.key[:4]}...{self.key[-4:]}"

    def is_available(self, now: Optional[float] = None) -> bool:
        """Returns True if the key is not in active rate-limit cooldown."""
        current = now if now is not None else time.time()
        return current >= self.cooldown_until

    def record_success(self) -> None:
        """Records a successful API response."""
        self.total_requests += 1
        self.successful_requests += 1
        self.consecutive_failures = 0
        self.last_used_timestamp = time.time()

    def record_429(self, cooldown_seconds: float = 60.0) -> None:
        """Enforces a temporary cooldown following an HTTP 429 response."""
        now = time.time()
        self.total_requests += 1
        self.rate_limit_429_count += 1
        self.consecutive_failures += 1
        self.cooldown_until = now + cooldown_seconds
        self.last_used_timestamp = now
        logger.warning(
            f"Key {self.redacted_key} for {self.provider} rate-limited (429). "
            f"Cooldown active for {cooldown_seconds:.1f}s."
        )

    def record_error(self) -> None:
        """Records a general network/HTTP error."""
        self.total_requests += 1
        self.error_count += 1
        self.consecutive_failures += 1
        self.last_used_timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Telemetry representation."""
        now = time.time()
        return {
            "key": self.redacted_key,
            "provider": self.provider,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "rate_limit_429_count": self.rate_limit_429_count,
            "error_count": self.error_count,
            "consecutive_failures": self.consecutive_failures,
            "in_cooldown": not self.is_available(now),
            "cooldown_remaining_sec": max(0.0, round(self.cooldown_until - now, 2)),
            "last_used_sec_ago": max(0.0, round(now - self.last_used_timestamp, 2))
            if self.last_used_timestamp
            else None,
        }

    def __repr__(self) -> str:
        return f"<KeyHealth {self.provider}:{self.redacted_key} ok={self.successful_requests} 429={self.rate_limit_429_count}>"


class BaseKeyRotator:
    """Base class for round-robin rotation across multiple API credentials."""

    def __init__(self, provider: str, keys: Optional[List[str]] = None):
        self.provider = provider
        self.keys: List[str] = []
        self._trackers: Dict[str, KeyHealth] = {}
        self._current_idx: int = 0

        if keys:
            for k in keys:
                self.add_key(k)

    def add_key(self, key: str) -> bool:
        """Registers a new key if non-empty and not already present."""
        if not key or not key.strip():
            return False
        clean = key.strip()
        if clean in self._trackers:
            return False
        self.keys.append(clean)
        self._trackers[clean] = KeyHealth(clean, provider=self.provider)
        return True

    @property
    def is_available(self) -> bool:
        """True if at least one valid key is registered."""
        return len(self.keys) > 0

    @property
    def key_count(self) -> int:
        return len(self.keys)

    def get_next_key(self, enforce_cooldown: bool = True) -> Optional[str]:
        """
        Retrieves the next available key via round-robin.
        If enforce_cooldown is True, selects the next key not currently in 429 cooldown.
        If all keys are cooled down, falls back to the key whose cooldown expires earliest.
        """
        if not self.keys:
            return None

        now = time.time()
        total = len(self.keys)

        # 1. Look for next healthy key in round-robin order
        for i in range(total):
            idx = (self._current_idx + i) % total
            candidate = self.keys[idx]
            tracker = self._trackers[candidate]
            if not enforce_cooldown or tracker.is_available(now):
                self._current_idx = (idx + 1) % total
                return candidate

        # 2. If all keys are rate-limited and cooldown enforced, select key with soonest cooldown
        earliest_key = min(self.keys, key=lambda k: self._trackers[k].cooldown_until)
        return earliest_key

    def get_tracker(self, key: str) -> Optional[KeyHealth]:
        return self._trackers.get(key)

    def get_metrics(self) -> Dict[str, Any]:
        """Returns structured health telemetry for all configured keys."""
        return {
            "provider": self.provider,
            "total_keys": len(self.keys),
            "keys": [tracker.to_dict() for tracker in self._trackers.values()],
        }

    def reset_metrics(self) -> None:
        """Resets all metrics counters for diagnostic testing."""
        for tracker in self._trackers.values():
            tracker.total_requests = 0
            tracker.successful_requests = 0
            tracker.rate_limit_429_count = 0
            tracker.error_count = 0
            tracker.consecutive_failures = 0
            tracker.cooldown_until = 0.0


class GeminiKeyRotator(BaseKeyRotator):
    """
    Multi-account load-balancing rotator for Google Gemini (Pro/Flash).
    Supports up to 3+ independent developer accounts (e.g. GEMINI_KEY_ACCOUNT_1,
    GEMINI_KEY_ACCOUNT_2, GEMINI_KEY_ACCOUNT_3, GEMINI_API_KEYS, GEMINI_API_KEY).
    Automatically fails over on HTTP 429 with exponential backoff.
    """

    def __init__(self, keys: Optional[List[str]] = None):
        super().__init__(provider="gemini")
        self.clients: Dict[str, Any] = {}
        self.key_cycle = None
        if keys:
            for k in keys:
                self.add_key(k)
        else:
            self._discover_keys()
        self._sync_blueprint_state()

    @property
    def valid_keys(self) -> List[str]:
        """Returns all non-empty configured keys per architectural blueprint."""
        return [k for k in self.keys if k]

    def _sync_blueprint_state(self) -> None:
        """Synchronizes key_cycle and clients map per architectural blueprint."""
        self.key_cycle = itertools.cycle(self.valid_keys) if self.valid_keys else None
        try:
            from google import genai

            for k in self.valid_keys:
                if k not in self.clients:
                    try:
                        self.clients[k] = genai.Client(api_key=k)
                    except Exception:
                        pass
        except ImportError:
            pass

    def add_key(self, key: str) -> bool:
        added = super().add_key(key)
        if added:
            self._sync_blueprint_state()
        return added

    def get_client(self) -> Any:
        """
        Cycles to next available key client to distribute request load per architectural blueprint.
        Gracefully provides adapter if google-genai is not installed in the local environment.
        """
        if not self.valid_keys:
            raise ValueError("No valid Gemini API keys configured in environment.")

        selected_key = self.get_next_key() or (next(self.key_cycle) if self.key_cycle else None)
        if not selected_key:
            raise ValueError("No valid Gemini API keys configured in environment.")

        if selected_key in self.clients:
            return self.clients[selected_key]

        try:
            from google import genai

            client = genai.Client(api_key=selected_key)
            self.clients[selected_key] = client
            return client
        except Exception:
            # High-fidelity fallback client adapter providing .models.generate_content
            class _ModelsAdapter:
                def __init__(models_self, rotator: GeminiKeyRotator, k: str):
                    models_self.rotator = rotator
                    models_self.k = k

                def generate_content(models_self, model: str, contents: Any, config: Any = None) -> Any:
                    prompt_str = contents if isinstance(contents, str) else json.dumps(contents)
                    res = models_self.rotator.generate_chat_completion(prompt_str, model=model)
                    if not res or not res.get("reply"):
                        raise RuntimeError(f"Gemini API execution failed for model {model}")
                    reply_text = res["reply"]

                    class _GenAIResponse:
                        def __init__(self, text: str):
                            self.text = text
                            self.candidates = [{"content": {"parts": [{"text": text}]}}]

                        def __str__(self) -> str:
                            return self.text

                    return _GenAIResponse(reply_text)

            class _ClientAdapter:
                def __init__(adapter_self, rotator: GeminiKeyRotator, k: str):
                    adapter_self.key = k
                    adapter_self.models = _ModelsAdapter(rotator, k)

            return _ClientAdapter(self, selected_key)

    def generate_content_with_retry(self, contents: Any, config: Any = None, model: str = "gemini-2.0-flash") -> Any:
        """
        Executes API call with automatic key rotation upon rate-limit detection
        as strictly defined in the architectural blueprint.
        """
        if not self.valid_keys:
            raise ValueError("No valid Gemini API keys configured in environment.")

        for attempt in range(len(self.valid_keys)):
            client = self.get_client()
            used_key = getattr(client, "key", None) or self.valid_keys[attempt % len(self.valid_keys)]
            tracker = self._trackers.get(used_key)

            try:
                if hasattr(client, "models") and hasattr(client.models, "generate_content"):
                    response = client.models.generate_content(model=model, contents=contents, config=config)
                    if tracker:
                        tracker.record_success()
                    return response
            except Exception as e:
                err_code = getattr(e, "code", None)
                err_str = str(e).lower()
                is_429 = err_code == 429 or "429" in err_str or "resource_exhausted" in err_str or "quota" in err_str
                if is_429:
                    if tracker:
                        tracker.record_429(cooldown_seconds=60.0)
                    continue
                if tracker:
                    tracker.record_error()
                raise e

        raise RuntimeError("All configured Gemini API keys are currently rate-limited.")

    def _discover_keys(self) -> None:
        """Discovers keys from environment and settings."""
        discovered: List[str] = []

        # Account-based variables (Architectural blueprint)
        for var in [
            "GEMINI_KEY_ACCOUNT_1",
            "GEMINI_KEY_ACCOUNT_2",
            "GEMINI_KEY_ACCOUNT_3",
            "GEMINI_KEY_1",
            "GEMINI_KEY_2",
            "GEMINI_KEY_3",
        ]:
            val = os.getenv(var)
            if val and val.strip():
                discovered.append(val.strip())

        # Comma-separated multi-key string
        multi = os.getenv("GEMINI_API_KEYS") or getattr(settings, "gemini_api_keys", None)
        if multi and isinstance(multi, str):
            for part in multi.split(","):
                if part.strip():
                    discovered.append(part.strip())

        # Single key fallback
        single = os.getenv("GEMINI_API_KEY") or getattr(settings, "gemini_api_key", None)
        if single and isinstance(single, str) and single.strip():
            discovered.append(single.strip())

        for k in discovered:
            self.add_key(k)

        logger.info(f"GeminiKeyRotator initialized with {len(self.keys)} accounts.")

    def generate_chat_completion(
        self,
        prompt: str,
        system_instruction: str = "You are JARVIS, an autonomous personal AI assistant.",
        model: str = "gemini-2.0-flash",
        max_retries: Optional[int] = None,
        timeout_sec: float = 12.0,
        backoff_base_sec: float = 0.5,
    ) -> Optional[Dict[str, Any]]:
        """
        Executes inference with automatic key rotation and backoff on HTTP 429.
        """
        if not self.is_available:
            return None

        # Zero-Leak Cloud Egress Sanitization (FAIL-CLOSED)
        try:
            from jarvis.security.ten_layer_shield import jarvis_security_suite

            prompt = jarvis_security_suite.sanitize_outbound_prompt(prompt)
            if system_instruction:
                system_instruction = jarvis_security_suite.sanitize_outbound_prompt(system_instruction)
        except Exception as _sec_err:
            logger.critical(f"Gemini egress firewall blocked inference: {_sec_err}")
            raise RuntimeError(f"Cloud egress blocked by Zero-Leak Firewall: {_sec_err}") from _sec_err

        attempts = max_retries if max_retries is not None else max(len(self.keys) * 2, 2)
        start_time = time.time()

        for attempt in range(attempts):
            api_key = self.get_next_key()
            if not api_key:
                break

            tracker = self._trackers[api_key]

            # Try modern google-genai SDK first if available
            try:
                from google import genai
                from google.genai.errors import APIError

                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                )
                text = response.text if hasattr(response, "text") else str(response)
                tracker.record_success()
                return {
                    "status": "success",
                    "model": f"google/{model}",
                    "reply": text,
                    "key_used": tracker.redacted_key,
                    "duration_ms": round((time.time() - start_time) * 1000, 2),
                }
            except ImportError:
                pass  # Fall back to native HTTP
            except Exception as e:
                # Check for rate-limiting in genai SDK
                err_str = str(e).lower()
                is_429 = "429" in err_str or "resource_exhausted" in err_str or "quota" in err_str
                if is_429:
                    tracker.record_429(cooldown_seconds=60.0)
                    time.sleep(backoff_base_sec * (2 ** min(attempt, 3)))
                    continue
                else:
                    tracker.record_error()
                    logger.warning(f"Google GenAI SDK error: {e}")

            # Native HTTP fallback (robust urllib)
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
            payload = json.dumps(
                {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "systemInstruction": {"parts": [{"text": system_instruction}]},
                    "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1024},
                }
            ).encode("utf-8")

            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        tracker.record_success()
                        return {
                            "status": "success",
                            "model": f"google/{model}",
                            "reply": text,
                            "key_used": tracker.redacted_key,
                            "duration_ms": round((time.time() - start_time) * 1000, 2),
                        }
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    tracker.record_429(cooldown_seconds=60.0)
                    time.sleep(backoff_base_sec * (2 ** min(attempt, 3)))
                    continue
                elif e.code in (401, 403, 500, 502, 503, 504):
                    tracker.record_error()
                    logger.warning(
                        f"Gemini API HTTP Error {e.code} on key {tracker.redacted_key}. Rotating to next account."
                    )
                    time.sleep(backoff_base_sec)
                    continue
                else:
                    tracker.record_error()
                    logger.error(f"Gemini API HTTP Error {e.code}: {e.read().decode('utf-8', errors='ignore')}")
                    break
            except Exception as e:
                tracker.record_error()
                logger.warning(f"Gemini HTTP connection error: {e}")
                time.sleep(backoff_base_sec)

        return None


class OpenRouterKeyRotator(BaseKeyRotator):
    """
    Multi-key load-balancing rotator for OpenRouter AI Gateway.
    Multiplexes across multiple OpenRouter keys with automatic 429 failover.
    """

    def __init__(self, keys: Optional[List[str]] = None):
        super().__init__(provider="openrouter")
        self.base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        self.default_model = os.getenv("OPENROUTER_DEFAULT_MODEL", "deepseek/deepseek-chat")
        self.site_url = getattr(settings, "openrouter_site_url", "https://github.com/GaneshNair007/Jarvis")
        self.site_title = getattr(settings, "openrouter_app_title", "JARVIS AI OS")

        if keys:
            for k in keys:
                self.add_key(k)
        else:
            self._discover_keys()

    def _discover_keys(self) -> None:
        """Discovers keys from environment and settings."""
        discovered: List[str] = []

        # Comma-separated keys
        multi = os.getenv("OPENROUTER_API_KEYS") or getattr(settings, "openrouter_api_keys", None)
        if multi and isinstance(multi, str):
            for part in multi.split(","):
                if part.strip():
                    discovered.append(part.strip())

        # Numbered keys
        for var in ["OPENROUTER_KEY_1", "OPENROUTER_KEY_2", "OPENROUTER_KEY_3"]:
            val = os.getenv(var)
            if val and val.strip():
                discovered.append(val.strip())

        # Single primary key
        single = os.getenv("OPENROUTER_API_KEY") or getattr(settings, "openrouter_api_key", None)
        if single and isinstance(single, str) and single.strip():
            discovered.append(single.strip())

        for k in discovered:
            self.add_key(k)

        logger.info(f"OpenRouterKeyRotator initialized with {len(self.keys)} keys.")

    def generate_chat_completion(
        self,
        prompt: str,
        system_instruction: str = "You are JARVIS, an autonomous personal AI assistant created for Ganesh Nair. Reply concisely with your signature Iron Man tone.",
        model: Optional[str] = None,
        timeout_sec: float = 20.0,
        max_retries: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Generates chat completion with automatic failover across keys."""
        if not self.is_available or not prompt:
            return None

        # Zero-Leak Cloud Egress Sanitization (FAIL-CLOSED)
        try:
            from jarvis.security.ten_layer_shield import jarvis_security_suite

            prompt = jarvis_security_suite.sanitize_outbound_prompt(prompt)
            if system_instruction:
                system_instruction = jarvis_security_suite.sanitize_outbound_prompt(system_instruction)
        except Exception as _sec_err:
            logger.critical(f"Groq egress firewall blocked inference: {_sec_err}")
            raise RuntimeError(f"Cloud egress blocked by Zero-Leak Firewall: {_sec_err}") from _sec_err

        target_model = model or self.default_model
        attempts = max_retries if max_retries is not None else max(len(self.keys), 2)
        start_time = time.time()

        for attempt in range(attempts):
            api_key = self.get_next_key()
            if not api_key:
                break

            tracker = self._trackers[api_key]
            url = f"{self.base_url.rstrip('/')}/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
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
                    "max_tokens": int(os.getenv("OPENROUTER_MAX_TOKENS", "300")),
                }
            ).encode("utf-8")

            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        choice = data.get("choices", [{}])[0]
                        reply_text = choice.get("message", {}).get("content", "").strip()
                        tokens = data.get("usage", {}).get("total_tokens", len(prompt) // 4 + len(reply_text) // 4)
                        duration_ms = round((time.time() - start_time) * 1000, 2)
                        tracker.record_success()
                        return {
                            "status": "success",
                            "model": target_model,
                            "reply": reply_text,
                            "tokens_used": tokens,
                            "key_used": tracker.redacted_key,
                            "duration_ms": duration_ms,
                        }
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    tracker.record_429(cooldown_seconds=45.0)
                    continue
                elif e.code == 404 and target_model != "deepseek/deepseek-chat":
                    # Fall back to deepseek-chat on 404
                    return self.generate_chat_completion(
                        prompt, system_instruction, model="deepseek/deepseek-chat", timeout_sec=timeout_sec
                    )
                else:
                    tracker.record_error()
                    logger.error(f"OpenRouter HTTP Error {e.code}: {e.read().decode('utf-8', errors='ignore')}")
            except Exception as e:
                tracker.record_error()
                logger.warning(f"OpenRouter request error: {e}")

        return None


class GroqKeyRotator(BaseKeyRotator):
    """
    Key rotator for Groq Cloud free-tier ultra-fast LPU inference (500 tokens/sec).
    Supports llama-3.3-70b-versatile, qwen-2.5-32b, deepseek-r1-distill, and whisper-large-v3.
    """

    def __init__(self, default_model: str = "llama-3.3-70b-versatile"):
        super().__init__(provider="groq")
        self.default_model = default_model
        self.base_url = "https://api.groq.com/openai/v1"
        self._discover_keys()

    def _discover_keys(self):
        discovered = []
        raw_keys = os.getenv("GROQ_API_KEYS", "")
        if raw_keys:
            discovered.extend([k.strip() for k in raw_keys.split(",") if k.strip()])

        for var in ["GROQ_KEY_1", "GROQ_KEY_2", "GROQ_KEY_3"]:
            val = os.getenv(var)
            if val and val.strip():
                discovered.append(val.strip())

        single = os.getenv("GROQ_API_KEY")
        if single and isinstance(single, str) and single.strip():
            discovered.append(single.strip())

        for k in discovered:
            self.add_key(k)

        logger.info(f"GroqKeyRotator initialized with {len(self.keys)} keys.")

    def generate_chat_completion(
        self,
        prompt: str,
        system_instruction: str = "You are JARVIS, an autonomous personal AI assistant created for Ganesh Nair.",
        model: Optional[str] = None,
        timeout_sec: float = 15.0,
    ) -> Optional[Dict[str, Any]]:
        if not self.is_available or not prompt:
            return None

        # Zero-Leak Cloud Egress Sanitization (FAIL-CLOSED)
        try:
            from jarvis.security.ten_layer_shield import jarvis_security_suite

            prompt = jarvis_security_suite.sanitize_outbound_prompt(prompt)
            if system_instruction:
                system_instruction = jarvis_security_suite.sanitize_outbound_prompt(system_instruction)
        except Exception as _sec_err:
            logger.critical(f"Groq egress firewall blocked inference: {_sec_err}")
            raise RuntimeError(f"Cloud egress blocked by Zero-Leak Firewall: {_sec_err}") from _sec_err

        target_model = model or self.default_model
        start_time = time.time()

        for attempt in range(max(len(self.keys), 2)):
            api_key = self.get_next_key()
            if not api_key:
                break

            tracker = self._trackers[api_key]
            url = f"{self.base_url.rstrip('/')}/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = json.dumps(
                {
                    "model": target_model,
                    "messages": [
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.7,
                    "max_tokens": int(os.getenv("OPENROUTER_MAX_TOKENS", "300")),
                }
            ).encode("utf-8")

            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        choice = data.get("choices", [{}])[0]
                        reply_text = choice.get("message", {}).get("content", "").strip()
                        tokens = data.get("usage", {}).get("total_tokens", len(prompt) // 4 + len(reply_text) // 4)
                        duration_ms = round((time.time() - start_time) * 1000, 2)
                        tracker.record_success()
                        return {
                            "status": "success",
                            "model": target_model,
                            "reply": reply_text,
                            "tokens_used": tokens,
                            "key_used": tracker.redacted_key,
                            "duration_ms": duration_ms,
                        }
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    tracker.record_429(cooldown_seconds=30.0)
                    continue
                else:
                    tracker.record_error()
                    logger.error(f"Groq HTTP Error {e.code}")
            except Exception as e:
                tracker.record_error()
                logger.warning(f"Groq request error: {e}")

        return None


class NvidiaNimKeyRotator(BaseKeyRotator):
    """
    Multi-key load-balancing rotator for NVIDIA NIM (build.nvidia.com).
    OpenAI-compatible /v1/chat/completions endpoint; multiplexes across multiple
    NVIDIA_API_KEY credentials with automatic 429 failover.

    Key discovery precedence:
      1. NVIDIA_API_KEYS  (comma-separated multi-key)
      2. NVIDIA_KEY_1 .. NVIDIA_KEY_5 (numbered)
      3. NVIDIA_API_KEY   (single primary)
    """

    def __init__(self, keys: Optional[List[str]] = None):
        super().__init__(provider="nvidia_nim")
        self.base_url = os.getenv("NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")
        self.default_model = os.getenv("NVIDIA_DEFAULT_MODEL", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning")

        if keys:
            for k in keys:
                self.add_key(k)
        else:
            self._discover_keys()

    def _discover_keys(self) -> None:
        """Discovers keys from environment and settings (never logs raw values)."""
        discovered: List[str] = []

        # Comma-separated keys
        multi = os.getenv("NVIDIA_API_KEYS") or getattr(settings, "nvidia_api_keys", None)
        if multi and isinstance(multi, str):
            for part in multi.split(","):
                if part.strip():
                    discovered.append(part.strip())

        # Numbered keys
        for var in ["NVIDIA_KEY_1", "NVIDIA_KEY_2", "NVIDIA_KEY_3", "NVIDIA_KEY_4", "NVIDIA_KEY_5"]:
            val = os.getenv(var)
            if val and val.strip():
                discovered.append(val.strip())

        # Single primary key
        single = os.getenv("NVIDIA_API_KEY") or getattr(settings, "nvidia_api_key", None)
        if single and isinstance(single, str) and single.strip():
            discovered.append(single.strip())

        for k in discovered:
            self.add_key(k)

        logger.info(f"NvidiaNimKeyRotator initialized with {len(self.keys)} keys.")

    def generate_chat_completion(
        self,
        prompt: str,
        system_instruction: str = "You are JARVIS, an autonomous personal AI assistant created for Ganesh Nair. Reply concisely with your signature Iron Man tone.",
        model: Optional[str] = None,
        timeout_sec: float = 20.0,
        max_retries: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Generates chat completion via NVIDIA NIM with automatic failover across keys."""
        if not self.is_available or not prompt:
            return None

        # Zero-Leak Cloud Egress Sanitization (FAIL-CLOSED)
        try:
            from jarvis.security.ten_layer_shield import jarvis_security_suite

            prompt = jarvis_security_suite.sanitize_outbound_prompt(prompt)
            if system_instruction:
                system_instruction = jarvis_security_suite.sanitize_outbound_prompt(system_instruction)
        except Exception as _sec_err:
            logger.critical(f"NVIDIA egress firewall blocked inference: {_sec_err}")
            raise RuntimeError(f"Cloud egress blocked by Zero-Leak Firewall: {_sec_err}") from _sec_err

        target_model = model or self.default_model
        attempts = max_retries if max_retries is not None else max(len(self.keys), 2)
        start_time = time.time()

        for attempt in range(attempts):
            api_key = self.get_next_key()
            if not api_key:
                break

            tracker = self._trackers[api_key]
            url = f"{self.base_url.rstrip('/')}/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            payload = json.dumps(
                {
                    "model": target_model,
                    "messages": [
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.7,
                    "max_tokens": int(os.getenv("OPENROUTER_MAX_TOKENS", "300")),
                }
            ).encode("utf-8")

            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        choice = data.get("choices", [{}])[0]
                        message = choice.get("message", {}) or {}
                        # Reasoning models (e.g. nemotron-3) may place final text
                        # in content while streaming their chain in reasoning_content.
                        reply_text = (
                            (message.get("content") or "").strip()
                            or (message.get("reasoning_content") or "").strip()
                            or (choice.get("text") or "").strip()
                        )
                        tokens = data.get("usage", {}).get("total_tokens", len(prompt) // 4 + len(reply_text) // 4)
                        duration_ms = round((time.time() - start_time) * 1000, 2)
                        tracker.record_success()
                        return {
                            "status": "success",
                            "provider": "nvidia_nim",
                            "model": target_model,
                            "reply": reply_text,
                            "tokens_used": tokens,
                            "key_used": tracker.redacted_key,  # redacted only, never raw
                            "duration_ms": duration_ms,
                        }
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    tracker.record_429(cooldown_seconds=30.0)
                    continue
                else:
                    tracker.record_error()
                    logger.error(f"NVIDIA NIM HTTP Error {e.code} on key {tracker.redacted_key}. Rotating keys.")
            except Exception as e:
                tracker.record_error()
                logger.warning(f"NVIDIA NIM request error: {e}")

        return None


class APIKeyRotatorManager:
    """Unified manager aggregating all provider key rotators."""

    def __init__(self):
        self.gemini = GeminiKeyRotator()
        self.openrouter = OpenRouterKeyRotator()
        self.groq = GroqKeyRotator()
        self.nvidia_nim = NvidiaNimKeyRotator()

    @property
    def is_available(self) -> bool:
        return (
            self.gemini.is_available
            or self.openrouter.is_available
            or self.groq.is_available
            or self.nvidia_nim.is_available
        )

    def get_summary(self) -> Dict[str, Any]:
        """Telemetry summary across all providers."""
        return {
            "gemini": self.gemini.get_metrics(),
            "openrouter": self.openrouter.get_metrics(),
            "groq": self.groq.get_metrics(),
            "nvidia_nim": self.nvidia_nim.get_metrics(),
        }


# Global Singletons
api_key_rotator = APIKeyRotatorManager()
gemini_rotator = api_key_rotator.gemini
openrouter_rotator = api_key_rotator.openrouter
groq_rotator = api_key_rotator.groq
nvidia_nim_rotator = api_key_rotator.nvidia_nim
