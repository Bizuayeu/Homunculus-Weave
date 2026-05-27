from __future__ import annotations

from pathlib import Path
from typing import Optional

from domain.media import MediaAttachment
from usecases.download_authorized_media import MediaDownloadResult
from usecases.render_authorized_media import RenderAuthorizedMedia

from tests.usecases.fakes import FakeMediaRenderer


def _download_result(
    update_id: int,
    mime_type: str,
    file_id: str = "x",
    skip_reason: Optional[str] = None,
    file_name: Optional[str] = None,
) -> MediaDownloadResult:
    """テスト用 helper: kind は mime から推定して MediaDownloadResult を組む。"""
    kind = "photo" if mime_type.startswith("image/") else "document"
    media = MediaAttachment(
        kind=kind,
        file_id=file_id,
        mime_type=mime_type,
        size=1024,
        file_name=file_name,
    )
    local_path = None if skip_reason else Path(f"/tmp/media/{file_id}.bin")
    return MediaDownloadResult(
        update_id=update_id,
        media=media,
        local_path=local_path,
        skip_reason=skip_reason,
    )


# === passthrough（Read tool が直接対応する形式）===

def test_image_jpeg_is_passthrough_without_renderer_call():
    dr = _download_result(1, "image/jpeg")
    renderer = FakeMediaRenderer()
    uc = RenderAuthorizedMedia(renderer)
    results = uc.execute([dr])

    assert len(results) == 1
    assert results[0].rendered.render_status == "passthrough"
    assert results[0].rendered.rendered_text is None
    assert renderer.render_calls == []


def test_image_png_is_passthrough():
    dr = _download_result(1, "image/png")
    renderer = FakeMediaRenderer()
    uc = RenderAuthorizedMedia(renderer)
    results = uc.execute([dr])
    assert results[0].rendered.render_status == "passthrough"
    assert renderer.render_calls == []


def test_pdf_is_passthrough():
    dr = _download_result(1, "application/pdf")
    renderer = FakeMediaRenderer()
    uc = RenderAuthorizedMedia(renderer)
    results = uc.execute([dr])
    assert results[0].rendered.render_status == "passthrough"
    assert renderer.render_calls == []


def test_plain_text_is_passthrough():
    """text/plain は Read tool が直接対応するため markitdown を通す必要なし。"""
    dr = _download_result(1, "text/plain")
    renderer = FakeMediaRenderer()
    uc = RenderAuthorizedMedia(renderer)
    results = uc.execute([dr])
    assert results[0].rendered.render_status == "passthrough"
    assert renderer.render_calls == []


def test_markdown_is_passthrough():
    dr = _download_result(1, "text/markdown")
    renderer = FakeMediaRenderer()
    uc = RenderAuthorizedMedia(renderer)
    results = uc.execute([dr])
    assert results[0].rendered.render_status == "passthrough"


def test_json_is_passthrough():
    dr = _download_result(1, "application/json")
    renderer = FakeMediaRenderer()
    uc = RenderAuthorizedMedia(renderer)
    results = uc.execute([dr])
    assert results[0].rendered.render_status == "passthrough"


# === render（markitdown で md 化）===

def test_docx_calls_renderer():
    dr = _download_result(
        1,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    renderer = FakeMediaRenderer(rendered_text="# docx 内容\n", render_status="ok")
    uc = RenderAuthorizedMedia(renderer)
    results = uc.execute([dr])

    assert results[0].rendered.render_status == "ok"
    assert results[0].rendered.rendered_text == "# docx 内容\n"
    assert len(renderer.render_calls) == 1


def test_pptx_calls_renderer():
    dr = _download_result(
        1,
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
    renderer = FakeMediaRenderer(rendered_text="# pptx スライド\n", render_status="ok")
    uc = RenderAuthorizedMedia(renderer)
    results = uc.execute([dr])
    assert results[0].rendered.render_status == "ok"
    assert len(renderer.render_calls) == 1


def test_xlsx_calls_renderer():
    dr = _download_result(
        1,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    renderer = FakeMediaRenderer(rendered_text="| col |\n", render_status="ok")
    uc = RenderAuthorizedMedia(renderer)
    results = uc.execute([dr])
    assert results[0].rendered.render_status == "ok"


def test_html_calls_renderer():
    """text/html は md 化に整形価値があるので render 経路。"""
    dr = _download_result(1, "text/html")
    renderer = FakeMediaRenderer()
    uc = RenderAuthorizedMedia(renderer)
    results = uc.execute([dr])
    assert results[0].rendered.render_status == "ok"
    assert len(renderer.render_calls) == 1


# === skipped（未対応 mime / audio/video / 未知）===

def test_audio_is_skipped():
    dr = _download_result(1, "audio/mpeg")
    renderer = FakeMediaRenderer()
    uc = RenderAuthorizedMedia(renderer)
    results = uc.execute([dr])
    assert results[0].rendered.render_status == "skipped"
    assert renderer.render_calls == []


def test_video_is_skipped():
    dr = _download_result(1, "video/mp4")
    renderer = FakeMediaRenderer()
    uc = RenderAuthorizedMedia(renderer)
    results = uc.execute([dr])
    assert results[0].rendered.render_status == "skipped"


def test_unknown_mime_is_skipped():
    """未知 mime は保守的に skipped（Weave に「読めない」を正直に渡す）。"""
    dr = _download_result(1, "application/octet-stream")
    renderer = FakeMediaRenderer()
    uc = RenderAuthorizedMedia(renderer)
    results = uc.execute([dr])
    assert results[0].rendered.render_status == "skipped"
    assert renderer.render_calls == []


def test_zip_archive_is_skipped():
    dr = _download_result(1, "application/zip")
    renderer = FakeMediaRenderer()
    uc = RenderAuthorizedMedia(renderer)
    results = uc.execute([dr])
    assert results[0].rendered.render_status == "skipped"


# === download skip 継承（size 超過等） ===

def test_skip_reason_propagates_to_render_skipped():
    """download 段階で skip された media（size 超過等）は render も skip。"""
    dr = _download_result(
        1,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        skip_reason="media_size_exceeded",
    )
    renderer = FakeMediaRenderer()
    uc = RenderAuthorizedMedia(renderer)
    results = uc.execute([dr])

    assert results[0].rendered.render_status == "skipped"
    assert results[0].skip_reason == "media_size_exceeded"  # 継承
    assert results[0].local_path is None
    assert renderer.render_calls == []  # download 失敗時は render も呼ばない


# === 複数 + 空 ===

def test_processes_multiple_download_results_in_one_call():
    drs = [
        _download_result(1, "image/jpeg", file_id="img"),
        _download_result(
            2,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            file_id="docx",
        ),
        _download_result(3, "audio/mpeg", file_id="audio"),
    ]
    renderer = FakeMediaRenderer()
    uc = RenderAuthorizedMedia(renderer)
    results = uc.execute(drs)

    assert len(results) == 3
    assert results[0].rendered.render_status == "passthrough"  # image
    assert results[1].rendered.render_status == "ok"  # docx
    assert results[2].rendered.render_status == "skipped"  # audio
    assert len(renderer.render_calls) == 1  # docx だけ


def test_empty_download_results_returns_empty():
    renderer = FakeMediaRenderer()
    uc = RenderAuthorizedMedia(renderer)
    assert uc.execute([]) == []


# === file_name / メタの引き継ぎ ===

def test_file_name_is_carried_through_render_result():
    """RenderResult が MediaAttachment の file_name を保持していること。"""
    dr = _download_result(
        1,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        file_id="docx",
        file_name="specification.docx",
    )
    renderer = FakeMediaRenderer()
    uc = RenderAuthorizedMedia(renderer)
    results = uc.execute([dr])
    assert results[0].media.file_name == "specification.docx"
