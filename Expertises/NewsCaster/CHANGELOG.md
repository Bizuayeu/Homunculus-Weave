# Changelog

## [0.2.2] - 2026-05-31

### Changed
- `ROUTINE_PROMPT.md` Step 4/5 にハルシネーション防止の手続きガードを追加（コード非改変、cloud routine の手順のみ）
  - Step 4: dry-run 出力（`/tmp/newscaster_dryrun.txt`）を必ず Read してから Step 5 へ進む明示 + Step 4（dry-run）と Step 5（WebFetch）の同一バッチ並列実行を禁止（Step 5 の WebFetch URL は dry-run 出力に依存）
  - Step 4: placeholder が 1 つも無ければ Step 5 を丸ごとスキップ（書き換え対象ゼロ時に本文を生成しない）
  - Step 5: WebFetch する URL は placeholder 直前の `- リンク:` 行から逐語コピー、推測で組み立てない
  - Step 5: `- リンク:` が読めない／WebFetch 失敗の item は description 範囲だけでベタ化し、本文が取れないことを理由に内容を創作しない

### Why
- 過去の cloud routine 実行で、dry-run 出力を Read する前に WebFetch URL を推測で組み立てて並列実行し、実在しない URL への 404 量産と本文捏造が発生
- 根本原因は「データ依存（Step 5 の入力 = Step 4 の出力）を越えて生成を並列化した手続き順序違反」。精神論でなく手続きで縛る
- コード層の防波堤（`send-rendered` の placeholder 残存検出 = exit 1）は、捏造で placeholder を埋めて送るケースを弾けない。手続き層での予防が必要

### Verification
- `ROUTINE_PROMPT.md`（手続きドキュメント）のみの変更、コード非改変のため既存 137 tests に影響なし（テスト未実行）
- 反映は翌 0:10 JST の cloud routine fresh clone 時（`prompt: ROUTINE_PROMPT.md を参照` 設計、RemoteTrigger update 不要）

## [0.2.1] - 2026-05-19

### Fixed
- Wireless Wire 型の複数 `<category>` 要素から先頭1件しか取得できず category が欠落していた問題
  - 2026-05-18 の実運用検証で、Wireless Wire News の前日記事に対し 3 カテゴリ中 1 つ（"科学技術芸術と社会"）しか配信されない欠落を観測

### Changed
- `RssXmlGateway._parse` の category 取得を `find("category")` → `findall("category")` ベースに変更
- 複数の `<category>` 要素のテキストを `,` で結合し、既存 `NewsItem.from_rss_dict` の CSV split ロジックへ渡す（Adapter 層完結、Domain 不変）
- 空タグ `<category></category>` は Adapter 側で弾く二段構え（Domain 側の strip も維持）

### Verification
- 137 tests green（既存 134 + 新規 3: Wireless Wire 型複数要素 / ナルエビ型後方互換 / 空要素混在）
- 新規 fixture: `tests/adapters/fixtures/sample_multi_category.xml`

## [0.2.0] - 2026-05-19

### Added
- マルチフィード対応：`NEWSCASTER_FEEDS` JSON 配列で複数 RSS フィードを設定可能
- フィード別整形ポリシー `FeedPolicy`（`passthrough` / `weave_compact`）
- `weave_compact` ポリシー：装飾的エッセイ系メディアを cloud routine 内の親プロセス Weave がベタ化（L00473 原則の実装手段二系統化）
- 新サブコマンド `send-rendered`：Weave がプレースホルダを書き換えた最終 subject/body を直接送信
- `--body-file <path>` オプション：長文 body をファイル経由で渡す（PowerShell ARG_MAX 回避）
- `domain/feed_policy.py`, `domain/feed_source.py`, `usecases/send_rendered.py` 新設
- Failure Mode：`PLACEHOLDER_REMAINS`（書き換え漏れの `{{WEAVE_COMPACT:<guid>}}` 検出時は送信拒否）

### Changed
- `NewsItem` に `source_name: str` 必須フィールド追加
- `FetchAndFilterUseCase.__init__` のシグネチャ：`rss_gateway` 単数 → `gateways: Sequence[tuple[FeedSource, RssGatewayPort]]`
- 個別フィード失敗は stderr に warn 後 skip。全フィード失敗時のみ最初の `RssFetchError` を送出
- `FormatDigestUseCase.execute` に `feed_sources` 引数を追加。出典別セクション分割（`## {feed_name}`）と policy 別本文選択
- subject 形式：`[NewsCaster] YYYY-MM-DD のダイジェスト (N件 / Mソース)`
- `DigestConfig` に `feeds: tuple[FeedSource, ...]` と `feeds_parse_error: str | None` を追加
- `ROUTINE_PROMPT.md`：dry-run → Weave による compact 書き換え → send-rendered の新フロー

### Migration
- 既存 `NEWSCASTER_RSS_URL` 単数指定は **後方互換のまま動作**（`FeedPolicy.PASSTHROUGH` の単一フィードに自動変換）
- 両方未設定時もデフォルトのナルエビフィードにフォールバック
- 単一 PASSTHROUGH フィード構成なら `run` サブコマンド一発実行は Stage 4 互換

### Verification
- 134 tests green（既存 91 + 新規 43）
- 新規テスト内訳: FeedPolicy 5 / FeedSource 7 / NewsItem.source_name 5 / FetchAndFilter multi 4 / FormatDigest source-sections 4 / Config feeds 9 / SendRendered 4 / CLI send-rendered 5

## [0.1.2] - 2026-05-15

### Fixed
- `RssXmlGateway` が CDN エッジキャッシュ起因で古いフィードをつかみ、前日エントリ 0 件と誤判定してメール空振りする問題

### Changed
- `RssXmlGateway._fetch_xml` に毎リクエスト固有の cache-buster クエリ `?_=<epoch_seconds>` を付与
- HTTP リクエストヘッダに `Cache-Control: no-cache, no-store, max-age=0` と `Pragma: no-cache` を追加
- `RssXmlGateway.__init__` に `time_provider: Callable[[], float] | None = None` 任意引数を追加（テスト時に固定時刻を注入可能、本番では既定の `time.time` が使われる）
- `RssFetchError.final_url` は cache-buster 込みの実 URL を保持（trace 容易性）。メッセージ本文は元 URL を維持（運用ログの可読性）

### Why
- 2026-05-15 朝の cloud routine 実運用で「前日エントリ 0 件」によるメール空振りが発生
- `news.nullevi.app` は Vercel/Cloudflare 系の static export と推測され、CDN エッジが直近の更新を反映しない時間帯がある
- 業務要件は「毎日 0:10 JST に最新フィードを必ず取得」なので、キャッシュ回避は冪等性と同等に必須

### Verification
- 91 tests green（既存 83 + 新規 8: cache-buster 3 / no-cache headers 3 / 統合 + 元 URL 保存 2）
- 本番 CDN 貫通は mock テストでは検証不可。**翌朝 0:10 JST cloud routine 実行ログで fetch 件数 > 0** を確認する運用律

## [0.1.1] - 2026-05-12

### Changed
- `bootstrap.sh` を BlueberrySprite パターンに準拠して全面改修
  - `pyproject.toml` を SSoT として依存抽出（重複定義の排除）
  - `--ignore-installed cffi cryptography` リトライ機構（debian 同梱版 RECORD 欠落対策）
  - `import cryptography.exceptions` defensive sanity check
  - `HTTPLIB2_CA_CERTS` を `/etc/ssl/certs/ca-certificates.crt` 等から自動 export（httplib2 が `REQUESTS_CA_BUNDLE` / `SSL_CERT_FILE` を読まない問題への対策）
  - import verification（`googleapiclient` / `google.auth` / `google_auth_oauthlib` / `cryptography`）
- `source` / `bash` 両方の起動方法に対応（`HTTPLIB2_CA_CERTS` を親シェルに残したい場合は `source`）

### Why
- L00480 の初回 cloud routine 実行で `google-api-python-client` 系と `cryptography`/`cffi` が未導入のため起動失敗
- 手動で `pip install --ignore-installed cffi cryptography` で復旧したが、次回以降も再発するため bootstrap 側で恒久対策
- BBS で完全な処方が既に実装済みのため、フォント・SVG 等 BBS 固有層を除いて移植

## [0.1.0] - 2026-05-12

### Added
- 初回リリース。Clean Architecture × TDD（Stage 1〜4）で実装
- `news.nullevi.app/rss` から JST 前日エントリを抽出し Gmail で配信
- 4 subcommands: `run` / `dry-run` / `test` / `validate-config`
- 冪等性（`JsonStateStore`、同日二重送信防止）
- 0件沈黙の許容（NO_ITEMS）
- BlueberrySprite の token.json 共有可（同一送信元 Gmail を想定）
- 82 tests green（Domain / UseCase / Adapter / CLI 全層）

### Design Decisions
- LLM 再要約しない（「ベタにまとめる」、L00473）
- 標準 `urllib` + `xml.etree` でRSS取得（新規依存最小化）
- Chrome 系 User-Agent 明示（Bot UA は 403）
- 送信元 Gmail は BlueberrySprite と共用想定（env var `NEWSCASTER_SENDER_EMAIL`）

### References
- 実装計画: `IMPLEMENTATION_PLAN.md`
- 既存パターン: `homunculus/Weave/Expertises/BlueberrySprite/`
