"""Stage 5 Tests — ドキュメント整備の検証。

計画書 Stage 5 Success Criteria より:
- test_skill_md_frontmatter_valid_yaml
- test_weave_claude_md_lists_precognitive_viewer
- test_corporate_strategist_unchanged
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

PRECOGNITIVE_ROOT = Path(__file__).parent.parent
WEAVE_ROOT = PRECOGNITIVE_ROOT.parent.parent
CORPORATE_STRATEGIST_DIR = PRECOGNITIVE_ROOT.parent / "CorporateStrategist"
FORESIGHT_DIR = CORPORATE_STRATEGIST_DIR / "ForesightReader"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ----------------------------------------------------------------------------
# SKILL.md の frontmatter 検証
# ----------------------------------------------------------------------------


def test_skill_md_exists() -> None:
    """PrecognitiveViewer/SKILL.md が存在する"""
    assert (PRECOGNITIVE_ROOT / "SKILL.md").exists()


def test_skill_md_frontmatter_has_precognitive_viewer_name() -> None:
    """SKILL.md の frontmatter に `name: precognitive-viewer` が含まれる"""
    skill_md = (PRECOGNITIVE_ROOT / "SKILL.md").read_text(encoding="utf-8")
    # frontmatter ブロックを抽出（先頭の --- から次の --- まで）
    m = re.match(r"^---\n(.*?)\n---\n", skill_md, re.DOTALL)
    assert m is not None, "frontmatter ブロックが見つからない"
    frontmatter = m.group(1)
    assert "name: precognitive-viewer" in frontmatter


def test_claude_md_exists() -> None:
    """PrecognitiveViewer/CLAUDE.md が存在する"""
    assert (PRECOGNITIVE_ROOT / "CLAUDE.md").exists()


def test_reading_report_template_exists() -> None:
    """Report/ReadingReportTemplate.md が存在する"""
    assert (PRECOGNITIVE_ROOT / "Report" / "ReadingReportTemplate.md").exists()


def test_tarot_theory_md_exists() -> None:
    """Tarot/タロット占術理論.md が存在する"""
    assert (PRECOGNITIVE_ROOT / "Tarot" / "タロット占術理論.md").exists()


def test_tarot_license_md_exists() -> None:
    """Tarot/LICENSE.md が存在し、tarot-mcp の出典を明示する"""
    license_path = PRECOGNITIVE_ROOT / "Tarot" / "LICENSE.md"
    assert license_path.exists()
    content = license_path.read_text(encoding="utf-8")
    assert "abdul-hamid-achik" in content
    assert "MIT License" in content


# ----------------------------------------------------------------------------
# Weave/CLAUDE.md の更新検証
# ----------------------------------------------------------------------------


def test_weave_claude_md_lists_precognitive_viewer() -> None:
    """homunculus/Weave/CLAUDE.md の Expertises 一覧に PrecognitiveViewer が追記されている"""
    weave_md = (WEAVE_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "PrecognitiveViewer" in weave_md
    # 専門ペルソナ活用セクション配下に存在する
    persona_section = weave_md.split("## 🎭 専門ペルソナ活用")[1] if "## 🎭 専門ペルソナ活用" in weave_md else ""
    assert "PrecognitiveViewer" in persona_section


# ----------------------------------------------------------------------------
# CorporateStrategist 無改変検証（並列進化方針）
# ----------------------------------------------------------------------------


def test_corporate_strategist_skill_md_unchanged_structure() -> None:
    """CorporateStrategist/SKILL.md に ForesightReader が引き続き存在する（無改変方針）"""
    skill_md = (CORPORATE_STRATEGIST_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert "ForesightReader" in skill_md
    # PrecognitiveViewer への言及がないことで「無改変」を担保
    assert "PrecognitiveViewer" not in skill_md, (
        "CorporateStrategist/SKILL.md は無改変方針。"
        "PrecognitiveViewer 言及はここに置かない"
    )


def test_corporate_strategist_claude_md_unchanged_structure() -> None:
    """CorporateStrategist/CLAUDE.md も同様に無改変"""
    claude_md = (CORPORATE_STRATEGIST_DIR / "CLAUDE.md").read_text(encoding="utf-8")
    assert "ForesightReader" in claude_md
    assert "PrecognitiveViewer" not in claude_md, (
        "CorporateStrategist/CLAUDE.md は無改変方針"
    )


def test_foresight_reader_files_present() -> None:
    """ForesightReader 配下のファイルが引き続き存在する（移動ではなくコピーだった証拠）"""
    assert (FORESIGHT_DIR / "SUBSKILL.md").exists()
    assert (FORESIGHT_DIR / "CLAUDE.md").exists()
    assert (FORESIGHT_DIR / "Seimei" / "fortune_teller_assessment.py").exists()
    assert (FORESIGHT_DIR / "I-Ching" / "iching_divination.py").exists()


# ----------------------------------------------------------------------------
# SKILL.md 内容の妥当性
# ----------------------------------------------------------------------------


def test_skill_md_describes_third_party_proxy() -> None:
    """SKILL.md が「第三者代理性」の核心理由に言及している"""
    skill_md = (PRECOGNITIVE_ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "第三者代理" in skill_md or "第三者の代理" in skill_md


def test_skill_md_describes_two_pillars() -> None:
    """SKILL.md が「相と卜の二柱」構成に言及している"""
    skill_md = (PRECOGNITIVE_ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "相と卜" in skill_md or "相術" in skill_md


def test_skill_md_describes_parallel_evolution() -> None:
    """SKILL.md が ForesightReader との並列進化に言及している"""
    skill_md = (PRECOGNITIVE_ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "並列進化" in skill_md
