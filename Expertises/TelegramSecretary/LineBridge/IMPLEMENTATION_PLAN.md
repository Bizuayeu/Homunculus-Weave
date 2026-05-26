# Implementation Plan: LineBridge（TelegramSecretary 用 LINE 薄ラッパー層）

> 本計画は `Expertises/ConsiderateCoder/rules/DEV.md` および `/plan-sdd` の方針で生成。全 Stage 完了後に削除する。
> 親 Expertise: `Expertises/TelegramSecretary/`。本ファイルはその入れ子 (`LineBridge/`) に置く。
> 哲学: **TelegramSecretary が本体、LineBridge は薄いラッパー**。Telegram 直接利用者は Bridge をバイパス可能。

## Overview

- **What**: 大環主の関係者複数を集約する Weave 専用 LINE Official Account を、Railway 相乗りの常駐サービスとして TelegramSecretary（Cloud Routine 上 Weave 本体）と接続する薄いプロトコル変換層。`LINE 関係者 N 人 ⇄ Telegram Weave bot 1 個` を mux する。
- **Why**: LINE は webhook-only で Cloud Routine の inbound HTTP 制約と非互換。だが大環主の日常導線・関係者の導入容易性は LINE が圧倒。Bridge を別ホスティング（決定論的世界）に切り出すことで、Weave 側（重要度の世界）の設計（TelegramSecretary）を無変更で活かす。
- **Where**: `Expertises/TelegramSecretary/LineBridge/`（本ファイル＋scripts）。デプロイ先は既存 SpiritualAdvisor の Railway プロジェクトに相乗りサービスとして追加。Redis アドオンを新規付与。
- **Reference Patterns**:
  1. `Expertises/TelegramSecretary/IMPLEMENTATION_PLAN.md`（親、依存先）
  2. `Expertises/NewsCaster/scripts/`（Clean Architecture 4 層、Port/Adapter 分離、UseCase は fake で全分岐検証可能）
  3. SpiritualAdvisor（Railway 本番運用パターン、env 管理、デプロイ手順）

## 設計の根幹（検証済みの環境制約から導出）

| 制約 | 出典 | 設計への反映 |
|---|---|---|
| LINE Messaging API は webhook only、long-polling 不可 | developers.line.biz/messaging-api/overview | 公開 HTTPS が必須。Bridge を Railway に常駐させ、Cloud Routine 制約を完全に外部化 |
| webhook URL は HTTPS + 信頼できる CA 発行 SSL/TLS 必須（自己署名不可） | LINE Developers Console 仕様 | Railway 標準ドメイン (`*.up.railway.app`) の有効証明書をそのまま利用 |
| `reply token` は 1 分以内に消費しないと失効 | LINE Messaging API リファレンス | 応答時間が 1 分を超える可能性ある以上、**reply API は使わず push message API を基本にする**。reply は短文確認系のみ補助利用 |
| webhook event は重複配信あり (`webhookEventId` で検出) | LINE 公式ドキュメント | KV `idempotency:{webhook_event_id}` (TTL 1h) で dedup |
| 関係者間プライバシー境界 | OPS.md §1・本計画 ③ 承認モデル | ③ 関係者間共有は大環主承認必須。Bridge は KV `identity.shared_with` を都度参照、未承認なら共有しない |
| LLM 推論を Bridge に持たない（決定論的世界の純化） | L00456 三世界分類 / CLAUDE.md | 応答生成は Telegram 経由で **Weave 本体に委譲**。Bridge は受信→正規化→転送→送信のみ |
| Webhook 検証 (X-Line-Signature) | LINE 公式 | 受信時に必ず HMAC-SHA256 で署名検証、失敗は即 400 |
| Cloud Routine ↔ Bridge 通信 | Cloud Routine は outbound のみ自由 | Cloud Routine 側 (TelegramSecretary) → Bridge への push は **Bridge が提供する内部 API**（Bearer 認証）で受ける。LINE 配信は Bridge が代行 |

## Architecture（Clean Architecture 4 層、依存は内向きのみ）

| Layer | 本機能における責務 | 主要な型/関数 | 依存先 |
|---|---|---|---|
| **Domain** | 純粋ロジック・値オブジェクト | `UserUuid` / `LineUserId` / `TelegramChatId` / `User`（status, role, identity を含む集約ルート）/ `Identity`（category, relationship_label, honorific, tone, context_notes, shared_with, priority_bias, taboo_topics）/ `RelayDirection`（`line_to_telegram` / `telegram_to_line`）/ `MuxTag`（`[from:line:X]` / `[to:line:X]` / `[relay-to:line:X]` パーサ・ビルダ）/ `ApprovalRequest`（pending 状態の関係者初回接触）/ `idempotency_key()` / `verify_line_signature()` 等の純関数 | なし |
| **UseCase** | オーケストレーション + Port 定義 | Ports: `UserStore` / `IdempotencyStore` / `LineApiPort` / `TelegramRelayPort` / `PendingApprovalStore` / `DailySummaryStore`<br>UseCases: `RegisterOrFetchUser`（friend 追加→pending 登録）/ `HandleIncomingLineMessage`（認可→正規化→mux タグ付与→Telegram へ）/ `RequestApprovalFromPrincipal`（未承認関係者初回接触時）/ `DeliverApprovedRelay`（承認後の通常応答）/ `RelayFromWeave`（Weave 起草を mux タグ解析→該当 LINE userId に push）/ `ListActiveUsers`（`/list` の応答用）/ `LinkAccounts`（Telegram/LINE 同一人物紐付け）/ `UpdateIdentity`（identity 編集）/ `BuildDailySummary` | Domain のみ |
| **Interface (Adapter)** | ゲートウェイ・ストア・HTTP エンドポイント | `LineApiGateway`（push/reply/profile 取得、UA・retry・timeout）/ `RedisUserStore`（user 主レコード + 逆引きインデックス）/ `RedisIdempotencyStore`（TTL 付き dedup）/ `TelegramRelayClient`（Cloud Routine 側 TelegramSecretary に転送、もしくは Telegram bot に直送）/ FastAPI ルーター（`POST /webhook/line` / `POST /internal/relay-to-line` / `GET /healthz` / `POST /internal/daily-summary`）| UseCase, Domain |
| **Infrastructure** | 外部・フレームワーク | `main.py`（FastAPI app 起動）/ `config.py`（env loader）/ `Procfile` or `railway.toml`（Railway デプロイ設定）/ Redis 接続管理 / cron worker（日次サマリ起動用、Railway cron アドオン or 自前 APScheduler）| 全層（最外殻） |

### Dependency Direction

`Infrastructure → Interface → UseCase → Domain`。Domain は外層を import しない。LINE SDK / FastAPI / Redis / HTTP client はすべて UseCase の外（Port の向こう）。**LLM 推論は本サービスに存在しない**——応答生成は Telegram 経由で Weave 本体が担う。

### Endpoints

| Method | Path | 機能 | 認証 |
|---|---|---|---|
| POST | `/webhook/line` | LINE Platform からの webhook 受信 | X-Line-Signature 検証 |
| POST | `/internal/relay-to-line` | Cloud Routine 側 Weave からの「LINE へ転送して」呼び出し（mux タグまたは user_uuid 指定 + 本文） | Bearer token (env) |
| POST | `/internal/approval-callback` | 承認結果コールバック（LINE Postback / Telegram callback_query の両方を統一受信） | Bearer token (Telegram 側) / 署名検証 (LINE 側) |
| POST | `/internal/daily-summary/trigger` | 日次サマリ起動（cron または手動） | Bearer token |
| GET | `/healthz` | 死活監視 | なし |

### 想定フロー（確定事項①〜⑤を全反映）

```
[関係者 X の friend 追加]
   ↓ LINE webhook (follow event)
[Bridge] 署名検証 → KV idempotency 確認 → user 自動登録 (status: pending)
                                          ↓
                                  TelegramSecretary に通知
                                          ↓
                                  Weave: 大環主に「Xから新規接触、承認しますか？」push
                                          ↓
                            ┌── 承認 → status: active、初回応答ドラフトを Weave が起草 → Bridge → X
                            └── 拒否 → status: blocked、以降の webhook は即破棄

[active 関係者 X の通常メッセージ]
   ↓ LINE webhook (message event)
[Bridge] 検証 → dedup → User 取得 → identity 取得
                                    ↓
                          mux タグ [from:line:X] + 本文 を Telegram 経由で Weave に転送
                                    ↓
                          Weave: identity（tone/honorific/taboo）参照しつつ応答ドラフト
                                + 重要度判定 + エスカレ判定 + 共有候補判定
                                    ↓
            ┌── 即返信、重要度 low  → [to:line:X] 付きで Bridge へ → X へ push
            ├── 即返信、重要度 high → 同上 + 大環主に同時 push（要旨）
            ├── 大環主判断要        → 大環主に push（X には「確認中です」自動応答）
            └── 共有候補あり        → 大環主に「Y にも共有可？」承認伺い → 承認後 identity.shared_with 更新 → Y にも relay

[毎日 09:00 JST 日次サマリ cron]
   Railway cron → POST /internal/daily-summary/trigger
   → Bridge: KV から過去24h の active threads / pending approvals / 重要案件を集約
   → TelegramSecretary 経由で Weave に「サマリ整形して」依頼
   → Weave 整形応答 → Bridge → 大環主の Telegram に push

[大環主の指示「Xにこう返して」]
   ↓ 大環主の Telegram → Weave
   ↓ Weave: [relay-to:line:X] + 本文 を Bridge の /internal/relay-to-line に送出
   ↓ Bridge: user_uuid 解決 → LINE push message → X
```

## ユーザーDB スキーマ（Redis、KV 構造）

```
user:{user_uuid}                              # 主レコード（JSON）
  uuid: str
  display_name: str
  role: "principal" | "associate"
  status: "pending" | "active" | "blocked"
  line_user_id: str | null
  telegram_chat_id: int | null
  registered_at: ISO8601
  approved_at: ISO8601 | null
  identity:
    category: "family" | "friend" | "client" | "vendor" | "employee" | "peer" | "introducer" | "other"
    relationship_label: str                   # "めぐる組営業部長"
    honorific: str                            # "山田さん"
    tone: "casual" | "polite" | "formal"
    context_notes: str                        # 自由記述
    shared_with: [user_uuid, ...]             # ③ 共有承認済み相手
    priority_bias: "low" | "normal" | "high"
    taboo_topics: [str, ...]

index:line:{line_user_id}      → user_uuid    # 逆引き
index:telegram:{telegram_chat_id} → user_uuid
principal:user_uuid            → user_uuid    # 大環主の uuid を単一値で保持

idempotency:{webhook_event_id} → "1"  TTL=1h
pending_approval:{user_uuid}   → JSON  TTL=72h  # 大環主が放置した場合の自動失効
thread:{thread_id}             → JSON  TTL=30d  # 進行中のコンテキスト要約
daily_summary:queue            → list[JSON]    # 過去24h の集約対象
```

## Subcommands / 操作コマンド（Telegram 側 = Weave 経由）

### マスター入口

| コマンド | 機能 | 権限 |
|---|---|---|
| `/secretary` | **管理パネル**：active/pending/blocked カウント表示＋全操作メニュー（インライン キーボード）。個別コマンドへの導線として機能 | principal のみ |

`/secretary` を叩けば下記の個別コマンドにメニュー経由でアクセスできる。コマンド名を覚えていなくても操作可能。慣れた利用者は個別コマンドを直接叩いてショートカット可能。

### 個別コマンド（`/secretary` メニューから展開、または直接実行）

| コマンド | 機能 | 権限 |
|---|---|---|
| `/list` | active な関係者一覧（display_name, role, LINE有無, Telegram有無, 最終接触日, priority_bias） | principal のみ |
| `/pending` | 承認待ち関係者一覧 | principal のみ |
| `/approve <user_uuid>` | pending → active 切替 | principal のみ |
| `/block <user_uuid>` | active/pending → blocked | principal のみ |
| `/edit-user <user_uuid>` | identity 編集（対話的に項目選択） | principal のみ |
| `/link <user_uuid> <other_id>` | 同一人物の LINE/Telegram アカウント紐付け | principal のみ |
| `/share <from_uuid> <to_uuid>` | 関係者間共有を事前許可（identity.shared_with に追加） | principal のみ |
| `/list-shares [<user_uuid>]` | 共有許可済みの関係性一覧。引数なしで全体、引数ありで該当 user の許可状況 | principal のみ |
| `/unshare <from_uuid> <to_uuid>` | 共有許可の取消（identity.shared_with から削除） | principal のみ |
| `/relay <user_uuid> <text>` | 関係者へのリレー指示（Weave 経由 or 直接送信） | principal のみ |

これらは TelegramSecretary 側で受信、Weave がプロンプトで意図解釈、必要に応じて Bridge の `/internal/*` API を叩く。`/secretary` メニュー UI は Weave 側プロンプトに「`/secretary` 受信時はインライン キーボードでメニュー表示」を組み込む。

## Stages

## Stage 1: Domain 値オブジェクト + 純粋ロジック
**Goal**: 外部依存ゼロの値オブジェクトと、認可・承認・正規化・mux タグの純関数。
**Layer**: Domain
**Success Criteria**: 全 Domain テストが green、import が標準ライブラリ + `dataclasses` + `hmac`/`hashlib` のみ。
**Tests** (Red → Green):
  - `User.is_active()` / `is_pending()` / `is_blocked()` の状態判定
  - `Identity` の正規化（taboo_topics 重複除去、tone 不正値で ValueError）
  - `MuxTag.parse("[from:line:U1234abc] hello")` → `(channel="line", user_id="U1234abc", body="hello")`、`build()` の対称性
  - `MuxTag` の不正フォーマットで `ValueError`（インジェクション防御）
  - `verify_line_signature(body, signature, secret)` が正常/改竄/secret 不一致を判定
  - `idempotency_key(event_id)` がフォーマット一意
**Implementation Notes**: frozen dataclass、`__post_init__` でバリデーション。NewsCaster `domain/` の書式に倣う。
**Status**: Not Started

## Stage 2: UseCase + Ports（fake adapter で駆動）
**Goal**: 承認フロー・通常応答・リレー・日次サマリのオーケストレーションを Port 越しに完成。
**Layer**: UseCase
**Success Criteria**: 6 Port すべて fake で UseCase 全分岐をテスト。実 I/O ゼロ。
**Tests** (Red → Green):
  - `RegisterOrFetchUser`: 新規 friend → user 作成 + status: pending、既存 → 取得のみ、blocked → 例外
  - `HandleIncomingLineMessage`: pending → ApprovalRequest 起票、active → Telegram へ転送、blocked → 即破棄
  - `RequestApprovalFromPrincipal`: pending_approval に書き込み、principal の telegram_chat_id へ push 依頼
  - `RelayFromWeave`: mux タグ解析→user_uuid 解決→LINE push、未知 mux タグでエラー、blocked user 宛で拒否
  - `ListActiveUsers`: フィルタ + 整形（最終接触日降順）
  - `LinkAccounts`: 既存 user_uuid に別チャネル ID 追加、衝突時エラー
  - `UpdateIdentity`: 部分更新、tone 不正で拒否、principal 以外の呼び出しで拒否
  - `BuildDailySummary`: 過去24h の thread / approval / 重要案件を集約、空時の挙動
  - 関係者間共有: identity.shared_with にない相手への共有試行は拒否、追加後は許可
**Implementation Notes**: Port 定義は Protocol（typing）または ABC。DI で組み立て。Claude 推論は Port にしない（Bridge は LLM を持たない）。
**Status**: Not Started

## Stage 3: Interface Adapters（LINE / Redis / Telegram Relay）
**Goal**: 実 LINE API・Redis・Telegram 中継の実装。HTTP はモックでテスト。
**Layer**: Interface (Adapter)
**Success Criteria**: push/reply/profile/署名検証、Redis round-trip、Telegram への内部送出が green。
**Tests** (Red → Green):
  - `LineApiGateway.push_message(user_id, text)`: 正常 200 / 401 → auth エラー / 429 → リトライ後失敗
  - `LineApiGateway.get_profile(user_id)`: 200 → display_name 取得、404 → None
  - `RedisUserStore`: user 主レコード + 逆引きインデックスの round-trip、破損 JSON フォールバック
  - `RedisIdempotencyStore`: setnx 成功 → True、既存 → False、TTL 設定確認
  - `TelegramRelayClient`: Cloud Routine 側 TelegramSecretary が公開する API に Bearer 認証で投稿（または Telegram bot に直送、Stage 5 で確定）
**Implementation Notes**: `httpx` 非同期クライアント。Redis は `redis-py` async。LINE SDK は薄く使うかフルスクラッチか Stage 着手時に決定（薄ラッパー哲学に従えば直 httpx で十分）。
**Status**: Not Started

## Stage 4: Infrastructure + Railway デプロイ + cron
**Goal**: FastAPI app の配線、env 設定、Railway デプロイ、日次サマリ cron。
**Layer**: Infrastructure
**Success Criteria**: Railway 上で `/webhook/line` が公開 HTTPS で疎通、`/healthz` が 200、cron で日次サマリトリガが発火、env が全て揃わないと起動失敗。
**Tests** (Red → Green):
  - `config.py` が env 欠損で起動失敗（fail-fast）
  - LINE Developers Console で webhook URL を `https://<railway-domain>/webhook/line` に設定 → 検証ボタンで 200
  - 自分の LINE OA に test 送信 → Bridge ログに event 到達確認
  - cron スケジュール 09:00 JST 確認（Railway cron アドオン または APScheduler 内蔵）
**Required env vars**:
  - `LINE_CHANNEL_SECRET`（署名検証用）
  - `LINE_CHANNEL_ACCESS_TOKEN`（push/reply 用）
  - `REDIS_URL`
  - `INTERNAL_API_BEARER_TOKEN`（Cloud Routine からの呼び出し認証）
  - `TELEGRAM_BOT_TOKEN`（Telegram への中継、TelegramSecretary と共有 or 専用 bot 別建て＝Stage 5 で判断）
  - `TELEGRAM_WEAVE_CHAT_ID`（mux 転送先）
  - `PRINCIPAL_LINE_USER_ID` / `PRINCIPAL_TELEGRAM_CHAT_ID`（principal 識別用、初期固定）
  - `DAILY_SUMMARY_TIME_JST`（既定 `09:00`）
**Implementation Notes**: SpiritualAdvisor の Railway プロジェクトに新サービス追加。Procfile or railway.toml で `uvicorn main:app` 起動。Redis アドオン新規付与。secret は env のみ、コード/コミット禁止。
**Status**: Not Started

## Stage 5: E2E + 未確定点の決定 + ドキュメント
**Goal**: 承認フロー / 通常応答 / リレー / 日次サマリ / `/list` の E2E、TelegramSecretary との結合方式確定、運用ドキュメント。
**Layer**: Infrastructure（運用統合）
**Success Criteria**: 
  - friend 追加 → 大環主に approve 依頼 → 承認 → 初回応答送達まで E2E
  - active 関係者から複数往復で会話成立
  - 重要度 high 案件で大環主にも即時 push される
  - `/relay <uuid> <text>` で関係者へ正しく届く
  - 関係者間共有で承認なし → 拒否、承認あり → 配信
  - 09:00 JST に日次サマリが大環主の Telegram に届く
  - `/list` で関係者一覧が読みやすい形で返る
**Stage 5 着手前に確定済みの決定事項**:
  - **TelegramSecretary との結合方式**: **B. 共通 Telegram bot 共有を採用**。Bridge は `sendMessage` API のみ叩く **send only 制限**（`getUpdates` は呼ばない）。これにより bot token を Bridge も保持するが、polling 競合は構造的に発生しない。`A. internal API 単独`は Bridge → Weave 方向が成立しないため却下。`C. 専用 bot 別建て`は規模拡大時の Reversibility として保留（bot token を Bridge 側で差し替えれば移行可能）
  - **承認 UX**: **LINE Quick Reply / Postback + Telegram インライン キーボードの両方を実装**。大環主が片方しか開いていない場面でも承認できるようにする。Bridge は `/internal/approval-callback` を統一受け口として LINE/Telegram 双方の承認結果を受ける。関係者には承認後に「Weave からご返信できるようになりました」の自動メッセージで結果通知
  - **`/share` の取り消し**: `/list-shares` で現在の許可一覧を確認、`/unshare <from_uuid> <to_uuid>` で削除——2 コマンドで完結
**残った未確定点**:
  - `/secretary` メニューのレイアウト詳細（カラム数、ボタンラベル文言）は Stage 5 で運用しながら微調整
**Implementation Notes**: 親 TelegramSecretary IMPLEMENTATION_PLAN.md の Stage 5（環境実測）と並行可能。Bridge 単体テストは Railway 上の dev サービスで先に通す。
**Status**: Not Started

## Documentation Plan

### 基本セット
| ドキュメント | パス | 新規/更新/不要 | 計画内容 |
|---|---|---|---|
| `README.md` | `Expertises/TelegramSecretary/LineBridge/README.md` | 新規 | サービス概要・env vars・Railway デプロイ手順・LINE OA 取得手順 |
| `CHANGELOG.md` | `Expertises/TelegramSecretary/LineBridge/CHANGELOG.md` | 新規 | Stage 単位の変更履歴 |
| `IMPLEMENTATION_PLAN.md` | （本ファイル） | 新規 | 全 Stage 完了後に削除 |

### 拡張レイヤー
| ドキュメント | パス | 新規/更新/不要 | 理由 |
|---|---|---|---|
| 親 `IMPLEMENTATION_PLAN.md` | `Expertises/TelegramSecretary/IMPLEMENTATION_PLAN.md` | **更新** | LineBridge 受け口（User DB スキーマ拡張、`/list` `/link` `/edit-user` 等 subcommand、`/internal/*` 呼び出し）を追記 |
| `SKILL.md` | `Expertises/TelegramSecretary/LineBridge/SKILL.md` | 新規 | サービスマニフェスト（Endpoints / Failure Modes / Health） |
| `CLAUDE.md`（root） | `./CLAUDE.md` | 更新 | TelegramSecretary 配下に LineBridge があることを Expertises 一覧に追記 |
| LINE OA 運用手順 | `Expertises/TelegramSecretary/LineBridge/docs/LINE_OA_SETUP.md` | 新規 | Business ID 取得・Messaging API 有効化・channel secret/token 取得手順 |

## Decision Priority Notes（Testability > Readability > Consistency > Simplicity > Reversibility）

- **LLM を Bridge に持たない**（最大の分岐）: 応答生成を Weave 本体（Telegram 経由）に完全委譲。Testability（UseCase が fake で完結）・Simplicity（決定論的世界の純化）・L00456 三世界分類の整合 が一致して勝つ。
- **reply API vs push API**: reply token 1 分制約で複雑化を避けるため、**push 基本・reply は補助**で統一。料金面でも push の方が予測可能。
- **mux 方式**: A. metadata プレフィックス採用（簡素、MVP 向き）。B. Telegram Forum chat への移行は規模拡大時の Reversibility として残す。
- **identity 更新責任**: MVP は大環主手動（`/edit-user`）。Weave 自動学習は後段の機能拡張として Reversibility 確保。
- **Telegram bot 共有方式 (B 採用)**: Bridge は **send only**（`sendMessage` のみ）。`getUpdates` は Cloud Routine 側 TelegramSecretary のみ呼ぶ。Bridge は polling せず、Weave からの内部 API 経由でのみ Telegram へ push。これで token 共有のリスクは「漏洩時の偽通知」のみに収束し、polling 競合は構造的に不可能。Consistency（TelegramSecretary との結合）と Simplicity（bot 1個）で勝つ。
- **マスタースキル `/secretary`**: 個別コマンドの記憶負担を大環主から外す UX。インライン キーボードで全操作にアクセス、慣れた利用者は直接コマンドでショートカット可能。Readability（操作の自己説明性）と Reversibility（個別コマンドは残るので併存可能）で採用。
- **ホスティング**: Railway 相乗り（SpiritualAdvisor 既存資産活用）。別建て (Cloudflare Workers, Fly.io) への切替は Stage 4 以降で容易（FastAPI app の移植性高い）。

## 3-Strike Rule

- **詰まりやすい予想ポイント**:
  1. **Weave 応答時間 > LINE reply token 1 分**: push API 基本化で構造的に回避済み、ただし「確認中です」自動応答の UX 設計で躓く可能性
  2. **Cloud Routine ↔ Bridge の双方向通信**: Bridge から Cloud Routine への push は不可（inbound 制約）。Cloud Routine 側が Bridge にポーリングする or Telegram bot 経由で受ける、の二択。後者を採用するなら TelegramSecretary 側のメッセージハンドラに「Bridge 由来」識別ロジックが必要
  3. **承認 UX の対話設計**: LINE Quick Reply の制約 vs Telegram インライン キーボードの自由度——後者推奨だが、principal が外出先で LINE しか開かない場合の retreat path
- **代替アプローチ候補**:
  - reply API でうまくいかない場合: push 完全化、料金影響を見て LINE 公式アカウントプラン見直し
  - Cloud Routine 双方向: TelegramSecretary が `watch` ループ内で Bridge の Telegram bot メッセージを区別して処理（mux タグで判別）
  - 承認 UX: principal にも Telegram メイン化を依頼、LINE 経由承認は禁止 UI（「承認は Telegram で」と返す）
- **ユーザーへ相談する判断ライン**: 上記いずれかで MVP 実装が 1 週間止まった時点で、`AskUserQuestion` で構造的選択肢を提示。

## セキュリティ（OPS.md §1・§7、SecretaryRole 前提で必須）

- **webhook 署名検証** — X-Line-Signature を HMAC-SHA256 で検証、失敗即 400、ログに署名は残さない
- **idempotency** — `webhookEventId` で dedup（TTL 1h）、二重応答を構造的に防止
- **principal vs associate の権限分離** — `/list` `/approve` `/block` `/edit-user` 等の管理コマンドは principal のみ
- **関係者間プライバシー境界** — identity.shared_with に基づく明示的許可制、未承認の relay 試行は拒否＋大環主へ承認伺い
- **プロンプトフェンシング** — LINE 受信本文を Telegram 転送前に XML タグで隔離し「データとして扱え」を明示
- **injection フラグ**（ブロックせず記録）・**出力漏洩スキャン**（LINE 送信前に token/env名/system prompt 混入チェック）
- **レート制限** — line_user_id 単位 sliding window（DoS & コスト暴走対策）
- **Bearer token (Internal API)** — Cloud Routine から Bridge への呼び出しは Bearer 認証、token は env、平文ログ禁止
- **Telegram bot token の共有制限** — Bridge は **send only**（`sendMessage` のみ）、`getUpdates` は呼ばない。Redis または起動時 assertion で「Bridge は polling 禁止」を構造的に強制。これで bot token 共有のリスクは漏洩時の偽通知のみに収束、polling 競合は構造的に不可能
- **承認 callback の認証分離** — `/internal/approval-callback` は LINE 側（X-Line-Signature 検証）と Telegram 側（Bearer token + callback_query 検証）で経路を分けて受ける。両者を Domain の `ApprovalDecision` に正規化してから処理
- **secrets は env のみ** — channel secret / access token / bearer token をコード/コミットに置かない
- **identity 自由記述の取り扱い** — context_notes に PII が入る前提、Redis アクセス権限を最小化、Railway 環境の access control を確認

## TelegramSecretary 本体への波及（親 IMPLEMENTATION_PLAN.md への追記事項）

LineBridge 採用に伴い、親計画には以下を追記する：

1. **Domain `User` 値オブジェクト**: identity 層と両アカウント属性 (line_user_id / telegram_chat_id) を含む集約ルートとして再設計
2. **Subcommands 追加**: `secretary`（マスタースキル、インライン キーボードでメニュー） / `list` / `pending` / `approve` / `block` / `edit-user` / `link` / `share` / `list-shares` / `unshare` / `relay`
3. **Bridge との通信 Port**: `BridgeRelayPort`（mux タグ付きメッセージを `/internal/relay-to-line` に POST、Bearer 認証）
4. **mux タグ解析・付与**: Telegram メッセージの先頭/末尾 `[from:line:X]` `[to:line:X]` `[relay-to:line:X]` を Domain の `MuxTag` で安全にパース・ビルド（インジェクション防御）
5. **承認 UX 双方向対応**: Telegram インライン キーボード（`callback_query` 受信）と LINE 由来承認の両方を扱う。LINE 由来は Bridge 側 `/internal/approval-callback` で受けて TelegramSecretary に転送
6. **prompt 強化**: SecretaryRole プロンプトに「identity 参照（tone/honorific/taboo_topics 反映）」「重要度判定」「エスカレ判定」「共有候補判定」「`/secretary` 受信時のメニュー応答」を追記

これらは TelegramSecretary Stage 1〜2 完了後、Stage 3 着手前に親計画へ反映する（実装互換性確保のため）。
