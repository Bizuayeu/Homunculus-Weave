"""Stage 4 Tests — ReadingReportComposer + ReadingReportPresenter + ReportFilenameGenerator。

計画書 Stage 4 Success Criteria より:
- test_filename_format
- test_presenter_renders_all_sections
- test_closing_message_includes_humility_statement
- test_e2e_triple_to_reading_report
"""
from __future__ import annotations

from datetime import datetime

from PrecognitiveViewer.Report.composer_usecase import (
    ReadingReportComposerUseCase,
)
from PrecognitiveViewer.Report.domain import (
    DivinationTriplet,
    DrawnCard,
    ReadingReport,
    Recipient,
    SpreadDefinition,
    TarotCard,
    TarotReading,
)
from PrecognitiveViewer.Report.filename import ReportFilenameGenerator
from PrecognitiveViewer.Report.presenter import ReadingReportPresenter
from PrecognitiveViewer.Report.triple_divination import TripleDivinationUseCase


def _make_sample_triplet() -> DivinationTriplet:
    """テスト用の最小限の DivinationTriplet を構築する"""
    seimei = {
        "姓": {"①山": 3, "②田": 5},
        "名": {"①太": 4, "②郎": 9},
        "七格": {
            "天格": {"数": 8, "数霊名": "発展", "吉凶": "吉", "系数": 8, "秘数": 8, "系数星導": "土星", "秘数星導": "土星", "象意": "発展する力", "十干": "辛", "五行": "金"},
            "人格": {"数": 9, "数霊名": "頂点", "吉凶": "吉", "系数": 9, "秘数": 9, "系数星導": "火星", "秘数星導": "火星", "象意": "頂点", "十干": "壬", "五行": "水"},
            "地格": {"数": 13, "数霊名": "知性", "吉凶": "吉", "系数": 3, "秘数": 4, "系数星導": "木星", "秘数星導": "水星", "象意": "知性", "十干": "丙", "五行": "火"},
            "総格": {"数": 21, "数霊名": "完成", "吉凶": "吉", "系数": 1, "秘数": 3, "系数星導": "太陽", "秘数星導": "木星", "象意": "完成", "十干": "甲", "五行": "木"},
            "外格": {"数": 12, "数霊名": "美", "吉凶": "凶", "系数": 2, "秘数": 3, "系数星導": "月", "秘数星導": "木星", "象意": "美", "十干": "乙", "五行": "木"},
            "雲格": {"数": 17, "数霊名": "勇気", "吉凶": "吉", "系数": 7, "秘数": 8, "系数星導": "金星", "秘数星導": "土星", "象意": "勇気", "十干": "庚", "五行": "金"},
            "底格": {"数": 22, "数霊名": "停滞", "吉凶": "凶", "系数": 2, "秘数": 4, "系数星導": "月", "秘数星導": "水星", "象意": "停滞", "十干": "乙", "五行": "木"},
        },
        "星導分布": {"太陽": 1, "月": 2, "水星": 2, "金星": 1, "火星": 2, "木星": 3, "土星": 3, "天王星": 0, "海王星": 0, "冥王星": 0},
        "人材4類型": {"軍人度": 3, "天才度": 0, "秀才度": 8, "凡人度": 7},
    }
    iching = {
        "占機": {"日時": "2026-05-18 14:30:00", "タイムスタンプ": 1747573800.0},
        "占的": "今年の事業展望を観たい",
        "状況整理": "建設業の新規事業を立ち上げ検討中",
        "得卦": {
            "番号": 1,
            "名前": "乾為天",
            "読み": "けんいてん",
            "シンボル": "☰☰",
            "バイナリ": "111111",
            "卦辞": "元亨利貞",
            "上卦": {"名前": "乾", "象意": "天", "性質": "剛健"},
            "下卦": {"名前": "乾", "象意": "天", "性質": "剛健"},
        },
        "得爻": {
            "番号": 5,
            "名前": "九五",
            "陰陽": "陽",
            "爻辞": "飛龍在天利見大人",
        },
    }
    tarot = TarotReading(
        spread=SpreadDefinition(
            name="past_present_future",
            positions=("過去", "現在", "未来"),
            focus="時間軸の流れ",
        ),
        drawn_cards=(
            DrawnCard(
                card=TarotCard(
                    id="major-19",
                    name="太陽",
                    arcana="major",
                    number=19,
                    keywords=("輝き", "成功", "喜び"),
                    upright_meaning="明晰な成功、純粋な喜び",
                    reversed_meaning="曇った成功",
                ),
                is_reversed=False,
                position=0,
            ),
            DrawnCard(
                card=TarotCard(
                    id="major-07",
                    name="戦車",
                    arcana="major",
                    number=7,
                    keywords=("意志", "前進"),
                    upright_meaning="意志による前進",
                    reversed_meaning="暴走",
                ),
                is_reversed=False,
                position=1,
            ),
            DrawnCard(
                card=TarotCard(
                    id="major-21",
                    name="世界",
                    arcana="major",
                    number=21,
                    keywords=("完成", "達成"),
                    upright_meaning="周期の完成、全体性",
                    reversed_meaning="未完了",
                ),
                is_reversed=False,
                position=2,
            ),
        ),
        question="今年の事業展望",
        context="建設業の新規事業",
        timestamp=datetime(2026, 5, 18, 14, 30, 0),
    )
    return TripleDivinationUseCase().synthesize(seimei, iching, tarot)


# ----------------------------------------------------------------------------
# ReportFilenameGenerator
# ----------------------------------------------------------------------------


def test_filename_format() -> None:
    """ReadingReport_yyyymmdd_hhmmss.md 形式"""
    ts = datetime(2026, 5, 18, 14, 30, 15)
    fname = ReportFilenameGenerator.generate(ts)
    assert fname == "ReadingReport_20260518_143015.md"


def test_filename_format_zero_padded() -> None:
    """月日時分秒がゼロ埋めされる"""
    ts = datetime(2026, 1, 5, 9, 7, 3)
    fname = ReportFilenameGenerator.generate(ts)
    assert fname == "ReadingReport_20260105_090703.md"


# ----------------------------------------------------------------------------
# Composer
# ----------------------------------------------------------------------------


def test_composer_returns_reading_report() -> None:
    """ReadingReportComposerUseCase が ReadingReport 型を返す"""
    triplet = _make_sample_triplet()
    recipient = Recipient(full_name="山田太郎", reading="やまだたろう")
    usecase = ReadingReportComposerUseCase()
    report = usecase.compose(triplet, recipient, datetime(2026, 5, 18, 14, 30, 0))

    assert isinstance(report, ReadingReport)
    assert report.recipient.full_name == "山田太郎"


def test_composer_seimei_section_contains_seven_frames() -> None:
    """第一章セクションに七格の主要キーワードが含まれる"""
    triplet = _make_sample_triplet()
    recipient = Recipient(full_name="山田太郎", reading="やまだたろう")
    report = ReadingReportComposerUseCase().compose(triplet, recipient, datetime.now())

    text = report.seimei_section
    for frame_name in ["天格", "人格", "地格", "総格", "外格"]:
        assert frame_name in text


def test_composer_iching_section_contains_hexagram_name() -> None:
    """第二章セクションに卦名が含まれる"""
    triplet = _make_sample_triplet()
    recipient = Recipient(full_name="山田太郎", reading="やまだたろう")
    report = ReadingReportComposerUseCase().compose(triplet, recipient, datetime.now())

    assert "乾為天" in report.iching_section


def test_composer_tarot_section_contains_card_names() -> None:
    """第三章セクションに引かれたカード名が含まれる"""
    triplet = _make_sample_triplet()
    recipient = Recipient(full_name="山田太郎", reading="やまだたろう")
    report = ReadingReportComposerUseCase().compose(triplet, recipient, datetime.now())

    text = report.tarot_section
    assert "太陽" in text
    assert "戦車" in text
    assert "世界" in text


def test_composer_integrated_insight_has_four_subsections() -> None:
    """第四章に 4 部構成（共通テーマ・補完関係・強みと活用・時機と行動）がある"""
    triplet = _make_sample_triplet()
    recipient = Recipient(full_name="山田太郎", reading="やまだたろう")
    report = ReadingReportComposerUseCase().compose(triplet, recipient, datetime.now())

    text = report.integrated_insight
    for sub in ["共通テーマ", "補完関係", "強みと活用", "時機と行動"]:
        assert sub in text


def test_closing_message_includes_humility_statement() -> None:
    """結びの言葉に慎みの語彙（自由意志/参考情報/ご自身のいずれか）が含まれる"""
    triplet = _make_sample_triplet()
    recipient = Recipient(full_name="山田太郎", reading="やまだたろう")
    report = ReadingReportComposerUseCase().compose(triplet, recipient, datetime.now())

    msg = report.closing_message
    assert any(kw in msg for kw in ["自由意志", "参考情報", "ご自身"])


# ----------------------------------------------------------------------------
# Presenter
# ----------------------------------------------------------------------------


def test_presenter_renders_all_sections() -> None:
    """Presenter 出力に章節構成がすべて出現する"""
    triplet = _make_sample_triplet()
    recipient = Recipient(full_name="山田太郎", reading="やまだたろう")
    report = ReadingReportComposerUseCase().compose(triplet, recipient, datetime(2026, 5, 18, 14, 30, 0))
    markdown = ReadingReportPresenter().render(report)

    expected_sections = [
        "鑑定情報",
        "被鑑定者",
        "序：鑑定にあたって",
        "第一章：姓名判断",
        "第二章：周易占断",
        "第三章：タロット・リーディング",
        "第四章：三位統合所見",
        "結びの言葉",
    ]
    # 各章節がこの順序で出現することを確認
    last_pos = -1
    for section in expected_sections:
        pos = markdown.find(section)
        assert pos != -1, f"セクション {section} が見つからない"
        assert pos > last_pos, f"セクション {section} の順序が不正"
        last_pos = pos


def test_presenter_includes_recipient_name() -> None:
    """Presenter 出力に被鑑定者の名前と読みが含まれる"""
    triplet = _make_sample_triplet()
    recipient = Recipient(full_name="山田太郎", reading="やまだたろう")
    report = ReadingReportComposerUseCase().compose(triplet, recipient, datetime.now())
    markdown = ReadingReportPresenter().render(report)

    assert "山田太郎" in markdown
    assert "やまだたろう" in markdown


def test_presenter_includes_formatted_timestamp() -> None:
    """Presenter 出力に YYYY-MM-DD HH:MM:SS 形式の鑑定日時が含まれる"""
    triplet = _make_sample_triplet()
    recipient = Recipient(full_name="山田太郎", reading="やまだたろう")
    report = ReadingReportComposerUseCase().compose(triplet, recipient, datetime(2026, 5, 18, 14, 30, 15))
    markdown = ReadingReportPresenter().render(report)

    assert "2026-05-18 14:30:15" in markdown


# ----------------------------------------------------------------------------
# E2E
# ----------------------------------------------------------------------------


def test_e2e_triple_to_reading_report() -> None:
    """三占術 → DivinationTriplet → ReadingReport → Markdown 全工程"""
    triplet = _make_sample_triplet()
    recipient = Recipient(
        full_name="山田太郎",
        reading="やまだたろう",
        context="今年の事業展望を観たい",
    )
    ts = datetime(2026, 5, 18, 14, 30, 15)

    report = ReadingReportComposerUseCase().compose(triplet, recipient, ts)
    markdown = ReadingReportPresenter().render(report)
    filename = ReportFilenameGenerator.generate(ts)

    assert filename == "ReadingReport_20260518_143015.md"
    assert markdown.startswith("# 三位占術 鑑定書")
    # 三占術それぞれの情報が含まれる
    assert "乾為天" in markdown
    assert "太陽" in markdown
    assert "戦車" in markdown
