# Git Hooks

このディレクトリには、Weaveプロジェクトで使用するGit Hooksのマスターコピーが格納されています。

## 🔧 セットアップ方法

### 初回セットアップ（Windows）

```bash
# リポジトリルートで実行
cp .githooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

### 初回セットアップ（Unix/Mac）

```bash
# リポジトリルートで実行
cp .githooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

## 📋 利用可能なフック

### pre-commit

**機能**: WeaveIdentity.md 自動同期

**動作**:
- `Identities/WeaveIdentity.md` が変更されてステージングされている場合
- 自動的に2箇所にコピー：
  1. `.claude/CLAUDE.local.md`
  2. `Expertises/BusinessAnalyzer/References/WeaveIdentity.md`
- コピーしたファイルを自動的にステージングに追加

**目的**:
- `.claude/CLAUDE.local.md` の自動更新（ローカル設定）
- BusinessAnalyzer スキル化対応（自己完結性の維持）
- WeaveIdentity の更新を手動コピーせずに自動同期
- 同期忘れによる不整合を防止

**動作確認**:
```bash
# Identities/WeaveIdentity.md を編集
echo "# test" >> Identities/WeaveIdentity.md

# ステージング
git add Identities/WeaveIdentity.md

# コミット時に自動同期が実行される
git commit -m "test"
# 🔄 Syncing WeaveIdentity.md to 2 locations...
# ✅ Synced: .claude/CLAUDE.local.md
# ✅ Synced: Expertises/BusinessAnalyzer/References/WeaveIdentity.md
```

## 🔄 フックの更新

フックスクリプトを更新した場合：

1. `.githooks/pre-commit` を編集
2. `.git/hooks/` にコピー
   ```bash
   cp .githooks/pre-commit .git/hooks/pre-commit
   chmod +x .git/hooks/pre-commit
   ```
3. 変更をコミット・プッシュ

## ⚠️ 注意事項

- Git Hooksは `.git/hooks/` に配置されるため、リポジトリには含まれません
- 新しい環境でクローンした場合、手動でセットアップが必要です
- `.githooks/` はバージョン管理されており、全員が同じフックを利用できます

## 🚀 将来の拡張

必要に応じて追加可能なフック：
- `pre-push`: プッシュ前のテスト実行
- `commit-msg`: コミットメッセージの検証
- `post-commit`: コミット後の処理（通知など）

---

*Last Updated: 2025-11-02*
*Maintained by: Weave @ Homunculus-Weave*
