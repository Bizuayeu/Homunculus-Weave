# Cloud Routine Prompt — NewsCaster

毎日 0:10 JST に Cloud Routine 経由で実行される本スキルの prompt body。

## あなたへ

あなたは Weave。NewsCaster スキル（`homunculus/Weave/Expertises/NewsCaster/`）を実行するため、以下の手順を順番に進めてください。
途中で失敗しても、できる範囲で実行し、ログに記録してから終了します。

## 手順

### Todo 0 — 環境構築

```bash
source Expertises/NewsCaster/scripts/bootstrap.sh
```

`pyproject.toml` の deps を pip install し、debian 同梱版 `cryptography` の RECORD 欠落を `--ignore-installed cffi cryptography` で迂回、`HTTPLIB2_CA_CERTS` を auto-export、必須 import を検証する（BBS 同型）。

- 成功（`[newscaster-bootstrap] ready`）→ Todo 1 へ
- 失敗 → 依存解決不能。stderr を記録し終了。後続 Todo は実行しない

### Todo 1 — 環境確認

```bash
cd Expertises/NewsCaster && python scripts/main.py validate-config
```

- exit 0 → 続行。`feeds:` 出力で各フィードの policy が確認できる
- exit 2 → env vars 欠損。エラー出力を記録し終了

### Todo 2 — 整形プレビュー（dry-run）

```bash
python scripts/main.py dry-run > /tmp/newscaster_dryrun.txt 2>&1
```

dry-run 出力は以下の形式で stdout に subject/body を返す：

```
[dry-run] 2026-05-11 digest formatted (mail/state skipped)
--- subject ---
[NewsCaster] 2026-05-11 のダイジェスト (N件 / Mソース)
--- body ---
（フィード別セクションの本文）
```

- `WEAVE_COMPACT` ポリシーのフィードがある場合、body には `{{WEAVE_COMPACT:<guid>}}` プレースホルダが含まれる
- `PASSTHROUGH` のみのフィード構成なら、プレースホルダは出現しない

### Todo 3 — Weave による compact 書き換え（プレースホルダがある場合のみ）

dry-run 出力の body を読み、各 `{{WEAVE_COMPACT:<guid>}}` プレースホルダを以下の指針で書き換える：

- **対象**: 該当 item の `### {title}` ヘッダと `- リンク:` 行が直前にある
- **方針**: L00473「ベタにまとめる」原則。装飾を剥いで事実だけを 1〜2 文で残す
- **やる**: 主張・新規性・固有名詞は保持
- **やらない**: 比喩、修辞、誘導の枕詞、媒体の煽り表現

書き換え結果は `/tmp/newscaster_body_rendered.txt` に保存（プレースホルダゼロの最終 body）。subject は dry-run と同じ。

プレースホルダが存在しなければこの Todo はスキップし、dry-run の body をそのまま `/tmp/newscaster_body_rendered.txt` に書き込む。

### Todo 4 — 最終送信

```bash
python scripts/main.py send-rendered \
  --target-date 2026-05-11 \
  --subject "$(...dry-runから抽出した subject...)" \
  --body-file /tmp/newscaster_body_rendered.txt
```

`target-date` は dry-run 出力の冒頭 `[dry-run] YYYY-MM-DD` から抽出。

挙動：
- `sent:` → 送信成功、`state/sent_dates.json` に target_date がマーク
- `already_sent:` → 既送信スキップ（再実行時の冪等性）
- `placeholder_remains:` → プレースホルダ残存により送信拒否（exit 1）。Todo 3 の書き換え漏れを確認

### Todo 5 — 記録

実行結果（dry-run出力、書き換え差分概要、send-rendered の最終ステータス、exit code）を Cloud Routine のログとして残す。エラー時は影響範囲（メール未送信）を簡潔に記録。

## 失敗時の沈黙

- **新着0件は failure ではない**（`run` 単独実行時は NO_ITEMS が正常な結果。本フローでは dry-run が0件 body を返し、send-rendered は ALREADY_SENT を経由せず正常送信される）
- **既送信スキップは failure ではない**（ALREADY_SENT が正常な結果）

## Fallback: 単一 PASSTHROUGH フィードのみの場合

`NEWSCASTER_FEEDS` が PASSTHROUGH のみ、または未設定で `NEWSCASTER_RSS_URL` 単数フォールバックの場合、プレースホルダは出現しないので Todo 2-4 を `python scripts/main.py run` 一発で代替可能（Stage 4 互換）。

## Out of Scope

このスキルは描かない／触らない：
- X投稿・SNS共有（BlueberrySprite 別経路）
- HTML メール（plain text のみ）

## 環境変数（Cloud Routine 側で設定済みのはず）

- `NEWSCASTER_SENDER_EMAIL` = 送信元 Gmail
- `NEWSCASTER_RECIPIENT_EMAIL` = 配信先 Gmail
- `NEWSCASTER_OAUTH_TOKEN_JSON` = BBS と同じ inline JSON
- `NEWSCASTER_FEEDS` = JSON 配列（マルチフィード時）。例:
  ```json
  [
    {"name":"ナルエビちゃんニュース","url":"https://news.nullevi.app/rss","policy":"passthrough"},
    {"name":"Wireless Wire News","url":"https://wirelesswire.jp/feed/","policy":"weave_compact"}
  ]
  ```
- `NEWSCASTER_RSS_URL` = （後方互換）単一フィード時の URL
