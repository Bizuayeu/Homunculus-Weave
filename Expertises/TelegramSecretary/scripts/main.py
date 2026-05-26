"""TelegramSecretary CLI entrypoint。subcommands を argparse で分岐。"""
from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path
from typing import Sequence

from adapters.state.emitter import StdoutEventEmitter
from adapters.state.json_state_store import JsonLeaseStore, JsonOffsetStore
from adapters.telegram.api_gateway import TelegramApiGateway
from adapters.telegram.media_downloader import TelegramMediaDownloader
from domain.exceptions import AuthFailureError, LeaseConflictError, TelegramSecretaryError
from domain.lease import utc_now
from domain.models import OutboundMessage
from infrastructure.config import Config
from usecases.acquire_lease import AcquireLease
from usecases.download_authorized_media import DownloadAuthorizedMedia
from usecases.fetch_authorized_updates import FetchAuthorizedUpdates
from usecases.release_lease import ReleaseLease
from usecases.renew_lease import RenewLease
from usecases.send_reply import SendReply


EXIT_OK = 0
EXIT_FETCH_FAILED = 1
EXIT_CONFIG_INVALID = 2
EXIT_AUTH_FAILED = 3
EXIT_LEASE_CONFLICT = 4


def _load_config() -> Config | int:
    try:
        return Config.from_env()
    except EnvironmentError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return EXIT_CONFIG_INVALID


def _session_owner(arg_owner: str | None) -> str:
    return (
        arg_owner
        or os.environ.get("TELEGRAM_SECRETARY_SESSION_ID")
        or f"session-{uuid.uuid4().hex[:8]}"
    )


def cmd_validate_config(_: argparse.Namespace) -> int:
    config = _load_config()
    if isinstance(config, int):
        return config
    print(
        f"ok: bot_token=set "
        f"authorized_chats={len(config.authorized_chats.chat_ids)} "
        f"state_dir={config.state_dir}"
    )
    return EXIT_OK


def cmd_lease(args: argparse.Namespace) -> int:
    config = _load_config()
    if isinstance(config, int):
        return config
    store = JsonLeaseStore(config.state_dir)
    owner = _session_owner(args.owner)
    now = utc_now()
    try:
        if args.action == "acquire":
            lease = AcquireLease(store).execute(owner=owner, now=now, ttl_seconds=args.ttl)
            print(f"acquired owner={lease.owner} ttl={lease.ttl_seconds}")
        elif args.action == "renew":
            lease = RenewLease(store).execute(owner=owner, now=now)
            print(f"renewed owner={lease.owner} heartbeat={lease.heartbeat.isoformat()}")
        elif args.action == "release":
            ReleaseLease(store).execute(owner=owner)
            print(f"released owner={owner}")
    except LeaseConflictError as exc:
        print(f"lease conflict: {exc}", file=sys.stderr)
        return EXIT_LEASE_CONFLICT
    return EXIT_OK


def cmd_poll(args: argparse.Namespace) -> int:
    config = _load_config()
    if isinstance(config, int):
        return config

    offset_store = JsonOffsetStore(config.state_dir)
    emitter = StdoutEventEmitter()
    download_results: list = []
    with TelegramApiGateway(bot_token=config.bot_token) as gateway:
        uc = FetchAuthorizedUpdates(gateway, offset_store, config.authorized_chats)
        try:
            updates = uc.execute(timeout_seconds=args.timeout)
        except AuthFailureError as exc:
            print(f"auth failure: {exc}", file=sys.stderr)
            return EXIT_AUTH_FAILED
        except TelegramSecretaryError as exc:
            print(f"fetch failed: {exc}", file=sys.stderr)
            return EXIT_FETCH_FAILED

        # Heavy モード: media を持つ update があれば download
        if config.media_enable_download and any(u.update.media for u in updates):
            with TelegramMediaDownloader(
                bot_token=config.bot_token, gateway=gateway
            ) as downloader:
                download_results = DownloadAuthorizedMedia(downloader).execute(
                    updates,
                    config.state_dir / "media",
                    config.media_max_size_bytes,
                )

    for u in updates:
        emitter.emit(u, download_results=download_results)
    return EXIT_OK


def cmd_watch(args: argparse.Namespace) -> int:
    config = _load_config()
    if isinstance(config, int):
        return config

    offset_store = JsonOffsetStore(config.state_dir)
    lease_store = JsonLeaseStore(config.state_dir)
    emitter = StdoutEventEmitter()
    owner = _session_owner(args.owner)
    iterations = 0
    media_target_dir = config.state_dir / "media"

    with TelegramApiGateway(bot_token=config.bot_token) as gateway:
        uc = FetchAuthorizedUpdates(gateway, offset_store, config.authorized_chats)
        renew = RenewLease(lease_store)
        # Heavy モードのみ downloader を loop 外で 1 回作って使い回す（接続コスト削減）
        downloader: TelegramMediaDownloader | None = None
        download_uc: DownloadAuthorizedMedia | None = None
        if config.media_enable_download:
            downloader = TelegramMediaDownloader(
                bot_token=config.bot_token, gateway=gateway
            )
            download_uc = DownloadAuthorizedMedia(downloader)
        try:
            while True:
                try:
                    updates = uc.execute(timeout_seconds=args.timeout)
                except AuthFailureError as exc:
                    print(f"auth failure: {exc}", file=sys.stderr)
                    return EXIT_AUTH_FAILED
                except TelegramSecretaryError as exc:
                    # 一時的エラーはログして次サイクルへ進む
                    print(f"transient fetch error: {exc}", file=sys.stderr)
                else:
                    download_results: list = []
                    if download_uc is not None and any(u.update.media for u in updates):
                        download_results = download_uc.execute(
                            updates,
                            media_target_dir,
                            config.media_max_size_bytes,
                        )
                    for u in updates:
                        emitter.emit(u, download_results=download_results)

                # アイドル時も heartbeat を維持。lease を失っていたら自己治癒で即終了
                try:
                    renew.execute(owner=owner, now=utc_now())
                except LeaseConflictError as exc:
                    print(f"lease lost during watch: {exc}", file=sys.stderr)
                    return EXIT_LEASE_CONFLICT

                iterations += 1
                if args.max_iterations and iterations >= args.max_iterations:
                    break
        finally:
            if downloader is not None:
                downloader.close()
    return EXIT_OK


def cmd_send_reply(args: argparse.Namespace) -> int:
    config = _load_config()
    if isinstance(config, int):
        return config

    owner = _session_owner(args.owner)
    text = Path(args.text_file).read_text(encoding="utf-8")
    offset_store = JsonOffsetStore(config.state_dir)
    lease_store = JsonLeaseStore(config.state_dir)
    lease = lease_store.load()
    if lease is None:
        print("no active lease (acquire first)", file=sys.stderr)
        return EXIT_LEASE_CONFLICT
    if lease.owner != owner:
        # 自分以外の owner の lease で送信しようとしている (運用律 B 案: env 経由で統一)
        print(
            f"lease owned by {lease.owner!r}, not {owner!r} — refusing send",
            file=sys.stderr,
        )
        return EXIT_LEASE_CONFLICT

    with TelegramApiGateway(bot_token=config.bot_token) as gateway:
        try:
            SendReply(gateway, offset_store, lease_store).execute(
                message=OutboundMessage(chat_id=args.chat_id, text=text),
                update_id=args.update_id,
                lease=lease,
                now=utc_now(),
            )
        except AuthFailureError as exc:
            print(f"auth failure: {exc}", file=sys.stderr)
            return EXIT_AUTH_FAILED
        except TelegramSecretaryError as exc:
            print(f"send failed: {exc}", file=sys.stderr)
            return EXIT_FETCH_FAILED

    print(f"sent chat_id={args.chat_id} update_id={args.update_id}")
    return EXIT_OK


def cmd_test(args: argparse.Namespace) -> int:
    config = _load_config()
    if isinstance(config, int):
        return config

    with TelegramApiGateway(bot_token=config.bot_token) as gateway:
        try:
            gateway.send(OutboundMessage(chat_id=args.chat_id, text=args.text))
        except AuthFailureError as exc:
            print(f"auth failure: {exc}", file=sys.stderr)
            return EXIT_AUTH_FAILED
        except TelegramSecretaryError as exc:
            print(f"send failed: {exc}", file=sys.stderr)
            return EXIT_FETCH_FAILED
    print(f"ping sent chat_id={args.chat_id}")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="telegram-secretary")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate-config", help="env vars と設定の検証 (exit 0=OK / 2=設定欠損)")

    p_lease = sub.add_parser("lease", help="リースの取得/更新/解放")
    p_lease.add_argument("action", choices=["acquire", "renew", "release"])
    p_lease.add_argument("--owner", help="session owner id (省略時は env か uuid 生成)")
    p_lease.add_argument("--ttl", type=int, default=300, help="TTL seconds (default 300)")

    p_poll = sub.add_parser("poll", help="getUpdates 1 サイクル")
    p_poll.add_argument("--timeout", type=int, default=30, help="long-poll timeout seconds")

    p_watch = sub.add_parser("watch", help="バックグラウンド long-poll ループ")
    p_watch.add_argument("--timeout", type=int, default=30)
    p_watch.add_argument("--owner", help="session owner id (lease renew 用、省略時は env か uuid)")
    p_watch.add_argument(
        "--max-iterations",
        type=int,
        default=0,
        help="0=無限ループ (Cloud Routine 常駐用), >0 はテスト用",
    )

    p_send = sub.add_parser("send-reply", help="Weave 起草の返信を送信")
    p_send.add_argument("--chat-id", type=int, required=True)
    p_send.add_argument("--update-id", type=int, required=True)
    p_send.add_argument("--text-file", required=True)
    p_send.add_argument("--owner", help="session owner id (lease 検証用、省略時は env か uuid)")

    p_test = sub.add_parser("test", help="疎通テスト：owner chat に ping 送信")
    p_test.add_argument("--chat-id", type=int, required=True)
    p_test.add_argument("--text", default="ping from TelegramSecretary")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "validate-config": cmd_validate_config,
        "lease": cmd_lease,
        "poll": cmd_poll,
        "watch": cmd_watch,
        "send-reply": cmd_send_reply,
        "test": cmd_test,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
