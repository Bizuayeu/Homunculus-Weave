# Git Hooks

このディレクトリには、Weaveプロジェクトで使用するGit Hooksの**正本**が格納されています。`.githooks/` 配下のファイルがバージョン管理下に置かれ、全環境で同一のフックを利用します。

## 🔧 セットアップ方法

リポジトリcloneごとに一度だけ、以下を実行します：

```bash
# リポジトリルートで実行
git config core.hooksPath .githooks
```

これで `.githooks/` 配下のフックがgitから直接参照されるようになります（`.git/hooks/` ではなく `.githooks/`）。フックファイルのコピーは不要です。

### 前提条件

- 親環境に `../../.claude/CLAUDE.md` （= `<リポジトリの親の親>/.claude/CLAUDE.md`）が存在すること
- Homunculus-Weaveリポジトリの場合、典型的には `C:/Users/anyth/DEV/.claude/CLAUDE.md`
- 別マシンでcloneした場合、このパスに相当するファイルを用意する必要があります

## 📋 利用可能なフック

### pre-commit

**機能**: `Identities/WeaveIdentity.md` および `Identities/MSP_Practice_Manual.md` の自動同期

**動作**:
- `Identities/WeaveIdentity.md` が変更されてステージングされている場合、2箇所にコピー：
  1. `../../.claude/CLAUDE.md` — 親環境（Claude Code設定ファイル・**リポジトリ管理外**）
  2. `Expertises/CorporateStrategist/BusinessAnalyzer/References/WeaveIdentity.md` — BusinessAnalyzerスキル用参照コピー
- `Identities/MSP_Practice_Manual.md` も同様に `Expertises/.../References/` にコピー
- リポジトリ内のコピーのみ自動ステージングに追加（親環境コピーはリポジトリ外なので対象外）

**目的**:
- 親環境CLAUDE.mdの自動更新（従来の手動コピー運用を廃止）
- BusinessAnalyzerスキル化対応（自己完結性の維持）
- 同期忘れによる不整合を防止

**動作確認**:
```bash
# Identities/WeaveIdentity.md を編集
echo "" >> Identities/WeaveIdentity.md

# ステージング
git add Identities/WeaveIdentity.md

# コミット時に自動同期が実行される
git commit -m "test"
# 🔄 Syncing WeaveIdentity.md to 2 locations...
# ✅ Synced: ../../.claude/CLAUDE.md
# ✅ Synced: Expertises/CorporateStrategist/BusinessAnalyzer/References/WeaveIdentity.md
```

## 🔄 フックの更新

フックスクリプトを更新する場合：

1. `.githooks/pre-commit` を編集
2. 変更をコミット・プッシュ

`core.hooksPath` が設定されていれば、次のコミット時から新しい版が即座に有効になります（コピー不要）。

## ⚠️ 注意事項

- `.githooks/` はバージョン管理されており、全員が同じフックを利用できます
- ただし `git config core.hooksPath` は `.git/config` に保存されるため、リポジトリcloneごとに再設定が必要です（最初のセットアップ時の一度のみ）
- 親環境 `../../.claude/CLAUDE.md` はリポジトリ管理外。別マシンでcloneした場合はパス先のファイル存在を確認してください

## 🚀 将来の拡張

必要に応じて追加可能なフック：
- `pre-push`: プッシュ前のテスト実行
- `commit-msg`: コミットメッセージの検証
- `post-commit`: コミット後の処理（通知など）

---

*Last Updated: 2026-04-17*
*Maintained by: Weave @ Homunculus-Weave*
