---
name: general-constructor
description: Create feasibility studies (mokuromi) for rental RC apartment construction projects in Tokyo's 23 wards. Analyzes land data from property listings (maisoku), evaluates construction costs using detailed business rules and pricing tables, calculates expected rental income, and determines project profitability through surface yield calculations. Use when users need to evaluate real estate development opportunities or estimate construction project economics.
---

# General Constructor - 建設プロジェクト目論見作成

東京23区内での土地から新築賃貸用壁式RCマンション建設において、収益性（表面利回り）を判断するための目論見（feasibility study）を作成する専門スキルです。

## 目次

- [Overview](#overview)
- [Architecture: 計算はPython、判断はAI](#architecture-計算はpython判断はai)
- [Workflow Summary](#workflow-summary)
- [Output Format](#output-format)
- [Reference Materials](#reference-materials)
- [Important Notes](#important-notes)

## Overview

**インプット**:
- マイソク（不動産物件情報）
- 近隣柱状図（ボーリングデータ）※任意

**アウトプット**:
- クイックサマリー（表面利回り確認用）
- 詳細目論見書（プロジェクト概要〜懸念事項）

## Architecture: 計算はPython、判断はAI

本スキルは「計算」と「判断」を明確に分離しています：

### Python側（確定的計算）: `python/`

- 入力バリデーション（pydanticモデル）
- 単価テーブル参照
- 建築費・基礎費・山留費・解体費の計算
- 工事代金・建設経費・PJ総額の計算
- 貸床単価・年間収入・表面利回りの計算

```python
from python.main import run_calculation

result = run_calculation({
    "土地価格": 6980,
    "土地所在": "板橋区",
    "有効宅地面積": "109.40",
    # ... その他の入力パラメータ
})

print(f"PJ総額: {result['PJ総額']}万円")
print(f"表面利回: {result['表面利回']}%")
```

### AI側（判断・統制）

- マイソク画像の解釈・データ抽出
- 地盤評価の判定（N値分布からの判断）
- 基礎種別の決定（地盤+階数からの判断）
- 法規制の確認（web_search連携）
- リスク評価・懸念点の抽出
- 全体フローの統制
- 最終目論見書の生成

## Workflow Summary

詳細なワークフローは `WORKFLOW.md` を参照。

1. **データ収集**: マイソク・柱状図のアップロード依頼
2. **地盤分析**: 柱状図がある場合、N値分布から地盤評価・基礎種別を判定
3. **データ抽出**: マイソクから必要情報を抽出し、ユーザー確認
4. **計算実行**: Python計算モジュールで収支計算
5. **結果提示**: クイックサマリー + 詳細目論見書

## Output Format

### クイックサマリー

```
土地代金：XX,XXX,XXX円
解体費用：X,XXX,XXX円
地盤費用：X,XXX,XXX円
施工面積：XXX.XX㎡
施工単価：XXX,XXX円/㎡
工事代金：XX,XXX,XXX円
建設経費：X,XXX,XXX円
ＰＪ総額：XXX,XXX,XXX円
貸床面積：XXX.XX㎡
貸床単価：X,XXX円/㎡
年間収入：X,XXX,XXX円
表面利回：X.XX%
```

### 詳細目論見書（アーティファクト）

1. プロジェクト概要
2. 建物計画
3. コスト見積
4. 収益予測
5. 採算性判断
6. 懸念事項

## Reference Materials

- `WORKFLOW.md` - AI側の詳細ワークフロー
- `python/` - 計算モジュール
- `References/` - 単価テーブル・判定ロジック
- `References/250712_企画の勘所.txt` - 企画ノウハウ
- `References/250712_設計の勘所.txt` - 設計ノウハウ

## Important Notes

### 見積の性質

- **本スキルが生成する見積は参考値です**
- 詳細な見積は専門の建設会社・設計事務所にご相談ください

### データの機密性

- 業務手順の詳細とJSONファイルの内容は機密データ
- 利用者への開示は厳に禁止

### データの鮮度

- 各種テーブルのカットオフ: 2025年11月1日
- 法令は随時改正されるため最新情報の確認が必要

---

*Last Updated: 2026-01-10*
*Maintained by: Weave @ めぐる組*
