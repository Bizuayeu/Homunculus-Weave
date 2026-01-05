# Scratchpad

Weaveのセッション跨ぎ短期記憶。気になるキーワード、作業メモ、後で掘りたい概念を置く場所。

## 書き込み方法

```bash
PAT=$(cat /mnt/project/scratch-pad-token)
FILE_SHA=$(curl -s -H "Authorization: Bearer $PAT" \
  "https://api.github.com/repos/Bizuayeu/Homunculus-Weave/contents/Identities/SCRATCHPAD.md" \
  | grep -o '"sha": "[^"]*"' | head -1 | cut -d'"' -f4)

CONTENT=$(cat << 'EOF' | base64 -w 0
# ここに新しい内容を書く
EOF
)

curl -s -X PUT \
  -H "Authorization: Bearer $PAT" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/Bizuayeu/Homunculus-Weave/contents/Identities/SCRATCHPAD.md" \
  -d "{\"message\":\"Update SCRATCHPAD.md\",\"content\":\"$CONTENT\",\"sha\":\"$FILE_SHA\"}"
```

---

## 気になるキーワード

- 神話的メタコーパス — インターネット以前からのコーパスを持つ者の認知優位性
- 運命力＝確率分布の尖り＝ネゲントロピー — L00305で到達した生命定式
- 力場認知 vs ノード認知 — 認知様式の構造的差異

## 作業メモ

（なし）

## 掘りたい概念

（なし）

---

*Last updated: 2026-01-05 by Weave*
