from __future__ import annotations

import base64
import email
import email.header
from unittest.mock import MagicMock, patch

import pytest

from adapters.mail.gmail_api_mail_gateway import GmailApiMailGateway
from domain.exceptions import AuthError, MailSendError


def _decode_subject(msg: email.message.Message) -> str:
    return str(email.header.make_header(email.header.decode_header(msg["Subject"])))


def _extract_body(msg: email.message.Message) -> str:
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            payload = part.get_payload(decode=True)
            if isinstance(payload, bytes):
                return payload.decode("utf-8", errors="replace")
    return ""


@pytest.fixture
def mock_creds():
    return MagicMock(name="Credentials")


@pytest.fixture
def mock_service():
    svc = MagicMock(name="GmailService")
    svc.users().messages().send().execute = MagicMock(return_value={"id": "msg_id"})
    return svc


def _patched_gateway(mock_creds, mock_service, retry_count: int = 3):
    return GmailApiMailGateway(
        oauth_token_path=None,
        oauth_token_json='{"refresh_token": "fake"}',
        retry_count=retry_count,
    )


def test_send_invokes_messages_send_once(mock_creds, mock_service):
    with patch(
        "adapters.mail.gmail_api_mail_gateway.load_credentials",
        return_value=mock_creds,
    ), patch(
        "adapters.mail.gmail_api_mail_gateway.build_service", return_value=mock_service
    ):
        gw = _patched_gateway(mock_creds, mock_service)
        gw.send(
            sender="from@example.com",
            to="to@example.com",
            subject="件名",
            body="本文",
        )

    send_method = mock_service.users().messages().send
    send_method.assert_called()
    call_kwargs = send_method.call_args.kwargs
    assert call_kwargs["userId"] == "me"
    raw_b64 = call_kwargs["body"]["raw"]
    decoded = base64.urlsafe_b64decode(raw_b64.encode("ascii"))
    msg = email.message_from_bytes(decoded)
    assert _decode_subject(msg) == "件名"
    assert "本文" in _extract_body(msg)
    assert msg["From"] == "from@example.com"
    assert msg["To"] == "to@example.com"


def test_auth_failure_raises_auth_error(mock_creds):
    failing_service = MagicMock()
    resp = MagicMock()
    resp.status = 401

    class FakeApiError(Exception):
        def __init__(self):
            self.resp = resp
            self.status_code = 401

        def __str__(self):
            return "unauthorized"

    failing_service.users().messages().send().execute.side_effect = FakeApiError()

    with patch(
        "adapters.mail.gmail_api_mail_gateway.load_credentials",
        return_value=mock_creds,
    ), patch(
        "adapters.mail.gmail_api_mail_gateway.build_service",
        return_value=failing_service,
    ):
        gw = GmailApiMailGateway(
            oauth_token_path=None,
            oauth_token_json='{"refresh_token": "fake"}',
            retry_count=1,
        )
        with pytest.raises(AuthError):
            gw.send(sender="a", to="b", subject="s", body="b")


def test_retryable_500_then_success(mock_creds):
    svc = MagicMock()
    resp_500 = MagicMock()
    resp_500.status = 500

    class FakeApiError(Exception):
        def __init__(self, status):
            self.resp = MagicMock(status=status)
            self.status_code = status

        def __str__(self):
            return f"http {self.status_code}"

    svc.users().messages().send().execute.side_effect = [
        FakeApiError(500),
        {"id": "msg_id"},
    ]

    with patch(
        "adapters.mail.gmail_api_mail_gateway.load_credentials",
        return_value=mock_creds,
    ), patch(
        "adapters.mail.gmail_api_mail_gateway.build_service", return_value=svc
    ), patch("adapters.mail.gmail_api_mail_gateway.time.sleep"):
        gw = GmailApiMailGateway(
            oauth_token_path=None,
            oauth_token_json='{"refresh_token": "fake"}',
            retry_count=3,
        )
        gw.send(sender="a", to="b", subject="s", body="b")

    assert svc.users().messages().send().execute.call_count == 2


def test_non_retryable_400_raises_mail_send_error(mock_creds):
    svc = MagicMock()

    class FakeApiError(Exception):
        def __init__(self):
            self.resp = MagicMock(status=400)
            self.status_code = 400

        def __str__(self):
            return "bad request"

    svc.users().messages().send().execute.side_effect = FakeApiError()

    with patch(
        "adapters.mail.gmail_api_mail_gateway.load_credentials",
        return_value=mock_creds,
    ), patch(
        "adapters.mail.gmail_api_mail_gateway.build_service", return_value=svc
    ):
        gw = GmailApiMailGateway(
            oauth_token_path=None,
            oauth_token_json='{"refresh_token": "fake"}',
            retry_count=3,
        )
        with pytest.raises(MailSendError):
            gw.send(sender="a", to="b", subject="s", body="b")
