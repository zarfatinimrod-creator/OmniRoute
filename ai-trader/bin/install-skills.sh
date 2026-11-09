#!/usr/bin/env bash
# Install the AI-trader skills and agents into the user's Claude config (run at the start of a session).
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$HOME/.claude/skills" "$HOME/.claude/agents"
cp -r "$here/skills/." "$HOME/.claude/skills/"
cp "$here/agents/"*.md "$HOME/.claude/agents/"
pip install -q -r "$here/requirements.txt" 2>/dev/null || true
echo "installed: $(ls "$here/skills" | tr '\n' ' ')"
