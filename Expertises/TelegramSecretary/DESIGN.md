# TelegramSecretary 設計正典（DESIGN）

設計の **why** を集約する。役割分担 — **DESIGN**=なぜこの設計か / **STRUCTURE**=どこに何を置くか / **IMPLEMENTATION_PLAN**=どう作るか / **DOCUMENTATION_PLAN**=ドキュメント整備の how/when。

## 1. 設計原則

- **秘書＝入力理解優先**: 大環主の業務入力（voice / 写真 / 文書）の「受信＋中身理解」が一次価値
- **双方向性の最小成立**: 出力（送信）は file 送信で双方向が完成する。対話 UX 装飾は選択的
- **LLM 推論はコード外**: 応答生成・判断は親プロセス Weave、コードは決定論的な fetch / render / send / 管理表 I/O のみ（L00473）
- **テンプレート/データ分離**: 配布可能性のため、コード・雛型（public）と実データ・人格（Private）を物理分離する
- **決定論コア + Weave 判断の分離**: 三世界分類（L00456）に基づき、スキーマ・I/O・archive はコード、判断は Weave
- **加算バイアス回避**: 公式が持つ機能でも設計目的に不要なら入れない（YAGNI）。必要になった時点で埋める

## 2. アーキテクチャ（Clean Architecture 4層）

```
Infrastructure → Interface(Adapter) → UseCase → Domain
              依存方向: 外から内へのみ（Domain は外層を import しない）
```

| Layer | 責務 | 例 |
|---|---|---|
| **Domain** | 純粋ロジック・値オブジェクト | `TelegramUpdate` / `OutboundMessage` / `Individual` / `Task` / `Knowledge` / `MediaAttachment` / 正規化・injection フラグ |
| **UseCase** | オーケストレーション + Port 定義 | `FetchAuthorizedUpdates` / `SendReply` / 管理表 CRUD UseCase / Ports（`UpdateSource`・`MessageSink`・`OffsetStore`・各 `*Store`） |
| **Interface (Adapter)** | ゲートウェイ・ストア・CLI | `TelegramApiGateway` / `JsonStateStore` / `Json*Store`（管理表）/ `StdoutEventEmitter` / `main.py` |
| **Infrastructure** | 外部・フレームワーク | `bootstrap.sh` / `watch_loop.sh` / `config` / `archive_rotate.py` |

### 三世界分類との対応（L00456）

| 世界 | LLMへの投入 | 該当 |
|---|---|---|
| **決定論的世界** | 投入しない（コード管理） | scripts 全般 — fetch / 認可 / 正規化 / 送信 / render / 管理表 I/O / archive・分割 |
| **重要度の世界** | 質の良い長文 | Weave の人格（WeaveIdentity）+ SecretaryRole。応答起草・CRUD 判断・エスカレ判断 |
| **従属度の世界** | 目的と前提のみ | ROUTINE_PROMPT（手順を委任） |

**設計線**: 「何を保存するか（スキーマ）・どう保存するか（I/O）・いつ分割するか（archive）」は決定論的世界。「誰を active にするか・何を KNOWLEDGE に残すか・どう応答するか」は重要度の世界（Weave）。この境界が管理表設計の背骨。

**keep-alive の三世界対応（Stage 10 / D）**: 「watch の窓満了・メッセージ駆動 exit（`WatchWindow` / `--max-duration` / `--exit-on-message`）」と「deadline 計算」は決定論的世界（コード + bash 算術、テスト可能）。「`/goal` で deadline まで各ターン watch を回し返信を起草する」運用は従属度の世界（ROUTINE_PROMPT に委任）。停止主軸を時刻（deadline）に置きポーリング回数を LLM 判断から切り離したのは、決定論をコードに寄せる本設計線の踏襲。詳細は [`GOAL_KEEPALIVE_PLAN.md`](./GOAL_KEEPALIVE_PLAN.md)。

## 3. データアーキテクチャ（管理表 + Identities）

### 3.1 二系統のデータ

- **管理表（事実データ）**: `INDIVIDUALS`（関係者）/ `TASKS`（依頼進捗）/ `KNOWLEDGE`（対応知の蓄積、判例DB的）
- **Identities（人格定義）**: `SecretaryRole` — **これが無いとエージェントが人格的に振る舞えない**。織守 BlueberrySprite の `HatoriRole.md` と同型

### 3.2 なぜ SSoT = Private JSON か

- **Private**: 関係者情報・依頼・人格はすべて個人資産。配布物（public コード）に焼き込めば、Phase B で他人の手に渡る。物理分離が必然
- **JSON**: Weave が後から必要に応じてスキーマを改変できる柔軟性。固いスキーマ言語より、判断主体（Weave）が触れる形式が適切
- **単一正典**: LineBridge 採用時の Redis は JSON のミラー（一方向 JSON→Redis）。チャネルを増やしても正典は1つ＝二重管理の破綻を防ぐ

### 3.3 なぜテンプレート/データ分離か（配布可能性の核心）

`templates/`（public、雛型）と実体（Private）を分ける。Phase A（個人利用）の初日からこの分離を徹底すれば、Phase B（plugins-weave バンドル）は「marketplace.json に1エントリ追加 ＋ Private を外す」だけで済む。**配布可能性を個人利用の構造に最初から埋める**。Identities（人格）も同じ — 雛型は public、大環主の SecretaryRole 実体は Private。

### 3.4 なぜ CRUD はエージェント主体 + `/secretary` ラップか

- **操作主体 = エージェント**: Weave/SecretaryRole が対話の文脈で「この人を active にする」「この判断を KNOWLEDGE に残す」と判断して CRUD（重要度の世界）
- **決定論 I/O = CLI subcommand**: 実際の書き込みは決定論的世界（テスト可能）。Weave は subcommand を呼ぶ
- **ユーザー向けにも解放**: skill / slash command として操作インターフェースを公開（人間が直接操作も可能）
- **`/secretary` で全ラップ**: マスタースキルが管理パネルとして全操作の入口。コマンド名を覚えずとも操作可能（LineBridge plan の `/secretary` 構想と統合）

### 3.5 なぜ肥大化対策が管理表ごとに違うか

| 管理表 | 方式 | 理由 |
|---|---|---|
| **TASKS** | 日付 Archive（done が N 日経過） | 完了タスクは「過去ログ」が自然。時系列で流れる |
| **INDIVIDUALS** | 日付 Archive（blocked + 長期非接触） | 離脱者は稀に過去ログ化 |
| **KNOWLEDGE** | **カテゴリ分割**（Archive せず） | 知識は**蓄積が本質**（判例DBは古いから捨てない）。肥大化は category 単位のシャード分割で解く（BusinessCurator wiki 同型） |

詳細スキーマ・ディレクトリ配置は [STRUCTURE.md](./STRUCTURE.md)、整備手順は [DOCUMENTATION_PLAN.md](./DOCUMENTATION_PLAN.md) を参照。

---

## 4. Scope: 公式 plugin（/channels）との差分と採否

Claude 公式の Telegram plugin（`/channels`）と比較した機能採否の記録。**「公式にあるから移植する」ではなく、設計目的に照らして選択的に実装する**ための参照点（加算バイアスへの歯止め）。

凡例 — 実装: ✅ 済 / ❌ 未 / ❌(静的) 静的代替 ｜ 要否: ◎必須 ○有効 △低優先 ✕不要

| 機能 | 公式 tool | 用途 | TS 実装 | 要否 | 採否理由 |
|---|---|---|---|---|---|
| 画像/ファイル送信 | `reply(files)` | 生成物（図表/レポート/docx）を送り返す | ✅ Stage 8 | ◎ | write 系の中核。拡張子で sendPhoto / sendDocument に自動振り分け、`--file` 複数可 |
| typing インジケータ | `sendChatAction` | 応答までの数秒ラグの UX 緩和 | ✅ Stage 8 | ○ | stateless 軽量、`send_chat_action` を best-effort で送信前に発火 |
| reply threading | `reply_to` | どの発言への返信か明示 | ✅ Stage 8 | ○ | `reply_to_message_id` は Domain に既存、`--reply-to` 配線で完成（ほぼ無コスト） |
| **受信メディアの中身理解** | （公式になし） | voice/audio/video→transcript、docx/pptx/xlsx→markdown | ✅ Stage 6/7/9 | ◎ | **TS が公式を超越する強み**。公式は file_id forward + download 止まりで中身を読まない |
| 絵文字リアクション | `react` | 軽い ack（既読スタンプ） | ❌ | ✕ | 返信本文の UTF-8 絵文字（七曜インジケータ等）で代替可。さらに **1:1 DM では bot が管理者になれず inbound reaction も構造的に受信不可** |
| 送信済み編集 | `edit_message` | 長時間タスクの進捗更新 | ❌ | ○ | 効用はあるが、`message_id` の状態管理を stateless 設計に持ち込むため見送り。必要なら独立 Stage |
| markdownv2 整形 | `format` | 見出し / 強調 | ❌ | △ | MarkdownV2 は `_*[]()~>#+-=\|{}.!` 全エスケープ要で送信失敗リスク。後付け容易ゆえ YAGNI 保留 |
| pairing 認可 | access skill | 利用者を実行中に動的承認 | ❌(静的) | ✕ | 静的 allowlist（`AUTHORIZED_CHATS`）で十分。**動的承認は LineBridge の `ApproveUser`/`pending-users` で計画**（LINE 関係者を増やす場面用） |
| bot commands | `setMyCommands` | `/` 入力でコマンド候補を表示 | ❌ | △ | 自然文で Weave に話しかける対話型が主。コマンド体系を前面に出さない |
| sticker 受信認識 | （受信側） | sticker を認識 | ❌ | △ | inbound 拡張。Stage 6/9 系で必要になれば追加 |
| group @mention | group policy | グループで `@bot` 呼び出し（privacy mode） | ❌ | ✕ | 1:1 DM（大環主との個人チャット）前提。グループ運用は想定外 |

### 構造的要約

「公式にあって TS にない」機能は**送信側 UX 装飾**に偏り、「TS にあって公式にない」機能は**受信の中身理解**（voice/docx の transcript/md 化）に集中する。この非対称が、設計思想「秘書の価値は read 系」の裏返しとして表に出ている。

整理すると——**pairing は「誰を入れるか」、commands は「何ができるかの提示」、group は「どこで聞くか」**。TS は「大環主と少数の関係者が、1:1 で、自然文で呼ぶ」運用に絞るため、これら3つは現状不要か LineBridge 側に寄せている。

### 今後の判断指針

- 残った穴（`edit_message` / `bot commands` / `sticker` 認識）は、運用で実際に欲しくなった時点で埋める。「公式にあるから」を理由に先回り実装しない
- `pairing` 相当の動的承認は LineBridge 側（`LineBridge/IMPLEMENTATION_PLAN.md`）に寄せる
- 採否が変わったら（例: `edit_message` を独立 Stage で実装）、本表を更新する
