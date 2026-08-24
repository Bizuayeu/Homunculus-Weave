"""Stage 2: 計算パイプライン v2 のテスト"""
import json
from decimal import Decimal
from pathlib import Path

import pytest

from python.calculator import (
    calculate_annual_income,
    calculate_basement_relaxation_area,
    calculate_building_area,
    calculate_building_cost,
    calculate_common_area,
    calculate_construction_area,
    calculate_construction_expense,
    calculate_demolition_cost,
    calculate_floor_common_area,
    calculate_max_construction_area,
    calculate_pile_cost,
    calculate_project,
    calculate_project_total,
    calculate_project_total_with_tax,
    calculate_rental_floor_area,
    calculate_surface_yield,
    lookup_constant,
    lookup_rental_price,
    lookup_standard_units,
)
from python.loader import load_tables
from python.pricing import TableLookupError
from python.schema.models import ProjectInput, normalize_ground_evaluation


@pytest.fixture
def case_001():
    """板橋区前野町の事例データ（v2 期待値。手計算の過程は fixture の notes）"""
    fixture_path = Path(__file__).parent / "fixtures" / "case_001_itabashi.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def tables():
    """テーブルデータ"""
    data_path = Path(__file__).parent.parent / "python" / "data"
    return load_tables(data_path)


class TestBuildingArea:
    """建築面積計算のテスト"""

    def test_calculate_building_area_normal(self):
        """建築面積 = 有効宅地面積 × 実効建蔽率"""
        result = calculate_building_area(
            有効宅地面積=Decimal("109.40"),
            実効建蔽率=Decimal("70"),
        )
        assert result == Decimal("76.58")

    def test_calculate_building_area_cap_at_70(self):
        """実効建蔽率が70%超の場合は70%でキャップ"""
        result = calculate_building_area(
            有効宅地面積=Decimal("100"),
            実効建蔽率=Decimal("80"),
        )
        assert result == Decimal("70")


class TestCommonArea:
    """共用部面積計算のテスト（EV は 4 値。無 以外で EV面積が乗る）"""

    def test_floor_common_area_without_ev(self):
        result = calculate_floor_common_area(
            EV="無", 共用部面積_層あたり=Decimal("8"), EV面積=Decimal("2")
        )
        assert result == Decimal("8")

    def test_floor_common_area_with_ev(self):
        result = calculate_floor_common_area(
            EV="6人乗り", 共用部面積_層あたり=Decimal("8"), EV面積=Decimal("2")
        )
        assert result == Decimal("10")

    def test_calculate_common_area(self):
        """共用部面積 = 建物層数 × 層あたり共用部面積"""
        assert calculate_common_area(4, Decimal("8")) == Decimal("32")
        assert calculate_common_area(5, Decimal("10")) == Decimal("50")


class TestBasementRelaxationArea:
    """地下緩和面積計算のテスト"""

    def test_calculate_basement_relaxation_with_basement(self):
        """地下緩和面積（半地下有）= 建築面積 - 層あたり共用部面積"""
        result = calculate_basement_relaxation_area(
            建築面積=Decimal("76.58"),
            半地下有無="半地下有",
            層あたり共用部面積=Decimal("8"),
        )
        assert result == Decimal("68.58")

    def test_calculate_basement_relaxation_without_basement(self):
        """地下緩和面積（半地下無）= 0"""
        result = calculate_basement_relaxation_area(
            建築面積=Decimal("76.58"),
            半地下有無="半地下無",
            層あたり共用部面積=Decimal("8"),
        )
        assert result == Decimal("0")

    def test_basement_relaxation_counts_ev(self, tables):
        """EV 有・半地下有 の緩和は 建築面積 − 10（v1 は EV 分を数えず 8 固定だった）"""
        層あたり共用部面積 = calculate_floor_common_area(
            EV="6人乗り",
            共用部面積_層あたり=lookup_constant("共用部面積_層あたり", tables),
            EV面積=lookup_constant("EV面積", tables),
        )
        assert 層あたり共用部面積 == Decimal("10")

        result = calculate_basement_relaxation_area(
            建築面積=Decimal("76.58"),
            半地下有無="半地下有",
            層あたり共用部面積=層あたり共用部面積,
        )
        assert result == Decimal("66.58")

    def test_basement_relaxation_for_full_basement(self):
        """全地下は半地下有と同じ扱い（緩和あり）。calculator の cc-defer と対"""
        result = calculate_basement_relaxation_area(
            建築面積=Decimal("76.58"),
            半地下有無="全地下",
            層あたり共用部面積=Decimal("8"),
        )
        assert result == Decimal("68.58")


class TestMaxConstructionArea:
    """最大施工面積計算のテスト"""

    def test_calculate_max_construction_area(self):
        """最大施工面積 = 有効宅地 × 容積率 + 共用部 + 地下緩和"""
        result = calculate_max_construction_area(
            有効宅地面積=Decimal("109.40"),
            最大容積率=Decimal("200"),
            共用部面積=Decimal("32"),
            地下緩和面積=Decimal("68.58"),
        )
        # 109.40 × 2.00 + 32 + 68.58 = 218.80 + 100.58 = 319.38
        assert result == Decimal("319.38")


class TestConstructionArea:
    """施工面積計算のテスト"""

    def test_calculate_construction_area_limited_by_floors(self):
        """施工面積 = min(建築面積×層数, 最大施工面積)"""
        result = calculate_construction_area(
            建築面積=Decimal("76.58"),
            建物層数=4,
            最大施工面積=Decimal("319.38"),
        )
        assert result == Decimal("306.32")

    def test_calculate_construction_area_limited_by_max(self):
        """最大施工面積で制限される場合"""
        result = calculate_construction_area(
            建築面積=Decimal("100"),
            建物層数=4,
            最大施工面積=Decimal("350"),
        )
        assert result == Decimal("350")


class TestPileCost:
    """杭費用計算のテスト（べた基礎はベース単価に内包＝別建てしない）"""

    def test_pile_cost_only_for_pile_foundation(self, tables):
        """べた → 0、30m杭 → 建築面積 × 12"""
        assert calculate_pile_cost(Decimal("76.58"), "礎ベタ基礎", tables) == 0
        assert calculate_pile_cost(Decimal("76.58"), "刃ベタ基礎", tables) == 0
        # 76.58 × 12 = 918.96 → 919
        assert calculate_pile_cost(Decimal("76.58"), "30m杭基礎", tables) == 919

    def test_pile_cost_unknown_foundation_raises(self, tables):
        """未知の基礎種別は 杭 へ落とさず例外"""
        with pytest.raises(TableLookupError):
            calculate_pile_cost(Decimal("100"), "未知基礎", tables)


class TestDemolitionCost:
    """解体費用計算のテスト（v2 は施工条件係数を掛けない）"""

    def test_calculate_demolition_cost(self):
        # 150 × 8 = 1200
        assert calculate_demolition_cost(Decimal("150"), Decimal("8")) == 1200

    def test_calculate_demolition_cost_zero_area(self):
        assert calculate_demolition_cost(Decimal("0"), Decimal("0")) == 0


class TestBuildingCost:
    """建物価格計算のテスト"""

    def test_calculate_building_cost(self):
        """建物価格 = 施工面積 × 最終単価"""
        # 306.32 × 57.05 = 17475.556 → 17476
        assert calculate_building_cost(Decimal("306.32"), Decimal("57.05")) == 17476


class TestProjectTotal:
    """PJ総額計算のテスト"""

    def test_calculate_construction_expense(self, tables):
        """建設経費 = 工事代金 × 建設経費率（定数.json が SSoT。v1 の 5% リテラルは退役）"""
        率 = lookup_constant("建設経費率", tables)
        assert 率 == Decimal("0.08")
        # 17476 × 0.08 = 1398.08 → 1398
        assert calculate_construction_expense(工事代金=17476, 建設経費率=率) == 1398

    def test_calculate_project_total(self):
        """PJ総額 = 土地価格 + 工事代金 + 建設経費"""
        result = calculate_project_total(
            土地価格=6980,
            工事代金=17476,
            建設経費=1398,
        )
        assert result == 25854

    def test_calculate_project_total_with_tax(self, tables):
        """PJ総額_税込 = 土地 + (工事代金 + 建設経費) × (1 + 消費税率)。土地は非課税"""
        税率 = lookup_constant("消費税率", tables)
        assert 税率 == Decimal("0.1")
        # 6980 + 18874 × 1.1 = 6980 + 20761.4 → 6980 + 20761 = 27741
        result = calculate_project_total_with_tax(
            土地価格=6980,
            工事代金=17476,
            建設経費=1398,
            消費税率=税率,
        )
        assert result == 27741


class TestRentalCalculation:
    """賃貸収益計算のテスト"""

    def test_calculate_rental_floor_area(self):
        """貸床面積 = 施工面積 - 共用部面積"""
        result = calculate_rental_floor_area(
            施工面積=Decimal("306.32"),
            共用部面積=Decimal("32"),
        )
        assert result == Decimal("274.32")

    def test_calculate_annual_income(self):
        """年間売上 = 貸床面積 × 貸床単価 × 12"""
        result = calculate_annual_income(
            貸床面積=Decimal("274.32"),
            貸床単価=4400,
        )
        # 274.32 × 4400 × 12 = 14484096円 → 万円で1448
        assert result == 1448

    def test_calculate_surface_yield(self):
        """表面利回 = 年間売上 / PJ総額 × 100（税抜ベース）"""
        result = calculate_surface_yield(年間売上=1448, PJ総額=25854)
        assert result == Decimal("5.60")


class TestTableLookups:
    """テーブル参照の fail-fast（v1 の silent default は全廃）"""

    def test_lookup_failure_raises(self, tables):
        """貸床単価テーブルに無い所在は例外（v1 は 4400円/6.0% へ黙って落ちていた）"""
        with pytest.raises(TableLookupError) as e:
            lookup_rental_price("足立区", tables)
        assert "足立区" in str(e.value)

    def test_lookup_rental_price_qualified_name(self, tables):
        """エリア括弧付きの正式名は引ける（上の失敗が誤検知でないことの対）"""
        単価, 利回 = lookup_rental_price("足立区（千住エリア内）", tables)
        assert 単価 > 0 and 利回 > 0

    def test_lookup_constant_unknown_raises(self, tables):
        with pytest.raises(TableLookupError):
            lookup_constant("存在しない定数", tables)

    def test_lookup_standard_units(self, tables):
        """基準戸数は 定数.json が SSoT（コードにリテラルで持たない）"""
        assert lookup_standard_units("共同住宅", tables) == 10
        assert lookup_standard_units("長屋", tables) == 9


class TestGroundEvaluationNormalization:
    """中間地盤①/② の明示写像（v1 は未知として既定値へ落ちていた）"""

    def test_normalize_intermediate_grades(self):
        assert normalize_ground_evaluation("中間地盤①") == "中間地盤"
        assert normalize_ground_evaluation("中間地盤②") == "中間地盤"

    def test_normalize_passthrough(self):
        assert normalize_ground_evaluation("軟弱地盤") == "軟弱地盤"


class TestFullCalculation:
    """フルパイプラインのテスト"""

    def test_case_001_v2_full_pipeline(self, case_001, tables):
        """Case001: 板橋区前野町を v2 モデルで再基線化

        期待値はコードを走らせる前に手計算で置いた（fixture の notes に連鎖を保存）。
        """
        project_input = ProjectInput.model_validate(case_001["input"])
        expected = case_001["expected_output"]

        result = calculate_project(project_input, tables)

        # 単価の連鎖
        assert result.道路区分 == expected["道路区分"]
        assert result.帯域 == expected["帯域"]
        assert result.ベース単価 == Decimal(expected["ベース単価"])
        assert result.オプション内訳 == {
            名称: Decimal(額) for 名称, 額 in expected["オプション内訳"].items()
        }
        assert result.最終単価 == Decimal(expected["最終単価"])

        # 面積
        assert result.建築面積 == Decimal(expected["建築面積"])
        assert result.共用部面積 == Decimal(expected["共用部面積"])
        assert result.地下緩和面積 == Decimal(expected["地下緩和面積"])
        assert result.最大施工面積 == Decimal(expected["最大施工面積"])
        assert result.施工面積 == Decimal(expected["施工面積"])
        assert result.基礎種別 == expected["基礎種別"]

        # 費用（Success Criteria の 4 項目を含む）
        assert result.建物価格 == expected["建物価格"]
        assert result.杭費用 == expected["杭費用"]
        assert result.解体費用 == expected["解体費用"]
        assert result.工事代金 == expected["工事代金"]
        assert result.建設経費 == expected["建設経費"]
        assert result.PJ総額 == expected["PJ総額"]
        assert result.PJ総額_税込 == expected["PJ総額_税込"]

        # 収支
        assert result.貸床面積 == Decimal(expected["貸床面積"])
        assert result.年間売上 == expected["年間売上"]
        assert result.表面利回 == Decimal(expected["表面利回"])
        assert result.目標利回 == Decimal(expected["目標利回"])

    def test_case_001_construction_cost_is_sum_of_parts(self, case_001, tables):
        """工事代金 = 建物価格 + 杭費用 + 解体費用（v1 の基礎・山留別建ては退役）"""
        result = calculate_project(
            ProjectInput.model_validate(case_001["input"]), tables
        )
        assert result.工事代金 == result.建物価格 + result.杭費用 + result.解体費用
