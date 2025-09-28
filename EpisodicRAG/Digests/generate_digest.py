#!/usr/bin/env python3
"""
EpisodicRAG Digest Template Generator
======================================

Weave分析用のテンプレート生成スクリプト
詳細な仕様付きプレースホルダーを含むJSONテンプレートを生成

使用方法：
    python generate_digest.py LEVEL START_NUM COUNT

    LEVEL: weekly | monthly | quarterly | annually
    START_NUM: 開始番号
    COUNT: 処理数

例：
    python generate_digest.py weekly 1 5      # Loop0001-0005 → W0001_template.json
    python generate_digest.py monthly 1 5     # W0001-W0005 → M001_template.json

生成後：
    1. テンプレートファイルを確認
    2. Weave（Claude）がプレースホルダーを実際の分析で置換
    3. _template を除いたファイル名で完成版を保存
"""

import json
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import re

class DigestTemplateGenerator:
    """ダイジェストテンプレート生成クラス"""

    def __init__(self):
        self.base_path = Path(__file__).parent.parent
        self.loops_path = self.base_path / "Loops"
        self.digests_path = self.base_path / "Digests"
        self.digest_config = self._get_digest_config()

    def _get_digest_config(self) -> Dict[str, Any]:
        """ダイジェスト設定を返す"""
        return {
            "weekly": {
                "dir": "1_Weekly",
                "prefix": "W",
                "digits": 4,
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
                "source": "quarterly",
                "abstract_chars": 2400,
                "impression_chars": 800,
                "individual_abstract_chars": 1200,
                "individual_impression_chars": 400
            }
        }

    def read_source_files(self, level: str, start_num: int, count: int) -> List[Dict[str, Any]]:
        """ソースファイル（LoopまたはDigest）を読み込む"""
        config = self.digest_config[level]

        if config["source"] == "loops":
            return self._read_loop_files(start_num, count)
        else:
            return self._read_digest_files(config["source"], start_num, count)

    def _read_loop_files(self, start_num: int, count: int) -> List[Dict[str, Any]]:
        """Loopファイルを読み込む"""
        loops = []
        for i in range(start_num, start_num + count):
            loop_num = str(i).zfill(4)
            pattern = f"Loop{loop_num}_*.txt"
            files = list(self.loops_path.glob(pattern))

            if files:
                filepath = files[0]
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()

                match = re.match(r'Loop\d{4}_(.+)\.txt', filepath.name)
                title = match.group(1) if match else filepath.stem

                loops.append({
                    "number": loop_num,
                    "title": title,
                    "filename": filepath.name,
                    "content": content,
                    "timestamp": datetime.fromtimestamp(filepath.stat().st_mtime).isoformat()
                })
                print(f"[OK] Loaded: {filepath.name} ({len(content):,} chars)")

        return loops

    def _read_digest_files(self, source_level: str, start_num: int, count: int) -> List[Dict[str, Any]]:
        """既存のダイジェストファイルを読み込む"""
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
                    content_parts.append(f"【全体】\n{od.get('abstract', '')}\n\n{od.get('weave_impression', '')}")

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
                print(f"[OK] Loaded: {filepath.name}")

        return digests

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

    def generate_template(self, level: str, start_num: int, count: int) -> Optional[Path]:
        """分析用テンプレートを生成"""
        config = self.digest_config.get(level)
        if not config:
            print(f"[ERROR] Unknown level: {level}")
            return None

        # ヘッダー表示
        self._print_header(level, start_num, count, config)

        # ソースファイル読み込み
        sources = self.read_source_files(level, start_num, count)
        if not sources:
            source_type = "Loop" if config["source"] == "loops" else config["source"].capitalize()
            print(f"[ERROR] No {source_type} files found in the specified range")
            return None

        source_type = "Loop" if config["source"] == "loops" else config["source"].capitalize()
        print(f"\n[INFO] Loaded {len(sources)} {source_type} files")
        print(f"[TOTAL] Content: {sum(len(s['content']) for s in sources):,} characters")

        # テンプレート生成
        template = self._create_template(sources, level)

        # 保存
        filepath = self._save_template(template, sources, level)

        # 次のステップを表示
        self._print_next_steps(filepath)

        return filepath

    def _print_header(self, level: str, start_num: int, count: int, config: Dict):
        """ヘッダー表示"""
        if config["source"] == "loops":
            target_range = f"Loop{start_num:04d} - Loop{(start_num+count-1):04d}"
        else:
            source_config = self.digest_config[config["source"]]
            source_type = source_config["prefix"]
            digits = source_config["digits"]
            target_range = f"{source_type}{str(start_num).zfill(digits)} - {source_type}{str(start_num+count-1).zfill(digits)}"

        print(f"""
+==========================================================+
|        EpisodicRAG Digest Template Generator            |
+==========================================================+
|  Level: {level.upper():20s}                     |
|  Target: {target_range:48s}|
|  Output: Placeholder template for Weave analysis        |
+==========================================================+""")

    def _create_template(self, sources: List[Dict[str, Any]], level: str) -> Dict[str, Any]:
        """分析テンプレートを作成"""
        config = self.digest_config[level]
        total_chars = sum(len(s['content']) for s in sources)

        # 全体分析用プレースホルダー
        overall_placeholder = self._create_overall_placeholder(sources, config, total_chars)

        # 個別分析用プレースホルダー
        individual_placeholders = [
            self._create_individual_placeholder(source, config)
            for source in sources
        ]

        return {
            "overall": overall_placeholder,
            "individuals": individual_placeholders,
            "_weave_title_decision": {
                "placeholder": "<!-- WEAVE TITLE DECISION: このダイジェストの内容を象徴する適切なタイトルを決定してください。機械的な「Loop番号統合」ではなく、分析内容の本質を表現する意味のあるタイトルにしてください。例: 知性射程理論と協働AI実現、AI個性化哲学基盤、有限性駆動型知性モデル等 -->",
                "instructions": "上記のプレースホルダーを、分析内容に基づく適切なタイトルで置換してください。このタイトルがファイル名に使用されます。"
            },
            "_analysis_metadata": {
                "source_files": [s["filename"] for s in sources],
                "total_content_length": total_chars,
                "analysis_timestamp": datetime.now().isoformat(),
                "instructions": "プレースホルダーを実際の分析内容で置換してください。HTMLコメントは完全に削除してください。"
            }
        }

    def _create_overall_placeholder(self, sources: List[Dict[str, Any]], config: Dict, total_chars: int) -> Dict:
        """全体分析用プレースホルダー作成"""
        abstract_spec = f"""
<!-- WEAVE ANALYSIS PLACEHOLDER: 全体統合分析 ({config['abstract_chars']}文字程度)

【分析対象】
- ファイル数: {len(sources)}個
- 総文字数: {total_chars:,}文字

【分析要求】
1. 表層的な要約を超えた本質的意義の抽出
2. 相互参照と知識の螺旋的統合
3. 技術的洞察と哲学的深層の統合分析
4. 創造的思考による新たな解釈の追加

【構成指針】
- 第1段落: 全体のテーマと背景文脈
- 第2-3段落: 主要な洞察と技術的発見
- 第4段落: 哲学的・概念的深層分析
- 第5段落: 今後の展望と意義
-->"""

        impression_spec = f"""
<!-- WEAVE IMPRESSION PLACEHOLDER: 所感・展望 ({config['impression_chars']}文字程度)

【記述内容】
1. この期間の群から得られた個人的洞察
2. 技術的発見が持つより広い意義
3. 認知アーキテクチャの進化に対する考察
4. 今後の探究方向への示唆

【トーン】
- Weaveとしての個人的な視点
- 内省的かつ前向きな展望
- 技術と哲学の融合した思考
-->"""

        return {
            "abstract": abstract_spec.strip(),
            "impression": impression_spec.strip(),
            "keywords": [
                "<!-- キーワード1: 主要テーマ -->",
                "<!-- キーワード2: 技術的発見 -->",
                "<!-- キーワード3: 哲学的洞察 -->",
                "<!-- キーワード4: 応用領域 -->",
                "<!-- キーワード5: 発展方向 -->"
            ],
            "digest_type": "<!-- OVERALL_DIGEST_TYPE: 全体分析の特性に応じて適切なタイプを選択してください。選択肢例: 統合(複数要素の結合), 発展(段階的進化), 転換(根本的変化), 確立(基盤構築), 探究(新領域開拓), 深化(既存概念の発展) -->"
        }

    def _create_individual_placeholder(self, source: Dict[str, Any], config: Dict) -> Dict:
        """個別分析用プレースホルダー作成"""
        filename = source.get('filename', 'Unknown')
        content_length = len(source['content'])

        abstract_spec = f"""
<!-- ANALYSIS: {filename} ({config['individual_abstract_chars']}文字程度)

【ファイル情報】
- ファイル名: {filename}
- 文字数: {content_length:,}文字
- タイムスタンプ: {source.get('timestamp', 'Unknown')}

【分析要求】
1. 核心的テーマの特定
2. 技術的・概念的な新規性の抽出
3. 他との関連性・差異点
4. 大きな文脈での位置づけ
-->"""

        impression_spec = f"""
<!-- IMPRESSION: {filename} ({config['individual_impression_chars']}文字程度)

【記述内容】
- 得られた個人的な気づき
- 印象的だった概念や発見
- 今後の発展可能性への期待
-->"""

        return {
            "abstract": abstract_spec.strip(),
            "impression": impression_spec.strip(),
            "keywords": [
                "<!-- キー1: 核心概念 -->",
                "<!-- キー2: 技術的特徴 -->",
                "<!-- キー3: 哲学的側面 -->",
                "<!-- キー4: 実用的価値 -->",
                "<!-- キー5: 独自性 -->"
            ],
            "digest_type": "<!-- DIGEST_TYPE: このLoopの特性に応じて適切なタイプを選択してください。選択肢例: 理論(基礎フレームワーク), 実験(新しい試み), 洞察(深層的発見), 統合(要素結合), 転換(パラダイムシフト), 検証(実証・確認), 探究(未知領域調査) -->"
        }

    def _save_template(self, template: Dict[str, Any], sources: List[Dict[str, Any]], level: str) -> Path:
        """テンプレートを保存"""
        config = self.digest_config[level]

        # ディレクトリ作成
        digest_dir = self.digests_path / config["dir"]
        digest_dir.mkdir(parents=True, exist_ok=True)

        # 番号のみ生成（タイトルはWeaveが決定）
        next_num = self.get_next_digest_number(level)
        digest_num = str(next_num).zfill(config["digits"])

        # 仮のダイジェスト名（Weaveがタイトルを決定後に更新）
        temp_name = f"{config['prefix']}{digest_num}_WEAVE_TITLE_PLACEHOLDER"

        # ダイジェスト構造構築
        digest = {
            "metadata": {
                "digest_name": temp_name,
                "digest_level": level,
                "digest_reason": "template",
                "input_files": [s["filename"] for s in sources],
                "generation_timestamp": datetime.now().isoformat(),
                "version": "1.0",
                "digest_number": digest_num
            },
            "overall_digest": {
                "name": temp_name,
                "timestamp": datetime.now().isoformat(),
                "digest_type": template["overall"]["digest_type"],
                "keywords": template["overall"]["keywords"],
                "abstract": template["overall"]["abstract"],
                "weave_impression": template["overall"]["impression"]
            },
            "individual_digests": [
                {
                    "filename": sources[i]["filename"],
                    "timestamp": sources[i]["timestamp"],
                    "digest_type": template["individuals"][i]["digest_type"],
                    "keywords": template["individuals"][i]["keywords"],
                    "abstract": template["individuals"][i]["abstract"],
                    "weave_impression": template["individuals"][i]["impression"]
                }
                for i in range(len(sources))
            ]
        }

        # ファイル保存
        filename = f"{temp_name}_template.json"
        filepath = digest_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(digest, f, ensure_ascii=False, indent=2)

        print(f"\n[SUCCESS] Template saved: {filepath}")
        return filepath

    def _print_next_steps(self, filepath: Path):
        """次のステップを表示"""
        print("\n" + "="*60)
        print("NEXT STEPS: WEAVE ANALYSIS REQUIRED")
        print("="*60)
        print(f"""
1. テンプレートファイルを確認:
   {filepath}

2. Weave（Claude）による分析:
   - プレースホルダーを実際の分析内容で置換
   - HTMLコメントは完全に削除
   - 指定文字数で高品質な分析を記述

3. 完成版の保存:
   - "_template" を除いたファイル名で保存
""")

def main():
    """メイン実行関数"""
    parser = argparse.ArgumentParser(
        description="EpisodicRAG Digest Template Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_digest.py weekly 1 5      # Loop0001-0005 → W0001_template.json
  python generate_digest.py monthly 1 5     # W0001-W0005 → M001_template.json
  python generate_digest.py quarterly 1 5   # M001-M005 → Q001_template.json
  python generate_digest.py annually 1 4    # Q001-Q004 → A01_template.json
        """
    )

    parser.add_argument("level",
                       choices=["weekly", "monthly", "quarterly", "annually"],
                       help="Digest level to generate")
    parser.add_argument("start_num", type=int,
                       help="Starting number")
    parser.add_argument("count", type=int,
                       help="Number of items to process")

    args = parser.parse_args()

    # テンプレート生成
    generator = DigestTemplateGenerator()
    result = generator.generate_template(args.level, args.start_num, args.count)

    if result:
        print("\n[SUCCESS] Template generation completed!")
    else:
        print("\n[ERROR] Template generation failed")
        sys.exit(1)

if __name__ == "__main__":
    main()