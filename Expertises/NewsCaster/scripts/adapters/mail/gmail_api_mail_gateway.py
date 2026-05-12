from __future__ import annotations

import base64
import os
import time
from pathlib import Path
from typing import Any

from adapters.mail.mime_builder import build_mime
from domain.exceptions import AuthError, MailSendError
from infrastructure.google_oauth_provider import load_credentials

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
AUTH_FAILURE_STATUS = {401, 403}


def build_service(creds: Any) -> Any:
    try:
        from googleapiclient.discovery import build
    except ImportError as e:
        raise MailSendError(
            "google-api-python-client not installed. "
            "Run: pip install google-api-python-client google-auth-oauthlib"
        ) from e
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


class GmailApiMailGateway:
    def __init__(
        self,
        *,
        oauth_token_path: Path | None,
        oauth_token_json: str | None,
        retry_count: int = 3,
    ) -> None:
        self._token_path = oauth_token_path
        self._token_json = oauth_token_json
        self._retry_count = max(1, retry_count)
        linux_ca = "/etc/ssl/certs/ca-certificates.crt"
        if os.environ.get("HTTPLIB2_CA_CERTS") is None and os.path.exists(linux_ca):
            os.environ["HTTPLIB2_CA_CERTS"] = linux_ca

    def send(self, *, sender: str, to: str, subject: str, body: str) -> None:
        if not sender or not to or not subject or not body:
            raise MailSendError("sender/to/subject/body are all required")

        mime = build_mime(sender=sender, to=to, subject=subject, body=body)
        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode("ascii")
        request_body = {"raw": raw}

        creds = load_credentials(
            token_path=self._token_path, token_json=self._token_json
        )
        service = build_service(creds)

        last: Exception | None = None
        for attempt in range(self._retry_count):
            try:
                service.users().messages().send(
                    userId="me", body=request_body
                ).execute()
                return
            except Exception as e:
                status = _extract_status(e)
                if status in AUTH_FAILURE_STATUS:
                    raise AuthError(
                        f"Gmail API authentication failed (status={status}): {e}"
                    ) from e
                if status in RETRYABLE_STATUS:
                    last = e
                    if attempt < self._retry_count - 1:
                        time.sleep(2**attempt)
                        continue
                    break
                raise MailSendError(
                    f"Gmail API send failed (status={status}): {e}"
                ) from e

        raise MailSendError(
            f"Gmail API send failed after {self._retry_count} retries: {last}"
        )


def _extract_status(exc: Exception) -> int | None:
    resp = getattr(exc, "resp", None)
    if resp is not None:
        status = getattr(resp, "status", None)
        if status is not None:
            try:
                return int(status)
            except (TypeError, ValueError):
                return None
    status_code = getattr(exc, "status_code", None)
    if status_code is not None:
        try:
            return int(status_code)
        except (TypeError, ValueError):
            return None
    return None
