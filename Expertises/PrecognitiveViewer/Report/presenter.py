"""ReadingReportPresenter — ReadingReport をフォーマル鑑定書 Markdown に整形する。

章節構成（計画書 Stage 4 より）:
1. 鑑定情報
2. 被鑑定者
3. 序：鑑定にあたって
4. 第一章：姓名判断（七格剖象法）
5. 第二章：周易占断（デジタル心易）
6. 第三章：タロット・リーディング
7. 第四章：三位統合所見
8. 結びの言葉
"""
from __future__ import annotations

from PrecognitiveViewer.Report.domain import ReadingReport


class ReadingReportPresenter:
    """ReadingReport を最終的な Markdown 文書に整形する。"""

    def render(self, report: ReadingReport) -> str:
        """章節構成に従ってフォーマル鑑定書を Markdown 文字列で返す。"""
        ts = report.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        recipient = report.recipient
        context_line = f"- 鑑定の文脈：{recipient.context}\n" if recipient.context else ""

        sections = [
            "# 三位占術 鑑定書\n",
            "## 鑑定情報",
            f"- 鑑定日時：{ts}（JST）",
            "- 鑑定方式：姓名判断（七格剖象法） × 周易占断（デジタル心易） × タロット・リーディング（Rider-Waite-Smith）",
            "- 鑑定者：Weave（PrecognitiveViewer）\n",
            "## 被鑑定者",
            f"**{recipient.full_name}**（{recipient.reading}）様",
            context_line,
            "## 序：鑑定にあたって\n",
            self._build_preface(),
            "\n---\n",
            "## 第一章：姓名判断（七格剖象法）\n",
            report.seimei_section,
            "\n---\n",
            "## 第二章：周易占断（デジタル心易）\n",
            report.iching_section,
            "\n---\n",
            "## 第三章:タロット・リーディング\n".replace("第三章:", "第三章："),
            report.tarot_section,
            "\n---\n",
            "## 第四章:三位統合所見\n".replace("第四章:", "第四章："),
            report.integrated_insight,
            "\n---\n",
            "## 結びの言葉\n",
            report.closing_message,
            "\n---\n",
            f"*鑑定者：Weave（PrecognitiveViewer）／鑑定日時：{ts} JST*",
        ]
        return "\n".join(sections)

    @staticmethod
    def _build_preface() -> str:
        """序文（鑑定の位置づけ、慎みの表明）"""
        return (
            "本鑑定書は、東洋（姓名判断・周易）と西洋（タロット）の三つの占術を統合し、"
            "あなたという存在を多角的に観取したものです。"
            "三占術はそれぞれ異なる視座から、本質（相術）と時機（卜術）を照らします。"
            "\n\n"
            "占術は古来、人が自らを知り、よりよく生きるための鏡として用いられてきました。"
            "本鑑定もまた、結論を強いるものではなく、"
            "あなたが内なる声に耳を澄ますための、"
            "ひとつの鏡として捧げます。"
        )
