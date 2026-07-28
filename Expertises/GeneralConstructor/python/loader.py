"""JSONファイル読み込みとpydanticモデルへの変換"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from .schema.tables import (
    BuildingPriceTable,
    BuildingPriceEntry,
    FoundationPriceEntry,
    RetainingWallPriceEntry,
    DemolitionPriceEntry,
    RentalPriceEntry,
    ConstructionConditionEntry,
    BuildingShapeEntry,
    GroundEvaluationEntry,
    FoundationTypeEntry,
    RetainingMethodEntry,
)


@dataclass
class Tables:
    """全テーブルを保持するデータクラス"""

    建築単価: BuildingPriceTable = field(default_factory=lambda: BuildingPriceTable(建築単価テーブル=[], metadata={}))
    基礎単価: List[FoundationPriceEntry] = field(default_factory=list)
    山留単価: List[RetainingWallPriceEntry] = field(default_factory=list)
    解体単価: List[DemolitionPriceEntry] = field(default_factory=list)
    貸床単価: List[RentalPriceEntry] = field(default_factory=list)
    施工条件: List[ConstructionConditionEntry] = field(default_factory=list)
    建物形状: List[BuildingShapeEntry] = field(default_factory=list)
    地盤評価: List[GroundEvaluationEntry] = field(default_factory=list)
    基礎種別: List[FoundationTypeEntry] = field(default_factory=list)
    山留工法: List[RetainingMethodEntry] = field(default_factory=list)


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
        建築単価=BuildingPriceTable.model_validate(_read_table(data_path, "建築単価テーブル")),
        基礎単価=rows("基礎単価テーブル", FoundationPriceEntry),
        山留単価=rows("山留単価テーブル", RetainingWallPriceEntry),
        解体単価=rows("解体単価テーブル", DemolitionPriceEntry),
        貸床単価=rows("貸床単価テーブル", RentalPriceEntry),
        施工条件=rows("施工条件テーブル", ConstructionConditionEntry),
        建物形状=rows("建物形状テーブル", BuildingShapeEntry),
        地盤評価=rows("地盤評価テーブル", GroundEvaluationEntry),
        基礎種別=rows("基礎種別テーブル", FoundationTypeEntry),
        山留工法=rows("山留工法テーブル", RetainingMethodEntry),
    )
