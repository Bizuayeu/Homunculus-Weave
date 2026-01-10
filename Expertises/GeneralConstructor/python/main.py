"""GeneralConstructor エントリーポイント

Usage:
    # Python関数として使用
    from python.main import run_calculation
    result = run_calculation(input_dict)

    # CLIから使用
    python -m python.main input.json
    python -m python.main input.json --output result.json
"""

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

from .loader import load_tables
from .calculator import calculate_project
from .schema.models import ProjectInput, ProjectOutput


def dict_to_project_input(input_dict: dict[str, Any]) -> ProjectInput:
    """辞書からProjectInputを作成"""
    return ProjectInput(
        土地価格=int(input_dict["土地価格"]),
        土地所在=input_dict["土地所在"],
        有効宅地面積=Decimal(str(input_dict["有効宅地面積"])),
        前面道路幅員=Decimal(str(input_dict["前面道路幅員"])),
        搬入経路=input_dict.get("搬入経路", "規制無"),
        道路種別=input_dict.get("道路種別", "私道"),
        接道長さ=Decimal(str(input_dict["接道長さ"])),
        古家構造=input_dict["古家構造"],
        解体面積=Decimal(str(input_dict.get("解体面積", "0"))),
        実効建蔽率=Decimal(str(input_dict["実効建蔽率"])),
        用途地域=input_dict["用途地域"],
        高度地区=input_dict.get("高度地区"),
        最大容積率=Decimal(str(input_dict["最大容積率"])),
        住宅種別=input_dict["住宅種別"],
        建物層数=int(input_dict["建物層数"]),
        半地下有無=input_dict["半地下有無"],
        EV有無=input_dict["EV有無"],
        壁率=input_dict["壁率"],
        設備率=input_dict["設備率"],
        グレード=input_dict.get("グレード", "やや高い"),
        地盤評価=input_dict["地盤評価"],
    )


def project_output_to_dict(output: ProjectOutput) -> dict[str, Any]:
    """ProjectOutputを辞書に変換（Decimalは文字列化）"""
    result = output.model_dump()
    # DecimalをFloatに変換してJSON互換にする
    for key, value in result.items():
        if isinstance(value, Decimal):
            result[key] = float(value)
    return result


def run_calculation(
    input_dict: dict[str, Any],
    data_path: Path | str | None = None,
) -> dict[str, Any]:
    """入力辞書から計算を実行し、結果を辞書で返す

    Args:
        input_dict: 入力パラメータ辞書
        data_path: テーブルデータのディレクトリパス（省略時は References/ を使用）

    Returns:
        計算結果の辞書
    """
    # テーブルデータのパスを決定
    if data_path is None:
        data_path = Path(__file__).parent.parent / "References"

    # テーブル読み込み
    tables = load_tables(data_path)

    # 入力変換
    project_input = dict_to_project_input(input_dict)

    # 計算実行
    result = calculate_project(project_input, tables)

    # 辞書に変換して返す
    return project_output_to_dict(result)


def main():
    """CLIエントリーポイント"""
    parser = argparse.ArgumentParser(
        description="GeneralConstructor - 不動産開発プロジェクト収支計算",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help="入力JSONファイルのパス",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="出力JSONファイルのパス（省略時は標準出力）",
    )
    parser.add_argument(
        "--data-path", "-d",
        type=Path,
        default=None,
        help="テーブルデータのディレクトリパス（省略時は References/）",
    )
    parser.add_argument(
        "--pretty", "-p",
        action="store_true",
        help="出力JSONを整形する",
    )

    args = parser.parse_args()

    # 入力ファイル読み込み
    if not args.input_file.exists():
        print(f"Error: Input file not found: {args.input_file}", file=sys.stderr)
        sys.exit(1)

    with open(args.input_file, "r", encoding="utf-8") as f:
        input_dict = json.load(f)

    # フィクスチャ形式（inputキーがある場合）に対応
    if "input" in input_dict:
        input_dict = input_dict["input"]

    # 計算実行
    try:
        result = run_calculation(input_dict, args.data_path)
    except Exception as e:
        print(f"Error: Calculation failed: {e}", file=sys.stderr)
        sys.exit(1)

    # 出力
    indent = 2 if args.pretty else None
    output_json = json.dumps(result, ensure_ascii=False, indent=indent)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"Result written to: {args.output}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
