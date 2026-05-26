"""Monitor が消費する JSON Lines 形式で `1 update = 1 行` を stdout 出力。"""
from __future__ import annotations

import json
import sys
from typing import TextIO

from usecases.fetch_authorized_updates import NormalizedUpdate


class StdoutEventEmitter:
    """`watch` モード時、認可・正規化済み update を JSON Lines で emit する。

    Monitor ツールがこの行を消費し、Weave が応答ドラフトを起草する。
    """

    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream = stream if stream is not None else sys.stdout

    def emit(self, update: NormalizedUpdate) -> None:
        payload = {
            "update_id": update.update.update_id,
            "chat_id": update.update.chat_id,
            "user_id": update.update.user_id,
            "username": update.update.username,
            "text": update.normalized_text,
            "injection_flags": list(update.injection_flags),
        }
        self._stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self._stream.flush()
