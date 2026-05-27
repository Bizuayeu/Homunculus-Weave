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

### photo / document を試す（Stage 6 Multimodal Inbox）

```powershell
# bot に画像 + caption "見える？" を送ってから（Telegram アプリで）：
python scripts/main.py poll --timeout 5
# → emit JSON Lines に v:2 + media[0] (kind=photo, local_path=<state_dir>/media/...) が乗る
# → caption が text に統合されて "見える？" として出力

# Heavy/Medium モード切替
$env:TELEGRAM_SECRETARY_MEDIA_ENABLE_DOWNLOAD = "false"  # Medium: メタのみ、download せず
python scripts/main.py poll --timeout 5
# → media[].local_path is null
```

### docx / pptx / xlsx を試す（Stage 7 MediaRenderer）

```powershell
# bot に .docx ファイル + caption "要約して" を送ってから：
python scripts/main.py poll --timeout 5
# → emit JSON Lines の media[0] に:
#    - kind="document"
#    - file_name="spec.docx"
#    - rendered_text="# 仕様書\n..."（markitdown が md 化）
#    - render_status="ok"
# image/pdf は render_status="passthrough"（Read tool が直接対応、render 不要）
# 音声/動画 (audio/*, video/*) や zip 等は render_status="skipped"
# 壊れたファイル等で markitdown が失敗すると render_status="failed"
```

## テスト

```powershell
python -m pytest scripts/tests/ -v
```

現在 **214 tests green**（Stage 1-4 完了 + v0.1.1 設計ホール修正で +9 + v0.1.2 運用律 B 案で +3 + v0.2.0 Stage 6 Multimodal Inbox で +66 + v0.2.1 follow-up で +6 + v0.3.0 Stage 7 MediaRenderer で +43、Stage 5 / 6.5 / 7.5 は実機検証フェーズ）。

### 依存ツリー注記

`markitdown[docx,pptx,xlsx]>=0.1.6` の install は内部で以下の再帰依存を連れてきます（Stage 7.3 着手時に `pip install --dry-run` で実測）:

- `mammoth` (docx parser)
- `python-pptx` / `openpyxl` (pptx/xlsx parser、`python-docx` も入る)
- `magika` + `onnxruntime` (ML model でファイルタイプ自動判定、~25MB 程度)
- `markdownify` / `beautifulsoup4` / `lxml` (html→md)
- `sympy` / `coloredlogs` / `humanfriendly` 等の小さな utility

Cloud Routine の bootstrap がやや遅くなる点に留意（初回 `pip install` で 30秒程度、以降はキャッシュで高速）。markitdown 自体は MIT、再帰依存も全て MIT/BSD/Apache 系で利用可。

## env vars

| Var | Required | 概要 |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ | BotFather から取得 |
| `TELEGRAM_SECRETARY_AUTHORIZED_CHATS` | ✅ | JSON array of int (chat_id allowlist) |
| `TELEGRAM_SECRETARY_STATE_DIR` | optional | 既定 `./state` |
| `TELEGRAM_SECRETARY_SESSION_ID` | optional | リース owner ID（省略時は uuid 自動生成）。**運用律 B 案**: `source bootstrap.sh` で自動 export され、`lease`/`watch`/`send-reply` 全コマンドで共有される |
| `TELEGRAM_SECRETARY_MEDIA_MAX_SIZE_BYTES` | optional | media download のサイズ上限（既定 20MB = 20971520）。超過は `skip_reason="media_size_exceeded"` で emit、download skip |
| `TELEGRAM_SECRETARY_MEDIA_RETENTION_HOURS` | optional | 保存 media の保持期限（既定 24）。`media_cleanup.cleanup_media_dir` が超過ファイルを削除 |
| `TELEGRAM_SECRETARY_MEDIA_ENABLE_DOWNLOAD` | optional | Heavy（true=既定）/ Medium（false）モード切替。Heavy は `state_dir/media/` に保存、Medium はメタのみで `local_path=null` |

## Subcommands

| Command | 機能 | Exit code |
|---|---|---|
| `validate-config` | env vars と設定の検証 | 0=OK, 2=設定欠損 |
| `lease acquire\|renew\|release [--owner]` | リースロック操作 | 0=成功, 4=conflict, 2=設定 |
| `poll` | getUpdates 1サイクル | 0=OK, 1=fetch失敗, 3=auth失敗 |
| `watch [--owner]` | 長期 long-poll ループ（サイクル毎に lease renew） | 長時間常駐 |
| `send-reply --chat-id --update-id --text-file [--owner]` | 返信送信 | 0=OK, 1=送信失敗, 3=auth, 4=lease |
| `test --chat-id` | 疎通テスト ping | 0=OK, 1/3 |
| `cleanup-media` | `state_dir/media/` 配下で retention 超過の保存ファイルを削除（手動 / 外部 cron 用）。`watch` は `--cleanup-interval`（既定 120 サイクル≒1h）で自動発火 | 0=OK, 2=設定欠損 |

`--owner` は省略可（運用律 B 案：`source bootstrap.sh` で env 経由自動同期）。緊急時の上書きにのみ使用。

## 関連ドキュメント

- [SKILL.md](./SKILL.md) — スキルマニフェスト
- [ROUTINE_PROMPT.md](./ROUTINE_PROMPT.md) — Cloud Routine prompt body
- [CHANGELOG.md](./CHANGELOG.md) — 変更履歴
- [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) — 実装計画（本イベント駆動開発の経緯ゆえ保持・修正方針）
- [LineBridge/IMPLEMENTATION_PLAN.md](./LineBridge/IMPLEMENTATION_PLAN.md) — LINE 連携の薄ラッパー実装計画
