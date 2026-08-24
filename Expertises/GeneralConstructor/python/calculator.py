"""計算ロジック（めぐる標準単価表・修正版 v2、as_of 2026-08-04）

工事代金 = 建物価格（施工床 × 最終㎡単価）＋ 杭費用 ＋ 解体費用。
v1 の「標準建築単価 ×(1＋施工条件係数＋建物形状係数)＋基礎・山留の㎡別建て」は退役。

テーブル参照は全て失敗時に TableLookupError を送出する（既定値へは落ちない）。
"""
from decimal import ROUND_HALF_UP, Decimal
from typing import Tuple

from .inference import road_class
from .loader import Tables
from .pricing import (
    OptionInput,
    TableLookupError,
    base_unit_price,
    final_unit_price,
    foundation_shape,
    option_costs,
    resolve_band,
)
from .schema.models import ProjectInput, ProjectOutput, normalize_ground_evaluation
from .schema.tables import UnitPriceBandEntry

_万円 = Decimal("1")
_小数2桁 = Decimal("0.01")


def _万円に丸める(金額: Decimal) -> int:
    return int(金額.quantize(_万円, rounding=ROUND_HALF_UP))


# === 表示補助 ===


def _band_label(band: UnitPriceBandEntry) -> str:
    """帯域を人が読める名前にする（上限開放は『500〜』）"""
    if band.上限 is None:
        return f"{band.下限}〜"
    return f"{band.下限}-{band.上限}"


# === 面積計算 ===


def calculate_building_area(
    有効宅地面積: Decimal,
    実効建蔽率: Decimal,
) -> Decimal:
    """建築面積 = 有効宅地面積 × 実効建蔽率（上限70%）

    ビジネスルール: 実効建蔽率≦70%
    """
    effective_rate = min(実効建蔽率, Decimal("70"))
    return (有効宅地面積 * effective_rate / Decimal("100")).quantize(
        _小数2桁, rounding=ROUND_HALF_UP
    )


def calculate_floor_common_area(
    EV: str,
    共用部面積_層あたり: Decimal,
    EV面積: Decimal,
) -> Decimal:
    """層あたり共用部面積 = 8 + EV面積（EV＝無 なら EV面積を足さない）

    数値は 定数.json（共用部面積_層あたり・EV面積）が SSoT。
    """
    return 共用部面積_層あたり + (EV面積 if EV != "無" else Decimal("0"))


def calculate_common_area(建物層数: int, 層あたり共用部面積: Decimal) -> Decimal:
    """共用部面積 = 建物層数 × 層あたり共用部面積"""
    return Decimal(建物層数) * 層あたり共用部面積


def calculate_basement_relaxation_area(
    建築面積: Decimal,
    半地下有無: str,
    層あたり共用部面積: Decimal,
) -> Decimal:
    """地下緩和面積 = 建築面積 − 層あたり共用部面積（8 + EV面積）。半地下無は 0

    v1 は EV 分を数えず 8 固定で引いていた（EV 有の案件で緩和を 2㎡ 過大に見ていた）。

    cc-defer: 全地下は半地下有と同じ扱い（緩和あり）とした。計画書に規定が無く、
    地下床の容積率緩和という趣旨から緩和ありを採る。岡田氏の確認が取れたら是正する
    """
    if 半地下有無 == "半地下無":
        return Decimal("0")
    return 建築面積 - 層あたり共用部面積


def calculate_max_construction_area(
    有効宅地面積: Decimal,
    最大容積率: Decimal,
    共用部面積: Decimal,
    地下緩和面積: Decimal,
) -> Decimal:
    """最大施工面積 = 有効宅地面積 × 最大容積率 + 共用部面積 + 地下緩和面積"""
    return (
        有効宅地面積 * 最大容積率 / Decimal("100") + 共用部面積 + 地下緩和面積
    ).quantize(_小数2桁, rounding=ROUND_HALF_UP)


def calculate_construction_area(
    建築面積: Decimal,
    建物層数: int,
    最大施工面積: Decimal,
) -> Decimal:
    """施工面積 = min(建築面積 × 建物層数, 最大施工面積)"""
    actual = 建築面積 * Decimal(建物層数)
    return min(actual, 最大施工面積)


# === コスト計算 ===


def calculate_demolition_cost(解体面積: Decimal, 解体単価: Decimal) -> int:
    """解体費用 = 解体面積 × 解体単価（単位: 万円）

    v1 の施工条件係数の乗算は廃止（条件は㎡単価へ焼き込む単価表の設計思想に合わせる）。
    """
    return _万円に丸める(解体面積 * 解体単価)


def calculate_pile_cost(建築面積: Decimal, 基礎種別: str, tables: Tables) -> int:
    """杭費用 = 建築面積 × 杭長別単価（べた基礎は 0。単位: 万円）

    べた基礎の費用はベース㎡単価に内包済み。別建てするのは杭のみ。
    """
    if foundation_shape(基礎種別) == "べた":
        return 0
    return _万円に丸める(建築面積 * lookup_foundation_price(基礎種別, tables))


def calculate_building_cost(施工面積: Decimal, 最終単価: Decimal) -> int:
    """建物価格 = 施工面積 × 最終単価（万円/㎡）。単位: 万円"""
    return _万円に丸める(施工面積 * 最終単価)


def calculate_construction_expense(工事代金: int, 建設経費率: Decimal) -> int:
    """建設経費 = 工事代金 × 建設経費率（率は 定数.json が SSoT）"""
    return _万円に丸める(Decimal(工事代金) * 建設経費率)


def calculate_project_total(
    土地価格: int,
    工事代金: int,
    建設経費: int,
) -> int:
    """PJ総額（税抜）= 土地価格 + 工事代金 + 建設経費"""
    return 土地価格 + 工事代金 + 建設経費


def calculate_project_total_with_tax(
    土地価格: int,
    工事代金: int,
    建設経費: int,
    消費税率: Decimal,
) -> int:
    """PJ総額（税込）= 土地価格 + (工事代金 + 建設経費) × (1 + 消費税率)

    土地は非課税なので課税されるのは建物分のみ。
    """
    建物分 = Decimal(工事代金 + 建設経費) * (Decimal("1") + 消費税率)
    return 土地価格 + _万円に丸める(建物分)


# === 収益計算 ===


def calculate_rental_floor_area(
    施工面積: Decimal,
    共用部面積: Decimal,
) -> Decimal:
    """貸床面積 = 施工面積 - 共用部面積"""
    return 施工面積 - 共用部面積


def calculate_annual_income(
    貸床面積: Decimal,
    貸床単価: int,
) -> int:
    """年間売上 = 貸床面積 × 貸床単価 × 12

    貸床単価: 円/㎡・月
    戻り値: 万円
    """
    income_yen = 貸床面積 * Decimal(貸床単価) * Decimal("12")
    return _万円に丸める(income_yen / Decimal("10000"))


def calculate_surface_yield(
    年間売上: int,
    PJ総額: int,
) -> Decimal:
    """表面利回 = 年間売上 / PJ総額 × 100（税抜 PJ総額ベース）"""
    return (Decimal(年間売上) / Decimal(PJ総額) * Decimal("100")).quantize(
        _小数2桁, rounding=ROUND_HALF_UP
    )


# === テーブル参照 ===


def lookup_constant(名称: str, tables: Tables) -> Decimal:
    """定数テーブルから単一の数値を取得"""
    entry = tables.定数.get(名称)
    if entry is None:
        raise TableLookupError(
            f"定数 '{名称}' が定数テーブルにありません（既知: {sorted(tables.定数)}）"
        )
    if not isinstance(entry.値, Decimal):
        raise TableLookupError(
            f"定数 '{名称}' は単一の数値ではありません（値: {entry.値}）"
        )
    return entry.値


def lookup_standard_units(住宅種別: str, tables: Tables) -> int:
    """定数テーブルから住宅種別ごとの基準戸数を取得（戸数増減の起点）"""
    entry = tables.定数.get("基準戸数")
    if entry is None or not isinstance(entry.値, dict):
        raise TableLookupError(
            "定数 '基準戸数' が種別→戸数の写像として定義されていません"
        )
    if 住宅種別 not in entry.値:
        raise TableLookupError(
            f"住宅種別 '{住宅種別}' の基準戸数がありません（既知: {sorted(entry.値)}）"
        )
    return entry.値[住宅種別]


def lookup_foundation_type(
    地盤評価: str,
    建物層数: int,
    tables: Tables,
) -> str:
    """基礎種別テーブルから基礎種別を取得（地盤評価 × 建物層数）

    cc-defer: 「高層」行は ProjectInput.建物層数 が Literal[3,4,5,6] のため到達不能。
    7 層以上を扱う要求が出たら Literal と併せて解禁する（本改定では対象外）。
    """
    層数_str = f"{建物層数}層" if 建物層数 <= 6 else "高層"

    for entry in tables.基礎種別:
        if entry.地盤評価 == 地盤評価 and entry.建物層数 == 層数_str:
            return entry.基礎種別

    raise TableLookupError(
        f"地盤評価 '{地盤評価}' × '{層数_str}' の基礎種別が基礎種別テーブルにありません"
    )


def lookup_foundation_price(
    基礎種別: str,
    tables: Tables,
) -> Decimal:
    """基礎単価テーブルから杭長別単価を取得（杭 3 行のみ）"""
    for entry in tables.基礎単価:
        if entry.基礎種別 == 基礎種別:
            return Decimal(str(entry.基礎単価))

    raise TableLookupError(
        f"基礎種別 '{基礎種別}' が基礎単価テーブルにありません"
        f"（既知: {[e.基礎種別 for e in tables.基礎単価]}）"
    )


def lookup_demolition_price(
    古家構造: str,
    tables: Tables,
) -> Decimal:
    """解体単価テーブルから解体単価を取得"""
    for entry in tables.解体単価:
        if entry.古家構造 == 古家構造:
            return Decimal(str(entry.解体単価))

    raise TableLookupError(
        f"古家構造 '{古家構造}' が解体単価テーブルにありません"
        f"（既知: {[e.古家構造 for e in tables.解体単価]}）"
    )


def lookup_rental_price(
    土地所在: str,
    tables: Tables,
) -> Tuple[int, Decimal]:
    """貸床単価テーブルから貸床単価と目標利回を取得"""
    for entry in tables.貸床単価:
        if entry.土地所在 == 土地所在:
            return entry.貸床単価, Decimal(str(entry.目標利回))

    raise TableLookupError(
        f"土地所在 '{土地所在}' が貸床単価テーブルにありません"
        "（エリア指定が要る区は『足立区（千住エリア内）』のように括弧付きで指定する）"
    )


# === メイン計算関数 ===


def calculate_project(
    input: ProjectInput,
    tables: Tables,
) -> ProjectOutput:
    """プロジェクト全体の計算を実行（v2）"""
    # 1. 判定
    地盤評価 = normalize_ground_evaluation(input.地盤評価)
    基礎種別 = input.基礎種別 or lookup_foundation_type(
        地盤評価, input.建物層数, tables
    )
    基礎形状 = foundation_shape(基礎種別)
    道路区分 = road_class(input.前面道路幅員)

    # 2. 面積計算
    建築面積 = calculate_building_area(input.有効宅地面積, input.実効建蔽率)
    層あたり共用部面積 = calculate_floor_common_area(
        input.EV,
        lookup_constant("共用部面積_層あたり", tables),
        lookup_constant("EV面積", tables),
    )
    共用部面積 = calculate_common_area(input.建物層数, 層あたり共用部面積)
    地下緩和面積 = calculate_basement_relaxation_area(
        建築面積, input.半地下有無, 層あたり共用部面積
    )
    最大施工面積 = calculate_max_construction_area(
        input.有効宅地面積,
        input.最大容積率,
        共用部面積,
        地下緩和面積,
    )
    施工面積 = calculate_construction_area(
        建築面積,
        input.建物層数,
        最大施工面積,
    )

    # 3. 単価（ベース → オプション → 最終㎡単価。丸めは最終の一度きり）
    帯域 = resolve_band(施工面積, tables.建築単価帯域)
    ベース単価 = base_unit_price(
        施工面積,
        input.住宅種別,
        道路区分,
        基礎形状,
        tables.建築単価帯域,
        tables.単価オフセット,
    )
    オプション内訳 = option_costs(
        OptionInput(
            施工床面積=施工面積,
            基礎形状=基礎形状,
            半地下有無=input.半地下有無,
            戸数=input.戸数,
            建物層数=input.建物層数,
            有効宅地面積=input.有効宅地面積,
            前面道路幅員=input.前面道路幅員,
            調査費=input.調査費,
            EV=input.EV,
            ソイル=input.ソイル,
            外周長=input.外周長,
            防音室数=input.防音室数,
            レコリード=input.レコリード,
            ペット=input.ペット,
            自火報=input.自火報,
            一層二戸=input.一層二戸,
        ),
        tables.オプション単価,
        lookup_standard_units(input.住宅種別, tables),
    )
    最終単価 = final_unit_price(ベース単価, 施工面積, オプション内訳)

    # 4. 費用計算
    建物価格 = calculate_building_cost(施工面積, 最終単価)
    杭費用 = calculate_pile_cost(建築面積, 基礎種別, tables)
    解体費用 = calculate_demolition_cost(
        input.解体面積, lookup_demolition_price(input.古家構造, tables)
    )
    工事代金 = 建物価格 + 杭費用 + 解体費用
    建設経費 = calculate_construction_expense(
        工事代金, lookup_constant("建設経費率", tables)
    )
    PJ総額 = calculate_project_total(input.土地価格, 工事代金, 建設経費)
    PJ総額_税込 = calculate_project_total_with_tax(
        input.土地価格, 工事代金, 建設経費, lookup_constant("消費税率", tables)
    )

    # 5. 収支計算
    貸床面積 = calculate_rental_floor_area(施工面積, 共用部面積)
    貸床単価, 目標利回 = lookup_rental_price(input.土地所在, tables)
    年間売上 = calculate_annual_income(貸床面積, 貸床単価)
    表面利回 = calculate_surface_yield(年間売上, PJ総額)

    return ProjectOutput(
        建築面積=建築面積,
        基礎種別=基礎種別,
        共用部面積=共用部面積,
        地下緩和面積=地下緩和面積,
        最大施工面積=最大施工面積,
        施工面積=施工面積,
        道路区分=道路区分,
        帯域=_band_label(帯域),
        ベース単価=ベース単価,
        オプション内訳=オプション内訳,
        最終単価=最終単価,
        解体費用=解体費用,
        杭費用=杭費用,
        建物価格=建物価格,
        工事代金=工事代金,
        建設経費=建設経費,
        PJ総額=PJ総額,
        PJ総額_税込=PJ総額_税込,
        貸床面積=貸床面積,
        貸床単価=貸床単価,
        年間売上=年間売上,
        表面利回=表面利回,
        目標利回=目標利回,
    )
