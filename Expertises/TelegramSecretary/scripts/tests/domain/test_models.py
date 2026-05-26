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
