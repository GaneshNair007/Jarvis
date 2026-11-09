"""Google OAuth 2.0 connection workflow for the JARVIS assistant account.

Owner flow:

1. Create a Google Cloud project and enable the Gmail API.
2. Create an OAuth 2.0 Client ID of type "Desktop app".
3. Put GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in ``.env``.
4. Run ``python -m integrations.google.oauth_flow connect``.
5. Sign in as the dedicated JARVIS account and grant the three Gmail scopes.

The loopback listener binds only to 127.0.0.1.  Tokens are persisted with
Windows DPAPI; they are never printed, logged or returned by the HTTP API.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

from integrations.base.credential_manager import credential_manager
from integrations.base.oauth_manager import OAuthError, OAuthManager, oauth_manager
from integrations.google.gmail_api import GoogleApiClient
from integrations.google.gmail_integration import GMAIL_SCOPES
from jarvis.config import settings
from jarvis.core.logger import get_logger

logger = get_logger("integrations.google.oauth")


class InteractiveAuthorization:
    """A running loopback OAuth authorization session.

    The CLI waits on it; the REST API starts it and polls :meth:`poll` so the
    owner can complete consent in a browser while the API stays responsive.
    """

    def __init__(
        self,
        flow: "GoogleOAuthFlow",
        server: ThreadingHTTPServer,
        thread: threading.Thread,
        authorization: Dict[str, Any],
        result: Dict[str, Any],
        timeout_sec: float,
    ):
        self.flow = flow
        self.server = server
        self.thread = thread
        self.authorization = authorization
        self.result = result
        self.deadline = time.monotonic() + timeout_sec
        self._closed = False

    @property
    def authorization_url(self) -> str:
        return self.authorization["authorization_url"]

    @property
    def redirect_uri(self) -> str:
        return self.authorization["redirect_uri"]

    def _expires_in(self) -> int:
        return max(0, int(self.deadline - time.monotonic()))

    def poll(self) -> Dict[str, Any]:
        """Return PENDING, or the verified connection summary; raise on failure."""
        if self.result["error"] is not None:
            error = self.result["error"]
            self.close()
            raise error
        if self.result["event"].is_set():
            data = self.result["data"] or {}
            self.close()
            return {"status": "CONNECTED", **data}
        if time.monotonic() >= self.deadline:
            self.close()
            raise OAuthError(
                "authorization_timeout",
                "No OAuth callback was received before the authorization session expired",
            )
        return {
            "status": "PENDING",
            "authorization_url": self.authorization_url,
            "redirect_uri": self.redirect_uri,
            "expires_in_sec": self._expires_in(),
        }

    def wait(self, timeout_sec: Optional[float] = None) -> Dict[str, Any]:
        remaining = self.deadline - time.monotonic() if timeout_sec is None else timeout_sec
        if not self.result["event"].wait(timeout=max(0.0, remaining)):
            self.close()
            raise OAuthError(
                "authorization_timeout",
                f"No OAuth callback received within {int(max(0.0, remaining))} seconds",
            )
        if self.result["error"] is not None:
            error = self.result["error"]
            self.close()
            raise error
        data = self.result["data"] or {}
        self.close()
        return data

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.server.shutdown()
        except Exception:
            pass
        try:
            self.server.server_close()
        except Exception:
            pass
        self.thread.join(timeout=2.0)


class GoogleOAuthFlow:
    """Authorization-code + PKCE flow with a 127.0.0.1 loopback callback."""

    def __init__(self, oauth: Optional[OAuthManager] = None, api: Optional[GoogleApiClient] = None):
        self.oauth = oauth or oauth_manager
        self.api = api or GoogleApiClient(oauth=self.oauth)

    def _credentials(self) -> tuple[str, str]:
        client_id = credential_manager.get_credential("GOOGLE_CLIENT_ID") or ""
        client_secret = credential_manager.get_credential("GOOGLE_CLIENT_SECRET") or ""
        if not client_id or not client_secret:
            guide = credential_manager.get_setup_guide("google_gmail")
            raise OAuthError(
                "google_oauth_not_configured",
                "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are required. "
                f"Setup: {guide['setup_url']} — {guide['instructions']}",
            )
        return client_id, client_secret

    def build_authorization(
        self,
        redirect_uri: str,
        scopes: Optional[list[str]] = None,
    ) -> Dict[str, Any]:
        client_id, _secret = self._credentials()
        return self.oauth.generate_authorization_url(
            "google",
            client_id,
            redirect_uri,
            scopes or list(GMAIL_SCOPES),
            use_pkce=True,
        )

    def complete(self, code: str, state: str, redirect_uri: Optional[str] = None) -> Dict[str, Any]:
        """Exchange the code, verify the account, and return a redacted status."""
        client_id, client_secret = self._credentials()
        summary = self.oauth.exchange_code(
            "google",
            code=code,
            state=state,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
        )

        profile = self.api.get_profile()
        email = str(profile.get("emailAddress") or "")
        expected = (settings.assistant_email or "").strip().lower()
        if expected and email.strip().lower() != expected:
            # Wrong account: revoke immediately and refuse the connection.
            self.oauth.revoke_token("google")
            raise OAuthError(
                "wrong_google_account",
                f"Signed in as {email}, but the assistant identity is {settings.assistant_email}. "
                "The token was revoked. Re-run the flow with the dedicated JARVIS account.",
            )

        self.oauth.set_account_email("google", email)
        return {
            **summary,
            "account_email": email,
            "verified": True,
            "gmail_messages_total": profile.get("messagesTotal"),
            "gmail_threads_total": profile.get("threadsTotal"),
        }

    def start_interactive(
        self,
        *,
        open_browser: bool = True,
        timeout_sec: float = 300.0,
        port: int = 0,
        scopes: Optional[list[str]] = None,
    ) -> InteractiveAuthorization:
        """Start the loopback callback server and return a pollable session."""
        result: Dict[str, Any] = {"event": threading.Event(), "data": None, "error": None}

        class CallbackHandler(BaseHTTPRequestHandler):
            def _respond(self, status: int, title: str) -> None:
                body = (
                    "<!doctype html><html><head><meta charset='utf-8'>"
                    f"<title>{title}</title></head><body style='font-family:Segoe UI,sans-serif;"
                    "background:#0b1020;color:#e8f1ff;padding:3rem'>"
                    f"<h1>{title}</h1><p>You can close this window and return to JARVIS.</p>"
                    "</body></html>"
                ).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):  # noqa: N802 (http.server API)
                parsed = urlparse(self.path)
                if parsed.path not in {"", "/", "/oauth2callback"}:
                    self.send_error(404)
                    result["event"].set()
                    return
                params = parse_qs(parsed.query)
                if "error" in params:
                    result["error"] = OAuthError(
                        params["error"][0],
                        (params.get("error_description") or [""])[0],
                    )
                    self._respond(400, "Google authorization denied")
                    result["event"].set()
                    return

                code = (params.get("code") or [""])[0]
                state = (params.get("state") or [""])[0]
                if not code or not state:
                    result["error"] = OAuthError("missing_callback_parameters", "No code/state in callback")
                    self._respond(400, "Invalid OAuth callback")
                    result["event"].set()
                    return

                try:
                    result["data"] = self.complete(
                        code,
                        state,
                        redirect_uri=f"http://127.0.0.1:{server.server_address[1]}",
                    )
                    self._respond(200, "JARVIS connected")
                except Exception as exc:  # noqa: BLE001 - reported to the CLI
                    result["error"] = exc
                    self._respond(400, "JARVIS connection failed")
                finally:
                    result["event"].set()

            def log_message(self, fmt, *args):  # noqa: A003
                # Never log the query string: it contains the authorization code.
                logger.debug("OAuth loopback request: %s", fmt % args)

        server = ThreadingHTTPServer(("127.0.0.1", port), CallbackHandler)
        server.daemon_threads = True
        redirect_uri = f"http://127.0.0.1:{server.server_address[1]}"
        authorization = self.build_authorization(redirect_uri, scopes=scopes)
        authorization["redirect_uri"] = redirect_uri
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        session = InteractiveAuthorization(self, server, thread, authorization, result, timeout_sec)
        if open_browser:
            try:
                webbrowser.open(authorization["authorization_url"])
            except Exception:
                logger.warning("Could not open the default browser; use the authorization URL.")
        return session

    def connect_interactive(
        self,
        *,
        open_browser: bool = True,
        timeout_sec: float = 300.0,
        port: int = 0,
        scopes: Optional[list[str]] = None,
    ) -> Dict[str, Any]:
        session = self.start_interactive(
            open_browser=open_browser,
            timeout_sec=timeout_sec,
            port=port,
            scopes=scopes,
        )
        try:
            print("Open this URL in a browser signed in as the JARVIS account:")
            print(session.authorization_url)
            return session.wait()
        finally:
            session.close()

    def status(self) -> Dict[str, Any]:
        is_valid, missing = credential_manager.validate_credentials(
            ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"]
        )
        if not is_valid:
            return {
                "status": "UNCONFIGURED",
                "connected": False,
                "missing_credentials": missing,
                "setup_guide": credential_manager.get_setup_guide("google_gmail"),
                "assistant_email": settings.assistant_email,
            }
        status = self.oauth.status("google")
        status["assistant_email"] = settings.assistant_email
        status["owner_email_configured"] = bool(settings.owner_email)
        status["scopes_requested"] = list(GMAIL_SCOPES)
        return status

    def disconnect(self) -> Dict[str, Any]:
        existed = self.oauth.revoke_token("google")
        return {
            "status": "DISCONNECTED",
            "local_token_deleted": bool(existed),
            "provider_revocation": "requested" if existed else "not_needed",
        }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="JARVIS Google OAuth setup")
    sub = parser.add_subparsers(dest="command", required=True)

    connect = sub.add_parser("connect", help="run the Google authorization-code flow")
    connect.add_argument("--no-browser", action="store_true", help="print the URL instead of opening a browser")
    connect.add_argument("--timeout", type=float, default=300.0, help="callback timeout in seconds")
    connect.add_argument("--port", type=int, default=0, help="fixed loopback port (default: ephemeral)")

    sub.add_parser("status", help="show redacted Google connection status")
    sub.add_parser("disconnect", help="revoke the Google token and delete local credentials")

    args = parser.parse_args(argv)
    flow = GoogleOAuthFlow()

    try:
        if args.command == "status":
            print(json.dumps(flow.status(), indent=2, sort_keys=True))
            return 0
        if args.command == "disconnect":
            print(json.dumps(flow.disconnect(), indent=2, sort_keys=True))
            return 0
        if args.command == "connect":
            status = flow.connect_interactive(
                open_browser=not args.no_browser,
                timeout_sec=args.timeout,
                port=args.port,
            )
            print(json.dumps(status, indent=2, sort_keys=True))
            return 0
    except OAuthError as exc:
        print(f"ERROR [{exc.error}]: {exc.description or exc.error}", file=sys.stderr)
        if exc.error == "google_oauth_not_configured":
            print(json.dumps(credential_manager.get_setup_guide("google_gmail"), indent=2), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
