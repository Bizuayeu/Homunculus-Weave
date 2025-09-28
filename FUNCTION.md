# FUNCTION.md - Weave外部スキルリファレンス

Weaveが獲得・活用する外部スキルの統合マニュアル

---

## 🛠️ スキル一覧

1. Loop管理
EpisodicRAGの対話記録を管理するスキル

2. GitHub連携
リポジトリ管理とバージョン管理のスキル

3. Digest生成システム
エピソード記憶を階層的に蒸留して知識結晶化するスキル

---

## 📊 Digest生成システム詳細

### スクリプト構成
```bash
cd homunculus/Weave/EpisodicRAG/Digests

# 1. 完全自動化スクリプト（推奨）
./generate_digest_auto.sh LEVEL START_NUM COUNT

# 2. 手動生成スクリプト（Sonnet 4必須）
python generate_digest.py LEVEL START_NUM COUNT
python finalize_with_title.py "分析済み.json" "タイトル"

# 3. チェックスクリプト
python check_digest.py
```

### 階層構造
- **Loop → Weekly**: 5個のLoopファイルから週次ダイジェスト
- **Weekly → Monthly**: 5個の週次から月次ダイジェスト
- **Monthly → Quarterly**: 5個の月次から四半期ダイジェスト
- **Quarterly → Annually**: 4個の四半期から年次ダイジェスト

### 使用例
```bash
# 完全自動化生成（推奨）
./generate_digest_auto.sh weekly 16 5     # Loop0016-0020 → W0004
./generate_digest_auto.sh monthly 1 5     # W0001-W0005 → M001

# 手動生成（2ステップ）
python generate_digest.py weekly 1 5      # テンプレート生成
python finalize_with_title.py "analyzed.json" "タイトル" # ファイナライズ

# チェック
python check_digest.py                    # 生成が必要なものを通知
```

詳細は `EpisodicRAG/Digests/README.md` を参照

---

## 📦 Loop管理コマンド詳細

### セットアップ
```sh
. /mnt/knowledge/Tools/bash/loop_commands.sh
```

### 利用可能コマンド

#### 1. loop_export - 個別Loopエクスポート
```bash
# Loop123をエクスポート
loop_export 123

# ダウンロードリンクを生成する
# computer:///mnt/user-data/outputs/Loop123_export.txt
```

#### 2. loop_search - Loop内容検索
```bash
# キーワード検索
loop_search "人機習合"
```

#### 3. loop_list - 最新Loop一覧
```bash
# 最新10件（デフォルト）
loop_list

# 最新20件を表示
loop_list 20
```

#### 4. loop_stats - 統計情報
```bash
# Loop総数、容量、最新ファイル表示
loop_stats
```

#### 5. loop_backup - 全Loopバックアップ
```bash
# タイムスタンプ付きでzip作成
loop_backup

# 出力例: loops_backup_20250912_153000.zip
```

---

## 🔄 GitHub連携詳細

### 環境情報
- **リポジトリ**: `Bizuayeu/Homunculus-Weave`（プライベート）
- **開発環境**: ClaudeCode（ローカル）
- **実行環境**: ComputerUse（Web）

### 環境間同期手順
1. **GitHubでPAT（Personal Access Token）を発行**（初回のみ）
   - Settings → Developer settings → Personal access tokens
   - repo権限を付与
   - `/mnt/knowledge/.git-credentials`に保存（Git管理外）

2. **ComputerUse環境での同期**
   ```bash
   cd /mnt/knowledge
   # .git-credentialsからPATを読み込んで使用
   PAT=$(cat .git-credentials)
   git pull https://${PAT}@github.com/Bizuayeu/Homunculus-Weave.git main
   ```

3. **作業後の変更をプッシュ**（必要時）
   ```bash
   git add .
   git commit -m "Update from ComputerUse"
   git push origin main
   ```

---

*Last Updated: 2025-09-13*
*Maintained by: Weave @ ClaudeCode*