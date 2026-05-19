---
name: newscaster-daily-digest
description: 複数 RSS フィードの前日(JST 00:00-23:59)エントリを Gmail で 0:10 JST に大環主へダイジェスト配信する Cloud Routine 用スキル。フィード別ポリシー（PASSTHROUGH / WEAVE_COMPACT）で、要約済みフィード（ナルエビちゃんニュース等）はそのまま、装飾的エッセイ系フィード（Wireless Wire News 等）は親プロセス Weave がベタ化（L00473）。
---

# NewsCaster — 前日マルチフィードダイジェスト配信スキル

## 概要

- **対象フィード**: 環境変数 `NEWSCASTER_FEEDS`（JSON 配列）または `NEWSCASTER_RSS_URL`（後方互換単数）で指定
- **デフォルトフィード**: [news.nullevi.app/rss](https://news.nullevi.app/rss)（🦐 ナルエビちゃんニュース、AI関連トピック）
- **対象範囲**: JST 前日 00:00〜23:59 公開のエントリ
- **配信時刻**: 毎日 0:10 JST（Cloud Routine cron `10 0 * * * Asia/Tokyo`）
- **整形ポリシー二系統**:
  - `PASSTHROUGH`: description をそのまま使う（既に要約済みのフィード向け）
  - `WEAVE_COMPACT`: 親プロセス Weave がベタ化（装飾エッセイ系フィード向け）
- **配信先**: env var `NEWSCASTER_RECIPIENT_EMAIL` で指定
- **配信元**: env var `NEWSCASTER_SENDER_EMAIL` で指定（BlueberrySprite と OAuth token.json 共有を想定）

## Daily Workflow（Cloud Routine 起動時に実行）

```
1. validate-config で env vars と feeds を確認
2. dry-run で全フィードの前日範囲を取得→フィルタ→出典別整形（プレースホルダ含む本文を返す）
3. WEAVE_COMPACT のフィードがあれば、親プロセス Weave が dry-run 出力の `{{WEAVE_COMPACT:<guid>}}` を1〜2文に圧縮
4. send-rendered で書き換え済み subject/body を直接送信し state mark
```

PASSTHROUGH のみのフィード構成なら、`run` サブコマンド一発で完結（Stage 4 互換）。

詳細フローは [`ROUTINE_PROMPT.md`](./ROUTINE_PROMPT.md) を参照。

## Subcommands

| Command | 機能 | Exit code |
|---|---|---|
| `run` | RSS取得→前日フィルタ→整形→送信→状態永続化（プレースホルダ非含のフィード構成向け） | 0=成功, 1=fetch/mail失敗, 2=設定エラー, 3=認証エラー |
| `dry-run` | 送信なしで整形までを実施し本文を確認（プレースホルダ含む） | 同上 |
| `send-rendered` | Weave がプレースホルダ書き換え済みの subject/body を直接送信し state mark | 0=成功 or 既送信, 1=プレースホルダ残存 / 送信失敗, 2=設定エラー, 3=認証エラー |
| `test` | Gmail疎通テスト用に1通だけ送信 | 同上 |
| `validate-config` | 必須env varsとfeeds設定の検証 | 0=OK, 2=欠損あり |

`run` と `send-rendered` は冪等性あり：同 target_date への二重送信は `state/sent_dates.json` で防止。

## RunResult

| Result | 意味 |
|---|---|
| `SENT` | 前日エントリあり、送信成功、状態永続化 |
| `NO_ITEMS` | 前日エントリ0件、送信スキップ（沈黙の許容） |
| `ALREADY_SENT` | 当日分は既に送信済み、スキップ |
| `DRY_RUN` | `dry-run` モードで整形まで実行 |
| `PLACEHOLDER_REMAINS` | `send-rendered` 実行時に `{{WEAVE_COMPACT:<guid>}}` 残存検出、送信拒否 |

## Architecture（Clean Architecture 4層）

```
scripts/
├── domain/         # 値オブジェクト（NewsItem, DailyDigest, DateRangeJST, DigestConfig, FeedPolicy, FeedSource）
├── usecases/       # Port + UseCase（FetchAndFilter / FormatDigest / SendDigestEmail / SendRendered / RunDaily orchestrator）
├── adapters/       # RssXmlGateway (× N feeds), GmailApiMailGateway, JsonStateStore
├── infrastructure/ # google_oauth_provider
└── tests/          # pytest（137 tests、Domain/UseCase/Adapter 全層カバー）
```

依存方向は内向きのみ。Domain → 外側 import なし。LLM 依存は Domain/UseCase に侵入させず、Cloud Routine の親プロセス Weave 経由でコード外側に追い出している（Testability 最優先）。

## 環境変数

| Var | 必須 | 説明 | 既定 |
|---|---|---|---|
| `NEWSCASTER_SENDER_EMAIL` | ✓ | 送信元 Gmail アドレス | — |
| `NEWSCASTER_RECIPIENT_EMAIL` | ✓ | 配信先 Gmail アドレス | — |
| `NEWSCASTER_OAUTH_TOKEN_PATH` | ✓* | BBS の token.json パス | — |
| `NEWSCASTER_OAUTH_TOKEN_JSON` | ✓* | inline token JSON（Cloud Routine env注入用） | — |
| `NEWSCASTER_FEEDS` | — | JSON 配列（複数フィード設定） | — |
| `NEWSCASTER_RSS_URL` | — | RSSエンドポイント（後方互換単数指定） | `https://news.nullevi.app/rss` |
| `NEWSCASTER_USER_AGENT` | — | RSS取得時UA（Bot検知対策、Chrome系必須） | Chrome 124 系 |
| `NEWSCASTER_STATE_DIR` | — | 状態ファイルディレクトリ | `<skill_dir>/state` |
| `NEWSCASTER_MAIL_RETRY_COUNT` | — | Gmail送信リトライ回数 | `3` |

\* `NEWSCASTER_OAUTH_TOKEN_PATH` または `NEWSCASTER_OAUTH_TOKEN_JSON` のいずれかが必須。

### `NEWSCASTER_FEEDS` の JSON 形式

```json
[
  {"name":"ナルエビちゃんニュース","url":"https://news.nullevi.app/rss","policy":"passthrough"},
  {"name":"Wireless Wire News","url":"https://wirelesswire.jp/feed/","policy":"weave_compact"}
]
```

- `name`: 出典セクション見出しに使われる
- `url`: RSS エンドポイント URL
- `policy`: `passthrough`（既定）または `weave_compact`

優先順位: `NEWSCASTER_FEEDS` ＞ `NEWSCASTER_RSS_URL` 単数 ＞ デフォルトフィード。

## Failure Modes

- **環境構成異常（bootstrap 段階、Todo 0）** → Cloud Routine 起動時に `scripts/bootstrap.sh` を source する前提（`ROUTINE_PROMPT.md` Todo 0）。`google-api-python-client` / `google-auth-oauthlib` 未導入、debian 同梱 `cryptography` の RECORD 欠落、`_cffi_backend` の panic を bootstrap が `--ignore-installed cffi cryptography` で迂回し、`HTTPLIB2_CA_CERTS` を auto-export する。
- **個別フィード fetch 失敗（403 / 5xx 等）** → stderr に warn 後 skip。他フィードの結果は維持して送信される
- **全フィード fetch 失敗** → 最初の `RssFetchError` を送出、exit 1
- **`NEWSCASTER_FEEDS` 不正 JSON / 不正 policy 名 / 必須フィールド欠落** → `validate()` でエラー報告、exit 2
- **WEAVE_COMPACT 書き換え漏れ** → `send-rendered` が `{{WEAVE_COMPACT:<guid>}}` 残存を検出して送信拒否（exit 1）。Todo 3 のロジックを確認
- **Gmail OAuth refresh 失敗** → `AuthError` 送出、exit 3、メール送信なし、状態更新なし
- **前日 0 件** → `NO_ITEMS` で沈黙、メール送信なし、状態更新なし
- **既に送信済み** → `ALREADY_SENT` でスキップ、再送なし
- **状態ファイル破損** → 空集合にフォールバック、新規mark_sent成功時に上書き

## Out of Scope

このスキルは描かない／触らない：

- HTML メール（plain text のみ）
- X投稿・SNS共有（BlueberrySprite 別経路）
- Cloud Routine の外で LLM 推論を立てる subprocess（`claude -p` 等。L00473 と API 課金化原則）

## Provenance

- 初版設計: L00480 (2026-05-12)
- Stage 5 マルチフィード化設計: L00498 (2026-05-19)
- Stage 6 複数 `<category>` 要素対応: 2026-05-19（Wireless Wire 実運用検証から派生）
- 実装計画: `IMPLEMENTATION_PLAN.md`（Clean Architecture × TDD、Stage 1〜6 で 137 tests green）
- 既存パターン参照: BlueberrySprite（Cloud Routine 自律エージェント完成形）
