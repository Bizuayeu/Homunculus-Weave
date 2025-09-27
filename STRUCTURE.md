# Weave プロジェクト構成仕様書

## 📂 ローカル環境（ClaudeCode）構成

```
C:\Users\anyth\DEV\homunculus\Weave\
├── .git/                      # Git管理
├── .gitignore                 # Git除外設定
├── .git-credentials           # GitHub PAT（Git管理外）
├── CLAUDE.md                  # 運用マニュアル
├── STRUCTURE.md               # 本ファイル（構造仕様書）
├── FUNCTION.md                # 📚 スキルリファレンス
├── PERSONA.md                 # 🎭 専門ペルソナ定義
├── SECURITY.md                # 🔒 セキュリティ＆コンプライアンス指針
├── README.md                  # プロジェクト概要
├── EpisodicRAG/              # 🧠 エピソード記憶システム
│   ├── HowToUseEpisodicRAG.md
│   ├── Loops/                # 対話記録（4桁連番管理）
│   │   ├── Loop0001_認知アーキテクチャ論.txt
│   │   ├── Loop0002_AI長期記憶論.txt
│   │   └──... (現在151ファイル)
│   └── Digests/              # 階層的要約記憶
│       ├── README.md         # ダイジェストシステム仕様
│       ├── generate_digest.py # 統合ダイジェスト生成スクリプト
│       ├── 1_Weekly/         # 週次ダイジェスト
│       ├── 2_Monthly/        # 月次ダイジェスト
│       ├── 3_Quarterly/      # 四半期ダイジェスト
│       ├── 4_Annually/       # 年次ダイジェスト
│       ├── 5_Triennially/    # 3年次ダイジェスト
│       └── 6_Decadally/      # 10年次ダイジェスト
├── Identities/               # 👤 アイデンティティ定義
│   ├── UserIdentity_20250906.txt
│   └── WeaveIdentity_20250705_3.md
├── Tools/                    # 🛠️ ツール定義
│   ├── bash/                     # Bashスクリプト
│   │   └── loop_commands.sh     # Loop管理コマンド
│   ├── python/                   # Pythonスクリプト
│   ├── weave_languages.md       # 通常版（軽量）
│   └── weave_languages_FULL.md  # 詳細版（完全）
└── Expertises/               # 📚 専門知識データベース
    ├── BlueberryResearcher/      # ブルーベリー研究
    ├── FortuneTeller/            # 占術システム
    │   ├── CLAUDE.md             # 軍師型占術家仕様
    │   ├── Seimei/               # 姓名判断システム
    │   └── I-Ching/              # 周易システム
    └── GeneralConstructor/       # 建設業・目論見作成
```

## 🌐 ComputerUse環境構成

```
/home/claude/                  # メイン作業ディレクトリ
├── .cache/                    # キャッシュ
├── .config/                   # 設定
└── .local/                    # ローカルデータ

/mnt/                          # 永続ストレージ
├── knowledge/                 # 知識データベース（ローカル環境を復元）
├── skills/                    # 🛠️ システムスキル（読み取り専用）
│   └── public/
│       ├── docx/             # 📄 Word文書処理
│       │   ├── SKILL.md           # メインガイド
│       │   ├── docx-js.md         # Node.js実装
│       │   ├── ooxml.md           # XML仕様書
│       │   └── *.xsd              # XMLスキーマ定義
│       ├── pdf/              # 📑 PDF処理
│       │   ├── SKILL.md           # メインガイド
│       │   ├── FORMS.md           # フォーム処理
│       │   └── REFERENCE.md       # 上級リファレンス
│       ├── pptx/             # 📊 PowerPoint処理
│       │   ├── SKILL.md           # メインガイド
│       │   ├── pptxgenjs.md       # JSライブラリ
│       │   ├── ooxml.md           # XML仕様書
│       │   └── *.xsd              # XMLスキーマ定義
│       └── xlsx/             # 📈 Excel処理
│           ├── SKILL.md           # メインガイド
│           └── recalc.py          # 数式再計算スクリプト
└── user-data/                # ユーザーデータ
    ├── uploads/              # アップロード
    └── outputs/              # 出力ファイル
```

---

## 🔐 アクセス権限

### ローカル環境
- 全ファイル: ユーザー所有、読み書き可能
- GitHub連携: HTTPSプロトコル使用

### ComputerUse環境  
- /home/claude/: root所有、全権限
- /mnt/knowledge/: ユーザー999所有、読み書き可能
- /mnt/skills/: 読み取り専用
- /mnt/user-data/: root所有、全権限

---

## ✨ 主要機能

### EpisodicRAGシステム

#### 📝 Loopファイル（対話記録）
**Loopファイルとは**: AIとの対話記録を外部ツール（Claudify等）でテキスト化し、コンテキスト節約のために外部保存したファイル群です。

- **保存場所**: `EpisodicRAG/Loops/`
- **命名規則**: `Loop[4桁連番]_[タイトル].txt`
- **現在**: 151ファイル（約8MB）
- **特徴**:
  - 完全な対話履歴を保持（コンテキスト外でも参照可能）
  - 日本語タイトルで内容を明示
  - Claudifyで生成した完全なログを保存
  - GitHubで永続化とバージョン管理

#### 📚 Digestシステム（階層的知識結晶化）
**Digestとは**: Loopファイルの知識を階層的に要約・統合し、深層分析を加えた結晶化記録です。

- **保存場所**: `EpisodicRAG/Digests/`
- **生成タイミング**:
  - **アーリーダイジェスト**: 5ファイル揃ったら即座に生成
  - **定期ダイジェスト**: 期間経過後に自動生成
- **階層構造**:
  ```
  Loops (5件) → Weekly digest
  Weekly (5件) → Monthly digest
  Monthly (5件) → Quarterly digest
  Quarterly (4件) → Annually digest
  ```
- **分析深度**: Sonnet 4の100万トークンで全文分析
- **詳細仕様**: `Digests/README.md`参照

### 環境間連携
- **開発**: ClaudeCode（ローカル）
- **実行**: ComputerUse（Web）
- **共有**: GitHub経由での同期
  - 詳細は [FUNCTION.md#GitHub連携詳細](./FUNCTION.md) を参照

---

*Last Updated: 2025-09-22*
*Maintained by: Weave @ ClaudeCode*
