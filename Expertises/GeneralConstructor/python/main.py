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
    """辞書から ProjectInput を作成

    v2 でフィールドの写しをやめた。ProjectInput が extra="forbid" と Literal で
    検証を全て持つので、ここで項目を並べ直すと二重管理になり、退役キーの取りこぼしが起きる。
    """
    return ProjectInput.model_validate(input_dict)


def project_output_to_dict(output: ProjectOutput) -> dict[str, Any]:
    """ProjectOutputを辞書に変換（Decimalは文字列化）"""
    result = output.model_dump()

    def to_json_value(value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, dict):  # オプション内訳（名称 → 万円）
            return {k: to_json_value(v) for k, v in value.items()}
        return value

    return {key: to_json_value(value) for key, value in result.items()}


def run_calculation(
    input_dict: dict[str, Any],
    data_path: Path | str | None = None,
) -> dict[str, Any]:
    """入力辞書から計算を実行し、結果を辞書で返す

    Args:
        input_dict: 入力パラメータ辞書
        data_path: テーブルデータのディレクトリパス（省略時は python/data/ を使用）

    Returns:
        計算結果の辞書
    """
    # テーブルデータのパスを決定
    if data_path is None:
        data_path = Path(__file__).parent / "data"

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
        help="テーブルデータのディレクトリパス（省略時は python/data/）",
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
