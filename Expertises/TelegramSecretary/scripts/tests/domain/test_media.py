from __future__ import annotations

import pytest

from domain.media import MediaAttachment, merge_caption_into_text


# === MediaAttachment.from_photo_api ===

def test_media_from_photo_api_picks_largest_resolution():
    # Telegram 仕様: photo 配列の末尾が最大解像度
    photo_array = [
        {"file_id": "small", "file_size": 1024, "width": 90, "height": 90},
        {"file_id": "medium", "file_size": 8192, "width": 320, "height": 320},
        {"file_id": "large", "file_size": 102400, "width": 1280, "height": 1280},
    ]
    media = MediaAttachment.from_photo_api(photo_array)
    assert media is not None
    assert media.kind == "photo"
    assert media.file_id == "large"
    assert media.size == 102400
    assert media.mime_type == "image/jpeg"


def test_media_from_photo_api_single_resolution():
    photo_array = [{"file_id": "only", "file_size": 4096}]
    media = MediaAttachment.from_photo_api(photo_array)
    assert media is not None
    assert media.file_id == "only"
    assert media.size == 4096
    assert media.mime_type == "image/jpeg"


def test_media_from_photo_api_empty_returns_none():
    assert MediaAttachment.from_photo_api([]) is None


def test_media_from_photo_api_missing_file_size_defaults_to_zero():
    photo_array = [{"file_id": "no_size"}]
    media = MediaAttachment.from_photo_api(photo_array)
    assert media is not None
    assert media.size == 0


# === MediaAttachment.from_document_api ===

def test_media_from_document_api_full():
    document = {
        "file_id": "BQACAgIAA",
        "mime_type": "application/pdf",
        "file_size": 524288,
        "file_name": "contract.pdf",
    }
    media = MediaAttachment.from_document_api(document)
    assert media.kind == "document"
    assert media.file_id == "BQACAgIAA"
    assert media.mime_type == "application/pdf"
    assert media.size == 524288


def test_media_from_document_api_missing_mime_type_falls_back():
    document = {"file_id": "BQACAgIAA", "file_size": 1024}
    media = MediaAttachment.from_document_api(document)
    assert media.mime_type == "application/octet-stream"


def test_media_from_document_api_missing_file_size_defaults_to_zero():
    document = {"file_id": "BQACAgIAA"}
    media = MediaAttachment.from_document_api(document)
    assert media.size == 0


# === merge_caption_into_text ===

def test_merge_caption_into_text_both_present():
    assert merge_caption_into_text("hello", "Look at this") == "Look at this\nhello"


def test_merge_caption_into_text_no_caption():
    assert merge_caption_into_text("hello", None) == "hello"


def test_merge_caption_into_text_no_text():
    assert merge_caption_into_text("", "caption only") == "caption only"


def test_merge_caption_into_text_both_empty():
    assert merge_caption_into_text("", None) == ""


def test_merge_caption_into_text_empty_caption_treated_as_none():
    # caption が空文字も「欠落」として扱う（falsy 統一）
    assert merge_caption_into_text("hello", "") == "hello"


# === Immutability ===

def test_media_attachment_is_immutable():
    media = MediaAttachment(kind="photo", file_id="x", mime_type="image/jpeg", size=100)
    with pytest.raises(AttributeError):
        media.size = 200  # type: ignore[misc]
