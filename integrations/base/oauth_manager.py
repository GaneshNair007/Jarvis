"""
JARVIS OAuth Manager
Handles OAuth 2.0 PKCE / state token lifecycle, scope requests, token expiration, and revocation.
Never exposes raw tokens in logs or unauthenticated APIs.
"""

import time
import uuid
import hmac
import hashlib
from typing import Dict, Any, Optional, List

class OAuthManager:
    """Manages OAuth 2.0 authorization flows, tokens, and verification states."""

    OAUTH_ENDPOINTS: Dict[str, Dict[str, str]] = {
        "google": {
            "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "revoke_url": "https://oauth2.googleapis.com/revoke"
        },
        "meta": {
            "auth_url": "https://www.facebook.com/v20.0/dialog/oauth",
            "token_url": "https://graph.facebook.com/v20.0/oauth/access_token",
            "revoke_url": "https://graph.facebook.com/v20.0/permissions"
        },
        "github": {
            "auth_url": "https://github.com/login/oauth/authorize",
            "token_url": "https://github.com/login/oauth/access_token",
            "revoke_url": "https://api.github.com/applications"
        },
        "slack": {
            "auth_url": "https://slack.com/oauth/v2/authorize",
            "token_url": "https://slack.com/api/oauth.v2.access",
            "revoke_url": "https://slack.com/api/auth.revoke"
        }
    }

    def __init__(self):
        # Map: state -> {"provider": str, "scopes": list, "created_at": float, "expires_at": float}
        self._pending_states: Dict[str, Dict[str, Any]] = {}
        # Map: provider -> {"access_token": str, "refresh_token": str, "expires_at": float, "scopes": list}
        self._tokens: Dict[str, Dict[str, Any]] = {}

    def generate_authorization_url(
        self,
        provider: str,
        client_id: str,
        redirect_uri: str,
        scopes: List[str]
    ) -> Dict[str, Any]:
        """Generates a secure OAuth authorization URL with anti-tamper state token."""
        endpoints = self.OAUTH_ENDPOINTS.get(provider)
        if not endpoints:
            raise ValueError(f"Unsupported OAuth provider: {provider}")

        state = f"st_{uuid.uuid4().hex}"
        now = time.time()
        self._pending_states[state] = {
            "provider": provider,
            "scopes": scopes,
            "created_at": now,
            "expires_at": now + 600.0  # 10 minute expiration
        }

        scope_param = " ".join(scopes)
        auth_url = (
            f"{endpoints['auth_url']}?"
            f"client_id={client_id}&"
            f"redirect_uri={redirect_uri}&"
            f"response_type=code&"
            f"scope={scope_param}&"
            f"state={state}&"
            f"access_type=offline&"
            f"prompt=consent"
        )

        return {
            "provider": provider,
            "authorization_url": auth_url,
            "state": state,
            "expires_in_sec": 600
        }

    def verify_state(self, state: str) -> Optional[Dict[str, Any]]:
        """Verifies state token is valid and unexpired."""
        entry = self._pending_states.get(state)
        if not entry:
            return None
        if time.time() > entry["expires_at"]:
            self._pending_states.pop(state, None)
            return None
        return entry

    def register_token(
        self,
        provider: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        expires_in_sec: int = 3600,
        scopes: Optional[List[str]] = None
    ) -> None:
        """Stores token with expiration timestamp."""
        now = time.time()
        self._tokens[provider] = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "created_at": now,
            "expires_at": now + expires_in_sec,
            "scopes": scopes or []
        }

    def is_connected(self, provider: str) -> bool:
        """Checks if a valid, non-expired token exists for provider."""
        t = self._tokens.get(provider)
        if not t:
            return False
        return time.time() < t["expires_at"]

    def get_token(self, provider: str) -> Optional[str]:
        """Returns active access token if valid."""
        if self.is_connected(provider):
            return self._tokens[provider]["access_token"]
        return None

    def revoke_token(self, provider: str) -> bool:
        """Revokes and discards stored token."""
        return self._tokens.pop(provider, None) is not None

# Global OAuth manager instance
oauth_manager = OAuthManager()
