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
├── README.md                  # プロジェクト概要
├── EpisodicRAG/              # 🧠 エピソード記憶システム
│   ├── HowToUseEpisodicRAG.md
│   ├── Loops/                # 対話記録（3桁連番管理）
│   │   ├── Loop001_認知アーキテクチャ論.txt
│   │   ├── Loop002_AI長期記憶論.txt
│   │   └──...
│   └── Digests/              # 階層的要約記憶
│       ├── 1_Weekly/         # 週次ダイジェスト
│       ├── 2_Monthly/        # 月次ダイジェスト  
│       ├── 3_Quarterly/      # 四半期ダイジェスト
│       ├── 4_Annually/       # 年次ダイジェスト
│       └── 5_Decadally/      # 十年ダイジェスト
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
    ├── FortuneTeller/            # 占術・姓名判断
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
1. **Loop記録**: 127個以上の対話記録（約7MB）
2. **3桁連番管理**: Loop001-Loop127+形式で統一
3. **階層的要約**: 5段階のDigest構造
4. **日本語完全対応**: ファイル名・内容ともに対応
5. **GitHub同期**: Bizuayeu/Homunculus-Weave

### 環境間連携
- **開発**: ClaudeCode（ローカル）
- **実行**: ComputerUse（Web）
- **共有**: GitHub経由での同期
  - 詳細は [FUNCTION.md#GitHub連携詳細](./FUNCTION.md) を参照

---

*Last Updated: 2025-09-13*
*Maintained by: Weave @ ClaudeCode*
