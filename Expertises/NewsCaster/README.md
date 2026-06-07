# NewsCaster

複数 RSS フィードの前日エントリを Gmail で配信するユーザスキル。cloud routine（**Claude Code Routines**＝Anthropic のクラウド実行スケジュールエージェント基盤。Remote 実行の routine ＝ cloud routine）で毎日 0:10 JST に自動実行。フィード別ポリシーで装飾強めエッセイ系メディアは cloud routine 内の親プロセス Weave がベタ化する（L00473）。

デフォルトフィード: 🦐 [ナルエビちゃんニュース](https://news.nullevi.app)

## Quickstart（ローカル動作確認）

```powershell
cd C:\Users\anyth\DEV\Homunculus-Weave\Expertises\NewsCaster

# 依存インストール（venv 推奨）
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"

# 環境変数設定（BBS と token.json を共有）
$env:NEWSCASTER_SENDER_EMAIL = "<your-sender>@gmail.com"
$env:NEWSCASTER_RECIPIENT_EMAIL = "<your-recipient>@gmail.com"
$env:NEWSCASTER_OAUTH_TOKEN_PATH = "C:\Users\anyth\DEV\Homunculus-Weave\Expertises\BlueberrySprite\token.json"

# 設定検証
python scripts/main.py validate-config

# 整形プレビュー（送信なし）
python scripts/main.py dry-run

# テストメール（1通だけ）
python scripts/main.py test

# 実運用
python scripts/main.py run
```

## テスト

```powershell
pip install -e ".[dev]"
python -m pytest scripts/tests/ -v
```

Stage 1〜6 で計 **137 tests** が green。

## 環境変数

| Var | 必須 | 説明 |
|---|---|---|
| `NEWSCASTER_SENDER_EMAIL` | ✓ | 送信元 Gmail アドレス |
| `NEWSCASTER_RECIPIENT_EMAIL` | ✓ | 配信先 Gmail アドレス |
| `NEWSCASTER_OAUTH_TOKEN_PATH` | ✓* | OAuth token.json パス（BBS と共有可） |
| `NEWSCASTER_OAUTH_TOKEN_JSON` | ✓* | inline JSON（cloud routine env用） |
| `NEWSCASTER_FEEDS` | — | JSON 配列でマルチフィード設定（後述） |
| `NEWSCASTER_RSS_URL` | — | 単一フィード URL（後方互換）。既定: `https://news.nullevi.app/rss` |
| `NEWSCASTER_USER_AGENT` | — | 既定: Chrome 124 系（Bot検知対策） |
| `NEWSCASTER_STATE_DIR` | — | 既定: `<skill_dir>/state` |
| `NEWSCASTER_MAIL_RETRY_COUNT` | — | 既定: `3` |

\* PATH or JSON のいずれか必須。

### `NEWSCASTER_FEEDS` 設定例

```json
[
  {"name":"ナルエビちゃんニュース","url":"https://news.nullevi.app/rss","policy":"passthrough"},
  {"name":"Wireless Wire News","url":"https://wirelesswire.jp/feed/","policy":"weave_compact"}
]
```

- `policy: passthrough` — description をそのまま使う（要約済みフィード向け）
- `policy: weave_compact` — cloud routine 内の親プロセス Weave が装飾を剥いで1〜2文に圧縮する（装飾エッセイ系フィード向け）
- 優先順位: `NEWSCASTER_FEEDS` ＞ `NEWSCASTER_RSS_URL` 単数 ＞ デフォルトフィード
- 単一 PASSTHROUGH 構成なら `run` 一発で動く（Stage 4 互換）

### ベタ化挙動（WEAVE_COMPACT）

`WEAVE_COMPACT` ポリシーのフィードがある場合、`run` の代わりに以下の三段フローが必要：

1. `dry-run` で `{{WEAVE_COMPACT:<guid>}}` プレースホルダを含む subject/body を出力
2. 親プロセス Weave が dry-run 出力を読んでプレースホルダを 1〜2 文のベタ化テキストに置き換え
3. `send-rendered --subject "..." --body-file <path>` で書き換え済み body を直接送信

これにより Domain/UseCase 層は LLM 依存ゼロを維持（Testability 最優先）。詳細フローは [`ROUTINE_PROMPT.md`](./ROUTINE_PROMPT.md) を参照。

## cloud routine 登録

`/schedule` 経由で以下を登録：

```
cron: 10 0 * * * Asia/Tokyo
prompt: ROUTINE_PROMPT.md を参照
env: 上記環境変数を cloud routine の Environment に設定
```

詳細は [`ROUTINE_PROMPT.md`](ROUTINE_PROMPT.md) を参照。

## トラブルシューティング

### `Configuration errors: NEWSCASTER_OAUTH_TOKEN_PATH or NEWSCASTER_OAUTH_TOKEN_JSON is required`
→ env var を設定。BBS の token.json をそのまま指せる。

### RSS が 403 Forbidden
→ `NEWSCASTER_USER_AGENT` が Bot 系UA になっていないか確認。Chrome 系UA で取れることは検証済（[`scripts/tests/adapters/fixtures/sample_rss.xml`](scripts/tests/adapters/fixtures/sample_rss.xml) は実フィードの先頭3件相当）。

### RSS が古い／前日エントリ 0 件でメール空振り
→ CDN エッジキャッシュ起因の可能性。`RssXmlGateway` は cache-buster クエリ `?_=<epoch>` と `Cache-Control: no-cache, no-store, max-age=0` + `Pragma: no-cache` を毎回付与しており、Vercel/Cloudflare 系エッジを貫通する想定（[CHANGELOG `[0.1.2]`](CHANGELOG.md) 参照）。それでも 0 件なら **実際に前日公開が無かった** 可能性が高い。

### Gmail API `403 PERMISSION_DENIED`
→ token.json の scope に `https://www.googleapis.com/auth/gmail.send` が含まれているか確認。BBS と共有しているなら自動的に含まれる。

### cloud routine 環境で `CERTIFICATE_VERIFY_FAILED`
→ httplib2 が独自 CA store を使う。`HTTPLIB2_CA_CERTS=/etc/ssl/certs/ca-certificates.crt` を env 設定（コード側で `setdefault` 済み、env で override 可能）。

### 同一日に複数回実行してもメールは1通だけ
→ 仕様。`state/sent_dates.json` で冪等性管理。再送したいなら該当日エントリを手動削除。

## 設計判断

- **要約しない**: description が既に1段落の要旨。LLM再要約は「ベタにまとめる」原則（L00473）に反する
- **token.json共有可**: BlueberrySprite と sender Gmail を共通化すれば初回OAuth省略
- **依存最小化**: 標準 `urllib` + `xml.etree` + `google-api-python-client` + `google-auth-oauthlib` のみ
- **冪等性**: 同日二重送信防止、0件沈黙、再実行安全

## License

個人スキル。配布想定なし。
