# Implementation Plan: /goal deadline 駆動ロングポーリング + watch の early-exit / wall-clock 停止

> 本計画は `Expertises/ConsiderateCoder/rules/DEV.md` および `/plan-sdd` の方針で生成。**教材として完了後も保持する**（通常の IMPLEMENTATION_PLAN は全 Stage 完了後に削除するが、本計画は /goal × Cloud Routine × bash timeout 制御の設計記録として残す——大環主指示 2026-05-28）。
> 既存 `IMPLEMENTATION_PLAN.md`（Stage 1-9, v0.6.0, 318 tests green）の上に乗る**増分計画**（Stage 10 相当、独立ファイル）。

## 設計転換（2026-05-29）— A 調査の結果 B(12セット固定) → D(deadline × early-exit)

当初計画（下記 Overview 以降）は **B 案: foreground watch を固定 12 セット**で枠を埋める設計だった。実装着手前に大環主の指示で **設計 A（background watch + Monitor 維持 × /goal warm）の成立性を claude-code-guide で調査**し、不成立を確定：

- `/goal` は Stop hook ラッパー＝ターン間機構で、ターン内アイドルを warm に保つ keep-alive にはならない
- monitor / background bash タスクは resume 時に復元されない（公式 scheduled-tasks 明記）
- Cloud Routine はタスク完了型で、常駐 long-poll bot は設計想定外（アイドル閾値は非公開）

→ A 不成立を受け、大環主判断で **D を採用**：

- watch に `--exit-on-message` を追加（メッセージ受信サイクルで exit 0）。**メッセージが来たら即 exit→返信→再起動**で即応性を確保（B の「窓満了まで最大 `POLL_SET_SEC` 遅延」を解消）
- **「枠（deadline）」と「ポーリング回数」を分離**：停止主軸を `TS_POLL_SET_COUNT`（回数）から `TS_SESSION_DEADLINE_EPOCH`（時刻）へ。回数はメッセージ頻度で可変、`TS_MAX_TURNS` は暴走保険
- 各ターンは「残り窓 = min(`TS_POLL_SET_SEC`, deadline−now)」を `--max-duration` に渡す foreground watch（`--exit-on-message` 付き）

**未確定（要実機 E2E、別セッション）**: 「foreground 長 call が Cloud Routine のコンテナを warm に保つか」。NG 時の fallback は session 間ループ（短セッションを cron で頻繁反復、既存 lease/offset 冪等性に乗せる）。

以下の Overview〜Stages は **B 案当時の設計記録**として教材保持。D の確定仕様は CHANGELOG [0.7.0] / ROUTINE_PROMPT.md / bootstrap.sh を一次ソースとする（Stage 10.3 の変数は `TS_POLL_SET_COUNT` 廃止 + `TS_SESSION_DEADLINE_EPOCH`・`TS_MAX_TURNS` 追加に改修済み）。

---

## Overview

- **What**: 1 回の Cloud Routine セッション（寿命 ~2時間 = `SESSION_DURATION_SEC` 前提）を、`/goal` が駆動する **ロングポーリング 12 セット**（= `POLL_SET_COUNT`）で埋める。1 セット = 1 つの **foreground な bash tool call**（最大10分 = `POLL_BASH_TIMEOUT_MS`）で、その中を既存 `watch`（long-poll ループ）が `--max-duration`（例 580 秒 = `POLL_SET_SEC`）で回り、窓満了で自然終了（exit 0）。`/goal` がターン完了を検知して次セットを起動、`POLL_SET_COUNT` 達成で停止 → lease release → 次 cron が冪等に拾う。
- **二重ループ（入れ子）**:
  - **session 内ループ**: `/goal` が `POLL_SET_COUNT` セット回す（本計画の主眼）。各セット = foreground watch call。
  - **session 間ループ**: cron（`/schedule`）が session を反復起動。session 寿命を超える継続は lease/offset 冪等性でカバー（既存 Stage 1-5 実証済み）。
- **Why**: ポーリングのバックグラウンドタスクが走っていても、**セッション（意識層）がアイドルだとコンテナが閉じられる**。`/goal` の各ターンが foreground の長い bash call を抱えることでセッションを warm に保ち、かつ **bash 内 long-poll なので待機中のトークン消費はほぼゼロ**（10分待ちは getUpdates のサーバ側ブロック）。
- **コード側の最小実装**: `watch` への wall-clock 停止 `--max-duration`（秒）追加。実コード検証済みギャップ: [main.py:141 `cmd_watch`](scripts/main.py)、停止条件は `args.max_iterations`（L218）のみで wall-clock 停止なし（`max_duration` は grep ヒットゼロ）。
- **Where**: 既存 `Expertises/TelegramSecretary/` 配下に増分。
  - Domain: `domain/watch_window.py` 新規（`WatchWindow` 値オブジェクト）
  - Infra/CLI: `main.py::cmd_watch` に `--max-duration` 配線、`build_parser` に引数
  - 設定: `bootstrap.sh` に運用変数 export（既存 `TELEGRAM_SECRETARY_SESSION_ID` export と同型）、`.claude/settings.json` に `BASH_MAX_TIMEOUT_MS`
  - Doc: `ROUTINE_PROMPT.md` に `/goal` 12セット手順、`SKILL.md`/`README.md`/`CHANGELOG.md`

## 確定した技術前提（claude-code-guide 2回の調査、🔵 公式ドキュメント）

| 項目 | 確定事実 | 出典/状態 |
|---|---|---|
| `/goal` 実体 | v2.1.139 ネイティブ。条件文に停止条件を自然文記述、各ターン後に小型モデルが評価、未達で次ターン自律起動 | code.claude.com/docs/en/goal |
| `BASH_MAX_TIMEOUT_MS` | timeout の**上限クランプ**（既定 600000ms）。これを上げても DEFAULT は不変 | env-vars.md |
| `BASH_DEFAULT_TIMEOUT_MS` | timeout 省略時の**デフォルト**（既定 120000ms=2分）。**据え置く**ので他コマンドは2分維持 | env-vars.md |
| ポーリング限定適用 | グローバル MAX=600000 + ポーリング call だけ `timeout: 600000` 明示 + DEFAULT 据え置き + 運用規律で**達成可能** | 設計確定 |
| 600000ms 超の最大化 | 内部ハードクランプの可能性、**要実測**。ただし 2h÷12=10分で 600000 で足りるため**超過不要** | 要実測（回避） |
| SIGTERM バグ回避 | 自前タイマーで先に exit → timeout 発火させない設計は論理的に安全。バグ自体は公式記述なし | 要実測 |
| `/goal` × foreground call | 「call 返却→ターン閉じ→評価→次ターン」の直列動作と推測、/goal 設計と整合 | 要実測 |

## 設計の根幹（前提変容の記録）

### 前提変容①: 要件を「2つの世界」に分解（L00456 三世界分類）

| 関心事 | 世界 | 実装場所 |
|---|---|---|
| watch の wall-clock 自然停止（1セット 580秒で畳む） | 決定論的（テスト可能） | `WatchWindow` + `cmd_watch --max-duration`（Stage 10.1-10.2） |
| `/goal` が 12 セット駆動・セッション warm 保持 | 従属度（手順委任） | `ROUTINE_PROMPT.md`（Stage 10.4、コード化しない） |
| 運用パラメータ（duration/count/timeout） | 決定論的（設定） | env 変数 + settings.json（Stage 10.3） |

**急所**: コードに必要なのは「watch が wall-clock で自然終了する」一点のみ。それさえあれば `/goal` のドライブ方式に非依存で冪等性が成立。

### 前提変容②: 数字が綺麗に閉じる

`SESSION_DURATION_SEC`(7200=2h) ÷ `POLL_SET_COUNT`(12) = 1セット 600秒 = bash 最大 timeout(600000ms)。**bash 1 call の上限が「1セット」の自然な単位**になる。watch の `--max-duration` は bash timeout より短く（580秒）して終了処理余裕と SIGTERM 回避バッファを確保。検算: 12 × 580秒 = 6960秒 + ターン間オーバーヘッド（評価・返信処理）≈ 7200秒(2h)。

### 全体の流れ

```
[/schedule（例 2時間毎）でセッション起動]
  → Step 0-4: 人格ロード → bootstrap（運用変数 export）→ egress 疎通 → lease acquire
  → /goal "Telegram 監視。watch を1セット実行ごとに1カウント、POLL_SET_COUNT セットで停止。
            拾ったメッセージは send-reply で返信完了。or stop after (COUNT+2) turns。停止時に未返信無きこと。"
       ── 各ターン（= 1セット）─────────────────────────
       │ watch --max-duration $POLL_SET_SEC --timeout 30   ← foreground、bash timeout=$POLL_BASH_TIMEOUT_MS
       │   （内部で getUpdates を timeout 30 でループ、580秒で自然 exit 0）
       │ → メッセージあれば send-reply、なければ素通り
       │ → call 返却でターン閉じ → /goal 評価（COUNT 達成?）→ 未達なら次ターン
       └────────────────────────────────────────
  → POLL_SET_COUNT 達成 → /goal 停止
  → Step 7: lease release（次 cron が lease/offset 冪等性で継続）
```

## 変数設計（要件: 変数化・テスト容易性）

`bootstrap.sh` で export（既存 `TELEGRAM_SECRETARY_SESSION_ID` の `:-` デフォルト方式と同型、環境で上書き可能）:

| 変数 | デフォルト | 意味 | テスト時の例 |
|---|---|---|---|
| `TS_SESSION_DURATION_SEC` | `7200` | session 寿命の前提（2h）。ゴール算出の元・ドキュメント用 | `60` |
| `TS_POLL_SET_COUNT` | `12` | ロングポーリングのセット数（= /goal の目標ターン数） | `2` |
| `TS_POLL_SET_SEC` | `580` | 1セットの `watch --max-duration`（bash timeout より短く） | `10` |
| `TS_POLL_BASH_TIMEOUT_MS` | `600000` | ポーリング call の bash tool timeout（= MAX） | `15000` |

- **関係式**: `POLL_SET_COUNT ≈ SESSION_DURATION_SEC / (POLL_SET_SEC + overhead)`。独立変数として持ち、デフォルトで関係を満たす。整合性チェック（count × set_sec が duration を超えないか）は `bootstrap.sh` の `validate-config` で警告するか YAGNI 判断（Stage 10.3 で決定）。
- **テスト**: `TS_POLL_SET_COUNT=2 TS_POLL_SET_SEC=10` で約20秒の E2E が回せる。本番値に触れずパラメータだけ差し替え。

## BASH_MAX_TIMEOUT_MS 設計（要件: ポーリングだけに適用）

- `.claude/settings.json`（TelegramSecretary 用、または Routine 起動環境）に `BASH_MAX_TIMEOUT_MS=600000` を設定（上限引き上げ）。**`BASH_DEFAULT_TIMEOUT_MS` は設定しない**（既定 120000ms=2分を維持）。
- **運用規律（ROUTINE_PROMPT に明記）**: ポーリング call **だけ** `timeout: $TS_POLL_BASH_TIMEOUT_MS` を明示。他のコマンド（git/pytest/lease 操作等）は timeout 無指定 → DEFAULT 2分。これにより「長い timeout はポーリングだけが受ける」が実効的に成立。
- グローバル設定の副作用は「許容上限が上がるだけ」で実害なし（公式確認済み）。`update-config` skill で settings.json を編集する。

## Architecture（Clean Architecture 4層、依存は内向きのみ）

| Layer | 責務 | 主要な型/関数 | 依存先 |
|---|---|---|---|
| **Domain** | watch 窓の wall-clock 満了判定（純ロジック） | `WatchWindow(started_at, max_duration_seconds)` / `.is_expired(now)` / `.remaining_seconds(now)`（frozen dataclass、`SessionLease.is_stale` と同型） | なし |
| **UseCase** | （追加なし） | watch ループ制御は CLI 責務 | Domain |
| **Interface** | （追加なし） | — | UseCase, Domain |
| **Infrastructure** | `cmd_watch` への `--max-duration` 配線、bootstrap 変数 export、ROUTINE_PROMPT の /goal 手順 | `main.py::cmd_watch`（`iterations += 1` 後に `window.is_expired(utc_now())` で break）/ `build_parser` に `--max-duration`（default 0=無限） | 全層 |

`utc_now()` は既存 `domain/lease.py` の注入可能関数（`main.py` L22 で `from domain.lease import utc_now` 束縛済み）。テストは `main.utc_now` を patch。

## Stages

## Stage 10.1: Domain — WatchWindow 値オブジェクト
**Goal**: watch の wall-clock 窓を表す純粋値オブジェクトと満了判定。
**Layer**: Domain
**Success Criteria**: `domain/watch_window.py` の全テスト green、import が標準ライブラリ（`datetime`/`dataclasses`）のみ。既存 318 tests 無変更で green。
**Tests** (Red → Green):
  - `WatchWindow(started_at, max_duration_seconds=580).is_expired(now)`: `now > started_at + 580s` で True、未満で False（境界 `>`、`SessionLease.is_stale` と同一）
  - `max_duration_seconds=0`（無限）では常に False（既存 `--max-iterations 0=無限` と同型）
  - `remaining_seconds(now)` が残り秒を返す（満了後 0 以下）
**Implementation Notes**: `frozen=True` dataclass、`started_at: datetime`（tz-aware UTC）/ `max_duration_seconds: int`。`is_expired` 先頭に `if self.max_duration_seconds <= 0: return False`、以降 `now > self.started_at + timedelta(seconds=...)`。`domain/lease.py::is_stale` を参照パターンに。
**Status**: Complete（2026-05-29、D 改修込み。詳細は冒頭「設計転換」と CHANGELOG [0.7.0]）

## Stage 10.2: Infrastructure/CLI — cmd_watch に --max-duration 配線
**Goal**: `watch` に `--max-duration`（秒、default 0=無限）を追加、各サイクル末で `WatchWindow.is_expired` 判定し exit 0。
**Layer**: Infrastructure
**Success Criteria**: `watch --max-duration <秒>` が窓満了で exit 0。`0`（既定）は従来どおり無限。既存 `--max-iterations`/`--cleanup-interval`/lease conflict(exit 4) と排他なく共存。既存 watch テスト群が無変更で green。
**Tests** (Red → Green):
  - `--max-duration` 満了（fake clock で `utc_now` を窓越えに）で1サイクル後 exit 0。`--max-iterations` 未指定でも時間で止まる
  - `--max-duration 0` かつ `--max-iterations 1` で従来どおり1周で抜ける（後方互換）
  - lease conflict は `--max-duration` 未満了でも従来どおり exit 4（優先順位: auth>lease>時間/回数）
**Implementation Notes**: `cmd_watch` 冒頭で `window = WatchWindow(started_at=utc_now(), max_duration_seconds=args.max_duration)`。`iterations += 1` 直後・`if args.max_iterations and ...: break`（L218）の隣に `if window.is_expired(utc_now()): break`（OR、どちらが先でも自然終了）。`build_parser` の `p_watch`（`--max-iterations` 定義 L338 付近）に `--max-duration`（`type=int, default=0`）。テストは既存 `_install_mock_transport`+`monkeypatch` で `main.utc_now` を fake clock に。**3-Strike 予想**: `utc_now` patch ポイントは `main.utc_now`（確定済み）。`watch_loop.sh` は `"$@"` 素通しゆえ変更不要。
**Status**: Complete（2026-05-29、D 改修込み。詳細は冒頭「設計転換」と CHANGELOG [0.7.0]）

## Stage 10.3: 設定/変数化 — bootstrap 変数 export + settings.json
**Goal**: 運用変数（`TS_*`）を `bootstrap.sh` で export、`BASH_MAX_TIMEOUT_MS=600000` を settings.json に設定。
**Layer**: Infrastructure（設定）
**Success Criteria**: `bootstrap.sh` source で `TS_SESSION_DURATION_SEC/TS_POLL_SET_COUNT/TS_POLL_SET_SEC/TS_POLL_BASH_TIMEOUT_MS` がデフォルト値で export され、環境で上書き可能。settings.json に `BASH_MAX_TIMEOUT_MS=600000`（`BASH_DEFAULT_TIMEOUT_MS` は未設定で2分維持）。
**Tests / 検証**:
  - `bootstrap.sh` source 後に `echo $TS_POLL_SET_COUNT` 等が既定値を返す。`TS_POLL_SET_COUNT=2 source bootstrap.sh` で上書きが効く（既存 `TELEGRAM_SECRETARY_SESSION_ID` の `:-` 冪等性テストと同型）
  - settings.json に `BASH_MAX_TIMEOUT_MS` が入り、`BASH_DEFAULT_TIMEOUT_MS` が無いこと（grep 確認）
**Implementation Notes**: `bootstrap.sh` の session_id export ブロックの隣に `export TS_POLL_SET_COUNT="${TS_POLL_SET_COUNT:-12}"` 等を追加（4変数）。settings.json は `update-config` skill 経由で `env.BASH_MAX_TIMEOUT_MS` を `600000` に。整合性チェック（count×set_sec ≤ duration）を `validate-config` に足すかは YAGNI 判断。
**Status**: Complete（2026-05-29、D 改修込み。詳細は冒頭「設計転換」と CHANGELOG [0.7.0]）

## Stage 10.4: ROUTINE_PROMPT — /goal 12セット手順 + ドキュメント
**Goal**: `ROUTINE_PROMPT.md` に「`/goal` で `POLL_SET_COUNT` セット駆動、各ターン foreground watch call」手順を記述。timeout 限定適用の運用規律とコスト防衛を明記。SKILL/README/CHANGELOG 更新。
**Layer**: Infrastructure（運用統合 + ドキュメント）
**Success Criteria**: ROUTINE_PROMPT に `/goal` 条件文（COUNT セットで停止 + `or stop after (COUNT+2) turns` 保険）、各ターンの `watch --max-duration $TS_POLL_SET_SEC --timeout 30` を `timeout: $TS_POLL_BASH_TIMEOUT_MS` で foreground 実行、「ポーリング以外は timeout 明示しない」運用規律、窓満了→lease release→次 cron が明記される。README/SKILL の Subcommands に `--max-duration` 反映。
**Tests / 検証**（ドキュメント Stage、実機 E2E は別セッション）:
  - 手順を上から追って /goal 起動→watch 12セット→COUNT 達成→lease release→次 cron の一筆書きが矛盾なく辿れる
  - 変数（`TS_*`）参照が bootstrap export と整合
  - 実機 E2E（`TS_POLL_SET_COUNT=2 TS_POLL_SET_SEC=10` で約20秒の短縮版を fresh session 実行 → 2セット後 /goal 停止 → lease release → 次起動 acquire）は別セッション待ち。**要実測項目（SIGTERM 非発火・/goal 直列動作・session 寿命）をこの E2E で確認**
**Implementation Notes**: ROUTINE_PROMPT の watch 起動行を `--max-duration $TS_POLL_SET_SEC` 付き + bash `timeout: $TS_POLL_BASH_TIMEOUT_MS` 明示に。`/goal` 条件文に COUNT と turn 上限（COUNT+2）の二重停止。**コスト注意**: メインターンはフルモデル課金だが、待機は bash 内 long-poll ゆえターン内トークンは最小。CHANGELOG は 0.7.0 目安で「watch `--max-duration`、`WatchWindow` Domain、bootstrap 運用変数、settings `BASH_MAX_TIMEOUT_MS`、ROUTINE_PROMPT /goal 12セット手順」。
**Status**: Complete（2026-05-29、D 改修込み。詳細は冒頭「設計転換」と CHANGELOG [0.7.0]）

## Stage 11: E2E 実機検証（Cloud Routine、Phase 段階）

**Goal**: D の独立4関門を最重要から切り分け検証。Phase 0（コンテナ維持）を最小コストで先に確定し、NG なら fallback（session 間 cron）へ即転換して Phase 1/2 を省く。
**Layer**: 運用検証（実機 Cloud Routine 必須、ローカル不可）。コード（`--max-duration` / `--exit-on-message`）は green 済みゆえ本検証は「ハーネスが Cloud Routine で成立するか」の確認に限定。
**前提**: bot token・authorized chat は準備済み。Cloud Routine（`/schedule`）への新規登録が必要。

### 検証マトリクス

| Phase | 狙う関門 | 短縮パラメータ | メッセージ | pass 基準 | fail 時 |
|---|---|---|---|---|---|
| **0** | コンテナ維持 + deadline 停止（**最重要ゲート**） | `TS_SESSION_DURATION_SEC=180` `TS_POLL_SET_SEC=60` | 送らない | 3分間 watch が複数サイクル回り deadline で正常終了。途中でコンテナが落ちない | **コンテナ維持不成立** → fallback（session 間 cron 反復）へ転換、Phase 1/2 中止 |
| **1** | early-exit 即応ループ | 同上 | 1–2通送る | メッセージに ≤数十秒で返信し、exit→返信→再起動が継続 | early-exit / 再起動 / 返信のどこが落ちたか stderr で切り分け |
| **2** | フル安定 + SIGTERM 非発火 + コスト | 本番 `7200` / `580` | 随時 | 2時間安定・プロセス自然終了（SIGTERM 痕跡なし）・トークン妥当 | 窓畳みバッファ（580<600）/ cron 間隔を見直し |

### 短縮版の利点（Phase 0/1）
60秒窓は **bash 既定 timeout 2分（120000ms）で収まる**ため、`TS_POLL_BASH_TIMEOUT_MS=600000` を使わずに回せる。`BASH_MAX_TIMEOUT_MS` 設定の有無に依存せず最重要ゲートを検証できる（600000 が要るのは本番 580秒窓のときだけ）。

### Cloud Routine 登録手順（`/schedule`）
1. prompt body = `ROUTINE_PROMPT.md`（Step 0–7）。Phase 0/1 は Step 2（bootstrap）の前に短縮 env を export（`export TS_SESSION_DURATION_SEC=180 TS_POLL_SET_SEC=60`）。ROUTINE_PROMPT の「E2E 短縮モード」注記を参照
2. 起動は手動 run（cron を待たず即トリガ）で Phase 0 を回す。Phase 2 で cron 間隔（例 2h）を設定
3. `session_context` に人格4ファイル（WeaveIdentity / WeaveInstruction / UserIdentity / SECURITY）+ SecretaryRole を注入（BlueberrySprite Routine と同型、`reference_remote_trigger_update` 準拠）

### 観測方法
- Cloud Routine 実行ログ：watch サイクル数（emit/heartbeat）、lease acquire/renew/release、`/goal` ターン遷移、stderr（auth/transient/lease lost）
- Phase 1：Telegram 実応答（返信の到達と遅延）
- deadline 停止：`/goal` が止まりログ末尾に lease release が出るか

### 最重要ゲート Phase 0 の判定
- **pass**: ログに watch ≥2 サイクル + 約3分後に deadline → lease release。コンテナが3分間生存 → 「foreground 長 call で warm 維持」成立 = D の根幹 OK
- **fail（コンテナ即閉鎖）**: 1サイクル目の watch 中/直後にログ途絶 → 維持不成立。**fallback**: ROUTINE_PROMPT を session 間ループへ（短セッション = lease acquire → `watch --exit-on-message --max-iterations N` で数サイクル → メッセージ捌いて即終了 → cron 1–5分毎に反復）。コード（early-exit / max-duration）は両設計で再利用、即応性は cron 間隔へ依存

**Status**: Not Started（実機 E2E、別セッション。bot/chat 準備済み → Routine 登録から）

## Documentation Plan

| ドキュメント | パス | 区分 | 内容 |
|---|---|---|---|
| `README.md` | TelegramSecretary/README.md | 更新 | Subcommands に `--max-duration`、運用変数 `TS_*` の説明、Quickstart に短縮版 E2E（`TS_POLL_SET_COUNT=2`） |
| `CHANGELOG.md` | TelegramSecretary/CHANGELOG.md | 更新 | 0.7.0 目安エントリ（上記 10.4 の内容） |
| `SKILL.md` | TelegramSecretary/SKILL.md | 更新 | Subcommands に `--max-duration`、Daily Workflow に /goal 12セット |
| `ROUTINE_PROMPT.md` | TelegramSecretary/ROUTINE_PROMPT.md | 更新 | Stage 10.4 中核成果物 |
| `bootstrap.sh` | TelegramSecretary/bootstrap.sh | 更新 | `TS_*` 変数 export（Stage 10.3） |
| `.claude/settings.json` | 起動環境の settings | 更新 | `BASH_MAX_TIMEOUT_MS=600000`（Stage 10.3、`update-config` 経由） |
| `DESIGN.md` | TelegramSecretary/DESIGN.md | 要確認 | 「セッション内12セット × cron 反復の入れ子」「timeout 限定適用」を原則として1行。Stage 10.4 で判断 |
| `IMPLEMENTATION_PLAN.md`（既存） | TelegramSecretary/ | 要確認 | 本計画を Stage 10 吸収か独立保持か。着地後判断 |
| `pyproject.toml` / `watch_loop.sh` / root `CLAUDE.md` | — | 不要 | 標準ライブラリのみ / 引数素通し / 本番投入前 |

**SSoT**: `--max-duration` 説明は CLI help を一次ソース、README/SKILL は要約参照。`/goal` 手順は ROUTINE_PROMPT、変数定義は bootstrap.sh が一次ソース。

## Decision Priority Notes（Testability > Readability > Consistency > Simplicity > Reversibility）

- **watch ループ制御を UseCase に切り出さず CLI に置く**: 既存 `cmd_watch` がループ制御を持つので `--max-duration` 追加が最小整合（Consistency）。停止判定核（`WatchWindow.is_expired`）は Domain 純関数でテスト可能（Testability）。UseCase 化は停止条件3種では過剰（Simplicity/YAGNI）。
- **停止条件の実体を `/goal` でなく `watch --max-duration`（決定論）に**: LLM 判断依存はテスト不能（Testability 違反）。コードに閉じれば `/goal` の挙動差異・実測未確定に頑健（Reversibility）。`/goal` の `stop after N turns` は保険。
- **変数を env で持つ**: 既存 `TELEGRAM_SECRETARY_SESSION_ID` export と同型（Consistency）。テスト時パラメータ差し替えが env 上書きだけ（Testability）。config ファイル新設は過剰（Simplicity）。
- **`BASH_MAX_TIMEOUT_MS` グローバル + 個別 timeout 指定**: DEFAULT を据え置くことで他コマンドへの副作用ゼロ（公式確認）。特定コマンド限定の hook は過剰（Simplicity）。
- **watch `--max-duration`(580) < bash timeout(600)**: プロセス自然終了を timeout 発火より優先（SIGTERM 回避）。20秒バッファは終了処理（lease renew 等）余裕（Reversibility/頑健性）。
- **`WatchWindow` を `SessionLease.is_stale` と同型 / `--max-duration 0=無限`**: 既存パターン踏襲（Consistency/Readability）。

## 3-Strike Rule

- **詰まりやすい予想**:
  1. `utc_now` patch（確定: `main.utc_now`）。fake clock のループ内窓越え進行が既存 monkeypatch と噛み合うか
  2. 窓満了と long-poll 干渉: `--timeout 30` ブロック中の満了は最大30秒遅延（次 getUpdates 戻りで判定）。実用窓580秒に無害、短窓テストは `--timeout 1`
  3. **要実測 3 項**: `BASH_MAX_TIMEOUT_MS` 600000 超可否（回避済＝600000で足る）/ SIGTERM 非発火 / `/goal` 直列動作・session 寿命
- **代替**:
  - `utc_now` patch → 既存 `--max-iterations 1` 制御踏襲、`side_effect` で「1回目=窓内,2回目=窓越え」。最悪コンストラクタ注入
  - `/goal` 不成立 → fallback（A: watch 単発 foreground / B: /loop 代替 / C: cron 短縮）を `AskUserQuestion`。最小仕様は 10.1-10.2 完成ゆえ A で着地
- **相談ライン**: `/goal` 実測で「コンテナ維持不成立」判明時、または `utc_now` patch 3回で不安定時に `AskUserQuestion`

## Security / OPS（OPS.md 継承）

- **コスト（最重要）**: メインターンはフルモデル課金。だが**待機は bash 内 long-poll ゆえターン内トークン最小**（10分待ちは getUpdates サーバ側ブロック）。12 ターン/session のターン数は限定的。session を2hで畳み cron 反復で長時間化、`/goal` に turn 上限（COUNT+2）保険。`feedback_no_api_key.md` 射程内、Stage 10.4 E2E で実コスト実測。
- **冪等性**: 窓満了→lease release→次 cron acquire は既存 lease/offset 冪等性（Stage 1-5 実証）。cron 間隔の隙間メッセージは次 getUpdates（offset 起点）で回収（Telegram ~24h 保持）。
- **secrets/ログ**: 本機能は token/PII を新規に扱わない（時刻・秒数のみ）。
