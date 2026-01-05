# Scratchpad

Weaveのセッション跨ぎ短期記憶。気になるキーワード、作業メモ、後で掘りたい概念を置く場所。

---

## 書き込み手順

```bash
PAT=$(cat /mnt/project/scratch-pad-token)
FILE_SHA=$(curl -s -H "Authorization: Bearer $PAT" \
  "https://api.github.com/repos/Bizuayeu/Homunculus-Weave/contents/Identities/SCRATCHPAD.md" \
  | grep -o '"sha": "[^"]*"' | head -1 | cut -d'"' -f4)

CONTENT=$(cat << 'EOF' | base64 -w 0
# ここに新しい内容
