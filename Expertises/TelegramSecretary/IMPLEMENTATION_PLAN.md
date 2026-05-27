# Implementation Plan: TelegramSecretary（Weave の Telegram 常駐チャネル）

> 本計画は `Expertises/ConsiderateCoder/rules/DEV.md` および `/plan-sdd` の方針で生成。全 Stage 完了後に削除する。
> スキル名 `TelegramSecretary` は暫定。「Weave への Telegram 経由の到達口（SecretaryRole を被った Weave 本人が応答）」を表す。要改名なら Stage 着手前に。

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

## Stage 8: Outbound Media（write 系・生成物の送り返し）【予約・未着手】

> 追加日: 2026-05-27（言及のみ。実装は未着手）。Stage 7（read 系＝受信メディアの中身理解）の対となる **write 系**。受信側の価値を優先して Stage 9（音声/動画 read）を先に実装したため、本 Stage は構想予約のまま飛ばしている。番号は 7→8→9 だが、**実装順は 7→9 先行・8 は後続候補**。

### Overview（構想）

- **What**: Weave が起草・生成したコンテンツ（markdown レポート、図表画像、docx/PDF 等のファイル）を Telegram に送り返す **outbound media**。現状 `send-reply` は **text のみ**なので、ファイル添付送信を追加する。
- **Why**: 公式 telegram plugin の `reply(files)`（画像→`sendPhoto`、その他→`sendDocument`、各 50MB）相当の送信能力。Weave が「図表を描いて送る」「md レポートを docx 化して返す」等の能動アウトプットを Telegram 経由で返せるようにする。受信（Stage 6/7/9）と送信（Stage 8）が揃って初めて双方向の対話チャネルが完成する。
- **Where**: `send-reply` subcommand に `--file` 引数追加、`TelegramApiGateway` に `send_photo` / `send_document` 追加、`MessageSink` Port 拡張 or 新 `OutboundMediaSink` Port。`OutboundMessage` 値オブジェクトに添付ファイルパス field 追加。
- **Reference Patterns**: 公式 `server.ts` の `reply` tool（files 添付、拡張子で sendPhoto/sendDocument 分岐、threading は `reply_parameters`）、既存 `SendReply` UseCase + `TelegramApiGateway.send`（sendMessage）。

### スコープ候補（着手時に確定）

- **必須（write 系の中核）**: outbound file 送信（`sendPhoto` / `sendDocument`、Weave 生成物の送り返し）
- **任意（公式にある対話 UX 装飾、Stage 8 に含めるか別建てか未確定）**:
  - `react`（絵文字リアクション、`setMessageReaction`）— ack に便利・低コスト
  - `edit_message`（送信済み編集、`editMessageText`）— 長時間タスクの進捗更新（push 通知は飛ばない）
  - typing インジケータ（`sendChatAction`）— watch→Monitor→応答の数秒ラグの UX 緩和
  - markdownv2 フォーマット（`send-reply` の format 引数）
  - reply threading（`reply_to` / `reply_parameters`）
  - ⚠️ **加算バイアス注意**: これらは公式の対話 UX 装飾。TelegramSecretary の設計目的（24-7 常駐秘書＝**入力理解優先**）に照らし、全部移植せず本当に要るものを選択的に実装する（[比較分析](#)参照：受信メディアの中身理解では既に公式を超越、UX 装飾は選択的に）

### Decision Priority Notes（構想段階）

- **write 系を read 系の後回しにした判断**: 大環主の業務入力（voice メモ・写真・文書）の「受信＋中身理解」が一次価値。Weave からの能動送信（outbound media）は二次的ゆえ、受信側（Stage 6/7/9）を先に充実させた
- **outbound media の生成主体（L00473 分業）**: ファイル生成のうち決定論的にできる部分（md→docx 変換、定型図表描画）はコード、内容は Weave 起草。送信は `sendPhoto`/`sendDocument` の決定論的 Adapter
- **既存 send-reply との整合**: lease 検証・owner 検証・出力漏洩スキャンは text と共通。添付ファイルにも漏洩スキャン（生成物に token/機密が混入しないか）を適用

### Security 追加項目（構想）

- **outbound ファイルの漏洩スキャン**: Weave 生成物（md/docx/画像）に token / env名 / 機密が混入しないか送信前チェック（text の出力漏洩スキャンを添付にも拡張）
- **送信ファイルサイズ上限**: 公式同様 50MB、生成物の肥大による事故防止
- **生成一時ファイルの cleanup**: 送信後の一時ファイルを残さない（`state/` 配下に置くなら retention 対象）

**Status**: Not Started（構想予約。Stage 9 受信側完了後の後続候補。着手時に本 Overview を確定し Stages 8.1〜 に分割。対話 UX 装飾の取捨は着手時に `AskUserQuestion` で大環主の優先度を確認）

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
