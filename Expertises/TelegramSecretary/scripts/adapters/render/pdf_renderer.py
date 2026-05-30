"""pdfplumber で PDF のテキスト層を抽出する MediaRenderer Port 実装（Stage 10.1）。

PDF のテキスト層を抽出して RenderedMedia.rendered_text に乗せ render_status="ok"。
テキスト層が空（スキャン PDF 等、ToUnicode 不備で拾えない場合を含む）でも "ok" + 空文字で
返し、「読めるテキストが無い」ことを Weave に正直に伝える（moonshine の無音 → ok+空 同型）。
例外は内部 catch → render_status="failed"（markitdown_renderer / moonshine_transcriber 同型、
クラッシュしない）。例外メッセージの絶対パス・file_id 全文は秘匿し、stderr に file_id[:8] のみ短く出す。

pdfplumber は遅延 import（Cloud Routine 起動を軽く保ち、validate-config / Medium モードでは不要）。

ライセンス: pdfplumber は MIT（配布安全）。pymupdf(AGPL) は同等の日本語テキスト層抽出品質だが
配布制約（AGPL）のため不採用（IMPLEMENTATION_PLAN Stage 10 Decision Notes 参照）。
PDF render は passthrough（Read tool 依存）からの移行であり、Read tool 非依存で rendered_text に
本文を載せることで Weave への到達経路を一般化する。

mime-routing は UseCase 側（render_authorized_media._route_mime）が担い、
ここに来た時点で render 対象（application/pdf）は確定している。
"""
from __future__ import annotations

import sys
from pathlib import Path

from domain.media import MediaAttachment, RenderedMedia


class PdfRenderer:
    """PDF テキスト層 → text（pdfplumber、MediaRenderer Port 実装）。

    `RenderAuthorizedMedia` の pdf_renderer として注入。watch ループでは loop 外で
    1 インスタンス作り使い回す。pdfplumber import は lazy（初回の実 render 時）。
    """

    def render(self, media: MediaAttachment, local_path: Path) -> RenderedMedia:
        """PDF のテキスト層を抽出。失敗は flag 化、Weave に正直に伝える。"""
        try:
            import pdfplumber

            texts = []
            with pdfplumber.open(str(local_path)) as pdf:
                for page in pdf.pages:
                    texts.append(page.extract_text() or "")
            rendered_text = "\n".join(texts).strip()
            return RenderedMedia(rendered_text=rendered_text, render_status="ok")
        except Exception:
            safe_id = media.file_id[:8]
            print(
                f"[pdf-renderer] failed to render file_id={safe_id}",
                file=sys.stderr,
            )
            return RenderedMedia(rendered_text=None, render_status="failed")
