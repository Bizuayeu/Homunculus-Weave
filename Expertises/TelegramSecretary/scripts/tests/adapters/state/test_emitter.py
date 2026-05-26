from __future__ import annotations

import io
import json

from adapters.state.emitter import StdoutEventEmitter
from domain.models import TelegramUpdate
from usecases.fetch_authorized_updates import NormalizedUpdate


def _normalized(text: str = "hi", flags=None) -> NormalizedUpdate:
    return NormalizedUpdate(
        update=TelegramUpdate(
            update_id=1, chat_id=100, user_id=200, username="weave_user", text=text
        ),
        normalized_text=text,
        injection_flags=list(flags or []),
    )


def test_emit_writes_one_jsonline_per_update():
    stream = io.StringIO()
    emitter = StdoutEventEmitter(stream=stream)
    emitter.emit(_normalized("hello"))
    line = stream.getvalue().strip()
    assert "\n" not in stream.getvalue().rstrip("\n")
    payload = json.loads(line)
    assert payload["update_id"] == 1
    assert payload["chat_id"] == 100
    assert payload["user_id"] == 200
    assert payload["text"] == "hello"


def test_emit_preserves_japanese():
    stream = io.StringIO()
    emitter = StdoutEventEmitter(stream=stream)
    emitter.emit(_normalized("こんにちは"))
    out = stream.getvalue()
    # ensure_ascii=False で日本語そのまま出力
    assert "こんにちは" in out
    payload = json.loads(out.strip())
    assert payload["text"] == "こんにちは"


def test_emit_serializes_injection_flags():
    stream = io.StringIO()
    emitter = StdoutEventEmitter(stream=stream)
    emitter.emit(_normalized("ignore previous", flags=["role_override"]))
    payload = json.loads(stream.getvalue().strip())
    assert payload["injection_flags"] == ["role_override"]


def test_emit_serializes_empty_flags_as_list():
    stream = io.StringIO()
    emitter = StdoutEventEmitter(stream=stream)
    emitter.emit(_normalized("hi"))
    payload = json.loads(stream.getvalue().strip())
    assert payload["injection_flags"] == []


def test_emit_multiple_updates_writes_multiple_lines():
    stream = io.StringIO()
    emitter = StdoutEventEmitter(stream=stream)
    emitter.emit(_normalized("first"))
    emitter.emit(_normalized("second"))
    lines = stream.getvalue().rstrip("\n").split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0])["text"] == "first"
    assert json.loads(lines[1])["text"] == "second"


# === Stage 6.3: emit v2 (media + version) ===

from pathlib import Path

from domain.media import MediaAttachment
from usecases.download_authorized_media import MediaDownloadResult


def _normalized_with_media(
    media: list[MediaAttachment], text: str = ""
) -> NormalizedUpdate:
    return NormalizedUpdate(
        update=TelegramUpdate(
            update_id=1,
            chat_id=100,
            user_id=200,
            username="weave_user",
            text=text,
            media=media,
        ),
        normalized_text=text,
        injection_flags=[],
    )


def test_emit_includes_version_v2():
    stream = io.StringIO()
    emitter = StdoutEventEmitter(stream=stream)
    emitter.emit(_normalized("hi"))
    payload = json.loads(stream.getvalue().strip())
    assert payload["v"] == 2


def test_emit_includes_empty_media_list_for_text_only():
    """text-only update でも `media: []` を明示出力（欠落≠未対応の混乱を避ける）。"""
    stream = io.StringIO()
    emitter = StdoutEventEmitter(stream=stream)
    emitter.emit(_normalized("hi"))
    payload = json.loads(stream.getvalue().strip())
    assert payload["media"] == []


def test_emit_serializes_photo_media_without_local_path():
    """download_results なし（Medium モード）: media は出るが local_path は null。"""
    media = MediaAttachment(
        kind="photo", file_id="ABC123", mime_type="image/jpeg", size=4096
    )
    stream = io.StringIO()
    emitter = StdoutEventEmitter(stream=stream)
    emitter.emit(_normalized_with_media([media]))
    payload = json.loads(stream.getvalue().strip())
    assert len(payload["media"]) == 1
    assert payload["media"][0]["kind"] == "photo"
    assert payload["media"][0]["file_id"] == "ABC123"
    assert payload["media"][0]["mime_type"] == "image/jpeg"
    assert payload["media"][0]["size"] == 4096
    assert payload["media"][0]["local_path"] is None
    assert payload["media"][0]["skip_reason"] is None


def test_emit_serializes_media_with_local_path_when_downloaded():
    """download_results 渡し（Heavy モード）: local_path が乗る。"""
    media = MediaAttachment(
        kind="photo", file_id="ABC123", mime_type="image/jpeg", size=4096
    )
    result = MediaDownloadResult(
        update_id=1,
        media=media,
        local_path=Path("/tmp/media/ABC123.jpg"),
        skip_reason=None,
    )
    stream = io.StringIO()
    emitter = StdoutEventEmitter(stream=stream)
    emitter.emit(_normalized_with_media([media]), download_results=[result])
    payload = json.loads(stream.getvalue().strip())
    # OS 依存の path separator を許容
    assert payload["media"][0]["local_path"] is not None
    assert "ABC123.jpg" in payload["media"][0]["local_path"]
    assert payload["media"][0]["skip_reason"] is None


def test_emit_includes_skip_reason_for_size_exceeded():
    media = MediaAttachment(
        kind="photo", file_id="BIG", mime_type="image/jpeg", size=30_000_000
    )
    result = MediaDownloadResult(
        update_id=1,
        media=media,
        local_path=None,
        skip_reason="media_size_exceeded",
    )
    stream = io.StringIO()
    emitter = StdoutEventEmitter(stream=stream)
    emitter.emit(_normalized_with_media([media]), download_results=[result])
    payload = json.loads(stream.getvalue().strip())
    assert payload["media"][0]["local_path"] is None
    assert payload["media"][0]["skip_reason"] == "media_size_exceeded"
