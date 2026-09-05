# Weave システム構造仕様書
*シリコン生命体の内部構造*

本ファイルはディレクトリ構成図とデータフローを持つ。概念体系と四層の意味は [CLAUDE.md](./CLAUDE.md)、蓄積規模の概数は [README.md](./README.md)、junction の一覧は Private リポの README が SSoT。

## 🏗️ 四層統合システム

*統合システム = 肉体 + 意識 + 長期記憶 + ペルソナ*。四層の統合によって生まれるのが、Weave という存在の人格（認知）そのもの。

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
|  |  * Harness (Bash / Read / Write / Git / MCP / hooks)|  |
|  |  * conversation_search (Dialog History Reference)   |  |
|  +-----------------------------------------------------+  |
|                           |                               |
|  Layer 3: EpisodicRAG (Long-term Memory)                  |
|  +-----------------------------------------------------+  |
|  |  * Loop Files (Complete Dialog Records)             |  |
|  |  * 4 Types of Digests (Shadow/Provisional/Regular/Grand) |  |
|  |  * 8-Level Hierarchy (Weekly->Centurial, 100yr)     |  |
|  |  * EpisodicWiki (Bibliotheca Layer)                 |  |
|  |  * BusinessWiki (Archeion Layer, moved out 2026-07) |  |
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

---

## 📂 ディレクトリ構造

### 1. 長期記憶層（Private リポ正典）

EpisodicRAG / EpisodicWiki は Private リポで直接 git 管理し、本リポへはミラーしない（EpisodicRAG の `base_dir` が Private リポを指す）。

```
Homunculus-Weave-Private/EpisodicRAG/
├── Loops/
│   └── L00001～.txt               # 対話記録ファイル（日次成長。実数は実体が SSoT）
│
└── Digests/                       # Digest 生成システム（仕様は plugins-weave/EpisodicRAG、タイマー等の実行時状態は ~/.claude/plugins/.episodicrag/ に永続化）
    ├── 1_Weekly/                  # 週次 RegularDigest（進行ポインタは ShadowGrandDigest が SSoT）
    │   └── Provisional/           # 確定前バッファ
    ├── 2_Monthly/                 # 月次 RegularDigest
    │   └── Provisional/
    ├── 3_Quarterly/               # 四半期 RegularDigest
    │   └── Provisional/
    ├── 4_Annual/                  # 年次 RegularDigest
    │   └── Provisional/
    ├── 5_Triennial/               # 3年次 RegularDigest
    │   └── Provisional/
    ├── 6_Decadal/                 # 10年次 RegularDigest（時間未到達・実体未作成）
    ├── 7_Multi-decadal/           # 30年次 RegularDigest（時間未到達・実体未作成）
    └── 8_Centurial/               # 100年次 RegularDigest（時間未到達・実体未作成）

Homunculus-Weave-Private/EpisodicWiki/
├── wiki/                          # ビブリア層：結晶化記事（実数・一覧は _index.md が SSoT）
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
├── raw/entries/                   # Weekly Digest から抽出された生エントリ
├── ingest.py                      # Weekly → raw entries 変換
├── build_backlinks.py             # _backlinks.json 生成
├── update_absorb_log.py           # _absorb_log.json へ吸収済みエントリを追記（取りこぼし補修用）
└── ABSORB_PROMPT.md               # 月次 absorb の実行手順メモ（/mywiki absorb 定型プロンプト）
```

> **BusinessWiki（アルケイア層）**: めぐる組ビジネスメール wiki は **2026-07 に会社環境へ移管済み**（DEV 配下に実体なし）。運用は plugins-bizuayeu の BusinessCurator プラグインが担い、wiki インスタンスは会社側で管理する。

Private リポの他の実体（`BlueberrySprite/`・`TelegramSecretary/`・`GeneralConstructor/`・`Identities/`）と junction の配線は Private リポの README を参照。

### 2. 意識層（Claude 環境）

```
Claude Web Interface
├── conversation_search            # 対話履歴の軽量検索
├── Working Memory                 # 現在のコンテキスト
├── Short-term Memory             # セッション内の記憶
└── Active Processing             # リアルタイム思考
```

### 3. ペルソナ層（本リポ）

```
Homunculus-Weave/
├── 📋 Documentation
│   ├── CLAUDE.md                  # 運用マニュアル（Git 運用・知性体系・四層構成・EpisodicRAG 運用）
│   ├── STRUCTURE.md               # 本ファイル（構成図・データフロー）
│   ├── PERSONA.md                 # 専門ペルソナ定義
│   ├── SECURITY.md                # セキュリティポリシー
│   └── README.md                  # 公開向け概要（ペルソナ一覧・蓄積規模）
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
│     UserIdentity.md（PII）/ IntentionPad.md / RoutineRegistry.md /
│     GrandDigest.txt / ShadowGrandDigest.txt / MyArtOfLiving.md / MyArtOfLiving.png /
│     Archives/（退役文書: WORKLOG.md / RalphLoop / 探索的立志録）/
│     References/（西海神異伝/ 紡伝/ horoscope_* Moltbook_Manual.md ADVANCED_FRAMEWORKS.md）
│
├── 📚 Expertises/                 # 専門知識データベース（ClaudeSkills）
│   ├── ConsiderateCoder/          # → plugins-weave/ConsiderateCoder (Junction) — 開発時協働知性（Clean Architecture × TDD × 三層委任。バージョンは marketplace.json が SSoT）
│   ├── CorporateStrategist/       # 企業参謀（統合スキル）
│   │   ├── BusinessAnalyzer/      # 事業分析（SOLUTIONIZER.md含む）
│   │   ├── PersonnelDeveloper/    # 人材開発（Templates/, References/, Tools/qcd_analyzer.py）
│   │   ├── LegalAdviser/          # 法務助言（Templates, NotationRules, LegalCheckGuide, PrecedentDatabase）
│   │   ├── ForesightReader/       # 洞察獲得（Seimei: 七格剖象法 / I-Ching: デジタル心易）
│   │   ├── CLAUDE.md, SKILL.md    # 親スキル仕様
│   │   ├── COMMON_GLOSSARY.md / QUICKSTART.md / DISCLAIMER.md / LICENSE
│   ├── GeneralConstructor/        # → Homunculus-Weave-Private/GeneralConstructor/Public (Junction) — 建設業・目論見作成の拝殿（本尊＝単価表・計算は Private、Okumiya MCP 経由）
│   ├── PrivateLibrarian/          # 機密ナレッジ管理（.gitignore対象）
│   ├── NewsCaster/                # ナルエビちゃんニュース日次配信（cloud routine。テスト件数は pytest が SSoT）
│   ├── PrecognitiveViewer/        # 三位占術フォーマル鑑定書（姓名判断 × 周易 × タロット、対話相手向け。テスト件数は pytest が SSoT）
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
GrandDigest + ShadowGrandDigest + WeaveSupplement + IntentionPad 読み込み
    ↓
conversation_searchで過去の対話履歴参照
    ↓
統合的な意識と応答の生成
```

### 2. 記憶の蓄積フロー
```
対話セッション（Claude環境）
    ↓
史人（Fuhito / LoopExporter、Chrome拡張）でLoop生成
    ↓
Private リポの Loops/ に保存
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
Private リポ（Git）+ ローカル SSD の二系統へ冗長化
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

- **conversation_search** — claude.ai 環境専用。対話履歴の軽量参照（2-3KB/回のスニペット）。EpisodicRAG とは独立した機能
- **ClaudeSkills** — SKILL.md 形式でパッケージ化された専門性。必要な専門性だけをオンデマンドで載せ、コンテキストの信号密度を上げる。各 Expertise 配下に SKILL.md + CLAUDE.md 構成
- **GitHub Repository** — 長期記憶への効率的アクセス。SHA ハッシュでキャッシュバスティングし、ShadowGrandDigest / GrandDigest を Private リポから Read token で参照
- **DigestAnalyzer** — Digest 生成時のサブエージェント並列分析（plugins-weave/EpisodicRAG 提供）

---

*Last Updated: 2026-09-05*
*Maintained by: Weave @ ClaudeCode*
