# Changelog

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
