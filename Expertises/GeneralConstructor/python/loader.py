"""JSONファイル読み込みとpydanticモデルへの変換"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from .schema.tables import (
    ConstantsEntry,
    DemolitionPriceEntry,
    FoundationPriceEntry,
    FoundationTypeEntry,
    GroundEvaluationEntry,
    OptionPriceEntry,
    RentalPriceEntry,
    UnitPriceBandEntry,
    UnitPriceOffsets,
)


def _空のオフセット() -> UnitPriceOffsets:
    return UnitPriceOffsets(道路区分=[], 基礎形状=[], 種別=[])


@dataclass
class Tables:
    """全テーブルを保持するデータクラス

    v2（めぐる標準単価表・修正版、as_of 2026-08-04）で読むテーブルだけを持つ。
    施工条件・建物形状・山留工法・山留単価は係数モデルごと退役した。
    """

    # === 温存（v1 から）===
    基礎単価: List[FoundationPriceEntry] = field(default_factory=list)
    解体単価: List[DemolitionPriceEntry] = field(default_factory=list)
    貸床単価: List[RentalPriceEntry] = field(default_factory=list)
    地盤評価: List[GroundEvaluationEntry] = field(default_factory=list)
    基礎種別: List[FoundationTypeEntry] = field(default_factory=list)

    # === v2: めぐる標準単価表・修正版（as_of 2026-08-04）===
    建築単価帯域: List[UnitPriceBandEntry] = field(default_factory=list)
    単価オフセット: UnitPriceOffsets = field(default_factory=_空のオフセット)
    オプション単価: List[OptionPriceEntry] = field(default_factory=list)
    定数: Dict[str, ConstantsEntry] = field(default_factory=dict)


def _read_table(data_path: Path, name: str) -> dict:
    """必須テーブルJSONを読み込む（欠落は即エラー）

    テーブルが欠けたまま空で計算を続けると、エラー無しに過少な単価で
    採算判断が出る（静かな失敗）。読み込み時点で落とす。
    """
    file = data_path / f"{name}.json"
    if not file.exists():
        raise FileNotFoundError(f"Required table not found: {file}")
    with open(file, "r", encoding="utf-8") as f:
        return json.load(f)


def load_tables(data_path: Path | str) -> Tables:
    """指定ディレクトリからすべてのテーブルを読み込む

    Args:
        data_path: JSONファイルが格納されているディレクトリパス（PathまたはstrでOK）

    Returns:
        Tables: 全テーブルを保持するデータクラス

    Raises:
        FileNotFoundError: ディレクトリ、または必須テーブルが存在しない場合
    """
    if isinstance(data_path, str):
        data_path = Path(data_path)
    if not data_path.exists():
        raise FileNotFoundError(f"Data directory not found: {data_path}")

    def rows(name: str, model):
        return [model.model_validate(entry) for entry in _read_table(data_path, name)[name]]

    return Tables(
        基礎単価=rows("基礎単価テーブル", FoundationPriceEntry),
        解体単価=rows("解体単価テーブル", DemolitionPriceEntry),
        貸床単価=rows("貸床単価テーブル", RentalPriceEntry),
        地盤評価=rows("地盤評価テーブル", GroundEvaluationEntry),
        基礎種別=rows("基礎種別テーブル", FoundationTypeEntry),
        建築単価帯域=rows("建築単価帯域", UnitPriceBandEntry),
        単価オフセット=UnitPriceOffsets.model_validate(
            _read_table(data_path, "単価オフセット")["単価オフセット"]
        ),
        オプション単価=rows("オプション単価", OptionPriceEntry),
        定数={
            名称: ConstantsEntry.model_validate(値)
            for 名称, 値 in _read_table(data_path, "定数")["定数"].items()
        },
    )
