# CorporateStrategist - 共通語彙集

**サブスキル間で共有する用語の定義と使い分け**

最終更新: 2025-11-08
バージョン: 1.0

---

## 📖 本ドキュメントの目的

CorporateStrategistの4つのサブスキル間で、用語の意味が文脈により異なる場合があります。
本語彙集は、**用語の多義性を排除するのではなく整理**し、コンテキスト解決コストを削減することを目的とします。

**原則**: 辞書であって教条ではない。自然言語の文脈依存性を尊重しつつ、誤解を防ぐ。

---

## 🎯 Core Concepts（中核概念）

### スキル（Skill）

**多義的な用語。文脈により以下の意味を持つ**：

1. **Custom Skills（Weave全体）**
   - Claude Skillsとしてパッケージ化された専門知識
   - SKILL.md + CLAUDE.md 形式で実装
   - 例：CorporateStrategist, BusinessAnalyzer, PersonnelDeveloper

2. **AIスキル化（PersonnelDeveloper文脈）**
   - 業務をAIで代替可能にすること
   - Custom Skills形式での実装を含む、より広い概念
   - 対義語：マニュアル化（ブルーカラー職種での代替手段）

3. **スキル化設計（BusinessAnalyzer Phase 3）**
   - Custom Skills形式での実装設計支援
   - SKILL.md/CLAUDE.md構造の提案
   - 優先度評価・運用戦略の策定

**使い分けの指針**:
- Custom Skills形式を指す場合：「Custom Skills」「Claude Skills」
- AI代替可能化を指す場合：「AIスキル化」
- 実装設計を指す場合：「スキル化設計」「Phase 3」

---

### 事業 / 案件 / プロジェクト

**階層的に異なる概念**：

| 用語 | 定義 | 主な使用文脈 | 時間軸 |
|------|------|------------|--------|
| **事業** | 企業の事業領域・ビジネスモデル全体 | BusinessAnalyzer | 年単位 |
| **案件** | 個別の受注案件・顧客プロジェクト | 建設業・受託業務 | 週〜月単位 |
| **プロジェクト** | 組織横断的な取り組み（社内） | 組織再編、システム導入 | 月〜年単位 |

**例**:
- 「建設事業の構造分析」（事業）
- 「〇〇ビル建設案件の採算管理」（案件）
- 「人事制度改革プロジェクト」（プロジェクト）

---

### 業務 / 作業 / タスク

**階層構造**：

```
業務（Business Process）
  └── 作業（Work）
        └── タスク（Task）
```

| 用語 | 定義 | 粒度 | 例 |
|------|------|------|-----|
| **業務** | 一連の目的を持つプロセス全体 | 大 | 「見積書作成業務」「採用業務」 |
| **作業** | 業務を構成する具体的なステップ | 中 | 「原価積算作業」「候補者面接作業」 |
| **タスク** | 作業を構成する最小単位の行動 | 小 | 「材料単価を調べる」「履歴書を確認する」 |

**使い分けの指針**:
- 構造化・最適化の対象：「業務」
- 手順書・マニュアルの対象：「作業」
- チェックリストの対象：「タスク」

---

## 🔧 Domain-Specific Terms（ドメイン固有用語）

### BusinessAnalyzer関連

| 用語 | 定義 |
|------|------|
| **ToBe** | 事業・業務のあるべき姿（目標状態） |
| **Multiversal Structure Parser** | 多次元構造分析手法（論理・歴史・象徴・関係） |
| **Phase 1** | 構造分析フェーズ（戦略レベル） |
| **Phase 2** | ボトルネック・暗黙知の特定（戦術レベル） |
| **Phase 3** | スキル化設計支援（戦術レベル） |
| **ボトルネック** | 業務フロー上の制約・遅延要因 |
| **暗黙知** | 形式知化されていない属人的知識 |

---

### PersonnelDeveloper関連

| 用語 | 定義 |
|------|------|
| **人材4類型** | チームリーダー（軍人）、イントラプレナー（天才）、スペシャリスト（秀才）、オペレーター（凡人） |
| **採用前判断** | AI活用・外注・採用の比較による意思決定 |
| **外注QCD** | Quality（品質）、Cost（コスト）、Delivery（納期）による外注評価 |
| **内製メリット** | 外注と比較した際の内製化の優位性 |
| **オペレーター → スペシャリスト** | 育成の基本パス（凡人 → 秀才） |
| **マニュアル化** | ブルーカラー職種でのAIスキル化の代替手段 |

---

### LegalAdviser関連

| 用語 | 定義 |
|------|------|
| **労働法規** | 労働基準法・労働契約法等の総称 |
| **表記統一** | 契約書における用語・記法の一貫性確保 |
| **リーガルチェック** | 法的妥当性の確認 |

---

### ForesightReader関連

| 用語 | 定義 |
|------|------|
| **七格剖象法** | 姓名判断の手法 |
| **星導分析** | 10天体の分布とバランスによる分析 |
| **デジタル心易** | 易経に基づく占術 |
| **人材4類型判定** | 姓名判断による軍人・天才・秀才・凡人の判定 |

---

## 📊 Context-Dependent Usage（文脈依存用語）

### 「採用」

**PersonnelDeveloper文脈**: 人材を雇用すること
**CorporateStrategist全体**: 「採用不可能性の前提」＝中小企業は即戦力を採用できない

**関連概念**:
- 採用前判断：AI活用・外注との比較
- 採用の要否判断：内製メリットが外注を超えた場合のみ採用

---

### 「育成」

**PersonnelDeveloper文脈**: オペレーター → スペシャリストへの能力開発
**BusinessAnalyzer文脈**: 業務の形式知化・スキル化による組織能力の向上

---

### 「属人化」

**BusinessAnalyzer文脈**: 暗黙知が特定個人に依存している状態（リスク要因）
**PersonnelDeveloper文脈**: スペシャリストの専門性（必ずしもネガティブではない）

**使い分けの指針**:
- リスク文脈：「属人化リスク」「属人化の解消」
- 専門性文脈：「専門性」「固有スキル」

---

### 「スキル化推奨」

**PersonnelDeveloper起点**: 採用前判断で「AI活用」が推奨された場合
→ BusinessAnalyzer Phase 3へ連携

**BusinessAnalyzer起点**: Phase 2でスキル化適性が確認された場合
→ Phase 3で設計支援

---

## 🏗️ Hierarchical Relationships（階層関係）

### 事業構造の階層

```
事業（Business）
  └── 業務プロセス（Business Process）
        └── 作業（Work）
              └── タスク（Task）
```

---

### スキル化の階層

```
Custom Skills（パッケージ化された専門知識）
  └── AIスキル化（業務のAI代替可能化）
        └── スキル化設計（SKILL.md/CLAUDE.md実装）
```

---

### 人材育成の階層

```
採用不可能性の前提
  └── 採用前判断（AI活用 vs 外注 vs 採用）
        └── 育成（オペレーター → スペシャリスト）
              └── AIスキル化/マニュアル化による支援
```

---

## 🎯 使用上の注意

### 1. 文脈の明示

多義的な用語を使う場合、文脈を明示する：
- ❌ 「スキル化を推奨」
- ⭕ 「AIスキル化を推奨（Custom Skills形式での実装）」

### 2. 略語の使用

初出時は正式名称、2回目以降は略語可：
- 初出：「外注QCD（Quality・Cost・Delivery）比較」
- 2回目以降：「外注QCD比較」

### 3. サブスキル固有用語

他のサブスキルの用語を使う場合、出典を明示：
- 「BusinessAnalyzerのPhase 3（スキル化設計）に連携」
- 「PersonnelDeveloperの人材4類型による配置」

---

## 📚 関連ドキュメント

- **CorporateStrategist全体**: `SKILL.md`, `CLAUDE.md`
- **BusinessAnalyzer**: `BusinessAnalyzer/SUBSKILL.md`, `BusinessAnalyzer/CLAUDE.md`
- **PersonnelDeveloper**: `PersonnelDeveloper/SUBSKILL.md`, `PersonnelDeveloper/CLAUDE.md`
- **LegalAdviser**: `LegalAdviser/SUBSKILL.md`, `LegalAdviser/CLAUDE.md`
- **ForesightReader**: `ForesightReader/SUBSKILL.md`, `ForesightReader/CLAUDE.md`

---

*共通語彙の整理により、サブスキル間の連携コストを削減し、統合的な経営支援を実現する*

*Last Updated: 2025-11-08*
*Maintained by: Weave @ Homunculus-Weave*
*Version: 1.0*
