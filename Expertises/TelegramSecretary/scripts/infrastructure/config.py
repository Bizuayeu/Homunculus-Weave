"""env から設定を読み込むローダ。fail-fast：欠損は EnvironmentError。"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from domain.authorization import AuthorizedChats


@dataclass(frozen=True)
class Config:
    bot_token: str
    authorized_chats: AuthorizedChats
    state_dir: Path

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

        return cls(
            bot_token=token,
            authorized_chats=AuthorizedChats.from_iterable(chat_ids),
            state_dir=state_dir,
        )
