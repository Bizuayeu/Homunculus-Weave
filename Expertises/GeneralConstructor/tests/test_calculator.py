"""Phase 3: 計算ロジックのテスト（TDD Red Phase）"""
import json
import pytest
from decimal import Decimal
from pathlib import Path

# テスト対象のインポート（まだ存在しないのでエラーになる）
from python.calculator import (
    calculate_building_area,
    calculate_common_area,
    calculate_basement_relaxation_area,
    calculate_max_construction_area,
    calculate_construction_area,
    calculate_foundation_cost,
    calculate_retaining_wall_cost,
    calculate_ground_cost,
    calculate_adjusted_building_price,
    calculate_building_cost,
    calculate_construction_expense,
    calculate_project_total,
    calculate_rental_floor_area,
    calculate_annual_income,
    calculate_surface_yield,
    calculate_project,
)
from python.loader import load_tables
from python.schema.models import ProjectInput, ProjectOutput


# フィクスチャ読み込み
@pytest.fixture
def case_001():
    """板橋区前野町の事例データ"""
    fixture_path = Path(__file__).parent / "fixtures" / "case_001_itabashi.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def tables():
    """テーブルデータ"""
    data_path = Path(__file__).parent.parent / "References"
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
        # 80%でも70%上限が適用される（ビジネスルール）
        # ただし手入力で70%超を許容する場合もあるので、この挙動は要確認
        assert result == Decimal("70")


class TestCommonArea:
    """共用部面積計算のテスト"""

    def test_calculate_common_area_without_ev(self):
        """共用部面積（EV無し）= 建物層数 × 8"""
        result = calculate_common_area(建物層数=4, EV有無="EV無")
        assert result == Decimal("32")

    def test_calculate_common_area_with_ev(self):
        """共用部面積（EV有り）= 建物層数 × (8 + 2)"""
        result = calculate_common_area(建物層数=5, EV有無="EV有")
        assert result == Decimal("50")


class TestBasementRelaxationArea:
    """地下緩和面積計算のテスト"""

    def test_calculate_basement_relaxation_with_basement(self):
        """地下緩和面積（半地下有）= 建築面積 - 8"""
        result = calculate_basement_relaxation_area(
            建築面積=Decimal("76.58"),
            半地下有無="半地下有",
        )
        assert result == Decimal("68.58")

    def test_calculate_basement_relaxation_without_basement(self):
        """地下緩和面積（半地下無）= 0"""
        result = calculate_basement_relaxation_area(
            建築面積=Decimal("76.58"),
            半地下有無="半地下無",
        )
        assert result == Decimal("0")


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
        # 76.58 × 4 = 306.32 < 319.38
        assert result == Decimal("306.32")

    def test_calculate_construction_area_limited_by_max(self):
        """最大施工面積で制限される場合"""
        result = calculate_construction_area(
            建築面積=Decimal("100"),
            建物層数=4,
            最大施工面積=Decimal("350"),
        )
        # 100 × 4 = 400 > 350 → 350が採用
        assert result == Decimal("350")


class TestFoundationCost:
    """基礎費用計算のテスト"""

    def test_calculate_foundation_cost(self):
        """基礎費用 = 建築面積 × 基礎単価 × (1 + 施工条件係数)"""
        result = calculate_foundation_cost(
            建築面積=Decimal("76.58"),
            基礎単価=Decimal("6"),
            施工条件係数=Decimal("0"),
        )
        # 76.58 × 6 × 1.00 = 459.48 → 四捨五入で459
        assert result == 459

    def test_calculate_foundation_cost_with_coefficient(self):
        """施工条件係数がある場合"""
        result = calculate_foundation_cost(
            建築面積=Decimal("100"),
            基礎単価=Decimal("6"),
            施工条件係数=Decimal("0.05"),
        )
        # 100 × 6 × 1.05 = 630
        assert result == 630


class TestRetainingWallCost:
    """山留費用計算のテスト"""

    def test_calculate_retaining_wall_cost(self):
        """山留費用 = 建築面積 × 山留単価 × (1 + 施工条件係数)"""
        result = calculate_retaining_wall_cost(
            建築面積=Decimal("76.58"),
            山留単価=Decimal("1"),
            施工条件係数=Decimal("0"),
        )
        # 76.58 × 1 × 1.00 = 76.58 → 四捨五入で77
        assert result == 77


class TestGroundCost:
    """地盤費用計算のテスト"""

    def test_calculate_ground_cost(self):
        """地盤費用 = 基礎費用 + 山留費用"""
        result = calculate_ground_cost(基礎費用=459, 山留費用=77)
        assert result == 536


class TestBuildingCost:
    """建物価格計算のテスト"""

    def test_calculate_adjusted_building_price(self):
        """補正建築単価 = 標準単価 × (1 + 施工条件係数 + 建物形状係数)"""
        result = calculate_adjusted_building_price(
            標準建築単価=50,
            施工条件係数=Decimal("0"),
            建物形状係数=Decimal("0.04"),
        )
        # 50 × (1 + 0 + 0.04) = 52
        assert result == Decimal("52")

    def test_calculate_building_cost(self):
        """建物価格 = 施工面積 × 補正建築単価"""
        result = calculate_building_cost(
            施工面積=Decimal("306.32"),
            補正建築単価=Decimal("52"),
        )
        # 306.32 × 52 = 15928.64 → 四捨五入で15929
        assert result == 15929


class TestProjectTotal:
    """PJ総額計算のテスト"""

    def test_calculate_construction_expense(self):
        """建設経費 = 工事代金 × 5%"""
        # 工事代金 = 建物価格 + 基礎費用 + 山留費用 + 解体費用
        工事代金 = 15929 + 459 + 77 + 0
        result = calculate_construction_expense(工事代金=工事代金)
        # 16465 × 0.05 = 823.25 → 823
        assert result == 823

    def test_calculate_project_total(self):
        """PJ総額 = 土地価格 + 工事代金 + 建設経費"""
        result = calculate_project_total(
            土地価格=6980,
            工事代金=16465,
            建設経費=823,
        )
        # 6980 + 16465 + 823 = 24268
        assert result == 24268


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
        """表面利回 = 年間売上 / PJ総額 × 100"""
        result = calculate_surface_yield(
            年間売上=1448,
            PJ総額=24268,
        )
        # 1448 / 24268 × 100 = 5.966... ≈ 5.97
        assert abs(result - Decimal("5.97")) < Decimal("0.01")


class TestFullCalculation:
    """フルパイプラインのテスト"""

    def test_calculate_project_case_001(self, case_001, tables):
        """Case001: 板橋区前野町の事例でフル計算"""
        input_data = case_001["input"]
        expected = case_001["expected_output"]

        # ProjectInputを作成
        project_input = ProjectInput(
            土地価格=input_data["土地価格"],
            土地所在=input_data["土地所在"],
            有効宅地面積=Decimal(input_data["有効宅地面積"]),
            前面道路幅員=Decimal(input_data["前面道路幅員"]),
            搬入経路=input_data["搬入経路"],
            道路種別=input_data["道路種別"],
            接道長さ=Decimal(input_data["接道長さ"]),
            古家構造=input_data["古家構造"],
            解体面積=Decimal(input_data["解体面積"]),
            実効建蔽率=Decimal(input_data["実効建蔽率"]),
            用途地域=input_data["用途地域"],
            最大容積率=Decimal(input_data["最大容積率"]),
            住宅種別=input_data["住宅種別"],
            建物層数=input_data["建物層数"],
            半地下有無=input_data["半地下有無"],
            EV有無=input_data["EV有無"],
            壁率=input_data["壁率"],
            設備率=input_data["設備率"],
            グレード=input_data["グレード"],
            地盤評価=input_data["地盤評価"],
        )

        # 計算実行
        result = calculate_project(project_input, tables)

        # 主要項目を検証
        assert result.PJ総額 == int(expected["PJ総額"])
        assert abs(result.表面利回 - Decimal(expected["表面利回"])) < Decimal("0.01")
        assert result.施工面積 == Decimal(expected["施工面積"])
        assert result.基礎種別 == expected["基礎種別"]
        assert result.山留工法 == expected["山留工法"]
