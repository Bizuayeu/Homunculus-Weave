#!/usr/bin/env python3
"""
EpisodicRAG Digest Checker
===========================

ダイジェスト生成の必要性をチェックする専用スクリプト
アーリー条件（5ファイル揃った）と定期条件（期間経過）を判定して通知

使用方法：
    python check_digest.py    # 全レベルを自動チェック

このスクリプトは生成を行いません。実際の生成には generate_digest.py を使用してください。
"""

import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple, Dict, Any

class DigestChecker:
    """ダイジェスト生成チェッカー"""

    def __init__(self):
        self.base_path = Path(__file__).parent.parent
        self.loops_path = self.base_path / "Loops"
        self.digests_path = self.base_path / "Digests"

        # ダイジェスト設定
        self.digest_config = {
            "weekly": {
                "dir": "1_Weekly",
                "prefix": "W",
                "digits": 4,
                "early_threshold": 5,
                "period_days": 7,
                "source": "loops"
            },
            "monthly": {
                "dir": "2_Monthly",
                "prefix": "M",
                "digits": 3,
                "early_threshold": 5,
                "period_days": 30,
                "source": "weekly"
            },
            "quarterly": {
                "dir": "3_Quarterly",
                "prefix": "Q",
                "digits": 3,
                "early_threshold": 5,
                "period_days": 90,
                "source": "monthly"
            },
            "annually": {
                "dir": "4_Annually",
                "prefix": "A",
                "digits": 2,
                "early_threshold": 4,
                "period_days": 365,
                "source": "quarterly"
            }
        }

        # タイマー管理
        self.last_digest_file = self.digests_path / "last_digest_times.json"
        self.last_digest_times = self.load_last_digest_times()

    def load_last_digest_times(self) -> Dict[str, str]:
        """最終ダイジェスト生成時刻を読み込む"""
        if self.last_digest_file.exists():
            with open(self.last_digest_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def check_digest_trigger(self, level: str) -> Tuple[List[Path], str]:
        """ダイジェスト生成のトリガーをチェック"""
        config = self.digest_config[level]

        # ソースディレクトリを決定
        if config["source"] == "loops":
            source_dir = self.loops_path
            pattern = "Loop*.txt"
        else:
            source_config = self.digest_config[config["source"]]
            source_dir = self.digests_path / source_config["dir"]
            pattern = f"{source_config['prefix']}*.json"

        if not source_dir.exists():
            return [], "none"

        # 最終ダイジェスト時刻
        last_time_str = self.last_digest_times.get(level)
        if last_time_str:
            last_time = datetime.fromisoformat(last_time_str)
        else:
            last_time = datetime.min

        # 対象ファイルを収集
        if last_time == datetime.min:
            files = sorted(list(source_dir.glob(pattern)))
        else:
            files = sorted([f for f in source_dir.glob(pattern)
                          if f.stat().st_mtime > last_time.timestamp()])

        # トリガー判定
        if len(files) >= config["early_threshold"]:
            return files[:config["early_threshold"]], "early"
        elif last_time != datetime.min:
            days_passed = (datetime.now() - last_time).days
            if days_passed >= config["period_days"] and files:
                return files, "periodic"

        return [], "none"

    def run(self) -> int:
        """チェックを実行"""
        print(f"""
========================================================
       EpisodicRAG Digest Checker
========================================================
 Checking for early/periodic digest opportunities...
========================================================
        """)

        found_triggers = []

        for level in ["weekly", "monthly", "quarterly", "annually"]:
            files, reason = self.check_digest_trigger(level)

            if files:
                found_triggers.append((level, files, reason))
                print(f"\n[TRIGGER] {level.capitalize()} digest needed: {reason}")
                print(f"   Target files: {len(files)} items")

                # 生成コマンドの提案
                config = self.digest_config[level]
                if config["source"] == "loops":
                    # Loop番号を抽出
                    first_file = files[0].stem.split('_')[0]  # "Loop0001"
                    first_num = int(first_file[4:])
                    print(f"   Run: python generate_digest.py {level} {first_num} {len(files)}")
                else:
                    # ダイジェスト番号を抽出
                    first_file = files[0].stem.split('_')[0]  # "W0001"
                    first_num = int(first_file[1:])
                    print(f"   Run: python generate_digest.py {level} {first_num} {len(files)}")

        if not found_triggers:
            print("\n[OK] No digests needed at this time")
            print("\nNext check timing:")
            for level in ["weekly", "monthly", "quarterly", "annually"]:
                config = self.digest_config[level]
                last_time_str = self.last_digest_times.get(level)
                if last_time_str:
                    last_time = datetime.fromisoformat(last_time_str)
                    next_time = last_time + timedelta(days=config["period_days"])
                    days_left = (next_time - datetime.now()).days
                    if days_left > 0:
                        print(f"  {level:10s}: {days_left} days remaining")
                    else:
                        print(f"  {level:10s}: Ready for periodic generation")
                else:
                    print(f"  {level:10s}: No previous digest")

        return len(found_triggers)

def main():
    """メイン実行関数"""
    checker = DigestChecker()
    triggers_found = checker.run()

    if triggers_found > 0:
        print(f"\n[WARNING] Found {triggers_found} digest(s) ready for generation")
        print("Use generate_digest.py with the suggested commands above")
        return 1  # Exit with non-zero to indicate action needed

    return 0  # Exit with zero to indicate all clear

if __name__ == "__main__":
    exit(main())