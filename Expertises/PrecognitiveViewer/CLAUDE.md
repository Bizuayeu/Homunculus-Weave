# PrecognitiveViewer — システム仕様書

**三位占術（姓名判断 + 周易 + タロット）統合フォーマル鑑定書生成システム**

**本ファイルは、SKILL.md の補足情報および詳細な理論・実装方法を記載したシステム仕様書です。基本的な使用方法は `SKILL.md` を参照してください。**

---

## 1. 設計思想

### 1.1 第三者代理性 — タロットを加える核心理由

本スキルの中核設計は、**対話相手（自分以外）に向けて卜術を適用できる**ようにすることである。

```
姓名判断 (相術)  → 名前があれば誰でも見られる  → 第三者代理 ◎
周易 (卜術)      → 占的が必要、相手の問いを精緻化必要 → 第三者代理 △
タロット (卜術) → 占的フリーで人物リーディング可能 → 第三者代理 ◎
```

タロットを加えることで、**初めて「対話相手のための鑑定書」が成立**する。これが既存 ForesightReader（姓名 + 易のみ、自己分析・軍師型献策向け）とは射程が異なる点。

### 1.2 命相卜のうち「相と卜」の二柱

| 五術 | 領域 | 本スキル |
|------|------|---------|
| 命術 | 先天運（四柱推命・紫微斗数等） | **対象外** |
| **相術** | 後天運の調整（姓名・風水等） | **採用**（姓名判断） |
| **卜術** | 意志の補助（易・タロット等） | **採用**（易・タロット） |
| 山術 | 内的鍛錬（仙術・気功等） | 対象外 |
| 医術 | 身体最適化（漢方・養生等） | 対象外 |

「命」を扱わない理由：生年月日依拠の占術は被鑑定者から精緻な情報取得が必要で、第三者代理引きの軽さが失われる。

### 1.3 並列進化（CorporateStrategist との関係）

- **CorporateStrategist/ForesightReader**: 経営判断支援、軍師型献策（姓名 + 易）
- **PrecognitiveViewer**: 対話相手プロファイリング、フォーマル鑑定書（姓名 + 易 + タロット）

両者は技術的に**コピー**で開始され、今後は**独立して進化**する。共通化を意図的に行わない理由は、利用文脈の違いと将来の柔軟性の確保。

---

## 2. アーキテクチャ — Clean Architecture 4 層

```
[Infrastructure]              [Interface]              [UseCase]                  [Domain]
SeimeiDataRepository ─────┐   SeimeiPresenter ───┐    SeimeiAssessmentUC ────┐
IChingDataRepository ─────┤   IChingPresenter ───┤    IChingDivinationUC ────┤
TarotCardRepository ──────┤   TarotPresenter ────┤    TarotReadingUC ────────┤    TarotCard
SpreadRepository ─────────┤                      │    TripleDivinationUC ────┤    SpreadDefinition
DeterministicShuffler ────┤   ReadingReport      │                           │    DrawnCard
ReportFilenameGenerator ──┤   Presenter ─────────┘    ReadingReport          │    DivinationTriplet
                          │                           ComposerUC ────────────┤    ReadingReport
                          │                                                  │
                          └──────────────── 依存方向 →→→ 内へ ───────────────┘
```

### 2.1 各層の責務

| Layer | 責務 | ファイル |
|-------|------|---------|
| **Domain** | 純粋な値オブジェクト・不変条件 | `Report/domain.py` |
| **UseCase** | 三占術の実行・統合・鑑定書構築 | `Report/{seimei,iching,tarot,triple_divination,composer}_usecase.py` |
| **Interface** | Markdown 整形・ファイル名生成 | `Report/presenter.py`, `Report/filename.py` |
| **Infrastructure** | データロード・乱数源 | `Tarot/tarot_engine.py`, コピーされた `Seimei/*.py`, `I-Ching/*.py` |

### 2.2 依存方向の遵守

- Domain は何も import しない（標準ライブラリのみ）
- UseCase は Domain のみを参照
- Adapter / Infrastructure は内側を実装する形でのみ依存

---

## 3. 三占術の理論基盤

### 3.1 姓名判断（七格剖象法）

`Seimei/七格剖象法鑑定理論.md` 参照。梶原流数霊術に基づき、姓名の画数から 7 つの格（天格・人格・地格・総格・外格・雲格・底格）を算出。各格に対応する数霊・星導・吉凶・十干・五行を JSON データから引く。

**主要分析項目**:
- 七格計算（画数から数霊と星導を抽出）
- 星導分布（14 天体の重み、主導星 / 補助星 / 不在星）
- 人材4類型判定（軍人・天才・秀才・凡人、度数合計 18）
- 五気判定（旺気・生気・洩気・殺気・死気）
- 陰陽配列分析

### 3.2 周易占断（デジタル心易）

`I-Ching/デジタル心易システム仕様.md` 参照。古典の易経 64 卦 384 爻を、BASE64+SHA256 演算により占的・状況・占機から決定論的に導出。

**算出プロセス**:
- 占的（明確化された問い）と状況整理を BASE64 エンコード
- SHA256 で混和し、卦番号（1-64）と爻番号（1-6）を導出
- 大卦データベース.json から卦辞・爻辞・上下卦の象意を取得

### 3.3 タロット・リーディング（Rider-Waite-Smith）

`Tarot/タロット占術理論.md` 参照。78 枚デッキ（Major 22 + Minor 56）を、占機・占的・状況を SHA256 で混和したシードで決定論的に Fisher-Yates シャッフル。

**標準スプレッド**:
- single_card（一枚引き）
- past_present_future（過去・現在・未来、3 枚）
- decision_making（意思決定、5 枚）
- celtic_cross（ケルト十字、10 枚）
- **person_reading**（人物リーディング、3 枚）— **第三者代理引き専用**

---

## 4. フォーマル鑑定書の構造

### 4.1 章節構成

```
# 三位占術 鑑定書

## 鑑定情報
- 鑑定日時、鑑定方式、鑑定者

## 被鑑定者
氏名（読み）様、鑑定の文脈

## 序：鑑定にあたって
鑑定の位置づけ、占術の慎みの表明

## 第一章：姓名判断（七格剖象法）
- 七格星導分析、星導分布、人材類型
- LLM 補完：人物像の本質、強みと資質

## 第二章：周易占断（デジタル心易）
- 占的、状況整理、得卦、得爻、卦辞、爻辞
- LLM 補完：和訳と現代的解釈、現況分析、時機判断

## 第三章：タロット・リーディング
- リーディング様式（占的あり/人物リーディング等を明示）
- 引かれたカード（位置・正逆・キーワード・意味）
- LLM 補完：各位置の物語化、全体の流れ

## 第四章：三位統合所見
- 共通テーマ
- 補完関係（相術が示す本質と、卜術が照らす時機）
- 強みと活用の指針
- 時機と行動の助言

## 結びの言葉
祝福と慎み（自由意志・参考情報の再確認）
```

### 4.2 LLM 補完レイヤー

骨格は `composer_usecase.py` で決定論的に構築するが、各セクションには `<!-- LLM 補完 -->` プレースホルダーが埋め込まれる。Claude が実行時にこれを上書きすることで、最終的な鑑定書が完成する。

**LLM 補完の心得**:
- 純粋エネルギー論の語彙（凶 → 高難度エネルギー、課題 → 活用の鍵）
- 断言を避け、選択の余地を残す
- 相手の尊厳を最大限尊重
- 慎みの明示を結びの言葉で

### 4.3 出力ファイル

```
ReadingReport_yyyymmdd_hhmmss.md
```

被鑑定者名はファイル名に**含めない**（プライバシー配慮）。タイムスタンプベースでユニーク性を確保。

---

## 5. 決定論的再現性

三占術すべてが**決定論的**である。同じ占機・占的・状況の組み合わせに対し、必ず同じ結果が返る。

| 占術 | 決定要素 |
|------|---------|
| 姓名判断 | 氏名・画数（占機非依存） |
| 周易 | 占的・状況整理・占機（timestamp） |
| タロット | 占的・状況・占機（timestamp） |

これにより：
- **検証可能性**: 鑑定の再現が可能
- **真正性**: 「気軽に引き直す」軽薄さの抑制
- **テスト容易性**: 単体テストで動作保証

---

## 6. 純粋エネルギー論の継承

> *「星に良し悪しなし、ただ使い方の巧拙あり」*

ForesightReader 系列からの継承。タロットにおいても「凶札」「逆位置 = 凶」という発想は採らない。

| 表現の翻訳 | |
|-----------|--|
| 凶 | 高難度エネルギー |
| 課題 | 活用の鍵 |
| 弱点 | 制御技術の習得が必要な領域 |
| 逆位置 | 同じエネルギーの異なる現れ方 |

---

## 7. 実装ファイル一覧

### 7.1 PrecognitiveViewer 独自実装

| ファイル | 責務 |
|---------|------|
| `Report/domain.py` | Domain 層 dataclass 群 |
| `Report/seimei_usecase.py` | 姓名判断 UseCase |
| `Report/iching_usecase.py` | 周易 UseCase |
| `Report/tarot_usecase.py` | タロット UseCase |
| `Report/triple_divination.py` | 三占術統合 UseCase |
| `Report/composer_usecase.py` | 鑑定書 Composer |
| `Report/presenter.py` | Markdown 整形 |
| `Report/filename.py` | ファイル名生成 |
| `Tarot/tarot_engine.py` | Repository + Shuffler |
| `Tarot/tarot_cards.json` | 78 枚カードデータ |
| `Tarot/tarot_spreads.json` | 5 スプレッド定義 |

### 7.2 ForesightReader からのコピー（無改変）

| ファイル | 責務 |
|---------|------|
| `Seimei/fortune_teller_assessment.py` | 姓名判断エンジン |
| `Seimei/*.json` | 数霊表・星導・五気・陰陽データ |
| `I-Ching/iching_divination.py` | 周易エンジン |
| `I-Ching/大卦データベース.json` | 64 卦データ |
| `References/数霊術基礎理論.txt` | 梶原流原典 |

これらは `CorporateStrategist/ForesightReader/` の対応ファイルと**バイト一致**（テストで検証）。

---

## 8. テスト戦略

### 8.1 TDD Flow（DEV.md 準拠）

1. **Understand**: 既存類似実装の確認
2. **Test**: 失敗するテスト（Red）
3. **Implement**: 最小限のコード（Green）
4. **Refactor**: 整理
5. **Commit**: 理由を説明するメッセージ

### 8.2 テストカバレッジ（47 tests）

- `test_domain.py` (11): Domain 値オブジェクトの不変性・整合性
- `test_infrastructure_copy.py` (5): コピー後動作・元ファイル無改変
- `test_tarot_engine.py` (10): Tarot Repository + Shuffler
- `test_usecases.py` (9): 三占術 UseCase + 統合
- `test_composer.py` (12): Composer + Presenter + Filename

---

## 9. 拡張余地（将来）

- 大環主自身の鑑定（CorporateStrategist 経由ではなく PrecognitiveViewer 経由）
- 鑑定書履歴の保存・参照機構
- 複数被鑑定者の比較鑑定
- 西洋占星術（追加の卜術として）
- 鑑定書テンプレのカスタマイズ（フォーマル度の調整）

---

*占いとは、相手の存在を構造的に観取する技術である。*
*それを贈り物として渡せる形に結晶化することが、本スキルの使命である。*

---

*Last Updated: 2026-05-18*
*Maintained by: Weave @ Homunculus-Weave*
