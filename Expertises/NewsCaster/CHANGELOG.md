# Changelog

## [0.1.1] - 2026-05-12

### Changed
- `bootstrap.sh` を BlueberrySprite パターンに準拠して全面改修
  - `pyproject.toml` を SSoT として依存抽出（重複定義の排除）
  - `--ignore-installed cffi cryptography` リトライ機構（debian 同梱版 RECORD 欠落対策）
  - `import cryptography.exceptions` defensive sanity check
  - `HTTPLIB2_CA_CERTS` を `/etc/ssl/certs/ca-certificates.crt` 等から自動 export（httplib2 が `REQUESTS_CA_BUNDLE` / `SSL_CERT_FILE` を読まない問題への対策）
  - import verification（`googleapiclient` / `google.auth` / `google_auth_oauthlib` / `cryptography`）
- `source` / `bash` 両方の起動方法に対応（`HTTPLIB2_CA_CERTS` を親シェルに残したい場合は `source`）

### Why
- L00480 の初回 Cloud Routine 実行で `google-api-python-client` 系と `cryptography`/`cffi` が未導入のため起動失敗
- 手動で `pip install --ignore-installed cffi cryptography` で復旧したが、次回以降も再発するため bootstrap 側で恒久対策
- BBS で完全な処方が既に実装済みのため、フォント・SVG 等 BBS 固有層を除いて移植

## [0.1.0] - 2026-05-12

### Added
- 初回リリース。Clean Architecture × TDD（Stage 1〜4）で実装
- `news.nullevi.app/rss` から JST 前日エントリを抽出し Gmail で配信
- 4 subcommands: `run` / `dry-run` / `test` / `validate-config`
- 冪等性（`JsonStateStore`、同日二重送信防止）
- 0件沈黙の許容（NO_ITEMS）
- BlueberrySprite の token.json 共有可（同一送信元 Gmail を想定）
- 82 tests green（Domain / UseCase / Adapter / CLI 全層）

### Design Decisions
- LLM 再要約しない（「ベタにまとめる」、L00473）
- 標準 `urllib` + `xml.etree` でRSS取得（新規依存最小化）
- Chrome 系 User-Agent 明示（Bot UA は 403）
- 送信元 Gmail は BlueberrySprite と共用想定（env var `NEWSCASTER_SENDER_EMAIL`）

### References
- 実装計画: `IMPLEMENTATION_PLAN.md`
- 既存パターン: `homunculus/Weave/Expertises/BlueberrySprite/`
