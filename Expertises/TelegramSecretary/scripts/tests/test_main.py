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
            "--owner",
            "S1",
        ]
    )
    assert rc == EXIT_OK
    assert captured["body"]["chat_id"] == 100
    assert captured["body"]["text"] == "hello"


def test_send_reply_fails_when_owner_mismatch(env_ready, monkeypatch, tmp_path):
    """別 owner の lease で send-reply は exit 4（CLI 層の防御）。"""
    text_file = tmp_path / "reply.txt"
    text_file.write_text("hello", encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
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
            "--owner",
            "S2",
        ]
    )
    assert rc == EXIT_LEASE_CONFLICT


def test_send_reply_uses_env_owner(env_ready, monkeypatch, tmp_path):
    """env で TELEGRAM_SECRETARY_SESSION_ID を export すれば --owner 省略可 (運用律 B 案)。"""
    text_file = tmp_path / "reply.txt"
    text_file.write_text("hello", encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "result": {}})

    _install_mock_transport(monkeypatch, handler)
    # bootstrap.sh が export する状況を再現
    monkeypatch.setenv("TELEGRAM_SECRETARY_SESSION_ID", "S-env")
    # --owner 省略、env 経由で同じ owner を共有
    assert main(["lease", "acquire"]) == EXIT_OK
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


def test_watch_uses_env_owner(env_ready, monkeypatch):
    """env で session_id を export しておけば watch も同じ owner で renew する。"""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "result": []})

    _install_mock_transport(monkeypatch, handler)
    monkeypatch.setenv("TELEGRAM_SECRETARY_SESSION_ID", "S-env-watch")
    # --owner 省略、env 経由で acquire→watch が同じ owner を共有
    assert main(["lease", "acquire"]) == EXIT_OK
    rc = main(["watch", "--timeout", "1", "--max-iterations", "1"])
    assert rc == EXIT_OK


# --- Stage 6.4: Medium モード（download 無効）切替 ---


def test_poll_medium_mode_emits_media_without_local_path(
    env_ready, monkeypatch, capsys
):
    """media_enable_download=false: photo 付き update が来ても download せず、
    emit に local_path=None の media[] が乗る。getFile も呼ばれない。"""
    monkeypatch.setenv("TELEGRAM_SECRETARY_MEDIA_ENABLE_DOWNLOAD", "false")

    def handler(request: httpx.Request) -> httpx.Response:
        # Medium モードでは getFile は絶対呼ばれない
        assert "getFile" not in str(request.url)
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
                            "photo": [{"file_id": "AgACphoto", "file_size": 4096}],
                            "caption": "見て",
                        },
                    },
                ],
            },
        )

    _install_mock_transport(monkeypatch, handler)
    rc = main(["poll", "--timeout", "1"])
    assert rc == EXIT_OK
    out = capsys.readouterr().out.strip()
    payload = json.loads(out)
    # caption は text に統合
    assert payload["text"] == "見て"
    # media は出るが local_path は None（Medium モード）
    assert len(payload["media"]) == 1
    assert payload["media"][0]["kind"] == "photo"
    assert payload["media"][0]["file_id"] == "AgACphoto"
    assert payload["media"][0]["local_path"] is None
    assert payload["media"][0]["skip_reason"] is None


def test_poll_medium_mode_text_only_unchanged(env_ready, monkeypatch, capsys):
    """media なし text-only update でも Medium モードで Stage 5 と同等に動く。"""
    monkeypatch.setenv("TELEGRAM_SECRETARY_MEDIA_ENABLE_DOWNLOAD", "false")

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
                ],
            },
        )

    _install_mock_transport(monkeypatch, handler)
    rc = main(["poll", "--timeout", "1"])
    assert rc == EXIT_OK
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["text"] == "hi"
    assert payload["media"] == []


def test_watch_medium_mode_does_not_call_getfile(env_ready, monkeypatch):
    """watch の Medium モードでも getFile を呼ばない（fetch のみ）。"""
    monkeypatch.setenv("TELEGRAM_SECRETARY_MEDIA_ENABLE_DOWNLOAD", "false")
    monkeypatch.setenv("TELEGRAM_SECRETARY_SESSION_ID", "S-medium-watch")

    def handler(request: httpx.Request) -> httpx.Response:
        assert "getFile" not in str(request.url)
        return httpx.Response(200, json={"ok": True, "result": []})

    _install_mock_transport(monkeypatch, handler)
    assert main(["lease", "acquire"]) == EXIT_OK
    rc = main(["watch", "--timeout", "1", "--max-iterations", "1"])
    assert rc == EXIT_OK
