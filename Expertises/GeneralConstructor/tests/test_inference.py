"""Stage 3: 判定ルール（inference.py）のテスト（TDD Red Phase）

WORKFLOW Phase 3.2 の「AI 判断による補完」のうち決定論的なものを固定する。
定数（標準住戸面積）はテーブルから引かず引数で渡す（inference は loader を知らない）。
"""
from decimal import Decimal

import pytest

from python.inference import (
    default_basement,
    default_elevator,
    default_floors,
    default_soil,
    defaults_for,
    estimate_units,
    housing_type,
    road_class,
    small_site,
    vehicle_class,
)


class Test道路区分:
    """道路区分（2026-08-24 裁定: ≤2.5 → 2.5m以下 / >12 → 幹線・バス通り / 他 → 2.5〜8m）"""

    @pytest.mark.parametrize(
        "幅員,期待",
        [
            ("2.5", "2.5m以下"),
            ("2.51", "2.5〜8m"),
            ("12.0", "2.5〜8m"),
            ("12.01", "幹線・バス通り"),
        ],
    )
    def test_road_class_boundaries(self, 幅員, 期待):
        assert road_class(Decimal(幅員)) == 期待


class Test車両と敷地小規模:
    """車両区分（有効宅地 150㎡ 以上が前提）と敷地小規模（80㎡ 以下）"""

    @pytest.mark.parametrize(
        "有効宅地,幅員,期待",
        [
            ("149.99", "3.9", "無"),
            ("150", "3.9", "立米車"),
            ("150", "4.0", "中型車"),
        ],
    )
    def test_vehicle_class(self, 有効宅地, 幅員, 期待):
        assert vehicle_class(Decimal(有効宅地), Decimal(幅員)) == 期待

    @pytest.mark.parametrize("有効宅地,期待", [("80.0", True), ("80.01", False)])
    def test_small_site(self, 有効宅地, 期待):
        assert small_site(Decimal(有効宅地)) is 期待


class Test住宅種別と層数:
    """住宅種別は接道長さ（v2 入力からは退役。判断の引数としてのみ生きる）"""

    @pytest.mark.parametrize(
        "接道長さ,期待", [("3.99", "長屋"), ("4.0", "共同住宅"), ("8", "共同住宅")]
    )
    def test_housing_type(self, 接道長さ, 期待):
        assert housing_type(Decimal(接道長さ)) == 期待

    def test_default_floors(self):
        assert default_floors("長屋") == 3
        assert default_floors("共同住宅") == 4


class Test戸数推定:
    """戸数 = 貸床面積 ÷ 標準住戸面積 を四捨五入（ROUND_HALF_UP）"""

    def test_estimate_units(self):
        # 274.32 ÷ 40 = 6.858 → 7
        assert estimate_units(Decimal("274.32"), Decimal("40")) == 7

    def test_estimate_units_rounds_half_up(self):
        # 260 ÷ 40 = 6.5 → 7（銀行丸めなら 6 になる）
        assert estimate_units(Decimal("260"), Decimal("40")) == 7

    def test_estimate_units_rejects_zero_unit_area(self):
        with pytest.raises(ValueError):
            estimate_units(Decimal("274.32"), Decimal("0"))


class Test既定値:
    """半地下・EV・ソイルの既定（WORKFLOW Phase 3.2 と 2026-08-24 裁定）"""

    def test_default_basement(self):
        assert default_basement("世田谷区") == "半地下無"
        assert default_basement("板橋区") == "半地下有"

    def test_default_elevator(self):
        assert default_elevator(4) == "無"
        assert default_elevator(5) == "6人乗り"

    @pytest.mark.parametrize(
        "地盤評価,幅員,期待",
        [
            ("軟弱地盤", "2.0", "悪条件"),
            ("軟弱地盤", "6.0", "通常"),
            ("中間地盤", "2.0", "無"),
            ("中間地盤①", "2.0", "無"),
            ("硬質地盤", "6.0", "無"),
        ],
    )
    def test_soil_default_for_soft_ground(self, 地盤評価, 幅員, 期待):
        assert default_soil(地盤評価, Decimal(幅員)) == 期待


class TestDefaultsFor:
    """欠損のうち埋められるものだけを提案する（黙って採用はしない）"""

    def test_proposes_only_missing_keys(self):
        提案 = defaults_for(
            {
                "土地所在": "板橋区",
                "接道長さ": Decimal("3.5"),
                "地盤評価": "軟弱地盤",
                "前面道路幅員": Decimal("2.0"),
                "建物層数": 5,  # 指定済みなので提案しない
            }
        )
        assert 提案 == {
            "住宅種別": "長屋",
            "半地下有無": "半地下有",
            "EV": "6人乗り",  # 指定済みの 5 層から導く
            "ソイル": "悪条件",
        }

    def test_does_not_propose_without_source_fields(self):
        """接道長さが無ければ住宅種別を提案しない。外周長は決して提案しない"""
        提案 = defaults_for({"土地所在": "世田谷区", "住宅種別": "共同住宅"})
        assert 提案 == {"半地下有無": "半地下無", "建物層数": 4, "EV": "無"}
        assert "外周長" not in 提案
