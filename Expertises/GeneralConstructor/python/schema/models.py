"""入出力モデル定義（pydanticモデル）"""
from decimal import Decimal
from typing import Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

# 地盤評価の正規化写像。AI 判断は 中間地盤①/② の粒度で出るが、
# テーブル（基礎種別テーブル）は「中間地盤」しか持たない。
# silent fallback（未知は既定値）ではなく、この表に載る語だけを明示的に畳む。
_地盤評価の正規化 = {
    "中間地盤①": "中間地盤",
    "中間地盤②": "中間地盤",
}


def normalize_ground_evaluation(地盤評価: str) -> str:
    """地盤評価をテーブル参照用の語へ写す（写像に無い語はそのまま返す）"""
    return _地盤評価の正規化.get(地盤評価, 地盤評価)


class ProjectInput(BaseModel):
    """プロジェクト入力モデル（マイソクから取得 + AI判断値）

    extra="forbid": v1 の退役キー（搬入経路・壁率・グレード等）を黙って無視すると、
    指定したはずの条件が単価に効かないまま採算判断が出る。未知キーは受領時に落とす。
    """

    model_config = ConfigDict(extra="forbid")

    # === 基本情報（マイソクから）===
    土地価格: int = Field(..., description="万円")
    土地所在: str
    有効宅地面積: Decimal = Field(..., description="㎡")

    # === 施工条件 ===
    前面道路幅員: Decimal = Field(..., description="m。道路区分の判定に使う")

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
    戸数: int = Field(..., description="戸。推定値は inference が提案し、確認後の値を入れる")
    半地下有無: Literal["半地下有", "半地下無", "全地下"]
    EV: Literal["無", "6人乗り", "9人乗り", "家庭用"] = "無"

    # === 地盤 ===
    # 中間地盤①/②はAI判断用、テーブル参照時は normalize_ground_evaluation で「中間地盤」へ
    地盤評価: Literal["硬質地盤", "中間地盤", "中間地盤①", "中間地盤②", "軟弱地盤"]
    基礎種別: Optional[str] = Field(
        default=None, description="override。無ければ 地盤評価 × 建物層数 から写像"
    )
    ソイル: Literal["無", "通常", "悪条件"] = "無"
    外周長: Optional[Decimal] = Field(default=None, description="m。ソイル≠無 のとき必須")

    # === オプション ===
    防音室数: int = 0
    レコリード: Literal["無", "床のみ", "部屋ごと"] = "無"
    ペット: Literal["無", "2点", "4点"] = "無"
    自火報: bool = False
    調査費: bool = Field(default=True, description="地盤調査・測量・家屋調査の 3 点")
    一層二戸: bool = False

    @model_validator(mode="after")
    def validate_soil_perimeter(self) -> "ProjectInput":
        """ソイルを計上するなら外周長が要る（既定値は置かない）"""
        if self.ソイル != "無" and self.外周長 is None:
            raise ValueError(
                f"ソイル＝{self.ソイル} のときは外周長が必須です（既定値は置かない）"
            )
        return self


class ProjectOutput(BaseModel):
    """プロジェクト出力モデル（計算結果）"""

    # === 中間計算値 ===
    建築面積: Decimal
    基礎種別: str
    共用部面積: Decimal
    地下緩和面積: Decimal
    最大施工面積: Decimal
    施工面積: Decimal

    # === 単価（万円/㎡）===
    道路区分: str
    帯域: str
    ベース単価: Decimal  # 万円/㎡
    オプション内訳: Dict[str, Decimal]  # 万円。万円未満を保持したまま返す
    最終単価: Decimal  # 万円/㎡

    # === 費用（万円）===
    解体費用: int
    杭費用: int
    建物価格: int
    工事代金: int
    建設経費: int
    PJ総額: int  # 万円（税込。単価表が税込なので ×1.1 はしない）

    # === 収支 ===
    貸床面積: Decimal
    貸床単価: int  # 円/㎡
    年間売上: int  # 万円
    表面利回: Decimal  # %（PJ総額ベース）
    目標利回: Decimal  # %
