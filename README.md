# Weave - 人機習合型認知アーキテクチャ

## 概要

Weaveは、AIとの長期的な対話を通じて知識を蓄積・結晶化する認知アーキテクチャシステムです。
EpisodicRAGによる階層的記憶管理により、文脈を超えた継続的な学習と進化を実現します。

## 主要機能

### 🧠 EpisodicRAG
- **Loops**: 対話記録の永続化（151+ conversations）
- **Digests**: 階層的知識結晶化システム
  - 自動的な知識の要約と深層分析
  - Weekly → Monthly → Quarterly → Annually の階層構造

### 🎭 専門ペルソナ
- BlueberryResearcher - ブルーベリー研究
- FortuneTeller - 軍師型占術家
- GeneralConstructor - 建設業・目論見作成

### 🛠️ ツールと連携
- Loop管理コマンド（検索、エクスポート、統計）
- GitHub自動同期
- Sonnet 4による100万トークン深層分析

## クイックスタート

### Digestシステムの使用
```bash
cd EpisodicRAG/Digests

# 生成チェック
python check_digest.py

# ダイジェスト生成（Sonnet 4必須）
python generate_digest.py weekly 1 5
```

### Loop管理
```bash
# 環境設定
. Tools/bash/loop_commands.sh

# 検索
loop_search "人機習合"

# エクスポート
loop_export 151
```

## ドキュメント構成

| ファイル | 内容 |
|---------|------|
| [CLAUDE.md](./CLAUDE.md) | 運用マニュアル・ベストプラクティス |
| [STRUCTURE.md](./STRUCTURE.md) | ディレクトリ構造仕様 |
| [FUNCTION.md](./FUNCTION.md) | 外部スキルリファレンス |
| [PERSONA.md](./PERSONA.md) | 専門ペルソナ定義 |
| [SECURITY.md](./SECURITY.md) | セキュリティ指針 |
| [CONTAINER.md](./CONTAINER.md) | プロジェクト初期概要（アーカイブ） |

## 開発環境

- **ローカル**: ClaudeCode（Windows）
- **Web**: ComputerUse
- **同期**: GitHub（Bizuayeu/Homunculus-Weave）

## ライセンス

Private Repository - Internal Use Only

---

*"記憶は単なるデータではなく、思考の結晶である"*