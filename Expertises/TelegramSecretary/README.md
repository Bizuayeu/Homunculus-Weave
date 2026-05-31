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
# image は render_status="passthrough"（Vision native、Read tool で直接解釈）
# PDF は render_status="ok" + derived_image_paths（常に画像化、Stage 11.5。全文は render-pdf --text）
# zip 等は render_status="skipped"
# 壊れたファイル等で render が失敗すると render_status="failed"
```

### PDF を試す（Stage 11.5 常に画像化 + render-pdf オンデマンド）

```powershell
# bot に PDF + caption "中身を読んで" を送ってから：
python scripts/main.py poll --timeout 5
# PDF は常に画像化 → render_status="ok" + rendered_text="" +
#   derived_image_paths=[先頭 cap 枚 png] + page_count（実総数）（Stage 11.5、pypdfium2）
#   → Weave は先頭最大 5 枚を Read で Vision → 大枠把握 → ①②③を判断
# ① 全文テキストが要る → オンデマンドで pdfplumber 抽出：
python scripts/main.py render-pdf --path <local_path> --text
#   → {"mode":"text","render_status":"ok","page_count":N,"rendered_text":"--- page 1 ---\n..."}
# ② cap 超（21枚目以降）のページ画像が要る → オンデマンドで画像化：
python scripts/main.py render-pdf --path <local_path> --pages 21-22
#   → {"mode":"pages","pages":"21-22","derived_image_paths":[...]}
# cap（既定20、TELEGRAM_SECRETARY_PDF_IMAGE_MAX_PAGES）超は先頭20枚、page_count は実総数
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
# 無音/壊れ/デコード不可は render_status="ok" + rendered_text=""（failed でなく「音声なし」扱い、PyAV が 0 フレームを返す）
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

現在 **369 tests green**（Stage 1-11.5 実装完了、詳細内訳は CHANGELOG 参照）。**Stage 9 E2E（音声）・Stage 10.4 E2E（PDF テキスト層）ともに PASS（2026-05-30 Live E2E）**——Stage 9 は Linux wheel・A〜D ケース・retention、Stage 10.4 は Read tool 不使用での PDF 内容到達・文字化け PDF のクリーン抽出・スキャン PDF の空 ok・壊れ PDF の failed を確認。**Stage 11.5（PDF は常に画像化、テキスト全文・cap 超ページは `render-pdf` でオンデマンド）は pypdfium2/pdfplumber 実 API を adapter test で検証済み、Live E2E（最大 5 枚 Vision → `render-pdf` 往復）も全5ケース PASS（2026-05-31 Cloud Routine 実機）**。Stage 5 / 6.5 / 7.5 / 8.5 E2E は実機検証フェーズ。

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
- win_amd64 wheel + **Cloud Routine（Linux）wheel ともに動作検証済み**（Linux は 2026-05-30 Live E2E：`moonshine-voice 0.0.59` + `av 17.0.1`、システム ffmpeg 不在でも PyAV 同梱 ffmpeg でデコード）。**kotoba-whisper への切替は当面不要**（年商 $1M 到達 or License 方針変更時に再検討）

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
| `TELEGRAM_SECRETARY_BUNDLE_VOICE` | optional | 音声/動画 STT（moonshine+av）を bootstrap で導入するか（既定 true）。`false` で除外＝音声は `skipped` にフォールバック。moonshine Community License は年商$1M 未満のみ商用無料ゆえ、大規模は `false`（or kotoba-whisper 移行）|
| `TELEGRAM_SECRETARY_OUTBOUND_MAX_SIZE_BYTES` | optional | **送信**添付の上限（既定 50MB = 52428800、Telegram bot API 上限）。超過は送信前に `AttachmentTooLarge` で弾く（exit 2、Stage 8） |
| `TELEGRAM_SECRETARY_PDF_IMAGE_MAX_PAGES` | optional | PDF 受信時に事前画像化する先頭ページ数の上限（既定 20）。超多ページの disk/トークン暴走の安全弁。21 枚目以降は `render-pdf --pages` でオンデマンド、`page_count` は実総数を emit（Stage 11.5） |

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
