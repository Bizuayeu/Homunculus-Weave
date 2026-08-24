"""単価モデル（Domain）

めぐる標準単価表・修正版（as_of 2026-08-04）の
「ベース㎡単価（帯域 ＋ 道路・基礎形状・種別オフセット）＋ オプション加減算」を
テーブル駆動の純粋関数として実装する。

loader / main は import しない（本尊化時にそのまま持ち出せる境界）。
テーブルの値（単価・数量基準）の SSoT は python/data/*.json、
適用条件と計算式の SSoT はこのモジュール（JSON の 適用条件 文字列は解釈しない）。
"""
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Mapping, Optional

from .schema.tables import (
    OptionPriceEntry,
    UnitPriceBandEntry,
    UnitPriceOffsetEntry,
    UnitPriceOffsets,
)


class PricingDomainError(ValueError):
    """単価モデルの定義域外（帯域外・未知の区分・必須入力の欠落）

    既定値へのフォールバックは置かない。過少な単価で採算判断が出る静かな失敗を、
    テーブル参照の時点で落とす（loader._read_table と同じ規律）。
    """


# 適用条件の閾値。出所は python/data/オプション単価.json 各行の 適用条件
_戸数増減の面積境界 = Decimal("300")  # 戸数増は 300㎡ 未満、戸数減は 300㎡ 以上
_敷地小規模の上限 = Decimal("80")  # 2026-08-24 裁定で Excel の 70㎡ から変更
_車両判定の敷地下限 = Decimal("150")
_車両判定の幅員境界 = Decimal("4")  # 4m 未満は立米車、4m 以上は中型車
_六層 = 6  # 「6層」行の対象層数
_ソイル外周係数 = Decimal("0.95")  # 数量基準「外周長×0.95」（Excel S35/S36）

# 列挙入力の許容値。未知の値は行が静かに立たなくなるため、入力時点で落とす
_許容値 = {
    "基礎形状": {"べた", "杭"},
    "半地下有無": {"半地下有", "半地下無", "全地下"},
    "EV": {"無", "6人乗り", "9人乗り", "家庭用"},
    "ソイル": {"無", "通常", "悪条件"},
    "レコリード": {"無", "床のみ", "部屋ごと"},
    "ペット": {"無", "2点", "4点"},
}


@dataclass(frozen=True)
class OptionInput:
    """オプション判定に要る入力一式

    受け口を dataclass にしたのは Testability 優先（Decision Priority 1）。
    16 項目を引数で並べると呼び出しが読めず、テストごとの差分も見えない。
    frozen なら 1 ケースを組んで dataclasses.replace で 1 項目だけ振れる。

    既定値は「そのオプションを頼んでいない」中立値のみ。
    調査費は「既定 ON」という運用方針（v2 ProjectInput 側の既定）なので、
    Domain では必須にして方針を持ち込まない。
    """

    施工床面積: Decimal
    基礎形状: str
    半地下有無: str
    戸数: int
    建物層数: int
    有効宅地面積: Decimal
    前面道路幅員: Decimal
    調査費: bool
    EV: str = "無"
    ソイル: str = "無"
    外周長: Optional[Decimal] = None
    防音室数: int = 0
    レコリード: str = "無"
    ペット: str = "無"
    自火報: bool = False
    一層二戸: bool = False

    def __post_init__(self) -> None:
        for 項目, 許容 in _許容値.items():
            値 = getattr(self, 項目)
            if 値 not in 許容:
                raise PricingDomainError(
                    f"{項目} の値 '{値}' は未知です（許容: {sorted(許容)}）"
                )


# オプション行の適用条件。キーは オプション単価.json の 名称
_適用条件 = {
    "防音室": lambda i, k: True,  # 数量（防音室数）が 0 なら積まれない
    "全地下（べた基礎）": lambda i, k: i.半地下有無 == "全地下" and i.基礎形状 == "べた",
    "全地下（杭基礎）": lambda i, k: i.半地下有無 == "全地下" and i.基礎形状 == "杭",
    "自火報": lambda i, k: i.自火報,
    "EV（6人乗り）": lambda i, k: i.EV == "6人乗り",
    "EV（9人乗り）": lambda i, k: i.EV == "9人乗り",
    "家庭用EV": lambda i, k: i.EV == "家庭用",
    "戸数増（基準戸数超）": lambda i, k: (
        i.戸数 > k and i.施工床面積 < _戸数増減の面積境界
    ),
    "戸数減（基準戸数未満）": lambda i, k: (
        i.戸数 < k and i.施工床面積 >= _戸数増減の面積境界
    ),
    "部屋ごとレコリード仕様": lambda i, k: i.レコリード == "部屋ごと",
    "床のみレコリード仕様": lambda i, k: i.レコリード == "床のみ",
    "ペット仕様（4点セット）": lambda i, k: i.ペット == "4点",
    "ペット仕様（2点セット）": lambda i, k: i.ペット == "2点",
    "地盤調査": lambda i, k: i.調査費,
    "測量": lambda i, k: i.調査費,
    "家屋調査": lambda i, k: i.調査費,
    "敷地小規模（敷地面積80㎡以下）": lambda i, k: i.有効宅地面積 <= _敷地小規模の上限,
    "敷地面積150㎡以上で立米車": lambda i, k: (
        i.有効宅地面積 >= _車両判定の敷地下限 and i.前面道路幅員 < _車両判定の幅員境界
    ),
    "敷地面積150㎡以上で中型車": lambda i, k: (
        i.有効宅地面積 >= _車両判定の敷地下限 and i.前面道路幅員 >= _車両判定の幅員境界
    ),
    "ソイル必要な現場": lambda i, k: i.ソイル == "通常",
    "ソイル必要な現場（施工条件悪い）": lambda i, k: i.ソイル == "悪条件",
    "ソイル必要な現場（山留マイナス分）": lambda i, k: i.ソイル != "無",
    "1層2戸共同住宅": lambda i, k: i.一層二戸,
    "6層": lambda i, k: i.建物層数 == _六層,
    "半地下無": lambda i, k: i.半地下有無 == "半地下無",
}


def _lookup_offset(
    区分: str,
    entries: List[UnitPriceOffsetEntry],
    軸: str,
) -> Decimal:
    """単価オフセットを引く（未知の区分は例外）"""
    for entry in entries:
        if entry.区分 == 区分:
            return entry.オフセット
    raise PricingDomainError(
        f"{軸} '{区分}' は単価オフセットテーブルにありません"
        f"（既知: {[e.区分 for e in entries]}）"
    )


def _数量(数量基準: str, 入力: OptionInput, 基準戸数: int) -> Decimal:
    """オプション単価.json の 数量基準 を数量へ写す"""
    if 数量基準 == "施工床":
        return 入力.施工床面積
    if 数量基準 == "戸数":
        return Decimal(入力.戸数)
    if 数量基準 == "室数":
        return Decimal(入力.防音室数)
    if 数量基準 == "層数−1":
        return Decimal(入力.建物層数 - 1)
    if 数量基準 == "戸数−基準戸数":
        return Decimal(入力.戸数 - 基準戸数)
    if 数量基準 == "基準戸数−戸数":
        return Decimal(基準戸数 - 入力.戸数)
    if 数量基準 == "外周長×0.95":
        if 入力.外周長 is None:
            raise PricingDomainError(
                "ソイルを計上するには外周長が要ります（既定値は置かない）"
            )
        return 入力.外周長 * _ソイル外周係数
    if 数量基準 == "式":
        return Decimal("1")
    raise PricingDomainError(f"数量基準 '{数量基準}' の解釈が実装されていません")


def resolve_band(
    施工床面積: Decimal,
    帯域: List[UnitPriceBandEntry],
) -> UnitPriceBandEntry:
    """施工床面積から建築単価帯域を引く（下限以上・上限未満、上限 None は開放）"""
    for entry in 帯域:
        if 施工床面積 < entry.下限:
            continue
        if entry.上限 is None or 施工床面積 < entry.上限:
            return entry
    if not 帯域:
        raise PricingDomainError("建築単価帯域テーブルが空です")
    raise PricingDomainError(
        f"施工床面積 {施工床面積}㎡ は帯域外です"
        f"（帯域下限 {min(e.下限 for e in 帯域)}㎡ 以上が対象）"
    )


def base_unit_price(
    施工床面積: Decimal,
    種別: str,
    道路区分: str,
    基礎形状: str,
    帯域: List[UnitPriceBandEntry],
    オフセット: UnitPriceOffsets,
) -> Decimal:
    """ベース㎡単価 = 帯域基準値 + 道路オフセット + 基礎形状オフセット + 種別オフセット

    単位: 万円/㎡
    """
    band = resolve_band(施工床面積, 帯域)
    return (
        band.基準値
        + _lookup_offset(道路区分, オフセット.道路区分, "道路区分")
        + _lookup_offset(基礎形状, オフセット.基礎形状, "基礎形状")
        + _lookup_offset(種別, オフセット.種別, "種別")
    )


def option_costs(
    入力: OptionInput,
    オプション単価: List[OptionPriceEntry],
    基準戸数: int,
) -> Dict[str, Decimal]:
    """適用されるオプションの内訳を返す（金額 = 数量 × 単価、単位: 万円）

    列挙順は オプション単価.json（Excel L17:L39）のまま。
    適用されない行と数量 0 の行は含めない。万円未満は丸めずに保持する
    （丸めは最終㎡単価の一度だけ）。
    """
    内訳: Dict[str, Decimal] = {}
    for entry in オプション単価:
        if entry.名称 not in _適用条件:
            raise PricingDomainError(
                f"オプション '{entry.名称}' の適用条件が実装されていません"
            )
        if not _適用条件[entry.名称](入力, 基準戸数):
            continue
        数量 = _数量(entry.数量基準, 入力, 基準戸数)
        if 数量 == 0:
            continue
        内訳[entry.名称] = 数量 * entry.単価
    return 内訳


def final_unit_price(
    ベース単価: Decimal,
    施工床面積: Decimal,
    オプション内訳: Mapping[str, Decimal],
) -> Decimal:
    """最終㎡単価 = (ベース㎡単価 × 施工床 + オプション合計) / 施工床

    単位: 万円/㎡（ROUND_HALF_UP 小数 2 桁）
    """
    if 施工床面積 <= 0:
        raise PricingDomainError(f"施工床面積は正の値が要ります（受領: {施工床面積}）")
    工事費 = ベース単価 * 施工床面積 + sum(オプション内訳.values(), Decimal("0"))
    return (工事費 / 施工床面積).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
