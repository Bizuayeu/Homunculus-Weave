# Changelog

## Stage 5 進捗ノート - 2026-05-26

### Live Functional Verification (Routine 側ローカル検証)

実コード（`origin/main` の `cbaeecc` 時点）を /tmp に展開して、実プロセス・実ソケットで以下を検証（Telegram egress 不要な部分のみ）:

| Success Criterion | 結果 |
|---|---|
| lease 並走防止（2セッション競合） | ✅ sessB の acquire/renew が exit 4 |
| crash 自己治癒（stale 奪取） | ✅ ttl=1 失効後に別 owner が takeover |
| `validate-config` env 欠損/充足 | ✅ exit 2 / exit 0 |
| `watch` アイドル時の沈黙 | ✅ 空 getUpdates → emit 0 行（idle-zero の土台） |
| 認可フィルタ | ✅ 未認可 chat 999 を破棄、認可 12345 のみ emit |
| injection フラグ | ✅ `role_override` + `credentials_request` 検出 |
| offset 単調前進 | ✅ 未認可分も消費して 43=max(42)+1（無限再取得なし） |
| sendMessage 経路 | ✅ ローカル mock Telegram サーバー経由で実ソケット疎通 |

**機能パイプラインは実質グリーン**。Routine 側がローカル mock サーバーを 127.0.0.1 に立てて実コードを駆動した結果、Domain → UseCase → Adapter → Infrastructure の各層がプロダクションコードとして整合して動作することを確認。

### Live E2E Pending (Fresh Session 必須)

以下は本物の Telegram egress と bot token が必要で、新コンテナでの実機検証が残る（現セッションは egress 403 = `host_not_allowed` + token 未設定。allowlist 変更はコンテナ生成時のみ反映ゆえ既存セッションには波及しない）:

- egress 疎通: `curl https://api.telegram.org/botINVALID/getMe` で 401/404 確認
- `test --chat-id` で自分の bot への ping 到達
- `watch` + Monitor の実メッセージ 1 往復（E2E）
- **未文書化2点の実測**: セッション寿命（inactivity reclaim / hard cap）/ `watch` blocking 中のアイドル枠消費量
- `/schedule` 登録と cron 起動

### 次セッションの前準備（ユーザー）

1. **BotFather** で bot 作成 → `TELEGRAM_BOT_TOKEN` 取得
2. **chat_id 発見**: 作った bot に 1 通送信 → fresh session で `getUpdates` を 1 回叩いて chat_id を読む（鶏卵問題ゆえ最初だけ手動）
3. Environment に 2 つ設定: `TELEGRAM_BOT_TOKEN` / `TELEGRAM_SECRETARY_AUTHORIZED_CHATS=[<chat_id>]`、任意で `TELEGRAM_SECRETARY_STATE_DIR` を private リポ配下にして state をセッション跨ぎ永続化
4. `api.telegram.org` は allowlist 追加済み（確認のみ）
5. **新コンテナのセッションを起動**（env と egress は新コンテナから有効になる）

新セッションで「Stage 5 続き」と告げれば E2E + 寿命/枠実測を一気通貫で回す。

## [0.1.2] - 2026-05-26

### Added — 運用律 B 案: session_id の env 統一

- `bootstrap.sh` を NewsCaster と同型の **source/exec デュアル対応** に書き換え
  - source 時は env を親シェルに引き継ぎ、bash 実行時は依存導入のみ
  - `set -u` のみ採用（source 時に呼び出し元シェルへの影響を避けるため `set -e` は不使用）
- `bootstrap.sh` 末尾に `TELEGRAM_SECRETARY_SESSION_ID` の**冪等な自動 export** を追加
  - 未設定時は uuid から生成（`session-xxxxxxxx`）
  - 設定済みなら尊重（冪等性）
- `cmd_send_reply` に `--owner` 引数と CLI 層の owner 検証を追加
  - lease.owner と caller の owner が不一致なら exit 4（並走奪取の二重防御）
- `ROUTINE_PROMPT.md` Step 2 を `bash` から `source` 呼び出しに変更
  - 運用律 B 案を明記、各コマンドでの `--owner` 明示が不要に

### Changed

- 全 subcommand (`lease` / `watch` / `send-reply`) は `--owner > env > uuid` の優先順位で
  owner を解決。`source bootstrap.sh` で env を固定すれば全コマンド自動同期、
  緊急時の上書きは `--owner <id>` で可能

### Tests

- **Total: 99 tests passing** (96 → +3)
- 新規: send-reply owner mismatch / send-reply env owner sharing / watch env owner sharing

### Rationale

- Routine 側レビュー後の残課題（Step 5 と Step 6 の owner 整合性）への対応
- ProsCons 検討の結果 B 案（env 統一）採用：書き忘れ防止 = Routine 指摘①と同型の構造的取りこぼし対策
- Cloud Routine ではセッション毎に env が独立ゆえ env 汚染リスク構造的にゼロ

## [0.1.1] - 2026-05-26

### Fixed — Routine 側レビュー指摘対応

- **lease keep-alive 配線漏れ (指摘①)**: `watch` ループがアイドル時に lease を renew せず、無音期間に stale 化して並走奪取される設計ホールを修正。`cmd_watch` がサイクル末尾で自動 renew、奪取検出時は exit 4 で自己終了
- **SendReply の owner 検証 (指摘④-2)**: `SendReply.execute` で送信前に lease store を再 load して引数 lease.owner と一致するか検証、奪取済みなら `LeaseConflictError`
- **429/Retry-After 尊重 (指摘④-3)**: `TelegramApiGateway._request_with_retry` で 429 を 5xx と同様に retry 対象に追加、`Retry-After` ヘッダがあれば sleep（上限 `max_retry_after_seconds`、既定 60 秒で自損防止）

### Changed

- **テスト公開ポリシー統一 (指摘②訂正)**: `.gitignore` の `**/tests/` `**/test/` ルールを削除、PrecognitiveViewer 専用例外も削除。全 Expertises のテストを信頼性証拠として公開する方針に統一
- **state/ 誤コミット防止 (指摘④-1)**: `.gitignore` に `Expertises/*/state/` を追加
- `cmd_watch` に `--owner` 引数追加（lease renew 用）
- `ROUTINE_PROMPT.md` Step 6 を「watch 内蔵の自動 renew」に書き換え、手動 renew を冗長化解除

### Tests

- **Total: 96 tests passing** (前 87 → +9)
- 新規: SendReply owner 検証 2 / 429 対応 4 / watch lease 関連 2 / 既存 watch テスト 1 件修正

### Notes

- LineBridge 実装は A 案で**計画凍結**（TelegramSecretary 実機検証を先に着手、本体安定後に再開）
- Stage 5: Cloud Routine 環境での実機検証は別途

## [0.1.0] - 2026-05-26

### Added — Stage 1〜4 完了、87 tests green

**Domain**: 認可・offset・lease・正規化・injection フラグの純粋ロジック層
- `AuthorizedChats` (chat_id allowlist、IDOR 防止)
- `UpdateOffset` (単調増加保証、再処理時の冪等性)
- `SessionLease` (heartbeat + TTL、crash 自己治癒対応)
- `TelegramUpdate` / `OutboundMessage`
- `normalize_input` (NFKC 正規化 + サロゲートペア安全化)
- `flag_injection` (role override / system prompt / credentials の検知フラグ、ブロックせず記録)
- `TelegramSecretaryError` / `InvalidOffsetError` / `LeaseConflictError` / `AuthFailureError`

**UseCase**: Port 越しのオーケストレーション、fake adapter で全分岐検証
- `AcquireLease` / `RenewLease` / `ReleaseLease`
- `FetchAuthorizedUpdates` (取得→認可フィルタ→正規化→フラグ判定→emit)
- `SendReply` (送信成功時のみ offset advance + lease renew)
- Ports: `UpdateSource` / `MessageSink` / `OffsetStore` / `LeaseStore`

**Interface (Adapter)**: 実 I/O 実装
- `TelegramApiGateway` (httpx, retry, 401 検出, UA 設定)
- `JsonOffsetStore` / `JsonLeaseStore` (破損 JSON フォールバック)
- `StdoutEventEmitter` (Monitor 消費用 JSON Lines、ensure_ascii=False)

**Infrastructure + CLI**:
- `Config.from_env` (fail-fast バリデーション)
- `main.py` (subcommands: `validate-config` / `lease` / `poll` / `watch` / `send-reply` / `test`)
- `bootstrap.sh` (依存導入 + validate-config)
- `watch_loop.sh` (`watch` の薄いラッパー)

### Tests

- Domain: 35 tests
- UseCase: 18 tests
- Adapters: 23 tests
- CLI (main): 11 tests
- **Total: 87 tests passing**

### Pending — Stage 5

- Cloud Routine 統合と環境実測（セッション寿命・watch アイドル枠消費）
- Custom network policy で `api.telegram.org` 開通確認
- E2E（自分の bot に 1 通送る→watch→Monitor→send-reply）
- LineBridge 連携実装（別 Expertise、Railway 相乗り）
