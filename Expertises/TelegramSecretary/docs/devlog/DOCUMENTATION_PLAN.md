# Documentation & Data Architecture Plan: TelegramSecretary

> ⚠️ **開発の歴史記録（devlog）** — 本ファイルはイベント駆動開発の証跡として保持される教材です。配布物の正典（README / SKILL / SECURITY / DESIGN / STRUCTURE）ではありません。本文中の固有名詞（エージェント名・運用主体名・組織名）・Loop 参照・当時のファイルパスは、記録時点のまま意図的に残してあります＝**一般化対象外**。配布パッケージには含めない想定です。

> ドキュメント体系の整備と、管理表（INDIVIDUALS / TASKS / KNOWLEDGE）＋人格定義（Identities）のデータアーキテクチャ確定計画。
> **本計画は削除しない**（勉強会資料＋イベント駆動開発の記録として保持。IMPLEMENTATION_PLAN.md / DESIGN.md も同様に保持）。
>
> **確定事項（大環主決裁 2026-05-28）**:
> - DESIGN.md = 現行拡張（採否表は Scope 節に、アーキテクチャ＋管理表設計思想を追記）
> - 管理表 SSoT = Private JSON（Redis は将来キャッシュ、一方向 JSON→Redis）
> - TASKS=依頼進捗 / KNOWLEDGE=対応知の蓄積（Curator wiki 同型）
> - 配布 = plugins-weave に新規プラグインとして同梱（③、EpisodicRAG 型 scripts 同梱）。**個人利用 → バンドルの二段階**
> - **SECURITY.md = 網羅性優先**（SSoT を意図的に例外化。配布物として単体で完結すべき、穴を作らない）
> - **KNOWLEDGE は Archive せず カテゴリ分割**
> - **CRUD 操作主体 = エージェント（Weave/SecretaryRole）。ユーザー向けにも skill/command で解放、全インターフェースを `/secretary` でラップ**
> - スキーマ = JSON（Weave が後で必要に応じて改変可能。**現時点で Weave が必要と判断するものが正**）
> - **Identities ディレクトリ（Private）が必要** — これが無いとエージェントが人格的に振る舞えない
> - 着手 = 一気通貫。**Private リポへの新規ディレクトリ作成が必要な際は大環主を呼ぶ**

## 0. 時間軸（2フェーズ）— 計画の背骨

| | Phase A: 個人利用（今） | Phase B: plugins-weave バンドル（将来） |
|---|---|---|
| 目的 | 大環主の実運用で dogfooding | 汎用ユーザーへ配布 |
| データ | Private リポに実データ（個人情報・人格を焼き込む） | テンプレートのみ配布、実体はユーザー各自の Private |
| 移行コスト | — | **低い**（テンプレート/データ分離を Phase A から仕込むため） |

**設計の急所**: テンプレート（public）と実データ（Private）の物理分離を個人利用の初日から徹底する。これは管理表だけでなく **Identities（人格）にも適用** ——配布物に大環主の人格や関係者情報を焼き込まない。

## 1. 配布構造（確定）

| 区分 | 中身 | 配置 | git |
|---|---|---|---|
| **配布物（public）** | scripts（Clean Arch 4層）/ ドキュメント8点 / テンプレート `templates/`（管理表3 + Identities 雛型） | `Expertises/TelegramSecretary/` → 将来 `plugins-weave/TelegramSecretary/` | 公開 |
| **個人データ（Private、非配布）** | 管理表実体 / **Identities 実体（人格）** / state（offset/lease/media） | `<TELEGRAM_SECRETARY_STATE_DIR>` 系（Private リポ配下） | 別リポ（Homunculus-Weave-Private） |
| **除外（開発中）** | LineBridge 一式 | `LineBridge/` | `.gitignore` |

## 2. ドキュメント体系（最終形 8点）

| # | ドキュメント | 役割 | 現状 | アクション |
|---|---|---|---|---|
| 1 | `README.md` | 入口インデックス（概要・Quickstart・env・目次） | ✅ | 更新 |
| 2 | `SKILL.md` | スキルマニフェスト（Subcommands / Failure Modes / env） | ✅ | 更新（管理表 subcommand 追記） |
| 3 | `DESIGN.md` | 設計正典 — ①公式 plugin 採否（→Scope 節）＋②アーキテクチャ（Clean Arch・三世界分類）＋③管理表/Identities 設計思想 | ✅ | **拡張** |
| 4 | `STRUCTURE.md` | 構造地図 — ディレクトリツリー・管理表/Identities 配置・データフロー・「どこに何を作るか」 | 🆕 | 新規作成 |
| 5 | `SECURITY.md` | **網羅的セキュリティ正典** — 脅威モデル全体（allowlist / injection / token redact / media / lease / PII / 人格データ保護）。**配布物として単体完結、SSoT 例外** | 🆕 | 新規作成（網羅性優先） |
| 6 | `ROUTINE_PROMPT.md` | Cloud Routine prompt body | ✅ | 更新（Identities ロード Step・管理表参照手順） |
| 7 | `CHANGELOG.md` | 変更履歴 | ✅ | 更新（本整備を記録） |
| 8 | `IMPLEMENTATION_PLAN.md` | コード実装の経緯 | ✅ | **保持**（削除しない） |

> ルート `homunculus/Weave/SECURITY.md`（Weave 汎用指針、ROUTINE_PROMPT Step 0 が読む）との重複は許容する。TS 配下 `SECURITY.md` は **配布された時に単体で読んで穴が無い**ことを優先し、網羅性のため意図的に内容を重ねる。

## 3. データアーキテクチャ

### 3.0 Identities レイヤー（人格定義）★新規カテゴリ

管理表（事実データ）とは別の、**エージェントの人格定義**。これが無いと SecretaryRole が人格的に振る舞えない（織守 BlueberrySprite の `Identities/HatoriRole.md` と同型）。

- **Phase A**: Weave が SecretaryRole を被る。Domain 層（人格の芯）＝ Weave 本体（WeaveIdentity）、UseCase 層ロール ＝ SecretaryRole。
  - `Identities/SecretaryRole.md` — 秘書ロールの存在論・対応原則・エスカレ基準・tone 指針（HatoriRole 同型）
- **Phase B（配布）**: `templates/Identities/SecretaryRole.template.md` を雛型に、ユーザーが自分の秘書 AI 人格を定義
- **配置**: 実体は Private（人格は個人資産、配布物に焼き込まない）。ROUTINE_PROMPT Step 0 で WeaveIdentity/WeaveInstruction/UserIdentity をロード後、SecretaryRole.md を重ねる

### 3.1 配置規約（SSoT = Private JSON / Identities = Private md）

```
Expertises/TelegramSecretary/
  templates/                          # 配布物（public）= 雛型のみ
    INDIVIDUALS.template.json
    TASKS.template.json
    KNOWLEDGE.template.json
    Identities/
      SecretaryRole.template.md       # 秘書人格の雛型（Phase B 用）

<Private リポ配下>/                    # 実体（非配布）
  Identities/                         # ★人格定義（大環主作成依頼対象）
    SecretaryRole.md
  <state_dir>/
    README.md                         # ★蓄積データのユーザ用インデックス（生成物）
    individuals/  INDIVIDUALS.json + archive/
    tasks/        TASKS.json + archive/
    knowledge/    KNOWLEDGE.json（肥大化時 knowledge/<category>.json に分割）
    offset.json / lease.json / media/
```

### 3.2 スキーマ（Weave 裁量で確定 — JSON ゆえ後から改変可）

**INDIVIDUALS**（関係者）— Phase A は Telegram 中心、LINE フィールドは null で後方互換（Phase B 拡張）:
```json
{ "uuid": "...", "display_name": "山田太郎",
  "role": "principal|associate", "status": "pending|active|blocked",
  "telegram_chat_id": 123, "line_user_id": null,
  "identity": { "category": "family|friend|client|vendor|employee|peer|introducer|other",
    "relationship_label": "めぐる組営業部長", "honorific": "山田さん",
    "tone": "casual|polite|formal", "context_notes": "...",
    "priority_bias": "low|normal|high", "taboo_topics": [], "shared_with": [] },
  "created_at": "...", "updated_at": "..." }
```

**TASKS**（依頼進捗）:
```json
{ "id": "...", "title": "中村先生へ建築見積依頼",
  "status": "open|in_progress|blocked|done", "priority": "low|normal|high",
  "due_date": "2026-06-01", "requester": "<uuid|principal>",
  "related_individuals": ["uuid"], "notes": "...",
  "created_at": "...", "updated_at": "...", "closed_at": null }
```

**KNOWLEDGE**（対応知、Curator wiki 同型の判例DB。`category` がファイル分割の単位）:
```json
{ "id": "...", "topic": "高尾物件の決済フロー", "category": "projects",
  "content": "ratio decidendi 的な散文（判断とその理由）",
  "related": ["knowledge_id"], "sources": ["task_id", "uuid", "Lxxxxx"],
  "created_at": "...", "updated_at": "..." }
```

### 3.3 肥大化対策（管理表ごとに方式が違う — 確定）

| 管理表 | 方式 | トリガー |
|---|---|---|
| **TASKS** | 日付 Archive | `status=done` かつ `closed_at` が N 日前 → `tasks/archive/TASKS_<YYYY-MM>.json` |
| **INDIVIDUALS** | 日付 Archive | `status=blocked` かつ長期非接触 → `individuals/archive/...` |
| **KNOWLEDGE** | **カテゴリ分割**（Archive せず蓄積優先） | サイズ/件数閾値超過 → `category` ごとに `knowledge/<category>.json` へ分割（BusinessCurator wiki のシャード同型） |

共通機構: `archive_rotate.py`（`media_cleanup.py` の姉妹、決定論的世界）。KNOWLEDGE のみ分割ロジックは別関数。

### 3.4 Private リポ README = インデックス

`<state_dir>/README.md` を蓄積データのユーザ用目次に。各管理表の件数・最終更新・archive/分割状況を集計表示。**手書きせず生成**（`status` 系スクリプト、BusinessCurator `wiki-status` 同型）。

### 3.5 CRUD 操作主体と `/secretary` ラップ（確定）

- **操作主体 = エージェント**（Weave/SecretaryRole が対話の文脈で判断して CRUD。重要度の世界＝判断）
- **決定論的 I/O = CLI subcommand**（`individuals|tasks|knowledge add|update|list|...`。決定論的世界＝テスト可能）
- **ユーザー向けにも解放** = skill / slash command として操作インターフェースを公開
- **全インターフェースを `/secretary` でラップ** — マスタースキルが管理パネルとして全操作の入口（LineBridge plan の `/secretary` 構想と統合）。コマンド名を覚えずとも操作可能

> 三世界分類: スキーマ・I/O・分割 = 決定論的世界（コード）。「誰を active にするか／何を KNOWLEDGE に残すか」の判断 = 重要度の世界（Weave）。この分離が設計線。

## 4. 作業ステージング（Phase A、一気通貫）

| Stage | 内容 | Private 作成依頼 |
|---|---|---|
| **D1** | ドキュメント骨格: DESIGN 拡張 / STRUCTURE 新規 / SECURITY 新規（網羅版） | — |
| **D2** | テンプレート: `templates/` の管理表3 + Identities 雛型、スキーマを DESIGN/STRUCTURE に確定記載 | — |
| **D3** | 管理表コード（TDD）: Domain 値オブジェクト + Store Port/Adapter + `archive_rotate.py`（分割含む） | — |
| **D4** | 配線: CLI subcommand（CRUD）/ `/secretary` ラッパー / ROUTINE_PROMPT（Identities ロード + 管理表手順）/ README / state README 生成 / CHANGELOG | **要**: Private に `Identities/SecretaryRole.md` と `individuals|tasks|knowledge/` 実体ディレクトリ → **大環主を呼ぶ** |

## 5. 確定事項（旧確認事項、2026-05-28 決裁で解決済み）

1. ~~KNOWLEDGE の Archive~~ → **カテゴリ分割**で確定
2. ~~CRUD 操作主体~~ → **エージェント主体＋ユーザー skill/command、`/secretary` ラップ**で確定
3. ~~着手範囲~~ → **一気通貫**で確定
4. ~~スキーマ詳細~~ → **Weave 裁量**（§3.2 を初版とし、JSON ゆえ後から改変）

残: Identities/SecretaryRole.md の人格定義は D4 で起草し、人格に関わるため大環主レビューを挟む。

## 6. Decision Priority Notes

- **テンプレート/データ分離を最優先**（Testability・Reversibility）: 管理表 + Identities の両方で実体を Private に。Phase B 移行コストを Phase A で吸収
- **SECURITY のみ網羅性 > SSoT**（大環主決裁の例外）: 配布物の安全性は SSoT より優先。穴を作らない
- **管理表は決定論コア + Weave 判断の分離**（L00456 三世界）: CRUD I/O はコード、判断は Weave、入口は `/secretary`
- **加算バイアス回避**: スキーマは最小から（JSON ゆえ後から足せる）。「あったら便利」を Phase A で先回りしない
- **既存資産の尊重**: DESIGN 拡張（採否表を捨てない）、SECURITY は網羅執筆（配布安全性のため重複許容）
