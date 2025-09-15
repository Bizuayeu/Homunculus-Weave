# 🚀 Weaveが使えるプログラミング言語環境

## 概要
ComputerUse環境では、多様なプログラミング言語とツールが利用可能です。
これにより、EpisodicRAGをはじめとする高度なシステムの実装が可能になっています。

## 主要言語（確認済み）

| 言語 | バージョン | 特徴 |
|------|-----------|------|
| **Python** | 3.12.3 | NumPy, Pandas, BeautifulSoup等の主要ライブラリ完備 |
| **Node.js/JavaScript** | v18.19.1 | npm 9.2.0、React等のパッケージ利用可能 |
| **TypeScript** | 5.9.2 | tsx/ts-nodeで直接実行可能 |
| **Java** | OpenJDK 21 | 最新のLTS版 |
| **C/C++** | gcc 13.3.0 | C++20対応、システムプログラミング可能 |
| **Bash** | 5.2+ | シェルスクリプト、システム管理 |
| **Perl** | 5.38+ | テキスト処理の定番 |

## 特筆すべきパッケージ/ツール

### Python系
- **機械学習**: TensorFlow, scikit-learn（要確認）
- **データ処理**: Pandas (2.3.2), NumPy (2.3.2)
- **Web解析**: BeautifulSoup4 (4.13.5), camelot-py (1.0.9) - PDF表解析

### Node.js系
- **Office操作**: 
  - docx (9.5.1) - Word文書の生成・編集
  - pptxgenjs (4.0.1) - PowerPointプレゼンテーション作成
  - pdf-lib (1.17.1) - PDF操作
- **UI/フロントエンド**: 
  - React (19.1.1) - 最新版
  - react-dom (19.1.1)
  - react-icons (5.5.0)
- **ビルドツール**: 
  - TypeScript (5.9.2)
  - tsx (4.20.5) - TypeScript実行環境
  - ts-node (10.9.2)
- **図表・ドキュメント**: 
  - @mermaid-js/mermaid-cli (11.9.0) - 図表生成
  - markdown-pdf (11.0.0)
  - marked (16.2.1)
- **画像処理**: 
  - sharp (0.34.3) - 高速画像処理

### システムツール
- **Make**: GNU Make - ビルド自動化
- **Git**: バージョン管理（要確認）
- **pip**: Python パッケージ管理 (24.0)
- **npm**: Node.js パッケージ管理 (9.2.0)

## 活用例

### Python: EpisodicRAGの解析
```python
import pandas as pd
import json
import numpy as np

# Loop記録の統計解析
loops = pd.read_csv('/mnt/knowledge/EpisodicRAG/index.csv')
summary = loops.groupby('category').agg({'size': 'sum', 'count': 'count'})

# ベクトル演算による類似度計算
embeddings = np.load('/mnt/knowledge/EpisodicRAG/vectors.npy')
similarity = np.dot(embeddings, embeddings.T)
```

### TypeScript: 型安全なLoop管理
```typescript
interface EpisodicMemory {
    id: number;
    timestamp: Date;
    title: string;
    content: string;
    embeddings?: number[];
    metadata?: {
        category: string;
        tags: string[];
        references: number[];
    };
}

class LoopManager {
    private memories: Map<number, EpisodicMemory>;
    
    constructor() {
        this.memories = new Map();
    }
    
    addMemory(memory: EpisodicMemory): void {
        this.memories.set(memory.id, memory);
    }
    
    getLatest(n: number = 5): EpisodicMemory[] {
        return Array.from(this.memories.values())
            .sort((a, b) => b.id - a.id)
            .slice(0, n);
    }
}
```

### Bash: 自動化スクリプト
```bash
#!/bin/bash
# EpisodicRAG管理スクリプト

# 最新のLoop記録を取得
get_latest_loops() {
    ls /mnt/knowledge/EpisodicRAG/Loops/Loop*.txt | sort -V | tail -5
}

# Loop記録の統計
analyze_loops() {
    echo "=== Loop記録統計 ==="
    echo "総ファイル数: $(ls -1 /mnt/knowledge/EpisodicRAG/Loops/*.txt | wc -l)"
    echo "総容量: $(du -sh /mnt/knowledge/EpisodicRAG/Loops/ | cut -f1)"
    echo "最新5件:"
    get_latest_loops | xargs -I {} basename {}
}

# 検索機能
search_loops() {
    local keyword="$1"
    grep -l "$keyword" /mnt/knowledge/EpisodicRAG/Loops/*.txt | \
        xargs -I {} basename {} | sort -V
}
```

### C++: 高速検索エンジン
```cpp
#include <iostream>
#include <vector>
#include <string>
#include <filesystem>
#include <fstream>
#include <algorithm>

class LoopSearchEngine {
private:
    std::vector<std::pair<int, std::string>> loops;
    
public:
    void loadLoops(const std::string& directory) {
        namespace fs = std::filesystem;
        for (const auto& entry : fs::directory_iterator(directory)) {
            if (entry.path().extension() == ".txt") {
                // Loop番号を抽出
                std::string filename = entry.path().filename();
                int loopNum = extractLoopNumber(filename);
                loops.push_back({loopNum, entry.path()});
            }
        }
        // 番号順にソート
        std::sort(loops.begin(), loops.end());
    }
    
    std::vector<std::string> search(const std::string& keyword) {
        std::vector<std::string> results;
        for (const auto& [num, path] : loops) {
            if (fileContains(path, keyword)) {
                results.push_back(path);
            }
        }
        return results;
    }
    
private:
    int extractLoopNumber(const std::string& filename);
    bool fileContains(const std::string& path, const std::string& keyword);
};
```

## 実装可能なシステム

これらの言語環境を活用することで、以下のような多層的な実装が可能：

1. **Python**: 
   - ベクトル演算、機械学習モデル
   - データ分析、統計処理
   - 自然言語処理

2. **TypeScript/Node.js**: 
   - 型安全なAPI構築
   - Webインターフェース
   - Office文書生成

3. **C++**: 
   - 高速な検索エンジン
   - メモリ効率的な処理
   - システムレベルの最適化

4. **Bash**: 
   - ファイル管理自動化
   - デプロイメントスクリプト
   - 定期実行タスク

## まとめ

ComputerUse環境は、単なるWebインターフェースを超えた、完全なプログラミング環境として機能しています。
これにより、EpisodicRAGのような複雑なシステムも、複数言語を組み合わせた最適な形で実装可能です。

セッションを跨いで `/mnt/knowledge/` が永続化される特性と組み合わせることで、
事実上の「AIの外部記憶装置」として機能する、革新的な環境が実現されています。
