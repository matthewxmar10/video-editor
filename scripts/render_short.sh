#!/usr/bin/env bash
# render_short.sh — render ONE short-form (9:16) SEGMENT from the current edit's plan.
#
# Short-form is ALWAYS a clip, NEVER the whole video (rendering a full vertical wastes
# resources and is never needed). Recommend Short ideas after a long-form render; render only
# an APPROVED segment here.
#
#   scripts/render_short.sh <name> <start_s> <end_s> [label]
#   e.g. scripts/render_short.sh Skep_Story 130 168 grandma-quote
#
# The video's plan must be the one currently built (src/methodology/officialTestBeatPlan.*);
# if it isn't, build it first with edit_video.sh (no --render).
set -euo pipefail

NAME="${1:?usage: render_short.sh <name> <start_s> <end_s> [label]}"
START="${2:?start seconds}"
END="${3:?end seconds}"
LABEL="$(printf '%s' "${4:-${START}-${END}}" | tr ' /' '__')"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
PLANJSON="src/methodology/officialTestBeatPlan.plan.json"
CUT="public/host/${NAME}-cut.mp4"

command -v ffmpeg >/dev/null || { echo "error: ffmpeg not on PATH"; exit 1; }
[ -f "$PLANJSON" ] || { echo "error: no plan built (run edit_video.sh for $NAME first)"; exit 1; }
grep -q "$NAME" "$PLANJSON" || { echo "error: the ACTIVE plan is not for '$NAME'. Build it first:  scripts/edit_video.sh <raw for $NAME>  (no --render)"; exit 1; }
[ -f "$CUT" ] || { echo "error: $CUT missing — build $NAME's plan first."; exit 1; }

DUR="$(python3 -c "print(round(float($END)-float($START), 2))")"
python3 -c "import sys; d=float($END)-float($START); sys.exit(0 if d>0 else 1)" \
  || { echo "error: end must be greater than start"; exit 1; }
# SAFETY RAIL: a Short is a CLIP. Refuse anything approaching full-length so a vertical
# full-render can never happen by accident.
python3 -c "import sys; sys.exit(0 if (float($END)-float($START))<=120 else 1)" \
  || { echo "error: ${DUR}s is too long for a Short — pick a <=120s clip. NEVER render the full video vertically."; exit 1; }

LO="$(python3 -c "print(int(round(float($START)*30)))")"
HI="$(python3 -c "print(int(round(float($END)*30)))")"
OUT="out/${NAME}-short-${LABEL}.mp4"

# Re-link the active channel's packs in their SHORT-FORM variant (falls back to the shared /
# long-form index.tsx when a pack has no dedicated vertical build). The channel is the one the
# active plan was built for, recorded by edit_video.sh.
ACTIVE_CHANNEL="$(cat script/.active-channel 2>/dev/null || true)"
node scripts/link_channel_packs.mjs --channel "$ACTIVE_CHANNEL" --format short-form >/dev/null
node scripts/build_anim_registry.mjs >/dev/null
PUB="$(mktemp -d)"; mkdir -p "$PUB/host" "$PUB/cutouts" "$PUB/fx" "$PUB/logos" "$PUB/photos" "$PUB/documents"
cp "$CUT" "$PUB/host/"
cp -R public/cutouts/. "$PUB/cutouts/" 2>/dev/null || true
cp -R public/fx/. "$PUB/fx/" 2>/dev/null || true
cp -R public/logos/. "$PUB/logos/" 2>/dev/null || true
cp -R public/photos/. "$PUB/photos/" 2>/dev/null || true
cp -R public/documents/. "$PUB/documents/" 2>/dev/null || true

printf '\n\033[1;36m▸ short-form 9:16  %s  (%ss, frames %s-%s) -> %s\033[0m\n' "$LABEL" "$DUR" "$LO" "$HI" "$OUT"
npx remotion render src/methodology/index.ts AutoReelVertical "$OUT" --frames="${LO}-${HI}" --crf=18 --public-dir="$PUB" --timeout=180000
rm -rf "$PUB"
printf '\n\033[1;32m✓ %s\033[0m\n' "$OUT"
