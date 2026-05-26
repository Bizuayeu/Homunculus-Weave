"""統合テスト: JSON入力→計算→出力の全工程テスト"""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from python.loader import load_tables
from python.calculator import calculate_project
from python.schema.models import ProjectInput, ProjectOutput


class TestFullPipeline:
    """エンドツーエンドの統合テスト"""

    @pytest.fixture
    def tables(self):
        """テーブルデータをロード"""
        data_path = Path(__file__).parent.parent / "References"
        return load_tables(str(data_path))

    @pytest.fixture
    def case_001(self):
        """板橋区前野町のテストケース"""
        fixture_path = Path(__file__).parent / "fixtures" / "case_001_itabashi.json"
        with open(fixture_path, encoding="utf-8") as f:
            return json.load(f)

    def test_full_pipeline_case_001(self, case_001, tables):
        """Case001: 板橋区前野町の事例でフルパイプラインテスト"""
        input_data = case_001["input"]
        expected = case_001["expected_output"]

        # ProjectInput作成
        project_input = ProjectInput(
            土地価格=int(input_data["土地価格"]),
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
            高度地区=input_data.get("高度地区"),
            最大容積率=Decimal(input_data["最大容積率"]),
            住宅種別=input_data["住宅種別"],
            建物層数=int(input_data["建物層数"]),
            半地下有無=input_data["半地下有無"],
            EV有無=input_data["EV有無"],
            壁率=input_data["壁率"],
            設備率=input_data["設備率"],
            グレード=input_data["グレード"],
            地盤評価=input_data["地盤評価"],
        )

        # 計算実行
        result = calculate_project(project_input, tables)

        # 結果検証（ProjectOutputの型確認）
        assert isinstance(result, ProjectOutput)

        # 主要な出力値の検証
        assert result.PJ総額 == int(expected["PJ総額"])
        assert abs(result.表面利回 - Decimal(expected["表面利回"])) < Decimal("0.01")
        assert result.施工面積 == Decimal(expected["施工面積"])
        assert result.建物価格 == int(expected["建物価格"])

    def test_full_pipeline_output_completeness(self, case_001, tables):
        """出力モデルの全フィールドが設定されていることを確認"""
        input_data = case_001["input"]

        project_input = ProjectInput(
            土地価格=int(input_data["土地価格"]),
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
            高度地区=input_data.get("高度地区"),
            最大容積率=Decimal(input_data["最大容積率"]),
            住宅種別=input_data["住宅種別"],
            建物層数=int(input_data["建物層数"]),
            半地下有無=input_data["半地下有無"],
            EV有無=input_data["EV有無"],
            壁率=input_data["壁率"],
            設備率=input_data["設備率"],
            グレード=input_data["グレード"],
            地盤評価=input_data["地盤評価"],
        )

        result = calculate_project(project_input, tables)

        # 全フィールドがNoneでないことを確認
        assert result.施工条件係数 is not None
        assert result.建物形状係数 is not None
        assert result.建築面積 is not None
        assert result.基礎種別 is not None
        assert result.基礎単価 is not None
        assert result.山留工法 is not None
        assert result.山留単価 is not None
        assert result.共用部面積 is not None
        assert result.地下緩和面積 is not None
        assert result.最大施工面積 is not None
        assert result.施工面積 is not None
        assert result.標準建築単価 is not None
        assert result.補正建築単価 is not None
        assert result.解体費用 is not None
        assert result.基礎費用 is not None
        assert result.山留費用 is not None
        assert result.地盤費用 is not None
        assert result.建物価格 is not None
        assert result.PJ総額 is not None
        assert result.貸床面積 is not None
        assert result.貸床単価 is not None
        assert result.年間売上 is not None
        assert result.表面利回 is not None
        assert result.目標利回 is not None

    def test_full_pipeline_json_roundtrip(self, case_001, tables):
        """結果をJSON形式で出力し、再読込できることを確認"""
        input_data = case_001["input"]

        project_input = ProjectInput(
            土地価格=int(input_data["土地価格"]),
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
            高度地区=input_data.get("高度地区"),
            最大容積率=Decimal(input_data["最大容積率"]),
            住宅種別=input_data["住宅種別"],
            建物層数=int(input_data["建物層数"]),
            半地下有無=input_data["半地下有無"],
            EV有無=input_data["EV有無"],
            壁率=input_data["壁率"],
            設備率=input_data["設備率"],
            グレード=input_data["グレード"],
            地盤評価=input_data["地盤評価"],
        )

        result = calculate_project(project_input, tables)

        # JSON形式で出力
        result_json = result.model_dump_json()

        # 再読込
        result_dict = json.loads(result_json)

        # 主要フィールドの確認
        assert "PJ総額" in result_dict
        assert "表面利回" in result_dict
        assert result_dict["PJ総額"] == result.PJ総額


class TestMultipleCases:
    """複数ケースでの回帰テスト"""

    @pytest.fixture
    def tables(self):
        """テーブルデータをロード"""
        data_path = Path(__file__).parent.parent / "References"
        return load_tables(str(data_path))

    def get_all_fixtures(self):
        """全てのフィクスチャファイルを取得"""
        fixtures_dir = Path(__file__).parent / "fixtures"
        return list(fixtures_dir.glob("case_*.json"))

    def test_all_fixtures_pass(self, tables):
        """全フィクスチャで計算が成功することを確認"""
        fixtures = self.get_all_fixtures()
        assert len(fixtures) > 0, "フィクスチャが見つかりません"

        for fixture_path in fixtures:
            with open(fixture_path, encoding="utf-8") as f:
                case_data = json.load(f)

            input_data = case_data["input"]
            expected = case_data["expected_output"]

            project_input = ProjectInput(
                土地価格=int(input_data["土地価格"]),
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
                高度地区=input_data.get("高度地区"),
                最大容積率=Decimal(input_data["最大容積率"]),
                住宅種別=input_data["住宅種別"],
                建物層数=int(input_data["建物層数"]),
                半地下有無=input_data["半地下有無"],
                EV有無=input_data["EV有無"],
                壁率=input_data["壁率"],
                設備率=input_data["設備率"],
                グレード=input_data["グレード"],
                地盤評価=input_data["地盤評価"],
            )

            result = calculate_project(project_input, tables)

            # 基本的な検証
            assert result.PJ総額 == int(expected["PJ総額"]), (
                f"{fixture_path.name}: PJ総額が一致しません"
            )
            assert abs(result.表面利回 - Decimal(expected["表面利回"])) < Decimal("0.01"), (
                f"{fixture_path.name}: 表面利回が一致しません"
            )


class TestEdgeCases:
    """境界値・エッジケースのテスト"""

    @pytest.fixture
    def tables(self):
        """テーブルデータをロード"""
        data_path = Path(__file__).parent.parent / "References"
        return load_tables(str(data_path))

    def test_minimum_area_project(self, tables):
        """最小面積のプロジェクト"""
        project_input = ProjectInput(
            土地価格=5000,
            土地所在="板橋区",
            有効宅地面積=Decimal("50.00"),
            前面道路幅員=Decimal("4.0"),
            搬入経路="規制無",
            道路種別="公道",
            接道長さ=Decimal("6.0"),
            古家構造="無し",
            解体面積=Decimal("0"),
            実効建蔽率=Decimal("60"),
            用途地域="第一種住居地域",
            最大容積率=Decimal("200"),
            住宅種別="共同住宅",
            建物層数=3,
            半地下有無="半地下無",
            EV有無="EV無",
            壁率="標準的",
            設備率="標準的",
            グレード="標準的",
            地盤評価="硬質地盤",
        )

        result = calculate_project(project_input, tables)

        # 計算が正常に完了することを確認
        assert result.PJ総額 > 0
        assert result.表面利回 > 0

    def test_maximum_coefficient_project(self, tables):
        """施工条件係数が最大のケース"""
        project_input = ProjectInput(
            土地価格=10000,
            土地所在="港区",
            有効宅地面積=Decimal("200.00"),
            前面道路幅員=Decimal("3.5"),  # 4m未満
            搬入経路="規制有",
            道路種別="私道",
            接道長さ=Decimal("3.0"),  # 4m未満
            古家構造="RC造",
            解体面積=Decimal("150"),
            実効建蔽率=Decimal("70"),
            用途地域="商業地域",
            最大容積率=Decimal("400"),
            住宅種別="共同住宅",
            建物層数=6,
            半地下有無="半地下有",
            EV有無="EV有",
            壁率="高い",
            設備率="高い",
            グレード="高い",
            地盤評価="軟弱地盤",
        )

        result = calculate_project(project_input, tables)

        # 計算が正常に完了することを確認
        assert result.PJ総額 > 0
        assert result.施工条件係数 > Decimal("0")
