"""Stage 1: 単価モデル（pricing.py）のテスト（TDD Red Phase）

テーブルは loader を通さず、テスト側で直接 JSON を読んで Domain の型へ変換する
（loader の v2 対応は Stage 3。Domain は loader を知らない）。
"""
import json
from decimal import Decimal
from pathlib import Path

import pytest

from python.pricing import (
    OptionInput,
    PricingDomainError,
    base_unit_price,
    final_unit_price,
    option_costs,
    resolve_band,
)
from python.schema.tables import (
    ConstantsEntry,
    OptionPriceEntry,
    UnitPriceBandEntry,
    UnitPriceOffsets,
)

DATA_DIR = Path(__file__).parent.parent / "python" / "data"
FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _read(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def 帯域():
    raw = _read(DATA_DIR / "建築単価帯域.json")["建築単価帯域"]
    return [UnitPriceBandEntry.model_validate(e) for e in raw]


@pytest.fixture(scope="module")
def オフセット():
    raw = _read(DATA_DIR / "単価オフセット.json")["単価オフセット"]
    return UnitPriceOffsets.model_validate(raw)


@pytest.fixture(scope="module")
def オプション単価():
    raw = _read(DATA_DIR / "オプション単価.json")["オプション単価"]
    return [OptionPriceEntry.model_validate(e) for e in raw]


@pytest.fixture(scope="module")
def 基準戸数():
    """定数.json が基準戸数の SSoT（コードにリテラルで持たない）"""
    raw = _read(DATA_DIR / "定数.json")["定数"]["基準戸数"]
    return ConstantsEntry.model_validate(raw).値


def _golden_rows():
    return _read(FIXTURE_DIR / "unit_price_golden.json")["unit_price_golden"]


class TestBaseUnitPrice:
    """ベース㎡単価 = 帯域基準値 + 道路 + 基礎形状 + 種別 オフセット"""

    @pytest.mark.parametrize(
        "row",
        _golden_rows(),
        ids=lambda r: f"{r['種別']}-{r['施工面積帯']['下限']}-{r['道路区分']}-{r['基礎形状']}",
    )
    def test_base_unit_price_matches_golden(self, row, 帯域, オフセット):
        """『参照用』78 行の全行と一致する

        施工床は各帯の下限で探る（「下限以上」側の境界テスト too）。
        """
        result = base_unit_price(
            施工床面積=Decimal(str(row["施工面積帯"]["下限"])),
            種別=row["種別"],
            道路区分=row["道路区分"],
            基礎形状=row["基礎形状"],
            帯域=帯域,
            オフセット=オフセット,
        )
        assert result == Decimal(str(row["ベース㎡単価"]))

    def test_rowhouse_derived_all_bands(self, 帯域, オフセット):
        """長屋は共同同帯 +2（Excel に行が無い帯も導出で埋まる）"""
        共通 = dict(
            種別="長屋",
            道路区分="2.5〜8m",
            基礎形状="べた",
            帯域=帯域,
            オフセット=オフセット,
        )
        # 300-320 帯の基準値 58 + 2
        assert base_unit_price(施工床面積=Decimal("300"), **共通) == Decimal("60")
        # 500〜（上限開放）帯の基準値 52（2026-08-24 大環主裁定の override）+ 2
        assert base_unit_price(施工床面積=Decimal("600"), **共通) == Decimal("54")

    def test_under_200_raises(self, 帯域):
        """施工床 200㎡ 未満は定義域外（フォールバックしない）"""
        with pytest.raises(PricingDomainError) as e:
            resolve_band(Decimal("199.99"), 帯域)
        assert "200" in str(e.value)


class TestExcelSample:
    """岡田お試し3 のサンプル（372.79㎡・共同・2.5〜8m・B1+3・べた・全地下）"""

    def _入力(self, 戸数: int) -> OptionInput:
        """サンプルの入力

        有効宅地面積 100・前面道路幅員 6 は「敷地小規模（80㎡以下）も車両行
        （150㎡以上）も発火しない域」の代表値。サンプルのオプション合計
        924.395 から、これらの行が立っていないことが逆算できる。EV は無し。
        """
        return OptionInput(
            施工床面積=Decimal("372.79"),
            基礎形状="べた",
            半地下有無="全地下",
            戸数=戸数,
            建物層数=4,
            有効宅地面積=Decimal("100"),
            前面道路幅員=Decimal("6"),
            調査費=True,
            防音室数=7,
            一層二戸=True,
        )

    def test_excel_sample_final_unit_price(self, 帯域, オフセット, オプション単価, 基準戸数):
        """最終㎡単価 57.48 を再現する

        注: Excel サンプルは戸数減チェック D24 が手動 OFF で、7 戸ながら戸数減が
        効いていない。よってここは戸数＝基準戸数（増減ゼロ）で 57.48 を再現する。
        戸数 7 を渡すと −200 × 3 = −600 が乗る（下の test_excel_sample_with_units_7）。
        """
        ベース = base_unit_price(
            施工床面積=Decimal("372.79"),
            種別="共同住宅",
            道路区分="2.5〜8m",
            基礎形状="べた",
            帯域=帯域,
            オフセット=オフセット,
        )
        assert ベース == Decimal("55")

        内訳 = option_costs(self._入力(戸数=基準戸数["共同住宅"]), オプション単価, 基準戸数["共同住宅"])
        # 内訳は Excel L17:L39 の列挙順（適用されない行は含めない）
        assert list(内訳) == [
            "防音室",
            "全地下（べた基礎）",
            "地盤調査",
            "測量",
            "家屋調査",
            "1層2戸共同住宅",
        ]
        assert 内訳 == {
            "防音室": Decimal("630"),
            "全地下（べた基礎）": Decimal("559.185"),
            "地盤調査": Decimal("55"),
            "測量": Decimal("33"),
            "家屋調査": Decimal("20"),
            "1層2戸共同住宅": Decimal("-372.79"),
        }
        assert sum(内訳.values()) == Decimal("924.395")

        assert final_unit_price(ベース, Decimal("372.79"), 内訳) == Decimal("57.48")

    def test_excel_sample_with_units_7(self, 帯域, オフセット, オプション単価, 基準戸数):
        """戸数 7（基準 10）を渡すと戸数減 −600 が内訳に入り 55.87 になる"""
        内訳 = option_costs(self._入力(戸数=7), オプション単価, 基準戸数["共同住宅"])
        assert 内訳["戸数減（基準戸数未満）"] == Decimal("-600")
        assert list(内訳) == [
            "防音室",
            "全地下（べた基礎）",
            "戸数減（基準戸数未満）",
            "地盤調査",
            "測量",
            "家屋調査",
            "1層2戸共同住宅",
        ]
        assert final_unit_price(Decimal("55"), Decimal("372.79"), 内訳) == Decimal("55.87")


class TestSiteBasedOptions:
    """敷地系 3 行は 敷地面積（有効宅地面積）× 単価（2026-08-24 大環主裁定）

    施工床 300㎡ に対し敷地は 150㎡ 前後を渡す。数量基準が 施工床 へ退行すると
    金額が 300 側に振れて落ちる。
    """

    def _入力(self, 有効宅地: str, 幅員: str) -> OptionInput:
        return OptionInput(
            施工床面積=Decimal("300"),
            基礎形状="べた",
            半地下有無="半地下有",
            戸数=10,  # 基準戸数と同じ＝戸数増減を立てない
            建物層数=4,
            有効宅地面積=Decimal(有効宅地),
            前面道路幅員=Decimal(幅員),
            調査費=False,
        )

    @pytest.mark.parametrize(
        "有効宅地,幅員,期待",
        [
            ("149.99", "3.99", {}),
            ("149.99", "4.00", {}),
            ("150.00", "3.99", {"敷地面積150㎡以上で立米車": "150.00"}),
            ("150.00", "4.00", {"敷地面積150㎡以上で中型車": "-150.00"}),
            ("80.01", "3.99", {}),
            ("80.01", "4.00", {}),
            ("80.00", "3.99", {"敷地小規模（敷地面積80㎡以下）": "80.00"}),
            ("80.00", "4.00", {"敷地小規模（敷地面積80㎡以下）": "80.00"}),
        ],
    )
    def test_site_options_boundaries(
        self, 有効宅地, 幅員, 期待, オプション単価, 基準戸数
    ):
        """適用可否と金額（＝敷地面積 × 単価）の両方を見る"""
        内訳 = option_costs(
            self._入力(有効宅地, 幅員), オプション単価, 基準戸数["共同住宅"]
        )
        assert 内訳 == {名称: Decimal(額) for 名称, 額 in 期待.items()}


class TestOptionDomainErrors:
    def test_soil_without_perimeter_raises(self, オプション単価, 基準戸数):
        """ソイル有りで外周長が無ければ例外（既定値でごまかさない）"""
        入力 = OptionInput(
            施工床面積=Decimal("300"),
            基礎形状="べた",
            半地下有無="半地下有",
            戸数=10,
            建物層数=4,
            有効宅地面積=Decimal("100"),
            前面道路幅員=Decimal("6"),
            調査費=False,
            ソイル="通常",
            外周長=None,
        )
        with pytest.raises(PricingDomainError) as e:
            option_costs(入力, オプション単価, 基準戸数["共同住宅"])
        assert "外周長" in str(e.value)
