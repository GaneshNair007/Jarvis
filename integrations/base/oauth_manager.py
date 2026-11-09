"""JARVIS OAuth 2.0 Manager.

Production-grade authorization-code flow with:

- cryptographically random ``state`` validation
- PKCE (S256) for public/desktop clients
- loopback redirect support
- refresh-token lifecycle
- encrypted persistence through Windows DPAPI
- explicit revoke/disconnect
- credential-redacted results and logs

The manager never accepts or stores Google account passwords, app passwords,
browser cookies or copied browser sessions.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

from integrations.base.credential_manager import DpapiFileStore
from jarvis.core.logger import get_logger

logger = get_logger("integrations.oauth")

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"


class OAuthError(Exception):
    """Redacted OAuth failure.  Never carries access/refresh tokens."""

    def __init__(self, error: str, description: str = "", status_code: Optional[int] = None):
        self.error = error
        self.description = description
        self.status_code = status_code
        super().__init__(f"{error}: {description}" if description else error)


class OAuthStateError(OAuthError):
    """Raised when a state value is missing, expired, or replayed."""


class TokenStore(Protocol):
    def load(self, provider: str) -> Optional[Dict[str, Any]]: ...
    def save(self, provider: str, payload: Dict[str, Any]) -> Any: ...
    def delete(self, provider: str) -> bool: ...


class InMemoryTokenStore:
    """Non-persistent token store for tests and ephemeral sessions."""

    def __init__(self):
        self._data: Dict[str, Dict[str, Any]] = {}

    def load(self, provider: str) -> Optional[Dict[str, Any]]:
        value = self._data.get(provider)
        return dict(value) if value else None

    def save(self, provider: str, payload: Dict[str, Any]) -> None:
        self._data[provider] = dict(payload)

    def delete(self, provider: str) -> bool:
        return self._data.pop(provider, None) is not None


class DpapiTokenStore:
    """Encrypted persistent token store backed by Windows DPAPI."""

    def __init__(self, base_dir: Optional[os.PathLike | str] = None):
        from jarvis.config import settings

        self._store = DpapiFileStore(base_dir or (settings.data_dir / "credentials"))

    def load(self, provider: str) -> Optional[Dict[str, Any]]:
        return self._store.load(f"{provider}_oauth")

    def save(self, provider: str, payload: Dict[str, Any]) -> Any:
        return self._store.save(f"{provider}_oauth", payload)

    def delete(self, provider: str) -> bool:
        return self._store.delete(f"{provider}_oauth")


class UrllibTransport:
    """Minimal HTTPS transport with no third-party dependencies."""

    def __init__(self, timeout: float = 20.0):
        self.timeout = timeout

    def _request(
        self,
        method: str,
        url: str,
        data: Optional[bytes] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        request = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read()
                if not body:
                    return {}
                return json.loads(body.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
            except ValueError:
                payload = {"error": f"HTTP {exc.code}", "error_description": raw[:300]}
            raise OAuthError(
                str(payload.get("error", f"HTTP {exc.code}")),
                str(payload.get("error_description", "")),
                status_code=exc.code,
            ) from exc
        except urllib.error.URLError as exc:
            raise OAuthError("network_error", str(exc.reason)) from exc

    def post_form(self, url: str, form: Dict[str, Any]) -> Dict[str, Any]:
        body = urllib.parse.urlencode(form).encode("utf-8")
        return self._request(
            "POST",
            url,
            data=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )

    def get_json(self, url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        return self._request("GET", url, headers=headers)

    def post_json(
        self,
        url: str,
        payload: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        body = json.dumps(payload or {}).encode("utf-8")
        merged = {"Content-Type": "application/json", "Accept": "application/json"}
        merged.update(headers or {})
        return self._request("POST", url, data=body, headers=merged)


@dataclass
class PendingAuthorization:
    provider: str
    scopes: List[str]
    redirect_uri: str
    client_id: str
    code_verifier: Optional[str]
    created_at: float
    expires_at: float
    use_pkce: bool

    def to_public_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "scopes": list(self.scopes),
            "redirect_uri": self.redirect_uri,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "pkce": self.use_pkce,
        }


class OAuthManager:
    """Manages OAuth 2.0 authorization flows, tokens, refresh and revocation."""

    OAUTH_ENDPOINTS: Dict[str, Dict[str, str]] = {
        "google": {
            "auth_url": GOOGLE_AUTH_URL,
            "token_url": GOOGLE_TOKEN_URL,
            "revoke_url": GOOGLE_REVOKE_URL,
        },
        "meta": {
            "auth_url": "https://www.facebook.com/v20.0/dialog/oauth",
            "token_url": "https://graph.facebook.com/v20.0/oauth/access_token",
            "revoke_url": "https://graph.facebook.com/v20.0/permissions",
        },
        "github": {
            "auth_url": "https://github.com/login/oauth/authorize",
            "token_url": "https://github.com/login/oauth/access_token",
            "revoke_url": "https://api.github.com/applications",
        },
        "slack": {
            "auth_url": "https://slack.com/oauth/v2/authorize",
            "token_url": "https://slack.com/api/oauth.v2.access",
            "revoke_url": "https://slack.com/api/auth.revoke",
        },
    }

    STATE_TTL_SEC = 600.0

    def __init__(
        self,
        token_store: Optional[TokenStore] = None,
        transport: Optional[UrllibTransport] = None,
        clock: Optional[Any] = None,
    ):
        self.token_store: TokenStore = token_store or InMemoryTokenStore()
        self.transport: UrllibTransport = transport or UrllibTransport()
        self._clock = clock or time.time
        self._pending_states: Dict[str, PendingAuthorization] = {}
        # Legacy in-memory cache; the persistent store is authoritative when set.
        self._tokens: Dict[str, Dict[str, Any]] = {}

    # ── Authorization request ────────────────────────────────────────────────

    def generate_authorization_url(
        self,
        provider: str,
        client_id: str,
        redirect_uri: str,
        scopes: List[str],
        use_pkce: bool = True,
        extra_params: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Generate a state-protected (and PKCE-bound) authorization URL."""
        endpoints = self.OAUTH_ENDPOINTS.get(provider)
        if not endpoints:
            raise ValueError(f"Unsupported OAuth provider: {provider}")
        if not client_id or not redirect_uri or not scopes:
            raise ValueError("client_id, redirect_uri and scopes are required")

        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64) if use_pkce else None
        now = self._clock()
        pending = PendingAuthorization(
            provider=provider,
            scopes=list(scopes),
            redirect_uri=redirect_uri,
            client_id=client_id,
            code_verifier=verifier,
            created_at=now,
            expires_at=now + self.STATE_TTL_SEC,
            use_pkce=use_pkce,
        )
        self._pending_states[state] = pending

        params: Dict[str, str] = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "state": state,
        }
        if provider == "google":
            params["access_type"] = "offline"
            params["prompt"] = "consent"
            params["include_granted_scopes"] = "true"
        if verifier:
            challenge = (
                base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
            )
            params["code_challenge"] = challenge
            params["code_challenge_method"] = "S256"
        for key, value in (extra_params or {}).items():
            if key not in {"client_secret", "code_verifier"}:
                params[str(key)] = str(value)

        authorization_url = f"{endpoints['auth_url']}?{urllib.parse.urlencode(params)}"
        return {
            "provider": provider,
            "authorization_url": authorization_url,
            "state": state,
            "expires_in_sec": int(self.STATE_TTL_SEC),
            "pkce": bool(verifier),
            "scopes": list(scopes),
        }

    def verify_state(self, state: str) -> Optional[Dict[str, Any]]:
        """Return the pending authorization for a valid, unexpired state."""
        entry = self._pending_states.get(state)
        if not entry:
            return None
        if self._clock() > entry.expires_at:
            self._pending_states.pop(state, None)
            return None
        return entry.to_public_dict()

    def consume_state(self, state: str) -> Optional[PendingAuthorization]:
        """Validate and one-time-consume a state value."""
        entry = self._pending_states.pop(state, None)
        if not entry:
            return None
        if self._clock() > entry.expires_at:
            return None
        return entry

    # ── Code exchange / refresh ──────────────────────────────────────────────

    def exchange_code(
        self,
        provider: str,
        code: str,
        state: str,
        client_id: str,
        client_secret: str,
        redirect_uri: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Exchange an authorization code, persist tokens, return a redacted summary."""
        entry = self.consume_state(state)
        if not entry:
            raise OAuthStateError("invalid_state", "State is missing, expired, or already used")
        if entry.provider != provider:
            raise OAuthStateError("state_provider_mismatch", "State was issued for another provider")
        if not code:
            raise OAuthError("missing_code", "Authorization code is empty")

        endpoints = self.OAUTH_ENDPOINTS[provider]
        form: Dict[str, Any] = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri or entry.redirect_uri,
            "grant_type": "authorization_code",
        }
        if entry.code_verifier:
            form["code_verifier"] = entry.code_verifier

        response = self.transport.post_form(endpoints["token_url"], form)
        token = self._store_token_response(provider, response)
        return self._public_status(provider, token)

    def refresh_access_token(
        self,
        provider: str,
        client_id: str,
        client_secret: str,
    ) -> Dict[str, Any]:
        """Refresh an expired access token using the persisted refresh token."""
        token = self._refresh_token(provider, client_id, client_secret)
        return self._public_status(provider, token)

    def _refresh_token(
        self,
        provider: str,
        client_id: str,
        client_secret: str,
    ) -> Dict[str, Any]:
        token = self._load_token(provider)
        if not token or not token.get("refresh_token"):
            raise OAuthError("no_refresh_token", "No refresh token is stored for this provider")
        endpoints = self.OAUTH_ENDPOINTS.get(provider)
        if not endpoints:
            raise ValueError(f"Unsupported OAuth provider: {provider}")

        response = self.transport.post_form(
            endpoints["token_url"],
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": token["refresh_token"],
                "grant_type": "refresh_token",
            },
        )
        return self._store_token_response(provider, response, existing=token)

    def get_valid_access_token(
        self,
        provider: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        skew_sec: float = 60.0,
    ) -> Optional[str]:
        """Return a usable access token, refreshing automatically when possible."""
        token = self._load_token(provider)
        if not token:
            return None
        now = self._clock()
        if token.get("access_token") and float(token.get("expires_at", 0)) - skew_sec > now:
            return token["access_token"]
        if token.get("refresh_token") and client_id and client_secret:
            refreshed = self._refresh_token(provider, client_id, client_secret)
            return refreshed.get("access_token")
        return None

    # ── Token persistence / status ───────────────────────────────────────────

    def _store_token_response(
        self,
        provider: str,
        response: Dict[str, Any],
        existing: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if response.get("error"):
            raise OAuthError(
                str(response.get("error")),
                str(response.get("error_description", "")),
                status_code=response.get("status_code"),
            )
        access_token = response.get("access_token")
        if not access_token:
            raise OAuthError("missing_access_token", "Token endpoint returned no access_token")

        now = self._clock()
        try:
            expires_in = int(response.get("expires_in", 3600))
        except (TypeError, ValueError):
            expires_in = 3600
        scopes = str(response.get("scope") or "").split()
        token = {
            "access_token": access_token,
            "refresh_token": response.get("refresh_token") or (existing or {}).get("refresh_token"),
            "token_type": response.get("token_type", "Bearer"),
            "expires_at": now + max(expires_in, 0),
            "obtained_at": now,
            "scopes": scopes or list((existing or {}).get("scopes", [])),
            "account_email": (existing or {}).get("account_email"),
        }
        self._tokens[provider] = token
        try:
            self.token_store.save(provider, token)
        except Exception as exc:  # never include token material in the message
            logger.error("Failed to persist OAuth token for %s: %s", provider, type(exc).__name__)
            raise OAuthError("token_persistence_failed", "Could not store the OAuth token securely") from exc
        return token

    def _load_token(self, provider: str) -> Optional[Dict[str, Any]]:
        cached = self._tokens.get(provider)
        if cached:
            return cached
        try:
            stored = self.token_store.load(provider)
        except Exception as exc:
            logger.warning("OAuth token store read failed for %s: %s", provider, type(exc).__name__)
            return None
        if stored:
            self._tokens[provider] = stored
        return stored

    def load_persisted(self, provider: str) -> Optional[Dict[str, Any]]:
        """Load a stored token (internal use; do not expose via APIs)."""
        return self._load_token(provider)

    def set_account_email(self, provider: str, email: str) -> bool:
        """Attach the verified provider account identity to the stored token."""
        token = self._load_token(provider)
        if not token:
            return False
        token["account_email"] = email
        self._tokens[provider] = token
        self.token_store.save(provider, token)
        return True

    def _public_status(self, provider: str, token: Dict[str, Any]) -> Dict[str, Any]:
        now = self._clock()
        return {
            "provider": provider,
            "status": "CONNECTED",
            "account_email": token.get("account_email"),
            "scopes": list(token.get("scopes", [])),
            "expires_at": token.get("expires_at"),
            "expires_in_sec": max(0, int(float(token.get("expires_at", now)) - now)),
            "has_refresh_token": bool(token.get("refresh_token")),
            "token_type": token.get("token_type", "Bearer"),
        }

    def status(self, provider: str) -> Dict[str, Any]:
        """Redacted connection status.  Never returns token values."""
        token = self._load_token(provider)
        if not token:
            return {
                "provider": provider,
                "status": "DISCONNECTED",
                "connected": False,
                "has_refresh_token": False,
                "scopes": [],
                "account_email": None,
            }
        now = self._clock()
        connected = bool(token.get("refresh_token")) or float(token.get("expires_at", 0)) > now
        status = self._public_status(provider, token)
        status["connected"] = connected
        status["status"] = "CONNECTED" if connected else "EXPIRED"
        return status

    def is_connected(self, provider: str) -> bool:
        """True when a usable access token or a refresh token exists."""
        token = self._load_token(provider)
        if not token:
            return False
        return bool(token.get("refresh_token")) or float(token.get("expires_at", 0)) > self._clock()

    # ── Legacy compatibility ─────────────────────────────────────────────────

    def register_token(
        self,
        provider: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        expires_in_sec: int = 3600,
        scopes: Optional[List[str]] = None,
    ) -> None:
        """Store a token in memory (legacy API; does not write DPAPI storage)."""
        now = self._clock()
        self._tokens[provider] = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "created_at": now,
            "obtained_at": now,
            "expires_at": now + expires_in_sec,
            "scopes": scopes or [],
            "account_email": None,
        }

    def get_token(self, provider: str) -> Optional[str]:
        """Return an unexpired access token without refreshing."""
        token = self._load_token(provider)
        if not token:
            return None
        if float(token.get("expires_at", 0)) > self._clock():
            return token.get("access_token")
        return None

    def revoke_token(
        self,
        provider: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ) -> bool:
        """Revoke at the provider when possible, then delete local tokens.

        Returns True when local token material existed and was removed.  Remote
        revocation failures are logged (without token values) but local
        credentials are still deleted so the next call cannot silently reuse
        them.
        """
        token = self._load_token(provider)
        existed = token is not None or provider in self._tokens
        remote_ok = False
        if token:
            endpoints = self.OAUTH_ENDPOINTS.get(provider)
            revoke_url = endpoints.get("revoke_url") if endpoints else None
            if revoke_url:
                for candidate in (token.get("refresh_token"), token.get("access_token")):
                    if not candidate:
                        continue
                    try:
                        # Google expects the token as a form/query parameter.
                        self.transport.post_form(revoke_url, {"token": candidate})
                        remote_ok = True
                        break
                    except Exception as exc:
                        logger.warning(
                            "OAuth revoke request failed for %s (%s); deleting local token anyway.",
                            provider,
                            type(exc).__name__,
                        )
        self._tokens.pop(provider, None)
        try:
            self.token_store.delete(provider)
        except Exception as exc:
            logger.warning("OAuth token store delete failed for %s: %s", provider, type(exc).__name__)
        if existed and not remote_ok and token:
            logger.warning("Local OAuth token for %s deleted; provider revocation was not confirmed.", provider)
        return existed

    def disconnect(self, provider: str) -> bool:
        return self.revoke_token(provider)


def _default_token_store() -> TokenStore:
    if os.name == "nt":
        try:
            return DpapiTokenStore()
        except Exception as exc:
            logger.error("DPAPI token store unavailable (%s); OAuth persistence disabled.", type(exc).__name__)
    return InMemoryTokenStore()


# Global OAuth manager instance (DPAPI-backed on Windows)
oauth_manager = OAuthManager(token_store=_default_token_store())
