# GeneralConstructor Python計算モジュール

建設プロジェクトの収支計算を行うPythonモジュールです。

## インストール

```bash
cd homunculus/Weave/Expertises/GeneralConstructor
pip install -e .
```

## 使用方法

### 関数として使用

```python
from python.main import run_calculation

result = run_calculation({
    "土地価格": 6980,              # 万円
    "土地所在": "板橋区",
    "有効宅地面積": "109.40",       # ㎡
    "前面道路幅員": "7.5",          # m
    "搬入経路": "規制無",           # 規制無 / 規制有
    "道路種別": "公道",             # 公道 / 私道
    "接道長さ": "8.7",              # m
    "古家構造": "無し",             # 無し / 木造 / 鉄骨造 / RC造 / その他
    "解体面積": "0",                # ㎡
    "実効建蔽率": "70",             # %
    "用途地域": "第1種住居地域",
    "最大容積率": "200",            # %
    "住宅種別": "共同住宅",         # 長屋 / 共同住宅
    "建物層数": 4,                  # 3 / 4 / 5 / 6
    "半地下有無": "半地下有",       # 半地下有 / 半地下無
    "EV有無": "EV無",               # EV有 / EV無
    "壁率": "標準的",               # 標準的 / やや高い / 高い
    "設備率": "やや高い",           # 標準的 / やや高い / 高い
    "グレード": "やや高い",         # 標準的 / やや高い / 高い
    "地盤評価": "中間地盤"          # 硬質地盤 / 中間地盤 / 軟弱地盤
})

print(f"PJ総額: {result['PJ総額']}万円")
print(f"表面利回: {result['表面利回']}%")
```

### CLIとして使用

```bash
# 標準出力に結果を表示
python -m python.main input.json

# ファイルに出力（整形済み）
python -m python.main input.json --output result.json --pretty

# カスタムデータディレクトリを指定
python -m python.main input.json --data-path /path/to/References
```

## 入力パラメータ

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| 土地価格 | int | ✓ | 万円 |
| 土地所在 | str | ✓ | 区名（板橋区、目黒区など） |
| 有効宅地面積 | str/Decimal | ✓ | ㎡ |
| 前面道路幅員 | str/Decimal | ✓ | m |
| 搬入経路 | str | - | 規制無（デフォルト）/ 規制有 |
| 道路種別 | str | - | 私道（デフォルト）/ 公道 |
| 接道長さ | str/Decimal | ✓ | m |
| 古家構造 | str | ✓ | 無し / 木造 / 鉄骨造 / RC造 / その他 |
| 解体面積 | str/Decimal | - | ㎡（デフォルト: 0） |
| 実効建蔽率 | str/Decimal | ✓ | % |
| 用途地域 | str | ✓ | |
| 高度地区 | str | - | |
| 最大容積率 | str/Decimal | ✓ | % |
| 住宅種別 | str | ✓ | 長屋 / 共同住宅 |
| 建物層数 | int | ✓ | 3 / 4 / 5 / 6 |
| 半地下有無 | str | ✓ | 半地下有 / 半地下無 |
| EV有無 | str | ✓ | EV有 / EV無 |
| 壁率 | str | ✓ | 標準的 / やや高い / 高い |
| 設備率 | str | ✓ | 標準的 / やや高い / 高い |
| グレード | str | - | やや高い（デフォルト） |
| 地盤評価 | str | ✓ | 硬質地盤 / 中間地盤 / 軟弱地盤 |

## 出力パラメータ

| パラメータ | 型 | 説明 |
|-----------|-----|------|
| 施工条件係数 | float | |
| 建物形状係数 | float | |
| 建築面積 | float | ㎡ |
| 基礎種別 | str | |
| 基礎単価 | int | 万円/㎡ |
| 山留工法 | str | |
| 山留単価 | int | 万円/㎡ |
| 共用部面積 | float | ㎡ |
| 地下緩和面積 | float | ㎡ |
| 最大施工面積 | float | ㎡ |
| 施工面積 | float | ㎡ |
| 標準建築単価 | int | 万円/㎡ |
| 補正建築単価 | float | 万円/㎡ |
| 解体費用 | int | 万円 |
| 基礎費用 | int | 万円 |
| 山留費用 | int | 万円 |
| 地盤費用 | int | 万円 |
| 建物価格 | int | 万円 |
| PJ総額 | int | 万円 |
| 貸床面積 | float | ㎡ |
| 貸床単価 | int | 円/㎡ |
| 年間売上 | int | 万円 |
| 表面利回 | float | % |
| 目標利回 | float | % |

## テスト

```bash
# 全テスト実行
pytest tests/ -v

# カバレッジ付き
pytest tests/ -v --cov=python --cov-report=html
```

## モジュール構成

```
python/
├── __init__.py
├── main.py           # エントリーポイント
├── loader.py         # JSONテーブル読み込み
├── calculator.py     # 計算ロジック
├── schema/
│   ├── __init__.py
│   ├── tables.py     # 単価テーブル型定義
│   └── models.py     # 入出力モデル定義
└── README.md         # このファイル
```

---

*Last Updated: 2026-01-10*
