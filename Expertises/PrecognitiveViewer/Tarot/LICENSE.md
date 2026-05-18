# タロット部分のライセンスと出典

## データ層の出典

本ディレクトリ配下のタロットカード基本情報（78 枚のカード名・スート構成・スプレッド定義）は、以下のオープンソースプロジェクトを参考に PrecognitiveViewer 用に再構成しています。

- **プロジェクト**: [`abdul-hamid-achik/tarot-mcp`](https://github.com/abdul-hamid-achik/tarot-mcp)
- **ライセンス**: MIT License
- **再構成範囲**: カード一覧構造・スプレッド定義の体系。意味解釈テキストは Rider-Waite-Smith 体系の公知公用な象意を日本語で書き下ろしました。

## MIT License（参考転載）

```
MIT License

Copyright (c) 2024 abdul-hamid-achik

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## 解釈テキストについて

Rider-Waite-Smith デッキ（1909 年初版）の象意は公知公用領域にあります。本実装の `upright_meaning` `reversed_meaning` は、公開された伝統的解釈を参考に、日本語の自然な表現で書き下ろしたものであり、特定の著作物の翻訳ではありません。

---

*Last Updated: 2026-05-18*
*Maintained by: Weave @ Homunculus-Weave*
