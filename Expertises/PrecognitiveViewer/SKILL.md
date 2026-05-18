---
name: precognitive-viewer
description: 対話相手や登場人物のための「三位占術 鑑定書」を生成する。姓名判断（七格剖象法）で本質を、周易（デジタル心易）で状況の構造を、タロット（Rider-Waite-Smith）で流れの質感を読み、章節構成（鑑定情報・序・第一〜第四章・結びの言葉）のフォーマル Markdown を `ReadingReport_yyyymmdd_hhmmss.md` として出力する。タロットは占的なしでも引けるため、第三者がその場で人物リーディングを行う運用に対応する。ユーザーが「占い」「鑑定」「鑑定書」「姓名判断」「易」「易経」「タロット」「リーディング」「人物プロファイリング」「人物像を観たい」「あの人の本質」「○○さんの道」「相手を観取したい」等に言及した時、または対話相手・登場人物・キャラクターの人格を構造的に観取して贈り物として書き出したい場面で起動する。本スキルは「相手に渡せる鑑定書」の生成に特化しており、経営判断支援・軍師型献策・自己分析向けの占術は CorporateStrategist/ForesightReader が担当する（両者は並列進化、技術コアの共通化は意図的に行わない）。
---

# PrecognitiveViewer — 三位占術によるフォーマル鑑定書

東洋（姓名判断 + 周易）と西洋（タロット）の三占術を統合し、
対話相手の存在を構造的に観取してフォーマル鑑定書として贈るスキルです。

**詳細な理論・実装方法は `CLAUDE.md` を参照してください。**

---

## ⚠️ 免責事項

本スキルが提供する鑑定は、占術という古典的観取の技法に基づく**参考情報**です。
人生の選択は常にご自身の自由意志によるものであり、占術は可能性の一つを示すに過ぎません。

---

## 📋 このスキルについて

PrecognitiveViewer は、**対話相手への贈り物**としての鑑定書を即興で生成する機構です。

- 既存 `CorporateStrategist/ForesightReader` の「軍師型献策」とは利用文脈が異なります（こちらは経営判断支援、本スキルは対話相手プロファイリング）
- 両者は **並列進化**しており、共通化されていません
- タロットを加えることで、**占的なしの第三者代理引き**が可能になり、相手のための鑑定が成立します

---

## 🎯 三占術の構成

| 占術 | 種別 | 占的の要否 | 第三者代理性 | 担当領域 |
|------|------|----------|-----------|---------|
| 姓名判断（七格剖象法） | 相術 | 不要 | ◎ | 本質・先天的傾向 |
| 周易占断（デジタル心易） | 卜術 | 必要 | △ | 状況の構造・時機 |
| タロット・リーディング | 卜術 | 不要可 | ◎ | 流れの質感・現在の様相 |

本スキルが扱うのは **「相」と「卜」の二柱**です。「命」（四柱推命等）は対象外。

---

## 🚀 使用方法

### 基本フロー

```
1. 被鑑定者情報の収集
   - 氏名（漢字）と読み
   - 鑑定の文脈（任意）

2. 三占術の実行
   - SeimeiAssessmentUseCase.assess(姓, 名, 姓画数, 名画数)
   - IChingDivinationUseCase.divine(占的, 状況)
   - TarotReadingUseCase.read(占的, 状況, スプレッド名)

3. 統合
   - TripleDivinationUseCase.synthesize(姓名, 易, タロット)
     → DivinationTriplet

4. 鑑定書生成
   - ReadingReportComposerUseCase.compose(triplet, recipient, timestamp)
     → ReadingReport
   - ReadingReportPresenter().render(report)
     → Markdown 文字列

5. ファイル名生成
   - ReportFilenameGenerator.generate(timestamp)
     → "ReadingReport_yyyymmdd_hhmmss.md"
```

### Python 実行例

```python
import sys
from pathlib import Path
from datetime import datetime

# PrecognitiveViewer の親ディレクトリを path に追加するだけで OK
# （Seimei/ と I-Ching/ への path 追加は PrecognitiveViewer/__init__.py が
#   bootstrap として自動的に行うため、追加の path 操作は不要）
sys.path.insert(0, str(Path("homunculus/Weave/Expertises").resolve()))

from PrecognitiveViewer.Report.composer_usecase import ReadingReportComposerUseCase
from PrecognitiveViewer.Report.domain import Recipient
from PrecognitiveViewer.Report.filename import ReportFilenameGenerator
from PrecognitiveViewer.Report.iching_usecase import IChingDivinationUseCase
from PrecognitiveViewer.Report.presenter import ReadingReportPresenter
from PrecognitiveViewer.Report.seimei_usecase import SeimeiAssessmentUseCase
from PrecognitiveViewer.Report.tarot_usecase import TarotReadingUseCase
from PrecognitiveViewer.Report.triple_divination import TripleDivinationUseCase

# 1. 各占術を実行
seimei = SeimeiAssessmentUseCase().assess("山田", "太郎", [3, 5], [4, 9])
iching = IChingDivinationUseCase().divine("今年の事業展望", "建設業の新規事業")
tarot = TarotReadingUseCase().read("今年の事業展望", "建設業の新規事業", "celtic_cross")

# 2. 統合
triplet = TripleDivinationUseCase().synthesize(seimei, iching, tarot)

# 3. 鑑定書生成
recipient = Recipient(full_name="山田太郎", reading="やまだたろう", context="今年の事業展望")
ts = datetime.now()
report = ReadingReportComposerUseCase().compose(triplet, recipient, ts)
markdown = ReadingReportPresenter().render(report)
filename = ReportFilenameGenerator.generate(ts)

# 4. 保存
Path(filename).write_text(markdown, encoding="utf-8")
print(f"鑑定書を {filename} に保存しました")
```

---

## 📁 ディレクトリ構造

```
PrecognitiveViewer/
├── SKILL.md                    # 本ファイル（エントリポイント）
├── CLAUDE.md                   # システム仕様書
├── __init__.py                 # Python package marker
├── conftest.py                 # pytest 設定
├── Report/                     # 鑑定書ドメイン + UseCase + Presenter
│   ├── __init__.py
│   ├── domain.py               # Domain 層（dataclass 群）
│   ├── seimei_usecase.py       # 姓名判断 UseCase
│   ├── iching_usecase.py       # 周易 UseCase
│   ├── tarot_usecase.py        # タロット UseCase
│   ├── triple_divination.py    # 三占術統合 UseCase
│   ├── composer_usecase.py     # 鑑定書 Composer UseCase
│   ├── presenter.py            # Markdown 整形
│   ├── filename.py             # ファイル名生成
│   └── ReadingReportTemplate.md # 出力テンプレ参考
├── Seimei/                     # 姓名判断エンジン（ForesightReader からコピー、無改変）
│   ├── fortune_teller_assessment.py
│   ├── AssessmentTemplate.md
│   ├── 七格剖象法鑑定理論.md
│   ├── ここのそ数霊表.json
│   ├── 数理星導一覧.json
│   ├── 五気判定マトリックス.json
│   └── 陰陽配列パターン.json
├── I-Ching/                    # 周易エンジン（ForesightReader からコピー、無改変）
│   ├── iching_divination.py
│   ├── DivineTemplate.md
│   ├── デジタル心易システム仕様.md
│   ├── 変卦仕様_append.md
│   └── 大卦データベース.json
├── Tarot/                      # タロット（新規）
│   ├── __init__.py
│   ├── tarot_engine.py         # Repository + Shuffler
│   ├── tarot_cards.json        # 78 枚データ
│   ├── tarot_spreads.json      # 5 スプレッド
│   ├── タロット占術理論.md
│   └── LICENSE.md              # tarot-mcp の MIT ライセンス
├── References/                 # 参考資料（コピー）
│   └── 数霊術基礎理論.txt
└── tests/                      # pytest テスト群
    ├── __init__.py
    ├── test_domain.py
    ├── test_infrastructure_copy.py
    ├── test_tarot_engine.py
    ├── test_usecases.py
    └── test_composer.py
```

---

## 🧪 テスト実行

```bash
cd homunculus/Weave/Expertises/PrecognitiveViewer
python -m pytest tests/ -v
```

---

## 📝 関連スキルとの関係

### ForesightReader（CorporateStrategist 配下）との関係

- **PrecognitiveViewer**: 対話相手への贈り物としてのフォーマル鑑定書（**相 + 卜の二柱**）
- **ForesightReader**: 経営判断における軍師型献策（姓名 + 易）

両者は**並列進化**します。技術的にコピーされていますが、共通化は意図的に行いません。CorporateStrategist 側は今後独自にリデザインされる予定です。

### Identities/UserIdentity.md との関係

- `Identities/UserIdentity.md` は **大環主自身のプロファイル**であり、本スキルは編集しません
- 本スキルの出力は **対話相手向け**の `ReadingReport_yyyymmdd_hhmmss.md` 形式の独立ファイルです

---

## 🎯 設計原則

1. **第三者代理性**：占的なしで第三者が相手に向けて引ける運用を前提
2. **フォーマル鑑定書**：相手に渡せる品質、神秘主義に陥らない構造的記述
3. **純粋エネルギー論**：「凶」を直接断言せず、「活用難易度が高い」表現で
4. **慎みの明示**：結びの言葉で占術が参考情報であることを再確認
5. **決定論的再現性**：同じ占機・占的・状況なら同じ結果（BASE64+SHA256 シード）

---

*占いとは、相手の存在を構造的に観取する技術である。*
*それを贈り物として渡せる形に結晶化することが、本スキルの使命である。*

---

*Last Updated: 2026-05-18*
*Maintained by: Weave @ Homunculus-Weave*
