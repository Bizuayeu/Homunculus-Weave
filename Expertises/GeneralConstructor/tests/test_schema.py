"""Phase 1: スキーマ定義のテスト（TDD Red Phase）"""
import pytest
from decimal import Decimal
from pydantic import ValidationError

# テスト対象のインポート（まだ存在しないのでエラーになる）
from python.schema.tables import (
    AreaRange,
    FloatRange,
    BuildingPriceEntry,
    FoundationPriceEntry,
    DemolitionPriceEntry,
    RentalPriceEntry,
    ConstructionConditionEntry,
    RetainingWallPriceEntry,
)
from python.schema.models import ProjectInput, ProjectOutput


class TestAreaRange:
    """面積範囲モデルのテスト"""

    def test_valid_area_range(self):
        """正常な面積範囲"""
        ar = AreaRange(min=0, max=200)
        assert ar.min == 0
        assert ar.max == 200

    def test_area_range_validates_min_max(self):
        """min > max でエラー"""
        with pytest.raises(ValidationError):
            AreaRange(min=100, max=50)


class TestBuildingPriceEntry:
    """建築単価エントリのテスト"""

    def test_valid_building_price_entry(self):
        """正常な建築単価エントリ"""
        entry = BuildingPriceEntry(
            半地下有無="半地下有",
            施工面積=AreaRange(min=0, max=200),
            建築単価=65,
        )
        assert entry.半地下有無 == "半地下有"
        assert entry.建築単価 == 65

    def test_building_price_entry_validates_literals(self):
        """半地下有無のLiteral制約をテスト"""
        with pytest.raises(ValidationError):
            BuildingPriceEntry(
                半地下有無="不正な値",
                施工面積=AreaRange(min=0, max=200),
                建築単価=65,
            )

    def test_building_price_entry_default_unit(self):
        """デフォルト単位のテスト"""
        entry = BuildingPriceEntry(
            半地下有無="半地下無",
            施工面積=AreaRange(min=0, max=200),
            建築単価=63,
        )
        assert entry.単位 == "万円/㎡"


class TestFoundationPriceEntry:
    """基礎単価エントリのテスト"""

    def test_valid_foundation_types(self):
        """正常な基礎種別"""
        for foundation_type in ["刃ベタ基礎", "礎ベタ基礎", "20m杭基礎", "30m杭基礎", "40m杭基礎"]:
            entry = FoundationPriceEntry(基礎種別=foundation_type, 基礎単価=10.0)
            assert entry.基礎種別 == foundation_type

    def test_foundation_price_is_float(self):
        """基礎単価はfloat型"""
        entry = FoundationPriceEntry(基礎種別="刃ベタ基礎", 基礎単価=3.0)
        assert entry.基礎単価 == 3.0


class TestDemolitionPriceEntry:
    """解体単価エントリのテスト"""

    def test_valid_structure_types(self):
        """正常な古家構造"""
        for structure in ["無し", "木造", "鉄骨造", "RC造", "RC造地下室付き"]:
            entry = DemolitionPriceEntry(古家構造=structure, 解体単価=5.0)
            assert entry.古家構造 == structure

    def test_demolition_price_is_float(self):
        """解体単価はfloat型"""
        entry = DemolitionPriceEntry(古家構造="木造", 解体単価=3.0)
        assert entry.解体単価 == 3.0


class TestRentalPriceEntry:
    """貸床単価エントリのテスト"""

    def test_valid_rental_entry(self):
        """正常な貸床単価エントリ"""
        entry = RentalPriceEntry(
            土地所在="目黒区",
            貸床単価=5000,
            目標利回=5.5,
        )
        assert entry.土地所在 == "目黒区"
        assert entry.貸床単価 == 5000
        assert entry.目標利回 == 5.5


class TestConstructionConditionEntry:
    """施工条件エントリのテスト"""

    def test_valid_condition_entry(self):
        """正常な施工条件エントリ"""
        entry = ConstructionConditionEntry(
            道路幅員=FloatRange(min=4.0, max=6.0),
            搬入経路="規制無",
            道路種別="私道",
            接道長さ=FloatRange(min=3.0, max=999),
            施工条件係数=0.05,
        )
        assert entry.施工条件係数 == 0.05

    def test_invalid_transport_route(self):
        """不正な搬入経路でエラー"""
        with pytest.raises(ValidationError):
            ConstructionConditionEntry(
                道路幅員=FloatRange(min=4.0, max=6.0),
                搬入経路="不正な値",
                道路種別="私道",
                接道長さ=FloatRange(min=3.0, max=999),
                施工条件係数=0.05,
            )


class TestProjectInput:
    """プロジェクト入力モデルのテスト"""

    def test_project_input_requires_mandatory_fields(self):
        """必須フィールドの欠落でエラー"""
        with pytest.raises(ValidationError):
            ProjectInput()

    def test_valid_project_input(self):
        """正常なプロジェクト入力"""
        input_data = ProjectInput(
            土地価格=10000,
            土地所在="目黒区",
            有効宅地面積=Decimal("150.5"),
            前面道路幅員=Decimal("6.0"),
            搬入経路="規制無",
            道路種別="私道",
            接道長さ=Decimal("8.0"),
            古家構造="木造",
            解体面積=Decimal("80.0"),
            実効建蔽率=Decimal("70"),
            用途地域="第一種住居地域",
            最大容積率=Decimal("200"),
            住宅種別="共同住宅",
            建物層数=4,
            半地下有無="半地下有",
            EV有無="EV無",
            壁率="標準的",
            設備率="標準的",
            地盤評価="中間地盤①",
        )
        assert input_data.土地価格 == 10000
        assert input_data.建物層数 == 4

    def test_invalid_building_floors(self):
        """不正な建物層数でエラー"""
        with pytest.raises(ValidationError):
            ProjectInput(
                土地価格=10000,
                土地所在="目黒区",
                有効宅地面積=Decimal("150.5"),
                前面道路幅員=Decimal("6.0"),
                接道長さ=Decimal("8.0"),
                古家構造="木造",
                実効建蔽率=Decimal("70"),
                用途地域="第一種住居地域",
                最大容積率=Decimal("200"),
                住宅種別="共同住宅",
                建物層数=10,  # 3,4,5,6以外
                半地下有無="半地下有",
                EV有無="EV無",
                壁率="標準的",
                設備率="標準的",
                地盤評価="中間地盤①",
            )

    def test_default_values(self):
        """デフォルト値のテスト"""
        input_data = ProjectInput(
            土地価格=10000,
            土地所在="目黒区",
            有効宅地面積=Decimal("150.5"),
            前面道路幅員=Decimal("6.0"),
            接道長さ=Decimal("8.0"),
            古家構造="無し",
            実効建蔽率=Decimal("70"),
            用途地域="第一種住居地域",
            最大容積率=Decimal("200"),
            住宅種別="共同住宅",
            建物層数=4,
            半地下有無="半地下有",
            EV有無="EV無",
            壁率="標準的",
            設備率="標準的",
            地盤評価="中間地盤①",
        )
        assert input_data.搬入経路 == "規制無"
        assert input_data.道路種別 == "私道"
        assert input_data.グレード == "やや高い"
        assert input_data.解体面積 == Decimal("0")


class TestProjectOutput:
    """プロジェクト出力モデルのテスト"""

    def test_valid_project_output(self):
        """正常なプロジェクト出力"""
        output = ProjectOutput(
            施工条件係数=Decimal("0.05"),
            建物形状係数=Decimal("0.10"),
            建築面積=Decimal("100.0"),
            基礎種別="礎ベタ基礎",
            基礎単価=5,
            山留工法="親杭横矢板",
            山留単価=3,
            共用部面積=Decimal("40.0"),
            地下緩和面積=Decimal("92.0"),
            最大施工面積=Decimal("500.0"),
            施工面積=Decimal("400.0"),
            標準建築単価=50,
            補正建築単価=Decimal("57.5"),
            解体費用=500,
            基礎費用=800,
            山留費用=400,
            地盤費用=1200,
            建物価格=23000,
            PJ総額=35000,
            貸床面積=Decimal("360.0"),
            貸床単価=5000,
            年間売上=2160,
            表面利回=Decimal("6.17"),
            目標利回=Decimal("5.5"),
        )
        assert output.PJ総額 == 35000
        assert output.表面利回 == Decimal("6.17")
