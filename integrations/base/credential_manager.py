"""
JARVIS Credential Manager
Provides secure, isolated credential retrieval, validation, and redaction.
Credentials are read strictly from environment variables or local secure vault.
Never commits secrets, never logs secrets in plaintext, and provides clear setup instructions when missing.
"""

import os
import re
from typing import Dict, Any, List, Optional, Tuple

class CredentialManager:
    """Manages credentials with zero leakage and actionable setup guides."""

    SETUP_GUIDES: Dict[str, Dict[str, Any]] = {
        "google": {
            "required_vars": ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"],
            "setup_url": "https://console.cloud.google.com/apis/credentials",
            "instructions": "Create an OAuth 2.0 Client ID in Google Cloud Console, enable Drive/Calendar/Gmail APIs, and export GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
        },
        "meta": {
            "required_vars": ["META_APP_ID", "META_APP_SECRET", "META_ACCESS_TOKEN"],
            "setup_url": "https://developers.facebook.com/apps/",
            "instructions": "Create a Meta Developer App, configure WhatsApp/Instagram Graph API, and generate a system user access token."
        },
        "openai": {
            "required_vars": ["OPENAI_API_KEY"],
            "setup_url": "https://platform.openai.com/api-keys",
            "instructions": "Generate an API key in your OpenAI account and export OPENAI_API_KEY."
        },
        "anthropic": {
            "required_vars": ["ANTHROPIC_API_KEY"],
            "setup_url": "https://console.anthropic.com/settings/keys",
            "instructions": "Generate an API key in your Anthropic Console and export ANTHROPIC_API_KEY."
        },
        "github": {
            "required_vars": ["GITHUB_PERSONAL_ACCESS_TOKEN"],
            "setup_url": "https://github.com/settings/tokens",
            "instructions": "Generate a GitHub Personal Access Token (classic or fine-grained) with repo/read scopes and export GITHUB_PERSONAL_ACCESS_TOKEN."
        },
        "docker": {
            "required_vars": ["DOCKER_HOST"],
            "setup_url": "https://docs.docker.com/engine/install/",
            "instructions": "Ensure Docker engine daemon is running locally (e.g., unix:///var/run/docker.sock or npipe:////./pipe/docker_engine)."
        },
        "home_assistant": {
            "required_vars": ["HASS_URL", "HASS_TOKEN"],
            "setup_url": "https://www.home-assistant.io/docs/authentication/",
            "instructions": "Create a Long-Lived Access Token in Home Assistant profile settings and provide HASS_URL and HASS_TOKEN."
        },
        "slack": {
            "required_vars": ["SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET"],
            "setup_url": "https://api.slack.com/apps",
            "instructions": "Create a Slack App with Bot scopes (chat:write, channels:read) and install to your workspace."
        }
    }

    def __init__(self, override_env: Optional[Dict[str, str]] = None):
        self._override_env = override_env or {}

    def get_credential(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Fetches credential from override store or environment."""
        if key in self._override_env:
            return self._override_env[key]
        return os.getenv(key, default)

    def set_override(self, key: str, value: str) -> None:
        """Sets a temporary in-memory override (useful for testing or runtime auth)."""
        self._override_env[key] = value

    def clear_override(self, key: str) -> None:
        self._override_env.pop(key, None)

    def validate_credentials(self, required_keys: List[str]) -> Tuple[bool, List[str]]:
        """
        Validates presence of required keys.
        Returns (is_valid, missing_keys_list).
        """
        missing = []
        for key in required_keys:
            val = self.get_credential(key)
            if not val or not val.strip():
                missing.append(key)
        return len(missing) == 0, missing

    def get_setup_guide(self, integration_id: str) -> Dict[str, Any]:
        """Returns actionable instructions when an integration is unconfigured."""
        return self.SETUP_GUIDES.get(integration_id, {
            "required_vars": [f"{integration_id.upper()}_API_KEY"],
            "setup_url": f"https://docs.jarvis.internal/integrations/{integration_id}",
            "instructions": f"Configure required environment variable {integration_id.upper()}_API_KEY in your .env file."
        })

    @staticmethod
    def mask_secret(secret: Optional[str]) -> str:
        """
        Sanitizes a secret string for safe logging or UI display.
        Example: 'sk-1234567890abcdef' -> 'sk-****cdef'
        """
        if not secret:
            return ""
        if len(secret) <= 8:
            return "****"
        prefix = secret[:3]
        suffix = secret[-4:]
        return f"{prefix}****{suffix}"

    def redact_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Deeply traverses and masks known credential fields."""
        sensitive_keys = {
            "key", "api_key", "secret", "token", "password", "auth",
            "private_key", "access_token", "client_secret"
        }
        redacted = {}
        for k, v in data.items():
            if any(s in k.lower() for s in sensitive_keys) and isinstance(v, str):
                redacted[k] = self.mask_secret(v)
            elif isinstance(v, dict):
                redacted[k] = self.redact_dict(v)
            elif isinstance(v, list):
                redacted[k] = [self.redact_dict(item) if isinstance(item, dict) else item for item in v]
            else:
                redacted[k] = v
        return redacted

# Global Credential Manager instance
credential_manager = CredentialManager()
