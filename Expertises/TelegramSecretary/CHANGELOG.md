# Changelog

## [0.4.0] - 2026-05-27 — Stage 9 Native Voice/Audio/Video Inbox: 音声 transcript (Doc Complete / E2E Pending)

### Added — voice / audio / video の中身理解（STT）

公式 telegram plugin（claude-plugins-official）が voice/audio/video を file_id forward + download 止まりで**中身理解しない**のに対し、本 Stage は音声を Moonshine 日本語 STT で transcript 化。Stage 7 の MediaRenderer 抽象に「音声→transcript も render の一種」として乗せ、emit スキーマは無変更（rendered_text 再利用）。

**Domain (9.1)**:
- `MediaAttachment.kind` に `voice|audio|video|video_note` 追加、`from_voice_api` / `from_audio_api` / `from_video_api` / `from_video_note_api`（voice/video_note は file_name なし、voice 既定 mime=audio/ogg、video/video_note 既定 video/mp4）

**UseCase (9.2 / 9.4 / 9.6-i)**:
- `TelegramUpdate.from_api` が voice/audio/video/video_note を抽出（既存 `FetchAuthorizedUpdates` / `DownloadAuthorizedMedia` は file_id ベースで kind 非依存＝**コード変更ゼロ流用**）
- `_route_mime` に `_TRANSCRIBE_MIME_PREFIXES=("audio/","video/")` → `"transcribe"` ルート追加
- `RenderAuthorizedMedia(renderer, transcriber=None)` で mime 分岐（**transcriber 未注入時は audio/video→skipped に後方互換フォールバック**）

**Interface / Infrastructure (9.5b)**:
- `FfmpegAudioPreprocessor`（PyAV `av`、任意音声/動画→16kHz mono float、**ffmpeg を wheel 内包＝システム ffmpeg 不要**、壊れ/音声なしは空リスト）
- `MoonshineTranscriber`（`MediaRenderer` Port 実装、`moonshine-voice` の日本語 `base-ja` モデル、**model load は lazy**＝初回の実音声 render 時、例外は `render_status="failed"` 化）
- `cmd_poll` / `cmd_watch` に transcriber 注入配線（lazy import）

### Changed

- emit JSON Lines は**スキーマ無変更**（音声 transcript は `rendered_text` に乗り `render_status="ok"`、Stage 7 の枠そのまま）。Weave 側は `media.kind` で transcript か md かを判別
- `pyproject.toml` に `moonshine-voice` + `av`（PyAV）を追加

### Tests

- **Total: 246 tests passing**（v0.3.1 の 214 → +32）
- Domain: +13（from_voice/audio/video/video_note_api 8 / from_api 抽出 5）
- UseCase: +11（download/fetch kind 非依存流用 5 / audio・video transcribe routing 6）
- Adapters: +6（FfmpegAudioPreprocessor 3 / MoonshineTranscriber 3、実 PyAV + 実 Moonshine integration）
- CLI: +2（Medium モードで voice/video emit）

### 実機検証（ローカル、2026-05-27）

- Moonshine 日本語 STT 動作確認（`DEV/verify_moonshine.py`）: RTF 0.43〜0.69（リアルタイム超）、建設業務語彙を正確認識、末尾欠落あり（Base 58M / CER 13.62%）
- 本番 adapter 経由の日本語 transcribe（`verify_adapter.py`）: 直接 API と同結果＝配線バグなし
- 動画(mp4)音声トラック transcribe（`verify_video.py`）: PyAV が動画コンテナの音声を decode → transcript 成功（108544 samples @16kHz）

### ライセンス申し送り（重要）

Moonshine Community License は「年商 $1M 未満は商用も無料」（"non-commercial" 表記だが実態は年商閾値）。**めぐる組（年商50-60億）の本番利用は Enterprise License（有償、contact@moonshine.ai）が必要**。テスト段階は Community で可（大環主決裁）。本番商用化前に Enterprise 契約 or `kotoba-whisper-v2.0`（Apache-2.0、日本語 large-v3 超）へ `MediaRenderer` Port 差し替え。

### Live E2E Pending (Fresh Session 必須)

- E2E: voice メモ送信 → emit `rendered_text` に transcript → Weave が内容応答
- E2E: audio(mp3) / video(mp4) の音声 transcript
- E2E: 壊れ音声 → `render_status="failed"` 応答
- 残: ①Cloud Routine（Linux）の `moonshine-voice` wheel 存在確認（win_amd64 で検証済み、Linux wheel 無ければ kotoba fallback）②末尾欠落緩和

### 後続フェーズ

- **Stage 9.6-ii: 動画 key frame Vision**（emit 複数 media 拡張が必要、段階的に後続）

## [0.3.1] - 2026-05-27 — Stage 7 follow-up: test fixture 依存の宣言漏れ修正

### Fixed

- `pyproject.toml` の dev extras に `python-docx` / `python-pptx` / `openpyxl` を明示追加。`test_markitdown_renderer.py` の fixture が `from docx import Document` 等で**書込**ライブラリを使うが、`markitdown[docx]` は docx **読込**に mammoth を使うため **python-docx を引かない**。fresh clone / CI で declared deps だけ入れると `test_renders_docx_to_markdown` が `ModuleNotFoundError: No module named 'docx'` で 1 件落ちる環境依存を解消（python-pptx / openpyxl は markitdown extras でも入るが、テスト依存を markitdown 内部依存に暗黙依存させず明示）
- `dependencies` のコメント修正（「markitdown が内部で python-docx を引く」→ 実態は mammoth が docx 読込担当、python-docx は引かれない）

### Rationale

- 新セッションの live レビューで発見（クリーン環境で **213 passed / 1 failed**）。「214 green」は開発機にたまたま python-docx があった環境依存だった
- Testability > Readability の判断: テスト依存を markitdown の内部依存に暗黙依存させず dev extras で明示し、宣言通り 214 が再現する状態にする。織守のように無人で回す前提では CI 再現性が効く
- コード本体の瑕疵ではなく**テスト依存の宣言漏れ**（実 render 経路は本物の docx 契約書で render_status=ok / 可読テキスト取得を live 実証済み）

## [0.3.0] - 2026-05-27 — Stage 7 Multimodal Inbox: MediaRenderer (Doc Complete / E2E Pending)

### Added — ドキュメント系 mime の Weave 判断委任完成形

L00473 分業（スキル=決定論的 fetch/render、Weave=判断と推論）を MediaRenderer 抽象で完成形に寄せる。Step 5 が「`local_path` → `Read` 一択」から「render → Weave が読む → Weave が動く」に一般化。

**Domain**:
- `MediaAttachment.file_name: Optional[str]` field 追加（document の元ファイル名取り込み、Weave の判断材料）
- `RenderedMedia` 値オブジェクト新設（`rendered_text: Optional[str]` / `render_status: str` の frozen dataclass）
- `_VALID_RENDER_STATUSES = frozenset({"ok", "passthrough", "skipped", "failed"})` で Domain 構造的保証（不正値は ValueError）

**UseCase**:
- `MediaRenderer` Port（`render(media, local_path) -> RenderedMedia`、Adapter 内部 catch + flag 化契約）
- `RenderAuthorizedMedia` UseCase（mime-routing 三分岐: passthrough / render / skipped、download skip 継承）
- `RenderResult` dataclass（`MediaDownloadResult` 延長として `rendered: RenderedMedia` を持つ）
- `_route_mime()` 純関数（image/* + application/pdf + text plain/csv/markdown + json → passthrough、docx/pptx/xlsx + text/html → render、その他 → skipped）

**Interface (Adapter)**:
- `MarkitdownRenderer` Adapter（`markitdown.MarkItDown` を呼んで md 化、内部 Exception catch → `RenderedMedia(render_status="failed")` 化、stderr warning は `file_id[:8]` のみで絶対パス・file_id 全文を秘匿）
- `StdoutEventEmitter` を v2 schema 拡張（`v: 2` 維持、`rendered_text` / `render_status` / `file_name` を**追加のみ**で v3 化なし、欠落=null で後方互換）

**Infrastructure**:
- `pyproject.toml` に `markitdown[docx,pptx,xlsx]>=0.1.6` 追加（extras で必要 mime に絞る、再帰依存膨張: mammoth/magika/onnxruntime/python-docx/python-pptx/openpyxl 等は受容）
- `cmd_poll` / `cmd_watch` に renderer instantiation 配線（**lazy import** で validate-config / Medium モードから markitdown 依存を切り離す）
- `cmd_watch` の renderer は loop 外で 1 回作って使い回し（MarkItDown の magika ML model load コスト削減、downloader と同じパターン）

### Changed

- emit JSON Lines の `media[]` 各 item に新フィールド: `file_name` / `rendered_text` / `render_status`（Stage 6 までの emit は欠落=null で後方互換）
- `ROUTINE_PROMPT.md` Step 5 を v2 schema 一般化:
  - **`render_status` 四状態の処理分岐**を明示（ok=rendered_text を直接活用 / passthrough=Read で開く / failed=読めなかった応答 / skipped=未対応 mime 応答）
  - Failure modes に `render_failed` / `render_skipped` を追加

### Tests

- **Total: 214 tests passing**（v0.2.1 の 171 → +43）
- Domain: +10（MediaAttachment.file_name 4 / RenderedMedia 6）
- UseCase: +18（RenderAuthorizedMedia passthrough 6 / render 4 / skipped 4 / 継承 1 / 複数+空 2 / file_name 1）
- Adapters: +13（MarkitdownRenderer 7 実 markitdown integration / emitter render フィールド 6）
- CLI: +2（Medium モード render フィールド null 後方互換）

### Design Notes / 発見

- **markitdown の寛容性**（Stage 7.3 着手時に判明）: garbage バイト列 (.docx 拡張子) でも magika ML model が plain text と判定し rendered_text にバイト列を返す（`render_status="ok"`）。本物の `failed` パスに入るのは空 .docx（BadZipFile）/ 存在しないファイル（FileNotFoundError）等の構造的失敗時のみ。この寛容性は L00473 分業の「Weave が意味のあるテキストか判断する」責務に整合的なため受容
- **emit schema v2 維持**（設計分岐 #3）: フィールド追加のみで v3 化せず、既存 consumer（ROUTINE_PROMPT.md / Weave）と既存テストへの影響を最小化
- **Port シグネチャ単一**（設計分岐 #1）: `render(media, local_path) -> RenderedMedia` 単一 Port + mime-routing は UseCase 側、markitdown が内部で mime 判定する以上 Adapter 内蔵 routing は冗長
- **Adapter 内部 catch**（設計分岐 #2）: Stage 6 `MediaSizeLimitExceeded` 同型の「フラグ化して emit、ブロックしない」、UseCase の `RenderAuthorizedMedia.execute` が個別 media 失敗で全体中断しない Reversibility

### Live E2E Pending (Fresh Session 必須)

実機 E2E（docx/pptx/xlsx の Weave 要約往復、render failure の skip、retention 動作）は新コンテナでの実機検証が残る:

- E2E: docx + caption "要約して" → emit に `rendered_text` 非 null → Weave が md を読んで要約返信
- E2E: pptx → mime_type=...presentationml で render → Weave 応答到達
- E2E: xlsx → 表データを md 化（パイプ区切り）→ Weave がデータ列を読んで応答
- E2E: 壊れた docx → `render_status="failed"` で emit → Weave が file_name 込みで「読めない」応答
- E2E: mp3 / mp4 → `render_status="skipped"` で emit → Weave が「音声/動画は現在未対応」応答

Stage 5 / 6.5 と同じく、Custom Environment の Network policy 反映と pyproject 更新の両方が新コンテナで反映されるため fresh session 起動が前提。env は Stage 5/6 のものを継承可能。

## [0.2.1] - 2026-05-27 — Stage 6 follow-up: cleanup 配線 + caption E2E テスト

### Added

- `cleanup-media` subcommand を追加（`main.py cmd_cleanup_media`）— `state_dir/media/` 配下で `media_retention_hours` 超過の保存ファイルを削除する単独実行エンドポイント
- `cmd_watch` に **cleanup hook** を配線（v0.2.0 で関数だけ実装し未配線だった漏れの修正）— `--cleanup-interval` サイクル毎に `cleanup_media_dir` を発火（default 120 ≒ 1h with timeout=30s、`0` で無効化）

### Tests

- **Total: 171 tests passing**（v0.2.0 の 165 → +6）
- `test_cleanup_media_subcommand_removes_expired_files` / `_no_op_when_media_dir_missing`
- `test_watch_runs_cleanup_hook_at_interval` / `_skips_cleanup_when_interval_zero`
- `test_poll_emits_caption_in_text_with_photo` — Stage 6.5 follow-up として **CLI 層 + photo + caption の end-to-end** を明示テスト化（ユニットテスト `test_caption_is_merged_into_normalized_text` は既に green だったが、CLI 経由の経路が未カバーだった）
- `test_poll_caption_above_text_for_text_message_with_caption` — caption + text 両方ある稀ケースで `見出し\n本文` 結合を CLI 経由で確認

### Rationale

- v0.2.0 の "doc complete" と実配線の間にあった 2 つのギャップに対応:
  - `cleanup_media_dir` 関数は実装＋単体テスト済みだったが `main.py` に呼び出しなし → watch hook + CLI subcommand の両方を配線
  - Live E2E で「caption "見える？" を送ったのに emit text:""」報告（実際は caption 無し送信疑い）の切り分け基盤として、CLI 層 caption 統合の E2E テストを明示化

## [0.2.0] - 2026-05-27 — Stage 6 Multimodal Inbox (Doc Complete / E2E Pending)

### Added — photo / document / caption 受信対応

**Domain**:
- `MediaAttachment` 値オブジェクト（`kind: photo|document` / `file_id` / `mime_type` / `size`、frozen dataclass、`@classmethod from_photo_api` / `from_document_api`）
- `merge_caption_into_text(text, caption)` 純関数（caption + "\n" + text を結合、欠落は falsy 統一）
- `MediaSizeLimitExceeded` exception（`flag_injection` 同型の「フラグ化して emit、ブロックしない」原則）
- `TelegramUpdate` に `media: List[MediaAttachment]` / `caption: Optional[str]` field 追加（default_factory で後方互換）、`from_api` が photo（最大解像度）/ document / caption を抽出

**UseCase**:
- `MediaDownloader` Port（`download(file_id, target_dir) -> Path`）
- `DownloadAuthorizedMedia` UseCase（認可済み update の media を size 制限内で download、size 超過は内部 raise → catch → skip_reason="media_size_exceeded" に変換）
- `MediaDownloadResult` dataclass（`update_id` / `media` / `local_path` / `skip_reason`）
- `FetchAuthorizedUpdates` を caption 統合へ拡張（normalized_text に caption を merge してから injection 判定）

**Interface (Adapter)**:
- `TelegramApiGateway.get_file(file_id) -> str`（既存 `_request_with_retry` 流用、5xx retry / 401 AuthFailureError）
- `TelegramMediaDownloader` 新規（別 httpx.Client で `/file/bot<TOKEN>/<file_path>` 取得、target ファイル名は `<file_id 先頭16>_<basename>` で衝突回避、`raise ... from None` で chain 切り token 漏洩防止）
- `StdoutEventEmitter` を v2 化（`v: 2` + `media: []` 追加、`emit(update, download_results=None)` で download 結果を統合、Medium モードは local_path null）

**Infrastructure**:
- `Config` に 3 env 追加: `TELEGRAM_SECRETARY_MEDIA_MAX_SIZE_BYTES`（default 20MB）/ `TELEGRAM_SECRETARY_MEDIA_RETENTION_HOURS`（default 24）/ `TELEGRAM_SECRETARY_MEDIA_ENABLE_DOWNLOAD`（default true）
- `_parse_positive_int` / `_parse_bool` ヘルパで env 解析統一、不正値は `EnvironmentError`（exit 2）
- `media_cleanup.cleanup_media_dir(target_dir, retention_seconds, now=None)` ユーティリティ（fake clock 注入可能、OSError は best-effort で吸収、サブディレクトリ無視）
- `cmd_poll` / `cmd_watch` に Heavy / Medium モード切替を統合（`media_enable_download` で分岐、Heavy 時は downloader を内側で確保、watch は loop 外で 1 回作って使い回し）

### Changed

- emit JSON Lines は `v: 2` を含む（v1 は `v` キー欠落として後方互換扱い）
- `ROUTINE_PROMPT.md` Step 5 を v2 schema に差し替え、`local_path` の三状態（非null=Read で開く / null+skip_reason=サイズ超過の旨応答 / null+null=Medium モード）処理分岐を明記
- Failure modes に `media_size_exceeded` / media download 失敗を追加

### Tests

- **Total: 165 tests passing**（v0.1.2 の 99 → +66）
- Domain: +13（MediaAttachment + merge_caption / TelegramUpdate.from_api 拡張 5 / 既存 media は空 list backward compat）
- UseCase: +13（DownloadAuthorizedMedia 5 / FetchAuthorizedUpdates caption 3 / TelegramUpdate media 5）
- Adapters: +14（get_file 4 / media_downloader 5 / emitter v2 5）
- Infrastructure: +23（config 17 parametrize 込 / media_cleanup 6）
- CLI: +3（Medium モード切替）

### Design Notes

- **Medium + Heavy ハイブリッド採用**（Reversibility）: env で切替、default Heavy で 24-7 即応性を取り、運用負荷顕在化時に Medium へ倒せる
- **token redact 多層防御**: `safe_id = file_id[:8]` + status code のみ例外メッセージに含める、`raise ... from None` で chain 切り、テストで `"TEST_TOKEN" not in str(excinfo.value)` を明示検証
- **既存 emit テスト破壊なし**（3-Strike 予想 #4 杞憂）: 既存テストは個別 field を読むだけで `v` キーに触れていなかったため、v2 追加で regression ゼロ
- **`.gitignore` 確認のみ**: 既存の `Expertises/*/state/` で state/media/ も既に除外済み、追加変更なし

### Live E2E Pending (Fresh Session 必須)

実機 E2E（photo / document / caption → Weave Vision 解釈 → 返信）は新コンテナでの実機検証が残る:

- E2E: photo + caption "見える？" → emit に media[0].local_path → 親プロセス Weave が Read で開いて Vision 解釈 → Telegram に返信到達
- E2E: 大画像（>20MB）送信 → `skip_reason="media_size_exceeded"` → サイズ超過応答
- E2E: PDF document 送信 → mime_type=application/pdf で Read 経由取得
- retention 実測: 24h 経過後 `media_cleanup.cleanup_media_dir` で該当ファイル削除

Stage 5 と同様、Custom Environment の Network policy 反映には新コンテナが必要。env は Stage 5 で設定済みのものをそのまま継承可能（追加 env 3 件は default 値で動くので未設定でも E2E 可能）。

## Stage 5 進捗ノート - 2026-05-26

### Live Functional Verification (Routine 側ローカル検証)

実コード（`origin/main` の `cbaeecc` 時点）を /tmp に展開して、実プロセス・実ソケットで以下を検証（Telegram egress 不要な部分のみ）:

| Success Criterion | 結果 |
|---|---|
| lease 並走防止（2セッション競合） | ✅ sessB の acquire/renew が exit 4 |
| crash 自己治癒（stale 奪取） | ✅ ttl=1 失効後に別 owner が takeover |
| `validate-config` env 欠損/充足 | ✅ exit 2 / exit 0 |
| `watch` アイドル時の沈黙 | ✅ 空 getUpdates → emit 0 行（idle-zero の土台） |
| 認可フィルタ | ✅ 未認可 chat 999 を破棄、認可 12345 のみ emit |
| injection フラグ | ✅ `role_override` + `credentials_request` 検出 |
| offset 単調前進 | ✅ 未認可分も消費して 43=max(42)+1（無限再取得なし） |
| sendMessage 経路 | ✅ ローカル mock Telegram サーバー経由で実ソケット疎通 |

**機能パイプラインは実質グリーン**。Routine 側がローカル mock サーバーを 127.0.0.1 に立てて実コードを駆動した結果、Domain → UseCase → Adapter → Infrastructure の各層がプロダクションコードとして整合して動作することを確認。

### Live E2E Pending (Fresh Session 必須)

以下は本物の Telegram egress と bot token が必要で、新コンテナでの実機検証が残る（現セッションは egress 403 = `host_not_allowed` + token 未設定。allowlist 変更はコンテナ生成時のみ反映ゆえ既存セッションには波及しない）:

- egress 疎通: `curl https://api.telegram.org/botINVALID/getMe` で 401/404 確認
- `test --chat-id` で自分の bot への ping 到達
- `watch` + Monitor の実メッセージ 1 往復（E2E）
- **未文書化2点の実測**: セッション寿命（inactivity reclaim / hard cap）/ `watch` blocking 中のアイドル枠消費量
- `/schedule` 登録と cron 起動

### 次セッションの前準備（ユーザー）

1. **BotFather** で bot 作成 → `TELEGRAM_BOT_TOKEN` 取得
2. **chat_id 発見**: 作った bot に 1 通送信 → fresh session で `getUpdates` を 1 回叩いて chat_id を読む（鶏卵問題ゆえ最初だけ手動）
3. Environment に 2 つ設定: `TELEGRAM_BOT_TOKEN` / `TELEGRAM_SECRETARY_AUTHORIZED_CHATS=[<chat_id>]`、任意で `TELEGRAM_SECRETARY_STATE_DIR` を private リポ配下にして state をセッション跨ぎ永続化
4. `api.telegram.org` は allowlist 追加済み（確認のみ）
5. **新コンテナのセッションを起動**（env と egress は新コンテナから有効になる）

新セッションで「Stage 5 続き」と告げれば E2E + 寿命/枠実測を一気通貫で回す。

## [0.1.2] - 2026-05-26

### Added — 運用律 B 案: session_id の env 統一

- `bootstrap.sh` を NewsCaster と同型の **source/exec デュアル対応** に書き換え
  - source 時は env を親シェルに引き継ぎ、bash 実行時は依存導入のみ
  - `set -u` のみ採用（source 時に呼び出し元シェルへの影響を避けるため `set -e` は不使用）
- `bootstrap.sh` 末尾に `TELEGRAM_SECRETARY_SESSION_ID` の**冪等な自動 export** を追加
  - 未設定時は uuid から生成（`session-xxxxxxxx`）
  - 設定済みなら尊重（冪等性）
- `cmd_send_reply` に `--owner` 引数と CLI 層の owner 検証を追加
  - lease.owner と caller の owner が不一致なら exit 4（並走奪取の二重防御）
- `ROUTINE_PROMPT.md` Step 2 を `bash` から `source` 呼び出しに変更
  - 運用律 B 案を明記、各コマンドでの `--owner` 明示が不要に

### Changed

- 全 subcommand (`lease` / `watch` / `send-reply`) は `--owner > env > uuid` の優先順位で
  owner を解決。`source bootstrap.sh` で env を固定すれば全コマンド自動同期、
  緊急時の上書きは `--owner <id>` で可能

### Tests

- **Total: 99 tests passing** (96 → +3)
- 新規: send-reply owner mismatch / send-reply env owner sharing / watch env owner sharing

### Rationale

- Routine 側レビュー後の残課題（Step 5 と Step 6 の owner 整合性）への対応
- ProsCons 検討の結果 B 案（env 統一）採用：書き忘れ防止 = Routine 指摘①と同型の構造的取りこぼし対策
- Cloud Routine ではセッション毎に env が独立ゆえ env 汚染リスク構造的にゼロ

## [0.1.1] - 2026-05-26

### Fixed — Routine 側レビュー指摘対応

- **lease keep-alive 配線漏れ (指摘①)**: `watch` ループがアイドル時に lease を renew せず、無音期間に stale 化して並走奪取される設計ホールを修正。`cmd_watch` がサイクル末尾で自動 renew、奪取検出時は exit 4 で自己終了
- **SendReply の owner 検証 (指摘④-2)**: `SendReply.execute` で送信前に lease store を再 load して引数 lease.owner と一致するか検証、奪取済みなら `LeaseConflictError`
- **429/Retry-After 尊重 (指摘④-3)**: `TelegramApiGateway._request_with_retry` で 429 を 5xx と同様に retry 対象に追加、`Retry-After` ヘッダがあれば sleep（上限 `max_retry_after_seconds`、既定 60 秒で自損防止）

### Changed

- **テスト公開ポリシー統一 (指摘②訂正)**: `.gitignore` の `**/tests/` `**/test/` ルールを削除、PrecognitiveViewer 専用例外も削除。全 Expertises のテストを信頼性証拠として公開する方針に統一
- **state/ 誤コミット防止 (指摘④-1)**: `.gitignore` に `Expertises/*/state/` を追加
- `cmd_watch` に `--owner` 引数追加（lease renew 用）
- `ROUTINE_PROMPT.md` Step 6 を「watch 内蔵の自動 renew」に書き換え、手動 renew を冗長化解除

### Tests

- **Total: 96 tests passing** (前 87 → +9)
- 新規: SendReply owner 検証 2 / 429 対応 4 / watch lease 関連 2 / 既存 watch テスト 1 件修正

### Notes

- LineBridge 実装は A 案で**計画凍結**（TelegramSecretary 実機検証を先に着手、本体安定後に再開）
- Stage 5: Cloud Routine 環境での実機検証は別途

## [0.1.0] - 2026-05-26

### Added — Stage 1〜4 完了、87 tests green

**Domain**: 認可・offset・lease・正規化・injection フラグの純粋ロジック層
- `AuthorizedChats` (chat_id allowlist、IDOR 防止)
- `UpdateOffset` (単調増加保証、再処理時の冪等性)
- `SessionLease` (heartbeat + TTL、crash 自己治癒対応)
- `TelegramUpdate` / `OutboundMessage`
- `normalize_input` (NFKC 正規化 + サロゲートペア安全化)
- `flag_injection` (role override / system prompt / credentials の検知フラグ、ブロックせず記録)
- `TelegramSecretaryError` / `InvalidOffsetError` / `LeaseConflictError` / `AuthFailureError`

**UseCase**: Port 越しのオーケストレーション、fake adapter で全分岐検証
- `AcquireLease` / `RenewLease` / `ReleaseLease`
- `FetchAuthorizedUpdates` (取得→認可フィルタ→正規化→フラグ判定→emit)
- `SendReply` (送信成功時のみ offset advance + lease renew)
- Ports: `UpdateSource` / `MessageSink` / `OffsetStore` / `LeaseStore`

**Interface (Adapter)**: 実 I/O 実装
- `TelegramApiGateway` (httpx, retry, 401 検出, UA 設定)
- `JsonOffsetStore` / `JsonLeaseStore` (破損 JSON フォールバック)
- `StdoutEventEmitter` (Monitor 消費用 JSON Lines、ensure_ascii=False)

**Infrastructure + CLI**:
- `Config.from_env` (fail-fast バリデーション)
- `main.py` (subcommands: `validate-config` / `lease` / `poll` / `watch` / `send-reply` / `test`)
- `bootstrap.sh` (依存導入 + validate-config)
- `watch_loop.sh` (`watch` の薄いラッパー)

### Tests

- Domain: 35 tests
- UseCase: 18 tests
- Adapters: 23 tests
- CLI (main): 11 tests
- **Total: 87 tests passing**

### Pending — Stage 5

- Cloud Routine 統合と環境実測（セッション寿命・watch アイドル枠消費）
- Custom network policy で `api.telegram.org` 開通確認
- E2E（自分の bot に 1 通送る→watch→Monitor→send-reply）
- LineBridge 連携実装（別 Expertise、Railway 相乗り）
