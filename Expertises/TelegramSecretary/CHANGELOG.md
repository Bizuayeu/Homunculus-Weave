# Changelog

## [0.10.1] - 2026-05-31 — Stage 11.5 Live E2E PASS（`render-pdf` オンデマンド往復、実機）

[0.10.0] で実装した Stage 11.5（PDF 常時画像化＋`render-pdf` オンデマンド）の **Telegram 実機 Live E2E を Cloud Routine 上で走破**（routine `telegram-secretary-stage11.5-e2e-pdf-ondemand`、全5ケース PASS）。最重要の「`rendered_text` 自動注入を廃し、Weave が能動的に `render-pdf --text/--pages` を叩いて到達できるか」が肯定された。

### Verified — Stage 11.5 Live E2E（Cloud Routine 実機、全5ケース PASS）

- **Case 1 テキスト PDF ✅【核心】**: 価格改定リスト 5p。`render_status=ok` + `rendered_text=""` + `page_count=5`。Weave が**能動的に** `render-pdf --text` を叩き `--- page N ---` マーカー付き全文を取得、3/4/5 ページ目の値上げ率をページ位置指定で正確に応答（旧 Stage 11 の自動 rendered_text 注入を廃した転換が実機で機能）
- **Case 2 スキャン/図面 PDF ✅**: Tree_of_Life.pdf 1p（カバラ生命の樹の線画）。画像 Vision で内容到達、`render-pdf --text` は `rendered_text=""` を正直に返す（テキスト層ゼロ）
- **Case 3 多ページ PDF ✅**: FLK 事後報告 17p（≤cap、全 17 枚画像化）。先頭 5 枚 Vision + page_count で総量把握 → send-reply で確認 → 指定の優勝プラン（page 14、N≤20）を `derived_image_paths[13]` からディスク Read（追加 render コストゼロ）
- **Case 4 cap 超 PDF ✅【新機能の核心】**: 地盤調査報告書 58p。`page_count=58`（実総数）/ `derived_image_paths=20`（cap 打切）。巻末ボーリング柱状図（PDF p33、cap 外）を **`render-pdf --pages` でオンデマンド生成**して引き当て（+2 ページオフセットを特定し探索）。58 頁中、必要な巻末頁だけを遅延生成する設計が実文書で稼働
- **Case 5 retention + 出力漏洩スキャン ✅**: `render()` 由来と `render-pdf --pages` 由来の png が `media/` フラット直下に同居。`cleanup-media`（既定 24h）は fresh ファイルを保持（`cleaned 0`）、mtime backdate→retention=1h で全 61 件削除（両 png 由来とも）。`retention=0`/`0.001` は exit 2（`_parse_positive_int` の下限防御）。全 9 応答で token/env/system prompt/絶対パスの漏洩なし（`local_path` を返信に転記せず）

### Tests

- Python 層は未変更（Live E2E 検証 + ドキュメント反映のみ）ゆえ pytest は 0.10.0 の **369 passed** 据え置き

### Notes — 改善余地2点は意図的に不採用

- **「`--text` で当たりをつけてから `--pages`」は SKILL 不記載**: 薄テキスト巻末では grep が効かず `always --text first` の誤読リスク → Weave 判断に委ねる（L00456 従属度の世界＝目的と前提のみ）
- **`cleanup-media` 即時全削除フラグは追加せず**: 本番不要・誤削除リスク（YAGNI）。下限 1h バリデーションは正しい防御、E2E は mtime backdate 代替で削除パス検証済み

## [0.10.0] - 2026-05-31 — Stage 11.5 PDF 判定撤廃＋オンデマンド抽出（`render-pdf`）

Stage 11 の二経路（テキスト層あり→`rendered_text` ／ 無し→画像化）を撤廃し、**PDF は常に画像化**へ一本化。スタンプ・薄いテキスト層の誤判定（全ページ同一の文書番号印で text 経路に落ち中身が読めない）を構造的に排除する。テキスト全文・cap 超ページは `render-pdf` サブコマンドで **オンデマンド**に分離（画像化＝決定論／抽出＝判断、L00473）。

### Changed — PDF を常に画像化（判定二経路の撤廃）

- `PdfRenderer.render()` を画像専用に単純化（テキスト層判定を削除）。先頭 `image_max_pages`（既定 20）枚を画像化し `rendered_text=""` ／ `page_count`（実総数）／ `derived_image_paths`。スタンプ PDF の誤判定が構造的に起きない
- 受信時（poll/watch）の自動テキスト抽出を廃止。mime-routing は不変（`application/pdf` → `pdf` ルート → `render()`）

### Added — オンデマンド抽出 API + `render-pdf` サブコマンド

- `PdfRenderer.extract_text(local_path)` — 全ページのテキスト層を pdfplumber で `--- page N ---` マーカー付き抽出（スキャン PDF はテキスト層ゼロで空 ok）
- `PdfRenderer.rasterize_pages(local_path, start, end)` — 任意ページ範囲を画像化（cap 超 21 枚目以降の個別要求用、実ページ数でクランプ、命名・保存先は `render()` と一貫）
- `main.py` に `render-pdf --path <pdf> (--text | --pages N-M)` サブコマンド（既存 poll/watch/send-reply 群と同作法、`--text`/`--pages` は排他必須）。`_parse_page_range` で 1-indexed inclusive → 0-indexed `[start, end)`
- 運用：受信時に先頭 20 枚を事前画像化 → Weave が最大 5 枚 Vision で大枠把握 → ①全文（`--text`）／②個別ページ（N≤20 はディスク済み Read、N>20 は `--pages`）／③十分 を判断

### Docs — SSoT 純化（重複解消）

- **SKILL.md に PDF 振る舞いの仕様を集約**（「PDF の扱い」セクション新設＋Subcommands 表に `render-pdf`）。ROUTINE_PROMPT は段階 Vision 記述を新仕様へ置換しコマンド例に絞る（SKILL 参照に寄せ、重複文を削除）＝役割分担（SKILL=仕様 SSoT／ROUTINE=実行手順）の純化
- README / IMPLEMENTATION_PLAN の Stage 11.5 を「Live E2E 申し送り」から「判定撤廃＋オンデマンド実装」へ更新

### Tests

- **Total: 369 passed**（0.9.0 の 358 → +11：常に画像化×3 ／ `extract_text`×4 ／ `rasterize_pages`×4 ／ `render-pdf` コマンド×5、判定二経路テスト撤去分を相殺）
- **Live E2E（実 Telegram で PDF → 最大 5 枚 Vision → `render-pdf` 往復）は [0.10.1] で全5ケース PASS**（2026-05-31、Cloud Routine 実機）

## [0.9.0] - 2026-05-30 — Stage 11 PDF Multipage/Image（Vision 経路、`derived_image_paths` 共通基盤）

Stage 10.4 Live E2E P3 で実証されたスキャン PDF 中身読取の実需に対し、**OCR ではなく Vision 経路**を採用（決裁 2026-05-30）。画像 PDF（スキャン/図面）を `pypdfium2` で全ページ画像化し、Weave が先頭1枚から**段階 Vision** する。画像化（決定論・安い）と Vision（高い・判断）を分離（L00473）。`RenderedMedia.derived_image_paths` は **Stage 9.6-ii 動画 key frame Vision と相乗りする共通基盤**。

### Added — 画像 PDF の全ページ画像化（Vision 経路）

- `RenderedMedia` に `derived_image_paths: list[str]`（派生ページ画像パス）と `page_count: Optional[int]`（PDF 総ページ数）を `default` 付き追加（Stage 7.1 `file_name` 同型の後方互換、既存構築は無変更で green）
- `PdfRenderer` を**二経路化**：テキスト層あり → ページ境界マーカー `--- page N ---` 挿入 + `page_count`（Weave の位置把握）／テキスト層が空（スキャン・図面 PDF）→ `pypdfium2` で全ページ画像化（cap 内）→ `derived_image_paths` + `page_count`、`rendered_text=""`
- `StdoutEventEmitter._build_media_payload` に `derived_image_paths` / `page_count` 出力（v2 維持・フィールド追加のみ、欠落は `[]`/null で後方互換）
- `Config` に `pdf_image_max_pages`（env `TELEGRAM_SECRETARY_PDF_IMAGE_MAX_PAGES`、既定 20）＝超多ページ画像化の安全弁。cmd_poll/cmd_watch の `PdfRenderer` に DI

### Changed — 段階 Vision（ROUTINE_PROMPT Step 5）

- `derived_image_paths` 非空なら Weave が**先頭1枚 Read → `page_count` で総量把握 → 残り要否を判断**（明白なら確認なし、多量/不明なら send-reply で確認）→ 残りはディスク済みを Read（追加 render コストゼロ）。`page_count` を両経路共通メタにし、テキスト（位置把握）と画像（段階 Vision）で判断枠組みを一貫
- ドキュメント同期（README Quickstart PDF / SKILL Daily Workflow + Security / ROUTINE_PROMPT スキーマ・render_status・media 処理）

### Infrastructure

- `pyproject.toml` / `bootstrap.sh` に `pypdfium2>=4.18.0` + `Pillow>=9.1` を**直接宣言**。pdfplumber>=0.11 が両者を transitive に引くことを実機確認したが、`pdf_renderer` が `pypdfium2` を直接 import する以上、再現性のため直接化（コードが直接使う依存は明示する原則）

### Decision Notes

- **OCR ではなく Vision を採用**（建設ドメインの図面・写真比重 + Stage 9.6-ii との共通基盤投資効果）。OCR は Vision でも読めない低解像度スキャン用の劣後 fallback として温存（`MediaRenderer` Port 差し替えで後付け、IMPLEMENTATION_PLAN 末尾「OCR 申し送り」に調査退避）
- **画像化（決定論）と Vision（判断）を分離**：コードは全ページ png 化までで、どれを Vision するかは Weave が `page_count` で段階判断（トークン節約）。テキスト PDF の段階化は YAGNI（トークン経済が画像の 1/N で軽く、`--- page N ---` マーカーで位置把握のみ）
- **派生画像は `media/` フラット直下保存**：既存 `cleanup_media_dir` の retention にそのまま乗る（サブディレクトリだと retention 漏れで機密スキャン画像が残存）
- **新規依存ゼロ→直接宣言に格上げ**：pypdfium2/Pillow は pdfplumber が引くが再現性のため明示（3-Strike #1 pypdfium2 API・#2 Pillow を実機検証で解消）

### Tests

- **Total: 358 passed**（0.8.1 の 339 → +19：Domain +6 / emit +4 / PdfRenderer +4 / config +4 / main characterization +1）。pypdfium2 実 API（`PdfDocument`→`render(scale=2.0)`→`to_pil().save()`）を adapter test で検証
- **Live E2E（実 Telegram でスキャン/図面/多ページ PDF → 段階 Vision 往復）は Stage 11.5 に申し送り**（fresh session 要、他 Stage 同様）

## [0.8.1] - 2026-05-30 — Stage 10.4 PDF Render: Live E2E PASS

[0.8.0] で実装した Stage 10（PDF Render）の **Telegram 実機 Live E2E を Cloud Routine 上で走破**。最重要の「Read tool を使わず PDF 内容に到達できるか」が肯定され、本命の不確実点だった文字化け PDF も pdfplumber でクリーン抽出を確認。

### Verified — Stage 10.4 Live E2E（Cloud Routine 実機、routine `telegram-secretary-stage10-e2e-pdf`、全 P1-P5 PASS）

- **P1 テキスト PDF ✅【最重要】**: 資材物価スライド条項（3頁）が `render_status=ok` + 本文完全抽出（バンド表・不感帯まで構造保持）。**Read tool 不使用で全内容に到達**し要約返信＝Stage 10 の主眼を満たす
- **P2 文字化けしやすい PDF ✅**: `フローリング.pdf`（3.0MB、Stage 9 で pypdf が文字化けした実物）が pdfplumber で **mojibake ゼロのクリーン抽出**。ライブラリ選定（pypdf→pdfplumber/pdfminer.six 系）が文字化け問題そのものを解消し、**三択申し送り（AGPL/OCR/text限定）は不発＝pdfplumber 確定**
- **P3 スキャン PDF ✅**: テキスト層ゼロが `ok` + 空 `rendered_text` に正しく落ち、「テキスト層なし（画像 PDF の可能性）」応答。**大環主が follow-up で OCR を明示要求→スキャン PDF OCR の実需を実証**（IMPLEMENTATION_PLAN Stage 11 backlog に調査結果を記録、RapidOCR ~30MB 第一候補だが日本語は公式事前ビルド ONNX 無し＝v4 自前変換要、YAGNI で着手保留）
- **P4 壊れ PDF ✅**: 非 PDF を .pdf リネームしたファイルが `render_status=failed`（pdfplumber 厳格、rename 攻撃耐性）。stderr は `file_id[:8]` のみで絶対パス秘匿を実機確認
- **P5 retention ✅**: 6+ 件処理後も PDF 中間 temp ファイルゼロ（pdfplumber pure-python・in-memory）、`cleanup-media` exit 0
- **出力漏洩スキャン ✅**: 全返信で送信前スキャン、PDF 埋め込み機密の漏れなし

### Tests

- Python 層は未変更（Live E2E 検証 + ドキュメント格上げのみ）ゆえ pytest は 0.8.0 の **339 passed** 据え置き

## [0.8.0] - 2026-05-30 — Stage 10 PDF Render（passthrough → render 移行、Read tool 非依存化）

### Added — PDF テキスト層抽出（pdfplumber、MediaRenderer Port 第三実装）

- `PdfRenderer`（`scripts/adapters/render/pdf_renderer.py`）— `MediaRenderer` Port 実装。pdfplumber で PDF のテキスト層を抽出し `rendered_text` に載せ `render_status="ok"`。`MarkitdownRenderer`(Stage 7) / `MoonshineTranscriber`(Stage 9) と同型の設計：pdfplumber は render 時 lazy import、内部例外は広く catch → `render_status="failed"`（クラッシュしない）、stderr warning は `file_id[:8]` のみ（絶対パス秘匿）。**テキスト層ゼロ（スキャン PDF 等）は `ok` + 空文字**で「読めるテキスト無し」を Weave に正直に渡す（Moonshine の無音 → ok+空 同型）
- `RenderAuthorizedMedia` に `pdf_renderer` を DI 追加（`pdf_renderer=None` で後方互換 = PDF は `skipped` にフォールバック、transcriber 同型）。`_route_mime` に `pdf` 状態を追加

### Changed — PDF を passthrough から render へ移行（Read tool 非依存化）

- `_route_mime` から `application/pdf` を `_PASSTHROUGH_MIME_EXACT` から除去し `pdf` ルート（テキスト層抽出）へ。従来は「`local_path` を `Read` で開く」passthrough だったが、render で `rendered_text` に本文を載せることで Read tool に依存しない到達経路へ一般化（L00473 分業＝決定論的 render は skill、判断は Weave）
- `cmd_poll` / `cmd_watch` に `PdfRenderer` を lazy import 注入（`cmd_watch` は ImportError 時 `pdf_renderer=None` で skipped フォールバック、transcriber 同型）
- ドキュメント同期（README Quickstart / SKILL Daily Workflow + Security / ROUTINE_PROMPT Step 5 render_status）：PDF を passthrough → render（ok + rendered_text）に更新

### Infrastructure

- `pyproject.toml` に `pdfplumber>=0.11`（本番依存、MIT、pure-python）と dev extras に `reportlab>=4.0`（PDF fixture 動的生成用、docx を python-docx で生成するのと同型）を追加
- `bootstrap.sh` Heavy モードに pdfplumber install を追加

### Decision Notes

- **pdfplumber(MIT) を採用、pymupdf(AGPL) は不採用**：日本語テキスト層抽出の基本品質は両者同一（smoke 比較で確認）。配布ライセンス安全性で MIT の pdfplumber を選択。AGPL の pymupdf は同等品質だが配布制約のため不採用。`MediaRenderer` Port 構造は不変で内部ライブラリのみ差し替え可能（Reversibility）
- スキャン PDF（テキスト層なし）は **(i) 空 ok + Weave 側で警告**方針（OCR は導入しない、YAGNI）。文字化け PDF（ToUnicode 不備）への強さは Live E2E（次フェーズ）で確認

### Tests

- **Total: 339 passed**（0.7.4 の 332 → +5 PdfRenderer adapter／routing は `test_pdf_is_passthrough` を `test_pdf_calls_pdf_renderer` + skip フォールバック + download skip 継承の 3 件に置換 = 差し引き +7、計 +5 net）
- **Live E2E（実 Telegram で PDF 送信 → 要約往復・文字化け PDF・スキャン PDF）は次フェーズ（Stage 10.4）** に申し送り

## [0.7.5] - 2026-05-30 — Stage 9 Native Voice/Audio/Video Inbox: Live E2E PASS + ドキュメント整合

[0.4.0] で実装した Stage 9（音声 transcript）の **Telegram 実機 Live E2E を Cloud Routine(Linux) で走破**。最重要の「Linux で moonshine-voice + av の wheel が入るか」が肯定され、本番デプロイの不確実性が解消。検証で判明した実挙動にドキュメントを整合した。（注: 番号は [0.8.0] Stage 10 より前に検証した順を保つため [0.7.5]。実コミット順は Stage 10 実装の後だが、検証日時 2026-05-30 で時系列整合）

### Verified — Stage 9 Live E2E（Cloud Routine Linux 実機、BlueberrySprite 環境、routine `telegram-secretary-stage9-e2e`）

- **Linux wheel ✅**: `moonshine-voice 0.0.59` + `av 17.0.1`（PyAV、codecs 560）が bootstrap で install 成功・import 機能確認。**システム ffmpeg 不在でも PyAV 同梱 ffmpeg でデコード可**。→ kotoba-whisper への Port 差し替えは当面不要
- **ケース A〜D ✅**: voice(.oga/OGG-Opus)・audio(.m4a/.mp3)・video(.mp4/.mov 音声トラック) が `render_status="ok"` + 日本語 transcript + `kind` 正常 emit。無音は `ok`+空 transcript
- **transcript 精度**: 長文朗読（新美南吉『うた時計』）をほぼ正確に文字起こし。末尾/語頭の軽い減衰、ゆっくり抑揚部の分かち書き化を観測（実用上許容）
- **Moonshine 初回 DL**: ≈134MB、~80–94MB/s で計約3–4秒。2件目以降はキャッシュで再 DL なし
- **retention ✅**: 6回以上の音声デコード後も中間 wav は state_dir・/tmp とも 0 件（PyAV メモリ内デコード＝残存リスク構造的にゼロ）。`cleanup-media` も exit 0
- **出力漏洩スキャン ✅**: 全返信で送信前スキャン、transcript 経由の機密漏れなし

### Fixed — ドキュメント整合（実挙動「音声の壊れ＝ok+空」への統一）

- `broken.mp3`（テキストを .mp3 リネーム）が `failed` でなく `ok`+空に落ちる実挙動を確認（`FfmpegAudioPreprocessor` が `av` の `InvalidDataError` を内部 catch して空リスト → `MoonshineTranscriber` が ok+空）。**音声は無音もこの種の壊れも `ok`+空に収束**（クラッシュせず安全側）。PDF(pdfplumber) は逆に壊れを failed 化、markitdown(docx) は寛容で ok＝**媒体で挙動が異なる**ことを render_status の説明に明記
- ドキュメント揺れ（ROUTINE_PROMPT「壊れ→failed」vs「デコード不可→ok+空」）を実挙動に統一。応答指針を「無音か、音声として読めないファイルの可能性」と両義化（ROUTINE_PROMPT / SKILL / README）。SKILL Security に「音声中間ファイルの不在」を追記
- `broken→failed` の実装変更は見送り（YAGNI：安全側でクラッシュせず両義応答でカバー可。大環主決裁 2026-05-30）

### 既知課題（別途対応）

- **passthrough PDF が Cloud Routine で描画不可**（poppler 未導入、Stage 6 系）→ **Stage 10 PDF Render（[0.8.0]）で解消済み**（pdfplumber でテキスト層抽出、Read tool 非依存化）
- `render_status="failed"`（真の transcribe 推論例外）は Live で踏めず（av の `InvalidDataError` は ok+空 経路に落ちるため）。ユニットテスト（`test_moonshine_transcriber.py`）でカバー済み

### Tests

- Python 層は未変更（ドキュメント整合のみ）ゆえ pytest は 0.7.4 の **332 passed** 据え置き

## [0.7.4] - 2026-05-29 — E2E Phase 2 PASS + FINDING 2 格上げ修正（窓畳みオーバーラン → SIGTERM リスク）

### Verified — E2E Phase 2（Cloud Routine 実機、本番 580s 窓・2h・SIGTERM 非発火）

- 本番設定（`deadline=now+7200s` / `window<=580s` / `bash timeout 600000ms` / Medium）で **約2h00m22s 生存**、watch 全15窓 exit 0、**SIGTERM(143) 発火ゼロ**、deadline 正常終了、lease conflict ゼロ
- early-exit 即応5通（挨拶/能力質問/写真メタ応答）併観測（Phase 1 を本番窓で再確認）
- 待機は getUpdates サーバ側ブロックでターン内トークン最小（約30ターン/2h）

### Fixed — FINDING 2: 最終窓オーバーランの深刻度格上げと根本修正

- [0.7.3] では deadline 最終窓のオーバーラン（≈`--timeout`）を「2h 枠に無視可、ROUTINE_PROMPT 注記のみ」と判断していた
- Phase 2 実測で **window 満了窓が 603〜604s** に達し、`max_duration(580) + timeout(30) = 610 > bash_timeout(600)`。exit 0 だったのは**ハーネスの自動 background 化**が 600s の foreground 上限を外したため＝**偽の安全**。厳密 foreground 経路なら 600s で SIGTERM(143) 発火する構成
- **修正**: `cmd_watch` が**最終サイクルの long-poll を残り窓に丸める**（`remaining < timeout` なら `timeout=remaining`）。値(580/30)非依存で不変条件 **`max_duration + timeout < bash_timeout`** を保証
- 切り分け: `BASH_MAX_TIMEOUT_MS` は実効（600000 確認済み）。純粋に窓畳みバッファ(600−580=20s) < オーバーラン上限(`--timeout`=30s)

### Tests

- **Total: 332 passed**（0.7.3 の 331 → +1: 残り窓 < `--timeout` の最終サイクルで long-poll が残り窓に丸められる spy テスト）

## [0.7.3] - 2026-05-29 — FINDING C/D: E2E Phase 1 PASS + 単一永続シェル前提の解消

E2E Phase 1（early-exit 即応ループ）を実機で走破。検証中に、ROUTINE_PROMPT が依拠していた「`source` で env を親シェルに引き継ぐ／単一の永続シェル」前提が Claude Code / Cloud Routine の Bash tool では成立しない（**env は call 間で揮発、cwd のみ persist**）ことが判明。env snapshot の re-source と STATE_DIR の絶対パス固定で根治した。

### Verified — E2E Phase 1（early-exit 即応ループ）

- 「メッセージ受信 → watch early-exit → 返信 → watch 再起動」の即応ループが実機で 3 サイクル連続成立。受信 5 件（text 4 + photo 1）に対し返信 5 件すべて成功、未返信ゼロ。窓満了 → deadline → lease release も正常
- photo は Medium モード（download 無効）のためメタ情報応答、`injection_flags` は全件空

### Fixed — FINDING C: env が call 間で揮発（運用律 B 案の前提崩れ）

- **症状**: `source bootstrap.sh` で export した `TELEGRAM_SECRETARY_SESSION_ID` / `TS_SESSION_DEADLINE_EPOCH` 等が後続 Bash call に残らない。無改修だと owner 不一致 → lease exit 4、または deadline 未設定 → 即停止。Phase 1 が通ったのは即席の env-dump workaround ゆえ
- **修正**: `bootstrap.sh` が派生 env（session_id / deadline / repo_root / 絶対 state_dir / TS_* 群）を `TELEGRAM_SECRETARY_ENV_FILE`（既定 `/tmp/telegram-secretary.env.sh`）へ snapshot。`ROUTINE_PROMPT.md` の Step 4-7 各 call は冒頭で `source <snapshot> && cd "$TELEGRAM_SECRETARY_REPO_ROOT"` を実行。`TELEGRAM_BOT_TOKEN` / `AUTHORIZED_CHATS` は Environment 注入で各 call に入る & 秘匿のため snapshot に書かない（出力漏洩スキャン規律）

### Fixed — FINDING D: 相対 STATE_DIR が subshell cd で幽霊パス化

- **症状**: 各 Step は `(cd Expertises/TelegramSecretary && ...)` で subshell cd するため、相対 `TELEGRAM_SECRETARY_STATE_DIR` がその cwd 基準で解決され、`Expertises/TelegramSecretary/.private/.../state/` という実体のないパスに落ちる（`.gitignore` の `Expertises/*/state/` にも当たらず untracked 化）。E2E Phase 1 の cleanup で顕在化
- **修正**: `bootstrap.sh` が STATE_DIR を bootstrap 実行時 cwd（=リポルート）基準で `os.path.abspath` 絶対化して snapshot に固定。既定 `./state` は従来どおり `Expertises/TelegramSecretary/state/` に解決され `.gitignore` に引き続きマッチ（**既定運用は不変**）

### Note — deadline 最終窓のオーバーラン（実害なし、FINDING 2）

- `--max-duration` の粒度は実行中の long-poll サイクル（≈`--timeout`）まで。deadline 直前の最終窓は ≤`--timeout`（既定 30s）超過し得るが、2h 枠に対し無視可。`ROUTINE_PROMPT.md` に注記のみ追加

### Tests

- shell 構文（`bash -n`）と path 解決ロジック（repo_root 導出 ・ STATE_DIR 絶対化 ・ `printf %q`）を決定論的に再現検証。env file パスの bootstrap↔ROUTINE 一致（9 occurrences）と source ガード網羅（Step 4-7 全 call）を確認。Python 層は未変更ゆえ pytest は 0.7.2 の **331 passed** 据え置き

## [0.7.2] - 2026-05-29 — FINDING B: media 依存の Tier 別 graceful（moonshine opt-out）

プラグイン配布を見据え、media stack を「種別で必要な依存が違う」前提に再設計。デフォルトは全 media 対応（多くの利用者は moonshine Community License で無料）、大規模/ライセンス回避は音声バンドルを外せる。FINDING A の lazy 化を踏まえた延長修正。

### Changed — moonshine(transcriber) を optional 構築

- `cmd_watch::_ensure_media_stack`: moonshine を **try-import**。未導入なら `transcriber=None` で `RenderAuthorizedMedia` を構築（render usecase は transcriber Optional ＝音声/動画を `skipped` にフォールバック）。markitdown(render) は必須デフォルトのまま
- **bootstrap: Tier 別 install**。Medium(`MEDIA_ENABLE_DOWNLOAD=false`)=httpx のみ / Heavy(既定)=+markitdown / voice(moonshine+av)=`TELEGRAM_SECRETARY_BUNDLE_VOICE=false` で除外可。Phase 0 等の keep-alive 検証は httpx だけで軽い（3分岐 source 検証済み）
- moonshine Community License は年商$1M 未満のみ商用無料・~134MB model ゆえ、大規模（めぐる組等）は `BUNDLE_VOICE=false` で外す運用

### Tests

- **Total: 331 passed**（0.7.1 の 330 → +1）。「moonshine 未導入でも Heavy watch が落ちず transcriber 無しで起動」テストを追加

## [0.7.1] - 2026-05-29 — E2E Phase 0 PASS + FINDING A 修正（media stack 遅延構築）

### Verified — E2E Phase 0（Cloud Routine 実機、Stage 11）

- **コンテナ維持 PASS**: foreground 長 call（`watch --max-duration`）で Cloud Routine のコンテナが約3分 warm 維持され、deadline で正常終了・lease release まで走破。**D（session 内 keep-alive）の根幹が実機で成立**し、fallback（session 間 cron 反復）は不要と確定
- routine `telegram-secretary-e2e-phase0`（BlueberrySprite 環境）で、Medium モードに隔離して keep-alive 単体を観測（watch 3 サイクル × 60/60/26s、いずれも foreground long-poll が窓満了で exit 0、コンテナ非ドロップ）

### Fixed — FINDING A: Heavy モード watch の起動時クラッシュ

- **症状**: fresh container で既定 Heavy モードの `watch` が `ModuleNotFoundError: No module named 'markitdown'` で exit 1。`bootstrap.sh` は httpx しか導入しないが、`cmd_watch` が起動時に renderer/transcriber を **eager 構築**して markitdown/moonshine/av を import していた（E2E Phase 0 で顕在化）
- **修正**: media stack（downloader/renderer/transcriber）を **遅延構築** `_ensure_media_stack()` に。実際に media を受けたサイクルで初回構築しキャッシュ。media を受けない常駐は httpx だけで起動する（Medium モードも自然に同経路）。起動が常に軽く、moonshine の ~134MB model DL も media 受信まで発生しない

### Tests

- **Total: 330 passed**（0.7.0 の 329 → +1）。「Heavy モード + media 無しサイクルで renderer を構築しない（遅延構築）」テストを追加

## [0.7.0] - 2026-05-29 — Stage 10: /goal deadline 駆動ロングポーリング（keep-alive + early-exit 即応）

Cloud Routine のセッションを枠（既定 2h）の間 warm に保ちつつ、Telegram メッセージに即応するための keep-alive 設計。**設計 A（background watch + Monitor 維持 × /goal warm）は claude-code-guide 調査で不成立**（`/goal` はターン間機構で keep-alive にならない／monitor タスクは resume 復元されない／Cloud Routine はタスク完了型で常駐想定外）。代わりに **D（session 内 keep-alive + early-exit）** を採用。

### Added — watch の wall-clock / message 駆動 exit

- **Domain** (`domain/watch_window.py`): `WatchWindow(started_at, max_duration_seconds)` 値オブジェクト（frozen、`is_expired` / `remaining_seconds`、`<=0`=無限窓、`SessionLease.is_stale` と同型の境界作法）
- **CLI** (`main.py::cmd_watch` + `build_parser`):
  - `--max-duration SEC`（既定 0=無限）: 窓満了で自然終了（exit 0）。bash timeout 発火（SIGTERM）より先にプロセスを自然終了させる窓畳み
  - `--exit-on-message`（D の核）: 認可済みメッセージを emit したサイクルで exit 0。「メッセージ受信→即返信→watch 再起動」の即応ループを実現（遅延 ≤ long-poll timeout）。無メッセージのサイクルでは発火しない

### Added — deadline 駆動の運用統合

- **bootstrap.sh**: deadline 方式の運用変数を export。**「枠（`TS_SESSION_DEADLINE_EPOCH`）」と「ポーリング回数（メッセージ頻度で可変）」を分離**。`TS_SESSION_DURATION_SEC`(7200) / `TS_SESSION_DEADLINE_EPOCH`(now+duration、停止主軸) / `TS_POLL_SET_SEC`(580、無メッセージ時の窓上限) / `TS_POLL_BASH_TIMEOUT_MS`(600000) / `TS_MAX_TURNS`(300、暴走保険)。旧 `TS_POLL_SET_COUNT`（停止条件）は廃止
- **settings** (`.private/.claude/settings.json`): `BASH_MAX_TIMEOUT_MS=600000`（上限引き上げ）。`BASH_DEFAULT_TIMEOUT_MS` は据え置き＝ポーリング以外は 2分のまま
- **ROUTINE_PROMPT.md**: Step 5 を `/goal` deadline 駆動に刷新（各ターン foreground `watch --exit-on-message --max-duration <残り窓>`、timeout 限定適用の運用規律、deadline→lease release→次 cron）

### Design — 路線判断と要実機検証

- 設計 A 不成立 → **D 採用**（即応性◎を保つため session 内 keep-alive）
- **⚠️ 要実機 E2E（別セッション）**: 「foreground 長 call が Cloud Routine のコンテナを warm に保つか」は公式未保証。NG 時の fallback は session 間ループ（短セッションを cron で頻繁反復、既存 lease/offset 冪等性に乗せる）
- 設計記録は `GOAL_KEEPALIVE_PLAN.md`（教材として保持）

### Tests

- **Total: 329 passed**（0.6.0 の 318 → `WatchWindow` Domain / `--max-duration` / `--exit-on-message` で +11）
- `--exit-on-message`: メッセージ受信サイクルで break（getUpdates 1回で抜ける）/ 無メッセージでは誤発火せず窓・回数まで継続

## [0.6.0] - 2026-05-28 — 管理表（INDIVIDUALS / TASKS / KNOWLEDGE）+ ドキュメント体系整備

### Added — 管理表アーキテクチャ（Clean Arch 4層）

秘書としての3管理表を新規構築。**SSoT = Private JSON、配布物はテンプレートのみ**（個人データを焼き込まない＝配布可能性の担保）。

- **Domain** (`domain/registry.py`): `Individual` / `Identity` / `Task` / `Knowledge` 値オブジェクト（frozen、from_dict/to_dict、enum バリデーション）+ `upsert` / `find_by` 純関数
- **UseCase** (`usecases/manage_registry.py`): `RegistryService`（list/get/add_or_update/remove、Store Port 越し）+ `RegistryStore` Port
- **Interface** (`adapters/registry/json_registry_store.py`): `JsonRegistryStore`（`{"version","records"}` 形式、破損フォールバック、ensure_ascii=False）
- **Infrastructure** (`infrastructure/archive_rotate.py`): `partition_for_archive`（TASKS/INDIVIDUALS 日付 Archive）+ `split_by_category`（KNOWLEDGE カテゴリ分割＝蓄積優先）
- **CLI** (`infrastructure/registry_cli.py` + `main.py`): `individuals|tasks|knowledge {list|get|add|remove}` subcommand。値オブジェクトで入力検証（不正は exit 2）。全操作は将来 `/secretary` がラップ
- **Config**: `individuals_path` / `tasks_path` / `knowledge_path` property（state_dir からの導出、SSoT）
- **templates/**: `INDIVIDUALS|TASKS|KNOWLEDGE.template.json`（`_record_schema` 付き雛型）+ `Identities/SecretaryRole.template.md`（人格雛型）

### Added — ドキュメント体系

- `DESIGN.md` 拡張（設計正典: Architecture + Data Architecture + Scope）/ `STRUCTURE.md` 新規（構造地図 + 早見表）/ `SECURITY.md` 新規（網羅版、配布前チェックリスト、SSoT を意図的に例外化）/ `DOCUMENTATION_PLAN.md`（整備計画、勉強会資料として保持）

### Data Architecture（確定事項）

- **SSoT = Private JSON**（Redis は将来 LineBridge のキャッシュ、一方向 JSON→Redis）
- **Identities レイヤー**: 人格定義（`SecretaryRole.md`）は Private、無いとエージェントが人格的に振る舞えない
- **CRUD 操作主体 = エージェント**、決定論 I/O は CLI、入口は `/secretary`
- **肥大化対策**: TASKS/INDIVIDUALS=日付 Archive、KNOWLEDGE=カテゴリ分割

### Tests

- **Total: 318 passed**（v0.5.1 の 279 → +39）
- Domain: +16（値オブジェクト 11 / upsert・find 5）
- Adapter: +5（JsonRegistryStore）
- UseCase: +6（RegistryService）
- Infrastructure: +12（archive_rotate 6 / registry_cli 6）
- CLI 配線は実機 smoke test（list→add→list→不正 add で exit 2）で end-to-end 確認

## [0.5.1] - 2026-05-27 — Stage 8 Live E2E follow-up: emit message_id + network error redact

### Fixed

- **emit に `message_id` 欠落（reply threading の入力源が Weave に届かない）**: `ROUTINE_PROMPT.md` Step 5 は Weave に「元発言への返信は `--reply-to <message_id>`」と指示していたが、Weave が読む emit JSON Lines に `message_id` が無く、threading に渡す値を取得できなかった。送信パイプライン（CLI `--reply-to` → `OutboundMessage.reply_to_message_id` → gateway payload）は完備していたのに**入力源だけが欠けていた設計不整合**。`TelegramUpdate.message_id` field + `from_api` 抽出 + emit payload 出力を追加（完全後方互換、欠落=null）。Stage 8 Live E2E（ケース D: reply threading、emit からではなく生 getUpdates から message_id を別途取得して通した）で顕在化
- **network error 経路の token 込み URL 漏洩**: `TelegramApiGateway._request_with_retry` の `httpx.RequestError` 経路が `raise ... from exc` で例外メッセージに `{exc}` を載せ、exc が `/bot<TOKEN>/...` URL を含むと token が漏れた（getUpdates / sendMessage / sendPhoto / sendDocument / getFile / sendChatAction の**全共通経路**）。`from None` で chain を切り、メッセージからも exc を除去（受信側 `media_downloader` の network error 経路と同型の redact に統一）。Stage 8 Live E2E の気づき（送信失敗例外の redact 未検証）への対応で、red テストが実際に `botTEST_TOKEN/sendMessage` の混入を実証

### Changed

- `ROUTINE_PROMPT.md` Step 5 の emit スキーマ例に `message_id` を追加、`--reply-to` の入力源であることを明記（プロンプトとスキーマの矛盾を解消）

### Tests

- **Total: 279 tests passing**（v0.5.0 の 273 → +6）
- Domain: +3（from_api の message_id 抽出 / 欠落時 None / edited_message でも取得）
- Adapters: +3（emit の message_id 出力 / 欠落時 null / network error の token redact）

### Rationale

- Stage 8 Live E2E（大環主目視確認）で「emit に message_id が無く本番 Cloud Routine フローで SecretaryRole が threading できない」「送信失敗例外の redact 未発火＝未検証」の 2 点が報告された。コード突き合わせで ①=プロンプトが存在しない値の使用を命じる設計不整合（実在）/ ②=network error 経路の穴（red テストで token 混入を実証）と確定
- **変更しなかったもの**（加算バイアス回避）: typing 不可視（best-effort 実装は正しい、`AuthFailureError` も握り潰す）/ PIL・python-docx 不在（本体の docx 解釈は markitdown 経由で成立、不足は送信テスト用の生成物作りのみ）/ caption 上限・複数 --file（実装済み・E2E 検証待ち）

## [0.5.0] - 2026-05-27 — Stage 8 Outbound Media: 生成物の送り返し (Doc Complete / E2E Pending)

### Added — write 系（受信 Stage 6/7/9 の対）

Stage 6/7/9 が受信メディアの中身理解（公式 plugin 超越）だったのに対し、本 Stage は Weave 起草の生成物（画像/レポート/docx 等）を Telegram に送り返す outbound media。`send-reply` が text-only から添付対応へ。送信ファイルの**生成**は親プロセス Weave、コードは**決定論的な送信と送信前チェックのみ**（L00473 分業）。

**Domain (8.1)**:
- `OutboundAttachment`（`path` のみ保持＝bytes を持たず純粋性維持、`is_photo()` で拡張子 routing）、`validate_attachments(attachments, max_bytes)` 純関数（存在/サイズ検証）
- `OutboundMessage.attachments` field 追加（`default_factory=list`、text-only と後方互換）
- `AttachmentNotFound` / `AttachmentTooLarge` 例外（受信側 `MediaSizeLimitExceeded` の送信側カウンターパート、こちらは送信中止＝ブロック）

**UseCase (8.2)**:
- `SendReply.execute` に `max_bytes` 引数（デフォルト 50MB）、`validate_attachments` を **lease 再検証の後・送信の前**に配置（不正なら送信前 raise → offset/lease 据え置きで冪等・再送可能）
- `MessageSink` Port 契約は不変（`OutboundMessage` に attachments が乗るだけ＝fake sink 無変更）

**Interface (8.3)**:
- `TelegramApiGateway.send` を添付有無で分岐：なし→ sendMessage（従来）、あり→ sendPhoto/sendDocument（multipart、file bytes 読み切りで retry 再利用）
- 本文は添付1件かつ caption 上限（1024）内なら caption に、それ以外は text を別 sendMessage で先送り。reply_to は最初の送信のみ（二重 reply 回避）
- `send_chat_action`（typing、best-effort＝失敗は本送信を妨げない）
- token redact: 送信失敗例外は method/chat_id/file 名のみで URL/token を載せない（テストで検証）

**Infrastructure (8.4)**:
- `cmd_send_reply` に `--file`（複数可）/ `--reply-to`（threading）/ 送信前 typing 配線、`Attachment*` 例外を exit 2 にマップ
- `TELEGRAM_SECRETARY_OUTBOUND_MAX_SIZE_BYTES` env（既定 50MB）

### 対話 UX 装飾の取捨（大環主決裁 2026-05-27）

「公式 plugin が持つから移植」前提を外し、「秘書の価値は read 系（Stage 6/7/9 で公式超越済み）、write は file 送信で双方向性が完成」を急所として選択的に実装：

- **採用**: outbound file 送信（中核）/ reply threading（既存 Domain の `reply_to_message_id` 完成、ほぼ無コスト）/ typing インジケータ（stateless 軽量）
- **見送り**: markdownv2（YAGNI、escape 事故リスク。後付け容易）/ react（本文 UTF-8 絵文字で代替可、さらに 1:1 DM は bot が管理者になれず inbound reaction も構造的に受信不可と確認）/ edit_message（stateless 設計に message_id 状態を持ち込むため、必要時に独立 Stage）

### Changed

- `OutboundMessage` が `attachments` を内包（Port 契約・fake は不変）
- `send-reply` Subcommand に `--file` / `--reply-to` 追加（後方互換、添付なしは従来動作）

### Tests

- **Total: 273 tests passing**（v0.4.0 の 246 → +27）
- Domain: +11（OutboundAttachment.is_photo / validate_attachments / OutboundMessage 後方互換）
- UseCase: +3（SendReply 添付素通し / サイズ超過送信前 raise / lease 検証が添付検証に先行）
- Interface: +7（sendPhoto / sendDocument / 長文 text 別送 / sendChatAction best-effort / token redact）
- Infrastructure: +6（config outbound env 3 / CLI --file→sendPhoto・missing→exit2・--reply-to 3）

### Live E2E Pending (Fresh Session 必須)

- E2E: 画像生成 → `--file figure.png` → Telegram で画像 + caption 受信
- E2E: docx/PDF → `--file report.docx` → sendDocument 受信
- E2E: >50MB → 送信前 exit 2、Telegram に何も送られない
- E2E: `--reply-to` で元発言への返信スレッド表示 / 送信前 typing インジケータ

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
