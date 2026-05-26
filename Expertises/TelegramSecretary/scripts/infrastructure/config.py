"""env から設定を読み込むローダ。fail-fast：欠損は EnvironmentError。"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from domain.authorization import AuthorizedChats

DEFAULT_MEDIA_MAX_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB
DEFAULT_MEDIA_RETENTION_HOURS = 24


@dataclass(frozen=True)
class Config:
    bot_token: str
    authorized_chats: AuthorizedChats
    state_dir: Path
    media_max_size_bytes: int = DEFAULT_MEDIA_MAX_SIZE_BYTES
    media_retention_hours: int = DEFAULT_MEDIA_RETENTION_HOURS
    media_enable_download: bool = True

    @classmethod
    def from_env(cls) -> "Config":
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise EnvironmentError("TELEGRAM_BOT_TOKEN is not set")

        chats_raw = os.environ.get("TELEGRAM_SECRETARY_AUTHORIZED_CHATS", "").strip()
        if not chats_raw:
            raise EnvironmentError("TELEGRAM_SECRETARY_AUTHORIZED_CHATS is not set")
        try:
            parsed = json.loads(chats_raw)
        except json.JSONDecodeError as exc:
            raise EnvironmentError(
                f"TELEGRAM_SECRETARY_AUTHORIZED_CHATS must be JSON array of int: {exc}"
            )
        if not isinstance(parsed, list):
            raise EnvironmentError(
                "TELEGRAM_SECRETARY_AUTHORIZED_CHATS must be a JSON array of int"
            )
        try:
            chat_ids: Iterable[int] = [int(c) for c in parsed]
        except (TypeError, ValueError) as exc:
            raise EnvironmentError(
                f"TELEGRAM_SECRETARY_AUTHORIZED_CHATS elements must be ints: {exc}"
            )

        state_dir = Path(os.environ.get("TELEGRAM_SECRETARY_STATE_DIR", "./state")).resolve()

        max_size = cls._parse_positive_int(
            "TELEGRAM_SECRETARY_MEDIA_MAX_SIZE_BYTES",
            default=DEFAULT_MEDIA_MAX_SIZE_BYTES,
        )
        retention = cls._parse_positive_int(
            "TELEGRAM_SECRETARY_MEDIA_RETENTION_HOURS",
            default=DEFAULT_MEDIA_RETENTION_HOURS,
        )
        enable_download = cls._parse_bool(
            "TELEGRAM_SECRETARY_MEDIA_ENABLE_DOWNLOAD",
            default=True,
        )

        return cls(
            bot_token=token,
            authorized_chats=AuthorizedChats.from_iterable(chat_ids),
            state_dir=state_dir,
            media_max_size_bytes=max_size,
            media_retention_hours=retention,
            media_enable_download=enable_download,
        )

    @staticmethod
    def _parse_positive_int(env_name: str, default: int) -> int:
        raw = os.environ.get(env_name, "").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError as exc:
            raise EnvironmentError(
                f"{env_name} must be a positive integer: {exc}"
            )
        if value <= 0:
            raise EnvironmentError(
                f"{env_name} must be > 0 (got {value})"
            )
        return value

    @staticmethod
    def _parse_bool(env_name: str, default: bool) -> bool:
        raw = os.environ.get(env_name, "").strip().lower()
        if not raw:
            return default
        if raw in ("true", "1", "yes"):
            return True
        if raw in ("false", "0", "no"):
            return False
        raise EnvironmentError(
            f"{env_name} must be true/false (got {raw!r})"
        )
