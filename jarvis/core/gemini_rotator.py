"""JARVIS Gemini Multi-Account API Key Rotator (Compatibility Re-export).

Maintains backward-compatibility while routing to the unified multi-account
APIKeyRotator architecture in `jarvis.core.api_key_rotator`.
"""

from jarvis.core.api_key_rotator import GeminiKeyRotator, gemini_rotator

__all__ = ["GeminiKeyRotator", "gemini_rotator"]
