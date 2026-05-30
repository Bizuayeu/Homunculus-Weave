from __future__ import annotations

from pathlib import Path

from domain.media import MediaAttachment
from adapters.render.pdf_renderer import PdfRenderer


def _make_pdf(path: Path, lines, font: str = "Helvetica") -> None:
    """テキスト層を持つ PDF を reportlab で動的生成（fixture を git に置かない方針）。

    font="Helvetica" は ASCII 用。日本語は CID フォント名を渡す（呼び出し側で登録）。
    """
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path))
    c.setFont(font, 14)
    y = 800
    for ln in lines:
        c.drawString(50, y, ln)
        y -= 24
    c.showPage()
    c.save()


def _make_blank_pdf(path: Path) -> None:
    """テキスト層ゼロ（スキャン PDF 相当）の空ページ PDF。"""
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path))
    c.showPage()
    c.save()


def _pdf(file_id: str = "p") -> MediaAttachment:
    return MediaAttachment(
        kind="document",
        file_id=file_id,
        mime_type="application/pdf",
        size=100,
        file_name="doc.pdf",
    )


def test_extracts_text_layer_returns_ok(tmp_path):
    """テキスト層のある PDF → ok + 抽出テキスト（pdfplumber）。"""
    pdf = tmp_path / "ascii.pdf"
    _make_pdf(pdf, ["Hello PDF Stage 10", "second line of body"])
    result = PdfRenderer().render(_pdf(), pdf)
    assert result.render_status == "ok"
    assert result.rendered_text is not None
    assert "Hello PDF Stage 10" in result.rendered_text
    assert "second line of body" in result.rendered_text


def test_japanese_text_layer(tmp_path):
    """日本語テキスト層 → ok + 日本語抽出（CID フォント、smoke test 同型）。"""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
    pdf = tmp_path / "jp.pdf"
    _make_pdf(pdf, ["日本語のテキスト層", "二行目の本文"], font="HeiseiKakuGo-W5")
    result = PdfRenderer().render(_pdf(), pdf)
    assert result.render_status == "ok"
    assert "日本語のテキスト層" in result.rendered_text


def test_empty_text_layer_returns_ok_empty(tmp_path):
    """テキスト層ゼロ（スキャン PDF 等）→ ok + 空文字（Weave に正直に、moonshine 同型）。"""
    pdf = tmp_path / "blank.pdf"
    _make_blank_pdf(pdf)
    result = PdfRenderer().render(_pdf(), pdf)
    assert result.render_status == "ok"
    assert result.rendered_text == ""


def test_failed_on_broken_pdf(tmp_path):
    """壊れた / PDF でないバイト列 → failed（クラッシュさせず Weave に正直に）。"""
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"this is not a pdf at all \x00\x01\x02")
    result = PdfRenderer().render(_pdf("abcdef1234"), broken)
    assert result.render_status == "failed"
    assert result.rendered_text is None


def test_failed_on_missing_file(tmp_path):
    """存在しないファイル → failed（FileNotFoundError を内部 catch）。"""
    result = PdfRenderer().render(_pdf(), tmp_path / "nope.pdf")
    assert result.render_status == "failed"
    assert result.rendered_text is None
