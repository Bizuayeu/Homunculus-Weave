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
**Status**: In Progress（ROUTINE_PROMPT.md / SKILL.md / README.md / CHANGELOG.md は作成済み、Cloud Routine 環境での実機検証は別途）

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
