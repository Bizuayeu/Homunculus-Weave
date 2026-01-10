"""入出力モデル定義（pydanticモデル）"""
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ProjectInput(BaseModel):
    """プロジェクト入力モデル（マイソクから取得 + AI判断値）"""

    # === 基本情報（マイソクから）===
    土地価格: int = Field(..., description="万円")
    土地所在: str
    有効宅地面積: Decimal = Field(..., description="㎡")

    # === 施工条件 ===
    前面道路幅員: Decimal = Field(..., description="m")
    搬入経路: Literal["規制無", "規制有"] = "規制無"
    道路種別: Literal["公道", "私道"] = "私道"
    接道長さ: Decimal = Field(..., description="m")

    # === 解体 ===
    古家構造: Literal["無し", "木造", "鉄骨造", "RC造", "その他"]
    解体面積: Decimal = Field(default=Decimal("0"), description="㎡")

    # === 設計条件 ===
    実効建蔽率: Decimal = Field(..., description="%")
    用途地域: str
    高度地区: Optional[str] = None
    最大容積率: Decimal = Field(..., description="%")

    # === 建物構造（AI判断 or 手入力）===
    住宅種別: Literal["長屋", "共同住宅"]
    建物層数: Literal[3, 4, 5, 6]
    半地下有無: Literal["半地下有", "半地下無"]
    EV有無: Literal["EV有", "EV無"]
    壁率: Literal["標準的", "やや高い", "高い"]
    設備率: Literal["標準的", "やや高い", "高い"]
    グレード: Literal["標準的", "やや高い", "高い"] = "やや高い"

    # === 地盤（AI判断 or テーブル参照）===
    # 中間地盤①/②はAI判断用、テーブル参照時は「中間地盤」に統合
    地盤評価: Literal["硬質地盤", "中間地盤", "中間地盤①", "中間地盤②", "軟弱地盤"]


class ProjectOutput(BaseModel):
    """プロジェクト出力モデル（計算結果）"""

    # === 中間計算値 ===
    施工条件係数: Decimal
    建物形状係数: Decimal
    建築面積: Decimal
    基礎種別: str
    基礎単価: int
    山留工法: str
    山留単価: int
    共用部面積: Decimal
    地下緩和面積: Decimal
    最大施工面積: Decimal
    施工面積: Decimal
    標準建築単価: int
    補正建築単価: Decimal

    # === 費用（万円）===
    解体費用: int
    基礎費用: int
    山留費用: int
    地盤費用: int
    建物価格: int
    PJ総額: int

    # === 収支 ===
    貸床面積: Decimal
    貸床単価: int  # 円/㎡
    年間売上: int  # 万円
    表面利回: Decimal  # %
    目標利回: Decimal  # %
