"""判定ルール（UseCase）

WORKFLOW Phase 3.2「AI 判断による補完」のうち決定論的なものを純粋関数に降ろす。
散文で持つと案件ごとに揺れ、境界値がテストできない。

`defaults_for` は欠損のうち埋められるものを「提案」として返すだけで、採用しない
（WORKFLOW のデータ確認ステップで利用者が上書きする前提）。幾何近似での補完はしない
——外周長は提案しない（根拠なき数値を発明しない）。

loader / main は import しない。定数（標準住戸面積）は引数で受ける。
"""
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict

from .pricing import (
    PricingDomainError,
    foundation_shape,  # noqa: F401  計画書 Stage 3 の列挙に合わせた re-export（実体は Domain）
    車両判定の敷地下限,
    車両判定の幅員境界,
    敷地小規模の上限,
)
from .schema.models import normalize_ground_evaluation

__all__ = [
    "road_class",
    "vehicle_class",
    "small_site",
    "housing_type",
    "foundation_shape",
    "estimate_units",
    "default_floors",
    "default_basement",
    "default_elevator",
    "default_soil",
    "defaults_for",
]

# 道路区分の境界（2026-08-24 裁定。IMPLEMENTATION_PLAN Stage 3）
_道路区分の狭小上限 = Decimal("2.5")  # 以下 → 2.5m以下
_道路区分の幹線下限 = Decimal("12")  # 超 → 幹線・バス通り

# 住宅種別の境界（WORKFLOW Phase 3.2: 接道長さ 4m 未満は長屋）
_長屋判定の接道上限 = Decimal("4")

# 既定値（WORKFLOW Phase 3.2）
_層数の既定 = {"長屋": 3, "共同住宅": 4}
_半地下無の区 = {"世田谷区"}  # 地下室条例の運用が厳しく、半地下を採らない
_EV必須の層数 = 5  # 5 層以上は EV 有（既定は 6 人乗り）


def road_class(前面道路幅員: Decimal) -> str:
    """前面道路幅員 → 単価オフセットの道路区分"""
    if 前面道路幅員 <= _道路区分の狭小上限:
        return "2.5m以下"
    if 前面道路幅員 > _道路区分の幹線下限:
        return "幹線・バス通り"
    return "2.5〜8m"


def vehicle_class(有効宅地面積: Decimal, 前面道路幅員: Decimal) -> str:
    """搬入車両の区分（オプション『敷地面積150㎡以上で…』の適用可否と同じ閾値）

    150㎡ 未満は車両オプションが立たない（＝『無』）。
    """
    if 有効宅地面積 < 車両判定の敷地下限:
        return "無"
    return "立米車" if 前面道路幅員 < 車両判定の幅員境界 else "中型車"


def small_site(有効宅地面積: Decimal) -> bool:
    """敷地小規模（80㎡ 以下）か"""
    return 有効宅地面積 <= 敷地小規模の上限


def housing_type(接道長さ: Decimal) -> str:
    """接道長さ → 住宅種別（4m 未満は長屋）

    接道長さは v2 の ProjectInput から退役した（施工条件係数の廃止に伴う）。
    住宅種別を判断するときだけ、引数として受け取る。
    """
    return "長屋" if 接道長さ < _長屋判定の接道上限 else "共同住宅"


def estimate_units(貸床面積: Decimal, 標準住戸面積: Decimal) -> int:
    """戸数の推定 = 貸床面積 ÷ 標準住戸面積 を四捨五入（2026-08-24 裁定）

    標準住戸面積は 定数.json が SSoT（呼び出し側が lookup_constant で渡す）。
    """
    if 標準住戸面積 <= 0:
        raise PricingDomainError(
            f"標準住戸面積は正の値が要ります（受領: {標準住戸面積}）"
        )
    return int((貸床面積 / 標準住戸面積).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def default_floors(住宅種別: str) -> int:
    """層数の既定（長屋 3 / 共同住宅 4）"""
    try:
        return _層数の既定[住宅種別]
    except KeyError:
        raise PricingDomainError(
            f"住宅種別 '{住宅種別}' の既定層数がありません（既知: {sorted(_層数の既定)}）"
        ) from None


def default_basement(土地所在: str) -> str:
    """半地下の既定（世田谷区 → 半地下無、それ以外 → 半地下有）"""
    return "半地下無" if 土地所在 in _半地下無の区 else "半地下有"


def default_elevator(建物層数: int) -> str:
    """EV の既定（5 層以上 → 6人乗り、それ以外 → 無）"""
    return "6人乗り" if 建物層数 >= _EV必須の層数 else "無"


def default_soil(地盤評価: str, 前面道路幅員: Decimal) -> str:
    """ソイルの既定（軟弱地盤のみ ON。狭小道路なら悪条件）

    軟弱地盤以外は『無』。ON を提案する場合、外周長が必須入力になる。
    """
    if normalize_ground_evaluation(地盤評価) != "軟弱地盤":
        return "無"
    return "悪条件" if road_class(前面道路幅員) == "2.5m以下" else "通常"


def defaults_for(partial_input: Dict[str, Any]) -> Dict[str, Any]:
    """欠損のうち埋められる項目だけを提案する（採用はしない）

    提案の根拠が partial_input に無ければ、その項目は返さない。
    外周長は提案しない（幾何近似での補完は根拠が無い）。
    戸数は貸床面積（計算結果）から推定するため、ここではなく estimate_units を使う。
    """
    提案: Dict[str, Any] = {}

    住宅種別 = partial_input.get("住宅種別")
    if 住宅種別 is None and "接道長さ" in partial_input:
        住宅種別 = housing_type(partial_input["接道長さ"])
        提案["住宅種別"] = 住宅種別

    if "半地下有無" not in partial_input and "土地所在" in partial_input:
        提案["半地下有無"] = default_basement(partial_input["土地所在"])

    建物層数 = partial_input.get("建物層数")
    if 建物層数 is None and 住宅種別 is not None:
        建物層数 = default_floors(住宅種別)
        提案["建物層数"] = 建物層数

    if "EV" not in partial_input and 建物層数 is not None:
        提案["EV"] = default_elevator(建物層数)

    if (
        "ソイル" not in partial_input
        and "地盤評価" in partial_input
        and "前面道路幅員" in partial_input
    ):
        提案["ソイル"] = default_soil(
            partial_input["地盤評価"], partial_input["前面道路幅員"]
        )

    return 提案
