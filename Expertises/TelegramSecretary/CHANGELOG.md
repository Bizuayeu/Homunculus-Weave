# Changelog

## [0.2.1] - 2026-05-27 — Stage 6 follow-up: cleanup 配線 + caption E2E テスト

### Added

- `cleanup-media` subcommand を追加（`main.py cmd_cleanup_media`）— `state_dir/media/` 配下で `media_retention_hours` 超過の保存ファイルを削除する単独実行エンドポイント
- `cmd_watch` に **cleanup hook** を配線（v0.2.0 で関数だけ実装し未配線だった漏れの修正）— `--cleanup-interval` サイクル毎に `cleanup_media_dir` を発火（default 120 ≒ 1h with timeout=30s、`0` で無効化）

### Tests

- **Total: 171 tests passing**（v0.2.0 の 165 → +6）
- `test_cleanup_media_subcommand_removes_expired_files` / `_no_op_when_media_dir_missing`
- `test_watch_runs_cleanup_hook_at_interval` / `_skips_cleanup_when_interval_zero`
- `test_poll_emits_caption_in_text_with_photo` — Stage 6.5 follow-up として **CLI 層 + photo + caption の end-to-end** を明示テスト化（ユニットテスト `test_caption_is_merged_into_normalized_text` は既に green だったが、CLI 経由の経路が未カバーだった）
- `test_poll_caption_above_text_for_text_message_with_caption` — caption + text 両方ある稀ケースで `見出し\n本文` 結合を CLI 経由で確認

### Rationale

- v0.2.0 の "doc complete" と実配線の間にあった 2 つのギャップに対応:
  - `cleanup_media_dir` 関数は実装＋単体テスト済みだったが `main.py` に呼び出しなし → watch hook + CLI subcommand の両方を配線
  - Live E2E で「caption "見える？" を送ったのに emit text:""」報告（実際は caption 無し送信疑い）の切り分け基盤として、CLI 層 caption 統合の E2E テストを明示化

## [0.2.0] - 2026-05-27 — Stage 6 Multimodal Inbox (Doc Complete / E2E Pending)

### Added — photo / document / caption 受信対応

**Domain**:
- `MediaAttachment` 値オブジェクト（`kind: photo|document` / `file_id` / `mime_type` / `size`、frozen dataclass、`@classmethod from_photo_api` / `from_document_api`）
- `merge_caption_into_text(text, caption)` 純関数（caption + "\n" + text を結合、欠落は falsy 統一）
- `MediaSizeLimitExceeded` exception（`flag_injection` 同型の「フラグ化して emit、ブロックしない」原則）
- `TelegramUpdate` に `media: List[MediaAttachment]` / `caption: Optional[str]` field 追加（default_factory で後方互換）、`from_api` が photo（最大解像度）/ document / caption を抽出

**UseCase**:
- `MediaDownloader` Port（`download(file_id, target_dir) -> Path`）
- `DownloadAuthorizedMedia` UseCase（認可済み update の media を size 制限内で download、size 超過は内部 raise → catch → skip_reason="media_size_exceeded" に変換）
- `MediaDownloadResult` dataclass（`update_id` / `media` / `local_path` / `skip_reason`）
- `FetchAuthorizedUpdates` を caption 統合へ拡張（normalized_text に caption を merge してから injection 判定）

**Interface (Adapter)**:
- `TelegramApiGateway.get_file(file_id) -> str`（既存 `_request_with_retry` 流用、5xx retry / 401 AuthFailureError）
- `TelegramMediaDownloader` 新規（別 httpx.Client で `/file/bot<TOKEN>/<file_path>` 取得、target ファイル名は `<file_id 先頭16>_<basename>` で衝突回避、`raise ... from None` で chain 切り token 漏洩防止）
- `StdoutEventEmitter` を v2 化（`v: 2` + `media: []` 追加、`emit(update, download_results=None)` で download 結果を統合、Medium モードは local_path null）

**Infrastructure**:
- `Config` に 3 env 追加: `TELEGRAM_SECRETARY_MEDIA_MAX_SIZE_BYTES`（default 20MB）/ `TELEGRAM_SECRETARY_MEDIA_RETENTION_HOURS`（default 24）/ `TELEGRAM_SECRETARY_MEDIA_ENABLE_DOWNLOAD`（default true）
- `_parse_positive_int` / `_parse_bool` ヘルパで env 解析統一、不正値は `EnvironmentError`（exit 2）
- `media_cleanup.cleanup_media_dir(target_dir, retention_seconds, now=None)` ユーティリティ（fake clock 注入可能、OSError は best-effort で吸収、サブディレクトリ無視）
- `cmd_poll` / `cmd_watch` に Heavy / Medium モード切替を統合（`media_enable_download` で分岐、Heavy 時は downloader を内側で確保、watch は loop 外で 1 回作って使い回し）

### Changed

- emit JSON Lines は `v: 2` を含む（v1 は `v` キー欠落として後方互換扱い）
- `ROUTINE_PROMPT.md` Step 5 を v2 schema に差し替え、`local_path` の三状態（非null=Read で開く / null+skip_reason=サイズ超過の旨応答 / null+null=Medium モード）処理分岐を明記
- Failure modes に `media_size_exceeded` / media download 失敗を追加

### Tests

- **Total: 165 tests passing**（v0.1.2 の 99 → +66）
- Domain: +13（MediaAttachment + merge_caption / TelegramUpdate.from_api 拡張 5 / 既存 media は空 list backward compat）
- UseCase: +13（DownloadAuthorizedMedia 5 / FetchAuthorizedUpdates caption 3 / TelegramUpdate media 5）
- Adapters: +14（get_file 4 / media_downloader 5 / emitter v2 5）
- Infrastructure: +23（config 17 parametrize 込 / media_cleanup 6）
- CLI: +3（Medium モード切替）

### Design Notes

- **Medium + Heavy ハイブリッド採用**（Reversibility）: env で切替、default Heavy で 24-7 即応性を取り、運用負荷顕在化時に Medium へ倒せる
- **token redact 多層防御**: `safe_id = file_id[:8]` + status code のみ例外メッセージに含める、`raise ... from None` で chain 切り、テストで `"TEST_TOKEN" not in str(excinfo.value)` を明示検証
- **既存 emit テスト破壊なし**（3-Strike 予想 #4 杞憂）: 既存テストは個別 field を読むだけで `v` キーに触れていなかったため、v2 追加で regression ゼロ
- **`.gitignore` 確認のみ**: 既存の `Expertises/*/state/` で state/media/ も既に除外済み、追加変更なし

### Live E2E Pending (Fresh Session 必須)

実機 E2E（photo / document / caption → Weave Vision 解釈 → 返信）は新コンテナでの実機検証が残る:

- E2E: photo + caption "見える？" → emit に media[0].local_path → 親プロセス Weave が Read で開いて Vision 解釈 → Telegram に返信到達
- E2E: 大画像（>20MB）送信 → `skip_reason="media_size_exceeded"` → サイズ超過応答
- E2E: PDF document 送信 → mime_type=application/pdf で Read 経由取得
- retention 実測: 24h 経過後 `media_cleanup.cleanup_media_dir` で該当ファイル削除

Stage 5 と同様、Custom Environment の Network policy 反映には新コンテナが必要。env は Stage 5 で設定済みのものをそのまま継承可能（追加 env 3 件は default 値で動くので未設定でも E2E 可能）。

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
