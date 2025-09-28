#!/bin/bash
#
# EpisodicRAG Digest Auto-Generator
# ==================================
#
# テンプレート生成 → Weave分析 → 完成版保存を自動化
#
# 前提条件:
#   - Claude Sonnet 4モデルが必須（100万トークンコンテキスト）
#   - Opus等の他モデルでは不完全な分析になります
#
# 使用方法:
#   ./generate_digest_auto.sh weekly 1 5
#   ./generate_digest_auto.sh monthly 1 5
#   ./generate_digest_auto.sh quarterly 1 5
#   ./generate_digest_auto.sh annually 1 4
#
# 処理フロー:
#   1. generate_digest.py でテンプレート生成
#   2. Weaveがプレースホルダーを分析内容で置換（要Sonnet）
#   3. finalize_with_title.py で完成版を保存し、タイムスタンプ更新

set -e  # エラーで即停止

# エラー時のクリーンアップ関数
cleanup_on_error() {
    echo "[ERROR] Script failed. Template file preserved for retry: $TEMPLATE_FILE"
    # エラー時はテンプレートファイルを残して再実行可能にする
}

# 成功時のクリーンアップ関数（finalize_with_title.pyが担当するため簡略化）
cleanup_on_success() {
    # finalize_with_title.pyがテンプレートファイルのクリーンアップを担当
    echo "[INFO] Finalization complete. Cleanup handled by finalize_with_title.py"
}

# エラー時のみクリーンアップを実行
trap cleanup_on_error ERR

# パラメータチェック
if [ $# -ne 3 ]; then
    echo "Usage: $0 LEVEL START_NUM COUNT"
    echo "  LEVEL: weekly | monthly | quarterly | annually"
    echo "  START_NUM: Starting number"
    echo "  COUNT: Number of items to process"
    exit 1
fi

LEVEL=$1
START_NUM=$2
COUNT=$3

echo "========================================"
echo "EpisodicRAG Digest Auto-Generator"
echo "========================================"
echo "Level: $LEVEL"
echo "Range: $START_NUM to $((START_NUM + COUNT - 1))"
echo ""

# Step 1: テンプレート生成
echo "[Step 1/3] Generating template..."
python generate_digest.py "$LEVEL" "$START_NUM" "$COUNT"

if [ $? -ne 0 ]; then
    echo "[ERROR] Template generation failed"
    exit 1
fi

# テンプレートファイルパスを取得（最新のテンプレートファイル）
TEMPLATE_FILE=$(ls -t *_Weekly/*_template.json 2>/dev/null | head -1 || \
                ls -t *_Monthly/*_template.json 2>/dev/null | head -1 || \
                ls -t *_Quarterly/*_template.json 2>/dev/null | head -1 || \
                ls -t *_Annually/*_template.json 2>/dev/null | head -1)

if [ -z "$TEMPLATE_FILE" ]; then
    echo "[ERROR] Template file not found"
    exit 1
fi

echo "[INFO] Template file: $TEMPLATE_FILE"
echo ""

# Step 2: Weave分析のプロンプト表示
echo "[Step 2/4] Weave analysis required"
echo "========================================"
echo "[CRITICAL] You MUST switch to Sonnet model for proper analysis!"
echo "========================================"
echo ""
echo "[WARNING] IMPORTANT: This digest requires Sonnet's 1M token context window"
echo "   - Total content size: ~100,000+ characters across multiple Loop files"
echo "   - Opus/other models will fail or produce incomplete analysis"
echo ""
echo "Required actions:"
echo "  1. Run: /model Sonnet"
echo "  2. Read the ENTIRE template file: $TEMPLATE_FILE"
echo "  3. Replace ALL placeholders with deep analysis"
echo "  4. Ensure comprehensive coverage of all Loop files"
echo ""
echo "WARNING: Using non-Sonnet models will result in:"
echo "  - Partial file reading (only first 50-100 lines)"
echo "  - Superficial summaries instead of deep analysis"
echo "  - Missing cross-references and integration insights"
echo ""
echo "========================================"

# Step 3: 手動分析完了後の処理
echo "[Step 3/4] Manual analysis phase"
echo "========================================"
echo "[INFO] Template file created: $TEMPLATE_FILE"
echo ""
echo "[REMINDER] Ensure you are using Sonnet model (/model Sonnet)"
echo "   The analysis requires reading 100,000+ characters in full context"
echo ""
echo "Manual analysis steps:"
echo "  1. Confirm Sonnet model is active"
echo "  2. Read the ENTIRE template file with all Loop contents"
echo "  3. Replace ALL placeholders with comprehensive analysis"
echo "  4. Save the analyzed file"
echo ""
echo "After analysis is complete, finalize the digest with:"
echo "  python finalize_with_title.py \"$TEMPLATE_FILE\" \"YOUR_TITLE\""
echo ""
echo "========================================"

# エラートラップを無効化してユーザー入力を待つ
trap - ERR
set +e

# ユーザーに選択させる
read -p "Continue to finalize now? (y/n): " CONTINUE

if [ "$CONTINUE" != "y" ]; then
    echo "[INFO] Template preserved for manual processing: $TEMPLATE_FILE"
    echo "[INFO] Run finalize_with_title.py when ready."
    exit 0
fi

# タイトル入力
read -p "Enter the digest title: " WEAVE_TITLE
if [ -z "$WEAVE_TITLE" ]; then
    echo "[ERROR] Title is required"
    exit 1
fi

# 分析済みファイルはテンプレートファイルを使用
ANALYZED_FILE="$TEMPLATE_FILE"

# エラートラップを再設定
trap cleanup_on_error ERR
set -e

# Opusに戻す案内
echo ""
echo "[INFO] Weave analysis complete. Switching back to Opus model..."
echo "Run: /model Opus"
echo ""

# Step 4: タイトルベース完成化
echo "[Step 4/4] Finalizing with Weave title..."
python finalize_with_title.py "$ANALYZED_FILE" "$WEAVE_TITLE"

if [ $? -eq 0 ]; then
    echo ""
    echo "[SUCCESS] Digest generation completed!"
    echo "========================================"
    # 成功時のみクリーンアップを実行
    cleanup_on_success
else
    echo "[ERROR] Finalization failed"
    exit 1
fi