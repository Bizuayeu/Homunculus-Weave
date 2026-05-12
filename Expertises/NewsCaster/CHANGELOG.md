# Changelog

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
