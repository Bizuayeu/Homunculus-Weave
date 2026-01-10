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


def load_tables(data_path: Path | str) -> Tables:
    """指定ディレクトリからすべてのテーブルを読み込む

    Args:
        data_path: JSONファイルが格納されているディレクトリパス（PathまたはstrでOK）

    Returns:
        Tables: 全テーブルを保持するデータクラス

    Raises:
        FileNotFoundError: ディレクトリが存在しない場合
    """
    if isinstance(data_path, str):
        data_path = Path(data_path)
    if not data_path.exists():
        raise FileNotFoundError(f"Data directory not found: {data_path}")

    tables = Tables()

    # 建築単価テーブル
    building_price_file = data_path / "建築単価テーブル.json"
    if building_price_file.exists():
        with open(building_price_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            tables.建築単価 = BuildingPriceTable.model_validate(data)

    # 基礎単価テーブル
    foundation_price_file = data_path / "基礎単価テーブル.json"
    if foundation_price_file.exists():
        with open(foundation_price_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            tables.基礎単価 = [
                FoundationPriceEntry.model_validate(entry)
                for entry in data.get("基礎単価テーブル", [])
            ]

    # 山留単価テーブル
    retaining_price_file = data_path / "山留単価テーブル.json"
    if retaining_price_file.exists():
        with open(retaining_price_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            tables.山留単価 = [
                RetainingWallPriceEntry.model_validate(entry)
                for entry in data.get("山留単価テーブル", [])
            ]

    # 解体単価テーブル
    demolition_price_file = data_path / "解体単価テーブル.json"
    if demolition_price_file.exists():
        with open(demolition_price_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            tables.解体単価 = [
                DemolitionPriceEntry.model_validate(entry)
                for entry in data.get("解体単価テーブル", [])
            ]

    # 貸床単価テーブル
    rental_price_file = data_path / "貸床単価テーブル.json"
    if rental_price_file.exists():
        with open(rental_price_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            tables.貸床単価 = [
                RentalPriceEntry.model_validate(entry)
                for entry in data.get("貸床単価テーブル", [])
            ]

    # 施工条件テーブル
    condition_file = data_path / "施工条件テーブル.json"
    if condition_file.exists():
        with open(condition_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            tables.施工条件 = [
                ConstructionConditionEntry.model_validate(entry)
                for entry in data.get("施工条件テーブル", [])
            ]

    # 建物形状テーブル
    shape_file = data_path / "建物形状テーブル.json"
    if shape_file.exists():
        with open(shape_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            tables.建物形状 = [
                BuildingShapeEntry.model_validate(entry)
                for entry in data.get("建物形状テーブル", [])
            ]

    # 地盤評価テーブル
    ground_file = data_path / "地盤評価テーブル.json"
    if ground_file.exists():
        with open(ground_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            tables.地盤評価 = [
                GroundEvaluationEntry.model_validate(entry)
                for entry in data.get("地盤評価テーブル", [])
            ]

    # 基礎種別テーブル
    foundation_type_file = data_path / "基礎種別テーブル.json"
    if foundation_type_file.exists():
        with open(foundation_type_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            tables.基礎種別 = [
                FoundationTypeEntry.model_validate(entry)
                for entry in data.get("基礎種別テーブル", [])
            ]

    # 山留工法テーブル
    retaining_method_file = data_path / "山留工法テーブル.json"
    if retaining_method_file.exists():
        with open(retaining_method_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            tables.山留工法 = [
                RetainingMethodEntry.model_validate(entry)
                for entry in data.get("山留工法テーブル", [])
            ]

    return tables
