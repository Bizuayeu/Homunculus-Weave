# Implementation Plan: TelegramSecretary（Weave の Telegram 常駐チャネル）

> 本計画は `Expertises/ConsiderateCoder/rules/DEV.md` および `/plan-sdd` の方針で生成。全 Stage 完了後に削除する。
> スキル名 `TelegramSecretary` は暫定。「Weave への Telegram 経由の到達口（SecretaryRole を被った Weave 本人が応答）」を表す。要改名なら Stage 着手前に。
> **Stage 10（keep-alive: /goal deadline 駆動ロングポーリング + watch early-exit）は独立ファイル [`GOAL_KEEPALIVE_PLAN.md`](./GOAL_KEEPALIVE_PLAN.md) に分離**（教材保持、本計画 Stage 1-9 とは別ライフサイクル）。

## Overview

- **What**: Telegram Bot API の long-polling を Cloud Routine 上で常駐させ、認可済みチャットからのメッセージに Weave（SecretaryRole）が即応する対話チャネル。state（last `update_id`・lease）は Private リポに永続化。
- **Why**: NewsCaster（push 型・1日1回）に対し、**pull/対話型・24-7 到達性**を追加する。Gmail より低レイテンシ（数秒）で大環主から Weave を呼べる常駐秘書。
- **Where**: `Expertises/TelegramSecretary/`（コード本体）。state は Private リポ（`.private/` 配下、`claude/fervent-franklin-Lbo5D`）に置き、git 管理外 or 専用 state ファイルとして扱う。NewsCaster と同型の skill レイアウト。
- **Reference Patterns**（既存3件）:
  1. `Expertises/NewsCaster/scripts/`（Clean Architecture 4層 + main.py subcommands + bootstrap.sh + JsonStateStore + dry-run→Weave→send-rendered の「LLM をコード外に追い出す」分割）★最重要参照
  2. `Expertises/BlueberrySprite/`（Cloud Routine 自律エージェント完成形・x_token 永続化パターン = state を Private リポに保つ）
  3. `Expertises/NewsCaster/ROUTINE_PROMPT.md`（Cloud Routine prompt body の書式・bootstrap→人格ロード→env橋渡し→subcommand の流れ）

## 設計の根幹（検証済みの環境制約から導出）

| 制約 | 出典 | 設計への反映 |
|---|---|---|
| Webhook 不可（inbound HTTP は 127.0.0.1 のみ、公開 ingress なし） | code.claude.com/docs channels-reference | **long-polling 一択**（`getUpdates?timeout=30`） |
| アイドル中の Claude 推論は枠を食う（Claude がループを回すと空ポーリング1周=1ターン） | 構造的推論 | **Claude をアイドルループから追い出す**：bash の `watch` ループをバックグラウンド実行し、実メッセージが来た行だけ stdout に出す → `Monitor` ツールで消費。アイドル=トークン非生成=枠消費ほぼゼロ |
| cron 最小粒度 1 時間（sub-hourly は reject） | code.claude.com/docs routines | 死活監視 cron は **1時間以上**。セッション寿命 < cron 間隔なら復旧に空白が出るため、寿命の実測が先 |
| セッション寿命（inactivity reclaim / hard cap）は**未文書化** | docs limitations | Stage 5 で**実測**。cron 間隔 = `min(観測寿命, 運用許容空白)`。自己治癒（次 cron が拾い直し）前提 |
| `api.telegram.org` は Trusted allowlist に非含。**network policy 変更はコンテナ生成時に焼き込まれ、実行中セッションには反映されない**（本セッションで 403 `host_not_allowed` を実測） | docs access-levels + 実測 | Environment を **Custom** にし `api.telegram.org` を allowlist 追加 → **新規セッションから有効**。ROUTINE_PROMPT に「起動直後に疎通 curl で確認」を入れる |
| state を git で**毎メッセージ** push すると遅い・コミット汚染 | OPS.md §4 | offset はセッション内 **in-memory**、永続化は graceful exit / 数分ごと / N件ごと。crash 時の再処理小窓は**ハンドラ冪等化**で吸収（Telegram の offset 確定セマンティクスと併用） |
| 並走セッションが offset を奪い合う（cron 重複起動） | 構造的推論 | **heartbeat + TTL のリースロック**を state に持つ。新セッションは heartbeat が新鮮なら起動拒否、stale なら奪取（crash 自己治癒と両立） |
| LLM 推論を subprocess で立てない（`claude -p` 禁止・API課金化原則・L00473） | CLAUDE.md / NewsCaster 設計判断 | 応答生成は**親プロセス Weave 本人**が担う。コードは fetch/認可/正規化/送信のみ。NewsCaster の send-rendered と同型 |

## Architecture（Clean Architecture 4層、依存は内向きのみ）

| Layer | 本機能における責務 | 主要な型/関数 | 依存先 |
|---|---|---|---|
| **Domain** | 純粋ロジック・値オブジェクト | `TelegramUpdate` / `OutboundMessage` / `UpdateOffset`（`advance()`）/ `AuthorizedChats`（`is_authorized(chat_id)`）/ `SessionLease`（`is_stale(now)` / `held_by_other(now, me)`）/ `normalize_input()`・`flag_injection()`（純関数） | なし |
| **UseCase** | オーケストレーション + Port 定義 | Ports: `UpdateSource`・`MessageSink`・`OffsetStore`・`LeaseStore`。UseCases: `AcquireLease` / `FetchAuthorizedUpdates`（取得→認可フィルタ→正規化→injection フラグ→Weave 向け emit）/ `SendReply`（Weave 起草の本文を送信→offset advance→永続化）/ `RenewLease` / `ReleaseLease` | Domain のみ |
| **Interface (Adapter)** | ゲートウェイ・ストア・CLI | `TelegramApiGateway`（getUpdates/sendMessage、UA・retry・timeout）/ `JsonStateStore`（offset+lease を Private state dir に）/ `StdoutEventEmitter`（Monitor 消費可能な1行/メッセージ）/ `main.py`（subcommands） | UseCase, Domain |
| **Infrastructure** | 外部・フレームワーク | `telegram_auth`（bot token を env から）/ `bootstrap.sh`（依存導入、NewsCaster 同型）/ `watch_loop.sh`（バックグラウンド long-poll → Monitor 給餌） | 全層（最外殻） |

### Dependency Direction
`Infrastructure → Interface → UseCase → Domain`。Domain は外層を import しない。Telegram SDK / HTTP / git / Claude 推論はすべて UseCase の外（Port の向こう、または親プロセス Weave）に追い出す。**Testability 最優先**：UseCase は fake adapter で全パス検証可能にする。

### Subcommands（NewsCaster の run/dry-run/send-rendered/validate-config/test と相似）

| Command | 機能 | Exit code |
|---|---|---|
| `validate-config` | env vars + authorized chats + token 形式 + （任意で）疎通確認 | 0=OK, 2=設定欠損 |
| `lease acquire\|renew\|release` | 並走防止のリースロック操作 | 0=取得/更新, 4=他セッション保持中 |
| `poll` | getUpdates 1サイクル。認可・正規化済み update を JSON Lines で stdout（Weave が読む）。取得分の offset を advance | 0=成功, 1=fetch失敗, 3=auth失敗 |
| `watch` | バックグラウンド long-poll ループ。実メッセージ1件=1行を emit（Monitor が消費）。アイドル枠ゼロの心臓部 | 長時間常駐 |
| `send-reply --chat-id --update-id --text-file` | Weave 起草の返信を送信 → offset 永続化 → lease renew | 0=送信, 1=送信失敗, 3=auth失敗 |
| `test` | owner chat に ping 1通（疎通テスト） | 0/1/3 |

### Cloud Routine の流れ（ROUTINE_PROMPT.md / Stage 5 で確定）
```
[cron 1h+ で起動] → bootstrap → Weave 人格 + SecretaryRole + SECURITY ロード
  → lease acquire（他セッション保持中なら即 exit＝自己治癒の重複防止）
  → 起動直後に api.telegram.org 疎通 curl（Custom policy 反映確認）
  → offset を Private リポから復元
  → `watch` を run_in_background で起動
  → Monitor ループ: emit 行（=実メッセージ）ごとに
       Weave が SecretaryRole + プロンプトフェンシングで応答起草
       → send-reply で送信・offset 永続化・lease renew
  → セッション終端で lease release（次 cron が拾い直し）
```

## Stages

## Stage 1: Domain 値オブジェクト + 純粋ロジック
**Goal**: 外部依存ゼロの値オブジェクトと、入力正規化・injection フラグの純関数。
**Layer**: Domain
**Success Criteria**: 全 Domain テストが green、import が標準ライブラリのみ。
**Tests** (Red → Green):
  - `AuthorizedChats.is_authorized()` が allowlist 外 chat_id を弾く / 許可 id を通す
  - `UpdateOffset.advance(update_id)` が常に `max(current, id+1)` 単調増加（古い update で巻き戻らない）
  - `SessionLease.is_stale(now)` が heartbeat + ttl 経過で True、`held_by_other()` が別 owner かつ非 stale で True
  - `normalize_input()` が全角/半角・Unicode 異体字・サロゲートペアを正規化、`flag_injection()` が role override / system prompt 抽出 / credential 要求を検知（ブロックせずフラグ）
**Implementation Notes**: NewsCaster `domain/`（FeedPolicy・DateRangeJST）の値オブジェクト書式に倣う。frozen dataclass。injection 検知は OPS.md §7「フラグのみ・偽陽性回避」。
**Status**: Complete

## Stage 2: UseCase + Ports（fake adapter で駆動）
**Goal**: ロック取得・取得認可・返信送信のオーケストレーションを Port 越しに完成。
**Layer**: UseCase
**Success Criteria**: 4 Port すべて fake で UseCase 全分岐をテスト。実 I/O ゼロ。
**Tests** (Red → Green):
  - `FetchAuthorizedUpdates`: 未認可 chat の update を捨て、認可分のみ正規化+フラグ付きで emit、offset を advance
  - `SendReply`: 送信成功で offset 永続化と lease renew が呼ばれる / 送信失敗で offset を進めない（冪等・再送可能）
  - `AcquireLease`: 他セッション保持中（非 stale）で取得失敗を返す / stale なら奪取
**Implementation Notes**: NewsCaster `usecases/`（Port + UseCase 分離、RunDaily orchestrator）に倣う。Claude 推論は Port にしない（親プロセス担当）。DI で組み立て。
**Status**: Complete

## Stage 3: Interface Adapters（Telegram Gateway / State Store）
**Goal**: 実 Telegram API と state 永続化の実装。HTTP はモックでテスト。
**Layer**: Interface (Adapter)
**Success Criteria**: getUpdates/sendMessage のパース・リトライ・タイムアウトと、offset+lease の読み書き（破損フォールバック含む）が green。
**Tests** (Red → Green):
  - `TelegramApiGateway.get_updates(offset, timeout)`: 正常 JSON → `TelegramUpdate` 列、5xx → リトライ後 fetch エラー、401 → auth エラー（exit 3 系）
  - `JsonStateStore`: offset+lease の round-trip、破損ファイル → 空にフォールバック後の新規書き込み成功
**Implementation Notes**: NewsCaster `adapters/`（RssXmlGateway・JsonStateStore）に倣う。UA は Telegram 推奨/Chrome 系。state dir は env `TELEGRAM_SECRETARY_STATE_DIR`、既定は Private 配下。
**Status**: Complete

## Stage 4: Infrastructure + CLI（main.py / bootstrap / watch ループ）
**Goal**: subcommands の配線、認証、bootstrap、バックグラウンド watch ループ。
**Layer**: Infrastructure
**Success Criteria**: `validate-config` / `poll` / `send-reply` / `lease` が CLI から動作。`watch` がアイドル時に行を出さず、実メッセージで1行 emit。`bootstrap.sh` で `[telegram-secretary-bootstrap] ready`。
**Tests** (Red → Green):
  - `main.py validate-config` が env 欠損で exit 2 / 揃って exit 0
  - `send-reply --text-file` が body を送信し offset を永続化（gateway/store はモック）
  - `watch_loop.sh` がモック getUpdates で「空応答→無出力」「メッセージ有→1行 emit」を満たす（shell レベル smoke）
**Implementation Notes**: NewsCaster `main.py` の argparse + env 橋渡し + bootstrap.sh をテンプレ流用。env: `TELEGRAM_BOT_TOKEN`・`TELEGRAM_SECRETARY_AUTHORIZED_CHATS`(JSON配列)・`TELEGRAM_SECRETARY_STATE_DIR`。token は env のみ（コード直書き禁止 / OPS.md §1）。
**Status**: Complete

## Stage 5: Cloud Routine 統合 + 環境実測 + ドキュメント
**Goal**: ROUTINE_PROMPT.md（Monitor 駆動ループ + lease 並走防止 + 疎通確認）、SKILL.md、egress/cron 設定手順、そして**未文書化2点の実測**。
**Layer**: Infrastructure（運用統合）
**Success Criteria**: 新規 fresh session で疎通 curl が 401/404（=egress 開通）、`test` で owner に ping 到達、`watch`+Monitor で実メッセージに Weave が1往復応答、lease で2セッション並走が防止される。**セッション寿命とアイドル枠消費の実測値を記録**。
**Tests / 検証**:
  - fresh session 起動 → `curl api.telegram.org/.../getMe`（invalid token）が 401 を返す（Custom policy 反映確認）
  - `watch` をバックグラウンド起動 → 自分の bot に 1 通送る → Monitor 行 emit → `send-reply` で返信が Telegram に届く（E2E）
  - lease 保持中に2つ目の `lease acquire` が exit 4
  - **実測ログ**: 無操作で session が何分生存するか / `watch` blocking 中に枠消費が発生するか
**Implementation Notes**: NewsCaster ROUTINE_PROMPT.md を骨格に。cron は `/schedule` で 1h+。3-Strike の最有力詰まりポイント（下記）はここで顕在化する。

**v0.1.1 修正履歴 (2026-05-26)**: Routine 側レビューで以下の設計ホール・取りこぼしを修正済み。詳細は [`CHANGELOG.md`](./CHANGELOG.md) [0.1.1] 参照。

- 指摘①（lease keep-alive 配線漏れ、重要）: `watch` ループがサイクル毎に lease 自動 renew するように配線。アイドル時 stale 化 → 並走奪取の設計ホールを塞いだ
- 指摘②（テスト未 commit）→ 事実訂正後、**運用ポリシーを変更**して全 Expertises のテストを公開する方針に統一（.gitignore 修正）
- 指摘④-1（state/ 誤コミット防止）: .gitignore に `Expertises/*/state/` 追加
- 指摘④-2（SendReply の owner 検証）: 送信前に lease store を再 load して並走奪取をブロック
- 指摘④-3（429/Retry-After 尊重）: api_gateway で 429 を retry 対象に追加、`Retry-After` 上限付きで sleep

**v0.1.2 修正履歴 (2026-05-26)**: 運用律 B 案として session_id を env 経由で統一。詳細は [`CHANGELOG.md`](./CHANGELOG.md) [0.1.2] 参照。

- `bootstrap.sh` を source/exec デュアル対応 + `TELEGRAM_SECRETARY_SESSION_ID` 冪等自動 export
- `cmd_send_reply` に `--owner` 引数 + CLI 層 owner 検証（二重防御）
- `ROUTINE_PROMPT.md` Step 2 を `source` 呼び出しに変更

**Live Functional Verification 結果 (Routine 側ローカル検証, 2026-05-26)**: 実コードを /tmp に展開して実プロセス・実ソケットで以下を検証 (Telegram egress 不要な部分のみ):
- ✅ lease 並走防止 / crash 自己治癒 (stale 奪取)
- ✅ validate-config env 欠損/充足
- ✅ watch アイドル時の沈黙 (idle-zero の土台)
- ✅ 認可フィルタ / injection フラグ / offset 単調前進
- ✅ sendMessage 経路 (ローカル mock サーバー経由で実ソケット疎通)

機能パイプラインは実質グリーン。詳細は [`CHANGELOG.md`](./CHANGELOG.md) 冒頭の「Stage 5 進捗ノート」を参照。

**Status**: In Progress（ROUTINE_PROMPT.md / SKILL.md / README.md / CHANGELOG.md 作成済み、v0.1.1 設計ホール修正・v0.1.2 運用律 B 案実装済み、Routine 側ローカル live 検証で functional パイプライン実質グリーン、本物 Telegram egress + bot token を用いた E2E と寿命/枠実測は新コンテナでの別セッション待ち）

## Documentation Plan

### 基本セット（毎回確認）
| ドキュメント | パス | 新規/更新/不要 | 計画内容 |
|---|---|---|---|
| `README.md` | `Expertises/TelegramSecretary/README.md` | 新規 | スキル概要・env vars・運用（NewsCaster README 同型） |
| `CHANGELOG.md` | `Expertises/TelegramSecretary/CHANGELOG.md` | 新規 | Stage 単位の変更履歴 |
| `IMPLEMENTATION_PLAN.md` | （本ファイル） | 新規 | 全 Stage 完了後に削除 |

### 拡張レイヤー
| ドキュメント | パス | 新規/更新/不要 | 理由 |
|---|---|---|---|
| `SKILL.md` | `Expertises/TelegramSecretary/SKILL.md` | 新規 | スキルマニフェスト（Subcommands / Failure Modes / RunResult） |
| `ROUTINE_PROMPT.md` | `Expertises/TelegramSecretary/ROUTINE_PROMPT.md` | 新規 | Cloud Routine prompt body（Monitor ループ・lease・疎通） |
| `CLAUDE.md`（root） | `./CLAUDE.md` | 更新 | 「利用可能ペルソナ」に1エントリ追加（NewsCaster と並列） |
| `STRUCTURE.md` | `./STRUCTURE.md` | 要確認 | Expertises ツリー記載があれば追記、なければ不要 |

> 拡張レイヤーの最終棚卸しは Stage 5 着手時に `Explore` サブエージェントで再確認（SSoT 違反チェック含む）。

## Decision Priority Notes（Testability > Readability > Consistency > Simplicity > Reversibility）
- **LLM をコード外に**（最大の分岐）: 応答生成を Port 化せず親プロセス Weave に委ねる。Testability（UseCase が fake で完結）と Consistency（NewsCaster send-rendered と同型）と原則（claude -p 禁止）が一致して勝つ。
- **offset 永続化の頻度**: 毎メッセージ git push（堅牢だが遅い・汚い）vs in-memory + 定期永続化（高速・冪等で吸収）。Simplicity と性能で後者。crash 再処理小窓は Domain の冪等性で担保。
- **ロック方式**: PID ファイル vs heartbeat+TTL リース。crash 自己治癒との両立（Reversibility）で後者。

## 3-Strike Rule
- **詰まりやすい予想ポイント**:
  1. セッション寿命が cron 最小 1h より極端に短い → 自己治癒に空白が出る（24-7 が崩れる）
  2. `watch` の blocking 中に枠消費が発生する（アイドルゼロの前提が崩れる）
  3. Custom network policy が期待通り api.telegram.org を通さない / 反映タイミングがズレる
- **代替アプローチ候補**:
  - 寿命が短い: cron を許容最大頻度（1h）にし「数分以内の取りこぼしは次回拾い直し＝準リアルタイム」に SLA を緩める / または Channels（ローカルPC常駐）へ方針転換
  - 枠消費する: `watch` の timeout を伸ばし poll 頻度を落として枠/日を圧縮、応答 SLA とのトレードオフを計測して決める
  - egress 不通: docs の deny-reason を確認、`*.telegram.org` ワイルドカード、最悪 Full policy の是非を相談
- **ユーザーへ相談する判断ライン**: 上記いずれかで「24-7 即応」が構造的に成立しないと判明した時点で、SLA緩和 / Channels(PC常駐) / 別ホスティング の三択を `AskUserQuestion` で提示。

## セキュリティ（OPS.md §1・§7、SecretaryRole 前提で必須）
- **認可 chat_id allowlist**（authn≠authz / IDOR 防止）— 未認可 chat は Domain で破棄、Weave に渡さない
- **プロンプトフェンシング** — 受信本文を XML タグで隔離し「データとして扱え」と明示してから Weave に渡す
- **injection フラグ**（ブロックせず記録）・**出力漏洩スキャン**（返信に token/env名/system prompt 混入がないか送信前チェック）
- **レート制限** — chat_id 単位 sliding window（コスト暴走 & DoS 防御）
- **secrets は env のみ**（bot token をコード/コミットに置かない）・**ログに secret を残さない**

## LineBridge 連携（拡張）

`Expertises/TelegramSecretary/LineBridge/` を併用する場合に、本計画の各 Stage に追加で必要となる実装事項。LineBridge を採用しない構成（Telegram 単独）でも本体は動作するため、本章はオプショナルな拡張章として位置付ける。詳細仕様は `LineBridge/IMPLEMENTATION_PLAN.md` を正典として参照。

### 結合方式（決定済み）

- **B. 共通 Telegram bot 共有**: 本体 (TelegramSecretary) と LineBridge は同じ bot token を保持。本体のみ `getUpdates` で受信、Bridge は `sendMessage` のみ呼ぶ **send only 制限**。これで polling 競合は構造的に不可能、token 共有のリスクは漏洩時の偽通知のみに収束
- **mux 方式 A**: Bridge 由来の Telegram メッセージは `[from:line:U1234abc]` プレフィックス付き、Weave 起草の LINE 宛応答は `[to:line:U1234abc]` または `[relay-to:line:U1234abc]` 付与

### Stage 1（Domain）への追加

- **`User` 集約ルート**: `uuid` / `display_name` / `role` (principal|associate) / `status` (pending|active|blocked) / `line_user_id` / `telegram_chat_id` / `registered_at` / `approved_at` / `identity` を保持
- **`Identity` 値オブジェクト**: `category` (family|friend|client|vendor|employee|peer|introducer|other) / `relationship_label` / `honorific` / `tone` (casual|polite|formal) / `context_notes` / `shared_with: list[user_uuid]` / `priority_bias` (low|normal|high) / `taboo_topics: list[str]`。frozen dataclass、`__post_init__` でバリデーション
- **`MuxTag`**: Telegram メッセージ内の `[from:line:X]` / `[to:line:X]` / `[relay-to:line:X]` を安全にパース・ビルド。不正フォーマット時は `ValueError`（インジェクション防御）

### Stage 2（UseCase + Ports）への追加

- **追加 Port**: `BridgeRelayPort`（mux タグ付きメッセージを LineBridge `/internal/relay-to-line` に POST、Bearer 認証）/ `UserStore`（User 集約の読み書き）
- **追加 UseCase**: `RegisterOrFetchUser` / `ApproveUser` / `BlockUser` / `UpdateIdentity` / `LinkAccounts` / `ShareWith` / `UnshareWith` / `ListShares` / `RelayToAssociate` / `RenderSecretaryMenu`（`/secretary` 応答のメニュー構築）

### Stage 3（Interface Adapters）への追加

- **`HttpBridgeRelayClient`**: `BridgeRelayPort` の実装、httpx 非同期、retry/timeout、Bearer 認証ヘッダ付与
- LINE 由来の承認 callback は Bridge 側 `/internal/approval-callback` で受信、Bridge → 本体への伝達は **共通 Telegram bot 経由**（B 結合方式の帰結）。本体は通常メッセージとして受け、`[approval:line:U1234abc:approve|reject]` 等の特殊 mux タグで承認結果を識別

### Stage 4（Infrastructure / CLI）への追加 Subcommands

| Subcommand | 機能 | Exit code |
|---|---|---|
| `secretary` | マスタースキル、`/secretary` 受信を検出してインライン キーボードでメニュー応答を生成 | 0 |
| `list-users` | active な関係者一覧出力 | 0 |
| `pending-users` | 承認待ち一覧出力 | 0 |
| `approve-user --user-uuid` | pending → active 切替 | 0 / 4 (未存在) |
| `block-user --user-uuid` | active/pending → blocked | 0 / 4 |
| `edit-identity --user-uuid` | identity 編集（対話的、項目選択） | 0 |
| `link-accounts --user-uuid --other-id` | LINE/Telegram アカウント紐付け | 0 / 4 (衝突) |
| `share --from-uuid --to-uuid` | identity.shared_with に追加 | 0 |
| `list-shares [--user-uuid]` | 共有許可一覧 | 0 |
| `unshare --from-uuid --to-uuid` | identity.shared_with から削除 | 0 |
| `relay --user-uuid --text-file` | 関係者へのリレー指示送信（Bridge 経由） | 0 / 1 (送信失敗) |

**追加 env vars**:
- `LINEBRIDGE_INTERNAL_API_URL`（Bridge の `/internal/*` 呼び出し先 URL）
- `LINEBRIDGE_BEARER_TOKEN`（内部 API 認証 token）

### Stage 5（Cloud Routine 統合）への追加

- **SecretaryRole プロンプト強化**:
  - **identity 参照**: 応答時に該当 user の `tone` / `honorific` / `taboo_topics` を必ず参照して文体・呼称・避ける話題を反映
  - **重要度判定**: 案件ごとに `low` / `normal` / `high` を判定、`high` なら大環主に即時 push（バッチ待ちしない）
  - **エスカレ判定**: 大環主判断要否を親性倫理に基づき判定、要なら関係者には「確認中です」自動応答 + 大環主に push
  - **共有候補判定**: 関係者間共有が筋良いと判断したら、`identity.shared_with` の未登録相手のみ大環主に承認伺いを出す
  - **`/secretary` 受信時のメニュー応答**: インライン キーボードでマスターメニューを返す、ボタンタップで個別 subcommand or 対話モードへ展開
- **承認 UX 双方向**: Telegram の `callback_query`（インライン キーボード）と LINE 由来承認（Bridge `/internal/approval-callback` 経由→共通 bot で本体に伝達）の両方を扱う
- **`/list` 等のマッピング**: ユーザーが Telegram で `/list` `/secretary` 等を打った場合の意図解釈→対応 subcommand 呼び出しを Weave プロンプトに明示

### Security 追加項目

- **`BridgeRelayPort` 経由の通信**: Bearer token 必須、token は env、ログ出力時に redact
- **Telegram bot token の共有**: 本体のみ `getUpdates` を呼ぶ、Bridge は **send only** 制限。起動時 assertion で「Bridge は polling 禁止」を構造的に強制
- **LINE 由来承認 callback の取り扱い**: Bridge 側で X-Line-Signature 検証済みのものを共通 bot 経由で本体に転送、本体は mux タグで識別後に Domain の `ApprovalDecision` に正規化
- **principal 権限分離**: `secretary` `list-users` `approve-user` `block-user` `edit-identity` `link-accounts` `share` `list-shares` `unshare` `relay` 等の管理系 subcommand は principal の chat_id 起源のみ実行、それ以外は拒否

---

## Stage 6: Multimodal Inbox（画像/メディア受信対応）

> 追加日: 2026-05-27。Stage 1-5 で確立した「Domain → UseCase → Interface → Infrastructure、LLM 推論はコード外」の原則を継承し、Telegram の photo / document / caption をハイブリッド（Medium=メタ flag + Heavy=ローカル保存）で扱う。Vision 解釈は親プロセス Weave が担当（`claude -p` 禁止 / L00473）。

### Overview（Stage 6 固有）

- **What**: Telegram の photo（写真）/ document（任意ファイル）/ caption（添付説明文）を受信し、emit JSON Lines に `media[]` 配列とメタデータ（file_id / mime_type / size / local_path）を加える。caption は text に統合。Heavy モードで `getFile` + ファイル download まで実行し、親プロセス Weave が `Read` で開いて Vision 解釈する状態まで運ぶ。
- **Why**: 現状の TelegramSecretary は text-only。建設プロジェクト写真、契約書 PDF、現場メモ画像など、大環主が即座に Weave と共有したい入力の多くが非テキスト。Vision 対応 LLM の能力を Cloud Routine の常駐チャネルに接続することで、24-7 即応の射程をマルチモーダルへ拡張する。
- **Where**: 既存 `Expertises/TelegramSecretary/` 配下に追記。新規ファイル: `domain/media.py`, `adapters/telegram/media_downloader.py`, テスト一式。state_dir 直下に `media/` サブディレクトリを作成（`.gitignore` で除外）。
- **Reference Patterns**:
  1. `scripts/domain/models.py` — `TelegramUpdate.from_api()` の minimal field 抽出パターン → `media` 抽出も同型で追加
  2. `scripts/adapters/telegram/api_gateway.py` — `_request_with_retry` の 5xx/429/401 ハンドリング → `getFile` + ファイル download にも同パターン適用
  3. `scripts/adapters/state/emitter.py` — JSON Lines 出力の `ensure_ascii=False` パターン → `media[]` を payload に追加、version フィールドで後方互換性を切る

### Stage 6 全体の Architecture 拡張

| Layer | Stage 6 で追加する責務 | 主要な型/関数 | 依存先 |
|---|---|---|---|
| **Domain** | メディアの値オブジェクトと caption 統合ロジック | `MediaAttachment`（kind: photo\|document、file_id、mime_type、size）/ `MediaSizeLimitExceeded`（exception）/ `merge_caption_into_text()`（純関数） | なし |
| **UseCase** | media 抽出 + ダウンロード判定 + ローカル保存呼び出し | Port: `MediaDownloader`（`fetch_file_path(file_id) -> str`、`download(file_path, target) -> Path`）。UseCase 拡張: `FetchAuthorizedUpdates` が media[] を抽出、`DownloadAuthorizedMedia` を新設（認可済み update の media をサイズ制限内で download） | Domain のみ |
| **Interface (Adapter)** | Bot API `getFile` + ファイル本体 download / emit 拡張 | `TelegramMediaDownloader`（`api_gateway` 経由で `getFile` 呼び出し、`https://api.telegram.org/file/bot<token>/<file_path>` を別 client で取得し state_dir/media/ に保存）/ `StdoutEventEmitter` に `media[]` + payload version 追加 | UseCase, Domain |
| **Infrastructure** | env 拡張 / 自動削除 cron / .gitignore | `Config` に `media_max_size_bytes`・`media_retention_hours`・`media_enable_download` 追加 / `scripts/media_cleanup.py`（保持期限超過ファイル削除）/ `.gitignore` の `state/` 配下に media/ 含む確認 | 全層 |

### Dependency Direction

Stage 1-5 と同じく `Infrastructure → Interface → UseCase → Domain`（内向き）を厳守。`MediaDownloader` Port は Domain の `MediaAttachment` 型のみを返す。HTTP / ファイル I/O は UseCase の外（Port の向こう）。Domain の `MediaAttachment` は file_id 等の identifier のみ保持し、bytes は持たない（純粋性維持）。

### emit スキーマ拡張と version 戦略

Stage 5 までの payload（`update_id` / `chat_id` / `user_id` / `username` / `text` / `injection_flags`）は **後方互換のフィールド追加**で延長する：

```json
{
  "v": 2,
  "update_id": 12345,
  "chat_id": 100,
  "user_id": 200,
  "username": "weave_user",
  "text": "<caption + text 統合済み正規化本文>",
  "injection_flags": [],
  "media": [
    {
      "kind": "photo",
      "file_id": "AgACAg...",
      "mime_type": "image/jpeg",
      "size": 102400,
      "local_path": "state/media/12345_AgACAg.jpg"
    }
  ]
}
```

- `v: 2` を**新規追加**（v1 は明示せず欠落 = v1 として扱う運用）。破壊的変更を将来入れる際の楔
- `media` フィールドは photo/document なしの update では空配列 `[]`（欠落ではなく明示）
- `local_path` は Heavy モード（`media_enable_download=true`）でのみ非 null、Medium モード（download 無効）では null
- ROUTINE_PROMPT.md Step 5 は「`media[].local_path` が non-null なら `Read` で開いてから起草」に拡張

### Stages

## Stage 6.1: Domain — MediaAttachment 値オブジェクト + caption 統合
**Goal**: photo / document / caption を Domain 層の純粋型として表現し、caption を text に統合する純関数を提供する。
**Layer**: Domain
**Success Criteria**: `domain/media.py` の全テストが green、外部依存ゼロ（標準ライブラリのみ）。`TelegramUpdate.from_api()` が photo / document / caption を含む payload からも minimal field を取り出せる。
**Tests** (Red → Green):
  - `MediaAttachment.from_photo_api()` が Telegram の `photo` 配列（最大解像度）から file_id / size を抽出、mime_type は固定 `"image/jpeg"`（Telegram の photo は常に jpeg）
  - `MediaAttachment.from_document_api()` が `document` から file_id / mime_type / file_size を抽出、mime_type 欠落時は `"application/octet-stream"` フォールバック
  - `merge_caption_into_text(text, caption)` が `caption + "\n" + text` を返す（caption 欠落時は text のみ、両方欠落時は空文字、片方欠落時は片方のみ）
**Implementation Notes**: `frozen dataclass`、`@classmethod from_*_api()` パターン。photo は配列で複数解像度が来るため最大 size を選択（Telegram API 仕様: 配列末尾が最大）。`TelegramUpdate.from_api` への媒介は Stage 6.2 で実装する（Domain の純粋性維持のため、Stage 6.1 では `MediaAttachment` 単体のみ）。
**Status**: Complete

## Stage 6.2: UseCase — Media Port + 認可済み media 抽出
**Goal**: `MediaDownloader` Port を定義し、`FetchAuthorizedUpdates` を拡張して media[] を抽出、`DownloadAuthorizedMedia` UseCase を新設して認可済み update の media をサイズ制限内でダウンロードする。
**Layer**: UseCase
**Success Criteria**: fake `MediaDownloader` で全分岐検証、実 I/O ゼロ。`TelegramUpdate` が `media: list[MediaAttachment]` フィールドを保持し、`from_api` が photo/document/caption を抽出する。
**Tests** (Red → Green):
  - `FetchAuthorizedUpdates`: photo 付き update を取得 → media[] に `MediaAttachment(kind="photo")` が入る、caption が text に統合される
  - `DownloadAuthorizedMedia`: 認可済み update の media を size 上限内なら fake downloader で download を呼ぶ / size 超過なら `MediaSizeLimitExceeded` を上げて該当 media を skip（他 media は続行、update 自体は emit される）
  - 認可外 chat の update は media も含めて Domain で破棄（Stage 1 の chat allowlist と整合）
**Implementation Notes**: `TelegramUpdate` 拡張は **frozen dataclass の field 追加**。既存テストの from_api ケースが `media=[]` で通る後方互換性を維持。`DownloadAuthorizedMedia` は Heavy モード時のみ呼ぶ（CLI 層で分岐、UseCase は副作用 download を Port 経由で持つだけ）。`MediaSizeLimitExceeded` は Domain exception（`domain/exceptions.py` に追加、`flag_injection` と同型の「フラグ化して emit、ブロックはしない」スタンスを基本にしつつ、download だけは skip）。
**Status**: Complete

## Stage 6.3: Interface — Telegram getFile + ダウンローダ実装 / emit v2
**Goal**: 実 Telegram API の `getFile` 呼び出し → ファイル本体取得 → `state_dir/media/` への保存と、emit JSON の `v:2` + `media[]` 出力。
**Layer**: Interface (Adapter)
**Success Criteria**: HTTP モックでテスト green。`StdoutEventEmitter` が photo/document 含む update を `v:2` + `media[]` で出力、photo/document 無し update でも `media: []` を含む。`token` 込み URL がログ・例外メッセージに混入しないこと（送信前の redact 確認テスト含む）。
**Tests** (Red → Green):
  - `TelegramApiGateway.get_file(file_id)`: `/getFile?file_id=...` の正常応答から `file_path` を返す、5xx → retry、401 → AuthFailureError
  - `TelegramMediaDownloader.download(file_path, target_dir)`: `/file/bot<TOKEN>/<file_path>` の bytes を target_dir 配下にユニークなファイル名で保存、URL は例外メッセージに含めない（regex で token redact 確認）
  - `StdoutEventEmitter.emit()` が `v:2` 付きで出力、media[] が photo を1件含む / 空配列を含む両ケース、`local_path` 有/無
**Implementation Notes**: `TelegramApiGateway` への `get_file` 追加は既存 `_request_with_retry` をそのまま流用。ファイル本体取得は **別 client**（base_url が `api.telegram.org/file/bot<TOKEN>/` で異なる、token 込み URL なのでログ秘匿が必須）。target ファイル名は `<file_id 先頭16>_<basename>` 形式（Port シグネチャ `download(file_id, target_dir)` に update_id が無いため、file_id プレフィックスで衝突回避と追跡性両立）。`v:2` の payload version は **新規追加のみで既存 emit テストは破壊されない**（既存テストは個別 field を読むだけで `v` キーに触れていないことを Stage 6.3 着手時に実測確認、3-Strike 予想 #4 は杞憂）。
**Status**: Complete

## Stage 6.4: Infrastructure — config / cleanup / .gitignore / ROUTINE_PROMPT 拡張
**Goal**: env vars 追加、保持期限超過 media の自動削除、`.gitignore` への media/ 確認、ROUTINE_PROMPT.md Step 5 拡張。CLI は `poll` / `watch` に Heavy/Medium モード切替を統合。
**Layer**: Infrastructure
**Success Criteria**: `validate-config` が新 env を含めて exit 0、`media_cleanup.py` が保持期限超過ファイルのみ削除、ROUTINE_PROMPT.md に「`media[].local_path` 非 null なら `Read` で開く」が記載される。
**Tests** (Red → Green):
  - `Config.from_env`: `TELEGRAM_SECRETARY_MEDIA_MAX_SIZE_BYTES`（default 20MB）/ `TELEGRAM_SECRETARY_MEDIA_RETENTION_HOURS`（default 24）/ `TELEGRAM_SECRETARY_MEDIA_ENABLE_DOWNLOAD`（default true）の parse、欠損は default、不正値は exit 2
  - `media_cleanup.py`: mtime が retention_hours 超過のファイルを削除、それ未満は保持（fake clock 注入）
  - `cmd_poll` / `cmd_watch` が `media_enable_download=false` のとき `DownloadAuthorizedMedia` を呼ばず Medium モードに留まる（fake gateway/downloader 注入）
**Implementation Notes**: env 名は `TELEGRAM_SECRETARY_MEDIA_*` プレフィックスで統一。`media_cleanup.py` は単独実行可能 + `watch` ループの cleanup hook（N サイクルに 1 回）両対応 — Stage 6.4 では cleanup 関数本体のみ実装、watch への定期呼び出し配線は Stage 6.5 で実機検証時に判断（毎サイクル / N サイクル毎 / Cloud Routine cron で別途）。`.gitignore` は既存の `Expertises/*/state/` で media/ 配下も既に除外済み（state/ サブツリー全体）→ 確認のみ、追加変更なし。ROUTINE_PROMPT.md は Step 5 の JSON 例を v2 形式に差し替え、`media[].local_path` 三状態（非null / null+skip_reason / null+null=Medium モード）の処理分岐を明記、Failure modes に `media_size_exceeded` 等を追加。
**Status**: Complete

## Stage 6.5: 統合テスト + ドキュメント + 実機 E2E
**Goal**: photo / document / caption の E2E（自分の bot に画像を送る → `watch` → `media[]` 付き emit → Weave が `Read` で開く → 内容を踏まえた返信）を Cloud Routine 上で 1 往復成立させる。CHANGELOG / README / SKILL.md / ROUTINE_PROMPT.md を v0.2.0 で更新。
**Layer**: Infrastructure（運用統合）
**Success Criteria**: fresh session で `watch` 起動 → 自分の bot に photo 1 枚 + caption "これ何？" を送る → emit に `media[0].local_path` と統合 text が乗る → 親プロセス Weave が `Read` で画像を開き、Vision 解釈を含めた返信 → Telegram に到達。size 上限超過時の skip、document（PDF）の同等動作、retention_hours 経過後の自動削除も実測。
**Tests / 検証**:
  - E2E: photo + caption "見える？" → emit → Weave が画像内容に言及した返信を送信、Telegram で受信確認
  - E2E: 大きな画像（>20MB）送信 → `injection_flags` 風に `media_size_exceeded` フラグが emit に乗る or 該当 media のみ skip、update 自体は他 media と text で emit
  - E2E: PDF document 送信 → mime_type=application/pdf で emit、`Read` で開けるか確認（PDF 直接読み取りは Read tool が対応、必要に応じて pages 指定）
  - retention 実測: 24h 経過後 `media_cleanup.py` 起動 → 該当ファイル削除、新規ファイルは保持
**Implementation Notes**: Stage 5 同様、新 fresh session 起動が前提（既存セッションには Custom policy 反映されないため）。CHANGELOG は [0.2.0] エントリで「Multimodal Inbox: photo/document/caption 受信対応、emit v2 化」を記載。README の env vars 表に 3 件追加、Subcommands 表は変化なし（既存の poll/watch がモード切替で兼ねる）。SKILL.md と ROUTINE_PROMPT.md は v2 payload を反映。
**Status**: In Progress（**Doc Complete** — CHANGELOG [0.2.0] / README env vars + Quickstart photo 試験 / SKILL.md Daily Workflow + env vars + Security 三層 / ROUTINE_PROMPT.md Step 5 v2 schema + media 三状態処理分岐 + Failure modes 拡張、すべて 2026-05-27 着地。**Live E2E Pending** — 新 fresh session での photo/document/caption の実機 E2E、retention 実測は Stage 5 と同じ要件で別セッション待ち）

### Documentation Plan（Stage 6 追加分）

| ドキュメント | パス | 新規/更新/不要 | 計画内容 |
|---|---|---|---|
| `CHANGELOG.md` | `Expertises/TelegramSecretary/CHANGELOG.md` | 更新 | [0.2.0] - 2026-MM-DD に「Multimodal Inbox: photo / document / caption 受信対応、emit JSON Lines v2 化、`MediaAttachment` Domain 追加、`TelegramMediaDownloader` Adapter 追加、`media_cleanup.py` 追加、3 つの env vars 追加」を記載 |
| `README.md` | `Expertises/TelegramSecretary/README.md` | 更新 | env vars 表に 3 件（`TELEGRAM_SECRETARY_MEDIA_MAX_SIZE_BYTES` / `TELEGRAM_SECRETARY_MEDIA_RETENTION_HOURS` / `TELEGRAM_SECRETARY_MEDIA_ENABLE_DOWNLOAD`）追加。Quickstart に「photo を送って試す」一節を追記 |
| `SKILL.md` | `Expertises/TelegramSecretary/SKILL.md` | 更新 | Daily Workflow に「emit に media[] があれば Read で開いて Vision 解釈」を追加、env vars 表に 3 件追加、Security に「media size 上限・retention・token 込み URL ログ秘匿」を追加 |
| `ROUTINE_PROMPT.md` | `Expertises/TelegramSecretary/ROUTINE_PROMPT.md` | 更新 | Step 5 の JSON 例を v2 形式（`v: 2` + `media[]`）に差し替え、「`media[].local_path` 非 null なら `Read` で開いてから起草」を明記。Failure modes に `media_size_exceeded` / `media_download_failed` を追加 |
| `IMPLEMENTATION_PLAN.md` | （本ファイル） | 更新 | 本 Stage 6 セクション追加済み。Stage 6 全 5 段階完了後に Stage 5 と合わせて削除検討（現運用：イベント駆動開発の経緯として保持中） |
| `.gitignore` | `homunculus/Weave/.gitignore` | 確認のみ | `Expertises/*/state/` で state/media/ も既に除外済み。Stage 6.4 で実測確認 |
| `pyproject.toml` | `Expertises/TelegramSecretary/pyproject.toml` | 要確認 | `httpx` は既存依存、photo download 用に追加ライブラリ不要。Stage 6.3 着手時に再確認 |

> 拡張レイヤーの最終棚卸しは Stage 6.5 着手時に `Explore` サブエージェントで再確認（SSoT 違反チェック含む）。

### Decision Priority Notes（Stage 6 固有、Testability > Readability > Consistency > Simplicity > Reversibility）

- **Medium + Heavy ハイブリッド採用**（最大の分岐）: Medium-only（メタ flag のみ）は Weave 側で `getFile` を別途呼ぶ必要があり、コード外で HTTP 知識が必要になる（Consistency 違反）。Heavy-only（常に download）はサイズ制限の運用負荷が高い。**両モードを env で切り替え**、デフォルト Heavy で 24-7 即応性を取り、運用負荷が顕在化したら Medium に倒せるよう Reversibility を確保。
- **emit version bump（v:2）の導入**: 既存 consumer（ROUTINE_PROMPT.md と Weave）の更新が必要だが、フィールド欠落で v1 とみなす運用律で後方互換も両立可能。Testability（既存テストは v=2 期待に**一括更新**してパターン統一）を優先。`media: []` を明示出力する設計は「欠落 = 未対応」の混乱を避ける Readability の判断。
- **Domain の `MediaAttachment` は bytes を持たない**: 純粋性維持と Testability（bytes 比較を避ける）の両立。bytes は Infrastructure 層の保存先（local_path）に閉じ込め、Domain は identifier のみ。
- **size 制限超過は skip + flag、ブロックではない**: Stage 1 の `flag_injection` と同型の「フラグ化して emit、判断は Weave に委ねる」原則。Consistency と Reversibility（後で「skip→reject」へ厳格化は容易、逆は壊れる）の両立。
- **保持期限は env で可変、デフォルト 24h**: 機密書類が長期残存しないよう短めにデフォルト、必要なら延長可能（Reversibility）。`watch` ループ N サイクルごとの cleanup hook は Simplicity 優先（外部 cron 別途設定不要）。

### 3-Strike Rule（Stage 6 固有）

- **詰まりやすい予想ポイント**:
  1. **`getFile` レスポンスの `file_path` 形式**: Telegram の仕様変更や bot token 込み URL のドメイン差異（`api.telegram.org/file/bot<TOKEN>/...`）で download URL 組み立てが想定とずれる
  2. **大きな photo / document の long-poll タイムアウト干渉**: download 中に `getUpdates` の long-poll が止まる、または OS の `httpx` クライアントが timeout 緩和を要する
  3. **state_dir/media/ の容量爆発**: cleanup hook の周期と retention_hours の組み合わせで disk 圧迫、Cloud Routine の disk quota（未文書化）を踏み抜く
  4. **emit v2 への一括更新で既存テストが大規模に壊れる**: payload 検証テスト 5-7 件が同時に red 化、Refactor 中に複数 Stage が混ざって診断困難
- **代替アプローチ候補**:
  - `getFile` 形式問題 → Telegram Bot API ドキュメント参照、無効 token で 401 を踏んで応答形式を実測、必要なら `MediaDownloader` を `httpx` 直叩きに切り替え
  - long-poll 干渉 → download を **別スレッド** or 別プロセスに切り出し、`watch` のメインループは getUpdates に専念。最終手段として Medium モードに倒し、Weave 側で download を skill 化
  - 容量爆発 → retention_hours のデフォルトを 6h に短縮、cleanup hook 頻度を 1 サイクル毎に上げる、または disk quota 実測後に上限 byte 数（合計）を新 env で追加
  - emit v2 一括更新 → Stage 6.3 を着手する**前に**全 emit テストを `v` キー無視に変えるリファクタを 1 commit で切る（red 状態を最小化）
- **ユーザーへ相談する判断ライン**: 上記いずれかで「Heavy モード成立せず・Medium fallback も Weave 側負荷が許容外」となった時点で、`AskUserQuestion` で（Medium-only に倒す / 別 Stage 化して延期 / Telegram 以外の add-on で Vision 接続）の三択を提示。

### Security 追加項目（Stage 6 固有）

- **認可済み chat のみ download**: `FetchAuthorizedUpdates` の chat allowlist フィルタが先、`DownloadAuthorizedMedia` は認可済み update の media しか受け取らない（Domain で構造的に保証）
- **size 上限（DoS 防御）**: `media_max_size_bytes`（default 20MB）超過は download せず skip + flag emit、超大ファイルでの disk 圧迫を防ぐ
- **保持期限の自動削除**: `media_retention_hours`（default 24h）経過した media を `media_cleanup.py` で削除、機密書類の長期残存を防ぐ
- **token 込み URL の秘匿**: `https://api.telegram.org/file/bot<TOKEN>/<file_path>` の TOKEN は例外メッセージ・ログ・stderr に絶対残さない（regex redact をテストで検証）
- **`.gitignore` で media/ 除外**: 既存の `Expertises/*/state/` で state/media/ も含めて除外済み、Stage 6.4 で実測確認
- **mime_type は Telegram の自己申告**: 信頼せず、親プロセス Weave が `Read` で開いた結果を真とする（rename 攻撃対策、ただし Vision 解釈は Weave 側責務）

---

## Stage 7: MediaRenderer（ドキュメント系 mime の Weave 判断委任完成形）

> 追加日: 2026-05-27。Stage 6 で photo / document / caption の受信・download・emit v2 化までは完了したが、Step 5 の Weave 側処理は image/pdf 以外のドキュメント系（docx / pptx / xlsx）で `Read` 一択のため中身が到達しない。L00473 の分業（スキル=決定論的 fetch/render、Weave=判断と推論）を MediaRenderer 抽象で完成形に寄せ、「render → Weave が読む → Weave が動く」に一般化する。read 側のみ Stage 7、write 系（md/docx 生成して送り返し）は別 Stage（Stage 8）で扱う。音声/動画系は外部 API 判断が必要なため別 Stage（Stage 9 等）で扱う。

### Overview（Stage 7 固有）

- **What**: docx / pptx / xlsx などのドキュメント系 mime を [markitdown](https://github.com/microsoft/markitdown)（Microsoft 製 MIT、Python ライブラリ）でローカル変換して markdown 化し、emit JSON Lines の `media[]` item に `rendered_text` と `render_status` を追加して Weave に渡す。image/pdf は既存どおりパススルー（Vision ネイティブ / Read tool が PDF 対応のため render 不要）。未対応 mime は `render_status="skipped"` または `"failed"` でメタ情報のみ emit。
- **Why**: 現状 Step 5 は「`local_path` を `Read` で開く」一択だが、`Read` tool は image / PDF / text 系には対応するものの docx / pptx / xlsx のバイナリは開けない。これらは Cloud Routine の常駐セッションで最も到達頻度の高いファイル形式の一群であり、Vision 対応 LLM の射程外。markitdown で md 化することで、テキスト系判断は全て Weave に委ねられる完成形になる。
- **Where**: 既存 `Expertises/TelegramSecretary/` 配下に追記。新規ファイル: `usecases/render_media.py`, `adapters/render/markitdown_renderer.py`, テスト一式。`MediaAttachment` に `file_name` 追加、`pyproject.toml` に `markitdown` 追加。
- **Reference Patterns**:
  1. `scripts/usecases/download_authorized_media.py` — `MediaDownloadResult` の `skip_reason` パターン → `RenderedMedia` の `render_status` を同型で設計（"ok" | "passthrough" | "skipped" | "failed"）
  2. `scripts/usecases/ports.py` — `MediaDownloader` Port の `download(file_id, target_dir) -> Path` シグネチャ → `MediaRenderer` Port も pure-function 寄りの `render(media, local_path) -> RenderedMedia` で同型
  3. `scripts/adapters/telegram/media_downloader.py` — 例外を Domain Error に変換しつつ chain を切る（`raise ... from None`）パターン → `markitdown_renderer.py` でも内部ライブラリ例外を catch → flag 化（Stage 6 と同型の「ブロックしない」スタンス）

### Stage 7 全体の Architecture 拡張

| Layer | Stage 7 で追加する責務 | 主要な型/関数 | 依存先 |
|---|---|---|---|
| **Domain** | `MediaAttachment` への `file_name` 追加（document の元ファイル名取り込み、Weave の判断材料） | `MediaAttachment(file_name: Optional[str])` field 追加、`from_document_api` で `document.file_name` を抽出 | なし |
| **UseCase** | mime に応じた render 判定 + render 実行のオーケストレーション | Port: `MediaRenderer`（`render(media, local_path) -> RenderedMedia`）。UseCase: `RenderAuthorizedMedia`（download 済み media を mime-routing し、image/pdf は passthrough、docx/pptx/xlsx 等は Port 経由で render、未対応 mime は skipped）。dataclass: `RenderedMedia`（`rendered_text: Optional[str]` / `render_status: str`） | Domain のみ |
| **Interface (Adapter)** | markitdown 実装 + emit 拡張 | `MarkitdownRenderer`（`MediaRenderer` 実装、`markitdown.MarkItDown` を呼ぶ、例外は内部 catch して `RenderedMedia(rendered_text=None, render_status="failed")` を返す）。`StdoutEventEmitter` に `rendered_text` / `render_status` フィールド追加（既存 v2 schema に**追加のみ**、version bump なし） | UseCase, Domain |
| **Infrastructure** | pyproject 依存追加 + CLI 配線 | `pyproject.toml` に `markitdown` 追加（再帰依存 python-docx / python-pptx / openpyxl が入ることを許容）。`cmd_poll` / `cmd_watch` に renderer instantiation 追加、`media_enable_download` 同型の `media_enable_render` env は**不要**（Heavy モードで download した時点で render も実行するのが Simplicity、disable は将来 YAGNI 解除時に検討） | 全層 |

### Dependency Direction

Stage 1-6 と同じく `Infrastructure → Interface → UseCase → Domain`（内向き）を厳守。`MediaRenderer` Port は Domain の `MediaAttachment` と新規 `RenderedMedia` のみを扱う。markitdown ライブラリ呼び出しは UseCase の外（Port の向こう）に閉じ込め、UseCase は mime-routing と Port 呼び出しのみを担う。

### emit スキーマ拡張（v2 維持、フィールド追加のみ）

Stage 6 で確立した payload v2 を**バージョン bump せず、フィールド追加のみ**で延長する。既存 consumer（ROUTINE_PROMPT.md / Weave）は `rendered_text` / `render_status` の欠落（=null）を「Stage 6 までの emit」として扱える後方互換性を確保：

```json
{
  "v": 2,
  "update_id": 12345,
  "chat_id": 100,
  "user_id": 200,
  "username": "weave_user",
  "text": "<caption + text 統合済み正規化本文>",
  "injection_flags": [],
  "media": [
    {
      "kind": "document",
      "file_id": "BAAD...",
      "file_name": "specification.docx",
      "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "size": 51200,
      "local_path": "<state_dir>/media/BAAD..._specification.docx",
      "skip_reason": null,
      "rendered_text": "# 仕様書\n\n## 概要\n...",
      "render_status": "ok"
    },
    {
      "kind": "photo",
      "file_id": "AgACAg...",
      "file_name": null,
      "mime_type": "image/jpeg",
      "size": 102400,
      "local_path": "<state_dir>/media/AgACAg..._file.jpg",
      "skip_reason": null,
      "rendered_text": null,
      "render_status": "passthrough"
    }
  ]
}
```

- `file_name` を全 media item に明示出力（photo は null、document は元ファイル名）— Weave が「何のファイルか」を判断する材料
- `rendered_text` は `render_status="ok"` の時のみ非 null、それ以外は null
- `render_status` 四状態:
  - `"ok"`: markitdown で md 化成功、`rendered_text` 非 null
  - `"passthrough"`: image/pdf 等 Weave の Read tool で直接読める形式、render 不要
  - `"skipped"`: 未対応 mime（音声/動画など Stage 7 射程外）、メタのみ
  - `"failed"`: render を試みたが内部例外発生、メタのみ + Weave に「読めない」と正直に伝える
- ROUTINE_PROMPT.md Step 5 を「`rendered_text` があればそれを使う / なければ `local_path` を `Read` / なければメタのみ」に一般化

### 対応 mime の routing 表（Stage 7 射程）

| mime | 処理 | render_status |
|---|---|---|
| `image/*`（jpeg / png / webp / gif） | passthrough（Read tool で直接 Vision 解釈） | `"passthrough"` |
| `application/pdf` | passthrough（Read tool が PDF 対応） | `"passthrough"` |
| `application/vnd.openxmlformats-officedocument.wordprocessingml.document`（docx） | markitdown で md 化 | `"ok"` / `"failed"` |
| `application/vnd.openxmlformats-officedocument.presentationml.presentation`（pptx） | markitdown で md 化 | `"ok"` / `"failed"` |
| `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`（xlsx） | markitdown で md 化 | `"ok"` / `"failed"` |
| `text/plain` / `text/csv` / `text/markdown` / `application/json` | passthrough（Read tool が text 系に対応、markitdown 通すと冗長） | `"passthrough"` |
| `text/html` | markitdown で md 化（html→md の整形価値あり） | `"ok"` / `"failed"` |
| `audio/*` / `video/*` | skipped（Whisper 等外部 API 判断、Stage 9 等別計画） | `"skipped"` |
| `application/zip` 等のアーカイブ系 | skipped（中身展開は別判断、Stage 7 射程外） | `"skipped"` |
| その他未知 mime | skipped（保守的、メタのみで Weave に正直に） | `"skipped"` |

### Stages

## Stage 7.1: Domain — MediaAttachment.file_name 追加 + RenderedMedia 値オブジェクト
**Goal**: `MediaAttachment` に `file_name` field を追加し、`from_document_api` が document の元ファイル名を抽出する。`RenderedMedia` を新規追加。
**Layer**: Domain
**Success Criteria**: 既存 Domain テスト 36 件が file_name=None backward compat で green、新規テスト green、外部依存ゼロ。
**Tests** (Red → Green):
  - `MediaAttachment.from_document_api()` が `document.file_name` を抽出（Telegram API 仕様の document field）、欠落時は None
  - `MediaAttachment.from_photo_api()` は photo に file_name が無いので常に None（既存テストが file_name=None で通る）
  - `RenderedMedia` dataclass の field（`rendered_text: Optional[str]` / `render_status: str`）と frozen 性
**Implementation Notes**: `MediaAttachment` への field 追加は `default=None` で既存テスト破壊を回避。`RenderedMedia` は `domain/media.py` に同居（純粋値オブジェクトゆえ）、frozen dataclass。`render_status` は文字列 enum 風（Domain では `frozenset({"ok", "passthrough", "skipped", "failed"})` を `__post_init__` で検証、Domain は型しか持たず文字列値そのものの意味は UseCase / Adapter 側で定義）。
**Status**: Complete

## Stage 7.2: UseCase — MediaRenderer Port + mime-routing
**Goal**: `MediaRenderer` Port を定義し、`RenderAuthorizedMedia` UseCase が download 済み media を mime に応じて routing する。
**Layer**: UseCase
**Success Criteria**: fake `MediaRenderer` で全分岐検証、実 I/O ゼロ。`MediaDownloadResult` の延長として `RenderedMedia` を返す。
**Tests** (Red → Green):
  - `RenderAuthorizedMedia`: image/* → render を呼ばず `render_status="passthrough"` を返す、PDF も同様
  - `RenderAuthorizedMedia`: docx/pptx/xlsx → fake renderer が呼ばれ `render_status="ok"` + `rendered_text` 非 null
  - `RenderAuthorizedMedia`: 未対応 mime（audio/mp3 等） → renderer 呼ばず `render_status="skipped"`、`rendered_text=None`
  - `RenderAuthorizedMedia`: `skip_reason` が立っている media（size 超過で download skip）は render も skip（`render_status="skipped"` の上位概念として skip_reason を継承）
**Implementation Notes**: mime-routing を Port の中に閉じ込めるか、UseCase 側に持つかで分岐 → **UseCase 側に持つ**（設計分岐 #1 の判断）。理由: Port はあくまで「与えられた mime を md 化する」決定論的責務に純化、何を render するかの policy は UseCase 層。`RenderAuthorizedMedia.execute(download_results) -> List[RenderResult]` で `MediaDownloadResult` を入力に取り、download skip された media は素通り（render_status="skipped"）。`fakes.py` に `FakeMediaRenderer` 追加（呼び出し回数記録 / 例外注入 / 戻り値カスタマイズ）。`_route_mime` は純関数として UseCase モジュール冒頭に置き、`_PASSTHROUGH_MIME_PREFIXES` / `_PASSTHROUGH_MIME_EXACT` / `_RENDER_MIME_EXACT` の三集合で mime を 3 状態に分類（その他は保守的に skipped）。
**Status**: Complete

## Stage 7.3: Interface — MarkitdownRenderer + emit 拡張
**Goal**: 実 markitdown ライブラリで docx / pptx / xlsx / html を md 化する Adapter と、emit JSON の `rendered_text` / `render_status` / `file_name` 出力。
**Layer**: Interface (Adapter)
**Success Criteria**: 実 markitdown を使った integration test と、HTTP モック相当の fake content での unit test 両方が green。`StdoutEventEmitter` が rendered_text / render_status / file_name を含めて出力、欠落フィールドは null で明示。
**Tests** (Red → Green):
  - `MarkitdownRenderer.render(media, local_path)`: 実 docx fixture（数行のテキスト含む）を渡し `RenderedMedia(rendered_text="...", render_status="ok")` を返す
  - `MarkitdownRenderer.render(media, local_path)`: 壊れた docx（zip 構造破損）を渡し、内部例外を catch して `RenderedMedia(rendered_text=None, render_status="failed")` を返す（クラッシュさせない）
  - `StdoutEventEmitter.emit()` が `rendered_text` / `render_status` / `file_name` を含めて出力、render_results が未指定なら全 media が `render_status=None` / `rendered_text=None` で出力（後方互換、Stage 6 までのテストを破壊しない）
**Implementation Notes**: `markitdown` 0.1.6 の API は `from markitdown import MarkItDown; md = MarkItDown(); result = md.convert(str(local_path)); rendered = result.text_content`。例外は広め（`Exception`）に catch して `render_status="failed"` 化、stderr に短い warning（file_id 先頭8桁のみ表示、絶対パスは出さない）。fixture は test 内で python-docx / openpyxl / python-pptx で動的生成（markitdown 依存として既に入る）。**実 markitdown 挙動の発見（Stage 7.3 着手時）**: garbage バイト列 (.docx 拡張子) でも markitdown は内部の magika ML model で plain text と判定し rendered_text にバイト列を返す（render_status="ok"）。本物の `failed` パスに入るのは空 .docx（BadZipFile）/ 存在しないファイル（FileNotFoundError）等の構造的失敗時のみ。この寛容性は L00473 分業の「Weave が意味のあるテキストか判断する」責務に整合的なため受容。
**Status**: Complete

## Stage 7.4: Infrastructure — pyproject + CLI 配線 + ドキュメント
**Goal**: `markitdown` 依存追加、`cmd_poll` / `cmd_watch` に renderer instantiation 配線、ROUTINE_PROMPT.md Step 5 一般化、README / SKILL.md / CHANGELOG 更新。
**Layer**: Infrastructure
**Success Criteria**: `validate-config` は変化なし（新 env なし）、`poll` / `watch` が download → render → emit を 1 サイクルで完了、ROUTINE_PROMPT.md に「`rendered_text` があればそれを使う / なければ `local_path` を `Read`」が記載される。
**Tests** (Red → Green):
  - `cmd_poll` が download → render → emit の順で実行、fake gateway / downloader / renderer 経由で全分岐確認
  - `cmd_watch` の loop 内でも renderer が download_uc と同様に loop 外で 1 回作って使い回し（接続コスト削減）
  - markitdown 未インストール環境では `import markitdown` が失敗するため、CLI 起動時に明確なエラー（"markitdown not installed, install via pip install markitdown"）で exit 2、もしくは `cmd_poll` 開始時に lazy import で検出
**Implementation Notes**: `pyproject.toml` の `dependencies` に `markitdown[docx,pptx,xlsx]>=0.1.6` 追加（extras で必要な mime に絞り、不要な依存を入れない）。**markitdown は内部で `python-docx` / `python-pptx` / `openpyxl` / `mammoth` / `magika`（ML model）/ `onnxruntime` 等を依存として持つ**（pip install --dry-run で実測、Stage 7.3 着手時に確認済み）。`media_enable_render` env は導入しない（YAGNI、Heavy モードと render は不可分とみなす）。ROUTINE_PROMPT.md Step 5 の JSON 例を更新、Failure modes に `render_failed` / `render_skipped` を追加。**Lazy import 実装**: `from adapters.render.markitdown_renderer import MarkitdownRenderer` を `cmd_poll` / `cmd_watch` の Heavy モード分岐内で行うことで、`validate-config` / Medium モードでは markitdown 不要のまま。Stage 7.4 ではテスト戦略として Heavy モード E2E はスキップ（実 markitdown + file CDN mock の二重 transport 構築が過剰）、Medium モードで `render_status`/`rendered_text`/`file_name` が null で出る後方互換テストのみ追加。Heavy モード E2E は Stage 7.5 の実機検証に集約。

**3-Strike 予想ポイント**（後述の Stage 7 固有 3-Strike Rule 参照）

**Status**: Complete

## Stage 7.5: 統合テスト + ドキュメント Doc Complete + 実機 E2E
**Goal**: docx / pptx / xlsx の E2E（自分の bot にドキュメントを送る → `watch` → download → render → emit に `rendered_text` → Weave がそれを使って返信）を Cloud Routine 上で 1 往復成立させる。CHANGELOG / README / SKILL.md / ROUTINE_PROMPT.md を v0.3.0 で更新。
**Layer**: Infrastructure（運用統合）
**Success Criteria**: fresh session で `watch` 起動 → 自分の bot に docx 1 通 + caption "要約して" を送る → emit に `rendered_text` で md 化された内容が乗る → 親プロセス Weave が `rendered_text` を読んで要約返信 → Telegram に到達。pptx / xlsx も同等動作、render failure（壊れたファイル送信）の skip 動作も実測。
**Tests / 検証**:
  - E2E: docx + caption "要約して" → emit に `rendered_text` 非 null → Weave が md を読んで要約返信、Telegram で受信確認
  - E2E: pptx → mime_type=...presentationml.presentation で render → Weave 応答到達
  - E2E: xlsx（表データ）→ md 化（パイプ区切り表）→ Weave がデータ列を読んで応答
  - E2E: 壊れた docx 送信 → `render_status="failed"` で emit → Weave が「ファイルが壊れて読めない」旨を応答
  - E2E: mp3 / mp4 送信 → `render_status="skipped"` で emit → Weave が「音声/動画は現在未対応」旨を応答
**Implementation Notes**: Stage 5 / 6.5 同様、新 fresh session 起動が前提（Custom policy 反映と pyproject 更新の両方が新コンテナで反映）。CHANGELOG は [0.3.0] エントリで「MediaRenderer 抽象導入、markitdown でドキュメント系 mime の md 化、emit に rendered_text / render_status / file_name 追加」を記載。README の Quickstart に「docx を送って試す」一節を追記、env vars 表は変化なし。SKILL.md と ROUTINE_PROMPT.md は rendered_text の四状態を反映。
**Status**: In Progress（**Doc Complete** — CHANGELOG [0.3.0] / README Quickstart docx 試験 + 依存ツリー注記 / SKILL.md Daily Workflow render_status 五状態 + Security markitdown 寛容性認識 / ROUTINE_PROMPT.md Step 5 一般化、すべて 2026-05-27 着地。**Live E2E Pending** — docx/pptx/xlsx の Weave 要約往復・render failure skip・retention 動作は新 fresh session で別途、Stage 5 / 6.5 と同じ要件）

### Documentation Plan（Stage 7 追加分）

| ドキュメント | パス | 新規/更新/不要 | 計画内容 |
|---|---|---|---|
| `CHANGELOG.md` | `Expertises/TelegramSecretary/CHANGELOG.md` | 更新 | [0.3.0] - 2026-MM-DD に「MediaRenderer 抽象導入、markitdown でドキュメント系 mime の md 化、emit に `rendered_text` / `render_status` / `file_name` 追加、`MediaAttachment.file_name` 追加、`RenderedMedia` 値オブジェクト追加、`MarkitdownRenderer` Adapter 追加、`RenderAuthorizedMedia` UseCase 追加、pyproject に `markitdown` 依存追加」を記載 |
| `README.md` | `Expertises/TelegramSecretary/README.md` | 更新 | Quickstart に「docx / pptx / xlsx を送って試す」一節を追記。env vars 表は変化なし（新 env なし）。**markitdown 依存ツリー膨張（python-docx / python-pptx / openpyxl / beautifulsoup4 / lxml 等が入る）を明記** |
| `SKILL.md` | `Expertises/TelegramSecretary/SKILL.md` | 更新 | Daily Workflow Step 5 に「`rendered_text` があればそれを Weave が読む / なければ `Read` で `local_path` を開く / 両方なければメタのみ」を反映。render_status 四状態（ok / passthrough / skipped / failed）の説明追加 |
| `ROUTINE_PROMPT.md` | `Expertises/TelegramSecretary/ROUTINE_PROMPT.md` | 更新 | Step 5 の JSON 例を新スキーマに差し替え、`rendered_text` / `render_status` / `file_name` 三状態の処理分岐を明記。Failure modes に `render_failed` / `render_skipped` を追加 |
| `IMPLEMENTATION_PLAN.md` | （本ファイル） | 更新 | 本 Stage 7 セクション追加済み。Stage 7 全 5 段階完了後、Stage 5 / 6 と合わせて削除検討（現運用：イベント駆動開発の経緯として保持） |
| `pyproject.toml` | `Expertises/TelegramSecretary/pyproject.toml` | 更新 | `dependencies` に `markitdown>=0.0.1` 追加。再帰依存（python-docx / python-pptx / openpyxl / beautifulsoup4 / lxml 等）が入ることを README で明記 |

> 拡張レイヤーの最終棚卸しは Stage 7.5 着手時に `Explore` サブエージェントで再確認（SSoT 違反チェック含む）。

### Decision Priority Notes（Stage 7 固有、Testability > Readability > Consistency > Simplicity > Reversibility）

- **Port シグネチャ: `render(media, local_path) -> RenderedMedia` 単一 Port 採用**（設計分岐 #1）: mime 別に Port を分ける案（`DocxRenderer` / `PptxRenderer` 等）は Consistency（既存 Stage 6 の `MediaDownloader` Port が単一）と Simplicity を破る。markitdown が内部で mime 判定する以上、Adapter 側で mime-routing を内蔵せず、UseCase 層で「passthrough / render / skipped」の三分岐のみ持ち、render 対象は全て markitdown に渡す。**Testability** も単一 Port の fake で完結。
- **rendering 失敗ハンドリング: Adapter 内部 catch + flag 化採用**（設計分岐 #2）: 例外を UseCase 呼び出し側に伝播させる案は、UseCase の `RenderAuthorizedMedia.execute` が個別 media の失敗で全体中断するリスク（Reversibility 違反）。Stage 6 の `MediaSizeLimitExceeded` 同型の「フラグ化して emit、ブロックしない」スタンス（Consistency）を踏襲、Adapter 内部で広く `Exception` catch → `RenderedMedia(render_status="failed")` を返す。例外詳細は stderr に短い warning（file_id 先頭8桁のみ）、ログには絶対パス・token を残さない（Security）。
- **emit schema v2 維持、フィールド追加のみ**（設計分岐 #3）: v3 化案は既存 consumer（ROUTINE_PROMPT.md / Weave）と既存テストへの影響が大きい。v2 のまま `rendered_text` / `render_status` / `file_name` を追加し、欠落（=null）を Stage 6 までの emit として後方互換扱い。**Testability**（既存 emit テストが追加フィールド null 付きで通る）と **Reversibility**（後で v3 化は容易、逆は壊れる）の両立。
- **markitdown 単体採用、複数ライブラリの組み合わせは見送り**: docx は python-docx、pptx は python-pptx、xlsx は openpyxl で個別実装する案は、Adapter コードが mime ごとに分岐して膨らみ、Readability と Simplicity が破られる。markitdown は Microsoft 製・MIT・依存も全て MIT/BSD で許容可能、再帰依存膨張は事前ヒアリング確定済み。**唯一の懸念は markitdown のメンテナンス停止リスク**（Reversibility）だが、Port 抽象化により後で個別ライブラリ実装に差し替え可能。
- **`media_enable_render` env を導入しない**: Heavy / Medium の二分は download 単位、render は download した時点で常に試みる（Simplicity）。disable したい場合は `media_enable_download=false` で Medium モードに倒す（Reversibility）。将来 render が運用負荷化したら個別 disable env を YAGNI 解除して追加。
- **`file_name` の追加は document 限定だが全 media で出力**: photo は常に null だが、フィールド自体は全 media item に出す（Readability、「欠落≠未対応」の混乱回避、Stage 6 の `media: []` 明示出力と同型方針）。

### 3-Strike Rule（Stage 7 固有）

- **詰まりやすい予想ポイント**:
  1. **markitdown の API 変更 / バージョン非互換**: PyPI の `markitdown` は 2024 後半リリースの比較的新しいライブラリで、API（`MarkItDown().convert()` / `result.text_content`）が version で変動する可能性。再現性確保のため `pyproject.toml` で version 範囲指定が必要になるかも
  2. **markitdown の再帰依存膨張**: python-docx / python-pptx / openpyxl / beautifulsoup4 / lxml が連れてこられる。Cloud Routine の bootstrap が遅くなる、または依存衝突（既存 httpx との conflict 等）が発生する可能性
  3. **markitdown が内部で OS コマンドを呼ぶ挙動**: 特定 mime（古い .doc / .ppt 等）で外部 binary（libreoffice 等）に depend する場合、Cloud Routine 環境で動かない。事前確認が必須
  4. **大きな docx / xlsx の render 中に long-poll タイムアウト干渉**: Stage 6.3 と同型の懸念だが、render は download より CPU 重い可能性（特に 表データの xlsx）。`watch` のメインループ blocking で getUpdates が止まる可能性
- **代替アプローチ候補**:
  - markitdown API 変更 → Stage 7.4 着手前に PyPI で最新版確認 + 簡単な smoke test、version 固定 (`markitdown==0.x.y`) で安定化
  - 再帰依存膨張 → `pip install --dry-run` で依存ツリー確認、衝突あれば固定 version で回避、ブートストラップ時間は README に明記して許容
  - OS コマンド依存 → markitdown ドキュメントで「pure python」を確認、外部 binary に依存する形式（古い .doc 等）は最初から非対応として `render_status="skipped"` 扱い、対応 mime を docx / pptx / xlsx / html に限定
  - render 中の long-poll 干渉 → render を**別スレッド**に切り出し、`watch` のメインループは getUpdates に専念（Stage 6 の 3-Strike #2 と同型の対応）。最終手段として `media_enable_render` env を YAGNI 解除して追加、Medium モードに倒せるよう Reversibility 確保
- **ユーザーへ相談する判断ライン**: 上記いずれかで「markitdown 単体採用が成立せず・個別ライブラリへの fallback も Adapter 肥大化が許容外」となった時点で、`AskUserQuestion` で（markitdown 固定 version で続行 / 個別ライブラリ実装に分割 / docx 単体に絞って pptx/xlsx は別 Stage 化）の三択を提示。

### Security 追加項目（Stage 7 固有）

- **markitdown の OS コマンド実行リスク**: 事前確認で「pure python」を確認できれば許容、外部 binary に依存する形式は最初から非対応とし `render_status="skipped"`。コード調査は Stage 7.3 着手時に実施
- **render 失敗時の例外メッセージ秘匿**: 内部例外 catch 時に stderr に出すログは `file_id[:8]` のみ表示、`local_path` の絶対パスは出さない（Stage 6 の token redact と同型）
- **rendered_text の出力漏洩**: docx / xlsx 内に embed された秘密情報（パスワード / token 等）が `rendered_text` 経由で emit に乗る可能性 → Weave 側の出力漏洩スキャンを send-reply 前に強化（既存の token / env名 / system prompt 検査に加え、rendered_text 内の機密パターンも検査対象、ROUTINE_PROMPT.md Step 5 に明記）
- **mime_type は Telegram の自己申告**: Stage 6 の方針継承。markitdown も `convert()` 時に file 拡張子で mime を再判定するため、Telegram 申告との不一致時は markitdown 側の判定が優先される。**ただし render 結果の真偽は Weave が判断**（rename 攻撃で xlsx を docx として送られても、markitdown が xlsx として開いて md 化、Weave がその内容を読んで判断）
- **render 結果のディスク残存**: markitdown の中間ファイル（temp dir 等）が残らないことを確認。残る場合は `cleanup_media_dir` の対象に追加するか、別途 cleanup ロジックを Stage 7.4 で配線

---

## Stage 8: Outbound Media（write 系・生成物の送り返し）

> 追加日: 2026-05-27（Overview のみ）。**Stages 8.1〜8.5 に分割 2026-05-27（本計画）**。Stage 7（read 系＝受信メディアの中身理解）の対となる **write 系**。受信側の価値を優先して Stage 9（音声/動画 read）を先に実装したため、本 Stage は後続として詰める。番号は 7→8→9 だが、**実装順は 7→9 先行・8 は後続**。
>
> Stage 1-7,9 で確立した「Domain → UseCase → Interface → Infrastructure、依存は内向きのみ」「LLM 推論はコード外（親プロセス Weave）」「失敗はフラグ化・ブロックしない」「token/絶対パスはログ秘匿」の原則を全て継承する。送信ファイルの**生成**は Weave（親プロセス）が担い、本 Stage のコードは**決定論的な送信（sendPhoto / sendDocument）と送信前チェック**のみを担う。

### Overview（Stage 8 固有）

- **What**: Weave が起草・生成したコンテンツ（markdown レポート、図表画像、docx/PDF 等のファイル）を Telegram に送り返す **outbound media**。現状 `send-reply` は **text のみ**なので、ファイル添付送信（`sendPhoto` / `sendDocument`）を追加する。`OutboundMessage` に添付ファイルパスを持たせ、`MessageSink` Port を拡張、CLI `send-reply` に `--file`（複数可）を足す。送信前に**ファイルサイズ上限（50MB）**と**パス存在検証**を Domain で行う。
- **Why**: 公式 telegram plugin の `reply(files)`（画像→`sendPhoto`、その他→`sendDocument`、各 50MB）相当の送信能力。Weave が「図表を描いて送る」「md レポートを docx 化して返す」等の能動アウトプットを Telegram 経由で返せるようにする。受信（Stage 6/7/9）と送信（Stage 8）が揃って初めて双方向の対話チャネルが完成する。
- **Where**: 既存 `Expertises/TelegramSecretary/scripts/` 配下に追記。
  - Domain: `domain/models.py` の `OutboundMessage` に `attachments: list[OutboundAttachment]` 追加 / `domain/outbound.py` 新規（`OutboundAttachment` 値オブジェクト + `is_photo()` 判定 + サイズ/存在検証の純ロジック）
  - UseCase: `usecases/ports.py` の `MessageSink` Port に `send` 拡張（attachments を扱う）、`SendReply` は添付込み `OutboundMessage` を素通しする最小変更
  - Interface: `adapters/telegram/api_gateway.py` に `send_photo` / `send_document`（multipart/form-data アップロード、`send` の retry 機構を流用）
  - Infrastructure: `main.py` の `cmd_send_reply` に `--file` 引数（`action="append"`）と `--reply-to`（threading、採否は確認分岐）追加
- **Reference Patterns**:
  1. `scripts/usecases/send_reply.py` + `scripts/adapters/telegram/api_gateway.py::send`（sendMessage）— lease 再検証 → 送信 → offset advance → lease renew の骨格と、payload 組み立て＋`_request_with_retry` 流用。★最重要参照
  2. `scripts/adapters/telegram/media_downloader.py`（multipart ではないが file I/O + token 込み URL 秘匿 `from None` パターン）— 送信側の files アップロードでも token redact を踏襲
  3. 公式 telegram plugin（claude-plugins-official、ローカルには無いが IMPLEMENTATION_PLAN 既述）の `reply` tool（files 添付、拡張子で sendPhoto/sendDocument 分岐、threading は `reply_parameters`）— 振る舞いの参照（移植ではなく取捨選択）

### ⚠️ 確認が必要な判断分岐：対話 UX 装飾の取捨（実装着手前に確定）

公式 telegram plugin にある対話 UX 装飾を**全部移植しない**（加算バイアス注意・YAGNI）。TelegramSecretary の設計目的は **24-7 常駐秘書＝入力理解優先**であり、受信メディアの中身理解（Stage 6/7/9）では既に公式を超越している。装飾は選択的に入れる。本計画では Decision Priority（Testability > Readability > Consistency > Simplicity > Reversibility）に基づき以下の**デフォルト推奨**を置くが、**実装着手前に大環主に取捨を確認する**（`/plan-sdd` の AskUserQuestion 相当。本計画は read-only 立案のため確認は実装フェーズ冒頭で実施）：

| 装飾 | Telegram API | デフォルト推奨 | 採用パターンとしての理由 |
|---|---|---|---|
| **outbound file 送信** | `sendPhoto` / `sendDocument` | **採用（Stage 8 の中核、確認不要）** | write 系の本体。これが無いと Stage 8 が成立しない |
| **reply threading** | `reply_parameters`（`reply_to_message_id`） | **採用（8.4 に含む）** | `OutboundMessage.reply_to_message_id` は**既に Domain に存在**（models.py L75）。gateway の `send` も既に payload に載せている。CLI 引数を足すだけで追加コストほぼゼロ、複数ユーザ対話で「どの発言への返信か」が明確化。Consistency 上も既存実装の完成 |
| **typing インジケータ** | `sendChatAction` | **採用（8.4、軽量）** | watch→Monitor→Weave 起draft の数秒ラグの UX 緩和。stateless な 1 API 呼び出しで lease/offset に絡まず、Simplicity を破らない。秘書が「考えている」感の演出 |
| **markdownv2 フォーマット** | `send-reply` の `parse_mode` | **保留（YAGNI、要確認）** | MarkdownV2 はエスケープ要件が厳しく（`_*[]()~>#+-=|{}.!` の全エスケープ）、誤エスケープで送信失敗のリスク。プレーンテキストで実用上困っていないなら入れない。入れるなら escape 純関数を Domain に置きテスト必須 |
| **react（絵文字リアクション）** | `setMessageReaction` | **保留（YAGNI、要確認）** | ack には便利だが、send-reply で text を返せば ack は足りる。二重 ack は冗長。優先度低 |
| **edit_message（送信済み編集）** | `editMessageText` | **見送り（別 Stage 候補）** | 長時間タスクの進捗更新用途。message_id の状態管理が必要で stateless な現設計に状態を持ち込む（Reversibility/Simplicity 違反）。現状の単発応答モデルには不要。必要になったら独立 Stage で |

> **前提変容の検討（思考階梯）**: 上記6装飾は「公式が持っているから移植するか？」という共通前提を共有している。この前提を外すと「**Weave の秘書としての価値は入力理解（read 系）にあり、出力は file 送信さえあれば双方向性は完成する**」が急所として焼成される。よって中核（file 送信）+ ほぼ無コストで既存実装を完成させる2つ（threading / typing）を採用し、残り3つは YAGNI で保留/見送り、というのが本計画の判断。実装着手前にこの判断を大環主に提示して最終確定する。

### Stage 8 全体の Architecture 拡張

| Layer | Stage 8 で追加する責務 | 主要な型/関数 | 依存先 |
|---|---|---|---|
| **Domain** | 添付ファイルの値オブジェクトと送信前検証の純ロジック | `OutboundAttachment`（`path: Path` / `is_photo() -> bool`：拡張子 routing） / `OutboundMessage.attachments` field 追加 / `validate_attachments(attachments, max_bytes) -> None`（純関数、存在しないパス→`AttachmentNotFound`、サイズ超過→`AttachmentTooLarge`） | なし |
| **UseCase** | 添付込み送信のオーケストレーション（既存 SendReply の最小拡張） | `MessageSink` Port の `send(message: OutboundMessage)` 契約は不変（`OutboundMessage` に attachments が乗るだけ）。`SendReply.execute` は変更なし or 検証呼び出しを1行追加。送信は Port の向こう | Domain のみ |
| **Interface (Adapter)** | `sendPhoto` / `sendDocument` の multipart アップロード + `sendChatAction`（typing） | `TelegramApiGateway.send` を attachments 有無で分岐（無→従来 sendMessage、有→各 attachment を sendPhoto/sendDocument、本文 text は最初の attachment の caption か別 sendMessage）/ `send_chat_action(chat_id, action)` 追加。multipart は httpx `files=` で送る、token は URL path のみ・例外メッセージに残さない | UseCase, Domain |
| **Infrastructure** | CLI 引数追加（`--file` 複数可・`--reply-to`） + 送信前検証の配線 | `cmd_send_reply` に `--file`（`action="append"`）/ `--reply-to`（int, optional）/ typing 送信の有無。`OutboundAttachment` 構築と `validate_attachments` 呼び出し、サイズ上限は env `TELEGRAM_SECRETARY_OUTBOUND_MAX_SIZE_BYTES`（default 50MB） | 全層 |

### Dependency Direction

Stage 1-7,9 と同じく `Infrastructure → Interface → UseCase → Domain`（内向き）を厳守。`OutboundAttachment` は `Path` と拡張子判定のみ持ち、bytes は持たない（純粋性維持、Stage 6 の `MediaAttachment` が identifier のみ持つ方針と同型）。multipart アップロードの HTTP は Adapter（`TelegramApiGateway`）に閉じ込め、UseCase は `OutboundMessage` を Port に渡すだけ。

### 送信ルーティングと挙動

- **添付なし**: 従来どおり `sendMessage`（text のみ）。後方互換、既存 `send-reply` テスト破壊なし
- **添付あり**: 各 `OutboundAttachment` を拡張子で routing
  - 画像拡張子（`.jpg`/`.jpeg`/`.png`/`.webp`/`.gif`）→ `sendPhoto`
  - その他（`.docx`/`.pdf`/`.md`/`.xlsx` 等）→ `sendDocument`
- **text + 添付の組み合わせ**: 公式同様、本文 text は **最初の attachment の caption** に載せる（添付1件時）。添付複数 or text が長い（caption 上限 1024 字超）場合は text を別 `sendMessage` で先送り → 添付を続けて送る（実装着手時に caption 長判定で分岐、Stage 8.3 で確定）
- **reply threading（採用時）**: `reply_to_message_id` を sendMessage / sendPhoto / sendDocument の payload に載せる（gateway の `send` は既に対応済み、sendPhoto/sendDocument にも同様に追加）

### Stages

## Stage 8.1: Domain — OutboundAttachment 値オブジェクト + 送信前検証
**Goal**: 添付ファイルを Domain の純粋型として表現し、拡張子による photo/document 判定と、存在・サイズの送信前検証を純関数で提供する。
**Layer**: Domain
**Success Criteria**: `domain/outbound.py` の全テストが green、外部依存ゼロ（標準ライブラリのみ）。`OutboundMessage` に `attachments` を足しても既存 SendReply テストが `attachments=[]` 既定で green。
**Tests** (Red → Green) — *代表ケースのみ*:
  - `OutboundAttachment.is_photo()`: `.jpg`/`.png`/`.webp`/`.gif` で True、`.docx`/`.pdf`/`.md` で False（拡張子の大文字小文字を正規化）
  - `validate_attachments()`: 存在しないパスで `AttachmentNotFound`、サイズ > max_bytes で `AttachmentTooLarge`、正常パスで例外なし（実ファイルは tmp_path fixture で生成）
  - `OutboundMessage(chat_id, text, attachments=[...])` が frozen で、`attachments` 既定は空 list（既存の text-only 構築と後方互換）
**Implementation Notes**: `OutboundAttachment` は `frozen dataclass`、`path: Path` のみ保持。`is_photo()` は `_PHOTO_SUFFIXES = frozenset({".jpg",".jpeg",".png",".webp",".gif"})` で判定。`AttachmentNotFound` / `AttachmentTooLarge` は `domain/exceptions.py` に追加（既存 `MediaSizeLimitExceeded` と同型の Domain exception）。`OutboundMessage.attachments` は `field(default_factory=list)`（models.py の `TelegramUpdate.media` と同型）。検証は「送信前にコードで弾く」決定論的世界の責務であり LLM 判断ではない。
**Status**: Complete

## Stage 8.2: UseCase — MessageSink 契約拡張 + SendReply の添付対応
**Goal**: `OutboundMessage` に乗った attachments を `SendReply` が Port へ素通しできることを fake で保証し、送信前検証を UseCase 境界で1回行う。
**Layer**: UseCase
**Success Criteria**: fake `MessageSink` で添付付き送信の全分岐検証、実 I/O ゼロ。既存 SendReply テスト（lease 再検証・offset advance・送信失敗時据え置き）が無変更で green。
**Tests** (Red → Green) — *代表ケースのみ*:
  - `SendReply.execute`: attachments 付き `OutboundMessage` を渡すと、fake sink の `send` に attachments 込みで渡る（sink が記録した message.attachments を検証）→ 成功で offset advance + lease renew（既存挙動を添付ありでも維持）
  - `SendReply.execute`: 添付の検証失敗（`AttachmentTooLarge`）時は送信前に raise、sink は呼ばれず offset 据え置き（lease 再検証の後・送信の前に検証を置く）
  - 添付なし `OutboundMessage`（attachments=[]）で従来パスが変わらない（後方互換）
**Implementation Notes**: `MessageSink` Protocol の `send(message: OutboundMessage)` シグネチャは**変更なし**（`OutboundMessage` に attachments が乗るだけなので Port 契約は不変、Consistency 最良）。`SendReply.execute` に `validate_attachments(message.attachments, max_bytes)` の呼び出しを「lease 再検証の後・`sink.send` の前」に1行追加するか、検証を CLI 層に置くかは設計分岐 → **UseCase に置く**（Testability：fake sink で検証失敗パスを driver できる、送信副作用の前に弾くのが正しい順序）。`fakes.py` の `FakeMessageSink` は既に `message` を記録するので拡張不要（attachments は message に内包）。max_bytes は execute 引数で受ける（Domain を env に依存させない）。
**Status**: Complete

## Stage 8.3: Interface — sendPhoto / sendDocument multipart + sendChatAction
**Goal**: 実 Telegram API の `sendPhoto` / `sendDocument`（multipart/form-data）と `sendChatAction`（typing）を実装し、`TelegramApiGateway.send` を添付有無で分岐する。
**Layer**: Interface (Adapter)
**Success Criteria**: httpx モック（既存 `_install_mock_transport` 相当 or `MockTransport`）でテスト green。添付なしは従来 sendMessage、添付ありは拡張子で sendPhoto/sendDocument へ振る。token が URL path のみに現れ、例外メッセージ・ログに残らないこと（redact 確認テスト含む）。
**Tests** (Red → Green) — *代表ケースのみ*:
  - `TelegramApiGateway.send`: 添付なし → `/sendMessage` を呼ぶ（既存挙動、回帰防止）
  - `TelegramApiGateway.send`: 画像添付1件 + text → `/sendPhoto` に multipart（`photo` file + `caption` text）、document 添付 → `/sendDocument`（`document` file）。5xx → retry、401 → AuthFailureError（`_request_with_retry` 流用）
  - `TelegramApiGateway.send_chat_action(chat_id, "typing")`: `/sendChatAction` を呼ぶ、失敗は握り潰す or 軽い例外（typing は best-effort、本送信を妨げない）
  - 送信失敗時の例外メッセージに bot token が含まれない（regex で TOKEN redact 確認、media_downloader と同型）
**Implementation Notes**: multipart は httpx の `files={"photo": open(...)}` or `files={"document": (...)}` で送る（`json=` ではなく `files=` + `data=`）。`_request_with_retry` は `**kwargs` を素通しするので `files=`/`data=` 併用可（既存実装で対応済み、確認のみ）。本文 text の扱い: 添付1件なら caption に載せる、複数 or caption 上限超なら text を先に `sendMessage` してから添付送信（caption 上限 1024 を Domain or Adapter どちらで判定するかは Simplicity 優先で Adapter 内に閉じる）。`send_chat_action` は stateless・best-effort（例外は warn して継続、本応答の信頼性を下げない）。file handle は `with open()` で確実に close。token redact は `safe` な例外メッセージ（URL を載せない）で担保。
**Status**: Complete

## Stage 8.4: Infrastructure — CLI `--file` / `--reply-to` / typing 配線 + env
**Goal**: `cmd_send_reply` に `--file`（複数可）・`--reply-to`（threading、採用時）を追加し、送信前検証と typing 送信を配線。outbound サイズ上限の env を追加。
**Layer**: Infrastructure
**Success Criteria**: `send-reply --file <path>` が添付込みで送信（gateway モック）、`validate-config` は outbound env 込みで exit 0、添付なしの既存 `send-reply` が無変更で動く（後方互換）。
**Tests** (Red → Green) — *代表ケースのみ*:
  - `cmd_send_reply --text-file <t> --file <img>`: lease 検証 → `OutboundMessage(attachments=[OutboundAttachment(img)])` を構築 → sink 送信（mock transport が sendPhoto を受ける）、exit 0
  - `cmd_send_reply --file <存在しないpath>`: `AttachmentNotFound` を捕捉して exit 2（設定/入力不正）、送信しない
  - `Config.from_env`: `TELEGRAM_SECRETARY_OUTBOUND_MAX_SIZE_BYTES`（default 50MB=52428800）の parse、欠損は default、不正値は exit 2
  - `--reply-to <message_id>`（採用時）: `OutboundMessage.reply_to_message_id` に載る
**Implementation Notes**: `p_send.add_argument("--file", action="append", default=[], help=...)` で複数添付。`--reply-to` は採否確認後に追加（採用なら `type=int`）。`cmd_send_reply` で `OutboundAttachment` を組み立て、`validate_attachments` を呼ぶ前に lease 検証は維持（owner 二重防御は既存どおり）。typing は send 直前に `gateway.send_chat_action(chat_id, "typing")` を best-effort で1回（採用時）。env は `Config` に `outbound_max_size_bytes` 追加（`media_max_size_bytes` と同型の parse）。`AttachmentNotFound`/`AttachmentTooLarge` は exit 2（入力不正）にマップ。**実装着手前に「確認が必要な判断分岐」表の取捨を大環主に確定**してから markdownv2/react の要否を反映（保留なら本 Stage に入れない＝YAGNI）。
**Status**: Complete

## Stage 8.5: 統合テスト + ドキュメント + 実機 E2E
**Goal**: outbound file 送信の E2E（Weave が画像/docx を生成 → `send-reply --file` → Telegram に届く）を Cloud Routine 上で成立させる。CHANGELOG / README / SKILL.md / ROUTINE_PROMPT.md を v0.5.0 で更新。
**Layer**: Infrastructure（運用統合）
**Success Criteria**: fresh session で `send-reply --chat-id <id> --update-id <uid> --text-file <t> --file <生成画像>` → owner chat に画像 + caption が届く。docx/PDF も `sendDocument` で届く。サイズ超過（>50MB）は送信前に弾かれる。reply threading（採用時）で元メッセージへの返信として表示される。
**Tests / 検証**:
  - E2E: Weave が matplotlib 等で図表 png を生成 → `--file figure.png` → Telegram で画像受信、caption に本文
  - E2E: md レポート → docx 化（コード側 or Weave 起草）→ `--file report.docx` → `sendDocument` で受信
  - E2E: >50MB ファイル → `AttachmentTooLarge` で送信前 exit 2、Telegram には何も送られない
  - E2E（採用時）: `--reply-to <message_id>` で元発言への返信スレッドとして表示 / typing インジケータが応答前に数秒表示
**Implementation Notes**: Stage 5/6.5/7.5/9.7 同様、新 fresh session 起動が前提（Custom network policy 反映）。ROUTINE_PROMPT.md Step 5 の send-reply 節に「ファイルを送り返す場合は `--file <path>`（複数可）、画像は sendPhoto・他は sendDocument に自動振り分け」を追記。**出力漏洩スキャンを添付にも拡張**（Weave 生成物に token/env名/機密が混入していないか送信前に Weave 側で確認、ROUTINE_PROMPT に明記）。生成一時ファイルの cleanup（`/tmp` or `state/outbound/`）を Weave 側手順に含める。CHANGELOG は [0.5.0] で「Outbound Media: sendPhoto/sendDocument による生成物送り返し、reply threading、typing インジケータ（採用分のみ）」を記載。
**Status**: In Progress（**Doc Complete** — CHANGELOG [0.5.0] / README env+Quickstart+Subcommands / SKILL Daily Workflow+Subcommands+env+Security / ROUTINE_PROMPT send-reply --file+threading+漏洩スキャン+Failure modes、すべて 2026-05-27 着地。**Live E2E 実施 2026-05-27（大環主目視、5ケース成立）** — 画像送り返し(sendPhoto+caption) / docx 送り返し(sendDocument) / >50MB 送信前弾き(exit 2、Telegram 未達) / reply threading / typing。E2E で **emit に message_id 欠落（threading 入力源が Weave に届かない）** と **network error 経路の token redact 未検証** を発見 → **v0.5.1 で修正**（emit に message_id 追加 + 全送信経路の network error redact、279 passed）。残: caption 上限・複数 --file の E2E）

### Documentation Plan（Stage 8 追加分）

#### 基本セット（毎回確認）

| ドキュメント | パス | 新規/更新/不要 | 計画内容 / 理由 |
|---|---|---|---|
| `README.md` | `Expertises/TelegramSecretary/README.md` | 更新 | Quickstart に「生成物を送り返す（`send-reply --file`）」一節を追記。env vars 表に `TELEGRAM_SECRETARY_OUTBOUND_MAX_SIZE_BYTES`（既定 50MB）追加。Subcommands 表の `send-reply` 行に `--file`/`--reply-to` を反映 |
| `CHANGELOG.md` | `Expertises/TelegramSecretary/CHANGELOG.md` | 更新 | [0.5.0] - 2026-MM-DD に「Outbound Media: `sendPhoto`/`sendDocument` 添付送信、`OutboundAttachment` Domain 追加、`send` Adapter の multipart 分岐、reply threading / typing（採用分）、`send-reply --file` CLI、`TELEGRAM_SECRETARY_OUTBOUND_MAX_SIZE_BYTES` env 追加」を記載 |
| `IMPLEMENTATION_PLAN.md` | （本ファイル） | 更新 | 本 Stage 8 を 8.1〜8.5 に分割（本計画）。Stage 5/6/7/8/9 全完了後にまとめて削除検討（現運用：イベント駆動開発の経緯として保持） |

#### 拡張レイヤー

| ドキュメント | パス | 新規/更新/不要 | 計画内容 / 理由 |
|---|---|---|---|
| `SKILL.md` | `Expertises/TelegramSecretary/SKILL.md` | 更新 | Subcommands 表の `send-reply` に `--file`/`--reply-to` を反映。Daily Workflow Step 5 に「生成物は `--file` で送り返す」を追加。env vars 表に outbound size 上限を追加。Security に「outbound ファイルの漏洩スキャン・サイズ上限・生成一時ファイル cleanup」を追加 |
| `ROUTINE_PROMPT.md` | `Expertises/TelegramSecretary/ROUTINE_PROMPT.md` | 更新 | Step 5 の send-reply 節に `--file`（sendPhoto/sendDocument 自動振り分け）と reply threading（採用時）を追記。出力漏洩スキャンの対象に「添付生成物」を明記。Failure modes に `attachment_too_large` / `attachment_not_found` を追加 |
| `pyproject.toml` | `Expertises/TelegramSecretary/pyproject.toml` | 要確認 | `httpx` は既存依存で multipart 対応済み（追加ライブラリ不要）。図表生成を**コード側**で行うなら matplotlib 等を足す判断が要るが、生成は Weave 起草が原則なので**おそらく不要**。Stage 8.3 着手時に確認 |
| `CLAUDE.md`（root） | `homunculus/Weave/CLAUDE.md` | 不要 | TelegramSecretary は「利用可能ペルソナ」に未掲載（NewsCaster/BlueberrySprite と異なり Cloud Routine 本番投入前）。Stage 8 単体では掲載タイミングではない。E2E 完了・本番投入時にまとめて追加判断 |
| `.gitignore` | `homunculus/Weave/.gitignore` | 確認のみ | 生成一時ファイルを `state/outbound/` に置く場合、既存の `Expertises/*/state/` で除外済み。Stage 8.5 で実測確認 |

> 拡張レイヤーの最終棚卸しは Stage 8.5 着手時に `Explore` サブエージェントで再確認（SSoT 違反チェック含む）。本計画立案時は read-only 調査で既存ドキュメント構成（README/CHANGELOG/SKILL/ROUTINE_PROMPT の4本 + pyproject + .gitignore）を確認済み、Stage 6/7/9 と同じ更新パターン。

### Decision Priority Notes（Stage 8 固有、Testability > Readability > Consistency > Simplicity > Reversibility）

- **`MessageSink` Port 契約を変えず `OutboundMessage` に attachments を載せる**（最大の分岐）: `send` シグネチャに files 引数を足す案 / 新 `OutboundMediaSink` Port を分ける案と比較。`OutboundMessage` に内包すれば Port 契約不変（**Consistency** 最良、既存 `SendReply` の DI が変わらない）、fake sink も無変更（**Testability**）。新 Port 分離は YAGNI（送信先は1つ、分ける必要なし）。
- **送信前検証を UseCase 境界に置く**（設計分岐）: CLI 層 vs UseCase。送信副作用の前に弾くのが正しい順序で、fake sink で検証失敗パスを driver できる（**Testability**）。Domain の `validate_attachments` 純関数を UseCase が呼ぶ＝決定論的世界の責務をコードに閉じる（LLM 判断ではない）。
- **対話 UX 装飾は中核 + 低コスト2つに絞り、残りは YAGNI 保留**（最大の取捨）: 「公式が持つから移植」前提を外し、「秘書の価値は read 系・write は file 送信で双方向完成」を急所として焼成（前提変容パターン）。file 送信（中核）+ threading（既存 Domain 実装の完成、ほぼ無コスト）+ typing（stateless 軽量）を採用、markdownv2/react は YAGNI 保留、edit_message は状態持ち込みのため見送り（**Simplicity/Reversibility**：後で足すのは容易、状態を持ち込むと戻すのは壊れる）。
- **`OutboundAttachment` は Path のみ・bytes を持たない**: Stage 6 `MediaAttachment` の identifier-only 方針と同型。bytes は Adapter の送信時に `open()` で読む（**Testability**：Domain で bytes 比較を避ける、純粋性維持）。
- **multipart は httpx 標準機能で・追加依存なし**: `files=` は httpx に既にある。新ライブラリを足さない（**Simplicity**、OPS.md「AI 提案ライブラリを鵜呑みにしない」とも整合）。

### 3-Strike Rule（Stage 8 固有）

- **詰まりやすい予想ポイント**:
  1. **text + 添付の組み合わせ仕様**: caption に載せるか別 sendMessage か、caption 1024 字上限、複数添付時の順序・media group（`sendMediaGroup`）の要否で分岐が膨らむ
  2. **multipart アップロードの httpx 作法**: `files=` と `data=`（chat_id 等）の併用、`_request_with_retry` の `**kwargs` 素通しが multipart で意図通り動くか、retry 時に file handle が消費済みで再送できない問題
  3. **token redact の漏れ**: sendPhoto/sendDocument の URL に token が入る、httpx の例外（`HTTPStatusError` 等）が URL を含んで漏れる
  4. **送信ファイルサイズと Telegram 実上限**: 公式は 50MB だが bot API の実上限・写真と document で上限が異なる（photo は 10MB 程度の別制限がある）可能性
- **代替アプローチ候補**:
  - text+添付仕様 → まず「添付1件 + caption」の最小形だけ実装（複数添付・media group は YAGNI で後回し）、caption 上限超は text 別送 sendMessage に倒す
  - multipart retry → file handle を bytes に読み切ってから `files=` に渡す（retry で再利用可能に）、`_request_with_retry` がそのまま使えなければ送信専用の薄い retry を Adapter 内に
  - token redact → media_downloader の `raise ... from None` パターンを踏襲、送信失敗例外は URL を載せず `chat_id`/status のみ、redact 確認テストを Stage 8.3 で必ず書く
  - サイズ上限 → Bot API ドキュメントで photo/document の実上限を確認、photo が小さいなら大きい画像は sendDocument に倒す（Telegram 公式 plugin の挙動を踏襲）
- **ユーザーへ相談する判断ライン**: 上記いずれかで「multipart 送信が安定せず・retry 設計が既存機構と噛み合わない」となった時点で、`AskUserQuestion` で（送信専用 retry を別実装 / 添付1件・caption のみの最小形に絞る / 送信は best-effort で retry 無し）の三択を提示。また**実装着手前に UX 装飾の取捨**（前述の表）を必ず確認。

### Security 追加項目（Stage 8 固有、OPS.md §1・§7 継承）

- **outbound ファイルの漏洩スキャン**: Weave 生成物（md/docx/画像/PDF）に token / env名 / system prompt / 機密が混入していないか**送信前**に Weave 側で確認（text の出力漏洩スキャンを添付にも拡張、ROUTINE_PROMPT Step 5 に明記）。コード側はバイナリの中身まで検査しない（決定論的に不可能）＝Weave の判断責務（L00473 分業）
- **送信ファイルサイズ上限（事故防止）**: `TELEGRAM_SECRETARY_OUTBOUND_MAX_SIZE_BYTES`（default 50MB）超過は送信前に `AttachmentTooLarge` で弾く（生成物の肥大による誤送信・コスト事故防止）
- **token 込み URL のログ秘匿**: `sendPhoto`/`sendDocument` の URL（`/bot<TOKEN>/sendPhoto`）の TOKEN を例外メッセージ・stderr・ログに残さない（Stage 6 の media_downloader と同型、`from None` で chain 切り、redact 確認テスト必須）
- **送信先 chat_id の検証**: send-reply は既に lease owner 検証 + chat_id 指定だが、添付送信でも**認可済み chat にのみ送る**前提を維持（owner の chat_id 起源の応答であること、IDOR 防止）
- **生成一時ファイルの cleanup**: 送信後の一時ファイル（`/tmp/*.png` 等）を残さない。`state/outbound/` に置くなら既存 `cleanup_media_dir` の retention 対象に含めるか別 cleanup を Stage 8.4/8.5 で配線（機密生成物の長期残存防止）
- **添付パスのトラバーサル注意**: `--file` に渡されるパスは Weave（信頼済み親プロセス）起源だが、`validate_attachments` で存在確認のみ行い、シンボリックリンク経由の意図しないファイル送信に留意（運用上は Weave が起草した生成物のみを渡す前提）

**Status**: 実装完了（Stages 8.1〜8.4 コード Red→Green 完了、回帰ゼロ。8.5 Doc Complete + **Live E2E 5ケース成立（2026-05-27 大環主目視）**。E2E 発見の emit message_id 欠落 / network error redact を **v0.5.1 で修正、279 passed**。対話 UX 装飾は中核+threading+typing 採用・markdownv2/react/edit_message 見送りで大環主確定済み 2026-05-27）

---

## Stage 9: Native Voice/Audio/Video Inbox（音声/動画のネイティブ受信と中身理解）

> 追加日: 2026-05-27。Stage 6（photo/document 受信・download・emit v2）と Stage 7（MediaRenderer によるドキュメント md 化）の上に、Telegram の voice / audio / video / video_note を受信し、音声は STT で transcript 化（中身理解）、動画は段階的（①音声トラック transcript ②key frame Vision）に扱う。STT は親プロセス Weave ではなくローカル STT エンジンで決定論的に行い（L00473 分業：スキル=決定論的 fetch/render、Weave=判断と推論）、Stage 7 の `MediaRenderer` 抽象に「音声→transcript も render の一種」として乗せる。公式 telegram plugin（claude-plugins-official）は voice/audio/video を file_id forward + download までしか行わず**中身理解の経路を持たない**——本 Stage はそこを超える。

### 設計方針の確定事項（2026-05-27 大環主決裁）

| 論点 | 決定 | 根拠 |
|---|---|---|
| 中身理解の射程 | 音声=transcript / 動画=段階的（①音声トラック transcript ②key frame Vision） | 0→1 の価値最大、動画フル解析は重いので後 |
| STT エンジン第一候補 | **Moonshine 日本語 (Base 58M)** | 「無いと有るの違いが最大、品質は後」（大環主）。超軽量58M・約100x高速・オフライン・Cloud Routine bootstrap 最小 |
| STT 品質向上の差し替え先 | `kotoba-whisper-v2.0-faster`（faster-whisper/CTranslate2、日本語 large-v3 超・6.3x） | `MediaRenderer` Port 抽象で差し替え容易（Reversibility）。Moonshine CER 13.62% が業務に不足と分かれば移行 |
| 受信基盤と STT の分離 | Stage 9 を 9.1-9.3（受信基盤・STT非依存・公式同等）と 9.4-9.6（STT・動画）に分割 | 受信認識は STT 方式に依存しない。9.1-9.3 だけで「無い→有る」を達成 |

### 実コードアンカー（2026-05-27 実読確認、机上計画→補正だらけ回避）

- `MediaAttachment.kind` は文字列（現状 `"photo"|"document"`）。拡張は `from_*_api` 追加のみで**構造変更不要**（[domain/media.py](./scripts/domain/media.py)）
- `TelegramUpdate.from_api` は photo/document を抽出（[domain/models.py](./scripts/domain/models.py) L35-42）。voice/audio/video/video_note を同所に追加
- **音声 transcript は `RenderedMedia.rendered_text` に乗せ `render_status="ok"`**。emit スキーマ（[emitter.py](./scripts/adapters/state/emitter.py) payload v2）も ROUTINE_PROMPT Step 5（rendered_text 処理）も **Stage 7 の枠そのまま＝変更ゼロ**
- `MediaRenderer` Port（`render(media, local_path) -> RenderedMedia`、[usecases/ports.py](./scripts/usecases/ports.py)）を音声にも流用。`MoonshineTranscriber` が同契約を実装し、内部で ffmpeg(OGG→16kHz wav)→Moonshine 推論を閉じ込める
- `_VALID_RENDER_STATUSES`（ok/passthrough/skipped/failed）は音声にも流用、**新状態不要**。transcript と md の区別は `media.kind` で行う（追加フィールド不要）
- mime-routing は `usecases/render_authorized_media.py` の `_route_mime`（Stage 7.2）を拡張：現状 `audio/* video/*` → `skipped` を render 対象へ。複数 Renderer（Markitdown / Moonshine）を mime で選択

### Overview（Stage 9 固有）

- **What**: Telegram の voice（ボイスメモ OGG/OPUS）/ audio（音楽 mp3 等）/ video（mp4）/ video_note（丸いビデオメッセージ）を受信し `media[]` に kind 追加。音声は Moonshine で transcript 化して `rendered_text` に乗せ、動画は音声トラックを transcript ＋ key frame を Stage 6 photo パイプライン経由で Vision。
- **Why**: 現状 text/photo/document/render(docx等) まで。大環主の業務入力には voice メモ（移動中の指示・現場音声）が多く、24-7 常駐秘書の入力射程を音声へ拡張する。公式 plugin すら中身理解しない領域を取りに行く。
- **Where**: 既存 `scripts/` 配下。新規: `usecases/transcribe` 系（または `render_authorized_media` 拡張）、`adapters/transcribe/moonshine_transcriber.py`、`adapters/audio/ffmpeg_preprocessor.py`（OGG→wav）、テスト一式。`pyproject.toml` に moonshine 系依存追加。
- **Reference Patterns**:
  1. Stage 7 `MediaRenderer` / `RenderAuthorizedMedia` / `MarkitdownRenderer` — `AudioTranscriber` 専用 Port を作らず **MediaRenderer 実装追加**（`MoonshineTranscriber`）、routing は `_route_mime` 拡張
  2. Stage 6 `MediaAttachment.from_*_api` / `from_api` / `DownloadAuthorizedMedia` — voice/audio/video の `from_*_api` と download 流用
  3. Stage 6 photo eager download + Read Vision — 動画 key frame を同じ photo パイプラインへ流す

### Architecture 拡張（層ごと）

| Layer | Stage 9 で追加する責務 | 主要な型/関数 | 依存先 |
|---|---|---|---|
| **Domain** | `MediaAttachment` に voice/audio/video/video_note の kind と from_*_api | `from_voice_api` / `from_audio_api` / `from_video_api` / `from_video_note_api` | なし |
| **UseCase** | from_api 抽出拡張、`_route_mime` に audio/video、複数 Renderer 選択 | `TelegramUpdate.from_api` 拡張、`RenderAuthorizedMedia` の renderer 選択ロジック | Domain |
| **Interface (Adapter)** | Moonshine 実装、ffmpeg 前処理 | `MoonshineTranscriber`（`MediaRenderer` 実装）、`FfmpegAudioPreprocessor`（OGG→16kHz wav） | UseCase, Domain |
| **Infrastructure** | moonshine/ffmpeg 依存、CLI 配線、モデルDL | `pyproject.toml` に moonshine 系、`cmd_poll`/`cmd_watch` の renderer 選択配線、bootstrap で ffmpeg 確認 | 全層 |

### Dependency Direction
Stage 1-7 と同じく `Infrastructure → Interface → UseCase → Domain`（内向き）厳守。`MoonshineTranscriber` は `MediaRenderer` Port 契約を満たし、ffmpeg/moonshine 呼び出しは Adapter 内部に閉じ込める。UseCase は mime-routing と Port 呼び出しのみ。

### emit スキーマ（**変更なし** — Stage 7 の rendered_text/render_status 再利用）
音声 transcript は `rendered_text`、状態は `render_status`（"ok"/"failed"/"skipped"）で表現。payload v2 のフィールド追加すら不要。Weave 側は `media.kind`（voice/audio/video）で「transcript か md か」を判別。

### メディア種別 routing 表（Stage 9 射程）

| メディア | Telegram形式 | 9.1-9.3 受信基盤 | 9.4-9.6 中身理解 |
|---|---|---|---|
| voice | OGG/OPUS | kind=voice・DL保存・emit | ffmpeg→wav→Moonshine(ja)→transcript を rendered_text |
| audio | mp3/m4a 等 | kind=audio・DL保存・emit | 同上 |
| video | mp4 | kind=video・DL保存・emit | 9.6: 音声トラック→transcript ＋ key frame→Stage6 Vision |
| video_note | mp4 | kind=video_note・DL保存・emit | 同上（9.6） |
| sticker | webp/tgs | kind=sticker・受信認識のみ（DL任意） | 射程外（中身理解しない） |

### Stages

## Stage 9.1: Domain — MediaAttachment に voice/audio/video/video_note kind 追加
**Goal**: voice / audio / video / video_note を Domain の純粋型として表現する from_*_api を追加。
**Layer**: Domain
**Success Criteria**: 既存 Domain テストが kind 拡張で破壊されず green、新規テスト green、外部依存ゼロ。
**Tests** (Red → Green):
  - `from_voice_api()`: Telegram の `voice`（`file_id` / `mime_type`=audio/ogg / `file_size` / `duration`）から kind="voice" を抽出、mime 欠落時 `"audio/ogg"` フォールバック
  - `from_audio_api()`: `audio`（`file_id` / `mime_type` / `file_size` / `file_name`）から kind="audio"、file_name 抽出
  - `from_video_api()`: `video`（`file_id` / `mime_type`=video/mp4 / `file_size`）から kind="video"
  - `from_video_note_api()`: `video_note`（`file_id` / `file_size`、mime は固定 `"video/mp4"`、file_name 概念なし）から kind="video_note"
**Implementation Notes**: `from_photo_api` / `from_document_api` のパターンに倣う。voice は `duration` を将来使う可能性があるが Domain では持たない（YAGNI、必要時追加）。kind 文字列拡張なので `MediaAttachment` の構造は不変。
**Status**: Complete（2026-05-27、4 つの from_*_api 実装、domain 76 passed）

## Stage 9.2: UseCase/Domain — from_api 抽出拡張 + download 流用
**Goal**: `TelegramUpdate.from_api` が voice/audio/video/video_note を `media[]` に抽出。既存 `DownloadAuthorizedMedia` がそのまま新 kind を download する。
**Layer**: UseCase（+ Domain の from_api）
**Success Criteria**: voice/audio/video 付き update が `media[]` に乗り、認可フィルタを通り、既存 downloader で保存される。fake で全分岐 green。
**Tests** (Red → Green):
  - `from_api`: voice 付き payload → `media=[MediaAttachment(kind="voice")]`、caption が text に統合
  - `from_api`: video 付き payload → kind="video"、audio/video_note も同様
  - `FetchAuthorizedUpdates`: 未認可 chat の voice update は破棄（既存 chat allowlist と整合）
  - `DownloadAuthorizedMedia`: voice の file_id を size 上限内で download（既存ロジック流用、kind 非依存を確認）
**Implementation Notes**: `from_api`（models.py L40-42 の document 抽出の隣）に voice/audio/video/video_note の抽出を追加。`DownloadAuthorizedMedia` は file_id ベースなので kind 非依存——**コード変更なしで動くことをテストで確認**（変更が要るなら最小限）。
**Status**: Complete（2026-05-27、from_api 抽出追加 + fetch/download の kind 非依存をテストで実証、全 232 passed・両 UseCase コード変更ゼロ）

## Stage 9.3: 受信基盤 E2E（公式同等・STT非依存・「無い→有る」達成）
**Goal**: voice/audio/video を受信→DL→保存→emit が 1 サイクルで成立（中身理解なし）。**この時点で公式 plugin と同等の受信射程に到達**。
**Layer**: Infrastructure（運用統合）
**Success Criteria**: fresh session で `watch` 起動 → 自分の bot に voice メモ送信 → emit に `kind="voice"` / `local_path` が乗る → 親プロセス Weave が「音声ファイルを受信（中身は未対応）」と認識し ack 応答。
**Tests / 検証**:
  - E2E: voice 送信 → emit に kind=voice・local_path 非null → Weave が受信を ack
  - E2E: video 送信 → kind=video で同様、video_note も
  - `cmd_poll` / `cmd_watch` が新 kind を download まで処理（render は次段）
**Implementation Notes**: ここまでは Stage 6 の photo/document パイプラインと完全同型。STT を一切含まないため、9.4 以降の方式決定を待たずに「voice/audio/video が届く」状態を確立できる。CHANGELOG は [0.4.0-rc] 等で受信基盤先行を記録。
**Status**: Complete（2026-05-27、test_main に Medium モードで voice/video が emit に kind 付きで乗る characterization test 追加、CLI レベルで受信基盤を実証、test_main 29 passed。実 Telegram E2E は fresh session 待ち）

## Stage 9.4: UseCase — 音声 mime-routing（_route_mime 拡張 + Renderer 選択）
**Goal**: `_route_mime` で `audio/*`・voice の OGG を render 対象（transcribe）に移し、`RenderAuthorizedMedia` が mime に応じて Markitdown / Moonshine を選ぶ。
**Layer**: UseCase
**Success Criteria**: fake transcriber で全分岐 green、実 I/O ゼロ。audio/voice → transcribe ルート、docx 等 → 既存 markitdown ルートが共存。
**Tests** (Red → Green):
  - `_route_mime`: `audio/ogg`・`audio/mpeg` → transcribe 対象（現状 skipped から変更）
  - `RenderAuthorizedMedia`: voice の MediaAttachment → fake transcriber が呼ばれ `render_status="ok"` + `rendered_text` 非null
  - docx → 従来通り markitdown renderer、選択が衝突しない
  - 動画 mime（video/mp4）は 9.4 段階では `skipped`（9.6 で対応）
**Implementation Notes**: renderer 選択は「mime → renderer インスタンス」の dict か、UseCase に複数 renderer を注入して mime で分岐。`MediaRenderer` Port 契約は不変。
**Status**: Complete（2026-05-27、`_route_mime` に audio/*→transcribe 追加 + `RenderAuthorizedMedia(renderer, transcriber=None)` で mime 分岐。transcriber 未注入時は audio→skipped に後方互換フォールバック。全 237→243 passed）

## Stage 9.5: Interface/Infra — MoonshineTranscriber + ffmpeg 前処理 + 音声 E2E
**Goal**: 実 Moonshine 日本語モデルで voice/audio を transcript 化する Adapter、OGG→16kHz wav 前処理、依存追加、音声 E2E。
**Layer**: Interface (Adapter) + Infrastructure
**Success Criteria**: 実音声 fixture で transcript が返る integration test green。fresh session で voice メモ → emit の `rendered_text` に日本語 transcript → Weave が内容を踏まえ応答 → Telegram 到達。
**Tests / 検証**:
  - `MoonshineTranscriber.render(media, local_path)`: 日本語音声 fixture → `RenderedMedia(rendered_text="...", render_status="ok")`、内部例外は `"failed"` に flag 化（markitdown_renderer と同型、クラッシュさせない）
  - `FfmpegAudioPreprocessor`: OGG → 16kHz mono wav 変換、中間ファイルは cleanup
  - E2E: voice "明日の現場は9時集合で" → transcript → Weave が内容に言及した返信
**Implementation Notes**: token/絶対パスはログ秘匿（Stage 6/7 同型）。

**実機検証結果（2026-05-27、Stage 9.5 スパイク、`DEV/verify_moonshine.py`）**:
- パッケージ: **`moonshine-voice 0.0.59`**（torch-free・56.5MB・onnxruntime 利用、`useful-moonshine`/`useful-moonshine-onnx` 系とは別物。後者は旧世代）
- 日本語モデル: `base-ja`（encoder 29.9M + decoder 104M + tokenizer ≒ 134MB、`python -m moonshine_voice.download --language ja` でランタイムDL、`%LOCALAPPDATA%/moonshine_voice/...` キャッシュ）
- API: `from moonshine_voice.transcriber import Transcriber` → `Transcriber(model_path, model_arch).transcribe_without_streaming(audio: List[float], 16000) -> Transcript`、`transcript.lines[].text` で取り出し。`model_path, model_arch = moonshine_voice.get_model_for_language("ja")`
- **OGG/mp3 → 16kHz mono float は PyAV（`av` 17.0.1、ffmpeg を wheel 内包＝システム ffmpeg 不要）でデコード成功**。当初 3-Strike #2（ffmpeg 不在）を PyAV で解消。`AudioResampler(format="flt", layout="mono", rate=16000)`
- 日本語精度: 建設業務語彙を正確認識（現場/集合/資材/搬入/9時/10時）。表記揺れ（漢字→かな・全角数字）は正常。**末尾欠落あり**（最終文が落ちる、Base 58M / CER 13.62% の限界）
- 速度: RTF 0.43〜0.69（リアルタイム超）

**ライセンス申し送り（重要）**: Moonshine Community License は「年商 $1M 未満は商用も無料」（"non-commercial" 表記だが実態は年商閾値）。**めぐる組（年商50-60億）の本番利用は Enterprise License（有償、contact@moonshine.ai）が必要**。テスト段階は Community で可（大環主決裁 2026-05-27、Claude もめぐる組では別アカウント契約の運用）。本番商用化前に Enterprise 契約 or `kotoba-whisper-v2.0`（Apache-2.0）へ `MediaRenderer` Port 差し替え。kotoba は Apache-2.0・年商無制限・日本語 large-v3 超（ReazonSpeech データセットのみ要独立確認）。

**残 3-Strike**: ①Cloud Routine（Linux）の `moonshine-voice` wheel 存在（win_amd64 で検証済み、Linux wheel を本番デプロイ時に確認、無ければ kotoba fallback）②末尾欠落の緩和（末尾に無音パディング、or `flags` 調整、or kotoba 切替）
**Status**: Complete（2026-05-27。`FfmpegAudioPreprocessor`(PyAV, 16kHz mono float, ffmpeg-free) + `MoonshineTranscriber`(MediaRenderer Port, lazy model load) 実装、main.py の cmd_poll/cmd_watch に transcriber 注入配線。本番 adapter で日本語 transcribe 実証（直接 API と同結果＝配線バグなし）。全 243 passed。残: ①Cloud Routine Linux wheel ②末尾欠落緩和 ③実 Telegram E2E（fresh session）)

## Stage 9.6: 動画段階的 — 音声トラック transcript + key frame Vision
**Goal**: video/video_note の音声トラックを ffmpeg 抽出→transcript、key frame を抽出して Stage 6 photo パイプライン経由で Weave が Vision 解釈。
**Layer**: Interface/Infra + UseCase
**Success Criteria**: video 送信 → emit に音声 transcript（rendered_text）＋ key frame の local_path（Read で Vision）→ Weave が音声と映像の両方に言及した返信。
**Tests / 検証**:
  - 音声トラック抽出 → 9.5 の transcriber 経路で transcript
  - key frame（先頭/中間 N枚）抽出 → photo と同じ download/Read 経路
  - E2E: 現場動画 → 音声 transcript + フレーム Vision の複合応答
**Implementation Notes**: 重い処理ゆえ long-poll 干渉に注意（3-Strike #4）。最悪 9.6 を後続 Stage に分離し、9.5（音声）までで一旦リリース。
**Status**: 9.6-i Complete（2026-05-27、`_route_mime` に video/* → transcribe 追加、`FfmpegAudioPreprocessor` が PyAV で mp4 の音声ストリームを decode することを実機実証＝`verify_video.py` で 108544 samples → 日本語 transcript 成功）。**9.6-ii（key frame Vision）は後続フェーズ**（emit 複数 media 拡張・PyAV video frame 抽出 → Stage 6 photo パイプライン統合が必要）

## Stage 9.7: 統合テスト + ドキュメント Doc Complete + 実機 E2E
**Goal**: voice/audio/video/video_note の E2E 一式と、CHANGELOG / README / SKILL.md / ROUTINE_PROMPT.md を v0.4.0 で更新。
**Layer**: Infrastructure（運用統合）
**Success Criteria**: fresh session で voice/audio/video の各 E2E、render failure（壊れた音声）の skip、retention 経過後の中間 wav 削除も実測。
**Tests / 検証**:
  - E2E: voice / audio / video / video_note の transcript・Vision 往復
  - E2E: 壊れた/無音声 → `render_status="failed"` or `"[No speech detected]"` で Weave に正直に
  - retention 実測: ffmpeg 中間 wav も `media_cleanup` 対象で削除
**Implementation Notes**: CHANGELOG は [0.4.0] で「Native Voice/Audio/Video Inbox: voice/audio/video/video_note 受信、Moonshine による音声 transcript、動画段階的対応、emit スキーマ無変更（rendered_text 再利用）」を記載。
**Status**: Doc Complete（2026-05-27、CHANGELOG [0.4.0] / README Quickstart+Stage 9 依存注記 / SKILL Daily Workflow+Security / ROUTINE_PROMPT render_status 四状態+media 処理+Failure modes / pyproject に moonshine-voice+av 追加。全 246 passed。**Live E2E Pending**: 実 Telegram での voice/audio/video 実送信は fresh session 待ち）

### Documentation Plan（Stage 9 追加分）

| ドキュメント | パス | 新規/更新/不要 | 計画内容 |
|---|---|---|---|
| `CHANGELOG.md` | `Expertises/TelegramSecretary/CHANGELOG.md` | 更新 | [0.4.0] に Native Voice/Audio/Video Inbox（Moonshine 音声 transcript、動画段階的、emit 無変更）を記載 |
| `README.md` | `Expertises/TelegramSecretary/README.md` | 更新 | Quickstart に「voice メモを送って試す」、依存に moonshine/ffmpeg、STT 差し替え（Moonshine→kotoba-whisper）を注記 |
| `SKILL.md` | `Expertises/TelegramSecretary/SKILL.md` | 更新 | Daily Workflow に「voice/audio の rendered_text=transcript を読む」、Security に「音声ローカル完結=外部送信ゼロ」 |
| `ROUTINE_PROMPT.md` | `Expertises/TelegramSecretary/ROUTINE_PROMPT.md` | 更新 | Step 5 は変更最小（rendered_text 処理が transcript にも効く）、Failure modes に `transcribe_failed` 追加 |
| `IMPLEMENTATION_PLAN.md` | （本ファイル） | 更新 | 本 Stage 9 追加済み。Stage 5/6/7/9 完了後にまとめて削除検討 |
| `pyproject.toml` | `Expertises/TelegramSecretary/pyproject.toml` | 更新 | moonshine 系 STT 依存追加（着手時に正確なパッケージ名確定） |

### Decision Priority Notes（Stage 9 固有、Testability > Readability > Consistency > Simplicity > Reversibility）

- **音声 transcript を rendered_text に統合（新フィールド/新 Port を作らない）**: Transcript 専用フィールドや AudioTranscriber 専用 Port を新設する案は emitter/ROUTINE_PROMPT/Weave 側処理の変更を誘発（Consistency/Simplicity 違反）。`RenderedMedia.rendered_text` 再利用で emit スキーマ無変更、`MediaRenderer` Port 流用で UseCase routing も `_route_mime` 拡張で済む。transcript/md は `media.kind` で区別。
- **STT 第一候補 Moonshine（品質より存在）**: 0→1 を最小 bootstrap で達成。Port 抽象で `kotoba-whisper-v2.0-faster` へ差し替え容易（Reversibility）。
- **受信基盤（9.1-9.3）と STT（9.4-9.6）の分離**: 受信認識は STT 非依存。9.1-9.3 だけで公式同等に到達。
- **ffmpeg 前処理を MoonshineTranscriber 内部に閉じ込め**: Port 契約 `render(media, local_path)->RenderedMedia` を保つ。OGG→wav は Adapter の実装詳細。
- **動画は段階的（9.6 で音声→transcript 先、keyframe Vision 後）**: フル動画理解は重い。音声トラック transcript が voice と同経路で価値先取り。

### 3-Strike Rule（Stage 9 固有）

- **詰まりやすい予想ポイント**:
  1. **Moonshine 日本語モデルの入手経路・パッケージ不明**: PyPI(`useful-moonshine` / `useful-moonshine-onnx`)が言語別モデルをどう配布するか、HF Hub 直 DL かが未確認。多言語対応は README で確認済みだが配布形態は要実測
  2. **Telegram voice=OGG/OPUS を Moonshine が直接食えない**: 16kHz wav 前処理が要る（ffmpeg）。ffmpeg が Cloud Routine コンテナに無い可能性
  3. **Moonshine 推論の Cloud Routine CPU 速度・bootstrap モデルDL**: 58M は軽いが、長 voice で long-poll 干渉の可能性
  4. **動画の音声抽出+keyframe が重く long-poll 干渉**: 9.6 のリスク
- **代替アプローチ候補**:
  - モデル入手不可/重い → `kotoba-whisper-v2.0-faster`（faster-whisper/CTranslate2）へ即フォールバック（日本語 large-v3 超）
  - OGG 前処理 → `FfmpegAudioPreprocessor` を 9.5 で標準化、ffmpeg は bootstrap で導入確認
  - 推論干渉 → transcribe を別スレッド、`watch` メインループは getUpdates 専念（Stage 6/7 の 3-Strike と同型）
  - 動画干渉 → 9.6 を後続 Stage に分離、9.5（音声）で一旦リリース
- **ユーザーへ相談する判断ライン**: Moonshine 入手・動作が成立せず kotoba-whisper fallback も Cloud Routine リソースで成立しない場合、`AskUserQuestion` で（Whisper API に課金許容で倒す / 音声受信のみ＝9.3 で止める / 別ホスティング）の三択を提示。

### Security 追加項目（Stage 9 固有）

- **認可済み chat のみ transcribe**: 既存 chat allowlist フィルタが先、未認可 chat の音声は Domain で破棄
- **size 上限（DoS 防御）**: 既存 `media_max_size_bytes` で超大音声/動画を skip
- **保持期限の自動削除**: 既存 `media_cleanup` の対象に **ffmpeg 中間 wav も追加**、機密音声の長期残存防止
- **Moonshine ローカル完結＝音声が外部に一切出ない（機密安全）**: Whisper API（外部送信）を第一候補にしなかった設計上の利点でもある。将来 Whisper API へ切り替える場合は「音声が OpenAI に渡る」プライバシー判断を別途必須化
- **transcript の出力漏洩スキャン**: 音声内の機密（パスワード読み上げ等）が transcript 経由で emit に乗る可能性 → send-reply 前の漏洩スキャン対象に transcript も含める（ROUTINE_PROMPT Step 5 に明記）
- **ffmpeg 中間ファイルの秘匿と cleanup**: 中間 wav の絶対パスをログに残さない、temp 残存防止

---

## Stage 10: PDF Render（passthrough → render 移行、Read tool 非依存化）

> 追加日: 2026-05-30。Stage 7（docx/pptx/xlsx → markitdown）・Stage 9（音声 → Moonshine transcript）に続く **MediaRenderer Port 第三実装**。Stage 6/7 で PDF は「`Read` tool が PDF 対応なので passthrough」としていたが、これは Weave の Read tool に依存する到達経路だった。L00473 分業（決定論的 fetch/render はスキル、判断は Weave）を PDF にも適用し、**テキスト層抽出を render 側に移して `rendered_text` で渡す＝Read tool 非依存**に一般化する。
>
> **番号の整理**: keep-alive の「Stage 10相当」は独立ファイル [`GOAL_KEEPALIVE_PLAN.md`](./GOAL_KEEPALIVE_PLAN.md)（別ライフサイクル track、v0.7.0 着地済み）。本 Stage 10 は media pipeline track（Stage 6/7/9 の系譜）の続きであり、両者は別 track の並行番号。

### Overview（Stage 10 固有）

- **What**: `application/pdf` を `_route_mime` の passthrough から外し、`PdfRenderer`（pdfplumber でテキスト層抽出）で `rendered_text` に本文を載せ `render_status="ok"`。テキスト層ゼロ（スキャン PDF 等）は `ok` + 空文字で「読めるテキスト無し」を正直に渡す。`RenderAuthorizedMedia` に `pdf_renderer` を DI（未注入なら PDF は skipped にフォールバック、transcriber 同型）。
- **Why**: passthrough は Weave の `Read` tool が PDF 対応であることに依存していた。render 側で本文を抽出すれば、Read tool の有無・PDF 対応状況に依存せず `rendered_text` 経路に一本化でき、docx/音声と処理が揃う。文字化け PDF（ToUnicode 不備）でもテキスト層を直接抽出する方が安定する可能性がある（Live E2E で確認）。
- **Where**: 新規 `scripts/adapters/render/pdf_renderer.py` + テスト。`usecases/render_authorized_media.py`（`_route_mime` に pdf 状態、`pdf_renderer` DI）、`scripts/main.py`（cmd_poll/cmd_watch 配線）、`pyproject.toml`（pdfplumber + dev reportlab）、`bootstrap.sh`（Heavy install）。

### 採用ライブラリ決定（smoke 比較、2026-05-30）

- **pdfplumber 0.11（MIT）を採用**。pymupdf（AGPL）は同等の日本語テキスト層抽出品質（reportlab 生成の日本語 PDF で両者の抽出結果が完全一致、複数ページも一致）だが、**配布ライセンス安全性で MIT を選択**。pymupdf は AGPL ゆえ配布物に持ち込むと制約が及ぶため不採用。
- pure-python（OS コマンド実行リスクなし）。`MediaRenderer` Port 構造は不変ゆえ、将来必要なら内部ライブラリのみ差し替え可能（Reversibility）。IMPLEMENTATION_PLAN 初稿の pymupdf 記述は本決定で pdfplumber に読み替え。

### Stages

## Stage 10.1: Interface — PdfRenderer（MediaRenderer Port 実装）
**Goal**: pdfplumber で PDF テキスト層を抽出する Adapter。moonshine_transcriber.py 同型（lazy import・内部 except→failed・file_id[:8] のみ stderr・テキスト層ゼロ→ok+空）。
**Success Criteria**: 実 PDF（reportlab 動的生成）の ASCII/日本語抽出 ok、空ページ→ok+空、壊れた/存在しないファイル→failed の unit test green。
**Tests**: 抽出 ok（ASCII・日本語）/ 空テキスト層→ok+空 / broken bytes→failed / missing file→failed。
**Status**: Complete（2026-05-30。pdfplumber は markitdown と異なり garbage に寛容でなく、構造破損は確実に failed パス。+5 tests）

## Stage 10.2: UseCase — _route_mime pdf 化 + pdf_renderer DI
**Goal**: `application/pdf` を `_PASSTHROUGH_MIME_EXACT` から除去し pdf ルート、`RenderAuthorizedMedia` に `pdf_renderer` 追加（None で skipped フォールバック）。
**Success Criteria**: fake で全分岐 green、実 I/O ゼロ。
**Tests**: `test_pdf_is_passthrough` を `test_pdf_calls_pdf_renderer` に置換 / pdf_renderer 未注入→skipped / download skip 継承。
**Status**: Complete（2026-05-30。transcriber 同型の routing + DI。net +5、計 339 passed）

## Stage 10.3: Infrastructure — pyproject + bootstrap + CLI 配線
**Goal**: pyproject に pdfplumber（本番）+ reportlab（dev fixture）、bootstrap Heavy に pdfplumber、cmd_poll/cmd_watch に PdfRenderer lazy import 注入。
**Success Criteria**: 全 unit test green を維持、Medium モードで PDF 依存を踏まない（lazy import）。
**Status**: Complete（2026-05-30。cmd_watch は ImportError 時 pdf_renderer=None で skipped フォールバック。統合配線サニティで実 PDF→ok+本文を確認）

## Stage 10.4: Live E2E（PASS、2026-05-30）
**Goal**: fresh session で `watch` 起動 → 自分の bot に PDF（テキスト PDF / 文字化け PDF / スキャン PDF）+ caption "要約して" を送る → emit に `rendered_text` → Weave が要約返信 → Telegram 到達。
**Success Criteria**: テキスト PDF の要約往復、文字化け PDF（ToUnicode 不備）での抽出品質確認、スキャン PDF で `rendered_text=""` → Weave が「テキスト層なし（画像 PDF）」応答。
**Status**: Complete（2026-05-30 Live E2E PASS、routine `telegram-secretary-stage10-e2e-pdf`、全 P1-P5 期待通り）:
- **P1 テキスト PDF**（資材物価スライド条項、3頁）→ `render_status=ok` + 本文完全抽出、**Read tool 不使用で全内容到達**（バンド表・不感帯まで構造保持）＝Stage 10 最重要目的 PASS
- **P2 文字化けしやすい PDF**（`フローリング.pdf` 3.0MB、Stage 9 で pypdf が文字化けした実物）→ pdfplumber は **mojibake ゼロでクリーン抽出**。ライブラリ選定（pypdf→pdfplumber/pdfminer.six 系）が文字化け問題そのものを解消。**三択申し送り（AGPL/OCR/text限定）は不発＝pdfplumber 確定**
- **P3 スキャン PDF**（`Tree_of_Life.pdf`）→ `ok` + 空 `rendered_text`、「テキスト層なし（画像 PDF の可能性）」応答。**大環主が follow-up で OCR を明示要求**＝スキャン PDF OCR の実需を実証（Stage 11 backlog 参照）
- **P4 壊れ PDF**（非 PDF を .pdf リネーム）→ `render_status=failed`（pdfplumber 厳格、rename 攻撃耐性）。stderr は `file_id[:8]` のみ＝絶対パス秘匿を実機確認
- **P5 retention** → 6+ 件処理後も PDF 中間 temp ゼロ（pdfplumber pure-python・in-memory）、`cleanup-media` exit 0
- 出力漏洩スキャン ✅（全返信、PDF 埋め込み機密の漏れなし）

### Documentation Plan（Stage 10 追加分）

| ドキュメント | パス | 新規/更新/不要 | 計画内容 |
|---|---|---|---|
| `CHANGELOG.md` | `Expertises/TelegramSecretary/CHANGELOG.md` | 更新 | [0.8.0] に PDF Render（passthrough→render、PdfRenderer、pdf_renderer DI、pdfplumber 依存）を記載 |
| `README.md` | 同上 | 更新 | Quickstart の render_status コメントを image=passthrough / PDF=ok（pdfplumber）に更新 |
| `SKILL.md` | 同上 | 更新 | Daily Workflow の rendered_text/passthrough 行に PDF render を反映、Security に pdfplumber（MIT・ローカル完結・pure-python）を追加 |
| `ROUTINE_PROMPT.md` | 同上 | 更新 | Step 5 の render_status 四状態と media[] 処理に PDF render（rendered_text 経路、空テキスト層の扱い）を反映 |
| `pyproject.toml` | 同上 | 更新 | `pdfplumber>=0.11`（本番）、dev extras に `reportlab>=4.0`（PDF fixture 生成） |
| `bootstrap.sh` | 同上 | 更新 | Heavy モードに pdfplumber install |
| `SECURITY.md` / `CLAUDE.md` | — | 不要 | ローカル完結・MIT・pure-python で新たな脅威面なし。SKILL Security 追記で十分 |

### Decision Priority Notes（Stage 10 固有、Testability > Readability > Consistency > Simplicity > Reversibility）

- **PDF 専用ルート + 専用 DI（pdf_renderer）採用**（transcriber 同型）: PDF を既存 markitdown `renderer` に通す案もあるが、採用ライブラリ（pdfplumber）が markitdown と別物ゆえ Port インスタンスを分けるのが Consistency（transcriber が別 DI なのと同型）。`_route_mime` に `pdf` 状態を足し、未注入は skipped フォールバックで後方互換（Reversibility）。
- **pdfplumber(MIT) > pymupdf(AGPL)**: 基本品質同等なら配布ライセンス安全を優先（上記決定参照）。
- **テキスト層ゼロ→ok+空（failed にしない）**: スキャン PDF は「失敗」ではなく「テキストが無い」。Moonshine の無音→ok+空 と同型。Weave が空を見て「画像 PDF の可能性」を判断する（L00473 分業）。
- **fixture は reportlab で動的生成**: docx を python-docx で生成するのと同型。git に巨大バイナリを置かない方針。reportlab は dev 依存（本番非依存）。

### 3-Strike Rule（Stage 10 固有）

- **詰まりやすい予想ポイント**: ①日本語 PDF の文字化け（ToUnicode 不備）で抽出が壊れる ②スキャン PDF（テキスト層皆無）で空が返る扱い ③pdfplumber の大 PDF での long-poll 干渉
- **代替アプローチ候補**: ①文字化けが pdfplumber で改善しなければ pymupdf(AGPL 明記の上)や OCR を Live E2E 後に検討、`MediaRenderer` Port 差し替えで対応 ②空 ok + Weave 警告で確定（OCR は YAGNI）③render を別スレッド化（Stage 7/9 の 3-Strike と同型）
- **ユーザーへ相談する判断ライン**: 文字化け PDF が pdfplumber で実用品質に達せず、AGPL 回避と品質がトレードオフになる場合、`AskUserQuestion` で（pymupdf 採用＝AGPL 受容 / OCR 追加 / テキスト PDF のみ対応）を提示。

### Security 追加項目（Stage 10 固有）

- **PDF ローカル完結**: pdfplumber はローカル抽出、PDF が外部に一切出ない（機密 PDF に安全）。
- **MIT・pure-python**: 配布安全、OS コマンド実行リスクなし（markitdown の外部 binary 懸念に相当するものが無い）。
- **失敗時の絶対パス秘匿**: 内部 except 時の stderr は `file_id[:8]` のみ（markitdown/Moonshine 同型、テストで検証）。
- **rendered_text の出力漏洩スキャン**: PDF 埋め込みの機密（パスワード等）が rendered_text 経由で emit に乗る可能性 → send-reply 前の漏洩スキャン対象（ROUTINE_PROMPT Step 5 既述の rendered_text 検査に含む）。
- **mime_type は Telegram 自己申告**: Stage 7 方針継承。pdfplumber は PDF 構造を実際に開くため、PDF でないものを pdf として送られても failed で弾かれる。

---

## Stage 11: PDF のマルチページ/画像対応（Vision 経路）

> 追加日: 2026-05-27（OCR 三択 backlog）。**2026-05-30 本計画で Vision 経路へ書き換え**（調査・対話で設計焼成済み、本 Stage はその計画化）。Stage 10（PDF テキスト層抽出）の続き＝media pipeline track（Stage 6/7/9/10 の系譜）。
>
> Stage 1-10 で確立した「Domain → UseCase → Interface → Infrastructure、依存は内向きのみ」「LLM 推論はコード外（応答生成は親プロセス Weave 本人、claude -p 禁止 L00473）」「失敗はフラグ化・ブロックしない（render_status / skip）」「token・絶対パスはログ秘匿（file_id[:8] のみ stderr）」を全て継承する。**画像化（決定論・安い）は本 Stage のコードが担い、Vision 解釈（高い・段階判断）は親プロセス Weave が ROUTINE_PROMPT Step 5 で担う** という分離が設計の核。

### Overview（Stage 11 固有）

- **What**: ① **画像 PDF**（テキスト層が空/薄いスキャン PDF・図面 PDF）を `pypdfium2` で全ページ画像化し、派生画像パスを `RenderedMedia.derived_image_paths` に載せて emit。Weave は ROUTINE_PROMPT Step 5 で**先頭1枚だけ Read/Vision** → 文書の性質と総ページ数を把握 → 残りページの要否を判断（明白なら確認なし、多量/不明なら send-reply で確認）→ 残りは**ディスク済みなので追加 render なしで Read するだけ**。② **テキスト PDF** は Stage 10 の全ページ抽出を維持しつつ**ページ境界マーカー（`--- page N ---`）を挿入**。③ 両経路共通に **`page_count`** を emit。
- **Why**: Stage 10.4 Live E2E P3 でスキャン PDF（`Tree_of_Life.pdf`）に対し大環主が follow-up で中身読取を実需要求。調査の結果 **OCR 経路ではなく Vision 経路を採用**（決裁 2026-05-30）。理由は (a) 建設ドメインの入力は図面・現場写真の比重が高く、画像化 → Vision のほうが OCR（テキスト復元）より広く効く、(b) **Stage 9.6-ii（動画 key frame Vision の複数 media emit 拡張）と `derived_image_paths` 基盤を共有でき投資効果が高い**、(c) `pypdfium2` は **pdfplumber>=0.11 の必須依存として同梱済み＝新規依存ゼロ・システムバイナリ不要**（Stage 11.3 で再確認）。OCR は Vision でも読めない低解像度スキャン用の**劣後 fallback として温存**（MediaRenderer Port 差し替えで後付け、本 Stage では実装しない）。
- **Where**: 既存 `Expertises/TelegramSecretary/scripts/` 配下に追記。**拡張対象**: `domain/media.py`（`RenderedMedia` に 2 field 追加）、`adapters/render/pdf_renderer.py`（テキスト/画像の二経路化）、`adapters/state/emitter.py`（`_build_media_payload` に 2 field）、`infrastructure/config.py`（cap env）、`main.py`（既存 PdfRenderer DI に env 受け渡し）、`ROUTINE_PROMPT.md`（Step 5 の段階 Vision 手順）。**新規ファイルは原則なし**（PdfRenderer 拡張で吸収）。派生画像は既存 `state_dir/media/` フラット直下に保存（既存 `cleanup_media_dir` の retention 対象にそのまま乗る）。
- **Reference Patterns**:
  1. `scripts/adapters/render/pdf_renderer.py`（Stage 10）— 拡張対象そのもの。lazy import・内部 except→failed・file_id[:8] のみ stderr・空テキスト層→ok+空 のスタンスを画像経路にも踏襲。★最重要
  2. `scripts/adapters/transcribe/moonshine_transcriber.py`（Stage 9.5）— Adapter 内部で「前処理（OGG→wav）→ 重い処理」を閉じ込め、`RenderedMedia` だけ返す型。PDF も「ラスタライズ → 派生画像保存」を Adapter 内部に閉じ込める同型
  3. `domain/media.py` の `MediaAttachment.file_name` 追加（Stage 7.1）— frozen dataclass への `default` 付き field 追加で既存構築を後方互換に保つパターン。`RenderedMedia` の 2 field 追加も同型
  4. `adapters/state/emitter.py::_build_media_payload`（Stage 6.3/7.3）— `media: []` / `file_name: null` の「欠落≠未対応、明示出力」規律。`derived_image_paths: []` / `page_count: null` も同規律

### 確定した設計（調査・対話で焼成済み、本 Stage はこれを計画化する）

| # | 決定 | 根拠 / 帰結 |
|---|---|---|
| 1 | **共通インフラ = `RenderedMedia` に `derived_image_paths: list[str]` 追加** | PDF と Stage 9.6-ii 動画 key frame が相乗りする基盤。`MediaRenderer` Port シグネチャ `render(media, local_path) -> RenderedMedia` は**不変**。emit は payload **v2 維持・フィールド追加のみ**（`derived_image_paths`, `page_count`） |
| 2 | **画像 PDF: `pypdfium2` で全ページ画像化** → `derived_image_paths` + `page_count` を emit | 画像化（決定論・安い）と Vision（高い・Weave 判断）を分離。cap は**超多ページの安全弁のみ**（env 可変）。Weave は先頭1枚 Read → 性質と総ページ把握 → 残り要否判断 → 残りはディスク済みを Read（追加 render なし） |
| 3 | **テキスト PDF: 全ページ抽出維持 + ページ境界マーカー挿入 + `page_count`** | 超長文の段階化は **YAGNI**（テキストはトークン経済が画像の 1/N で軽い）。位置把握はマーカーで足りる |
| 4 | **`page_count` は両経路共通メタ** | Weave が総量把握 → どこを読むか判断する枠組みを、テキスト（位置把握）と画像（段階 Vision）で一貫させる |
| 5 | **OCR は劣後 fallback として温存（本 Stage では実装しない）** | Vision でも読めない低解像度スキャン用。`MediaRenderer` Port 差し替えで後付け。調査結果は本ファイル末尾「OCR 申し送り」に退避 |

### Stage 11 全体の Architecture 拡張

| Layer | Stage 11 で追加する責務 | 主要な型/関数 | 依存先 |
|---|---|---|---|
| **Domain** | `RenderedMedia` に派生画像・ページ数のメタを追加（純粋値、bytes は持たない） | `RenderedMedia(derived_image_paths: list[str] = field(default_factory=list), page_count: Optional[int] = None)`。`__post_init__` の `render_status` 検証は不変（新 field は値域制約なし） | なし |
| **UseCase** | 変更最小。`_render_one` の pdf 分岐は既存どおり `pdf_renderer.render()` を呼ぶだけ（派生画像/ページ数は `RenderedMedia` に内包されて返る） | `RenderAuthorizedMedia`（**コード変更なし想定**、`RenderedMedia` の field 追加が透過。passthrough/skipped/failed 分岐で構築する `RenderedMedia` は default 引数で後方互換） | Domain のみ |
| **Interface (Adapter)** | `PdfRenderer` の二経路化 + emit 拡張 | `PdfRenderer.render()`: テキスト層抽出 → 薄ければ `pypdfium2` で全ページ画像化（cap 付き）→ `derived_image_paths`、テキスト経路は page マーカー挿入、両経路で `page_count`。`StdoutEventEmitter._build_media_payload` に `derived_image_paths` / `page_count` 追加（v2 維持） | UseCase, Domain |
| **Infrastructure** | cap の env + DI 受け渡し（cleanup は既存流用） | `Config` に `pdf_image_max_pages`（default 例: 20、超多ページ安全弁）追加。`cmd_poll` / `cmd_watch` の `PdfRenderer()` 構築に cap を渡す。`cleanup_media_dir` は**変更不要**（派生画像を `state_dir/media/` フラット直下に置けば既存 retention に乗る） | 全層 |

### Dependency Direction

Stage 1-10 と同じく `Infrastructure → Interface → UseCase → Domain`（内向き）を厳守。`RenderedMedia` は `derived_image_paths`（**str パスのみ**、bytes を持たない＝純粋性維持、Stage 6 `MediaAttachment` が identifier-only の方針と同型）。`pypdfium2` のラスタライズ・ファイル I/O は `PdfRenderer`（Adapter）に閉じ込め、UseCase は mime-routing と Port 呼び出しのみ。Vision 解釈は Port の外（親プロセス Weave、L00473 分業）。

### emit スキーマ拡張（v2 維持、フィールド追加のみ）

Stage 10 までの `media[]` item に**バージョン bump せず 2 field 追加**。欠落（=既存の空 list / null）を「Stage 10 までの emit」として後方互換扱い：

```json
{
  "v": 2,
  "update_id": 12345,
  "message_id": 678,
  "chat_id": 100,
  "text": "<caption + text 統合済み正規化本文>",
  "injection_flags": [],
  "media": [
    {
      "kind": "document",
      "file_id": "BAAD...",
      "file_name": "drawings.pdf",
      "mime_type": "application/pdf",
      "size": 3145728,
      "local_path": "<state_dir>/media/BAAD..._drawings.pdf",
      "skip_reason": null,
      "rendered_text": "",
      "render_status": "ok",
      "page_count": 12,
      "derived_image_paths": [
        "<state_dir>/media/BAAD..._page-001.png",
        "<state_dir>/media/BAAD..._page-002.png"
      ]
    }
  ]
}
```

- `page_count`: 両経路共通。null = PDF 以外 or Stage 10 までの emit（後方互換）
- `derived_image_paths`: **画像 PDF のみ非空**。テキスト PDF・非 PDF は `[]`（欠落ではなく明示、`media: []` と同規律）
- 画像 PDF の `rendered_text` は `""`（テキスト層なし）＋ `render_status="ok"`（Stage 10 で確定済みの「テキスト無しは失敗ではない」）。Weave は `derived_image_paths` の存在で「画像で読め」と判断
- テキスト PDF の `rendered_text` は page マーカー挿入済み本文、`derived_image_paths=[]`
- ROUTINE_PROMPT.md Step 5 を「`derived_image_paths` が非空なら**先頭1枚を Read**→性質と `page_count` 把握→残り要否判断（多量/不明なら send-reply で確認）→残りはディスク済みを Read」に拡張

### PDF 二経路の routing（PdfRenderer 内部）

| 入力 | 判定 | 出力 |
|---|---|---|
| テキスト層が**実質あり**（抽出長 > 闾値、env 可変想定） | テキスト経路 | `rendered_text`=page マーカー入り本文 / `render_status="ok"` / `page_count`=N / `derived_image_paths=[]` |
| テキスト層が**空/薄い**（スキャン・図面 PDF） | 画像経路 | `rendered_text=""` / `render_status="ok"` / `page_count`=N / `derived_image_paths`=全ページ画像（cap 内） |
| 画像化が cap 超 | 画像経路（cap 打ち切り） | `derived_image_paths`=先頭 cap 枚 / `page_count`=実 N（cap ではなく総数）→ Weave に「N ページ中 cap 枚を画像化」を伝える |
| `pypdfium2` 例外・壊れ PDF | failed | `rendered_text=None` / `render_status="failed"` / `page_count=None` / `derived_image_paths=[]`（Stage 10 同型、クラッシュしない） |

> **テキスト層「薄い」の閾値判定**は PdfRenderer 内部の決定論的責務（LLM 判断ではない）。初期は「全ページ抽出を strip して空なら画像経路」のシンプル判定から始め、図面 PDF で「テキスト層に枠線ラベルだけ薄く入る」ケースが顕在化したら閾値 env を YAGNI 解除（Stage 11.3 Decision Notes 参照）。

### Stages

## Stage 11.1: Domain — RenderedMedia に derived_image_paths + page_count 追加
**Goal**: `RenderedMedia` に派生画像パス list とページ数のメタを `default` 付きで追加し、既存の全構築箇所を後方互換に保つ。
**Layer**: Domain
**Success Criteria**: 既存 Domain テスト（`test_media.py` の RenderedMedia 群 + 全体）が 2 field 未指定で green、新規テスト green、外部依存ゼロ（標準ライブラリのみ）。
**Tests** (Red → Green) — *代表ケースのみ*:
  - `RenderedMedia(rendered_text="...", render_status="ok")` が `derived_image_paths == []` / `page_count is None`（default、既存構築の後方互換）
  - `RenderedMedia(rendered_text="", render_status="ok", derived_image_paths=["a.png","b.png"], page_count=12)` が値を保持し frozen（再代入で `AttributeError`）
  - `render_status` の 4 状態検証（`__post_init__`）が新 field 追加後も不変（不正 status で `ValueError`）
**Implementation Notes**: `from dataclasses import field` を追加し `derived_image_paths: list[str] = field(default_factory=list)` / `page_count: Optional[int] = None`。**field 順序は既存 2 field（`rendered_text` / `render_status`）の後ろに置く**（位置引数での既存構築 `RenderedMedia(None, "passthrough")` を壊さない）。`__post_init__` は触らない（新 field に値域制約なし＝負の page_count 等は Adapter 側責務、Domain は型のみ）。`FakeMediaRenderer`（fakes.py）と emitter は Stage 11.2/11.3 で追従。
**Status**: Complete（2026-05-30。`RenderedMedia` に `derived_image_paths`/`page_count` を `default` 付き追加、test_media.py +6、domain・全 suite green=345 passed。位置引数構築 `RenderedMedia(None, "passthrough")` の後方互換も test で保証。併せて未導入だった pdfplumber/reportlab をローカル導入し、**pypdfium2・Pillow が pdfplumber 経由で transitive に入る＝Stage 11.3「新規依存ゼロ」を前倒し実証**＝3-Strike #1/#2 解消）

## Stage 11.2: Interface(emit) — _build_media_payload に 2 field 追加
**Goal**: emit の `media[]` item に `derived_image_paths` / `page_count` を v2 維持で追加し、render_results 不在時は `[]` / null を明示出力する。
**Layer**: Interface (Adapter)
**Success Criteria**: `test_emitter.py` 既存群が無変更で green（追加 field が現れても既存アサーションは個別 key を見るだけ）、新規テスト green。
**Tests** (Red → Green) — *代表ケースのみ*:
  - render_results に画像 PDF（`derived_image_paths=["...page-001.png"]`, `page_count=12`）を渡す → payload の該当 media に両 field が乗る
  - render_results 未指定（Medium モード / Stage 10 までの呼び出し）→ `derived_image_paths == []` / `page_count is None`（後方互換、`rendered_text: null` と同型）
  - テキスト PDF（`derived_image_paths=[]`, `page_count=3`）→ 空 list と page 数が両方明示される
**Implementation Notes**: `_build_media_payload` の `rd is not None` 分岐で `derived_image_paths = list(rd.rendered.derived_image_paths)` / `page_count = rd.rendered.page_count`、`dl`/else 分岐では `[]` / `None`。out dict に 2 key 追加。`PAYLOAD_VERSION` は **2 のまま**（フィールド追加は破壊的でない）。`ensure_ascii=False` は不変。
**Status**: Complete（2026-05-30。`_build_media_payload` の3分岐に2 field 追加、`rd` 分岐のみ値・`dl`/`else` は `[]`/null。test_emitter.py +4、全 suite green=349 passed。v2 維持・既存 emit テスト無変更で後方互換）

## Stage 11.3: Interface(PdfRenderer) — テキスト/画像の二経路化 + pypdfium2 ラスタライズ
**Goal**: `PdfRenderer.render()` を二経路化する。テキスト層ありはページ境界マーカー挿入 + `page_count`、テキスト層が空/薄ければ `pypdfium2` で全ページ画像化（cap 付き）→ `derived_image_paths` + `page_count`。
**Layer**: Interface (Adapter)
**Success Criteria**: 実 PDF（reportlab 動的生成）での integration test green。テキスト PDF → マーカー入り本文 + page_count、画像 PDF（空テキスト層）→ 派生 png がディスクに生成され `derived_image_paths` に絶対パスが乗る + `rendered_text=""`、壊れ PDF → failed。**`pypdfium2` が pdfplumber 経由で import 可能（新規依存ゼロ）を Stage 着手時に実測確認**。token/絶対パスは stderr に出さず file_id[:8] のみ。
**Tests** (Red → Green) — *代表ケースのみ*:
  - テキスト PDF（複数ページ）→ `rendered_text` に `--- page 1 ---` / `--- page 2 ---` マーカーが各ページ本文の境界に入る、`page_count == ページ数`、`derived_image_paths == []`
  - 空テキスト層 PDF（`_make_blank_pdf` の複数ページ版）→ `render_status="ok"`、`rendered_text == ""`、`derived_image_paths` が**ページ数ぶんの実在 png パス**（`Path.exists()` で検証）、各パスは `media/` 直下・file_id[:N] プレフィックス命名
  - cap 超（cap=2 注入 + 3 ページ画像 PDF）→ `len(derived_image_paths) == 2`、`page_count == 3`（総数、cap ではない）
  - 壊れ PDF / 存在しないファイル → `render_status="failed"`、`derived_image_paths == []`、`page_count is None`（Stage 10 既存テスト維持 + 画像経路でもクラッシュしない）
**Implementation Notes**: `pypdfium2` は **lazy import**（pdfplumber 同様、Medium モード/validate-config で不要）。**まず Stage 着手の最初に `python -c "import pypdfium2"` で pdfplumber>=0.11 経由の同梱を実測**（WebFetch 確認済みだが環境で再検証、OPS.md「AI 提案ライブラリを鵜呑みにしない」）。同梱されていなければ 3-Strike #1 へ。ラスタライズ: `pdf = pypdfium2.PdfDocument(str(local_path)); n = len(pdf); for i in range(min(n, cap)): page = pdf[i]; bitmap = page.render(scale=...); pil = bitmap.to_pil(); pil.save(target)`（scale は Vision 可読な DPI、初期 ~2.0＝~144dpi 相当から）。**派生画像の保存先は `local_path.parent`（=`state_dir/media/`）フラット直下**、命名 `f"{file_id[:16]}_page-{i+1:03d}.png"`（既存 download の file_id プレフィックス命名と同型、cleanup の `is_file()` フラット前提に乗る）。テキスト経路のマーカーは `"\n".join(f"--- page {i+1} ---\n{txt}" for i, txt in enumerate(page_texts))`。`page_count` は**両経路とも `len(pdf.pages)` の総数**。cap は `__init__(self, image_max_pages: int = 20)` で受ける（main.py が Config から渡す、Stage 11.4）。例外は既存どおり広く catch → failed、`derived_image_paths` は確定済み分を捨てて `[]`（部分生成画像は cleanup retention が回収）。**Pillow 依存**: `bitmap.to_pil()` は Pillow を要する → pypdfium2 が Pillow を引くか実測、引かなければ `to_numpy()` + 別ライブラリ or Pillow 明示追加を Stage 11.4 で判断（3-Strike #2）。
**Status**: Complete（2026-05-30。PdfRenderer 二経路化＝テキスト層あり→`--- page N ---` マーカー+page_count、空→pypdfium2 で全ページ画像化(cap 内)→derived_image_paths+page_count。`__init__(image_max_pages=20)`。test_pdf_renderer.py +4、全 suite green=353 passed。**pypdfium2 実 API（`PdfDocument`→`render(scale=2.0)`→`to_pil().save()`）を実機検証、3-Strike #1/#2 解消**。UseCase は無変更で透過＝設計の後方互換が効いた）

## Stage 11.4: Infrastructure — cap env + DI 配線 + ドキュメント
**Goal**: cap の env（`TELEGRAM_SECRETARY_PDF_IMAGE_MAX_PAGES`）を追加、`cmd_poll` / `cmd_watch` の `PdfRenderer()` 構築に cap を渡し、ROUTINE_PROMPT Step 5 の段階 Vision 手順・README/SKILL/CHANGELOG を更新。
**Layer**: Infrastructure
**Success Criteria**: `validate-config` が新 env 込みで exit 0、`cmd_poll` / `cmd_watch` が `PdfRenderer(image_max_pages=config.pdf_image_max_pages)` を構築、Medium モードで PDF 依存（pypdfium2/Pillow）を踏まない（lazy import 維持）、ROUTINE_PROMPT に段階 Vision 手順が記載される。
**Tests** (Red → Green) — *代表ケースのみ*:
  - `Config.from_env`: `TELEGRAM_SECRETARY_PDF_IMAGE_MAX_PAGES`（default 20）の parse、欠損は default、不正値（0 以下/非整数）は exit 2（既存 `_parse_positive_int` 流用）
  - `cmd_poll` の Heavy 分岐で `PdfRenderer` が cap 付きで構築される（既存 `test_main.py` の poll 経路に cap 受け渡しの characterization 追加、fake gateway/downloader 注入）
  - Medium モード（`media_enable_download=false`）で pypdfium2/Pillow を import しない（lazy import の後方互換、`cmd_watch` の `_ensure_media_stack` 未発火を確認）
**Implementation Notes**: `Config` に `pdf_image_max_pages: int = DEFAULT_PDF_IMAGE_MAX_PAGES`（=20）追加、`from_env` で `_parse_positive_int` 流用。`main.py` の `cmd_poll`（L133-137）と `cmd_watch::_ensure_media_stack`（L194-200）の `PdfRenderer()` を `PdfRenderer(image_max_pages=config.pdf_image_max_pages)` に。`cmd_watch` の lazy import / `ImportError`→`pdf_renderer=None`→skipped フォールバックは**不変**（pypdfium2 同梱なので通常は import 成功）。`bootstrap.sh` の Heavy install は **pdfplumber が pypdfium2 を引くので追加 install 不要**（Stage 11.3 で同梱実測 → Pillow が別途要るなら bootstrap に 1 行追加）。**cleanup は変更不要**（派生画像は `media/` フラット直下＝既存 `cleanup_media_dir` の retention 対象）。Live E2E は Stage 11.5 に集約（新 fresh session 要、Custom network policy 反映待ち）。
**Status**: Complete（2026-05-30。Config に `pdf_image_max_pages`（default 20、`_parse_positive_int` 流用）、test_config +4。cmd_poll/cmd_watch の PdfRenderer に cap を DI、test_main に cap 配線 characterization +1（重い renderer を stub 化）。全 suite green=358 passed。**pyproject/bootstrap に `pypdfium2>=4.18.0`・`Pillow>=9.1` を直接宣言**＝計画の「原則変更なし」を再現性重視で「直接化」に倒す判断（pdf_renderer が pypdfium2 を直接 import、to_pil が Pillow を要するため transitive に暗黙依存しない）。ドキュメントは別途更新）

## Stage 11.5: Live E2E（実機・段階 Vision 往復）
**Goal**: 画像 PDF / 多ページ PDF の E2E（自分の bot にスキャン PDF + caption "中身を読んで" を送る → `watch` → 全ページ画像化 → emit に `derived_image_paths` + `page_count` → Weave が**先頭1枚 Read → 性質と総ページ把握 → 残り要否判断 → 必要なら追加 Read で全容把握 → 返信**）を Cloud Routine 上で成立させる。CHANGELOG / README / SKILL.md / ROUTINE_PROMPT.md を Doc Complete に。
**Layer**: Infrastructure（運用統合）
**Success Criteria**: fresh session で `watch` 起動 → スキャン PDF 送信 → emit に派生画像と page_count → Weave が先頭1枚で性質把握し、明白なら確認なしで内容応答 / 多量・不明なら send-reply で確認メッセージ → 残りページをディスク済みから Read（追加 render なし）→ 全容応答。テキスト PDF はページマーカー入り `rendered_text` で位置把握、超多ページ PDF は cap 打ち切りが効く、retention で派生画像も削除される。
**Tests / 検証**:
  - E2E: スキャン PDF（Stage 10.4 の `Tree_of_Life.pdf` 再利用）+ "中身を読んで" → `derived_image_paths` 非空 → Weave が先頭1枚 Read → 内容に言及した応答（OCR なしで Vision 到達）＝Stage 11 最重要目的
  - E2E: 多ページ画像 PDF（図面複数枚）→ Weave が先頭1枚 + page_count で「N ページの図面、全部見る？」を send-reply で確認 → 承認後に残りページをディスク済みから Read
  - E2E: テキスト PDF（Stage 10.4 の資材物価スライド）→ `rendered_text` に page マーカー → Weave が「3 ページ目の不感帯条項」等ページ位置を指定して応答
  - E2E: 超多ページ PDF（cap=20 超）→ `page_count`=実数 / `derived_image_paths`=20 枚 → Weave に「N ページ中 20 枚を画像化」が伝わる
  - retention 実測: 派生 png も `cleanup_media_dir` 対象で削除（既存 retention に乗ることを実機確認）、出力漏洩スキャン（PDF 埋め込み機密が Vision 応答に漏れない）
**Implementation Notes**: Stage 5/6.5/7.5/9.7/10.4 同様、新 fresh session 起動が前提（Custom network policy 反映と pyproject/bootstrap 反映の両方が新コンテナで効く）。ROUTINE_PROMPT Step 5 の段階 Vision 判断（先頭1枚→要否→確認 or 追加 Read）は**プロンプト責務**であり、コード側は派生画像をディスクに置くまで（L00473 分業）。CHANGELOG は新エントリで「PDF Multipage/Image: pypdfium2 で画像 PDF を全ページ画像化、`derived_image_paths` + `page_count` を emit（v2 維持）、テキスト PDF にページ境界マーカー、段階 Vision 判断は ROUTINE_PROMPT」を記載。**Stage 9.6-ii との基盤共有を CHANGELOG/SKILL に明記**（`derived_image_paths` は動画 key frame と相乗り）。
**Status**: Doc Complete（2026-05-30。CHANGELOG [0.9.0] / README（PDF Quickstart + env cap + tests 358）/ SKILL（Daily Workflow 段階 Vision + env + Security）/ ROUTINE_PROMPT（スキーマ例 + render_status + media 処理の段階 Vision 分岐）すべて着地。**Live E2E（実 Telegram でスキャン/図面/多ページ PDF → 段階 Vision 往復、retention）は fresh session 待ち**、Stage 5/6.5/7.5/8.5/9.7 と同要件）

### Documentation Plan（Stage 11 追加分）

#### 基本セット（毎回確認）

| ドキュメント | パス | 新規/更新/不要 | 計画内容 / 理由 |
|---|---|---|---|
| `README.md` | `Expertises/TelegramSecretary/README.md` | 更新 | Quickstart の PDF 節に「スキャン PDF/図面 PDF は全ページ画像化 → Weave が段階 Vision」を追記。env vars 表に `TELEGRAM_SECRETARY_PDF_IMAGE_MAX_PAGES`（default 20）追加。Stage 10 の「PDF=ok（pdfplumber）」コメントに「画像 PDF は derived_image_paths で Vision」を補足 |
| `CHANGELOG.md` | `Expertises/TelegramSecretary/CHANGELOG.md` | 更新 | 新バージョンエントリに「PDF Multipage/Image: 画像 PDF を pypdfium2 で全ページ画像化、`RenderedMedia` に `derived_image_paths`/`page_count` 追加、emit v2 維持・フィールド追加、テキスト PDF にページ境界マーカー、cap env 追加、段階 Vision 判断は ROUTINE_PROMPT。新規依存ゼロ（pypdfium2 は pdfplumber 同梱）。Stage 9.6-ii 動画 key frame と derived_image_paths 基盤共有」を記載 |
| `IMPLEMENTATION_PLAN.md` | （本ファイル） | 更新 | 本 Stage 11 を Vision 経路へ書き換え（OCR 三択 backlog → Vision 5 段階）。Stage 5/6/7/8/9/10/11 全完了後にまとめて削除検討（現運用：イベント駆動開発の経緯として保持） |

#### 拡張レイヤー

| ドキュメント | パス | 新規/更新/不要 | 計画内容 / 理由 |
|---|---|---|---|
| `SKILL.md` | `Expertises/TelegramSecretary/SKILL.md` | 更新 | Daily Workflow Step 5 に「PDF の `derived_image_paths` が非空なら先頭1枚 Read → page_count で総量把握 → 段階 Vision」を追加。env vars 表に cap 追加。Security に「PDF ローカル完結・派生画像も retention 対象・Vision 応答の漏洩スキャン」を反映 |
| `ROUTINE_PROMPT.md` | `Expertises/TelegramSecretary/ROUTINE_PROMPT.md` | 更新 | Step 5 の media[] 処理に PDF 段階 Vision 分岐を明記（`derived_image_paths` 非空 → 先頭1枚 Read → 性質/`page_count` 把握 → 残り要否判断 → 多量/不明なら send-reply で確認 → 残りはディスク済みを Read）。テキスト PDF の page マーカーで位置指定も明記。Failure modes は Stage 10 の `render_failed` で兼ねる（画像化失敗も failed） |
| `pyproject.toml` | `Expertises/TelegramSecretary/pyproject.toml` | 要確認 | **原則変更なし**（pypdfium2 は pdfplumber>=0.11 の必須依存として同梱）。Stage 11.3 の同梱実測で `to_pil()` 用 Pillow が pypdfium2 に引かれないと判明した場合のみ Pillow を明示追加（その場合 dev ではなく本番依存、Heavy） |
| `bootstrap.sh` | `Expertises/TelegramSecretary/bootstrap.sh` | 要確認 | **原則変更なし**（pdfplumber install で pypdfium2 が入る）。Pillow が別途要るなら Heavy 分岐に 1 行追加（Stage 11.3/11.4 で確定） |
| `CLAUDE.md`（root） / `SECURITY.md` | — | 不要 | TelegramSecretary は「利用可能ペルソナ」未掲載（本番投入前）。PDF 画像化はローカル完結・新規脅威面なし（SKILL Security 追記で十分）。E2E 完了・本番投入時にまとめて掲載判断 |
| `.gitignore` | `homunculus/Weave/.gitignore` | 確認のみ | 派生画像は `state_dir/media/` フラット直下 → 既存 `Expertises/*/state/` で除外済み。Stage 11.5 で実測確認 |

> 拡張レイヤーの最終棚卸しは Stage 11.4 着手時に `Explore` サブエージェントで再確認（SSoT 違反チェック含む）。本計画立案時に read-only 調査で既存ドキュメント構成（README/CHANGELOG/SKILL/ROUTINE_PROMPT + pyproject + bootstrap + .gitignore）を確認済み、Stage 6/7/9/10 と同じ更新パターン。

### Decision Priority Notes（Stage 11 固有、Testability > Readability > Consistency > Simplicity > Reversibility）

- **共通インフラ `derived_image_paths` を `RenderedMedia` に載せる（新 Port / 新 dataclass を作らない）**（最大の分岐）: 派生画像専用の戻り型 or `DerivedImages` Port を分ける案は、`MediaRenderer` Port シグネチャ変更・emitter 大改修・Stage 9.6-ii との二重実装を招く。`RenderedMedia` に `default` 付き 2 field 追加なら **Port 不変（Consistency 最良）**・**既存構築が全て後方互換（Testability、UseCase/emitter/fake/既存テストが無変更 or null 追従のみ）**・**Stage 9.6-ii 動画 key frame が同じ field に相乗り（Reversibility＝投資が二度効く）**。Stage 7 の `file_name` 追加と完全同型。
- **画像化（決定論・安い）と Vision（高い・判断）を分離**（設計の核）: 「PDF を render したら Vision まで一気に」案は LLM 推論をコード内に持ち込み L00473 分業違反。コードは全ページ**ディスクに画像を置くまで**、どれを Vision するかは Weave が `page_count` を見て段階判断（**Simplicity**＝コードは決定論に純化、**Reversibility**＝判断ポリシーは ROUTINE_PROMPT で可変）。「先頭1枚だけ Read → 残りはディスク済みを追加 render なしで Read」は Vision トークン経済の段階化。
- **テキスト PDF の段階化は YAGNI、ページマーカーのみ**（設計分岐）: テキストはトークン経済が画像の 1/N で軽い。超長文を分割する機構は入れず、`--- page N ---` マーカーで Weave の位置把握だけ足す（**Simplicity**）。必要になったら YAGNI 解除。
- **cap は超多ページの安全弁のみ・env 可変**（設計分岐）: cap を「常時の段階化装置」にすると Weave の総量把握（`page_count`）と二重管理になる。cap は disk/トークン暴走の事故防止に純化、default は緩め（20）、env で可変（**Reversibility**）。`page_count` は cap ではなく**総数**を返し、Weave に「N ページ中 cap 枚」を正直に伝える。
- **テキスト層「薄い」判定は初期シンプル（strip して空＝画像経路）**: 図面 PDF で「枠線ラベルだけ薄く入る」ケースの閾値判定は **YAGNI で初期実装しない**（空判定のみ）。顕在化したら閾値 env を解除（過剰な事前最適化を避ける、Stage 10 のスキャン PDF=空 ok の延長）。
- **派生画像は `media/` フラット直下に保存（サブディレクトリを切らない）**: `cleanup_media_dir` は `is_file()` でフラット前提・サブディレクトリ無視。サブディレクトリに置くと retention から漏れ機密画像が残存する。フラット + file_id プレフィックス命名なら**既存 cleanup が無変更で retention をカバー**（**Consistency / Simplicity**、Stage 6 download 命名と同型）。
- **OCR は Port 差し替えで後付け（本 Stage で実装しない）**: Vision で大半は読める前提。低解像度スキャンの OCR fallback は `MediaRenderer` Port 差し替えで後付け可能（**Reversibility**）。本 Stage に入れると射程肥大（YAGNI）。

### 3-Strike Rule（Stage 11 固有）

- **詰まりやすい予想ポイント**:
  1. **pypdfium2 が pdfplumber 経由で実は入らない / バージョン非互換**: 「新規依存ゼロ」前提が崩れると bootstrap/pyproject 変更が要る。WebFetch 確認済みだが環境差で外す可能性
  2. **`bitmap.to_pil()` が Pillow を要し pypdfium2 が Pillow を引かない**: 派生 png 保存に Pillow 明示追加が要る（本番依存が増える＝「新規依存ゼロ」が部分的に崩れる）
  3. **大 PDF の全ページ画像化が重く long-poll 干渉**: Stage 7/9 同型。ラスタライズは CPU/メモリ重く、多ページで `watch` メインループ blocking → getUpdates が止まる
  4. **画像経路 vs テキスト経路の閾値誤判定**: テキスト層が薄く入る図面 PDF を「テキストあり」と誤判定し画像化されず Vision に届かない（実需の図面が読めない）
- **代替アプローチ候補**:
  - pypdfium2 非同梱 → pyproject/bootstrap に `pypdfium2` を明示追加（pdfplumber と同じ pure-python・wheel 配布なので追加は容易、「新規依存ゼロ」を「新規システムバイナリゼロ」に緩める）
  - Pillow 問題 → `bitmap.to_numpy()` + `pdfplumber` 同梱の画像書き出し経路を探す、無ければ Pillow を本番依存に明示追加（pypdfium2 公式が Pillow 推奨なら受容）
  - long-poll 干渉 → ラスタライズを**別スレッド**化、`watch` メインループは getUpdates 専念（Stage 6/7/9 の 3-Strike と同型）。最終手段は cap を小さくし「先頭数枚だけ画像化、残りは要求時」に倒す（ただし「ディスク済みを追加 Read」設計と要整合）
  - 閾値誤判定 → 初期は「strip して空＝画像経路」の単純判定、図面で漏れたら抽出長の閾値 env を解除、最終手段は「テキスト薄い PDF は**両方**出す（テキスト + 画像）」で Weave に両方渡す
- **ユーザーへ相談する判断ライン**: 上記いずれかで「新規依存ゼロが崩れ Pillow/pypdfium2 の明示追加が要る」と判明した時点で、`AskUserQuestion` で（Pillow/pypdfium2 を本番依存に明示追加して続行 / 画像 PDF は OCR 経路に切替 / テキスト PDF のみ対応で画像 PDF は Stage 分離）の三択を提示。また long-poll 干渉が実機で顕在化したら（別スレッド化 / cap 縮小 / Medium 退避）を提示。

### Security 追加項目（Stage 11 固有、Stage 10 継承）

- **PDF ローカル完結**: pypdfium2 もローカルでラスタライズ、PDF・派生画像が外部に一切出ない（機密 PDF/図面に安全）。Vision 解釈は Weave（Claude）が Read するが、これは既存 photo パイプラインと同じ信頼境界
- **派生画像も retention 対象**: 全ページ画像化したスキャン PDF（契約書・図面の機密）が `media/` に残存しないよう、既存 `cleanup_media_dir` の retention で削除（フラット直下保存により無変更でカバー、Stage 11.5 で実測）
- **失敗時の絶対パス秘匿**: 画像経路の内部 except 時も stderr は `file_id[:8]` のみ（Stage 10 の PdfRenderer / markitdown / Moonshine 同型、テストで検証）。派生画像の絶対パスを stderr/ログに出さない
- **Vision 応答の出力漏洩スキャン**: 画像化された PDF 内の機密（図面の発注者名・契約金額等）が Weave の Vision 応答経由で漏れないか send-reply 前にスキャン（既存の rendered_text 漏洩スキャンを Vision 応答にも拡張、ROUTINE_PROMPT Step 5 に明記）
- **cap による DoS/disk 防御**: 超多ページ PDF（悪意 or 事故）での画像化暴走を cap で打ち切り、disk/トークン暴走を防ぐ（既存 `media_max_size_bytes` の download 段階防御に加え、ページ数次元の防御を追加）
- **mime_type は Telegram 自己申告**: Stage 10 方針継承。pypdfium2 は PDF 構造を実際に開くため、PDF でないものを pdf として送られても failed で弾かれる

**Status**: 実装完了（2026-05-30。Stages 11.1〜11.4 コード Red→Green、全 suite green=358 passed・回帰ゼロ。11.5 Doc Complete。**Live E2E（段階 Vision 往復）は fresh session 待ち**。pypdfium2/Pillow 直接宣言＝計画の「原則変更なし」を再現性重視で倒した実装判断。3-Strike #1 pypdfium2 API・#2 Pillow を実機検証で解消。OCR 三択から Vision 経路へ設計確定 2026-05-30）

---

## OCR 申し送り（Stage 11 で劣後 fallback に降格、調査結果の退避）

> Stage 11 は Vision 経路を採用したため OCR は本 Stage で実装しない。以下は再調査コストが高いため退避する調査結果（Vision でも読めない低解像度スキャン用の fallback を将来 `MediaRenderer` Port 差し替えで後付けする際の参照）。

**候補ライブラリのサイズと調達（2026-05-30 調査、確信度 🔵 サイズ / 🟡 v5 統合時期）**:

| 候補 | 日本語モデル | ランタイム | 追加実質サイズ | システムバイナリ | ライセンス |
|---|---|---|---|---|---|
| **RapidOCR** (onnxruntime) | det 4.75MB + rec ~11MB ≈ **16MB** | onnxruntime（markitdown の magika 経由で**既存**） | wheel 15MB + モデル 16MB ≈ **~30MB** | **不要**（pure-python+onnx） | Apache-2.0 |
| Tesseract | jpn 13.7MB（best）/ 2.36MB（fast） | — | モデル 14MB | **要 `tesseract` apt**（poppler を避けた方針に反する） | Apache-2.0 |
| EasyOCR | japanese.pth 221MB | **torch ~2.7GB** | **数 GB** | 不要 | Apache-2.0 |

**第一候補 = RapidOCR**（~30MB、Moonshine 134MB より軽い、onnxruntime 既存、システムバイナリ不要、SECURITY.md「pure-python・OS コマンド非依存」と一致）。EasyOCR は torch 2.7GB で Moonshine が torch-free を選んだ設計思想に反し除外。Tesseract はモデル最小だが `tesseract` バイナリ apt 必須＝poppler を避けた轍。

**急所＝サイズではなく調達の再現性**（🔵 校正済み）: RapidOCR は**日本語の公式事前ビルド ONNX を持たない**（SWHL/RapidOCR は ch/en のみ、日本語は PP-OCRv1 の古い CRNN のみ）。Moonshine が公式 base-ja を自動 DL するクリーンさと違い、日本語は (a) `paddleocr_convert` で v4 を自前変換（bootstrap に変換ステップ＝供給安定だが重い）/ (b) 非公式 HF リポ（`monkt/paddleocr-onnx` 等、消失・改変リスク）/ (c) v1 CRNN で妥協（精度↓）のいずれか。PP-OCRv5 は単一モデルで日本語ネイティブ（<100MB）だが **RapidOCR 統合は未配信**（`LangRec.JAPAN` で File not Found、2025 discussion #521）→ 採用するなら v4 + 自前変換が現実解。

**OCR を採る場合の接続点**: PdfRenderer の空テキスト層検知（Stage 11 の画像経路判定と同地点）→ ページ画像化（Stage 11 の `derived_image_paths` 生成を再利用）→ RapidOCR。MediaRenderer Port は不変ゆえ既存枠に乗る。**Stage 11 の Vision 経路で大半が読めれば OCR は不要**（Vision でも読めない低解像度スキャンに限定した劣後 fallback）。
