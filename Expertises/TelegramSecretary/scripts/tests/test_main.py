from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

import adapters.telegram.api_gateway as gateway_module
from main import (
    EXIT_AUTH_FAILED,
    EXIT_CONFIG_INVALID,
    EXIT_LEASE_CONFLICT,
    EXIT_OK,
    main,
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in [
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_SECRETARY_AUTHORIZED_CHATS",
        "TELEGRAM_SECRETARY_STATE_DIR",
        "TELEGRAM_SECRETARY_SESSION_ID",
    ]:
        monkeypatch.delenv(k, raising=False)


@pytest.fixture
def env_ready(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TEST_TOKEN")
    monkeypatch.setenv("TELEGRAM_SECRETARY_AUTHORIZED_CHATS", "[100]")
    monkeypatch.setenv("TELEGRAM_SECRETARY_STATE_DIR", str(tmp_path))
    return tmp_path


# --- validate-config ---


def test_validate_config_fails_when_env_missing(capsys):
    assert main(["validate-config"]) == EXIT_CONFIG_INVALID
    assert "TELEGRAM_BOT_TOKEN" in capsys.readouterr().err


def test_validate_config_succeeds(env_ready, capsys):
    assert main(["validate-config"]) == EXIT_OK
    assert "ok" in capsys.readouterr().out


def test_validate_config_invalid_json_chats(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TEST")
    monkeypatch.setenv("TELEGRAM_SECRETARY_AUTHORIZED_CHATS", "not json")
    monkeypatch.setenv("TELEGRAM_SECRETARY_STATE_DIR", str(tmp_path))
    assert main(["validate-config"]) == EXIT_CONFIG_INVALID


# --- lease ---


def test_lease_acquire_then_release(env_ready, capsys):
    assert main(["lease", "acquire", "--owner", "S1", "--ttl", "120"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "acquired" in out

    assert main(["lease", "release", "--owner", "S1"]) == EXIT_OK


def test_lease_acquire_conflict(env_ready):
    assert main(["lease", "acquire", "--owner", "S1", "--ttl", "120"]) == EXIT_OK
    # 別 owner が fresh lease を奪取しようとすると conflict
    rc = main(["lease", "acquire", "--owner", "S2", "--ttl", "120"])
    assert rc == EXIT_LEASE_CONFLICT


def test_lease_renew_without_existing_lease(env_ready):
    rc = main(["lease", "renew", "--owner", "S1"])
    assert rc == EXIT_LEASE_CONFLICT


# --- poll (TelegramApiGateway をモック) ---


def _install_mock_transport(monkeypatch, handler):
    """TelegramApiGateway が内部で作る httpx.Client を MockTransport で置換。"""
    original_init = gateway_module.TelegramApiGateway.__init__

    def patched_init(
        self,
        bot_token,
        base_url=gateway_module.TelegramApiGateway.DEFAULT_BASE_URL,
        client=None,
        retry_count=2,
        request_timeout=40.0,
    ):
        if client is None:
            client = httpx.Client(transport=httpx.MockTransport(handler))
        original_init(
            self,
            bot_token=bot_token,
            base_url=base_url,
            client=client,
            retry_count=retry_count,
            request_timeout=request_timeout,
        )

    monkeypatch.setattr(gateway_module.TelegramApiGateway, "__init__", patched_init)


def test_poll_emits_authorized_updates(env_ready, monkeypatch, capsys):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": [
                    {
                        "update_id": 1,
                        "message": {
                            "chat": {"id": 100},
                            "from": {"id": 200, "username": "weave"},
                            "text": "hi",
                        },
                    },
                    {
                        "update_id": 2,
                        "message": {
                            "chat": {"id": 999},  # 未認可
                            "from": {"id": 300, "username": "stranger"},
                            "text": "nope",
                        },
                    },
                ],
            },
        )

    _install_mock_transport(monkeypatch, handler)
    rc = main(["poll", "--timeout", "1"])
    assert rc == EXIT_OK
    out = capsys.readouterr().out.strip().split("\n")
    assert len(out) == 1  # 認可済みのみ
    payload = json.loads(out[0])
    assert payload["chat_id"] == 100
    assert payload["text"] == "hi"


def test_poll_returns_auth_failed_on_401(env_ready, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="Unauthorized")

    _install_mock_transport(monkeypatch, handler)
    assert main(["poll", "--timeout", "1"]) == EXIT_AUTH_FAILED


# --- watch (max-iterations=1 で停止) ---


def test_watch_runs_one_iteration_and_exits(env_ready, monkeypatch, capsys):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "result": []})

    _install_mock_transport(monkeypatch, handler)
    # watch はサイクル末尾で lease renew するため、事前 acquire が必要
    assert main(["lease", "acquire", "--owner", "S1"]) == EXIT_OK
    rc = main(["watch", "--timeout", "1", "--max-iterations", "1", "--owner", "S1"])
    assert rc == EXIT_OK


def test_watch_exits_4_when_no_lease(env_ready, monkeypatch):
    """事前 acquire 無しで watch を回すと、renew 段階で exit 4 を返す（並走奪取の自己治癒経路の入口）。"""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "result": []})

    _install_mock_transport(monkeypatch, handler)
    rc = main(["watch", "--timeout", "1", "--max-iterations", "1", "--owner", "S1"])
    assert rc == EXIT_LEASE_CONFLICT


def test_watch_exits_4_when_lease_stolen(env_ready, monkeypatch):
    """watch 中に lease が他人に奪われていた場合、renew で exit 4。"""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "result": []})

    _install_mock_transport(monkeypatch, handler)
    # 別 owner が lease を保持している状態を作る
    assert main(["lease", "acquire", "--owner", "OTHER"]) == EXIT_OK
    # 自分の owner で watch を回そうとすると renew が刺さる
    rc = main(["watch", "--timeout", "1", "--max-iterations", "1", "--owner", "S1"])
    assert rc == EXIT_LEASE_CONFLICT


# --- send-reply ---


def test_send_reply_requires_lease(env_ready, monkeypatch, tmp_path):
    text_file = tmp_path / "reply.txt"
    text_file.write_text("hello", encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "result": {}})

    _install_mock_transport(monkeypatch, handler)
    rc = main(
        [
            "send-reply",
            "--chat-id",
            "100",
            "--update-id",
            "1",
            "--text-file",
            str(text_file),
        ]
    )
    assert rc == EXIT_LEASE_CONFLICT


def test_send_reply_after_lease_acquire(env_ready, monkeypatch, tmp_path, capsys):
    text_file = tmp_path / "reply.txt"
    text_file.write_text("hello", encoding="utf-8")

    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if "sendMessage" in str(request.url):
            captured["body"] = json.loads(request.read())
        return httpx.Response(200, json={"ok": True, "result": {}})

    _install_mock_transport(monkeypatch, handler)
    assert main(["lease", "acquire", "--owner", "S1"]) == EXIT_OK
    rc = main(
        [
            "send-reply",
            "--chat-id",
            "100",
            "--update-id",
            "1",
            "--text-file",
            str(text_file),
        ]
    )
    assert rc == EXIT_OK
    assert captured["body"]["chat_id"] == 100
    assert captured["body"]["text"] == "hello"
