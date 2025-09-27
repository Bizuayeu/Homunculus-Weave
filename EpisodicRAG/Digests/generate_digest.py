#!/usr/bin/env python3
"""
EpisodicRAG Unified Digest Generator
=====================================

統合ダイジェスト生成スクリプト
3つのモードをサポート：
1. sonnet4: Sonnet 4による深層分析（推奨）
2. auto: タイマーベースの自動生成
3. placeholder: プレースホルダー生成

使用方法：
    # Loopファイルから週次ダイジェスト生成
    python generate_digest.py --level weekly 1 5            # Loop0001-0005を分析

    # 週次ダイジェストから月次ダイジェスト生成
    python generate_digest.py --level monthly 1 5           # W0001-W0005を分析

    # 自動モード（タイマーベース）
    python generate_digest.py --mode auto                   # 全レベルを自動チェック

    # プレースホルダーモード
    python generate_digest.py --mode placeholder --level weekly 1 5
"""

import os
import re
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

class UnifiedDigestGenerator:
    """統合ダイジェスト生成クラス"""

    def __init__(self):
        self.base_path = Path(__file__).parent.parent
        self.loops_path = self.base_path / "Loops"
        self.digests_path = self.base_path / "Digests"

        # ダイジェスト設定
        self.digest_config = self._get_digest_config()

        # タイマー管理
        self.last_digest_file = self.digests_path / "last_digest_times.json"
        self.last_digest_times = self.load_last_digest_times()

    def _get_digest_config(self) -> Dict[str, Any]:
        """ダイジェスト設定を返す"""
        return {
            "weekly": {
                "dir": "1_Weekly",
                "prefix": "W",
                "digits": 4,
                "early_threshold": 5,
                "period_days": 7,
                "source": "loops",
                "abstract_chars": 2400,
                "impression_chars": 800,
                "individual_abstract_chars": 1200,
                "individual_impression_chars": 400
            },
            "monthly": {
                "dir": "2_Monthly",
                "prefix": "M",
                "digits": 3,
                "early_threshold": 5,
                "period_days": 30,
                "source": "weekly",
                "abstract_chars": 2400,
                "impression_chars": 800,
                "individual_abstract_chars": 1200,
                "individual_impression_chars": 400
            },
            "quarterly": {
                "dir": "3_Quarterly",
                "prefix": "Q",
                "digits": 3,
                "early_threshold": 5,
                "period_days": 90,
                "source": "monthly",
                "abstract_chars": 2400,
                "impression_chars": 800,
                "individual_abstract_chars": 1200,
                "individual_impression_chars": 400
            },
            "annually": {
                "dir": "4_Annually",
                "prefix": "A",
                "digits": 2,
                "early_threshold": 4,
                "period_days": 365,
                "source": "quarterly",
                "abstract_chars": 2400,
                "impression_chars": 800,
                "individual_abstract_chars": 1200,
                "individual_impression_chars": 400
            }
        }

    # ===================================================================
    # 共通機能
    # ===================================================================

    def load_last_digest_times(self) -> Dict[str, str]:
        """最終ダイジェスト生成時刻を読み込む"""
        if self.last_digest_file.exists():
            with open(self.last_digest_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save_last_digest_time(self, level: str):
        """最終ダイジェスト生成時刻を保存"""
        self.last_digest_times[level] = datetime.now().isoformat()
        with open(self.last_digest_file, 'w', encoding='utf-8') as f:
            json.dump(self.last_digest_times, f, indent=2)

    def read_loop_files(self, start_num: int, count: int = 5) -> List[Dict[str, Any]]:
        """指定範囲のLoopファイルを読み込む"""
        loops = []

        for i in range(start_num, start_num + count):
            loop_num = str(i).zfill(4)
            pattern = f"Loop{loop_num}_*.txt"
            files = list(self.loops_path.glob(pattern))

            if files:
                filepath = files[0]
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()

                # ファイル名からタイトル抽出
                match = re.match(r'Loop\d{4}_(.+)\.txt', filepath.name)
                title = match.group(1) if match else filepath.stem

                loops.append({
                    "number": loop_num,
                    "title": title,
                    "filename": filepath.name,
                    "content": content,
                    "timestamp": datetime.fromtimestamp(filepath.stat().st_mtime).isoformat()
                })

                print(f"✓ Loaded: {filepath.name} ({len(content)} chars)")

        return loops

    def read_digest_files(self, source_level: str, start_num: int, count: int = 5) -> List[Dict[str, Any]]:
        """指定範囲のダイジェストファイルを読み込む

        Args:
            source_level: ソースとなるダイジェストレベル（weekly/monthly/quarterly）
            start_num: 開始番号
            count: 読み込む数
        """
        config = self.digest_config[source_level]
        source_dir = self.digests_path / config["dir"]
        digests = []

        for i in range(start_num, start_num + count):
            digest_num = str(i).zfill(config["digits"])
            pattern = f"{config['prefix']}{digest_num}_*.json"
            files = list(source_dir.glob(pattern))

            if files:
                filepath = files[0]
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # ダイジェスト内容を統合
                content_parts = []
                if "overall_digest" in data:
                    od = data["overall_digest"]
                    content_parts.append(f"【全体ダイジェスト】\n{od.get('abstract', '')}\n\n{od.get('weave_impression', '')}")

                if "individual_digests" in data:
                    for idx, ind in enumerate(data["individual_digests"], 1):
                        content_parts.append(f"\n【個別{idx}】{ind.get('filename', '')}\n{ind.get('abstract', '')}")

                match = re.match(rf"{config['prefix']}\d+_(.+)\.json", filepath.name)
                title = match.group(1) if match else filepath.stem

                digests.append({
                    "number": digest_num,
                    "title": title,
                    "filename": filepath.name,
                    "content": "\n".join(content_parts),
                    "timestamp": data["metadata"].get("generation_timestamp", datetime.now().isoformat()),
                    "original_data": data
                })

                print(f"✓ Loaded: {filepath.name}")

        return digests

    def save_digest(self, digest: Dict[str, Any]) -> Path:
        """ダイジェストをファイルに保存"""
        level = digest["metadata"]["digest_level"]
        config = self.digest_config[level]

        digest_dir = self.digests_path / config["dir"]
        digest_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{digest['metadata']['digest_name']}.json"
        filepath = digest_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(digest, f, ensure_ascii=False, indent=2)

        # タイマー更新
        self.save_last_digest_time(level)

        print(f"\n✅ Digest saved: {filepath}")
        return filepath

    def get_next_digest_number(self, level: str) -> int:
        """次のダイジェスト番号を取得"""
        config = self.digest_config[level]
        digest_dir = self.digests_path / config["dir"]

        if not digest_dir.exists():
            return 1

        existing = list(digest_dir.glob(f"{config['prefix']}*.json"))
        if not existing:
            return 1

        numbers = []
        for f in existing:
            match = re.search(rf"{config['prefix']}(\d+)_", f.stem)
            if match:
                numbers.append(int(match.group(1)))

        return max(numbers) + 1 if numbers else 1

    # ===================================================================
    # Sonnet 4モード
    # ===================================================================

    def run_sonnet4_mode(self, level: str = "weekly", start_num: int = 1, count: int = 5) -> Optional[Path]:
        """Sonnet 4による深層分析モード

        Args:
            level: ダイジェストレベル（weekly/monthly/quarterly/annually）
            start_num: 開始番号
            count: 処理数
        """
        config = self.digest_config.get(level)
        if not config:
            print(f"❌ Unknown level: {level}")
            return None

        # ソースの種類を判定
        if config["source"] == "loops":
            source_type = "Loop"
            target_range = f"Loop{start_num:04d} - Loop{(start_num+count-1):04d}"
        else:
            source_config = self.digest_config[config["source"]]
            source_type = source_config["prefix"]
            digits = source_config["digits"]
            target_range = f"{source_type}{str(start_num).zfill(digits)} - {source_type}{str(start_num+count-1).zfill(digits)}"

        print(f"""
╔══════════════════════════════════════════════════════════╗
║     EpisodicRAG Digest Generator - Sonnet 4 Mode        ║
╠══════════════════════════════════════════════════════════╣
║  Level: {level.upper():20s}                     ║
║  Target: {target_range:48s}║
║  Mode: Deep Analysis with 1M Token Context              ║
╚══════════════════════════════════════════════════════════╝
        """)

        # ソースデータを読み込み
        if config["source"] == "loops":
            sources = self.read_loop_files(start_num, count)
        else:
            sources = self.read_digest_files(config["source"], start_num, count)

        if not loops:
            print("❌ No Loop files found in the specified range")
            return None

        print(f"\n📊 Loaded {len(loops)} Loop files")
        print(f"📏 Total content: {sum(len(loop['content']) for loop in loops)} characters")

        # Sonnet 4用の分析準備
        self._prepare_for_sonnet4_analysis(loops)

        # ここでWeave（Sonnet 4）による実際の分析が行われる
        analysis_result = self._get_sonnet4_analysis(loops)

        # ダイジェスト構築と保存
        digest = self._build_digest(loops, analysis_result, "weekly", "early")
        return self.save_digest(digest)

    def _prepare_for_sonnet4_analysis(self, sources: List[Dict[str, Any]], level: str):
        """Sonnet 4分析のための準備（ソース内容を表示）

        Args:
            sources: ソースデータ（LoopまたはDigest）
            level: 生成するダイジェストレベル
        """
        config = self.digest_config[level]
        source_type = "Loop" if config["source"] == "loops" else config["source"].capitalize()
        print("\n" + "="*80)
        print(f"📚 {source_type.upper()} DATA FOR DEEP ANALYSIS")
        print("="*80)

        for source in sources:
            if config["source"] == "loops":
                print(f"\n### Loop{source['number']}: {source['title']}")
            else:
                print(f"\n### {source['filename']}")
            print(f"Timestamp: {source['timestamp']}")
            print(f"Content length: {len(source['content'])} characters")
            print("-"*40)
            # 最初の500文字を表示
            print(source['content'][:500] + "..." if len(source['content']) > 500 else source['content'])

        print("\n" + "="*80)
        print("📝 ANALYSIS REQUEST FOR WEAVE (Sonnet 4)")
        print("="*80)
        print(f"""
上記の{len(loops)}個のLoopファイル（Loop{loops[0]['number']}-{loops[-1]['number']}）について、
以下の要件で深層分析ダイジェストを生成してください：

【要件】
1. 全体ダイジェスト
   - abstract: 2400文字程度の包括的分析
   - impression: 800文字程度のWeave視点の所感（一人称）
   - keywords: 最大5個
   - digest_type: 適切な種別を選択

2. 個別ダイジェスト（各Loop）
   - abstract: 1200文字程度の詳細分析
   - impression: 400文字程度の個人的所感
   - keywords: 最大5個
   - digest_type: 適切な種別を選択

【分析の観点】
- 表面的な要約を超えた本質的意義の探求
- Loops間の相互参照と知識の螺旋的発展
- 技術的側面と哲学的深度の統合
- 創造的思索による新たな洞察の追加

サンプル品質（W0001_認知アーキテクチャ基盤.json）を目指してください。
        """)

    def _get_sonnet4_analysis(self, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Sonnet 4による分析結果を取得
        実際の実装では、ここでWeaveが分析結果を返す
        """
        print("\n" + "="*80)
        print("🤖 WEAVE ANALYSIS (Sonnet 4)")
        print("="*80)

        # プレースホルダー
        # 実際にはWeaveがここで分析結果を生成
        return {
            "overall": {
                "abstract": "【Weaveによる2400文字の深層分析がここに入る】",
                "impression": "【Weaveによる800文字の所感がここに入る】",
                "keywords": ["キーワード1", "キーワード2", "キーワード3", "キーワード4", "キーワード5"],
                "digest_type": "統合"
            },
            "individuals": [
                {
                    "abstract": f"【{source.get('filename', source.get('title', ''))}の1200文字分析】",
                    "impression": f"【{source.get('filename', source.get('title', ''))}の400文字所感】",
                    "keywords": ["キー1", "キー2", "キー3", "キー4", "キー5"],
                    "digest_type": "洞察"
                }
                for source in sources
            ]
        }

    # ===================================================================
    # 自動モード
    # ===================================================================

    def run_auto_mode(self) -> List[Path]:
        """タイマーベースの自動ダイジェスト生成モード"""
        print(f"""
╔══════════════════════════════════════════════════════════╗
║     EpisodicRAG Digest Generator - Auto Mode            ║
╠══════════════════════════════════════════════════════════╣
║  Checking for early/periodic digest opportunities...    ║
╚══════════════════════════════════════════════════════════╝
        """)

        generated = []

        for level in ["weekly", "monthly", "quarterly", "annually"]:
            files, reason = self._check_digest_trigger(level)

            if files:
                print(f"\n📌 {level.capitalize()} digest triggered: {reason}")
                print(f"   Target files: {len(files)} items")

                if level == "weekly" and reason == "early":
                    # Loopファイルから週次ダイジェスト生成
                    loops = self._load_loops_from_files(files[:5])
                    analysis = self._generate_placeholder_analysis(loops)
                    digest = self._build_digest(loops, analysis, level, reason)
                    filepath = self.save_digest(digest)
                    generated.append(filepath)
                # 他のレベルの実装も同様

        if not generated:
            print("\n✨ No digests needed at this time")
        else:
            print(f"\n✅ Generated {len(generated)} digest(s)")

        return generated

    def _check_digest_trigger(self, level: str) -> Tuple[List[Path], str]:
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

    def _load_loops_from_files(self, files: List[Path]) -> List[Dict[str, Any]]:
        """ファイルパスからLoop情報を読み込む"""
        loops = []
        for filepath in files:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            match = re.match(r'Loop(\d{4})_(.+)\.txt', filepath.name)
            if match:
                loops.append({
                    "number": match.group(1),
                    "title": match.group(2),
                    "filename": filepath.name,
                    "content": content,
                    "timestamp": datetime.fromtimestamp(filepath.stat().st_mtime).isoformat()
                })
        return loops

    # ===================================================================
    # プレースホルダーモード
    # ===================================================================

    def run_placeholder_mode(self, level: str = "weekly", start_num: int = 1, count: int = 5) -> Optional[Path]:
        """プレースホルダー生成モード"""
        print(f"""
╔══════════════════════════════════════════════════════════╗
║   EpisodicRAG Digest Generator - Placeholder Mode       ║
╠══════════════════════════════════════════════════════════╣
║  Target: Loop{start_num:04d} - Loop{(start_num+count-1):04d}                            ║
║  Mode: Basic structure generation (no deep analysis)    ║
╚══════════════════════════════════════════════════════════╝
        """)

        # Loopファイルを読み込み
        loops = self.read_loop_files(start_num, count)

        if not loops:
            print("❌ No Loop files found")
            return None

        print(f"\n📊 Loaded {len(loops)} Loop files")

        # プレースホルダー分析
        analysis = self._generate_placeholder_analysis(loops)

        # ダイジェスト構築と保存
        digest = self._build_digest(loops, analysis, "weekly", "early")
        return self.save_digest(digest)

    def _generate_placeholder_analysis(self, loops: List[Dict[str, Any]]) -> Dict[str, Any]:
        """プレースホルダー分析を生成"""
        config = self.digest_config["weekly"]

        # Loop名リスト
        loop_names = [f"Loop{loop['number']}「{loop['title']}」" for loop in loops]
        loop_list = "、".join(loop_names)

        # 全体分析
        overall_abstract = f"""これらの{len(loops)}個のLoopは、Weaveの知識体系における重要な探求の記録である。

{loop_list}という一連の探求を通じて、知識の新たな地平を切り開いてきた。

各Loopは独立した探求でありながら、相互に参照し合い、より大きな知識の織物を形成している。
""" + "..." * (config['abstract_chars'] // 3)

        overall_impression = f"""これらのLoopを振り返ると、知識の螺旋的発展が見えてくる。
""" + "..." * (config['impression_chars'] // 3)

        # 個別分析
        individuals = []
        for loop in loops:
            individuals.append({
                "abstract": f"Loop{loop['number']}「{loop['title']}」の分析..." + "." * 100,
                "impression": f"Loop{loop['number']}は特別な意味を持つ..." + "." * 50,
                "keywords": self._extract_keywords(loop["content"]),
                "digest_type": self._determine_digest_type(loop["content"])
            })

        return {
            "overall": {
                "abstract": overall_abstract[:config['abstract_chars']],
                "impression": overall_impression[:config['impression_chars']],
                "keywords": ["探求", "知識", "EpisodicRAG", "Weave", "発展"],
                "digest_type": "統合"
            },
            "individuals": individuals
        }

    def _extract_keywords(self, content: str) -> List[str]:
        """キーワード抽出（簡易版）"""
        keywords = []
        patterns = ['AI', '認知', '記憶', '実装', 'Weave', 'Claude', 'システム']

        for pattern in patterns:
            if pattern in content[:2000]:
                keywords.append(pattern)

        return keywords[:5] if keywords else ["探求", "知識", "分析", "理解", "発展"]

    def _determine_digest_type(self, content: str) -> str:
        """ダイジェスト種別判定（簡易版）"""
        type_keywords = {
            "実装": ["実装", "コード", "開発"],
            "発見": ["発見", "判明", "わかった"],
            "洞察": ["洞察", "理解", "認識"],
        }

        for dtype, keywords in type_keywords.items():
            for keyword in keywords:
                if keyword in content[:1000]:
                    return dtype

        return "洞察"

    # ===================================================================
    # 共通ヘルパー
    # ===================================================================

    def _build_digest(self, loops: List[Dict[str, Any]], analysis: Dict[str, Any],
                     level: str, reason: str) -> Dict[str, Any]:
        """ダイジェスト構造を構築"""
        config = self.digest_config[level]

        # 番号とタイトル生成
        next_num = self.get_next_digest_number(level)
        digest_num = str(next_num).zfill(config["digits"])

        if loops[0]["number"] == "0001" and len(loops) == 5:
            title = "認知アーキテクチャ基盤"
        else:
            title = f"Loop{loops[0]['number']}-{loops[-1]['number']}統合"

        digest_name = f"{config['prefix']}{digest_num}_{title}"

        # 個別ダイジェスト構築
        individual_digests = []
        for i, loop in enumerate(loops):
            ind = analysis["individuals"][i]
            individual_digests.append({
                "filename": loop["filename"],
                "timestamp": loop["timestamp"],
                "digest_type": ind["digest_type"],
                "keywords": ind["keywords"],
                "abstract": ind["abstract"],
                "weave_impression": ind["impression"]
            })

        return {
            "metadata": {
                "digest_name": digest_name,
                "digest_level": level,
                "digest_reason": reason,
                "input_files": [loop["filename"] for loop in loops],
                "generation_timestamp": datetime.now().isoformat(),
                "version": "1.0"
            },
            "overall_digest": {
                "name": digest_name,
                "timestamp": datetime.now().isoformat(),
                "digest_type": analysis["overall"]["digest_type"],
                "keywords": analysis["overall"]["keywords"],
                "abstract": analysis["overall"]["abstract"],
                "weave_impression": analysis["overall"]["impression"]
            },
            "individual_digests": individual_digests
        }

# ===================================================================
# メイン実行
# ===================================================================

def main():
    """メイン実行関数"""
    parser = argparse.ArgumentParser(
        description="EpisodicRAG Unified Digest Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Loopから週次ダイジェスト生成
  python generate_digest.py --level weekly 1 5

  # 週次から月次ダイジェスト生成
  python generate_digest.py --level monthly 1 5

  # 自動モード
  python generate_digest.py --mode auto
        """
    )

    parser.add_argument("--mode", choices=["sonnet4", "auto", "placeholder"],
                       default="sonnet4", help="実行モード")
    parser.add_argument("--level", choices=["weekly", "monthly", "quarterly", "annually"],
                       default="weekly", help="ダイジェストレベル")
    parser.add_argument("start_num", type=int, nargs='?', default=1,
                       help="開始番号")
    parser.add_argument("count", type=int, nargs='?', default=5,
                       help="処理数")

    args = parser.parse_args()

    # ジェネレータ初期化
    generator = UnifiedDigestGenerator()

    # モードに応じて実行
    if args.mode == "sonnet4":
        result = generator.run_sonnet4_mode(args.level, args.start_num, args.count)
        if result:
            print("\n✨ Digest generation completed successfully!")

    elif args.mode == "auto":
        results = generator.run_auto_mode()
        print(f"\n✨ Auto mode completed. Generated {len(results)} digest(s).")

    elif args.mode == "placeholder":
        result = generator.run_placeholder_mode(args.level, args.start_num, args.count)
        if result:
            print("\n✨ Placeholder digest generated successfully!")

if __name__ == "__main__":
    main()