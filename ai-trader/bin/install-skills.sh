#!/usr/bin/env bash
# Install the AI-trader skills and agents into the user's Claude config (run at the start of every session).
# Order: Jake Schincariol's Trader skill v1, then v2 on top (6 shared names, v2 is newer), then our own skills.
# trader-broker is never installed: it walks Claude into placing broker orders, and this bot is paper-only.
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
dst="$HOME/.claude/skills"
mkdir -p "$dst" "$HOME/.claude/agents"
for pack in jake-trader-skill-v1 jake-trader-skill-v2; do
  for d in "$here/vendor/$pack"/trader-*/; do
    name="$(basename "$d")"
    [ "$name" = "trader-broker" ] && continue
    rm -rf "${dst:?}/$name" && cp -r "$d" "$dst/$name"
  done
done
for d in "$here/skills"/*/; do
  name="$(basename "$d")"
  rm -rf "${dst:?}/$name" && cp -r "$d" "$dst/$name"
done
cp "$here/agents/"*.md "$HOME/.claude/agents/"
python3 -m pip install -q -r "$here/requirements.txt" 2>/dev/null || pip install -q -r "$here/requirements.txt" 2>/dev/null || true
echo "installed skills: $(ls "$dst" | tr '\n' ' ')"
