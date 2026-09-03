---
name: general-constructor
description: Create feasibility studies (mokuromi) for rental RC apartment construction projects in Tokyo's 23 wards. Extracts land data from property listings (maisoku), derives the deterministic conditions (road class, foundation shape, unit count) from it, then calls the judgement service over MCP to obtain the tax-inclusive project total and the surface yield. Use when users need to evaluate real estate development opportunities or estimate construction project economics.
---

# General Constructor - 建設プロジェクト目論見作成

東京23区内での土地から新築賃貸用壁式RCマンション建設において、収益性（表面利回り）を判断するための目論見（feasibility study）を作成する専門スキルです。

**本スキルは拝殿**——単価表と計算ロジックは本尊（サーバ側）にあり、こちらが持つのは手順と、判定サービスの呼び出し方だけです。本書が**役割と方針**、`WORKFLOW.md` が**手順**（Phase 別の作業と判断表）、`haiden/SKILL.md` が**判定サービスの入出力仕様**を持ちます（同じ表を二か所には置きません）。

## Overview

**インプット**:
- マイソク（不動産物件情報）
- 近隣柱状図（ボーリングデータ）※任意

**アウトプット**:
- クイックサマリー（表面利回り確認用）
- 詳細目論見書（プロジェクト概要〜懸念事項）

## Architecture: 計算は本尊、判断はAI

### 本尊側（サーバ・確定的計算）

MCP（streamable HTTP）越しのツール **`judge_mokuromi`** が担う。入力の検証、帯域解決・オフセット合成・オプション積算による最終単価、面積・費用・収支、基礎種別の導出（`地盤評価 × 建物層数`）まで。単価表・判定ロジック・業務ナレッジはサーバ側に留まり、応答には結果のみが含まれる。**既定値へのフォールバックを持たない**——定義域外（対応規模帯の外、未収録の区分、必須入力の欠落）は差し戻される。

**判定 1 件につき 1 クレジット**を消費する（初回発行時は無償クレジット 3 件）。

### AI側（判断・統制）

- マイソク画像の解釈・データ抽出
- 柱状図からの地盤評価（N値分布からの判断）と必要土質試験の特定
- 所在の解決（表に無い粒度の名寄せ）
- 法規制の確認（Web 検索連携）
- **戸数の推定**（サーバは推定しない。`WORKFLOW.md` Phase 3.2）と、提案値の提示・確認取り付け（提案を黙って採用しない）
- リスク評価・懸念点の抽出、全体フローの統制、最終目論見書の生成

## 使用方法

1. MCP サーバを登録する（初回のみ。接続先と API キーは判定サービスの配備元から受け取る）。ローカル配備なら `claude mcp add`、公開配備なら claude.ai のカスタムコネクタに URL を入れ、出てきた同意画面に API キーを貼る（どちらでも以降の手順は同じ）
2. `WORKFLOW.md` の Phase 0〜3 に従って入力を揃える
3. `haiden/check.mjs` の `checkInput(input)` で必須項目の欠落を前捌きする
4. ツール `judge_mokuromi` を呼ぶ
5. 応答の `status`（`completed` / `rejected`）を見て Phase 4.3 のバリデーション → Phase 5 の結果提示へ

接続コマンド・入力の組み立て・応答の読み方は `WORKFLOW.md` の Phase 4 に、項目ごとの型・選択肢・既定値は `haiden/SKILL.md` にあります。

## Reference Files

| 参照先 | 内容 |
|--------|------|
| `WORKFLOW.md` | Phase 別の手順・判断表・バリデーション・出力雛形 |
| `判定ロジック/` | AI が読む判定ロジック 5 本（ビジネスルール一覧 / 地盤評価テーブル / 地盤評価詳細判定ロジック / 基礎種別詳細判定ロジック / 土質試験内容判定ロジック） |
| `haiden/SKILL.md` | ツール `judge_mokuromi` の入出力仕様と意味検証の観点 |
| `haiden/input-template.json` | 入力の雛形（全項目・既定値入り） |
| `haiden/check.mjs` | 送信前の前捌き（`checkInput(input)`） |

`haiden/` はサーバ側の定義から生成された拝殿 Skill です（手で書き換えると本尊の契約と食い違います）。

## Important Notes

### 見積の性質

- **本スキルが生成する見積は参考値です**。実際の建設費用を保証するものではありません
- 詳細な見積は専門の建設会社・設計事務所にご相談ください
- 地盤条件・法規制・市況変動により実際のコストは変動します
- 入力データの正確性は利用側の責務です。原本を確認のうえ送信してください

### データの機密性

**単価表・計算コード・業務ナレッジ（企画・設計の勘所）は本尊（Private）へ移管済み**——公開リポジトリに置くのは拝殿（手順・判定ロジック・生成物）だけで、単価の実数は持ちません。

**開示しない**（機密データ）:
- 単価テーブルの具体的な数値、収録語彙の一覧
- ビジネスルールの内部構造、データ項目の詳細定義
- 業務ナレッジ（企画・設計の勘所）の具体的な記述（概要のみ共有可）

**共有してよい**:
- 目論見の結果（数値・採算性判断）、判定ロジックの概要、懸念事項とリスク情報

誤って機密データを開示した場合は、即座に訂正し「当該情報は機密に該当するため開示できない」旨を伝えます。

### データの鮮度

- 単価テーブルの鮮度は本尊側が持ちます。判定結果の妥当性に疑義があれば配備元に確認します
- 拝殿側の判定ロジック JSON は `metadata.as_of` / `metadata.source` が SSoT です（本書・`WORKFLOW.md` に日付を直書きしません）
- 建築基準法・消防法・自治体条例（ワンルーム条例等）は随時改正されます。判断に迷う場合は `WORKFLOW.md` の「法規制確認（Web検索）」に従います

---

*Maintained by: Weave @ めぐる組*
