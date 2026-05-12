from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

from adapters.mail.gmail_api_mail_gateway import GmailApiMailGateway
from adapters.rss.rss_xml_gateway import RssXmlGateway
from adapters.state.json_state_store import JsonStateStore
from domain.config import DigestConfig
from domain.exceptions import AuthError, MailSendError, RssFetchError
from usecases.run_daily_digest import RunDailyDigestUseCase, RunOutcome, RunResult

JST = ZoneInfo("Asia/Tokyo")

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_CONFIG = 2
EXIT_AUTH = 3


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="newscaster",
        description="ナルエビちゃんニュース 前日ダイジェスト配信",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("run", help="Fetch RSS, filter yesterday, send email")
    sub.add_parser("dry-run", help="Same as run but skip sending and state mark")
    sub.add_parser("test", help="Send a single test email to verify Gmail")
    sub.add_parser("validate-config", help="Check required environment variables")
    return parser


def _build_run_usecase(config: DigestConfig) -> RunDailyDigestUseCase:
    rss = RssXmlGateway(rss_url=config.rss_url, user_agent=config.user_agent)
    mail = GmailApiMailGateway(
        oauth_token_path=config.oauth_token_path,
        oauth_token_json=config.oauth_token_json,
        retry_count=config.retry_count,
    )
    state = JsonStateStore(state_dir=config.state_dir)
    return RunDailyDigestUseCase(
        rss_gateway=rss,
        mail_gateway=mail,
        state_store=state,
        sender=config.sender,
        recipient=config.recipient,
    )


def _print_config_errors(errors: list[str]) -> None:
    print("Configuration errors:", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)


def _cmd_run(*, dry_run: bool) -> int:
    config = DigestConfig.load()
    errors = config.validate()
    if errors:
        _print_config_errors(errors)
        return EXIT_CONFIG

    uc = _build_run_usecase(config)
    now = datetime.now(JST)
    try:
        outcome = uc.execute(now=now, dry_run=dry_run)
    except AuthError as e:
        print(f"Auth error: {e}", file=sys.stderr)
        return EXIT_AUTH
    except RssFetchError as e:
        print(f"RSS fetch error: {e}", file=sys.stderr)
        return EXIT_ERROR
    except MailSendError as e:
        print(f"Mail send error: {e}", file=sys.stderr)
        return EXIT_ERROR

    _print_outcome(outcome)
    return EXIT_OK


def _print_outcome(outcome: RunOutcome) -> None:
    result = outcome.result
    target = outcome.target_date
    if result == RunResult.SENT:
        n = len(outcome.digest.items) if outcome.digest else 0
        print(f"sent: {target} digest delivered ({n} items)")
    elif result == RunResult.NO_ITEMS:
        print(f"no_items: {target} had no entries (silence)")
    elif result == RunResult.ALREADY_SENT:
        print(f"already_sent: {target} digest was already delivered")
    elif result == RunResult.DRY_RUN:
        print(f"[dry-run] {target} digest formatted (mail/state skipped)")
        print("--- subject ---")
        print(outcome.digest.formatted_subject if outcome.digest else "")
        print("--- body ---")
        print(outcome.digest.formatted_body if outcome.digest else "")


def _cmd_test() -> int:
    config = DigestConfig.load()
    errors = config.validate()
    if errors:
        _print_config_errors(errors)
        return EXIT_CONFIG

    mail = GmailApiMailGateway(
        oauth_token_path=config.oauth_token_path,
        oauth_token_json=config.oauth_token_json,
        retry_count=config.retry_count,
    )
    now_jst = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST")
    try:
        mail.send(
            sender=config.sender,
            to=config.recipient,
            subject=f"[NewsCaster test] {now_jst}",
            body=(
                "NewsCaster test email\n"
                f"sent_at: {now_jst}\n"
                f"sender: {config.sender}\n"
                f"recipient: {config.recipient}\n"
                f"rss_url: {config.rss_url}\n"
            ),
        )
    except AuthError as e:
        print(f"Auth error: {e}", file=sys.stderr)
        return EXIT_AUTH
    except MailSendError as e:
        print(f"Mail send error: {e}", file=sys.stderr)
        return EXIT_ERROR
    print(f"Test email sent to {config.recipient}")
    return EXIT_OK


def _cmd_validate_config() -> int:
    config = DigestConfig.load()
    errors = config.validate()
    if errors:
        _print_config_errors(errors)
        return EXIT_CONFIG
    print("Configuration OK")
    print(f"  sender:    {config.sender}")
    print(f"  recipient: {config.recipient}")
    print(f"  rss_url:   {config.rss_url}")
    print(f"  state_dir: {config.state_dir}")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "run":
        return _cmd_run(dry_run=False)
    if args.command == "dry-run":
        return _cmd_run(dry_run=True)
    if args.command == "test":
        return _cmd_test()
    if args.command == "validate-config":
        return _cmd_validate_config()
    return EXIT_CONFIG


if __name__ == "__main__":
    sys.exit(main())
