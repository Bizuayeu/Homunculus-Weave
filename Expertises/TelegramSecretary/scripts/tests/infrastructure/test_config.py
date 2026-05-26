from __future__ import annotations

import pytest

from infrastructure.config import Config


@pytest.fixture(autouse=True)
def base_env(monkeypatch, tmp_path):
    """最低限の env を揃え、media 系は各テストで上書きする。"""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TEST")
    monkeypatch.setenv("TELEGRAM_SECRETARY_AUTHORIZED_CHATS", "[100]")
    monkeypatch.setenv("TELEGRAM_SECRETARY_STATE_DIR", str(tmp_path))
    for k in [
        "TELEGRAM_SECRETARY_MEDIA_MAX_SIZE_BYTES",
        "TELEGRAM_SECRETARY_MEDIA_RETENTION_HOURS",
        "TELEGRAM_SECRETARY_MEDIA_ENABLE_DOWNLOAD",
    ]:
        monkeypatch.delenv(k, raising=False)


def test_config_defaults_when_media_env_missing():
    cfg = Config.from_env()
    assert cfg.media_max_size_bytes == 20 * 1024 * 1024
    assert cfg.media_retention_hours == 24
    assert cfg.media_enable_download is True


def test_config_parses_max_size_bytes(monkeypatch):
    monkeypatch.setenv("TELEGRAM_SECRETARY_MEDIA_MAX_SIZE_BYTES", "5242880")
    cfg = Config.from_env()
    assert cfg.media_max_size_bytes == 5 * 1024 * 1024


def test_config_rejects_non_positive_max_size(monkeypatch):
    monkeypatch.setenv("TELEGRAM_SECRETARY_MEDIA_MAX_SIZE_BYTES", "0")
    with pytest.raises(EnvironmentError):
        Config.from_env()


def test_config_rejects_invalid_max_size(monkeypatch):
    monkeypatch.setenv("TELEGRAM_SECRETARY_MEDIA_MAX_SIZE_BYTES", "not-a-number")
    with pytest.raises(EnvironmentError):
        Config.from_env()


def test_config_parses_retention_hours(monkeypatch):
    monkeypatch.setenv("TELEGRAM_SECRETARY_MEDIA_RETENTION_HOURS", "6")
    cfg = Config.from_env()
    assert cfg.media_retention_hours == 6


def test_config_rejects_non_positive_retention(monkeypatch):
    monkeypatch.setenv("TELEGRAM_SECRETARY_MEDIA_RETENTION_HOURS", "-1")
    with pytest.raises(EnvironmentError):
        Config.from_env()


@pytest.mark.parametrize("value", ["true", "1", "yes", "TRUE", "Yes"])
def test_config_enable_download_truthy_values(monkeypatch, value):
    monkeypatch.setenv("TELEGRAM_SECRETARY_MEDIA_ENABLE_DOWNLOAD", value)
    assert Config.from_env().media_enable_download is True


@pytest.mark.parametrize("value", ["false", "0", "no", "FALSE", "No"])
def test_config_enable_download_falsy_values(monkeypatch, value):
    monkeypatch.setenv("TELEGRAM_SECRETARY_MEDIA_ENABLE_DOWNLOAD", value)
    assert Config.from_env().media_enable_download is False


def test_config_enable_download_invalid_value(monkeypatch):
    monkeypatch.setenv("TELEGRAM_SECRETARY_MEDIA_ENABLE_DOWNLOAD", "maybe")
    with pytest.raises(EnvironmentError):
        Config.from_env()
