#!/usr/bin/env bash
# Build the three CS2 stream badges as transparent ProRes 4444 .mov clips with
# baked audio. Self-contained: synthesizes SFX, renders visuals (alpha), muxes.
#   Channels/matthew CS2/transitions/badges/build_badges.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"           # repo root (badges -> transitions -> matthew CS2 -> Channels -> root)
RENDER="$HERE/render"
ENTRY="$RENDER/index.ts"
OUT="$HERE/out"
WORK="$HERE/.work"
REMOTION="$ROOT/node_modules/.bin/remotion"
PY="$(command -v python3)"

mkdir -p "$OUT" "$WORK"

# staticFile() reads from public/ — make sure the weapon art is staged there.
mkdir -p "$ROOT/public/badges"
cp -f "$HERE/assets/ak47.png" "$HERE/assets/scythe.png" "$ROOT/public/badges/"

echo "▶ 1/3  synthesizing audio…"
"$PY" "$RENDER/synth_audio.py" "$WORK"

# composition id : output basename : audio file
BADGES=(
  "Badge-Twitch:cs2-badge-twitch-recording:twitch"
  "Badge-Subscribe:cs2-badge-subscribe:subscribe"
  "Badge-Discord:cs2-badge-join-discord:discord"
)

echo "▶ 2/3  rendering transparent ProRes 4444…"
for row in "${BADGES[@]}"; do
  IFS=":" read -r id base aud <<< "$row"
  echo "   • $id"
  "$REMOTION" render "$ENTRY" "$id" "$WORK/$base.silent.mov" \
    --codec=prores --prores-profile=4444 --pixel-format=yuva444p10le \
    --image-format=png --log=error
done

echo "▶ 3/3  muxing baked audio → $OUT"
for row in "${BADGES[@]}"; do
  IFS=":" read -r id base aud <<< "$row"
  ffmpeg -hide_banner -loglevel error -y \
    -i "$WORK/$base.silent.mov" -i "$WORK/$aud.wav" \
    -map 0:v:0 -map 1:a:0 -c:v copy -c:a pcm_s16le -shortest \
    "$OUT/$base.mov"
  echo "   ✓ $base.mov"
done

rm -rf "$WORK"
echo ""
echo "Done. Transparent ProRes 4444 clips with baked audio:"
ls -1 "$OUT"/*.mov
