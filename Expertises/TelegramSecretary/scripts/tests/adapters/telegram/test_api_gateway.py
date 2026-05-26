from __future__ import annotations

import json

import httpx
import pytest

from adapters.telegram import api_gateway as gateway_module
from adapters.telegram.api_gateway import TelegramApiGateway
from domain.exceptions import AuthFailureError, TelegramSecretaryError
from domain.models import OutboundMessage
from domain.offset import UpdateOffset


def _gateway(handler, retry_count: int = 2, max_retry_after: int = 60) -> TelegramApiGateway:
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, headers={"User-Agent": "test"})
    return TelegramApiGateway(
        bot_token="TEST_TOKEN",
        client=client,
        retry_count=retry_count,
        max_retry_after_seconds=max_retry_after,
    )


def test_fetch_parses_updates():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "getUpdates" in str(request.url)
        assert "TEST_TOKEN" in str(request.url)
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": [
                    {
                        "update_id": 7,
                        "message": {
                            "chat": {"id": 100},
                            "from": {"id": 200, "username": "weave_user"},
                            "text": "hi",
                        },
                    }
                ],
            },
        )

    gw = _gateway(handler)
    updates = gw.fetch(UpdateOffset.initial(), timeout_seconds=30)
    assert len(updates) == 1
    assert updates[0].update_id == 7
    assert updates[0].text == "hi"


def test_fetch_empty_result():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "result": []})

    gw = _gateway(handler)
    assert gw.fetch(UpdateOffset.initial()) == []


def test_fetch_raises_auth_failure_on_401():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="Unauthorized")

    gw = _gateway(handler)
    with pytest.raises(AuthFailureError):
        gw.fetch(UpdateOffset.initial())


def test_send_message_success():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert "sendMessage" in str(request.url)
        captured["body"] = json.loads(request.read())
        return httpx.Response(200, json={"ok": True, "result": {}})

    gw = _gateway(handler)
    gw.send(OutboundMessage(chat_id=100, text="hi"))
    assert captured["body"]["chat_id"] == 100
    assert captured["body"]["text"] == "hi"


def test_send_message_with_reply_to():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.read())
        return httpx.Response(200, json={"ok": True, "result": {}})

    gw = _gateway(handler)
    gw.send(OutboundMessage(chat_id=100, text="reply", reply_to_message_id=42))
    assert captured["body"]["reply_to_message_id"] == 42


def test_5xx_is_retried_until_success():
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) < 3:
            return httpx.Response(503, text="bad gateway")
        return httpx.Response(200, json={"ok": True, "result": []})

    gw = _gateway(handler, retry_count=2)
    updates = gw.fetch(UpdateOffset.initial())
    assert updates == []
    assert len(attempts) == 3


def test_5xx_fails_after_retries_exhausted():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="bad gateway")

    gw = _gateway(handler, retry_count=2)
    with pytest.raises(TelegramSecretaryError):
        gw.fetch(UpdateOffset.initial())


def test_4xx_client_error_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="bad request")

    gw = _gateway(handler)
    with pytest.raises(TelegramSecretaryError):
        gw.fetch(UpdateOffset.initial())


def test_send_failure_raises_on_ok_false():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": False, "description": "chat not found"})

    gw = _gateway(handler)
    with pytest.raises(TelegramSecretaryError):
        gw.send(OutboundMessage(chat_id=999, text="x"))


# --- 429 / Retry-After ---


def test_429_is_retried_until_success(monkeypatch):
    sleep_calls: list[float] = []
    monkeypatch.setattr(gateway_module.time, "sleep", lambda s: sleep_calls.append(s))

    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) < 3:
            return httpx.Response(429, headers={"Retry-After": "1"})
        return httpx.Response(200, json={"ok": True, "result": []})

    gw = _gateway(handler, retry_count=2)
    updates = gw.fetch(UpdateOffset.initial())
    assert updates == []
    assert len(attempts) == 3
    # Retry-After を尊重して 2 回 sleep（最後の成功時は sleep しない）
    assert sleep_calls == [1, 1]


def test_429_fails_after_retries_exhausted(monkeypatch):
    monkeypatch.setattr(gateway_module.time, "sleep", lambda s: None)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "1"})

    gw = _gateway(handler, retry_count=2)
    with pytest.raises(TelegramSecretaryError) as excinfo:
        gw.fetch(UpdateOffset.initial())
    assert "429" in str(excinfo.value)


def test_429_caps_sleep_at_max_retry_after(monkeypatch):
    sleep_calls: list[float] = []
    monkeypatch.setattr(gateway_module.time, "sleep", lambda s: sleep_calls.append(s))

    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) < 2:
            # 攻撃的に大きな Retry-After を返すケース（自損防止のため上限で丸める）
            return httpx.Response(429, headers={"Retry-After": "3600"})
        return httpx.Response(200, json={"ok": True, "result": []})

    gw = _gateway(handler, retry_count=2, max_retry_after=10)
    gw.fetch(UpdateOffset.initial())
    assert sleep_calls == [10]  # 3600 → 10 に丸められる


def test_429_without_retry_after_does_not_sleep(monkeypatch):
    sleep_calls: list[float] = []
    monkeypatch.setattr(gateway_module.time, "sleep", lambda s: sleep_calls.append(s))

    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) < 2:
            return httpx.Response(429)  # Retry-After ヘッダ無し
        return httpx.Response(200, json={"ok": True, "result": []})

    gw = _gateway(handler, retry_count=2)
    gw.fetch(UpdateOffset.initial())
    # Retry-After 無しなら sleep せず即 retry
    assert sleep_calls == []
    assert len(attempts) == 2


def test_429_invalid_retry_after_does_not_sleep(monkeypatch):
    sleep_calls: list[float] = []
    monkeypatch.setattr(gateway_module.time, "sleep", lambda s: sleep_calls.append(s))

    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) < 2:
            return httpx.Response(429, headers={"Retry-After": "not-a-number"})
        return httpx.Response(200, json={"ok": True, "result": []})

    gw = _gateway(handler, retry_count=2)
    gw.fetch(UpdateOffset.initial())
    assert sleep_calls == []
