"""
JARVIS Credential Manager
Provides secure, isolated credential retrieval, validation, and redaction.
Credentials are read strictly from environment variables or local secure vault.
Never commits secrets, never logs secrets in plaintext, and provides clear setup instructions when missing.
"""

import json
import os
import re
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


def dpapi_protect(data: bytes, description: str = "JARVIS protected secret") -> bytes:
    """Encrypt bytes with Windows DPAPI (current-user scope).

    DPAPI binds the ciphertext to the Windows user profile.  Copying the file
    to another account or machine does not reveal the plaintext.
    """
    try:
        import win32crypt
    except ImportError as exc:  # pragma: no cover - Windows-only dependency
        raise RuntimeError("Windows DPAPI is unavailable (pywin32 not installed)") from exc
    return win32crypt.CryptProtectData(data, description, None, None, None, 0)


def dpapi_unprotect(data: bytes) -> bytes:
    """Decrypt a Windows DPAPI blob created by :func:`dpapi_protect`."""
    try:
        import win32crypt
    except ImportError as exc:  # pragma: no cover - Windows-only dependency
        raise RuntimeError("Windows DPAPI is unavailable (pywin32 not installed)") from exc
    _description, plaintext = win32crypt.CryptUnprotectData(data, None, None, None, 0)
    return plaintext


class DpapiFileStore:
    """Atomic JSON store whose payload is encrypted with Windows DPAPI.

    Used for OAuth tokens.  The file never contains a plaintext refresh token,
    access token or client secret.
    """

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)

    def _path(self, name: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
        return self.base_dir / f"{safe}.bin"

    def save(self, name: str, payload: Dict[str, Any]) -> Path:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        plaintext = json.dumps(payload, sort_keys=True).encode("utf-8")
        ciphertext = dpapi_protect(plaintext, f"JARVIS secret: {name}")
        path = self._path(name)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
        try:
            with open(tmp, "wb") as fh:
                fh.write(ciphertext)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
        finally:
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
        return path

    def load(self, name: str) -> Optional[Dict[str, Any]]:
        path = self._path(name)
        if not path.exists():
            return None
        try:
            ciphertext = path.read_bytes()
            plaintext = dpapi_unprotect(ciphertext)
            data = json.loads(plaintext.decode("utf-8"))
            return data if isinstance(data, dict) else None
        except Exception:
            # Never log the ciphertext or decrypted payload.
            return None

    def delete(self, name: str) -> bool:
        path = self._path(name)
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return False


class CredentialManager:
    """Manages credentials with zero leakage and actionable setup guides."""

    SETUP_GUIDES: Dict[str, Dict[str, Any]] = {
        "google": {
            "required_vars": ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"],
            "setup_url": "https://console.cloud.google.com/apis/credentials",
            "instructions": "Create an OAuth 2.0 Client ID (Desktop app) in Google Cloud Console, enable the Gmail API, and export GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET. Never use a Google password or app password.",
        },
        "google_gmail": {
            "required_vars": ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"],
            "setup_url": "https://console.cloud.google.com/apis/credentials",
            "instructions": "Enable the Gmail API, create an OAuth 2.0 Client ID of type 'Desktop app', add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to .env, then run the JARVIS Google connection wizard to grant gmail.readonly, gmail.compose and gmail.send.",
        },
        "meta": {
            "required_vars": ["META_APP_ID", "META_APP_SECRET", "META_ACCESS_TOKEN"],
            "setup_url": "https://developers.facebook.com/apps/",
            "instructions": "Create a Meta Developer App, configure WhatsApp/Instagram Graph API, and generate a system user access token.",
        },
        "openai": {
            "required_vars": ["OPENAI_API_KEY"],
            "setup_url": "https://platform.openai.com/api-keys",
            "instructions": "Generate an API key in your OpenAI account and export OPENAI_API_KEY.",
        },
        "anthropic": {
            "required_vars": ["ANTHROPIC_API_KEY"],
            "setup_url": "https://console.anthropic.com/settings/keys",
            "instructions": "Generate an API key in your Anthropic Console and export ANTHROPIC_API_KEY.",
        },
        "github": {
            "required_vars": ["GITHUB_PERSONAL_ACCESS_TOKEN"],
            "setup_url": "https://github.com/settings/tokens",
            "instructions": "Generate a GitHub Personal Access Token (classic or fine-grained) with repo/read scopes and export GITHUB_PERSONAL_ACCESS_TOKEN.",
        },
        "docker": {
            "required_vars": ["DOCKER_HOST"],
            "setup_url": "https://docs.docker.com/engine/install/",
            "instructions": "Ensure Docker engine daemon is running locally (e.g., unix:///var/run/docker.sock or npipe:////./pipe/docker_engine).",
        },
        "home_assistant": {
            "required_vars": ["HASS_URL", "HASS_TOKEN"],
            "setup_url": "https://www.home-assistant.io/docs/authentication/",
            "instructions": "Create a Long-Lived Access Token in Home Assistant profile settings and provide HASS_URL and HASS_TOKEN.",
        },
        "slack": {
            "required_vars": ["SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET"],
            "setup_url": "https://api.slack.com/apps",
            "instructions": "Create a Slack App with Bot scopes (chat:write, channels:read) and install to your workspace.",
        },
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
        return self.SETUP_GUIDES.get(
            integration_id,
            {
                "required_vars": [f"{integration_id.upper()}_API_KEY"],
                "setup_url": f"https://docs.jarvis.internal/integrations/{integration_id}",
                "instructions": f"Configure required environment variable {integration_id.upper()}_API_KEY in your .env file.",
            },
        )

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
            "key",
            "api_key",
            "secret",
            "token",
            "password",
            "auth",
            "private_key",
            "access_token",
            "client_secret",
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
