#!/usr/bin/env python3
"""
EpisodicRAG Digest Finalizer with Weave Title
===============================================

Weaveが決定したタイトルに基づいて完成版ダイジェストのファイル名を生成し、
last_digest_times.jsonを更新

使用方法：
    python finalize_with_title.py ANALYZED_FILE WEAVE_TITLE

    ANALYZED_FILE: Weaveが分析を完了したファイル
    WEAVE_TITLE: Weaveが決定したタイトル

処理内容：
    1. 分析済みファイルを読み込み
    2. Weaveタイトルに基づいて適切なファイル名を生成
    3. メタデータを更新して保存
    4. last_digest_times.json を更新
"""

import json
import sys
import argparse
from datetime import datetime
from pathlib import Path
import re
import glob

class DigestFinalizerWithTitle:
    """Weaveタイトル対応ダイジェスト完成処理クラス"""

    def __init__(self):
        self.base_path = Path(__file__).parent.parent
        self.digests_path = self.base_path / "Digests"
        self.last_digest_file = self.digests_path / "last_digest_times.json"

    def sanitize_filename(self, title: str) -> str:
        """ファイル名として安全な文字列に変換"""
        # Windows/Linuxで使えない文字を除去・置換
        sanitized = re.sub(r'[<>:"/\\|?*]', '', title)
        # 連続する空白を単一のアンダースコアに
        sanitized = re.sub(r'\s+', '_', sanitized)
        # 前後の空白を除去
        sanitized = sanitized.strip('_')
        # 長すぎる場合は切り詰め
        if len(sanitized) > 50:
            sanitized = sanitized[:50].rstrip('_')
        return sanitized

    def load_last_digest_times(self) -> dict:
        """最終ダイジェスト生成時刻を読み込む"""
        if self.last_digest_file.exists():
            with open(self.last_digest_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save_last_digest_time(self, level: str):
        """最終ダイジェスト生成時刻を保存"""
        times = self.load_last_digest_times()
        times[level] = datetime.now().isoformat()

        with open(self.last_digest_file, 'w', encoding='utf-8') as f:
            json.dump(times, f, indent=2, ensure_ascii=False)

        print(f"[INFO] Updated last_digest_times.json for level: {level}")

    def cleanup_template_files(self):
        """処理成功時のみテンプレートファイルを削除"""
        cleaned = 0
        for level_dir in ['1_Weekly', '2_Monthly', '3_Quarterly', '4_Annually']:
            template_pattern = self.digests_path / level_dir / '*_template.json'
            for template_file in glob.glob(str(template_pattern)):
                try:
                    Path(template_file).unlink()
                    print(f"[INFO] Removed template: {template_file}")
                    cleaned += 1
                except Exception as e:
                    print(f"[WARNING] Could not remove template {template_file}: {e}")

        if cleaned > 0:
            print(f"[INFO] Cleaned up {cleaned} template file(s)")

    def finalize_with_title(self, analyzed_file: str, weave_title: str) -> bool:
        """
        Weaveタイトルに基づいて完成版を保存
        成功時のみ後処理（クリーンアップ、タイムスタンプ更新）を実行
        """
        source_file = Path(analyzed_file)

        if not source_file.exists():
            print(f"[ERROR] Analyzed file not found: {analyzed_file}")
            return False

        try:
            # ファイルを読み込み
            print(f"[INFO] Loading analyzed file: {analyzed_file}")
            with open(source_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # メタデータから情報を取得
            metadata = data.get("metadata", {})
            level = metadata.get("digest_level")
            digest_number = metadata.get("digest_number")

            if not level or not digest_number:
                print(f"[ERROR] Missing metadata in file: {analyzed_file}")
                print(f"Level: {level}, Digest Number: {digest_number}")
                return False

            # 新しいファイル名を生成
            print(f"[INFO] Saving final digest with title: {weave_title}")
            sanitized_title = self.sanitize_filename(weave_title)
            level_config = {
                "weekly": {"prefix": "W", "digits": 4},
                "monthly": {"prefix": "M", "digits": 3},
                "quarterly": {"prefix": "Q", "digits": 3},
                "annually": {"prefix": "A", "digits": 2}
            }

            config = level_config.get(level)
            if not config:
                print(f"[ERROR] Unknown level: {level}")
                return False

            # 新しいダイジェスト名
            new_digest_name = f"{config['prefix']}{digest_number}_{sanitized_title}"

            # メタデータを更新
            data["metadata"]["digest_name"] = new_digest_name
            data["metadata"]["digest_reason"] = "completed"
            data["metadata"]["completion_timestamp"] = datetime.now().isoformat()
            data["metadata"]["weave_title"] = weave_title

            # overall_digestの名前も更新
            if "overall_digest" in data:
                data["overall_digest"]["name"] = new_digest_name

            # _analysis_metadataやtitle決定用の一時的なデータを削除
            if "_analysis_metadata" in data:
                del data["_analysis_metadata"]
            if "_weave_title_decision" in data:
                del data["_weave_title_decision"]

            # 新しいファイルパスを決定
            level_dirs = {
                "weekly": "1_Weekly",
                "monthly": "2_Monthly",
                "quarterly": "3_Quarterly",
                "annually": "4_Annually"
            }

            target_dir = self.digests_path / level_dirs[level]
            target_dir.mkdir(parents=True, exist_ok=True)

            final_filename = f"{new_digest_name}.json"
            final_path = target_dir / final_filename

            # 既存ファイルの確認
            if final_path.exists():
                print(f"[WARNING] File already exists: {final_path}")
                try:
                    response = input("Overwrite? (y/n): ")
                    if response.lower() != 'y':
                        return False
                except EOFError:
                    print("[INFO] Non-interactive mode: overwriting existing file")
                    # 非対話モードでは上書き

            # 完成版を保存
            with open(final_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            print(f"[SUCCESS] Final digest saved: {final_path}")

            # ===== ここまで成功した場合のみ、以下を実行 =====

            # 全体的なテンプレートファイルをクリーンアップ
            print("[INFO] Cleaning up template files...")
            self.cleanup_template_files()

            # タイムスタンプ更新
            print(f"[INFO] Updating last_digest_times.json for {level}")
            self.save_last_digest_time(level)

            # 元のファイルを削除するか確認
            if source_file != final_path:
                try:
                    response = input(f"\nDelete source file? {source_file} (y/n): ")
                    if response.lower() == 'y':
                        source_file.unlink()
                        print(f"[INFO] Source file deleted: {source_file}")
                except EOFError:
                    # 非対話モードでは自動削除
                    print("[INFO] Non-interactive mode: auto-deleting source file")
                    source_file.unlink()
                    print(f"[INFO] Source file deleted: {source_file}")

            print(f"[SUCCESS] Digest finalization completed!")
            return True

        except FileNotFoundError as e:
            print(f"[ERROR] File not found: {e}")
            return False
        except json.JSONDecodeError as e:
            print(f"[ERROR] Invalid JSON format: {e}")
            return False
        except Exception as e:
            print(f"[ERROR] Finalization failed: {e}")
            # エラー時は一切の更新を行わない
            # テンプレートファイルも残す（再実行可能にするため）
            return False

def main():
    """メイン実行関数"""
    parser = argparse.ArgumentParser(
        description="Finalize digest with Weave-decided title",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script:
1. Reads the Weave-analyzed file
2. Generates proper filename based on Weave title
3. Updates metadata with the title
4. Saves as final digest
5. Updates last_digest_times.json

Example:
  python finalize_with_title.py W0002_Loop0006-0010統合.json "知性射程理論と協働AI実現"
        """
    )

    parser.add_argument("analyzed_file",
                       help="Path to the Weave-analyzed file")
    parser.add_argument("weave_title",
                       help="Title decided by Weave")

    args = parser.parse_args()

    # ファイナライザー実行
    finalizer = DigestFinalizerWithTitle()
    success = finalizer.finalize_with_title(args.analyzed_file, args.weave_title)

    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()