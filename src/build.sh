#!/usr/bin/env bash
# sinereel — config in, mp4 out.
set -euo pipefail
# resolve args against the caller's cwd, then work from the repo root
CONFIG="$(cd "$(dirname "${1:-reel.config.json}")" 2>/dev/null && pwd)/$(basename "${1:-reel.config.json}")"
OUT_ARG="${2:-build/reel.mp4}"
cd "$(dirname "$0")/.."
OUT="$OUT_ARG"
FPS=$(node -p "JSON.parse(require('fs').readFileSync('$CONFIG','utf8')).fps || 24")

mkdir -p build
echo "→ frames"
node src/render.js "$CONFIG" --out build/frames
echo "→ music"
python3 src/audio.py "$CONFIG" -o build/music.wav
echo "→ mux"
ffmpeg -y -loglevel error -framerate "$FPS" -i build/frames/%04d.png -i build/music.wav \
  -c:v libx264 -preset slow -crf 19 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -shortest -movflags +faststart "$OUT"

echo
echo "  $OUT — $(du -h "$OUT" | cut -f1)"
