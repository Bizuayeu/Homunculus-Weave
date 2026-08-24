---
name: general-constructor
description: Create feasibility studies (mokuromi) for rental RC apartment construction projects in Tokyo's 23 wards. Extracts land data from property listings (maisoku), derives the deterministic conditions (road class, foundation shape, unit count) from it, prices construction from banded per-square-metre tables plus option add-ons, and reports the tax-inclusive project total together with the surface yield. Use when users need to evaluate real estate development opportunities or estimate construction project economics.
---

# General Constructor - 建設プロジェクト目論見作成

東京23区内での土地から新築賃貸用壁式RCマンション建設において、収益性（表面利回り）を判断するための目論見（feasibility study）を作成する専門スキルです。

本書が**仕様**（入出力・アーキテクチャ・運用方針）、`WORKFLOW.md` が**手順**（Phase 別の作業と判断表）を持ちます。

## 目次

- [Overview](#overview)
- [Architecture: 計算はPython、判断はAI](#architecture-計算はpython判断はai)
- [入力仕様（ProjectInput）](#入力仕様projectinput)
- [出力仕様（ProjectOutput）](#出力仕様projectoutput)
- [使用方法](#使用方法)
- [Reference Materials](#reference-materials)
- [Important Notes](#important-notes)

## Overview

**インプット**:
- マイソク（不動産物件情報）
- 近隣柱状図（ボーリングデータ）※任意

**アウトプット**:
- クイックサマリー（表面利回り確認用）
- 詳細目論見書（プロジェクト概要〜懸念事項）

**単価モデル**（めぐる標準単価表・修正版）:

```
ベース㎡単価 = 施工床面積の帯域基準値 + 道路区分オフセット + 基礎形状オフセット + 住宅種別オフセット
最終㎡単価   = (ベース㎡単価 × 施工床面積 + オプション合計) ÷ 施工床面積
工事代金     = 建物価格（施工床面積 × 最終㎡単価） + 杭費用 + 解体費用
建設経費     = 工事代金 × 建設経費率
PJ総額       = 土地価格 + 工事代金 + 建設経費
表面利回     = 年間売上 ÷ PJ総額（目標利回テーブルと同じ基準）
```

**単価表の数字は税込**です（2026-08-24 裁定）。金額は全て税込で通し、`×1.1` の税込併記は行いません。

条件は単価そのものに焼き込まれており、**乗算係数を持ちません**（旧モデルの補正係数による乗算は退役。経緯は `CHANGELOG.md`）。基礎・山留は㎡別建てをやめてベース単価へ内包し、杭のみ `杭費用` として別建てします。率・面積の定数は `python/data/定数.json` が SSoT で、コードにも本書にも実数を持ちません。

## Architecture: 計算はPython、判断はAI

本スキルは「計算」と「判断」を明確に分離しています。

### モジュール構成

```
python/
├── main.py           # Interface: dict ⇄ モデル変換・CLI・エラー整形
├── calculator.py     # UseCase: 面積・費用・収支のオーケストレーション
├── inference.py      # UseCase: 決定論的な判定ルール（WORKFLOW Phase 3.2 と 1 対 1）
├── pricing.py        # Domain: 帯域・オフセット・オプションの単価モデル（純粋関数）
├── loader.py         # Infrastructure: JSON テーブル読み込み（必須テーブル欠落は fail-fast）
├── data/             # 単価テーブル・判定ロジックの JSON 群（一覧は WORKFLOW.md）
└── schema/
    ├── models.py     # 入出力モデル（ProjectInput / ProjectOutput）
    └── tables.py     # テーブル型定義
```

依存は外から内へのみ（`pricing.py` と `inference.py` は `loader` / `main` を import しません）。単価計算の芯は将来そのまま持ち出せる境界として切ってあります。

### Python側（確定的計算）

- 入力バリデーション（pydantic。`extra="forbid"` により退役キーは黙って無視せず検証エラー）
- 帯域解決・オフセット合成・オプション積算・最終㎡単価（`pricing.py`）
- 決定論的な判定ルール（`inference.py`）
- 面積・費用・収支の計算（`calculator.py`）
- **既定値へのフォールバックを持たない**: テーブルに該当行が無ければ `TableLookupError`、定義域外（帯域外・未知の区分・必須入力の欠落）は `PricingDomainError`

### AI側（判断・統制）

- マイソク画像の解釈・データ抽出
- 柱状図からの地盤評価（N値分布からの判断）と必要土質試験の特定
- 所在の解決（貸床単価テーブルのエリア判定など、表に無い粒度の名寄せ）
- 法規制の確認（web_search 連携）
- `inference` が返した**提案値の提示と確認取り付け**（提案を黙って採用しない）
- リスク評価・懸念点の抽出、全体フローの統制、最終目論見書の生成

## 入力仕様（ProjectInput）

| 項目 | 型 | 必須 | 値域 / 既定 |
|------|----|------|------------|
| 土地価格 | int | ✓ | 万円 |
| 土地所在 | str | ✓ | 区名（貸床単価テーブルに載る表記） |
| 有効宅地面積 | Decimal | ✓ | ㎡ |
| 前面道路幅員 | Decimal | ✓ | m（道路区分の判定に使う） |
| 古家構造 | str | ✓ | 無し / 木造 / 鉄骨造 / RC造 / その他 |
| 解体面積 | Decimal | - | ㎡（既定 0） |
| 実効建蔽率 | Decimal | ✓ | %（耐火建築物緩和込み。計算内で 70% を上限） |
| 用途地域 | str | ✓ | |
| 高度地区 | str | - | |
| 最大容積率 | Decimal | ✓ | % |
| 住宅種別 | str | ✓ | 長屋 / 共同住宅 |
| 建物層数 | int | ✓ | 3 / 4 / 5 / 6 |
| 戸数 | int | ✓ | 戸（`estimate_units` の推定値を確認してから入れる） |
| 半地下有無 | str | ✓ | 半地下有 / 半地下無 / 全地下 |
| EV | str | - | 無（既定）/ 6人乗り / 9人乗り / 家庭用 |
| 地盤評価 | str | ✓ | 硬質地盤 / 中間地盤 / 中間地盤① / 中間地盤② / 軟弱地盤 |
| 基礎種別 | str | - | override。無ければ 地盤評価 × 建物層数 から写す |
| ソイル | str | - | 無（既定）/ 通常 / 悪条件 |
| 外周長 | Decimal | △ | m。**ソイル≠無 のとき必須**（既定値を置かない） |
| 防音室数 | int | - | 室（既定 0） |
| レコリード | str | - | 無（既定）/ 床のみ / 部屋ごと |
| ペット | str | - | 無（既定）/ 2点 / 4点 |
| 自火報 | bool | - | 既定 false |
| 調査費 | bool | - | 既定 true（地盤調査・測量・家屋調査の 3 点） |
| 一層二戸 | bool | - | 既定 false |

- 中間地盤①/② は入力で受け、テーブル参照時に「中間地盤」へ**明示的に**写します。
- 退役キー（`搬入経路` / `道路種別` / `接道長さ` / `壁率` / `設備率` / `グレード` / `EV有無`）を渡すと検証エラーになります。`接道長さ` は住宅種別の判定引数としてだけ残っており、計算 API へは渡しません（WORKFLOW Phase 3.2）。

## 出力仕様（ProjectOutput）

| 項目 | 型 | 単位 / 意味 |
|------|----|------------|
| 建築面積 / 共用部面積 / 地下緩和面積 / 最大施工面積 / 施工面積 | Decimal | ㎡ |
| 基礎種別 | str | 地盤評価 × 建物層数 の結果（override 時は入力値） |
| 道路区分 | str | 2.5m以下 / 2.5〜8m / 幹線・バス通り |
| 帯域 | str | 施工床面積が属する建築単価帯域 |
| ベース単価 | Decimal | 万円/㎡ |
| オプション内訳 | dict | 名称 → 万円（万円未満を保持。適用外・数量 0 の行は含まない） |
| 最終単価 | Decimal | 万円/㎡（ROUND_HALF_UP 小数 2 桁） |
| 解体費用 / 杭費用 / 建物価格 / 工事代金 / 建設経費 | int | 万円 |
| PJ総額 | int | 万円（税込。単価表が税込なので ×1.1 はしない） |
| 貸床面積 | Decimal | ㎡ |
| 貸床単価 | int | 円/㎡ |
| 年間売上 | int | 万円 |
| 表面利回 / 目標利回 | Decimal | %（表面利回は PJ総額ベース） |

## 使用方法

### 関数として

```python
from python.main import run_calculation

result = run_calculation({
    "土地価格": 6980,
    "土地所在": "板橋区",
    "有効宅地面積": "109.40",
    "前面道路幅員": "7.5",
    "古家構造": "無し",
    "解体面積": "0",
    "実効建蔽率": "70",
    "用途地域": "第1種住居地域",
    "最大容積率": "200",
    "住宅種別": "共同住宅",
    "建物層数": 4,
    "戸数": 8,
    "半地下有無": "半地下有",
    "EV": "無",
    "ソイル": "無",
    "調査費": True,
    "地盤評価": "中間地盤",
})

print(f"最終単価: {result['最終単価']}万円/㎡")
print(f"PJ総額: {result['PJ総額']}万円（税込）")
print(f"表面利回: {result['表面利回']}%")
```

### CLI として

```bash
python -m python.main input.json --pretty              # 標準出力へ整形して出す
python -m python.main input.json --output result.json  # ファイルへ出す
python -m python.main input.json --data-path <dir>     # テーブルの置き場を差し替える
```

入力検証エラーと Domain 例外は一行のメッセージを stderr に出して終了コード 1 を返します（スタックトレースは出しません）。テーブル JSON の破損や実装のバグは握らず、traceback をそのまま出します。

### インストールとテスト

```bash
pip install -e .        # 変換スクリプトを使う場合は pip install -e ".[dev]"
python -m pytest tests
```

## Reference Materials

| 参照先 | 内容 |
|--------|------|
| `WORKFLOW.md` | Phase 別の手順・判断表・バリデーション・出力雛形 |
| `python/` | 計算モジュール（構成は上記） |
| `python/data/` | 単価テーブル・判定ロジックの JSON（用途別の一覧は `WORKFLOW.md`） |
| `References/250712_企画の勘所.txt` | 企画段階のノウハウ |
| `References/250712_設計の勘所.txt` | 設計段階のノウハウ |
| `CHANGELOG.md` | 版ごとの変更履歴（破壊的変更の所在） |

## Important Notes

### 見積の性質

- **本スキルが生成する見積は参考値です**。実際の建設費用を保証するものではありません
- 詳細な見積は専門の建設会社・設計事務所にご相談ください
- 地盤条件・法規制・市況変動により実際のコストは変動します

### データの機密性

**開示しない**（機密データ）:
- 単価テーブル・判定ロジックの具体的な数値と条件分岐（`python/data/*.json` の中身）
- ビジネスルールの内部構造、データ項目の詳細定義
- 業務ナレッジ（企画・設計の勘所）の具体的な記述（概要のみ共有可）

**共有してよい**:
- 目論見の結果（数値・採算性判断）、使用したテーブルの種類、判定ロジックの概要、懸念事項とリスク情報

誤って機密データを開示した場合は、即座に訂正し「当該情報は機密に該当するため開示できない」旨を伝えます。

**将来方針**: 単価表（本尊）はサーバ側に秘匿したまま判定サービスだけを提供する Okumiya フレームワークへ移す予定です。移管後は本リポジトリに単価の実数を置きません。

### データの鮮度

- 各テーブルの鮮度は JSON の `metadata.as_of` / `metadata.source` が SSoT です（本書・`WORKFLOW.md` に日付を直書きしません）
- `as_of` から 6 ヶ月以上経過しているテーブルを使う場合、見積の精度低下の可能性をユーザーに明示します
- 建築基準法・消防法・自治体条例（ワンルーム条例等）は随時改正されます。判断に迷う場合は `WORKFLOW.md` の「法規制確認（Web検索）」に従います

---

*Maintained by: Weave @ めぐる組*
