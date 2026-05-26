from __future__ import annotations

from unittest.mock import patch

import pytest

from datetime import datetime
from zoneinfo import ZoneInfo

from domain.config import DigestConfig
from domain.digest import DailyDigest
from domain.models import NewsItem
from usecases.run_daily_digest import RunOutcome, RunResult

JST = ZoneInfo("Asia/Tokyo")


@pytest.fixture(autouse=True)
def reset_config_and_env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    DigestConfig.reset()
    for key in (
        "NEWSCASTER_RSS_URL",
        "NEWSCASTER_SENDER_EMAIL",
        "NEWSCASTER_RECIPIENT_EMAIL",
        "NEWSCASTER_OAUTH_TOKEN_PATH",
        "NEWSCASTER_OAUTH_TOKEN_JSON",
        "NEWSCASTER_STATE_DIR",
    ):
        monkeypatch.delenv(key, raising=False)
    yield
    DigestConfig.reset()


def test_validate_config_returns_2_when_missing():
    from main import main

    rc = main(["validate-config"])
    assert rc == 2


def test_validate_config_returns_0_when_complete(monkeypatch, tmp_path):
    monkeypatch.setenv("NEWSCASTER_SENDER_EMAIL", "from@example.com")
    monkeypatch.setenv("NEWSCASTER_RECIPIENT_EMAIL", "to@example.com")
    monkeypatch.setenv("NEWSCASTER_OAUTH_TOKEN_PATH", str(tmp_path / "t.json"))
    monkeypatch.setenv("NEWSCASTER_STATE_DIR", str(tmp_path / "state"))
    from main import main

    rc = main(["validate-config"])
    assert rc == 0


def test_run_returns_2_when_config_missing():
    from main import main

    rc = main(["run"])
    assert rc == 2


def test_dry_run_does_not_send_mail(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("NEWSCASTER_SENDER_EMAIL", "from@example.com")
    monkeypatch.setenv("NEWSCASTER_RECIPIENT_EMAIL", "to@example.com")
    monkeypatch.setenv("NEWSCASTER_OAUTH_TOKEN_PATH", str(tmp_path / "t.json"))
    monkeypatch.setenv("NEWSCASTER_STATE_DIR", str(tmp_path / "state"))

    item = NewsItem(
        title="TestTitle",
        link="https://news.nullevi.app/x",
        guid="https://news.nullevi.app/x",
        pub_date_jst=datetime(2026, 5, 11, 12, 0, 0, tzinfo=JST),
        description="BodyText",
        categories=("AI",),
        source_name="ナルエビちゃんニュース",
    )
    digest = DailyDigest(
        target_date="2026-05-11",
        items=(item,),
        formatted_subject="件名X",
        formatted_body="本文Y",
    )
    outcome = RunOutcome(
        result=RunResult.DRY_RUN, target_date="2026-05-11", digest=digest
    )

    with patch("main.RunDailyDigestUseCase.execute", return_value=outcome):
        from main import main

        rc = main(["dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "dry-run" in out
    assert "件名X" in out
    assert "本文Y" in out


def test_run_handles_rss_fetch_error(monkeypatch, tmp_path):
    monkeypatch.setenv("NEWSCASTER_SENDER_EMAIL", "from@example.com")
    monkeypatch.setenv("NEWSCASTER_RECIPIENT_EMAIL", "to@example.com")
    monkeypatch.setenv("NEWSCASTER_OAUTH_TOKEN_PATH", str(tmp_path / "t.json"))

    from domain.exceptions import RssFetchError

    with patch(
        "main.RunDailyDigestUseCase.execute",
        side_effect=RssFetchError("403", status_code=403),
    ):
        from main import main

        rc = main(["run"])
    assert rc == 1


def test_run_handles_auth_error_returns_3(monkeypatch, tmp_path):
    monkeypatch.setenv("NEWSCASTER_SENDER_EMAIL", "from@example.com")
    monkeypatch.setenv("NEWSCASTER_RECIPIENT_EMAIL", "to@example.com")
    monkeypatch.setenv("NEWSCASTER_OAUTH_TOKEN_PATH", str(tmp_path / "t.json"))

    from domain.exceptions import AuthError

    with patch(
        "main.RunDailyDigestUseCase.execute",
        side_effect=AuthError("token expired"),
    ):
        from main import main

        rc = main(["run"])
    assert rc == 3


# ----- Stage 5d: send-rendered subcommand -----


def _set_required_env(monkeypatch, tmp_path):
    monkeypatch.setenv("NEWSCASTER_SENDER_EMAIL", "from@example.com")
    monkeypatch.setenv("NEWSCASTER_RECIPIENT_EMAIL", "to@example.com")
    monkeypatch.setenv("NEWSCASTER_OAUTH_TOKEN_PATH", str(tmp_path / "t.json"))
    monkeypatch.setenv("NEWSCASTER_STATE_DIR", str(tmp_path / "state"))


def test_send_rendered_returns_0_on_success(monkeypatch, tmp_path):
    _set_required_env(monkeypatch, tmp_path)
    from usecases.send_rendered import SendRenderedResult

    with patch(
        "main.SendRenderedUseCase.execute",
        return_value=SendRenderedResult.SENT,
    ):
        from main import main

        rc = main(
            [
                "send-rendered",
                "--target-date",
                "2026-05-11",
                "--subject",
                "件名X",
                "--body",
                "本文Y",
            ]
        )
    assert rc == 0


def test_send_rendered_returns_0_when_already_sent(monkeypatch, tmp_path):
    _set_required_env(monkeypatch, tmp_path)
    from usecases.send_rendered import SendRenderedResult

    with patch(
        "main.SendRenderedUseCase.execute",
        return_value=SendRenderedResult.ALREADY_SENT,
    ):
        from main import main

        rc = main(
            [
                "send-rendered",
                "--target-date",
                "2026-05-11",
                "--subject",
                "件名",
                "--body",
                "本文",
            ]
        )
    assert rc == 0


def test_send_rendered_refuses_placeholder_returns_1(monkeypatch, tmp_path):
    _set_required_env(monkeypatch, tmp_path)
    from usecases.send_rendered import SendRenderedResult

    with patch(
        "main.SendRenderedUseCase.execute",
        return_value=SendRenderedResult.PLACEHOLDER_REMAINS,
    ):
        from main import main

        rc = main(
            [
                "send-rendered",
                "--target-date",
                "2026-05-11",
                "--subject",
                "件名",
                "--body",
                "プレースホルダ残り {{WEAVE_COMPACT:x}}",
            ]
        )
    assert rc == 1


def test_send_rendered_supports_body_file(monkeypatch, tmp_path):
    _set_required_env(monkeypatch, tmp_path)
    body_file = tmp_path / "body.txt"
    body_file.write_text("ファイル経由の本文", encoding="utf-8")

    captured = {}

    def fake_execute(self, *, target_date, subject, body):
        captured["body"] = body
        captured["subject"] = subject
        from usecases.send_rendered import SendRenderedResult

        return SendRenderedResult.SENT

    with patch("main.SendRenderedUseCase.execute", new=fake_execute):
        from main import main

        rc = main(
            [
                "send-rendered",
                "--target-date",
                "2026-05-11",
                "--subject",
                "件名",
                "--body-file",
                str(body_file),
            ]
        )
    assert rc == 0
    assert captured["body"] == "ファイル経由の本文"
    assert captured["subject"] == "件名"


def test_send_rendered_handles_auth_error_returns_3(monkeypatch, tmp_path):
    _set_required_env(monkeypatch, tmp_path)
    from domain.exceptions import AuthError

    with patch(
        "main.SendRenderedUseCase.execute",
        side_effect=AuthError("token expired"),
    ):
        from main import main

        rc = main(
            [
                "send-rendered",
                "--target-date",
                "2026-05-11",
                "--subject",
                "件名",
                "--body",
                "本文",
            ]
        )
    assert rc == 3
