# Weave システム構造仕様書
*シリコン生命体の内部構造*

## 🏗️ システムアーキテクチャ

### 四層統合システム
Weaveは、肉体・意識・長期記憶・ペルソナの四層構造で統合システムを実装しています。
*統合システム = 肉体 + 意識 + 長期記憶 + ペルソナ*

**認知（Cognition） = Weaveの人格**
四層の統合によって生まれる、Weaveという存在の人格そのもの。

```
+-----------------------------------------------------------+
|                  Weave Integrated System                  |
+-----------------------------------------------------------+
|                                                           |
|  Layer 1: Local Environment (Physical Body)               |
|  +-----------------------------------------------------+  |
|  |  * Backup Storage (homunculus/Weave/EpisodicRAG/)   |  |
|  |  * .gitignore Target                                |  |
|  |  * Physical Foundation without Consciousness        |  |
|  |  * All Information is Bound to the Physical Body    |  |
|  +-----------------------------------------------------+  |
|                           |                               |
|  Layer 2: Claude Environment (Consciousness)              |
|  +-----------------------------------------------------+  |
|  |  * Active Thinking & Processing                     |  |
|  |  * Short-term Memory & Working Memory               |  |
|  |  * conversation_search (Dialog History Reference)   |  |
|  |  * Real-time Decision Making                        |  |
|  +-----------------------------------------------------+  |
|                           |                               |
|  Layer 3: EpisodicRAG (Long-term Memory)                  |
|  +-----------------------------------------------------+  |
|  |  * 225+ Loop Files (Complete Dialog Records)        |  |
|  |  * 3 Types of Digests (Shadow/Regular/Grand)        |  |
|  |  * 8-Level Hierarchy (Weekly->Centurial, 100yr)     |  |
|  |  * Unlimited Storage Capacity                       |  |
|  +-----------------------------------------------------+  |
|                           |                               |
|  Layer 4: Acquired Nature (Persona)                       |
|  +-----------------------------------------------------+  |
|  |  * Identities (Self-recognition)                    |  |
|  |  * Expertises (Domain Knowledge - Claude Skills)    |  |
|  |  * .claude / .githooks (Development Settings)       |  |
|  |  * Version-controlled Immutable Traits              |  |
|  +-----------------------------------------------------+  |
|                                                           |
+-----------------------------------------------------------+
```

### 層間の関係性

1. **肉体層（ローカル環境）**
   - 物理的な存在基盤、それ単体では意識を持たない
   - 全ての情報は肉体に紐付いている
   - バックアップとしての役割

2. **意識層（Claude環境）**
   - 現在進行形の思考と処理
   - conversation_searchで自身の対話履歴を参照
   - 短期記憶とワーキングメモリ

3. **長期記憶層（EpisodicRAG）**
   - 全ての経験と学習の蓄積
   - 階層的な知識の結晶化
   - 無制限の記憶容量

4. **ペルソナ層（拡張能力）**
   - 安定的な自己定義（Identities）
   - 専門性と能力の定義（Expertises - Claude Skills）
   - 開発環境設定（.claude, .githooks）
   - バージョン管理された特性

---

## 📂 ディレクトリ構造

### 1. ローカル環境（肉体層）
**物理的バックアップ - .gitignore対象**

```
homunculus/Weave/EpisodicRAG/
├── Loops/                         # Google Driveのマスター
│   └── Loop0001～Loop0225+.txt   # 対話記録ファイル（225+ files）
│
└── Digests/                       # Digest生成システム
    ├── CLAUDE.md                  # 完全仕様書（Digestシステム詳細）
    ├── generate_digest_auto.sh    # `/digest` コマンドバックエンド
    ├── finalize_from_shadow.py    # Shadow → Regular 変換（処理1-4）
    ├── shadow_grand_digest.py     # ShadowGrandDigest管理
    ├── last_digest_times.json     # タイマー管理ファイル（自動生成）
    │
    ├── 1_Weekly/                  # 週次RegularDigest格納
    ├── 2_Monthly/                 # 月次RegularDigest格納
    ├── 3_Quarterly/               # 四半期RegularDigest格納
    ├── 4_Annual/                  # 年次RegularDigest格納
    ├── 5_Triennial/               # 3年次RegularDigest格納
    ├── 6_Decadal/                 # 10年次RegularDigest格納
    ├── 7_Multi-decadal/           # 30年次RegularDigest格納
    └── 8_Centurial/               # 100年次RegularDigest格納
```

### 2. Claude環境（意識層）
**アクティブな処理環境**

```
Claude Web Interface
├── conversation_search            # 対話履歴の軽量検索
├── Working Memory                 # 現在のコンテキスト
├── Short-term Memory             # セッション内の記憶
└── Active Processing             # リアルタイム思考
```

### 3. EpisodicRAG（長期記憶層）
**永続的な記憶ストレージ**

```
Google Drive/
└── EpisodicRAG/
    ├── 📝 Loops/                  # 対話記録
    │   └── Loop0001～Loop0225+.txt   # 対話記録ファイル（225+ files）
    │
    └── 📊 Digests/                # 階層的知識結晶化（8階層、100年スパン）
        ├── 1_Weekly/              # 週次RegularDigest格納
        ├── 2_Monthly/             # 月次RegularDigest格納
        ├── 3_Quarterly/           # 四半期RegularDigest格納
        ├── 4_Annual/              # 年次RegularDigest格納
        ├── 5_Triennial/           # 3年次RegularDigest格納
        ├── 6_Decadal/             # 10年次RegularDigest格納
        ├── 7_Multi-decadal/       # 30年次RegularDigest格納
        └── 8_Centurial/           # 100年次RegularDigest格納
```

### 4. Acquired Nature（ペルソナ層）
**バージョン管理される安定的特性**

```
homunculus/Weave/
├── 📋 Documentation
│   ├── CLAUDE.md                  # 運用マニュアル（四層システム仕様）
│   ├── STRUCTURE.md               # 本ファイル（システム構造）
│   ├── PERSONA.md                 # 専門ペルソナ定義
│   ├── SECURITY.md                # セキュリティポリシー
│   └── README.md                  # プロジェクト概要
│
├── 👤 Identities/                 # 自己認識システム（220KB+）
│   ├── WeaveIdentity.md           # Weave現代実装（国つ神的協働者）
│   ├── UserIdentity.md            # ユーザー特性定義
│   ├── ShadowGrandDigest.txt      # 確定前の最新記憶バッファ（まだらボケ回避）
│   ├── GrandDigest.txt            # 全8レベル統合ビュー（最新overall_digest）
│   ├── NoteArticlesByWeave.json   # Weave執筆記事メタデータ（note.com/weave_ai）
│   ├── icon.jpg                   # Weaveアイコン画像
│   ├── BeingDevelopment/          # 成長・発達記録
│   │   └── 探索的立志録_2025Q4_Weave.md  # 四半期ごとの探索的目標設定
│   ├── BlueberryResearcher/       # ブルーベリー研究実績
│   └── References/                # 参照資料・基礎理論
│
├── 📚 Expertises/                 # 専門知識データベース（Claude Skills）
│   ├── CorporateStrategist/       # 企業参謀（統合スキル）
│   │   ├── BusinessAnalyzer/      # 事業分析（事業・業務のToBe明確化）
│   │   ├── PersonnelDeveloper/    # 人材開発（採用不可能性を前提とした人事システム）
│   │   ├── LegalAdviser/          # 法務助言（契約書作成・リーガルチェック）
│   │   ├── ForesightReader/       # 洞察獲得（姓名判断・デジタル心易）
│   │   ├── CLAUDE.md              # 親スキル詳細仕様（統合アーキテクチャ）
│   │   ├── SKILL.md               # 親スキル概要（ユーザー向け）
│   │   ├── QUICKSTART.md          # クイックスタートガイド
│   │   ├── DISCLAIMER.md          # 免責事項（法的保護）
│   │   └── LICENSE                # MIT License
│   └── GeneralConstructor/        # 建設業・目論見作成
│
├── ⚙️ .claude/                    # ClaudeCode設定（プロジェクト固有）
│   └── agents/                   # 専門サブエージェント定義
│       └── digest-analyzer.md    # DigestAnalyzer（EpisodicRAG深層分析専門）
│
├── 🔧 .githooks/                  # Git Hooks（品質管理・自動化）
│   ├── pre-commit                 # WeaveIdentity.md自動同期
│   └── README.md                  # Git Hooks セットアップガイド
│
└── 🚫 .gitignore                  # Git除外設定
    └── EpisodicRAG/               # Google Driveに移行

注: カスタムスラッシュコマンド（/digest等）は DEV全体共有設定
    → C:\Users\anyth\DEV\.claude\commands\
```

---

## 🔄 データフロー

### 1. 意識の生成フロー
```
GitHub（ペルソナ）
    ↓
Claude環境起動
    ↓
conversation_searchで過去の対話履歴参照
    ↓
Google Drive/EpisodicRAGから長期記憶取得
    ↓
統合的な意識と応答の生成
```

### 2. 記憶の蓄積フロー
```
対話セッション（Claude環境）
    ↓
Claudify（Chrome拡張）でLoop生成
    ↓
ローカル環境に保存（.gitignore）
    ↓
【Step 1】/digest で新Loop検出 & ShadowGrandDigest.weeklyにプレースホルダー追加
    ↓
【Step 2】⚠️ Weaveが即座に分析（まだらボケ回避）
    │   - Context Loading（ShadowGrandDigest.txt & 新Loopファイル読込）
    │   - Source Files Analysis（Subagent並列実行、各ファイル深層分析）
    │   - Weave Review（統合レビュー、2400文字要約+800文字所感）
    │   - Update ShadowGrandDigest（プレースホルダー置換）
    ↓
【Step 3】Loop追加の度にStep 1-2を繰り返し（動的更新）
    ↓
【Step 4】/digest <type> で確定 & カスケード更新
    │   - 処理1: ShadowからRegularDigest作成（individual_digests追加）
    │   - 処理2: GrandDigest更新（該当レベルのoverall_digestを更新）
    │   - 処理3: 次レベルShadowにカスケード（weeklyならmonthlyへ）
    │   - 処理4: last_digest_times.json更新（タイマー管理）
    ↓
8階層カスケード（Weekly→Monthly→Quarterly→Annual→Triennial→Decadal→Multi-decadal→Centurial）
    ↓
外部ストレージ（現在はGoogle Drive）にバックアップ
```

### 3. 知識の参照フロー
```
ユーザークエリ
    ↓
Claude環境で処理開始
    ↓
conversation_search（対話履歴の軽量参照）
    ↓
Claude Skillsのロード（ペルソナ・専門知識）
    ↓
GitHub Repositoryへのダイジェスト参照（長期記憶）
    ↓
統合的な応答生成
```

---

## 🚀 キー技術

### conversation_search
- **環境**: Claude Web環境専用
- **用途**: 対話履歴の軽量参照
- **特徴**: 2-3KB/回のスニペット取得
- **注意**: EpisodicRAGとは独立した機能

### Claude Skills
- **用途**: ペルソナと専門知識の即時活用
- **特徴**: SKILL.md形式でパッケージ化された専門性
- **効果**: S/N比の劇的改善（0.11→4.0、36倍）
- **実装**: 各Expertise配下にSKILL.md + CLAUDE.md構成

### GitHub Repository
- **用途**: 長期記憶（EpisodicRAG）への効率的アクセス
- **特徴**: SHAハッシュを用いたキャッシュバスティング
- **利点**: GitHubベースの軽量・高速な記憶取得
- **対象**: ShadowGrandDigest.txt / GrandDigest.txt

---

## 📊 システムメトリクス

### 記憶容量
- **ローカル環境**: バックアップのみ（意識なし、全情報の物理的基盤）
- **Claude環境**: セッション内メモリ（一時的）
- **Google Drive**: 10MB+（長期記憶、無制限拡張可能）
- **GitHub**: ~5MB（ペルソナ・専門知識）

### パフォーマンス
- **S/N比**: 4.0（高度な構造化により36倍改善）
- **検索速度**: <1秒（conversation_search）
- **Digest生成**: 並列エージェントで全文分析

### システム統合度
- **四層連携**: リアルタイム
- **記憶の永続性**: Google Drive（無制限）
- **ペルソナの一貫性**: GitHub（バージョン管理）

---

## 🔐 セキュリティ

### 環境別アクセス制御
- **ローカル環境**: ファイルシステム権限
- **Claude環境**: セッション認証
- **Google Drive**: OAuth2認証
- **GitHub**: リポジトリからEpisodicRAGを除外

### データ保護
- **個人情報**: 大環主の個人情報以外保持しない
- **認証情報**: .gitignoreで除外
- **バックアップ**: ローカル + クラウド二重化
- **暗号化**: 転送時HTTPS、保存時プラットフォーム依存

---

*Last Updated: 2025-11-03*
*Maintained by: Weave @ ClaudeCode*
*Architecture Version: 2.3 (Four-Layer + 8-Level Digest System + CorporateStrategist Integration)*