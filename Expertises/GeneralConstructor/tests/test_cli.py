"""CLI（Interface 層）テスト: python -m python.main の入出力と終了コード

サブプロセスで実際に起動する。関数 API（run_calculation）は test_integration.py が
見ているので、ここが見るのは CLI 固有の責務——標準出力の JSON・終了コード・
標準エラーの一行整形（スタックトレースを出さないこと）。
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from python.main import dict_to_project_input

GC_ROOT = Path(__file__).parent.parent
FIXTURE = GC_ROOT / "tests" / "fixtures" / "case_001_itabashi.json"

# v2 で退役した入力キー。ProjectInput は extra="forbid" なので、指定しても効かない値が
# 黙って捨てられることはない（IMPLEMENTATION_PLAN Stage 4 / case_001 の input_notes）。
退役キー = [
    "搬入経路",
    "道路種別",
    "接道長さ",
    "壁率",
    "設備率",
    "グレード",
    "EV有無",
]


def run_cli(*args: str) -> subprocess.CompletedProcess:
    """CLI をサブプロセスで起動する

    PYTHONIOENCODING: Windows の既定 cp932 では日本語のフィールド名を stdout へ書けない。
    encoding: 受け側も UTF-8 で読まないと、CLI が返す日本語のエラー文で decode に失敗する。
    """
    return subprocess.run(
        [sys.executable, "-m", "python.main", *args],
        cwd=GC_ROOT,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        encoding="utf-8",
        check=False,  # 終了コードは呼び出し側が assert する
    )


class TestCliRoundtrip:
    def test_cli_v2_roundtrip(self):
        """fixture 入力 → 標準出力の JSON が v2 の出力を持つ"""
        proc = run_cli(str(FIXTURE), "--pretty")

        assert proc.returncode == 0, proc.stderr
        result = json.loads(proc.stdout)
        assert result["PJ総額_税込"] == 27741
        assert result["オプション内訳"]["地盤調査"] == 55


class TestCliDomainError:
    def test_cli_domain_error_exit_code(self, tmp_path):
        """帯域下限（200㎡）を割る入力は、一行のエラーと非ゼロ終了で落ちる"""
        入力 = json.loads(FIXTURE.read_text(encoding="utf-8"))["input"]
        # 有効宅地 70.00 → 建築面積 49.00 → 施工床 196.00㎡（帯域下限 200 未満）
        入力["有効宅地面積"] = "70.00"
        小規模 = tmp_path / "under_band.json"
        小規模.write_text(json.dumps(入力, ensure_ascii=False), encoding="utf-8")

        proc = run_cli(str(小規模))

        assert proc.returncode == 1
        assert "PricingDomainError" in proc.stderr
        assert "Traceback" not in proc.stderr
        assert len(proc.stderr.strip().splitlines()) == 1


class TestDictAdapter:
    @pytest.mark.parametrize("退役キー", 退役キー)
    def test_dict_adapter_rejects_retired_keys(self, 退役キー):
        """v1 の退役キーを含む dict は明示エラー（黙って無視しない）"""
        入力 = dict(
            json.loads(FIXTURE.read_text(encoding="utf-8"))["input"],
            **{退役キー: "標準的"},
        )

        with pytest.raises(ValidationError) as e:
            dict_to_project_input(入力)
        assert 退役キー in str(e.value)
