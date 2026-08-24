"""単価テーブル型定義（pydanticモデル）"""
from decimal import Decimal
from typing import Dict, List, Optional, Union

from pydantic import BaseModel


class FoundationPriceEntry(BaseModel):
    """基礎単価テーブルのエントリ"""

    基礎種別: str  # 刃ベタ基礎 | 礎ベタ基礎 | 20m杭基礎 | 30m杭基礎 | 40m杭基礎
    基礎単価: float  # 万円/㎡
    単位: str = "万円/㎡"


class DemolitionPriceEntry(BaseModel):
    """解体単価テーブルのエントリ"""

    古家構造: str  # 無し | 木造 | 鉄骨造 | RC造 | RC造地下室付き
    解体単価: float  # 万円/㎡
    単位: str = "万円/㎡"


class RentalPriceEntry(BaseModel):
    """貸床単価テーブルのエントリ"""

    土地所在: str  # 区名
    貸床単価: int  # 円/㎡・月
    目標利回: float  # %
    エリア区分: str = ""
    特定エリア: str = ""
    単位: dict = {}


class GroundEvaluationEntry(BaseModel):
    """地盤評価テーブルのエントリ"""

    土地所在: str  # 区名
    地盤評価: str  # 硬質地盤 | 中間地盤 | 軟弱地盤


class FoundationTypeEntry(BaseModel):
    """基礎種別テーブルのエントリ"""

    地盤評価: str  # 硬質地盤 | 中間地盤 | 軟弱地盤
    建物層数: str  # "3層" | "4層" | "5層" | "6層" | "高層"
    基礎種別: str  # 刃ベタ基礎 | 礎ベタ基礎 | 20m杭基礎 | ...


# === v2: めぐる標準単価表・修正版（as_of 2026-08-04）の単価モデル ===


class UnitPriceBandEntry(BaseModel):
    """建築単価帯域テーブルのエントリ（下限以上・上限未満。上限 None は開放）"""

    下限: Decimal
    上限: Optional[Decimal] = None
    基準値: Decimal  # 万円/㎡（共同住宅・道路区分 2.5〜8m・べた基礎の基準）
    単位: str = "万円/㎡"


class UnitPriceOffsetEntry(BaseModel):
    """単価オフセットのエントリ（道路区分・基礎形状・種別で同型）"""

    区分: str
    オフセット: Decimal  # 万円/㎡
    単位: str = "万円/㎡"
    derived: bool = False  # Excel に行が無く導出した値
    note: str = ""
    excel_ラベル: List[str] = []


class UnitPriceOffsets(BaseModel):
    """単価オフセットテーブル全体（3 軸）"""

    道路区分: List[UnitPriceOffsetEntry]
    基礎形状: List[UnitPriceOffsetEntry]
    種別: List[UnitPriceOffsetEntry]


class OptionPriceEntry(BaseModel):
    """オプション単価テーブルのエントリ（金額 = 数量 × 単価）

    適用条件は人間向けの記述。判定の SSoT は python/pricing.py（文字列を解釈しない）。
    """

    名称: str
    単価: Decimal
    単位: str
    数量基準: str  # 語彙は オプション単価.json metadata、解釈は pricing._数量
    適用条件: Optional[str] = None
    備考: str = ""
    note: str = ""
    出所: str = ""


class ConstantsEntry(BaseModel):
    """定数テーブルのエントリ（値は数値、または基準戸数のような種別→値の写像）"""

    値: Union[Dict[str, int], Decimal]
    単位: str
    出所: str
