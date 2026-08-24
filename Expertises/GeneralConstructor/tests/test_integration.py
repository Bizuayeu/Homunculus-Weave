"""統合テスト: JSON入力→計算→出力の全工程テスト"""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from python.calculator import calculate_project
from python.loader import load_tables
from python.main import run_calculation
from python.pricing import PricingDomainError
from python.schema.models import ProjectInput, ProjectOutput


@pytest.fixture
def tables():
    """テーブルデータをロード"""
    data_path = Path(__file__).parent.parent / "python" / "data"
    return load_tables(str(data_path))


@pytest.fixture
def case_001():
    """板橋区前野町のテストケース"""
    fixture_path = Path(__file__).parent / "fixtures" / "case_001_itabashi.json"
    with open(fixture_path, encoding="utf-8") as f:
        return json.load(f)


class TestFullPipeline:
    """エンドツーエンドの統合テスト"""

    def test_full_pipeline_case_001(self, case_001, tables):
        """Case001: 板橋区前野町の事例でフルパイプラインテスト"""
        expected = case_001["expected_output"]
        result = calculate_project(
            ProjectInput.model_validate(case_001["input"]), tables
        )

        assert isinstance(result, ProjectOutput)
        assert result.PJ総額 == expected["PJ総額"]
        assert result.PJ総額_税込 == expected["PJ総額_税込"]
        assert result.表面利回 == Decimal(expected["表面利回"])
        assert result.施工面積 == Decimal(expected["施工面積"])
        assert result.建物価格 == expected["建物価格"]

    def test_full_pipeline_output_completeness(self, case_001, tables):
        """出力モデルの全フィールドが設定されていることを確認"""
        result = calculate_project(
            ProjectInput.model_validate(case_001["input"]), tables
        )
        for 名称 in ProjectOutput.model_fields:
            assert getattr(result, 名称) is not None, f"{名称} が未設定"

    def test_full_pipeline_json_roundtrip(self, case_001, tables):
        """結果をJSON形式で出力し、再読込できることを確認"""
        result = calculate_project(
            ProjectInput.model_validate(case_001["input"]), tables
        )

        result_dict = json.loads(result.model_dump_json())

        assert "PJ総額" in result_dict
        assert "表面利回" in result_dict
        assert result_dict["PJ総額"] == result.PJ総額
        # オプション内訳は名称→金額の写像として往復する
        assert set(result_dict["オプション内訳"]) == set(result.オプション内訳)

    def test_run_calculation_from_dict(self, case_001):
        """main.run_calculation（Interface 層）が dict 入力で通り、JSON 化できる"""
        result = run_calculation(case_001["input"])

        assert result["PJ総額"] == case_001["expected_output"]["PJ総額"]
        # Decimal が残っていれば json.dumps がここで落ちる（入れ子の内訳を含む）
        json.dumps(result, ensure_ascii=False)

    def test_run_calculation_rejects_retired_key(self, case_001):
        """v1 の退役キーを黙って無視しない（extra="forbid"）"""
        入力 = dict(case_001["input"], 壁率="標準的")
        with pytest.raises(Exception) as e:
            run_calculation(入力)
        assert "壁率" in str(e.value)


class TestMultipleCases:
    """複数ケースでの回帰テスト"""

    def get_all_fixtures(self):
        """全てのフィクスチャファイルを取得"""
        fixtures_dir = Path(__file__).parent / "fixtures"
        return list(fixtures_dir.glob("case_*.json"))

    def test_all_fixtures_pass(self, tables):
        """全フィクスチャで計算が成功し、期待値と一致することを確認"""
        fixtures = self.get_all_fixtures()
        assert len(fixtures) > 0, "フィクスチャが見つかりません"

        for fixture_path in fixtures:
            with open(fixture_path, encoding="utf-8") as f:
                case_data = json.load(f)

            expected = case_data["expected_output"]
            result = calculate_project(
                ProjectInput.model_validate(case_data["input"]), tables
            )

            assert result.PJ総額 == expected["PJ総額"], (
                f"{fixture_path.name}: PJ総額が一致しません"
            )
            assert result.表面利回 == Decimal(expected["表面利回"]), (
                f"{fixture_path.name}: 表面利回が一致しません"
            )


class TestEdgeCases:
    """境界値・エッジケースのテスト"""

    def test_under_band_floor_raises(self, tables):
        """帯域下限（200㎡）を割る小規模案件は定義域外

        v1 は建築単価テーブルの既定値 50 万円/㎡ へ落ちて数字を返していた。
        単価表は 200㎡ 未満の値を持たないので、返さずに落とす。
        """
        project_input = ProjectInput(
            土地価格=5000,
            土地所在="板橋区",
            有効宅地面積=Decimal("50.00"),
            前面道路幅員=Decimal("4.0"),
            古家構造="無し",
            解体面積=Decimal("0"),
            実効建蔽率=Decimal("60"),
            用途地域="第一種住居地域",
            最大容積率=Decimal("200"),
            住宅種別="共同住宅",
            建物層数=3,
            戸数=2,
            半地下有無="半地下無",
            地盤評価="硬質地盤",
        )

        with pytest.raises(PricingDomainError) as e:
            calculate_project(project_input, tables)
        assert "200" in str(e.value)

    def test_large_project_with_pile_foundation(self, tables):
        """大規模・軟弱地盤・全地下・EV 有：杭費用と全地下オプションが立つ"""
        project_input = ProjectInput(
            土地価格=10000,
            土地所在="港区",
            有効宅地面積=Decimal("200.00"),
            前面道路幅員=Decimal("3.5"),
            古家構造="RC造",
            解体面積=Decimal("150"),
            実効建蔽率=Decimal("70"),
            用途地域="商業地域",
            最大容積率=Decimal("400"),
            住宅種別="共同住宅",
            建物層数=6,
            戸数=21,
            半地下有無="全地下",
            EV="9人乗り",
            地盤評価="軟弱地盤",
        )

        result = calculate_project(project_input, tables)

        assert result.基礎種別 == "40m杭基礎"
        assert result.杭費用 > 0  # 杭基礎なので別建てされる
        assert result.解体費用 == 1200  # 150㎡ × 8万円（係数の乗算なし）
        assert "全地下（杭基礎）" in result.オプション内訳
        assert "EV（9人乗り）" in result.オプション内訳
        assert "6層" in result.オプション内訳
        assert result.道路区分 == "2.5〜8m"  # 3.5m は狭小（≦2.5）ではない
        assert result.PJ総額_税込 > result.PJ総額

    def test_narrow_road_raises_unit_price(self, tables):
        """前面道路 2.5m 以下は道路区分オフセット +2 万円/㎡"""
        共通 = dict(
            土地価格=8000,
            土地所在="板橋区",
            有効宅地面積=Decimal("109.40"),
            古家構造="無し",
            実効建蔽率=Decimal("70"),
            用途地域="第1種住居地域",
            最大容積率=Decimal("200"),
            住宅種別="共同住宅",
            建物層数=4,
            戸数=8,
            半地下有無="半地下有",
            地盤評価="中間地盤",
        )
        狭小 = calculate_project(
            ProjectInput(前面道路幅員=Decimal("2.5"), **共通), tables
        )
        標準 = calculate_project(
            ProjectInput(前面道路幅員=Decimal("2.6"), **共通), tables
        )

        assert 狭小.道路区分 == "2.5m以下"
        assert 標準.道路区分 == "2.5〜8m"
        assert 狭小.ベース単価 - 標準.ベース単価 == Decimal("2")
