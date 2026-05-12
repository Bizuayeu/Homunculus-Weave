from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from domain.exceptions import AuthError

GMAIL_SEND_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def load_credentials(
    token_path: Path | None = None,
    token_json: str | None = None,
) -> Any:
    """OAuth credentials を path または inline JSON から構築する.

    BlueberrySprite と互換のインターフェース。同じ token.json を共有可能。
    """
    if token_json is not None:
        try:
            raw = json.loads(token_json)
        except json.JSONDecodeError as e:
            raise AuthError(f"failed to parse NEWSCASTER_OAUTH_TOKEN_JSON: {e}") from e
        return _build_credentials(raw, persist_path=None)

    if token_path is None:
        raise AuthError(
            "either token_path or token_json is required. "
            "Set NEWSCASTER_OAUTH_TOKEN_PATH or NEWSCASTER_OAUTH_TOKEN_JSON."
        )

    if not token_path.exists():
        raise AuthError(
            f"OAuth token not found: {token_path}. "
            "Set NEWSCASTER_OAUTH_TOKEN_PATH to an existing BBS token.json or run oauth_setup."
        )

    try:
        raw = json.loads(token_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise AuthError(f"failed to parse OAuth token at {token_path}: {e}") from e

    return _build_credentials(raw, persist_path=token_path)


def _build_credentials(raw: dict, persist_path: Path | None) -> Any:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ImportError as e:
        raise AuthError(
            "google-auth / google-auth-oauthlib not installed. "
            "Run: pip install google-api-python-client google-auth-oauthlib"
        ) from e

    creds = Credentials(
        token=raw.get("access_token") or raw.get("token"),
        refresh_token=raw.get("refresh_token"),
        token_uri=raw.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=raw.get("client_id"),
        client_secret=raw.get("client_secret"),
        scopes=raw.get("scopes", GMAIL_SEND_SCOPES),
    )

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as e:
            raise AuthError(f"OAuth token refresh failed: {e}") from e
        if persist_path is not None:
            _save_credentials(persist_path, creds)

    if not creds.valid:
        raise AuthError(
            "OAuth credentials are invalid (no refresh_token or refresh failed)."
        )

    return creds


def _save_credentials(token_path: Path, creds: Any) -> None:
    payload = {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes or GMAIL_SEND_SCOPES),
    }
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    try:
        token_path.chmod(0o600)
    except OSError:
        pass
