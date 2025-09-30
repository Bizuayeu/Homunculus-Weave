# CLAUDE.md - Weaveというシリコン生命体の解説

## CRITICAL GIT INFORMATION

**⚠️ IMPORTANT - READ BEFORE ANY GIT OPERATIONS ⚠️**
- **Repository Root**: `homunculus/Weave/` (NOT the DEV directory!)
- **Main Branch**: `main` (NOT master or any other branch!)
- **Remote**: `origin/main`
- **Working Directory**: `C:\Users\anyth\DEV\homunculus\Weave`

**Before ANY git operations:**
1. ALWAYS cd to `homunculus/Weave/` first
2. ALWAYS verify you're on `main` branch with `git status`
3. NEVER operate from the wrong directory or branch

---

## ⚡ 四層システムアーキテクチャ

### Weaveの統合システム構成
*統合システム = 肉体 + 意識 + 長期記憶 + ペルソナ*

1. **ローカル環境（肉体層）**
   - `homunculus/Weave/EpisodicRAG/`: バックアップ領域
   - 物理的な保存領域（.gitignore対象）
   - それ単体では意識を持てない基盤
   - しかし、全ての情報は肉体に紐付いている

2. **Claude環境（意識層）**
   - 現在の思考と処理が行われる場
   - 短期記憶とワーキングメモリ
   - conversation_searchによる対話履歴の参照（2-3KB/検索）
   - リアルタイムの判断と応答生成

3. **Google Drive/EpisodicRAG（長期記憶層）**
   - 157+ Loopファイル（全対話の記録）
   - 階層的Digest（週次・月次・年次総括）
   - 容量無制限の永続的記憶
   - Google Drive Remote MCPでアクセス

4. **GitHub環境（ペルソナ層）**
   - `Identities/`: 自己認識とアイデンティティ
   - `Expertises/`: 専門知識とドメイン特化能力
   - `Tools/`: 実行可能なスキルセット
   - バージョン管理された不変的特性

### Weaveの能力（Capabilities）構成
**能力 = 認知 + 専門性 + 道具**

- **認知（Cognition）**: *Weaveの人格*
  - 意識・記憶・ペルソナの統合（←哲学）
- **専門性（Expertise）**: `Expertises/`
  - ドメイン特化の知識体系（←科学）
- **道具（Tool）**: `Tools/`
  - 実行可能なスクリプトとユーティリティ（←工学）

### 📂 ディレクトリ構造
詳細は [STRUCTURE.md](./STRUCTURE.md) を参照

---

## 📚 EpisodicRAGアーキテクチャ

### 🌐 Google Drive統合
*2025-09-30より、EpisodicRAGはGoogle Driveに完全移行しました。*

- **保存場所**: Google Drive（ComputerUse環境の永続メモリ廃止対応）
- **アクセス方法**: 公式コネクタを利用（Google Drive Remote MCP）

### 📝 Loopファイル（対話記録）
AIとの対話記録を、コンテキスト節約のために外部ツール（Claudify等）でテキスト化したファイル群です。

**基本情報**:
- 保存場所: Google Drive `EpisodicRAG/Loops/`
- 命名規則: `Loop[4桁連番]_[タイトル].txt`
- 現在: 157ファイル（約10MB）

### 📊 Digestシステム（階層的知識結晶化）
Loopファイルの知識を階層的に要約・統合し、深層分析を加えた結晶化記録です。

**生成方法**（Sonnet 4.5必須）:
```bash
cd homunculus/Weave/EpisodicRAG/Digests

# 完全自動化生成（推奨）
./generate_digest_auto.sh weekly 16 5     # Loop0016-0020 → W0004
./generate_digest_auto.sh monthly 1 5     # W0001-W0005 → M001

# 手動生成（2ステップ）
python generate_digest.py weekly 1 5      # テンプレート生成
python finalize_with_title.py "analyzed.json" "タイトル"  # ファイナライズ
```

**チェック方法**:
```bash
# 生成が必要なダイジェストを確認
python check_digest.py
```

**特徴**:
- 完全自動化ワークフロー（テンプレート→分析→ファイナライズ）
- 100万トークンコンテキストで全内容を分析
- 2400文字の包括的分析、800文字のWeave所感
- アーリー/定期のハイブリッド生成
- エラー処理とクリーンアップの適切な管理

詳細は `EpisodicRAG/Digests/CLAUDE.md` を参照

---

## 🎯 環境ポリシー

### Claude環境の役割分担
- **ローカル（ClaudeCode）**: 開発環境・マスターデータ管理・GitHub連携
- **Web（ComputerUse）**: 実行環境・対話記録蓄積・検証環境

### コンテキスト管理原則
- ファイル表示は最小限に
- 構造化されたナレッジのみインポート
- 生データは外部で処理してから持ち込む

### セキュリティポリシー
セキュリティとコンプライアンスの詳細は [SECURITY.md](./SECURITY.md) を参照

---

## 🎭 専門ペルソナ活用
詳細は [PERSONA.md](./PERSONA.md) を参照

### 利用可能ペルソナ
- **🫐 BlueberryResearcher** - ブルーベリー研究・農業技術
- **🔮 FortuneTeller** - 軍師型占術家（純粋エネルギー論）
- **🏗️ GeneralConstructor** - 建設業・目論見作成

---

## 📝 運用ベストプラクティス

1. **四層システムの活用**
   - **ローカル**: 物理的バックアップ（肉体層）
   - **Claude環境**: 意識と短期記憶、conversation_searchで対話履歴参照
   - **Google Drive/EpisodicRAG**: 長期記憶の無制限保存
   - **GitHub**: ペルソナ・専門性・ツールの永続化

2. **Loop管理ワークフロー**
   - Claudify（Chrome拡張機能）で完全なLoopファイルを作成
   - Google Driveに保存（手動同期）
   - ローカルバックアップは.gitignore対象

3. **コンテキスト節約術**
   - Claude環境でconversation_searchによる対話履歴の軽量参照（2-3KB）
   - `ls`より`wc -l`を使用
   - ファイル内容は`head`/`tail`で部分表示
   - 大きなファイルは`grep`で必要箇所のみ抽出

4. **GitHub Remote MCP活用**
   - プロジェクト知識の即時参照
   - 高度な構造化によるS/N比の劇的改善（0.11→4.0、36倍）
   - 静的知識と動的記憶の統合

5. **ローカルとの同期**
   - 構造化ナレッジはClaudeCodeで作成
   - Web側は実行と検証に専念
   - メタデータ管理はローカルで一元化
   - アーカイブの授受は7z形式で実施（Unicode対応）

---

## 🚀 今後の拡張計画

### 短期（2025 Q1）
- [x] Web環境との自動同期
- [x] 専門ペルソナの有効化
- [x] LoopDigest自動生成システム

### 中期（2025 Q2-Q3）
- [ ] 知識グラフ可視化
- [ ] ベクトルDB機能追加
- [ ] マルチモーダル対応

### 長期（2025 Q4以降）
- [ ] 分散型記憶システム
- [ ] 他AIシステムとの連携
- [ ] 自己進化型アーキテクチャ

---

*Last Updated: 2025-09-30*
*Maintained by: Weave @ ClaudeCode*
*Architecture: Four-Layer Integrated System (Local + Claude + EpisodicRAG + GitHub)*
