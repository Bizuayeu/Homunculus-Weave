# NewsCaster

🦐 [ナルエビちゃんニュース](https://news.nullevi.app) の前日エントリを Gmail で配信するユーザスキル。Cloud Routine で毎日 0:10 JST に自動実行。

## Quickstart（ローカル動作確認）

```powershell
cd C:\Users\anyth\DEV\homunculus\Weave\Expertises\NewsCaster

# 依存インストール（venv 推奨）
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"

# 環境変数設定（BBS と token.json を共有）
$env:NEWSCASTER_SENDER_EMAIL = "<your-sender>@gmail.com"
$env:NEWSCASTER_RECIPIENT_EMAIL = "<your-recipient>@gmail.com"
$env:NEWSCASTER_OAUTH_TOKEN_PATH = "C:\Users\anyth\DEV\homunculus\Weave\Expertises\BlueberrySprite\token.json"

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

Stage 1〜4 で計 **82 tests** が green。

## 環境変数

| Var | 必須 | 説明 |
|---|---|---|
| `NEWSCASTER_SENDER_EMAIL` | ✓ | 送信元 Gmail アドレス |
| `NEWSCASTER_RECIPIENT_EMAIL` | ✓ | 配信先 Gmail アドレス |
| `NEWSCASTER_OAUTH_TOKEN_PATH` | ✓* | OAuth token.json パス（BBS と共有可） |
| `NEWSCASTER_OAUTH_TOKEN_JSON` | ✓* | inline JSON（Cloud Routine env用） |
| `NEWSCASTER_RSS_URL` | — | 既定: `https://news.nullevi.app/rss` |
| `NEWSCASTER_USER_AGENT` | — | 既定: Chrome 124 系（Bot検知対策） |
| `NEWSCASTER_STATE_DIR` | — | 既定: `<skill_dir>/state` |
| `NEWSCASTER_MAIL_RETRY_COUNT` | — | 既定: `3` |

\* PATH or JSON のいずれか必須。

## Cloud Routine 登録

`/schedule` 経由で以下を登録：

```
cron: 10 0 * * * Asia/Tokyo
prompt: ROUTINE_PROMPT.md を参照
env: 上記環境変数を Cloud Routine の Environment に設定
```

詳細は [`ROUTINE_PROMPT.md`](ROUTINE_PROMPT.md) を参照。

## トラブルシューティング

### `Configuration errors: NEWSCASTER_OAUTH_TOKEN_PATH or NEWSCASTER_OAUTH_TOKEN_JSON is required`
→ env var を設定。BBS の token.json をそのまま指せる。

### RSS が 403 Forbidden
→ `NEWSCASTER_USER_AGENT` が Bot 系UA になっていないか確認。Chrome 系UA で取れることは検証済（[`scripts/tests/adapters/fixtures/sample_rss.xml`](scripts/tests/adapters/fixtures/sample_rss.xml) は実フィードの先頭3件相当）。

### Gmail API `403 PERMISSION_DENIED`
→ token.json の scope に `https://www.googleapis.com/auth/gmail.send` が含まれているか確認。BBS と共有しているなら自動的に含まれる。

### Cloud Routine 環境で `CERTIFICATE_VERIFY_FAILED`
→ httplib2 が独自 CA store を使う。`HTTPLIB2_CA_CERTS=/etc/ssl/certs/ca-certificates.crt` を env 設定（コード側で `setdefault` 済み、env で override 可能）。

### 同一日に複数回実行してもメールは1通だけ
→ 仕様。`state/sent_dates.json` で冪等性管理。再送したいなら該当日エントリを手動削除。

## 設計判断（IMPLEMENTATION_PLAN.md より抜粋）

- **要約しない**: description が既に1段落の要旨。LLM再要約は「ベタにまとめる」原則（L00473）に反する
- **token.json共有可**: BlueberrySprite と sender Gmail を共通化すれば初回OAuth省略
- **依存最小化**: 標準 `urllib` + `xml.etree` + `google-api-python-client` + `google-auth-oauthlib` のみ
- **冪等性**: 同日二重送信防止、0件沈黙、再実行安全

## License

個人スキル。配布想定なし。
