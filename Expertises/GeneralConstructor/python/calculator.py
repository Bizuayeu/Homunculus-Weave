"""計算ロジック（ビジネスルール一覧に基づく）"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from .loader import Tables
from .schema.models import ProjectInput, ProjectOutput


# === 面積計算 ===


def calculate_building_area(
    有効宅地面積: Decimal,
    実効建蔽率: Decimal,
) -> Decimal:
    """建築面積 = 有効宅地面積 × 実効建蔽率（上限70%）

    ビジネスルール: 実効建蔽率≦70%
    """
    # 実効建蔽率の上限を70%に制限
    effective_rate = min(実効建蔽率, Decimal("70"))
    return (有効宅地面積 * effective_rate / Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def calculate_common_area(建物層数: int, EV有無: str) -> Decimal:
    """共用部面積 = 建物層数 × (8 + EV面積)

    EV面積は2㎡と仮定
    """
    ev_area = Decimal("2") if EV有無 == "EV有" else Decimal("0")
    return Decimal(建物層数) * (Decimal("8") + ev_area)


def calculate_basement_relaxation_area(
    建築面積: Decimal,
    半地下有無: str,
) -> Decimal:
    """地下緩和面積 = 建築面積 - 8（半地下無の場合は0）"""
    if 半地下有無 == "半地下無":
        return Decimal("0")
    return 建築面積 - Decimal("8")


def calculate_max_construction_area(
    有効宅地面積: Decimal,
    最大容積率: Decimal,
    共用部面積: Decimal,
    地下緩和面積: Decimal,
) -> Decimal:
    """最大施工面積 = 有効宅地面積 × 最大容積率 + 共用部面積 + 地下緩和面積"""
    return (
        有効宅地面積 * 最大容積率 / Decimal("100") + 共用部面積 + 地下緩和面積
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_construction_area(
    建築面積: Decimal,
    建物層数: int,
    最大施工面積: Decimal,
) -> Decimal:
    """施工面積 = min(建築面積 × 建物層数, 最大施工面積)"""
    actual = 建築面積 * Decimal(建物層数)
    return min(actual, 最大施工面積)


# === コスト計算 ===


def calculate_foundation_cost(
    建築面積: Decimal,
    基礎単価: Decimal,
    施工条件係数: Decimal,
) -> int:
    """基礎費用 = 建築面積 × 基礎単価 × (1 + 施工条件係数)

    単位: 万円
    """
    cost = 建築面積 * 基礎単価 * (Decimal("1") + 施工条件係数)
    return int(cost.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def calculate_retaining_wall_cost(
    建築面積: Decimal,
    山留単価: Decimal,
    施工条件係数: Decimal,
) -> int:
    """山留費用 = 建築面積 × 山留単価 × (1 + 施工条件係数)

    単位: 万円
    """
    cost = 建築面積 * 山留単価 * (Decimal("1") + 施工条件係数)
    return int(cost.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def calculate_ground_cost(基礎費用: int, 山留費用: int) -> int:
    """地盤費用 = 基礎費用 + 山留費用"""
    return 基礎費用 + 山留費用


def calculate_demolition_cost(
    解体面積: Decimal,
    解体単価: Decimal,
    施工条件係数: Decimal,
) -> int:
    """解体費用 = 解体面積 × 解体単価 × (1 + 施工条件係数)

    単位: 万円
    """
    if 解体面積 == Decimal("0"):
        return 0
    cost = 解体面積 * 解体単価 * (Decimal("1") + 施工条件係数)
    return int(cost.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def calculate_adjusted_building_price(
    標準建築単価: int,
    施工条件係数: Decimal,
    建物形状係数: Decimal,
) -> Decimal:
    """補正建築単価 = 標準建築単価 × (1 + 施工条件係数 + 建物形状係数)"""
    return Decimal(標準建築単価) * (
        Decimal("1") + 施工条件係数 + 建物形状係数
    )


def calculate_building_cost(
    施工面積: Decimal,
    補正建築単価: Decimal,
) -> int:
    """建物価格 = 施工面積 × 補正建築単価

    単位: 万円
    """
    cost = 施工面積 * 補正建築単価
    return int(cost.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def calculate_construction_expense(工事代金: int) -> int:
    """建設経費 = 工事代金 × 5%"""
    return int(
        (Decimal(工事代金) * Decimal("0.05")).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )


def calculate_project_total(
    土地価格: int,
    工事代金: int,
    建設経費: int,
) -> int:
    """PJ総額 = 土地価格 + 工事代金 + 建設経費

    注: SKILL.mdの定義に従う（ビジネスルール一覧では建設経費が漏れている）
    """
    return 土地価格 + 工事代金 + 建設経費


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
    return int((income_yen / Decimal("10000")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def calculate_surface_yield(
    年間売上: int,
    PJ総額: int,
) -> Decimal:
    """表面利回 = 年間売上 / PJ総額 × 100"""
    return (Decimal(年間売上) / Decimal(PJ総額) * Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


# === テーブル参照 ===


def lookup_construction_coefficient(
    前面道路幅員: Decimal,
    搬入経路: str,
    道路種別: str,
    接道長さ: Decimal,
    tables: Tables,
) -> Decimal:
    """施工条件テーブルから施工条件係数を取得"""
    for entry in tables.施工条件:
        # 道路幅員の範囲チェック
        if not (entry.道路幅員.min <= float(前面道路幅員) < entry.道路幅員.max):
            continue
        # 搬入経路チェック
        if entry.搬入経路 != 搬入経路:
            continue
        # 道路種別チェック
        if entry.道路種別 != 道路種別:
            continue
        # 接道長さの範囲チェック
        if not (entry.接道長さ.min <= float(接道長さ) < entry.接道長さ.max):
            continue
        return Decimal(str(entry.施工条件係数))

    # デフォルト値
    return Decimal("0.05")


def lookup_building_shape_coefficient(
    壁率: str,
    設備率: str,
    グレード: str,
    tables: Tables,
) -> Decimal:
    """建物形状テーブルから建物形状係数を取得"""
    for entry in tables.建物形状:
        if entry.壁率 == 壁率 and entry.設備率 == 設備率 and entry.グレード == グレード:
            return Decimal(str(entry.建物形状係数))

    # デフォルト値
    return Decimal("0.04")


def lookup_foundation_type(
    地盤評価: str,
    建物層数: int,
    tables: Tables,
) -> str:
    """基礎種別テーブルから基礎種別を取得"""
    層数_str = f"{建物層数}層" if 建物層数 <= 6 else "高層"

    for entry in tables.基礎種別:
        if entry.地盤評価 == 地盤評価 and entry.建物層数 == 層数_str:
            return entry.基礎種別

    # デフォルト値
    return "礎ベタ基礎"


def lookup_foundation_price(
    基礎種別: str,
    tables: Tables,
) -> Decimal:
    """基礎単価テーブルから基礎単価を取得"""
    for entry in tables.基礎単価:
        if entry.基礎種別 == 基礎種別:
            return Decimal(str(entry.基礎単価))

    # デフォルト値
    return Decimal("6")


def lookup_retaining_method(
    地盤評価: str,
    tables: Tables,
) -> str:
    """山留工法テーブルから山留工法を取得"""
    for entry in tables.山留工法:
        if entry.地盤評価 == 地盤評価:
            return entry.山留工法

    # デフォルト値
    return "親杭横矢板"


def lookup_retaining_wall_price(
    山留工法: str,
    基礎種別: str,
    半地下有無: str,
    tables: Tables,
) -> Decimal:
    """山留単価テーブルから山留単価を取得"""
    for entry in tables.山留単価:
        if (
            entry.山留工法 == 山留工法
            and entry.基礎種別 == 基礎種別
            and entry.半地下有無 == 半地下有無
        ):
            return Decimal(str(entry.山留単価))

    # デフォルト値
    return Decimal("1")


def lookup_building_price(
    半地下有無: str,
    施工面積: Decimal,
    tables: Tables,
) -> int:
    """建築単価テーブルから標準建築単価を取得"""
    area = float(施工面積)
    for entry in tables.建築単価.建築単価テーブル:
        if entry.半地下有無 != 半地下有無:
            continue
        if entry.施工面積.min <= area < entry.施工面積.max:
            return entry.建築単価

    # デフォルト値
    return 50


def lookup_demolition_price(
    古家構造: str,
    tables: Tables,
) -> Decimal:
    """解体単価テーブルから解体単価を取得"""
    for entry in tables.解体単価:
        if entry.古家構造 == 古家構造:
            return Decimal(str(entry.解体単価))

    # デフォルト値（無し = 0）
    return Decimal("0")


def lookup_rental_price(
    土地所在: str,
    tables: Tables,
) -> tuple[int, Decimal]:
    """貸床単価テーブルから貸床単価と目標利回を取得"""
    for entry in tables.貸床単価:
        if entry.土地所在 == 土地所在:
            return entry.貸床単価, Decimal(str(entry.目標利回))

    # デフォルト値
    return 4400, Decimal("6.0")


# === メイン計算関数 ===


def calculate_project(
    input: ProjectInput,
    tables: Tables,
) -> ProjectOutput:
    """プロジェクト全体の計算を実行

    ビジネスルール一覧の計算式を順番に実行
    """
    # 1. 係数取得
    施工条件係数 = lookup_construction_coefficient(
        input.前面道路幅員,
        input.搬入経路,
        input.道路種別,
        input.接道長さ,
        tables,
    )
    建物形状係数 = lookup_building_shape_coefficient(
        input.壁率,
        input.設備率,
        input.グレード,
        tables,
    )

    # 2. 面積計算
    建築面積 = calculate_building_area(input.有効宅地面積, input.実効建蔽率)
    共用部面積 = calculate_common_area(input.建物層数, input.EV有無)
    地下緩和面積 = calculate_basement_relaxation_area(建築面積, input.半地下有無)
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

    # 3. 単価取得
    基礎種別 = lookup_foundation_type(input.地盤評価, input.建物層数, tables)
    基礎単価 = lookup_foundation_price(基礎種別, tables)
    山留工法 = lookup_retaining_method(input.地盤評価, tables)
    山留単価 = lookup_retaining_wall_price(
        山留工法, 基礎種別, input.半地下有無, tables
    )
    標準建築単価 = lookup_building_price(input.半地下有無, 施工面積, tables)
    解体単価 = lookup_demolition_price(input.古家構造, tables)

    # 4. 費用計算
    解体費用 = calculate_demolition_cost(input.解体面積, 解体単価, 施工条件係数)
    基礎費用 = calculate_foundation_cost(建築面積, 基礎単価, 施工条件係数)
    山留費用 = calculate_retaining_wall_cost(建築面積, 山留単価, 施工条件係数)
    地盤費用 = calculate_ground_cost(基礎費用, 山留費用)
    補正建築単価 = calculate_adjusted_building_price(
        標準建築単価, 施工条件係数, 建物形状係数
    )
    建物価格 = calculate_building_cost(施工面積, 補正建築単価)

    # 工事代金 = 建築費 + 基礎費 + 山留費 + 解体費
    工事代金 = 建物価格 + 基礎費用 + 山留費用 + 解体費用
    建設経費 = calculate_construction_expense(工事代金)
    PJ総額 = calculate_project_total(input.土地価格, 工事代金, 建設経費)

    # 5. 収支計算
    貸床面積 = calculate_rental_floor_area(施工面積, 共用部面積)
    貸床単価, 目標利回 = lookup_rental_price(input.土地所在, tables)
    年間売上 = calculate_annual_income(貸床面積, 貸床単価)
    表面利回 = calculate_surface_yield(年間売上, PJ総額)

    return ProjectOutput(
        施工条件係数=施工条件係数,
        建物形状係数=建物形状係数,
        建築面積=建築面積,
        基礎種別=基礎種別,
        基礎単価=int(基礎単価),
        山留工法=山留工法,
        山留単価=int(山留単価),
        共用部面積=共用部面積,
        地下緩和面積=地下緩和面積,
        最大施工面積=最大施工面積,
        施工面積=施工面積,
        標準建築単価=標準建築単価,
        補正建築単価=補正建築単価,
        解体費用=解体費用,
        基礎費用=基礎費用,
        山留費用=山留費用,
        地盤費用=地盤費用,
        建物価格=建物価格,
        PJ総額=PJ総額,
        貸床面積=貸床面積,
        貸床単価=貸床単価,
        年間売上=年間売上,
        表面利回=表面利回,
        目標利回=目標利回,
    )
