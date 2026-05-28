# TelegramSecretary

Telegram Bot API の long-polling を Cloud Routine 上で常駐させ、認可済みチャットからのメッセージに Weave（SecretaryRole）が即応する対話チャネル。

Webhook 不可な Cloud Routine 環境制約を、long-polling + /goal deadline 駆動ループで回避する設計（`watch --exit-on-message` で即応再起動。詳細は [`ROUTINE_PROMPT.md`](./ROUTINE_PROMPT.md)、GOAL_KEEPALIVE_PLAN.md）。

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

# watch の deadline 駆動を試す（D: --exit-on-message で即応再起動、--max-duration で窓満了 exit）
python scripts/main.py lease acquire
python scripts/main.py watch --exit-on-message --max-duration 10 --timeout 5
#   → メッセージが来たサイクルで即 exit 0／無ければ 10 秒の窓満了で exit 0
python scripts/main.py lease release
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
# zip 等は render_status="skipped"
# 壊れたファイル等で markitdown が失敗すると render_status="failed"
```

### voice / audio / video を試す（Stage 9 Native Voice/Audio/Video Inbox）

```powershell
# bot に voice メモ（ボイスメッセージ）を送ってから：
python scripts/main.py poll --timeout 5
# → emit JSON Lines の media[0] に:
#    - kind="voice"
#    - rendered_text="（Moonshine が文字起こしした日本語 transcript）"
#    - render_status="ok"
# audio(mp3) / video(mp4) も音声トラックが transcript 化される（key frame Vision は後続フェーズ）
# Moonshine 日本語モデル base-ja は初回 transcribe 時に自動DL（約134MB、ローカルキャッシュ）
# transcriber 未注入（or Medium モード）では音声は render_status="skipped"
```

### 生成物を送り返す（Stage 8 Outbound Media）

```powershell
# Weave 生成物（画像/レポート）を Telegram に送り返す（lease 取得済み前提）
python scripts/main.py send-reply --chat-id <id> --update-id <uid> --text-file reply.txt --file figure.png
# → --file は複数指定可。画像(.jpg/.png/.webp/.gif)→sendPhoto、他→sendDocument に自動振り分け
# → 本文は添付1件かつ1024字以内なら caption に載る、それ以外は別 sendMessage で先送り
# → --reply-to <message_id> で reply threading、送信前に typing インジケータを表示
# → 50MB 超 or 存在しないパスは送信前に弾く（exit 2）
```

## テスト

```powershell
python -m pytest scripts/tests/ -v
```

現在 **273 tests green**（Stage 1-4 完了 + v0.1.1 設計ホール修正で +9 + v0.1.2 運用律 B 案で +3 + v0.2.0 Stage 6 Multimodal Inbox で +66 + v0.2.1 follow-up で +6 + v0.3.0 Stage 7 MediaRenderer で +43 + v0.4.0 Stage 9 Native Voice/Audio/Video Inbox で +32 + v0.5.0 Stage 8 Outbound Media で +27、Stage 5 / 6.5 / 7.5 / 8.5 / 9 E2E は実機検証フェーズ）。

### 依存ツリー注記

`markitdown[docx,pptx,xlsx]>=0.1.6` の install は内部で以下の再帰依存を連れてきます（Stage 7.3 着手時に `pip install --dry-run` で実測）:

- `mammoth` (docx parser)
- `python-pptx` / `openpyxl` (pptx/xlsx parser、`python-docx` も入る)
- `magika` + `onnxruntime` (ML model でファイルタイプ自動判定、~25MB 程度)
- `markdownify` / `beautifulsoup4` / `lxml` (html→md)
- `sympy` / `coloredlogs` / `humanfriendly` 等の小さな utility

Cloud Routine の bootstrap がやや遅くなる点に留意（初回 `pip install` で 30秒程度、以降はキャッシュで高速）。markitdown 自体は MIT、再帰依存も全て MIT/BSD/Apache 系で利用可。

**Stage 9 追加依存**（voice/audio/video transcript）:

- `moonshine-voice>=0.0.59`（~56.5MB wheel、**torch-free**・onnxruntime）— 日本語 STT。日本語モデル `base-ja`（~134MB）は初回 transcribe 時にランタイムDL（`%LOCALAPPDATA%/moonshine_voice` 等にキャッシュ）。⚠️ **Community License は年商 $1M 未満のみ商用無料**。めぐる組の本番利用は Enterprise License（有償）か、`kotoba-whisper-v2.0`（Apache-2.0）への切替が必要
- `av>=17.0`（PyAV、~29MB wheel）— **ffmpeg を wheel 内包**し OGG/OPUS/mp4 を 16kHz mono float へ decode（システム ffmpeg 不要）
- win_amd64 wheel で動作検証済み。Cloud Routine（Linux）wheel の存在は本番デプロイ時に確認（無ければ kotoba-whisper へ fallback）

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
| `TELEGRAM_SECRETARY_OUTBOUND_MAX_SIZE_BYTES` | optional | **送信**添付の上限（既定 50MB = 52428800、Telegram bot API 上限）。超過は送信前に `AttachmentTooLarge` で弾く（exit 2、Stage 8） |

> **`/goal` deadline 駆動の運用変数**（`TS_SESSION_DURATION_SEC`=7200 / `TS_SESSION_DEADLINE_EPOCH`=now+duration / `TS_POLL_SET_SEC`=580 / `TS_POLL_BASH_TIMEOUT_MS`=600000 / `TS_MAX_TURNS`=300）は `bootstrap.sh` が export（SSoT）。グローバル `BASH_MAX_TIMEOUT_MS=600000` は `.private/.claude/settings.json`（`BASH_DEFAULT_TIMEOUT_MS` は据え置き＝他コマンド 2分）。

## Subcommands

| Command | 機能 | Exit code |
|---|---|---|
| `validate-config` | env vars と設定の検証 | 0=OK, 2=設定欠損 |
| `lease acquire\|renew\|release [--owner]` | リースロック操作 | 0=成功, 4=conflict, 2=設定 |
| `poll` | getUpdates 1サイクル | 0=OK, 1=fetch失敗, 3=auth失敗 |
| `watch [--owner] [--max-iterations N] [--max-duration SEC] [--exit-on-message]` | 長期 long-poll ループ（サイクル毎に lease renew）。`--max-duration`=窓満了 exit 0、`--exit-on-message`=メッセージ受信サイクルで exit 0（D 即応再起動） | 長時間常駐 / 窓畳み |
| `send-reply --chat-id --update-id --text-file [--owner] [--file ...] [--reply-to]` | 返信送信。`--file`（複数可）で画像→sendPhoto・他→sendDocument を添付、`--reply-to` で reply threading（Stage 8） | 0=OK, 1=送信失敗, 2=添付不正, 3=auth, 4=lease |
| `test --chat-id` | 疎通テスト ping | 0=OK, 1/3 |
| `cleanup-media` | `state_dir/media/` 配下で retention 超過の保存ファイルを削除（手動 / 外部 cron 用）。`watch` は `--cleanup-interval`（既定 120 サイクル≒1h）で自動発火 | 0=OK, 2=設定欠損 |
| `individuals\|tasks\|knowledge {list\|get\|add\|remove}` | 管理表 CRUD。`get`/`remove` は `--key`、`add` は `--json`/`--json-file`。値オブジェクトで入力検証（不正は exit 2）。全操作は `/secretary` がラップ予定 | 0=OK, 2=不正入力 |

`--owner` は省略可（運用律 B 案：`source bootstrap.sh` で env 経由自動同期）。緊急時の上書きにのみ使用。

## 関連ドキュメント

- [SKILL.md](./SKILL.md) — スキルマニフェスト
- [DESIGN.md](./DESIGN.md) — 設計正典（Architecture + Data Architecture + 公式 plugin 採否 Scope）
- [STRUCTURE.md](./STRUCTURE.md) — 構造地図（ディレクトリ・管理表/Identities 配置・データフロー・早見表）
- [SECURITY.md](./SECURITY.md) — 網羅的セキュリティ正典（脅威モデル・配布前チェックリスト）
- [ROUTINE_PROMPT.md](./ROUTINE_PROMPT.md) — Cloud Routine prompt body
- [CHANGELOG.md](./CHANGELOG.md) — 変更履歴
- [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) — 実装計画（本イベント駆動開発の経緯ゆえ保持・修正方針）
- [DOCUMENTATION_PLAN.md](./DOCUMENTATION_PLAN.md) — ドキュメント体系・管理表データアーキテクチャの整備計画
- [LineBridge/IMPLEMENTATION_PLAN.md](./LineBridge/IMPLEMENTATION_PLAN.md) — LINE 連携の薄ラッパー実装計画
