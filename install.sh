#!/usr/bin/env bash
# install.sh — make the token-saver available in every Claude Code session.
# Shows each step before doing it. Re-run any time; it's idempotent.
#
#   1. symlinks prep-video / prep-images into ~/bin
#   2. symlinks the skill into ~/.claude/skills/token-saver
#   3. (macOS) compiles mac/vision.swift to ~/bin/vision for faster OCR
#   4. prints the hook snippet for ~/.claude/settings.json (it doesn't edit that file for you)

set -euo pipefail
REPO=$(cd "$(dirname "$0")" && pwd)
BIN=${BIN:-$HOME/bin}

ask() { printf '%s [y/N] ' "$1"; read -r a; [ "$a" = y ] || [ "$a" = Y ]; }

echo "Token saver install — repo: $REPO"
echo

missing=""
for t in ffmpeg ffprobe python3; do command -v $t >/dev/null || missing="$missing $t"; done
[ -z "$missing" ] || echo "Missing:$missing  (macOS: brew install ffmpeg)"
if ! python3 -c 'import mlx_whisper' 2>/dev/null && ! python3 -c 'import faster_whisper' 2>/dev/null && ! python3 -c 'import whisper' 2>/dev/null; then
  echo "No Whisper found — transcripts will be skipped. Apple Silicon: pip3 install mlx-whisper   Intel: pip3 install faster-whisper"
fi
echo

if ask "1. Link prep-video and prep-images into $BIN?"; then
  mkdir -p "$BIN"
  ln -sf "$REPO/scripts/prep-video" "$BIN/prep-video"
  ln -sf "$REPO/scripts/prep-images" "$BIN/prep-images"
  case ":$PATH:" in *":$BIN:"*) ;; *) echo "   note: $BIN isn't on your PATH — add: export PATH=\"$BIN:\$PATH\"" ;; esac
fi

if ask "2. Link the token-saver skill into ~/.claude/skills?"; then
  mkdir -p "$HOME/.claude/skills"
  ln -sfn "$REPO/.claude/skills/token-saver" "$HOME/.claude/skills/token-saver"
fi

if [ "$(uname)" = Darwin ] && command -v swiftc >/dev/null; then
  if ask "3. Compile mac/vision.swift to $BIN/vision?"; then
    mkdir -p "$BIN"
    swiftc -O "$REPO/mac/vision.swift" -o "$BIN/vision" && echo "   built $BIN/vision"
  fi
fi

cat <<EOF

4. To block raw video/audio reads in every project, add this to ~/.claude/settings.json
   (merge into an existing "hooks" block if you have one):

{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Read",
        "hooks": [ { "type": "command", "command": "$REPO/scripts/hooks/guard-media.sh" } ]
      }
    ]
  }
}

Done. Try:  prep-video ~/Movies/some-clip.mov
EOF
