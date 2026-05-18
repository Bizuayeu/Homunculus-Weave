"""ReadingReportComposerUseCase — 三位占術統合からフォーマル鑑定書を構築する。

各セクションは LLM 解釈レイヤーが後で補完する「骨格」を生成する。
具体的な解釈・物語化はテンプレ内コメント `<!-- LLM 補完 -->` で明示し、
Claude が実行時に上書きする設計。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from PrecognitiveViewer.Report.domain import (
    DivinationTriplet,
    ReadingReport,
    Recipient,
)


class ReadingReportComposerUseCase:
    """フォーマル鑑定書 Composer。三占術統合から骨格 ReadingReport を構築する。"""

    def compose(
        self,
        triplet: DivinationTriplet,
        recipient: Recipient,
        timestamp: datetime,
    ) -> ReadingReport:
        """三占術統合結果と被鑑定者情報から ReadingReport を構築する。"""
        return ReadingReport(
            recipient=recipient,
            timestamp=timestamp,
            seimei_section=self._build_seimei_section(triplet.seimei_summary),
            iching_section=self._build_iching_section(triplet.iching_summary),
            tarot_section=self._build_tarot_section(triplet.tarot_summary),
            integrated_insight=self._build_integrated_insight(triplet),
            closing_message=self._build_closing_message(recipient),
        )

    # ------------------------------------------------------------------------
    # 第一章：姓名判断
    # ------------------------------------------------------------------------

    def _build_seimei_section(self, summary: dict) -> str:
        """七格・星導分布・人材4類型を Markdown 骨格に整形する"""
        lines: list[str] = []

        # 七格テーブル
        lines.append("### 七格星導分析\n")
        lines.append("| 格名 | 画数 | 吉凶 / 数霊 | 星導 |")
        lines.append("|------|------|------------|------|")
        frames = summary.get("七格", {})
        for fname in ["天格", "人格", "地格", "総格", "外格", "雲格", "底格"]:
            f = frames.get(fname, {})
            if not f:
                continue
            # 数霊は番号で表示（数霊名は内部に保持されない）
            seirei = f.get("数霊")
            seirei_disp = f"数霊{seirei}" if seirei is not None else "-"
            lines.append(
                f"| {fname} | {f.get('数', '-')}画 "
                f"| {f.get('吉凶', '-')} / {seirei_disp} "
                f"| 系数{f.get('系数', '-')}={f.get('系数星導', '-')} / "
                f"秘数{f.get('秘数', '-')}={f.get('秘数星導', '-')} |"
            )

        # 星導分布
        star_dist = summary.get("星導分布", {})
        if star_dist:
            lines.append("\n### 星導分布（七格から抽出された 14 天体）\n")
            lines.append("```")
            for star, count in star_dist.items():
                stars = "★" * count if count > 0 else "-"
                lines.append(f"{star}：{stars} ({count})")
            lines.append("```")

        # 人材4類型（既存エンジンのキー名は "軍人度・天才度・秀才度・凡人度"）
        personnel = summary.get("人材4類型", {})
        if personnel:
            lines.append("\n### 人材類型分析（星導の重み）\n")
            for ptype in ["軍人度", "天才度", "秀才度", "凡人度"]:
                count = personnel.get(ptype, 0)
                stars = "★" * count if count > 0 else "-"
                # 表示時は "軍人度" → "軍人型" に整形
                display_name = ptype.replace("度", "型")
                lines.append(f"- {display_name}：{stars} ({count})")
            # 主導類型を抽出（"軍人度" → "軍人型"）
            dominant_key, _dominant_count = max(personnel.items(), key=lambda x: x[1])
            dominant_display = dominant_key.replace("度", "型")
            lines.append(f"\n**主導類型**：{dominant_display}")

        lines.append("\n<!-- LLM 補完：星導・数霊・十干を踏まえた人物像の本質、強みと資質を、純粋エネルギー論の語彙で記述。慎みを保ちつつ相手の尊厳を尊重 -->")

        return "\n".join(lines)

    # ------------------------------------------------------------------------
    # 第二章：周易占断
    # ------------------------------------------------------------------------

    def _build_iching_section(self, summary: dict) -> str:
        """得卦・得爻と卦辞・爻辞を Markdown に整形する"""
        lines: list[str] = []

        question = summary.get("占的", "")
        if question:
            lines.append(f"### 占的\n\n> {question}\n")

        context = summary.get("状況整理", "")
        if context:
            lines.append(f"### 状況整理\n\n{context}\n")

        hexagram = summary.get("得卦", {})
        if hexagram:
            lines.append(
                f"### 得卦：第{hexagram.get('番号', '-')}卦"
                f" {hexagram.get('名前', '-')}"
                f"（{hexagram.get('読み', '-')}）"
                f" {hexagram.get('シンボル', '')}\n"
            )
            upper = hexagram.get("上卦", {})
            lower = hexagram.get("下卦", {})
            if upper:
                lines.append(
                    f"- 上卦：{upper.get('名前', '-')}"
                    f"（{upper.get('象意', '-')}）— {upper.get('性質', '-')}"
                )
            if lower:
                lines.append(
                    f"- 下卦：{lower.get('名前', '-')}"
                    f"（{lower.get('象意', '-')}）— {lower.get('性質', '-')}"
                )
            ket = hexagram.get("卦辞", "")
            if ket:
                lines.append(f"\n**卦辞**\n\n> {ket}")

        yao = summary.get("得爻", {})
        if yao:
            lines.append(
                f"\n### 得爻：第{yao.get('番号', '-')}爻"
                f" {yao.get('名前', '-')}"
                f"（{yao.get('陰陽', '-')}爻）\n"
            )
            yt = yao.get("爻辞", "")
            if yt:
                lines.append(f"**爻辞**\n\n> {yt}")

        lines.append("\n<!-- LLM 補完：卦辞・爻辞の和訳と現代的解釈、現況分析、展開予測、時機判断、行動の指針を記述 -->")

        return "\n".join(lines)

    # ------------------------------------------------------------------------
    # 第三章：タロット・リーディング
    # ------------------------------------------------------------------------

    def _build_tarot_section(self, summary: dict) -> str:
        """スプレッドと引かれたカードを Markdown に整形する"""
        lines: list[str] = []

        # リーディング様式（占的なし対応を明示）
        question = summary.get("question", "")
        spread_name = summary.get("spread_name", "")
        focus = summary.get("spread_focus", "")

        lines.append(f"### リーディング様式\n\n- スプレッド：{spread_name}")
        if focus:
            lines.append(f"- 主題：{focus}")
        if question:
            lines.append(f"- 占的：{question}")
        else:
            lines.append("- 占的：（指定なし／第三者代理引き・人物リーディング）")

        # 引かれたカード
        drawn = summary.get("drawn_cards", [])
        if drawn:
            lines.append("\n### 引かれたカード\n")
            for d in drawn:
                position = d.get("position_name", f"位置{d.get('position', '-')}")
                name = d.get("name", "-")
                orientation = "逆位置" if d.get("is_reversed") else "正位置"
                keywords = "、".join(d.get("keywords", []))
                meaning = d.get("meaning", "")
                lines.append(f"#### {position}：{name}（{orientation}）")
                if keywords:
                    lines.append(f"- キーワード：{keywords}")
                if meaning:
                    lines.append(f"- 意味：{meaning}")
                lines.append("")

        lines.append("<!-- LLM 補完：各位置のカードを物語として読み解き、全体の流れを記述。純粋エネルギー論の語彙で（凶札という発想を採らない） -->")

        return "\n".join(lines)

    # ------------------------------------------------------------------------
    # 第四章：三位統合所見
    # ------------------------------------------------------------------------

    def _build_integrated_insight(self, triplet: DivinationTriplet) -> str:
        """4 部構成の統合所見の骨格を構築する"""
        lines: list[str] = []

        lines.append("### 共通テーマ\n")
        lines.append("<!-- LLM 補完：三占術が共通して指し示す核心を 2-3 段落で記述。相術と卜術が同じ方向を指す場合は強い示唆として明示 -->\n")

        lines.append("### 補完関係（相術が示す本質と、卜術が照らす時機）\n")
        lines.append("<!-- LLM 補完：姓名判断（相術＝本質）と易・タロット（卜術＝時機）が異なる側面で明らかにする要素を統合的に記述 -->\n")

        lines.append("### 強みと活用の指針\n")
        lines.append("<!-- LLM 補完：純粋エネルギー論に基づく肯定的解釈。「凶」を「高難度エネルギー」「活用の鍵」として記述。相手を喜ばせる発見を含める -->\n")

        lines.append("### 時機と行動の助言\n")
        lines.append("<!-- LLM 補完：易卦の時機判断 + タロットの流れの質感を統合し、具体的行動指針を提示。断言を避け、選択の余地を残す -->\n")

        return "\n".join(lines)

    # ------------------------------------------------------------------------
    # 結びの言葉
    # ------------------------------------------------------------------------

    def _build_closing_message(self, recipient: Recipient) -> str:
        """祝福と慎みを含む結びの言葉の骨格を構築する"""
        lines: list[str] = []
        lines.append("<!-- LLM 補完：被鑑定者への祝福と励まし。三占術が示した本質と時機を踏まえた一人称の言葉 -->\n")
        lines.append(
            "*本鑑定は、占術という古典的な観取の技法に基づく**参考情報**です。"
            "あなたの人生の選択は、いつもご自身の自由意志によるものです。"
            "占いは可能性の一つを示すに過ぎず、最終的な決定の主はあなた自身にあります。*"
        )
        return "\n".join(lines)
