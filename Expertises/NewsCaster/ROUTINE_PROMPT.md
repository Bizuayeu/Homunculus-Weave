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

- exit 0 → 続行
- exit 2 → env vars 欠損。エラー出力を記録し終了

### Todo 2 — 実行

```bash
python scripts/main.py run
```

挙動：
- **`sent:`** → 前日エントリありメール送信成功
- **`no_items:`** → 前日0件、メール送信なし（沈黙の許容）
- **`already_sent:`** → 当日分送信済み、スキップ
- **エラー** → stderr に記録、exit code に応じて以下を判断
  - exit 1 → RSS取得失敗 / Gmail送信失敗。再試行は次回 Routine に任せる
  - exit 3 → OAuth認証失敗。token.json の refresh_token が失効。手動oauth_setup必要

### Todo 3 — 記録

実行結果（stdout / stderr / exit code）を Cloud Routine のログとして残す。エラー時は影響範囲（メール未送信）を簡潔に記録。

## 失敗時の沈黙

- **新着0件は failure ではない**（NO_ITEMSが正常な結果）
- **既送信スキップは failure ではない**（ALREADY_SENTが正常な結果）

## Out of Scope

このスキルは描かない／触らない：
- LLM要約（descriptionそのまま）
- 複数フィード
- X投稿・SNS共有

## 環境変数（Cloud Routine 側で設定済みのはず）

- `NEWSCASTER_SENDER_EMAIL` = 送信元 Gmail
- `NEWSCASTER_RECIPIENT_EMAIL` = 配信先 Gmail
- `NEWSCASTER_OAUTH_TOKEN_JSON` = BBS と同じ inline JSON
