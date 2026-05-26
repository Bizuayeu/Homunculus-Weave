from __future__ import annotations

import pytest

from domain.config import DEFAULT_FEED_NAME, DEFAULT_RSS_URL, DigestConfig
from domain.feed_policy import FeedPolicy


@pytest.fixture(autouse=True)
def reset_and_clean(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    DigestConfig.reset()
    for key in (
        "NEWSCASTER_RSS_URL",
        "NEWSCASTER_FEEDS",
        "NEWSCASTER_SENDER_EMAIL",
        "NEWSCASTER_RECIPIENT_EMAIL",
        "NEWSCASTER_OAUTH_TOKEN_PATH",
        "NEWSCASTER_OAUTH_TOKEN_JSON",
        "NEWSCASTER_OAUTH_CLIENT_SECRET_PATH",
        "NEWSCASTER_STATE_DIR",
        "NEWSCASTER_USER_AGENT",
        "NEWSCASTER_MAIL_RETRY_COUNT",
    ):
        monkeypatch.delenv(key, raising=False)
    yield
    DigestConfig.reset()


def test_load_from_env_vars(monkeypatch, tmp_path):
    token_path = tmp_path / "token.json"
    monkeypatch.setenv("NEWSCASTER_SENDER_EMAIL", "from@example.com")
    monkeypatch.setenv("NEWSCASTER_RECIPIENT_EMAIL", "to@example.com")
    monkeypatch.setenv("NEWSCASTER_OAUTH_TOKEN_PATH", str(token_path))

    cfg = DigestConfig.load()

    assert cfg.sender == "from@example.com"
    assert cfg.recipient == "to@example.com"
    assert cfg.oauth_token_path == token_path
    assert cfg.rss_url == "https://news.nullevi.app/rss"


def test_user_agent_has_default_chrome(monkeypatch, tmp_path):
    monkeypatch.setenv("NEWSCASTER_OAUTH_TOKEN_PATH", str(tmp_path / "t.json"))
    cfg = DigestConfig.load()
    assert "Mozilla" in cfg.user_agent
    assert "Chrome" in cfg.user_agent


def test_user_agent_overridable(monkeypatch, tmp_path):
    monkeypatch.setenv("NEWSCASTER_OAUTH_TOKEN_PATH", str(tmp_path / "t.json"))
    monkeypatch.setenv("NEWSCASTER_USER_AGENT", "MyBot/1.0")
    cfg = DigestConfig.load()
    assert cfg.user_agent == "MyBot/1.0"


def test_rss_url_overridable(monkeypatch, tmp_path):
    monkeypatch.setenv("NEWSCASTER_OAUTH_TOKEN_PATH", str(tmp_path / "t.json"))
    monkeypatch.setenv("NEWSCASTER_RSS_URL", "https://example.com/feed")
    cfg = DigestConfig.load()
    assert cfg.rss_url == "https://example.com/feed"


def test_state_dir_default_under_skill_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("NEWSCASTER_OAUTH_TOKEN_PATH", str(tmp_path / "t.json"))
    cfg = DigestConfig.load()
    assert cfg.state_dir.name == "state"


def test_load_is_singleton(monkeypatch, tmp_path):
    monkeypatch.setenv("NEWSCASTER_SENDER_EMAIL", "from@example.com")
    monkeypatch.setenv("NEWSCASTER_RECIPIENT_EMAIL", "to@example.com")
    monkeypatch.setenv("NEWSCASTER_OAUTH_TOKEN_PATH", str(tmp_path / "t.json"))
    a = DigestConfig.load()
    b = DigestConfig.load()
    assert a is b


def test_validate_returns_errors_when_missing():
    cfg = DigestConfig.load()
    errors = cfg.validate()
    assert any("NEWSCASTER_SENDER_EMAIL" in e for e in errors)
    assert any("NEWSCASTER_RECIPIENT_EMAIL" in e for e in errors)
    assert any("NEWSCASTER_OAUTH_TOKEN" in e for e in errors)


def test_validate_passes_with_token_json_only(monkeypatch):
    monkeypatch.setenv("NEWSCASTER_SENDER_EMAIL", "from@example.com")
    monkeypatch.setenv("NEWSCASTER_RECIPIENT_EMAIL", "to@example.com")
    monkeypatch.setenv(
        "NEWSCASTER_OAUTH_TOKEN_JSON",
        '{"refresh_token": "fake", "client_id": "x", "client_secret": "y"}',
    )
    cfg = DigestConfig.load()
    assert cfg.validate() == []


def test_validate_passes_with_token_path_only(monkeypatch, tmp_path):
    monkeypatch.setenv("NEWSCASTER_SENDER_EMAIL", "from@example.com")
    monkeypatch.setenv("NEWSCASTER_RECIPIENT_EMAIL", "to@example.com")
    monkeypatch.setenv("NEWSCASTER_OAUTH_TOKEN_PATH", str(tmp_path / "t.json"))
    cfg = DigestConfig.load()
    assert cfg.validate() == []


def test_retry_count_default_and_override(monkeypatch, tmp_path):
    monkeypatch.setenv("NEWSCASTER_OAUTH_TOKEN_PATH", str(tmp_path / "t.json"))
    cfg = DigestConfig.load()
    assert cfg.retry_count == 3

    DigestConfig.reset()
    monkeypatch.setenv("NEWSCASTER_MAIL_RETRY_COUNT", "5")
    cfg2 = DigestConfig.load()
    assert cfg2.retry_count == 5


def test_invalid_retry_count_falls_back(monkeypatch, tmp_path):
    monkeypatch.setenv("NEWSCASTER_OAUTH_TOKEN_PATH", str(tmp_path / "t.json"))
    monkeypatch.setenv("NEWSCASTER_MAIL_RETRY_COUNT", "not-a-number")
    cfg = DigestConfig.load()
    assert cfg.retry_count == 3


# ----- Stage 5c: NEWSCASTER_FEEDS resolution -----


def test_feeds_parses_json_array(monkeypatch, tmp_path):
    monkeypatch.setenv("NEWSCASTER_OAUTH_TOKEN_PATH", str(tmp_path / "t.json"))
    monkeypatch.setenv(
        "NEWSCASTER_FEEDS",
        '[{"name":"A","url":"https://a.example/feed","policy":"passthrough"},'
        '{"name":"B","url":"https://b.example/feed","policy":"weave_compact"}]',
    )
    cfg = DigestConfig.load()
    assert cfg.feeds_parse_error is None
    assert len(cfg.feeds) == 2
    assert cfg.feeds[0].name == "A"
    assert cfg.feeds[0].url == "https://a.example/feed"
    assert cfg.feeds[0].policy is FeedPolicy.PASSTHROUGH
    assert cfg.feeds[1].name == "B"
    assert cfg.feeds[1].policy is FeedPolicy.WEAVE_COMPACT


def test_feeds_defaults_policy_to_passthrough(monkeypatch, tmp_path):
    monkeypatch.setenv("NEWSCASTER_OAUTH_TOKEN_PATH", str(tmp_path / "t.json"))
    monkeypatch.setenv(
        "NEWSCASTER_FEEDS",
        '[{"name":"X","url":"https://x.example/feed"}]',
    )
    cfg = DigestConfig.load()
    assert cfg.feeds_parse_error is None
    assert cfg.feeds[0].policy is FeedPolicy.PASSTHROUGH


def test_feeds_backward_compat_rss_url_singular(monkeypatch, tmp_path):
    monkeypatch.setenv("NEWSCASTER_OAUTH_TOKEN_PATH", str(tmp_path / "t.json"))
    monkeypatch.setenv("NEWSCASTER_RSS_URL", "https://example.com/legacy")
    cfg = DigestConfig.load()
    assert cfg.feeds_parse_error is None
    assert len(cfg.feeds) == 1
    assert cfg.feeds[0].name == DEFAULT_FEED_NAME
    assert cfg.feeds[0].url == "https://example.com/legacy"
    assert cfg.feeds[0].policy is FeedPolicy.PASSTHROUGH


def test_feeds_default_when_nothing_set(monkeypatch, tmp_path):
    monkeypatch.setenv("NEWSCASTER_OAUTH_TOKEN_PATH", str(tmp_path / "t.json"))
    cfg = DigestConfig.load()
    assert cfg.feeds_parse_error is None
    assert len(cfg.feeds) == 1
    assert cfg.feeds[0].url == DEFAULT_RSS_URL


def test_validate_reports_invalid_feeds_json(monkeypatch, tmp_path):
    monkeypatch.setenv("NEWSCASTER_SENDER_EMAIL", "from@example.com")
    monkeypatch.setenv("NEWSCASTER_RECIPIENT_EMAIL", "to@example.com")
    monkeypatch.setenv("NEWSCASTER_OAUTH_TOKEN_PATH", str(tmp_path / "t.json"))
    monkeypatch.setenv("NEWSCASTER_FEEDS", "{not valid json")
    cfg = DigestConfig.load()
    errors = cfg.validate()
    assert any("NEWSCASTER_FEEDS" in e and "JSON" in e for e in errors)


def test_validate_reports_invalid_policy_name(monkeypatch, tmp_path):
    monkeypatch.setenv("NEWSCASTER_SENDER_EMAIL", "from@example.com")
    monkeypatch.setenv("NEWSCASTER_RECIPIENT_EMAIL", "to@example.com")
    monkeypatch.setenv("NEWSCASTER_OAUTH_TOKEN_PATH", str(tmp_path / "t.json"))
    monkeypatch.setenv(
        "NEWSCASTER_FEEDS",
        '[{"name":"X","url":"https://x/","policy":"unknown_policy"}]',
    )
    cfg = DigestConfig.load()
    errors = cfg.validate()
    assert any("unknown_policy" in e or "invalid policy" in e for e in errors)


def test_validate_reports_feeds_not_array(monkeypatch, tmp_path):
    monkeypatch.setenv("NEWSCASTER_SENDER_EMAIL", "from@example.com")
    monkeypatch.setenv("NEWSCASTER_RECIPIENT_EMAIL", "to@example.com")
    monkeypatch.setenv("NEWSCASTER_OAUTH_TOKEN_PATH", str(tmp_path / "t.json"))
    monkeypatch.setenv("NEWSCASTER_FEEDS", '{"name":"X","url":"https://x/"}')
    cfg = DigestConfig.load()
    errors = cfg.validate()
    assert any("NEWSCASTER_FEEDS must be a JSON array" in e for e in errors)


def test_validate_reports_empty_feeds_array(monkeypatch, tmp_path):
    monkeypatch.setenv("NEWSCASTER_SENDER_EMAIL", "from@example.com")
    monkeypatch.setenv("NEWSCASTER_RECIPIENT_EMAIL", "to@example.com")
    monkeypatch.setenv("NEWSCASTER_OAUTH_TOKEN_PATH", str(tmp_path / "t.json"))
    monkeypatch.setenv("NEWSCASTER_FEEDS", "[]")
    cfg = DigestConfig.load()
    errors = cfg.validate()
    assert any("empty array" in e for e in errors)


def test_validate_reports_missing_url_field(monkeypatch, tmp_path):
    monkeypatch.setenv("NEWSCASTER_SENDER_EMAIL", "from@example.com")
    monkeypatch.setenv("NEWSCASTER_RECIPIENT_EMAIL", "to@example.com")
    monkeypatch.setenv("NEWSCASTER_OAUTH_TOKEN_PATH", str(tmp_path / "t.json"))
    monkeypatch.setenv("NEWSCASTER_FEEDS", '[{"name":"X"}]')
    cfg = DigestConfig.load()
    errors = cfg.validate()
    assert any("string 'name' and 'url'" in e for e in errors)
