# TelegramSecretary

Telegram Bot API の long-polling を Cloud Routine 上で常駐させ、認可済みチャットからのメッセージに Weave（SecretaryRole）が即応する対話チャネル。

Webhook 不可な Cloud Routine 環境制約を、long-polling + Monitor 駆動ループで回避する設計（IMPLEMENTATION_PLAN.md L20 参照）。

## アーキテクチャ

Clean Architecture 4 層（Domain → UseCase → Interface → Infrastructure）。詳細は [`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md)。

LINE 経由の薄いラッパーは [`LineBridge/`](./LineBridge/) を参照（Railway 相乗りの別サービスとして実装予定）。

## Quickstart（ローカル動作確認）

```powershell
cd C:\Users\anyth\DEV\homunculus\Weave\Expertises\TelegramSecretary

# 依存インストール
python -m pip install -e ".[dev]"

# 環境変数設定
$env:TELEGRAM_BOT_TOKEN = "<bot-token-from-botfather>"
$env:TELEGRAM_SECRETARY_AUTHORIZED_CHATS = "[<your-chat-id>]"
$env:TELEGRAM_SECRETARY_STATE_DIR = ".\state"

# 設定検証
python scripts/main.py validate-config

# 疎通テスト（owner chat に ping を送る）
python scripts/main.py test --chat-id <your-chat-id>

# 1サイクル poll（getUpdates → JSON Lines で stdout に emit）
python scripts/main.py poll --timeout 5
```

## テスト

```powershell
python -m pytest scripts/tests/ -v
```

現在 **87 tests green**（Stage 1-4 完了、Stage 5 は実機検証フェーズ）。

## env vars

| Var | Required | 概要 |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ | BotFather から取得 |
| `TELEGRAM_SECRETARY_AUTHORIZED_CHATS` | ✅ | JSON array of int (chat_id allowlist) |
| `TELEGRAM_SECRETARY_STATE_DIR` | optional | 既定 `./state` |
| `TELEGRAM_SECRETARY_SESSION_ID` | optional | リース owner ID（省略時は uuid 自動生成） |

## Subcommands

| Command | 機能 | Exit code |
|---|---|---|
| `validate-config` | env vars と設定の検証 | 0=OK, 2=設定欠損 |
| `lease acquire\|renew\|release` | リースロック操作 | 0=成功, 4=conflict, 2=設定 |
| `poll` | getUpdates 1サイクル | 0=OK, 1=fetch失敗, 3=auth失敗 |
| `watch` | 長期 long-poll ループ | 長時間常駐 |
| `send-reply --chat-id --update-id --text-file` | 返信送信 | 0=OK, 1=送信失敗, 3=auth, 4=lease |
| `test --chat-id` | 疎通テスト ping | 0=OK, 1/3 |

## 関連ドキュメント

- [SKILL.md](./SKILL.md) — スキルマニフェスト
- [ROUTINE_PROMPT.md](./ROUTINE_PROMPT.md) — Cloud Routine prompt body
- [CHANGELOG.md](./CHANGELOG.md) — 変更履歴
- [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) — 実装計画（本イベント駆動開発の経緯ゆえ保持・修正方針）
- [LineBridge/IMPLEMENTATION_PLAN.md](./LineBridge/IMPLEMENTATION_PLAN.md) — LINE 連携の薄ラッパー実装計画
