from __future__ import annotations

from domain.models import OutboundMessage, TelegramUpdate


def test_telegram_update_from_api_minimal():
    payload = {
        "update_id": 12345,
        "message": {
            "chat": {"id": 100},
            "from": {"id": 200, "username": "weave_user"},
            "text": "hello",
        },
    }
    update = TelegramUpdate.from_api(payload)
    assert update.update_id == 12345
    assert update.chat_id == 100
    assert update.user_id == 200
    assert update.username == "weave_user"
    assert update.text == "hello"


def test_telegram_update_from_api_handles_missing_text():
    payload = {
        "update_id": 12345,
        "message": {
            "chat": {"id": 100},
            "from": {"id": 200},
        },
    }
    update = TelegramUpdate.from_api(payload)
    assert update.text == ""
    assert update.username is None


def test_telegram_update_from_api_edited_message():
    # edited_message でも同等のパス
    payload = {
        "update_id": 99,
        "edited_message": {
            "chat": {"id": 1},
            "from": {"id": 2},
            "text": "edited",
        },
    }
    update = TelegramUpdate.from_api(payload)
    assert update.text == "edited"
    assert update.chat_id == 1


def test_outbound_message_minimal():
    msg = OutboundMessage(chat_id=100, text="hi")
    assert msg.chat_id == 100
    assert msg.text == "hi"
    assert msg.reply_to_message_id is None


def test_outbound_message_with_reply_to():
    msg = OutboundMessage(chat_id=100, text="hi", reply_to_message_id=42)
    assert msg.reply_to_message_id == 42


def test_telegram_update_is_immutable():
    update = TelegramUpdate(update_id=1, chat_id=1, user_id=1, username=None, text="x")
    import pytest
    with pytest.raises(AttributeError):
        update.text = "y"  # type: ignore[misc]


# === Stage 6.2: media / caption 抽出 ===

def test_telegram_update_from_api_extracts_photo():
    payload = {
        "update_id": 12345,
        "message": {
            "chat": {"id": 100},
            "from": {"id": 200},
            "photo": [
                {"file_id": "small", "file_size": 1024},
                {"file_id": "large", "file_size": 102400},
            ],
        },
    }
    update = TelegramUpdate.from_api(payload)
    assert len(update.media) == 1
    assert update.media[0].kind == "photo"
    assert update.media[0].file_id == "large"
    assert update.media[0].size == 102400


def test_telegram_update_from_api_extracts_document():
    payload = {
        "update_id": 1,
        "message": {
            "chat": {"id": 100},
            "from": {"id": 200},
            "document": {
                "file_id": "BQACAgIAA",
                "mime_type": "application/pdf",
                "file_size": 524288,
            },
        },
    }
    update = TelegramUpdate.from_api(payload)
    assert len(update.media) == 1
    assert update.media[0].kind == "document"
    assert update.media[0].mime_type == "application/pdf"


def test_telegram_update_from_api_extracts_caption():
    payload = {
        "update_id": 1,
        "message": {
            "chat": {"id": 100},
            "from": {"id": 200},
            "caption": "ここを見て",
            "photo": [{"file_id": "x", "file_size": 4096}],
        },
    }
    update = TelegramUpdate.from_api(payload)
    assert update.caption == "ここを見て"
    # text と caption は別フィールドで保持（統合は UseCase 層の責務）
    assert update.text == ""


def test_telegram_update_from_api_text_only_has_empty_media():
    """Stage 6.1 までの既存挙動と後方互換: media は空 list、caption は None。"""
    payload = {
        "update_id": 1,
        "message": {
            "chat": {"id": 100},
            "from": {"id": 200},
            "text": "hello",
        },
    }
    update = TelegramUpdate.from_api(payload)
    assert update.media == []
    assert update.caption is None


def test_telegram_update_from_api_with_both_photo_and_document():
    """photo と document が同一 message に並ぶケース（Telegram では稀だが構造的に可能）。"""
    payload = {
        "update_id": 1,
        "message": {
            "chat": {"id": 100},
            "from": {"id": 200},
            "photo": [{"file_id": "p", "file_size": 1000}],
            "document": {"file_id": "d", "mime_type": "application/pdf", "file_size": 2000},
        },
    }
    update = TelegramUpdate.from_api(payload)
    kinds = [m.kind for m in update.media]
    assert "photo" in kinds
    assert "document" in kinds
