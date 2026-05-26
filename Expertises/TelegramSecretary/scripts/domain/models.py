"""Telegram update / outbound message の値オブジェクト。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Mapping, Optional

from domain.media import MediaAttachment


@dataclass(frozen=True)
class TelegramUpdate:
    """getUpdates で取得した update を正規化した Domain 表現。"""

    update_id: int
    chat_id: int
    user_id: int
    username: Optional[str]
    text: str
    raw: Mapping[str, Any] = field(default_factory=dict)
    media: List[MediaAttachment] = field(default_factory=list)
    caption: Optional[str] = None

    @classmethod
    def from_api(cls, payload: Mapping[str, Any]) -> "TelegramUpdate":
        """Telegram Bot API の update JSON から構築。最小限のフィールドのみ抽出。

        Stage 6.2 拡張: photo / document / caption を抽出する。
        media 配列は photo（最大解像度）→ document の順。
        """
        message = payload.get("message") or payload.get("edited_message") or {}
        chat = message.get("chat") or {}
        from_user = message.get("from") or {}

        media: List[MediaAttachment] = []
        photo_array = message.get("photo")
        if photo_array:
            photo_media = MediaAttachment.from_photo_api(photo_array)
            if photo_media is not None:
                media.append(photo_media)
        document = message.get("document")
        if document:
            media.append(MediaAttachment.from_document_api(document))

        return cls(
            update_id=int(payload["update_id"]),
            chat_id=int(chat.get("id", 0)),
            user_id=int(from_user.get("id", 0)),
            username=from_user.get("username"),
            text=message.get("text") or "",
            raw=payload,
            media=media,
            caption=message.get("caption"),
        )


@dataclass(frozen=True)
class OutboundMessage:
    """Weave 起草の送信メッセージ。"""

    chat_id: int
    text: str
    reply_to_message_id: Optional[int] = None
