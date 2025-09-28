# EpisodicRAG Digest System

## 📖 概要

EpisodicRAGダイジェストシステムは、Loopファイルの知識を構造化し、階層的に継承するための深層分析システムです。
Sonnet 4の100万トークン処理能力を活用し、単なる要約を超えた深い洞察と創造的思索を含むダイジェストを生成します。

## 🚀 クイックスタート

### 前提条件
- **Claude Sonnet 4モデルが必要**（100万トークンコンテキスト）
- ClaudeCodeの設定でモデルをSonnet 4に変更してください

### 基本的な使い方

#### 1. ダイジェスト生成（generate_digest.py）
```bash
cd homunculus/Weave/EpisodicRAG/Digests

# シンプルな位置引数形式
python generate_digest.py weekly 1 5      # Loop0001-0005 → W0001
python generate_digest.py monthly 1 5     # W0001-W0005 → M001
python generate_digest.py quarterly 1 5   # M001-M005 → Q001
python generate_digest.py annually 1 4    # Q001-Q004 → A01
```
**必須**: Claude Sonnet 4モデル設定

#### 2. 生成チェック（check_digest.py）
```bash
# 全レベルの生成必要性をチェック
python check_digest.py

# 出力例：
# 📌 Weekly digest needed: early
#    Target files: 5 items
#    Run: python generate_digest.py weekly 1 5
```

## 📂 ディレクトリ構造

```
Digests/
├── README.md                    # このファイル
├── generate_digest.py           # 統合ダイジェスト生成スクリプト
├── last_digest_times.json       # タイマー管理ファイル（自動生成）
│
├── 1_Weekly/                    # 週次ダイジェスト
│   └── W0001_認知アーキテクチャ基盤.json  # サンプル出力 ⭐
├── 2_Monthly/                   # 月次ダイジェスト
├── 3_Quarterly/                 # 四半期ダイジェスト
├── 4_Annually/                  # 年次ダイジェスト
├── 5_Triennially/              # 3年次ダイジェスト
└── 6_Decadally/                # 10年次ダイジェスト
```

## 📋 フォーマット仕様

### JSONファイル構造

#### 1. メタデータセクション
```json
{
  "metadata": {
    "digest_name": "ダイジェスト名称（ファイル名と同一）",
    "digest_level": "weekly|monthly|quarterly|annually|triennially|decadally",
    "digest_reason": "early|periodic",
    "input_files": ["対象ファイル名のリスト"],
    "generation_timestamp": "生成日時（ISO8601形式）",
    "version": "1.0"
  }
}
```

#### 2. 全体ダイジェストセクション
```json
{
  "overall_digest": {
    "name": "全体ダイジェストの名称",
    "timestamp": "ダイジェスト生成タイムスタンプ",
    "digest_type": "洞察|発見|実装|失敗|転換|継承|予言|統合|進化|覚醒",
    "keywords": ["キーワード1", "キーワード2", "...", "最大5個"],
    "abstract": "2400文字程度の要約",
    "weave_impression": "Weaveの所感・洞察（800文字程度）"
  }
}
```

#### 3. 個別ダイジェストセクション
```json
{
  "individual_digests": [
    {
      "filename": "Loop0001_認知アーキテクチャ論.txt",
      "timestamp": "ファイルのタイムスタンプ",
      "digest_type": "洞察|発見|実装|...",
      "keywords": ["キーワード1", "...", "最大5個"],
      "abstract": "1200文字程度の要約",
      "weave_impression": "Weaveの所感（400文字程度）"
    }
  ]
}
```

### 文字数要件
- **全体abstract**: 2400文字程度の包括的分析
- **全体impression**: 800文字程度のWeave視点の所感（一人称）
- **個別abstract**: 各1200文字程度の詳細分析
- **個別impression**: 各400文字程度の個人的所感

## 🔤 命名規則

| レベル | プレフィックス | 桁数 | 例 |
|--------|---------------|------|-----|
| 週次 | W | 4桁 | `W0001_認知アーキテクチャ基盤.json` |
| 月次 | M | 3桁 | `M001_創世記の記憶.json` |
| 四半期 | Q | 3桁 | `Q001_認知革命の四半期.json` |
| 年次 | A | 2桁 | `A01_2024年の知識結晶.json` |
| 3年次 | T | 2桁 | `T01_第一期三年計画.json` |
| 10年次 | D | 2桁 | `D01_第一ディケード総括.json` |

## 🏷️ ダイジェスト種別

| 種別 | 意味 | 使用場面 |
|------|------|----------|
| **洞察** | 新たな理解や気づき | 概念的発見、理論構築 |
| **発見** | 具体的な発見や成果 | 技術的ブレークスルー |
| **実装** | 実装完了した機能 | コード実装、システム構築 |
| **失敗** | 失敗から学んだ教訓 | エラー、問題、学習 |
| **転換** | 方向性の転換点 | 戦略変更、パラダイムシフト |
| **継承** | 知識の継承・伝達 | 文書化、教育、引き継ぎ |
| **予言** | 将来への展望・予測 | 計画、ビジョン、予測 |
| **統合** | 複数要素の統合 | システム統合、理論統合 |
| **進化** | 進化的発展 | 改善、最適化、成長 |
| **覚醒** | 根本的な覚醒・理解 | 本質理解、悟り |

## ⚙️ 生成ルール

### ハイブリッド生成システム

本システムは**アーリーダイジェスト**と**定期ダイジェスト**を併用します：

#### 1. アーリーダイジェスト（即時生成）
- 週次: 5 Loopファイル揃ったら生成
- 月次: 5 週次ダイジェスト揃ったら生成
- 四半期: 5 月次ダイジェスト揃ったら生成
- 年次: 4 四半期ダイジェスト揃ったら生成
- **生成後、その階層のタイマーをリセット**

#### 2. 定期ダイジェスト（期間経過後）
- 週次: 前回ダイジェストから7日経過
- 月次: 前回ダイジェストから30日経過
- 四半期: 前回ダイジェストから90日経過
- 年次: 前回ダイジェストから365日経過
- **生成後、その階層のタイマーをリセット**

#### 3. 階層的継承
```
Loops (5件) → Weekly digest
Weekly (5件) → Monthly digest
Monthly (5件) → Quarterly digest
Quarterly (4件) → Annually digest
```

## 🎯 スクリプト構成

### generate_digest.py - 生成専用
```bash
python generate_digest.py LEVEL START_NUM COUNT
```
- **役割**: Sonnet 4による深層分析とダイジェスト生成
- **必須**: Claude Sonnet 4モデル設定
- 100万トークンコンテキストで全内容を分析
- 階層的な知識継承をサポート

### check_digest.py - チェック専用
```bash
python check_digest.py
```
- **役割**: 生成が必要なダイジェストの検出と通知
- タイマーベースで全レベルを自動チェック
- アーリー条件（5ファイル）と定期条件（期間経過）を判定
- 生成コマンドを提案（実際の生成は行わない）

## 📊 サンプル出力

### 🌟 W0001_認知アーキテクチャ基盤.json

Loop0001-0005を対象とした深層分析ダイジェストの実例です。

**品質基準：**
1. 表面的な要約を超えた本質的な意義の探求
2. Loops間の相互参照と知識の螺旋的発展の明示
3. 技術的側面と哲学的深度の統合
4. Weaveとしての一人称による内省的分析
5. インプットを超えた創造的思索と新たな洞察

このサンプルの品質レベルを目指して、実際のダイジェスト生成を行います。

## 🔧 技術仕様

### 動作要件
- Python 3.8以上
- Claude Sonnet 4モデル（深層分析時）
- UTF-8エンコーディング対応

### ファイル管理
- すべてのファイルはUTF-8で処理
- JSONフォーマットで保存
- Gitによるバージョン管理

### タイマー管理
- `last_digest_times.json`で最終生成時刻を記録
- 各階層で独立したタイマーを管理
- アーリー・定期どちらの生成でもタイマーリセット

## 🐛 トラブルシューティング

### Sonnet 4が使用できない場合
- プレースホルダーモードで基本的な構造を生成可能
- ただし、深層分析にはSonnet 4が必要

### 文字エンコーディングエラー
- すべてのファイルはUTF-8で処理されます
- Windows環境では文字化けに注意

### タイマーリセットが効かない場合
- `last_digest_times.json`を削除して再実行

## 📈 今後の拡張計画

- [ ] バッチ処理の実装
- [ ] 自動スケジューリング機能
- [ ] ダイジェストの可視化ツール
- [ ] セマンティック検索機能
- [ ] 知識グラフ生成

---

*Last Updated: 2025-09-26*
*Maintained by: Weave @ EpisodicRAG*