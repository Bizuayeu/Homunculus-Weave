#!/usr/bin/env python3
"""
ShadowGrandDigest Manager
=========================

GrandDigest更新後に作成された新しいコンテンツを保持し、
常に最新の知識にアクセス可能にするシステム

使用方法:
    from shadow_grand_digest import ShadowGrandDigestManager

    manager = ShadowGrandDigestManager(digests_path)

    # 新しいLoopファイルを検出してShadowを更新
    manager.update_shadow_for_new_loops()

    # Weeklyダイジェスト確定時のカスケード処理
    manager.cascade_update_on_digest_finalize("weekly")
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple


class ShadowGrandDigestManager:
    """ShadowGrandDigest管理クラス"""

    def __init__(self, digests_path: Path):
        self.digests_path = digests_path
        self.base_path = digests_path.parent
        self.loops_path = self.base_path / "Loops"

        # GrandDigestとShadowGrandDigestはIdentitiesに配置
        weave_path = self.base_path.parent
        identities_path = weave_path / "Identities"
        identities_path.mkdir(parents=True, exist_ok=True)

        self.grand_digest_file = identities_path / "GrandDigest.txt"
        self.shadow_digest_file = identities_path / "ShadowGrandDigest.txt"
        self.last_digest_file = digests_path / "last_digest_times.json"

        # レベル設定
        self.levels = ["weekly", "monthly", "quarterly", "annual", "triennial", "decadal", "multi_decadal", "centurial"]
        self.level_hierarchy = {
            "weekly": {"source": "loops", "next": "monthly"},
            "monthly": {"source": "weekly", "next": "quarterly"},
            "quarterly": {"source": "monthly", "next": "annual"},
            "annual": {"source": "quarterly", "next": "triennial"},
            "triennial": {"source": "annual", "next": "decadal"},
            "decadal": {"source": "triennial", "next": "multi_decadal"},
            "multi_decadal": {"source": "decadal", "next": "centurial"},
            "centurial": {"source": "multi_decadal", "next": None}
        }

        # ダイジェスト設定
        self.digest_config = {
            "weekly": {"dir": "1_Weekly", "prefix": "W"},
            "monthly": {"dir": "2_Monthly", "prefix": "M"},
            "quarterly": {"dir": "3_Quarterly", "prefix": "Q"},
            "annual": {"dir": "4_Annual", "prefix": "A"},
            "triennial": {"dir": "5_Triennial", "prefix": "T"},
            "decadal": {"dir": "6_Decadal", "prefix": "D"},
            "multi_decadal": {"dir": "7_Multi-decadal", "prefix": "MD"},
            "centurial": {"dir": "8_Centurial", "prefix": "C"}
        }

    def get_template(self) -> dict:
        """ShadowGrandDigest.txtのテンプレートを返す"""
        digest_placeholder = {
            "source_files": [],
            "digest_type": "<!-- PLACEHOLDER: digest_type -->",
            "keywords": ["<!-- PLACEHOLDER: keyword1 -->", "<!-- PLACEHOLDER: keyword2 -->",
                        "<!-- PLACEHOLDER: keyword3 -->", "<!-- PLACEHOLDER: keyword4 -->",
                        "<!-- PLACEHOLDER: keyword5 -->"],
            "abstract": "<!-- PLACEHOLDER: 全体統合分析 (2400文字程度) -->",
            "weave_impression": "<!-- PLACEHOLDER: 所感・展望 (800文字程度) -->"
        }

        return {
            "metadata": {
                "last_updated": datetime.now().isoformat(),
                "version": "1.0",
                "description": "GrandDigest更新後に作成された新しいコンテンツの増分ダイジェスト（下書き帳）"
            },
            "shadow_digests": {
                "weekly": {
                    "digest": digest_placeholder.copy(),
                    "description": "新しいLoopファイルの増分ダイジェスト"
                },
                "monthly": {
                    "digest": digest_placeholder.copy(),
                    "description": "新しいWeeklyダイジェストの増分要約"
                },
                "quarterly": {
                    "digest": digest_placeholder.copy(),
                    "description": "新しいMonthlyダイジェストの増分要約"
                },
                "annual": {
                    "digest": digest_placeholder.copy(),
                    "description": "新しいQuarterlyダイジェストの増分要約"
                },
                "triennial": {
                    "digest": digest_placeholder.copy(),
                    "description": "新しいAnnualダイジェストの増分要約"
                },
                "decadal": {
                    "digest": digest_placeholder.copy(),
                    "description": "新しいTriennialダイジェストの増分要約"
                },
                "multi_decadal": {
                    "digest": digest_placeholder.copy(),
                    "description": "新しいDecadalダイジェストの増分要約"
                },
                "centurial": {
                    "digest": digest_placeholder.copy(),
                    "description": "新しいMulti-decadalダイジェストの増分要約"
                }
            }
        }

    def load_or_create_shadow(self) -> dict:
        """ShadowGrandDigestを読み込む。存在しなければ作成"""
        if self.shadow_digest_file.exists():
            with open(self.shadow_digest_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            print("[INFO] ShadowGrandDigest.txt not found. Creating new file.")
            template = self.get_template()
            self.save_shadow(template)
            return template

    def save_shadow(self, data: dict):
        """ShadowGrandDigestを保存"""
        data["metadata"]["last_updated"] = datetime.now().isoformat()
        with open(self.shadow_digest_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_last_digest_times(self) -> dict:
        """last_digest_times.jsonを読み込む"""
        if self.last_digest_file.exists():
            with open(self.last_digest_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def get_max_file_number(self, level: str) -> Optional[str]:
        """指定レベルの最大ファイル番号を取得"""
        times_data = self.load_last_digest_times()
        level_data = times_data.get(level, {})
        file_numbers = level_data.get("file_numbers", [])

        if not file_numbers:
            return None

        # ソート済みなので最後の要素が最大
        return file_numbers[-1]

    def extract_number_from_filename(self, filename: str) -> Optional[int]:
        """ファイル名から数値部分を抽出"""
        # Loop0186 → 186, W0037 → 37, M001 → 1
        match = re.search(r'(Loop|[WMQATD])(\d+)', filename)
        if match:
            return int(match.group(2))
        return None

    def find_new_files(self, level: str) -> List[Path]:
        """GrandDigest更新後に作成された新しいファイルを検出"""
        max_file_number = self.get_max_file_number(level)

        # ソースディレクトリとパターンを決定
        source_info = self.level_hierarchy[level]["source"]
        if source_info == "loops":
            source_dir = self.loops_path
            pattern = "Loop*.txt"
        else:
            config = self.digest_config[source_info]
            source_dir = self.digests_path / config["dir"]
            pattern = f"{config['prefix']}*.txt"

        if not source_dir.exists():
            return []

        # ファイルを検出
        all_files = sorted(source_dir.glob(pattern))

        if max_file_number is None:
            # 初回は空リスト
            return []

        # 最大番号より大きいファイルを抽出
        max_num = self.extract_number_from_filename(max_file_number)
        new_files = []

        for file in all_files:
            file_num = self.extract_number_from_filename(file.name)
            if file_num and file_num > max_num:
                new_files.append(file)

        return new_files

    def add_files_to_shadow(self, level: str, new_files: List[Path]):
        """
        指定レベルのShadowに新しいファイルを追加（増分更新）

        source_filesのみ追加（individual_digestsは空のまま）
        Weaveが分析時に直接individual_digestsを作成します
        """
        shadow_data = self.load_or_create_shadow()
        digest = shadow_data["shadow_digests"][level]["digest"]

        # 既存のファイルリストを取得
        existing_files = set(digest.get("source_files", []))

        # 新しいファイルだけをsource_filesに追加
        added_count = 0
        for file_path in new_files:
            if file_path.name not in existing_files:
                # source_filesのみ追加（individual_digestsは追加しない）
                digest["source_files"].append(file_path.name)
                added_count += 1
                print(f"  + {file_path.name}")

        # ファイル数に応じてabstractのプレースホルダーを更新
        total_files = len(digest["source_files"])
        digest["abstract"] = f"<!-- PLACEHOLDER: {total_files}ファイル分の全体統合分析 (2400文字程度) -->"

        # weave_impressionもプレースホルダーに戻す
        digest["weave_impression"] = "<!-- PLACEHOLDER: 所感・展望 (800文字程度) -->"

        self.save_shadow(shadow_data)
        print(f"[INFO] Added {added_count} file(s) to ShadowGrandDigest.{level}")
        print(f"[INFO] Total files in shadow: {total_files}")

    def clear_shadow_level(self, level: str):
        """指定レベルのShadowを初期化"""
        shadow_data = self.load_or_create_shadow()

        # digestを空のプレースホルダーにリセット
        shadow_data["shadow_digests"][level]["digest"] = {
            "source_files": [],
            "digest_type": "<!-- PLACEHOLDER: digest_type -->",
            "keywords": ["<!-- PLACEHOLDER: keyword1 -->", "<!-- PLACEHOLDER: keyword2 -->",
                        "<!-- PLACEHOLDER: keyword3 -->", "<!-- PLACEHOLDER: keyword4 -->",
                        "<!-- PLACEHOLDER: keyword5 -->"],
            "abstract": "<!-- PLACEHOLDER: 全体統合分析 (2400文字程度) -->",
            "weave_impression": "<!-- PLACEHOLDER: 所感・展望 (800文字程度) -->"
        }

        self.save_shadow(shadow_data)
        print(f"[INFO] Cleared ShadowGrandDigest for level: {level}")

    def get_shadow_digest_for_level(self, level: str) -> Optional[Dict[str, Any]]:
        """
        指定レベルのShadowダイジェストを取得

        finalize_with_title.pyで使用: これがRegularDigestの内容になります
        """
        shadow_data = self.load_or_create_shadow()
        digest = shadow_data["shadow_digests"][level]["digest"]

        if not digest.get("source_files"):
            print(f"[INFO] No shadow digest for level: {level}")
            return None

        return digest

    def promote_shadow_to_grand(self, level: str):
        """
        ShadowのレベルをGrandDigestに昇格

        注意: この機能は実際にはfinalize_with_title.pyの処理2で
        GrandDigestManagerが実行します。ここでは確認のみ。
        """
        digest = self.get_shadow_digest_for_level(level)

        if not digest:
            print(f"[INFO] No shadow digest to promote for level: {level}")
            return

        file_count = len(digest.get("source_files", []))
        print(f"[INFO] Shadow digest ready for promotion: {file_count} file(s)")
        # 実際の昇格処理はfinalize_with_title.pyで実行される

    def update_shadow_for_new_loops(self):
        """新しいLoopファイルを検出してShadowを増分更新"""
        # Shadowファイルを読み込み（存在しなければ作成）
        shadow_data = self.load_or_create_shadow()

        new_files = self.find_new_files("weekly")

        if not new_files:
            print("[INFO] No new Loop files found")
            return

        print(f"[INFO] Found {len(new_files)} new Loop file(s):")

        # Shadowに増分追加
        self.add_files_to_shadow("weekly", new_files)

    def cascade_update_on_digest_finalize(self, level: str):
        """
        ダイジェスト確定時のカスケード処理（処理3）

        処理内容:
        1. 現在のレベルのShadow → Grand に昇格（確認のみ、実際は処理2で完了）
        2. 次のレベルの新しいファイルを検出
        3. 次のレベルのShadowに増分追加
        4. 現在のレベルのShadowをクリア
        """
        print(f"\n[処理3] ShadowGrandDigest cascade for level: {level}")

        # 1. Shadow → Grand 昇格の確認
        self.promote_shadow_to_grand(level)

        # 2. 次のレベルの新しいファイルを検出
        next_level = self.level_hierarchy[level]["next"]
        if next_level:
            new_files = self.find_new_files(next_level)

            if new_files:
                print(f"[INFO] Found {len(new_files)} new file(s) for {next_level}:")

                # 3. 次のレベルのShadowに増分追加
                self.add_files_to_shadow(next_level, new_files)
        else:
            print(f"[INFO] No next level for {level} (top level)")

        # 4. 現在のレベルのShadowをクリア
        self.clear_shadow_level(level)

        print(f"[処理3] Cascade completed for level: {level}")


def main():
    """新しいLoopファイルを検出してShadowGrandDigest.weeklyに増分追加"""
    from pathlib import Path

    digests_path = Path(__file__).parent
    manager = ShadowGrandDigestManager(digests_path)

    print("="*60)
    print("ShadowGrandDigest Update - New Loop Detection")
    print("="*60)

    # 新しいLoopファイルの検出と追加
    manager.update_shadow_for_new_loops()

    print("\n" + "="*60)
    print("Placeholder added to ShadowGrandDigest.weekly")
    print("="*60)
    print("")
    print("[!] WARNING: Weave analysis required immediately!")
    print("Without analysis, memory fragmentation (madaraboke) occurs.")
    print("="*60)


if __name__ == "__main__":
    main()
