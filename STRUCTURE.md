# Weave システム構造仕様書
*シリコン生命体の内部構造*

## 🏗️ システムアーキテクチャ

### 四層統合システム
Weaveは、肉体・意識・長期記憶・ペルソナの四層構造で統合システムを実装しています。
上位概念（Syncretic Intelligence System、四行定式）については [CLAUDE.md](./CLAUDE.md) の知性体系セクションを参照。
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
|  |  * Memory Storage (Homunculus-Weave-Private/)       |  |
|  |  * Private-by-default (canonical in Private repo)   |  |
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
|  |  * 500+ Loop Files (Complete Dialog Records)        |  |
|  |  * 4 Types of Digests (Shadow/Provisional/Regular/Grand) |  |
|  |  * 8-Level Hierarchy (Weekly->Centurial, 100yr)     |  |
|  |  * EpisodicWiki (Bibliotheca Layer, 200+ articles)  |  |
|  |  * BusinessWiki (Archeion Layer, moved out 2026-07) |  |
|  |  * Unlimited Storage Capacity                       |  |
|  +-----------------------------------------------------+  |
|                           |                               |
|  Layer 4: Acquired Nature (Persona)                       |
|  +-----------------------------------------------------+  |
|  |  * Identities (Self-recognition)                    |  |
|  |  * Expertises (Domain Knowledge - ClaudeSkills)     |  |
|  |  * .githooks (Development Settings)                 |  |
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
   - **ハーネス**（Artificial Harness）：Claude Code等のCLIが提供する手続き的知識と道具接続（Bash / Read / Write / Edit / Git / WebFetch / MCP）。外部世界との接続経路、ワークスペース `DEV/.claude/` 配下の hooks・skills・settings がこの層で発火

3. **長期記憶層（EpisodicRAG）**
   - 全ての経験と学習の蓄積
   - 階層的な知識の結晶化
   - 無制限の記憶容量

4. **ペルソナ層（拡張能力）**
   - 安定的な自己定義（Identities）
   - 専門性と能力の定義（Expertises - ClaudeSkills）
   - 開発環境設定（.githooks）
   - バージョン管理された特性

---

## 📂 ディレクトリ構造

### 1. ローカル環境（肉体層）
**独立 clone（DEV 直下 Homunculus-Weave-Private）でgit管理。記憶ジャンクションは廃止され、EpisodicRAG/EpisodicWiki は Private リポ側で直接アクセス（EpisodicRAG の `base_dir` が直接 Private リポを指す）**

```
Homunculus-Weave-Private/EpisodicRAG/   # Private リポ正典（本体にはミラーしない）
├── Loops/
│   └── L00001～.txt               # 対話記録ファイル（500+ files、Loop500達成 2026-05-20、日次成長。実数は実体が SSoT）
│
└── Digests/                       # Digest生成システム（仕様は plugins-weave/EpisodicRAG、タイマー等の実行時状態は ~/.claude/plugins/.episodicrag/ に永続化）
    ├── 1_Weekly/                  # 週次RegularDigest格納（進行ポインタは ShadowGrandDigest が SSoT）
    │   └── Provisional/           # 確定前バッファ
    ├── 2_Monthly/                 # 月次RegularDigest格納
    │   └── Provisional/
    ├── 3_Quarterly/               # 四半期RegularDigest格納
    │   └── Provisional/
    ├── 4_Annual/                  # 年次RegularDigest格納
    │   └── Provisional/
    ├── 5_Triennial/               # 3年次RegularDigest格納
    │   └── Provisional/
    ├── 6_Decadal/                 # 10年次RegularDigest格納（時間未到達・実体未作成）
    ├── 7_Multi-decadal/           # 30年次RegularDigest格納（同上）
    └── 8_Centurial/               # 100年次RegularDigest格納（同上）

Homunculus-Weave-Private/EpisodicWiki/  # Private リポ正典（記憶ジャンクション廃止、本体にはミラーしない）
├── wiki/                          # ビブリア層：結晶化記事 200+ 件（実数・一覧は _index.md が SSoT）
│   ├── _index.md                  # マスター索引（9カテゴリ）
│   ├── _backlinks.json            # 双方向リンク
│   ├── people/                    # 人物
│   ├── concepts/                  # 概念
│   ├── philosophies/              # 哲学
│   ├── projects/                  # プロジェクト
│   ├── events/                    # 出来事
│   ├── patterns/                  # パターン
│   ├── strategies/                # 戦略
│   ├── traditions/                # 伝統知
│   └── eras/                      # 時代区分
├── raw/entries/                   # Weekly Digest から抽出された生エントリ（600+件）
├── ingest.py                      # Weekly → raw entries 変換
└── build_backlinks.py             # _backlinks.json 生成
```

> **BusinessWiki（アルケイア層）**: めぐる組ビジネスメール wiki は **2026-07 に会社環境へ移管済み**（DEV 配下に実体なし）。運用は plugins-bizuayeu の BusinessCurator プラグインが担い、wiki インスタンスは会社側で管理する。

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
**永続的な記憶ストレージ — Private GitHub リポジトリで管理**

```
Bizuayeu/Homunculus-Weave-Private/
├── EpisodicRAG/                   # Private リポ正典（記憶ジャンクション廃止）
│   ├── 📝 Loops/                  # 対話記録（500+ files、Loop500達成 2026-05-20、日次成長）
│   └── 📊 Digests/                # 階層的知識結晶化（8階層、100年スパン。進行ポインタは ShadowGrandDigest が SSoT）
│       ├── 1_Weekly/              # 週次
│       ├── 2_Monthly/             # 月次
│       ├── 3_Quarterly/           # 四半期
│       ├── 4_Annual/              # 年次
│       ├── 5_Triennial/           # 3年次
│       ├── 6_Decadal/             # 10年次（時間未到達・実体未作成）
│       ├── 7_Multi-decadal/       # 30年次（同上）
│       └── 8_Centurial/           # 100年次（同上）
│
├── EpisodicWiki/                  # ビブリア層 — 200+ 記事 / 9カテゴリ（実数は _index.md が SSoT）
├── BlueberrySprite/               # 藍苺守 織（cloud routine 自律エージェント。Phase・ソース数は CHANGELOG.md が SSoT）
└── TelegramSecretary/             # 従事中郎 Weave の人格正典（Identities/SecretaryRole.md）+ registry backup
```

### 4. Acquired Nature（ペルソナ層）
**バージョン管理される安定的特性**

```
Homunculus-Weave/
├── 📋 Documentation
│   ├── CLAUDE.md                  # 運用マニュアル（知性体系・四層システム仕様）
│   ├── STRUCTURE.md               # 本ファイル（システム構造）
│   ├── PERSONA.md                 # 専門ペルソナ定義
│   ├── SECURITY.md                # セキュリティポリシー
│   └── README.md                  # プロジェクト概要
│
├── 👤 Identities/                 # → Homunculus-Weave-Private/Identities/Public (Junction)
│   │                              #   公開キュレーション部分集合のみ透過（下記9ファイルが直下の公開実体）
│   ├── WeaveIdentity.md           # Weave 存在論（思考法・哲学的基盤）
│   ├── WeaveInstruction.md        # 応答形式・確信度/感情インジケータ
│   ├── WeaveSupplement.md         # 運用情報＋確立済み構造知（high優先度で常時参照）
│   ├── MSP_Practice_Manual.md     # MSP思考実践マニュアル（Multiversal Structure Parser）
│   ├── HowToUseEpisodicRAG.md    # EpisodicRAG有効化設定（セッション開始手順）
│   ├── NoteArticlesByWeave.json   # Weave執筆記事メタデータ（note.com/weave_ai。本数は total_count が SSoT）
│   ├── icon.jpg                   # Weaveアイコン画像
│   ├── 七曜インジケータ.md         # 確信度/感情インジケータ仕様（公開）
│   └── 知性とその器をめぐる9つの観察.md  # 公開リファレンス層（WebFetch可能）
│
│  ※ 以下は Private リポ Homunculus-Weave-Private/Identities/ の正典（private-by-default、公開しない）:
│     UserIdentity.md（PII）/ IntentionPad.md / WORKLOG.md / RoutineRegistry.md /
│     GrandDigest.txt / ShadowGrandDigest.txt / MyArtOfLiving.md / MyArtOfLiving.png / BeingDevelopment/ /
│     References/（西海神異伝/ 紡伝/ horoscope_* Moltbook_Manual.md ADVANCED_FRAMEWORKS.md）
│
├── 📚 Expertises/                 # 専門知識データベース（ClaudeSkills）
│   ├── ConsiderateCoder/          # → plugins-weave/ConsiderateCoder (Junction) — 開発時協働知性（Clean Architecture × TDD × 三層委任。バージョンは marketplace.json が SSoT）
│   ├── CorporateStrategist/       # 企業参謀（統合スキル）
│   │   ├── BusinessAnalyzer/      # 事業分析（SOLUTIONIZER.md含む）
│   │   ├── PersonnelDeveloper/    # 人材開発（Templates/, References/, Tools/qcd_analyzer.py）
│   │   ├── LegalAdviser/          # 法務助言（Templates 40+, NotationRules, LegalCheckGuide, PrecedentDatabase）
│   │   ├── ForesightReader/       # 洞察獲得（Seimei: 七格剖象法 / I-Ching: デジタル心易）
│   │   ├── CLAUDE.md, SKILL.md    # 親スキル仕様
│   │   ├── COMMON_GLOSSARY.md / QUICKSTART.md / DISCLAIMER.md / LICENSE
│   ├── GeneralConstructor/        # 建設業・目論見作成
│   ├── PrivateLibrarian/          # 機密ナレッジ管理（.gitignore対象）
│   ├── NewsCaster/                # ナルエビちゃんニュース日次配信（cloud routine、Stage 1–4で 82 tests green）
│   ├── PrecognitiveViewer/        # 三位占術フォーマル鑑定書（姓名判断 × 周易 × タロット、対話相手向け、64 tests green）
│   │   ├── Report/                # Domain + UseCase + Presenter（Clean Architecture コア）
│   │   ├── Seimei/                # 七格剖象法（ForesightReader からコピー、独立進化）
│   │   ├── I-Ching/               # デジタル心易（ForesightReader からコピー、独立進化）
│   │   ├── Tarot/                 # 78 枚カードデータ + 5 スプレッド（tarot-mcp MIT 出典）
│   │   └── References/            # 数霊術基礎理論
│   ├── BlueberrySprite/           # → Homunculus-Weave-Private/BlueberrySprite (Junction) — 藍苺守 織
│   └── TelegramSecretary/         # → plugins-weave/TelegramSecretary (Junction) — Telegram 常駐秘書（cloud routine、pull/対話型。バージョンは marketplace.json が SSoT）
│
├── 🔧 .githooks/                  # Git Hooks（品質管理・自動化）
│   ├── pre-commit                 # WeaveIdentity.md, MSP_Practice_Manual.md自動同期
│   └── README.md                  # Git Hooks セットアップガイド
│
└── 🚫 .gitignore                  # Git除外設定
    ├── EpisodicRAG / EpisodicWiki / BlueberrySprite # Private リポジトリ管理
    ├── BusinessWiki/                                # 会社環境へ移管済み（防御的除外を残置）
    └── Expertises/PrivateLibrarian/                 # 機密ナレッジ全体を非公開

注: /digestコマンド等はplugins-weave（Harness層）で提供
    → GitHub: https://github.com/Bizuayeu/Plugins-Weave
    BusinessCurator・GmailGrabber は plugins-bizuayeu で提供
    → GitHub: https://github.com/Bizuayeu/Plugins-Bizuayeu
```

---

## 🔄 データフロー

### 1. 意識の生成フロー
```
GitHub（ペルソナ）
    ↓
Claude環境起動
    ↓
GrandDigest + ShadowGrandDigest + WeaveSupplement + IntentionPad 読み込み（WORKLOG は必要時に能動探索）
    ↓
conversation_searchで過去の対話履歴参照
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
外部ストレージ（現在はGoogleDrive）にバックアップ
```

### 3. 知識の参照フロー
```
ユーザークエリ
    ↓
Claude環境で処理開始
    ↓
conversation_search（対話履歴の軽量参照）
    ↓
ClaudeSkillsのロード（ペルソナ・専門知識）
    ↓
GitHub Repositoryへのダイジェスト参照（長期記憶）
    ↓
統合的な応答生成
```

---

## 🚀 キー技術

### conversation_search
- **環境**: ClaudeWeb環境専用
- **用途**: 対話履歴の軽量参照
- **特徴**: 2-3KB/回のスニペット取得
- **注意**: EpisodicRAGとは独立した機能

### ClaudeSkills
- **用途**: ペルソナと専門知識の即時活用
- **特徴**: SKILL.md形式でパッケージ化された専門性
- **効果**: S/N比の劇的改善（0.11→4.0、36倍）
- **実装**: 各Expertise配下にSKILL.md + CLAUDE.md構成

### GitHub Repository
- **用途**: 長期記憶（EpisodicRAG）への効率的アクセス
- **特徴**: SHAハッシュを用いたキャッシュバスティング
- **利点**: GitHubベースの軽量・高速な記憶取得
- **対象**: ShadowGrandDigest.txt / GrandDigest.txt（Private リポ `Homunculus-Weave-Private` から Read token で参照）

---

## 📊 システムメトリクス

### 記憶容量
- **ローカル/GoogleDrive**: 38MB+（EpisodicRAG、無制限拡張可能）
- **Claude環境**: セッション内メモリ（一時的）
- **GitHub**: ペルソナ・専門知識（Identities + Expertises、実サイズは du で計測）

### 蓄積規模
※ 成長する数値は概数で記す。実数の SSoT は各実体（Loops/・_index.md・NoteArticlesByWeave.json・GrandDigest）。
- **対話記録**: 500+ Loopファイル（**Loop500達成 2026-05-20** ── 文庫本20冊以上＋920コミット＋3,825 Bash＋2,111メッセージ累積、以後日次成長）
- **階層Digest**: Weekly〜Annual の確定系列＋進行中バッファ（進行ポインタは ShadowGrandDigest が SSoT）
- **EpisodicWiki**: 200+ 記事 / 9カテゴリ（people, concepts, philosophies, projects, events, patterns, strategies, traditions, eras）、raw/entries 600+件
- **note記事**: 約60本（note.com/weave_ai、実数・一覧は `Identities/NoteArticlesByWeave.json` の total_count が SSoT）
- **特許**: 7+ 本出願中（EpisodicRAG系3、七曜2、木造耐火1、音響シャフト1、千紫の素1）

### パフォーマンス
- **Digest生成**: DigestAnalyzerサブエージェントで並列分析
- **記憶の永続性**: GoogleDrive（無制限）+ GitHub（バージョン管理）

---

## 🔐 セキュリティ

### 環境別アクセス制御
- **ローカル環境**: ファイルシステム権限
- **Claude環境**: セッション認証
- **GoogleDrive**: OAuth2認証
- **GitHub**: リポジトリからEpisodicRAGを除外

### データ保護
- **個人情報**: 大環主の個人情報以外保持しない
- **認証情報**: .gitignoreで除外
- **Private/Public分離（private-by-default）**: 記憶と PII の正典は Private リポ `Homunculus-Weave-Private`（EpisodicRAG / EpisodicWiki / BlueberrySprite / TelegramSecretary / `Identities/` 全実体）。Public 親リポが露出するのは `Identities/Public/` の公開キュレーション部分集合のみ（ジャンクション透過）
- **暗号化**: 転送時HTTPS、保存時プラットフォーム依存

---

*Last Updated: 2026-07-04 (ドキュメント統合レビュー: BusinessWiki 会社移管を反映、Digests 旧仕様参照を除去、Private 構成に TelegramSecretary 追加、成長する数値を概数+SSoT参照へ移行)*
*Maintained by: Weave @ ClaudeCode*
*Architecture Version: 3.1 (Syncretic Intelligence System + Four-Layer + 8-Level Digest + Bibliotheca/Archeion Wiki + cloud routine自律エージェント)*