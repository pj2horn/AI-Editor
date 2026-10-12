#!/usr/bin/env bash
# PreToolUse hook for Read: stop Claude opening raw video/audio and point it
# at the prep scripts instead. Exit 2 = block the call and show Claude stderr.
# Set TOKEN_SAVER_OFF=1 to disable.

[ "${TOKEN_SAVER_OFF:-0}" = 1 ] && exit 0
path=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))' 2>/dev/null)
PV=$(command -v prep-video 2>/dev/null || echo "$(cd "$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")/.." && pwd)/prep-video")
ext=$(echo "${path##*.}" | tr '[:upper:]' '[:lower:]')

case $ext in
  mp4|mov|m4v|mkv|avi|webm|mxf|braw|r3d|mts)
    echo "Don't read raw video. Run: $PV \"$path\"  then read the summary.md it prints (plus sheet.jpg / hook.jpg only if you need the picture)." >&2
    exit 2 ;;
  wav|mp3|m4a|aac|aif|aiff|flac)
    echo "Don't read raw audio. Run: $PV \"$path\"  (works on audio-only files too) and read summary.md / transcript.txt." >&2
    exit 2 ;;
esac
exit 0
