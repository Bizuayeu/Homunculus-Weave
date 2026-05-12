---
name: newscaster-daily-digest
description: 前日(JST 00:00-23:59)公開のナルエビちゃんニュース(news.nullevi.app)を Gmail で 0:10 JST に大環主へダイジェスト配信する Cloud Routine 用スキル。description 整形のみで LLM 再要約はしない（「ベタにまとめる」設計、L00473）。
---

# NewsCaster — 前日ダイジェスト配信スキル

## 概要

- **対象フィード**: [news.nullevi.app/rss](https://news.nullevi.app/rss)（🦐 ナルエビちゃんニュース、AI関連トピック）
- **対象範囲**: JST 前日 00:00〜23:59 公開のエントリ
- **配信時刻**: 毎日 0:10 JST（Cloud Routine cron `10 0 * * * Asia/Tokyo`）
- **要約方針**: description は既に1段落の要旨なので **再要約しない**。整形して並べるのみ
- **配信先**: env var `NEWSCASTER_RECIPIENT_EMAIL` で指定
- **配信元**: env var `NEWSCASTER_SENDER_EMAIL` で指定（BlueberrySprite と OAuth token.json 共有を想定）（OAuth token.json 共有）

## Daily Workflow（Cloud Routine 起動時に実行）

```
1. validate-config で env vars を確認
2. dry-run で前日範囲のRSS取得→フィルタ→整形を試走（任意）
3. run で本送信
```

Cloud Routine 内では `python scripts/main.py run` を直接実行する。

## Subcommands

| Command | 機能 | Exit code |
|---|---|---|
| `run` | RSS取得→前日フィルタ→整形→送信→状態永続化 | 0=成功, 1=fetch/mail失敗, 2=設定エラー, 3=認証エラー |
| `dry-run` | 送信なしで整形までを実施し本文を確認 | 同上 |
| `test` | Gmail疎通テスト用に1通だけ送信 | 同上 |
| `validate-config` | 必須env varsの欠損検出 | 0=OK, 2=欠損あり |

`run` は冪等性あり：同日に複数回実行されてもメールは1通のみ送信される（`state/sent_dates.json` で管理）。

## RunResult

| Result | 意味 |
|---|---|
| `SENT` | 前日エントリあり、送信成功、状態永続化 |
| `NO_ITEMS` | 前日エントリ0件、送信スキップ（沈黙の許容） |
| `ALREADY_SENT` | 当日分は既に送信済み、スキップ |
| `DRY_RUN` | `dry-run` モードで整形まで実行 |

## Architecture（Clean Architecture 4層）

```
scripts/
├── domain/         # 値オブジェクト（NewsItem, DailyDigest, DateRangeJST, DigestConfig）
├── usecases/       # Port + 4 UseCase（FetchAndFilter / FormatDigest / SendEmail / RunDaily orchestrator）
├── adapters/       # RssXmlGateway, GmailApiMailGateway, JsonStateStore
├── infrastructure/ # google_oauth_provider
└── tests/          # pytest（77 tests、Domain/UseCase/Adapter 全層カバー）
```

依存方向は内向きのみ。Domain → 外側 import なし。

## 環境変数

| Var | 必須 | 説明 | 既定 |
|---|---|---|---|
| `NEWSCASTER_SENDER_EMAIL` | ✓ | 送信元 Gmail アドレス | — |
| `NEWSCASTER_RECIPIENT_EMAIL` | ✓ | 配信先 Gmail アドレス | — |
| `NEWSCASTER_OAUTH_TOKEN_PATH` | ✓* | BBS の token.json パス | — |
| `NEWSCASTER_OAUTH_TOKEN_JSON` | ✓* | inline token JSON（Cloud Routine env注入用） | — |
| `NEWSCASTER_RSS_URL` | — | RSSエンドポイント | `https://news.nullevi.app/rss` |
| `NEWSCASTER_USER_AGENT` | — | RSS取得時UA（Bot検知対策、Chrome系必須） | Chrome 124 系 |
| `NEWSCASTER_STATE_DIR` | — | 状態ファイルディレクトリ | `<skill_dir>/state` |
| `NEWSCASTER_MAIL_RETRY_COUNT` | — | Gmail送信リトライ回数 | `3` |

\* `NEWSCASTER_OAUTH_TOKEN_PATH` または `NEWSCASTER_OAUTH_TOKEN_JSON` のいずれかが必須。BBS の token.json をそのまま共有可。

## Failure Modes

- **環境構成異常（bootstrap 段階、Todo 0）** → Cloud Routine 起動時に `scripts/bootstrap.sh` を source する前提（`ROUTINE_PROMPT.md` Todo 0）。`google-api-python-client` / `google-auth-oauthlib` 未導入、debian 同梱 `cryptography` の RECORD 欠落、`_cffi_backend` の panic を bootstrap が `--ignore-installed cffi cryptography` で迂回し、`HTTPLIB2_CA_CERTS` を auto-export する。bootstrap が失敗した場合は以降の Todo を実行せず stderr を Routine ログに残す。**症状は run 時に `ModuleNotFoundError` / `_cffi_backend` panic / TLS verify 失敗として現れる**ため、下記 OAuth/Send 系 Failure Mode と取り違えないこと（exit 1/3 は bootstrap 通過後の本来の意味でのみ発火する想定）
- **RSS 403 / 5xx** → `RssFetchError` 送出、exit 1。Chrome系UA必須（Bot UAは403）
- **Gmail OAuth refresh 失敗** → `AuthError` 送出、exit 3、メール送信なし、状態更新なし（次回再試行可能）
- **前日 0 件** → `NO_ITEMS` で沈黙、メール送信なし、状態更新なし
- **既に送信済み** → `ALREADY_SENT` でスキップ、再送なし
- **状態ファイル破損** → 空集合にフォールバック、新規mark_sent成功時に上書き

## Out of Scope

- LLM要約（「ベタにまとめる」L00473、descriptionそのまま使う）
- 複数フィード対応（news.nullevi.app/rss のみ）
- HTML メール（plain text のみ）
- X投稿・SNS共有（BlueberrySprite 別経路）

## Provenance

- 設計: L00480 (2026-05-12)
- 実装計画: `IMPLEMENTATION_PLAN.md`（Clean Architecture × TDD、Stage 1〜4 で 77 tests green）
- 既存パターン参照: BlueberrySprite（Cloud Routine 自律エージェント完成形）
