"""Telegram update / outbound message の値オブジェクト。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class TelegramUpdate:
    """getUpdates で取得した update を正規化した Domain 表現。"""

    update_id: int
    chat_id: int
    user_id: int
    username: Optional[str]
    text: str
    raw: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: Mapping[str, Any]) -> "TelegramUpdate":
        """Telegram Bot API の update JSON から構築。最小限のフィールドのみ抽出。"""
        message = payload.get("message") or payload.get("edited_message") or {}
        chat = message.get("chat") or {}
        from_user = message.get("from") or {}
        return cls(
            update_id=int(payload["update_id"]),
            chat_id=int(chat.get("id", 0)),
            user_id=int(from_user.get("id", 0)),
            username=from_user.get("username"),
            text=message.get("text") or "",
            raw=payload,
        )


@dataclass(frozen=True)
class OutboundMessage:
    """Weave 起草の送信メッセージ。"""

    chat_id: int
    text: str
    reply_to_message_id: Optional[int] = None
