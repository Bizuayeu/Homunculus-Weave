#!/bin/bash

# Loop管理コマンドセット - /mnt/knowledge版
# EpisodicRAG Loop管理のための便利関数集

LOOP_DIR="/mnt/knowledge/EpisodicRAG/Loops"
OUTPUT_DIR="/mnt/user-data/outputs"

# 1. loop_export - 個別Loopエクスポート
loop_export() {
    if [ $# -lt 1 ]; then
        echo "使用法: loop_export <番号>"
        return 1
    fi

    local loop_num=$1
    local source_file=$(ls "$LOOP_DIR"/Loop${loop_num}_*.txt 2>/dev/null | head -n 1)

    if [ -z "$source_file" ]; then
        echo "❌ Loop${loop_num} が見つかりません"
        return 1
    fi

    local export_file="$OUTPUT_DIR/Loop${loop_num}_export.txt"
    cp "$source_file" "$export_file"

    echo "✅ エクスポート完了:"
    echo "   computer://$export_file"
}

# 2. loop_search - Loop内容検索
loop_search() {
    if [ $# -lt 1 ]; then
        echo "使用法: loop_search <検索キーワード>"
        return 1
    fi

    local keyword=$1
    echo "🔍 '$keyword' を検索中..."
    echo "───────────────────"

    grep -l "$keyword" "$LOOP_DIR"/Loop*.txt 2>/dev/null | while read -r file; do
        echo "📄 $(basename "$file" .txt)"
        grep -n "$keyword" "$file" | head -3 | sed 's/^/   /'
        echo ""
    done
}

# 3. loop_list - 最新Loop一覧
loop_list() {
    local num=${1:-10}
    echo "📋 最新 $num 件のLoop:"

    ls -t "$LOOP_DIR"/Loop*.txt 2>/dev/null | head -n "$num" | while read -r file; do
        echo "  $(basename "$file" .txt)"
    done
}

# 4. loop_stats - 統計情報
loop_stats() {
    echo "📊 Loop統計情報:"
    echo "───────────────────"

    local total_files=$(ls "$LOOP_DIR"/Loop*.txt 2>/dev/null | wc -l)
    local total_size=$(du -sh "$LOOP_DIR" 2>/dev/null | cut -f1)
    local latest_file=$(ls -t "$LOOP_DIR"/Loop*.txt 2>/dev/null | head -n 1)

    echo "総Loop数: $total_files"
    echo "合計サイズ: $total_size"

    if [ -n "$latest_file" ]; then
        echo "最新Loop: $(basename "$latest_file" .txt)"
        echo "最終更新: $(stat -c '%y' "$latest_file" | cut -d' ' -f1,2)"
    fi
}

# 5. loop_backup - 全Loopバックアップ
loop_backup() {
    local timestamp=$(date '+%Y%m%d_%H%M%S')
    local backup_file="$OUTPUT_DIR/loops_backup_${timestamp}.tar.gz"

    echo "⏳ バックアップ作成中..."
    tar -czf "$backup_file" -C "$(dirname "$LOOP_DIR")" "Loops" 2>/dev/null

    if [ $? -eq 0 ]; then
        echo "✅ バックアップ完了:"
        echo "   computer://$backup_file"
        echo "   サイズ: $(du -h "$backup_file" | cut -f1)"
    else
        echo "❌ バックアップ失敗"
        return 1
    fi
}



# 環境チェック
if [ ! -d "$LOOP_DIR" ]; then
    echo "⚠️  警告: Loop ディレクトリが見つかりません: $LOOP_DIR"
fi

if [ ! -d "$OUTPUT_DIR" ]; then
    mkdir -p "$OUTPUT_DIR" 2>/dev/null
fi

echo "✅ Loop管理コマンドが利用可能になりました"
echo "利用可能なコマンド: loop_export, loop_search, loop_list, loop_stats, loop_backup"