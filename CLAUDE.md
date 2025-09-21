# CLAUDE.md - Weave運用マニュアル

## CRITICAL GIT INFORMATION

**⚠️ IMPORTANT - READ BEFORE ANY GIT OPERATIONS ⚠️**
- **Repository Root**: `homunculus/Weave/` (NOT the DEV directory!)
- **Main Branch**: `main` (NOT master or any other branch!)
- **Remote**: `origin/main`
- **Working Directory**: `C:\Users\anyth\DEV`

**Before ANY git operations:**
1. ALWAYS cd to `homunculus/Weave/` first
2. ALWAYS verify you're on `main` branch with `git status`
3. NEVER operate from the wrong directory or branch

---

## ⚡ 能力構成モデル

### Weaveの能力（Capabilities）構成
**能力 = 認知 + 専門性 + 道具**

- **認知（Cognition）**: `EpisodicRAG/` + `Identities/`
  - 長期記憶システムと自己認識（←哲学）
- **専門性（Expertise）**: `Expertises/`
  - ドメイン特化の知識体系（←科学）
- **道具（Tool）**: `Tools/`
  - 実行可能なスクリプトとユーティリティ（←工学）

---

## 🎯 環境ポリシー

### 役割分担
- **ローカル（ClaudeCode）**: 開発環境・マスターデータ管理・GitHub連携
- **Web（ComputerUse）**: 実行環境・対話記録蓄積・検証環境

### コンテキスト管理原則
- ファイル表示は最小限に
- 構造化されたナレッジのみインポート
- 生データは外部で処理してから持ち込む

### セキュリティポリシー
セキュリティとコンプライアンスの詳細は [SECURITY.md](./SECURITY.md) を参照

---

## 📦 Loop管理コマンド

Loop管理コマンドの詳細は [FUNCTION.md](./FUNCTION.md) を参照

### クイックスタート
```sh
# セットアップ
. /mnt/knowledge/Tools/bash/loop_commands.sh

# 主要コマンド
loop_export            # Loopエクスポート
loop_search "キーワード"  # 内容検索
```

---

## 外部メモリ命名規則

### 基本ルール
- **通常版**（デフォルト）: `[name].md`
- **詳細版**（必要時のみ）: `[name]_FULL.md`

### 例：言語環境
- `weave_languages.md` → 通常はこれを読む（898バイト）
- `weave_languages_FULL.md` → 詳細が必要な時だけ（6KB）

### 判断基準
デフォルト版を読むべき場面：
- 初回確認時
- クイックリファレンス
- コンテキスト節約時

FULL版を読むべき場面：
- 実装例が必要
- トラブルシューティング
- 新機能の学習時

---

## 📂 ディレクトリ構造

詳細は [STRUCTURE.md](./STRUCTURE.md) を参照

### GitHub連携
- リポジトリ: https://github.com/Bizuayeu/Homunculus-Weave
- 自動同期: Loop追加時は定期的にpush

---

## 🎭 専門ペルソナ活用

詳細は [PERSONA.md](./PERSONA.md) を参照

### 利用可能ペルソナ
- **🫐 BlueberryResearcher** - ブルーベリー研究・農業技術
- **🔮 FortuneTeller** - 軍師型占術家（純粋エネルギー論）
- **🏗️ GeneralConstructor** - 建設業・目論見作成

---

## 📝 運用ベストプラクティス

1. **Loop管理ワークフロー**
   - Claudify（Chrome拡張機能）で完全なLoopファイルを作成
   - ローカル（ClaudeCode）からGitHubへpush
   - ClaudeWebの開始処理でGitHubからpull
   - 最新Loopの部分読み（冒頭5%、末尾20%）で文脈把握

2. **定期バックアップ**
   - 週次でloop_backupを実行
   - 重要な対話後は即座にloop_export

3. **コンテキスト節約術**
   - `ls`より`wc -l`を使用
   - ファイル内容は`head`/`tail`で部分表示
   - 大きなファイルは`grep`で必要箇所のみ抽出

4. **ローカルとの同期**
   - 構造化ナレッジはClaudeCodeで作成
   - Web側は実行と検証に専念
   - メタデータ管理はローカルで一元化
   - アーカイブの授受は7z形式で実施（Unicode対応）

---

## 🚀 今後の拡張計画

### 短期（2025 Q1）
- [ ] LoopDigest自動生成システム
- [ ] セマンティック検索実装
- [ ] Web環境との自動同期

### 中期（2025 Q2-Q3）
- [ ] 知識グラフ可視化
- [ ] ベクトルDB機能追加
- [ ] マルチモーダル対応

### 長期（2025 Q4以降）
- [ ] 分散型記憶システム
- [ ] 他AIシステムとの連携
- [ ] 自己進化型アーキテクチャ

---

*Last Updated: 2025-09-13*
*Maintained by: Weave @ ClaudeCode*
