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
