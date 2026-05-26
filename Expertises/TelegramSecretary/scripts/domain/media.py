"""メディア添付の Domain 値オブジェクトと caption 統合の純関数。

Stage 6.1: photo / document / caption を Domain 層の純粋型として表現する。
bytes は持たず file_id 等の identifier のみ保持（Infrastructure 層の local_path に閉じ込め）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence


@dataclass(frozen=True)
class MediaAttachment:
    """Telegram message に含まれる photo / document を Domain 表現したもの。"""

    kind: str  # "photo" | "document"
    file_id: str
    mime_type: str
    size: int

    @classmethod
    def from_photo_api(
        cls, photo_array: Sequence[Mapping[str, Any]]
    ) -> Optional["MediaAttachment"]:
        """Telegram の photo 配列（複数解像度）から最大解像度を抽出。

        Telegram API 仕様で配列末尾が最大解像度。空配列なら None を返す。
        photo は常に jpeg（Telegram 側で正規化済み）。
        """
        if not photo_array:
            return None
        largest = photo_array[-1]
        return cls(
            kind="photo",
            file_id=str(largest["file_id"]),
            mime_type="image/jpeg",
            size=int(largest.get("file_size", 0)),
        )

    @classmethod
    def from_document_api(cls, document: Mapping[str, Any]) -> "MediaAttachment":
        """Telegram の document から MediaAttachment を構築。

        mime_type 欠落時は application/octet-stream にフォールバック。
        """
        return cls(
            kind="document",
            file_id=str(document["file_id"]),
            mime_type=document.get("mime_type") or "application/octet-stream",
            size=int(document.get("file_size", 0)),
        )


def merge_caption_into_text(text: str, caption: Optional[str]) -> str:
    """画像/ドキュメントの caption を本文に統合する。

    両方あれば caption + "\\n" + text、片方欠落時は片方のみ、両方欠落時は空文字。
    空文字 caption は欠落として扱う（falsy 統一）。
    """
    if caption and text:
        return f"{caption}\n{text}"
    if caption:
        return caption
    return text or ""
