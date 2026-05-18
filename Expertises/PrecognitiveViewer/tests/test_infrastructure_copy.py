"""Stage 2a Tests — Seimei/I-Ching コピー後の動作と元ファイル無改変を検証する。

計画書 Stage 2 の Success Criteria より:
- test_seimei_engine_loads_after_copy
- test_iching_engine_loads_after_copy
- test_original_seimei_files_intact
- test_original_iching_files_intact（補強）
"""
from __future__ import annotations

import hashlib
from pathlib import Path


PRECOGNITIVE_ROOT = Path(__file__).parent.parent
FORESIGHT_SRC = (
    PRECOGNITIVE_ROOT.parent
    / "CorporateStrategist"
    / "ForesightReader"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_dir_identical(src: Path, dst: Path) -> None:
    """src と dst の全ファイルが SHA256 で一致することを assert する"""
    assert src.exists(), f"元ディレクトリが見つからない: {src}"
    assert dst.exists(), f"コピー先ディレクトリが見つからない: {dst}"

    for src_file in src.rglob("*"):
        if src_file.is_file():
            rel = src_file.relative_to(src)
            dst_file = dst / rel
            assert dst_file.exists(), f"コピー漏れ: {rel}"
            assert _sha256(src_file) == _sha256(dst_file), f"ハッシュ不一致: {rel}"


# ----------------------------------------------------------------------------
# コピー後動作テスト
# ----------------------------------------------------------------------------


def test_seimei_engine_loads_after_copy() -> None:
    """コピーされた fortune_teller_assessment.py が PrecognitiveViewer 配下で動作する"""
    from fortune_teller_assessment import FortuneTellerAssessment

    assessor = FortuneTellerAssessment()
    result = assessor.assess("山田", "太郎", [3, 5], [4, 9])

    assert "七格" in result
    assert "天格" in result["七格"]
    assert "人格" in result["七格"]
    assert "地格" in result["七格"]


def test_iching_engine_loads_after_copy() -> None:
    """コピーされた iching_divination.py が PrecognitiveViewer 配下で動作する"""
    from iching_divination import IChingDivination

    divination = IChingDivination()
    result = divination.divine("今年の事業展望を観たい", "建設業の主力事業を拡大検討中")

    assert "得卦" in result
    assert "得爻" in result
    assert "番号" in result["得卦"]
    assert "卦辞" in result["得卦"]


# ----------------------------------------------------------------------------
# 元ファイル無改変テスト
# ----------------------------------------------------------------------------


def test_original_seimei_files_intact() -> None:
    """元 ForesightReader/Seimei/ がコピー後も改変されていない"""
    _assert_dir_identical(
        FORESIGHT_SRC / "Seimei",
        PRECOGNITIVE_ROOT / "Seimei",
    )


def test_original_iching_files_intact() -> None:
    """元 ForesightReader/I-Ching/ がコピー後も改変されていない"""
    _assert_dir_identical(
        FORESIGHT_SRC / "I-Ching",
        PRECOGNITIVE_ROOT / "I-Ching",
    )


def test_original_references_intact() -> None:
    """元 ForesightReader/References/ がコピー後も改変されていない"""
    _assert_dir_identical(
        FORESIGHT_SRC / "References",
        PRECOGNITIVE_ROOT / "References",
    )
