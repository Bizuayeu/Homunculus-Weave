"""Monitor が消費する JSON Lines 形式で `1 update = 1 行` を stdout 出力。"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional, Sequence, TextIO

from usecases.download_authorized_media import MediaDownloadResult
from usecases.fetch_authorized_updates import NormalizedUpdate

PAYLOAD_VERSION = 2


class StdoutEventEmitter:
    """`watch` モード時、認可・正規化済み update を JSON Lines で emit する。

    Stage 6.3: `v: 2` + `media[]` 拡張。download_results を渡せば local_path / skip_reason が乗る。
    Monitor ツールがこの行を消費し、Weave が応答ドラフトを起草する。
    """

    def __init__(self, stream: Optional[TextIO] = None) -> None:
        self._stream = stream if stream is not None else sys.stdout

    def emit(
        self,
        update: NormalizedUpdate,
        download_results: Optional[Sequence[MediaDownloadResult]] = None,
    ) -> None:
        media_payload = self._build_media_payload(update, download_results or [])
        payload: Dict[str, Any] = {
            "v": PAYLOAD_VERSION,
            "update_id": update.update.update_id,
            "chat_id": update.update.chat_id,
            "user_id": update.update.user_id,
            "username": update.update.username,
            "text": update.normalized_text,
            "injection_flags": list(update.injection_flags),
            "media": media_payload,
        }
        self._stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self._stream.flush()

    def _build_media_payload(
        self,
        update: NormalizedUpdate,
        download_results: Sequence[MediaDownloadResult],
    ) -> List[Dict[str, Any]]:
        """update.update.media を JSON 化、対応する download_result があれば
        local_path / skip_reason を埋める。"""
        own_results = {
            r.media.file_id: r
            for r in download_results
            if r.update_id == update.update.update_id
        }
        out: List[Dict[str, Any]] = []
        for media in update.update.media:
            result = own_results.get(media.file_id)
            local_path = (
                str(result.local_path)
                if result is not None and result.local_path is not None
                else None
            )
            skip_reason = result.skip_reason if result is not None else None
            out.append(
                {
                    "kind": media.kind,
                    "file_id": media.file_id,
                    "mime_type": media.mime_type,
                    "size": media.size,
                    "local_path": local_path,
                    "skip_reason": skip_reason,
                }
            )
        return out
