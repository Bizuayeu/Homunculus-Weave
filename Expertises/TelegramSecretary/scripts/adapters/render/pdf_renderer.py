"""pdfplumber + pypdfium2 で PDF を二経路 render する MediaRenderer Port 実装（Stage 10 → 11）。

テキスト層がある PDF: pdfplumber でページ毎に抽出し `--- page N ---` 境界マーカーを挿入して
rendered_text に載せ render_status="ok"（Weave が「第 N 条は何ページ」を追える）。page_count も付す。

テキスト層が空/薄い PDF（スキャン・図面 PDF）: pypdfium2 で全ページを画像化（cap 内）し、
派生 png のパスを derived_image_paths に載せて rendered_text=""・render_status="ok"。
Weave は ROUTINE_PROMPT Step 5 で先頭1枚を Read/Vision → page_count で総量把握 → 段階判断
（画像化＝決定論・安い はコード、Vision＝高い・判断 は親プロセス Weave、L00473 分業）。

派生画像は local_path.parent（=state_dir/media/）フラット直下に file_id プレフィックスで保存し、
既存 cleanup_media_dir の retention にそのまま乗せる（サブディレクトリを切ると retention から漏れ
機密スキャン画像が残存する）。

例外は内部 catch → render_status="failed"（markitdown_renderer / moonshine_transcriber 同型、
クラッシュしない）。例外メッセージの絶対パス・file_id 全文は秘匿し、stderr に file_id[:8] のみ短く出す。

pdfplumber / pypdfium2 は遅延 import（Cloud Routine 起動を軽く保ち validate-config / Medium モード
では不要）。pypdfium2・Pillow は pdfplumber>=0.11 の依存として同梱（新規依存ゼロ・システムバイナリ不要、
Stage 11.1 で transitive 実測確認）。

mime-routing は UseCase 側（render_authorized_media._route_mime）が担い、
ここに来た時点で render 対象（application/pdf）は確定している。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List

from domain.media import MediaAttachment, RenderedMedia


class PdfRenderer:
    """PDF テキスト層 → マーカー入り text / スキャン PDF → 全ページ画像（MediaRenderer Port 実装）。

    `RenderAuthorizedMedia` の pdf_renderer として注入。watch ループでは loop 外で
    1 インスタンス作り使い回す。pdfplumber / pypdfium2 import は lazy（初回の実 render 時）。
    """

    def __init__(self, image_max_pages: int = 20) -> None:
        # 画像 PDF を全ページ画像化する際の安全弁（超多ページの disk/トークン暴走防止）。
        # 常時の段階化装置ではなく事故防止＝default は緩め。Weave の総量把握は page_count（総数）で行う。
        self._image_max_pages = image_max_pages

    def render(self, media: MediaAttachment, local_path: Path) -> RenderedMedia:
        """PDF を二経路で render。テキスト層あり→マーカー本文、空/薄い→全ページ画像化。失敗は flag 化。"""
        try:
            import pdfplumber

            page_texts: List[str] = []
            with pdfplumber.open(str(local_path)) as pdf:
                for page in pdf.pages:
                    page_texts.append(page.extract_text() or "")
            page_count = len(page_texts)

            if any(t.strip() for t in page_texts):
                # テキスト経路: ページ境界マーカーを挿入（Weave の位置把握用）
                marked = "\n".join(
                    f"--- page {i + 1} ---\n{t}" for i, t in enumerate(page_texts)
                )
                return RenderedMedia(
                    rendered_text=marked.strip(),
                    render_status="ok",
                    page_count=page_count,
                )

            # 画像経路: テキスト層が空（スキャン・図面 PDF）→ pypdfium2 で全ページ画像化（cap 内）
            derived = self._rasterize(media, local_path)
            return RenderedMedia(
                rendered_text="",
                render_status="ok",
                derived_image_paths=derived,
                page_count=page_count,
            )
        except Exception:
            safe_id = media.file_id[:8]
            print(
                f"[pdf-renderer] failed to render file_id={safe_id}",
                file=sys.stderr,
            )
            return RenderedMedia(rendered_text=None, render_status="failed")

    def _rasterize(self, media: MediaAttachment, local_path: Path) -> List[str]:
        """全ページを cap 内で png 化し、保存先パス（str）の list を返す。

        派生画像は local_path.parent（=state_dir/media/）フラット直下に file_id プレフィックス命名で
        保存（既存 cleanup_media_dir の is_file() フラット retention にそのまま乗る）。scale=2.0 は
        ~144dpi 相当で Vision 可読。例外は呼び出し元 render() の except に伝播させ failed 化する。
        """
        import pypdfium2

        target_dir = local_path.parent
        prefix = media.file_id[:16]
        paths: List[str] = []
        pdf = pypdfium2.PdfDocument(str(local_path))
        try:
            n = min(len(pdf), self._image_max_pages)
            for i in range(n):
                bitmap = pdf[i].render(scale=2.0)  # ~144dpi 相当、Vision 可読
                target = target_dir / f"{prefix}_page-{i + 1:03d}.png"
                bitmap.to_pil().save(str(target))
                paths.append(str(target))
        finally:
            pdf.close()
        return paths
