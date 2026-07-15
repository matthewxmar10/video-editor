#!/usr/bin/env bash
# edit_video.sh — one raw host recording -> a finished, beat-matched AutoReel edit.
# Deterministic + repeatable: same recording => same edit. The renderer (AutoReel) is generic;
# the generated plan carries this video's source/face-anchor/cutout, so NOTHING here is
# hand-edited per video.
#
#   scripts/edit_video.sh <raw.mp4> [face_x]              builds the plan + BEAT MAP, then STOPS
#   scripts/edit_video.sh <raw.mp4> [face_x] --render      also renders + runs both gates
#
# HARD RULE (Ryan 2026-07-01): never render on the first pass. Read the beat map — what's
# SAID, what's SHOWN, what MOTION plays, what the TRANSITION is — for every beat. If a row
# looks wrong (stray words, wrong device, a beat too long), fix the devices cache or the
# script alignment and re-run WITHOUT --render. Only pass --render once the beat map reads
# right. A render that "looks fine" is not proof; a beat map you actually read is.
#
# Device choices (which line becomes a card/quote/glide/stat...) resolve in build_matched_plan via
# classify_beats_llm: a committed <stem>-devices.json cache -> Claude API -> rule-based fallback.
# For a script-driven cut (phrases from a writer's script, not just whisperX punctuation), drop
# the script at script/<name>.txt and this passes --script automatically if it exists.
set -euo pipefail

RAW="${1:?usage: edit_video.sh <raw.mp4> [face_x] [--render]}"
FACE_X=960
DO_RENDER=0
for a in "${@:2}"; do
  if [ "$a" = "--render" ]; then DO_RENDER=1; else FACE_X="$a"; fi
done
# Short-form is NEVER auto-rendered here (and never a full-length vertical). After the
# long-form render, recommend Short IDEAS; render only an approved SEGMENT with render_short.sh.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

NAME="$(basename "$RAW")"; NAME="${NAME%.*}"           # e.g. mytalk

# PER-CHANNEL config: a recording under Channels/<name>/ is edited by THAT channel's rules —
# its style.json drives the engine knobs (via CONTENT_ENGINE_PREFS) and its guidelines.md is
# the editorial brief the operator reads. Recordings outside Channels/ use the global default.
CHANNEL="$(printf '%s' "$RAW" | sed -n 's#.*Channels/\([^/]*\)/.*#\1#p')"
if [ -n "$CHANNEL" ] && [ -f "Channels/$CHANNEL/style.json" ]; then
  export CONTENT_ENGINE_PREFS="Channels/$CHANNEL/style.json"
  printf '\n\033[1;36mChannel: %s\033[0m  (knobs: Channels/%s/style.json — READ Channels/%s/guidelines.md before editing)\n' "$CHANNEL" "$CHANNEL" "$CHANNEL"
fi

# Make THIS channel's own transition packs (Channels/<name>/transitions/) discoverable, and
# clear any left over from a different channel. This runs BEFORE the plan is built (step 4)
# so the device picker sees the channel's packs, and the fresh registry below feeds the render
# too. A recording outside Channels/ (empty CHANNEL) just clears prior channel copies.
node scripts/link_channel_packs.mjs --channel "$CHANNEL" --format long-form
node scripts/build_anim_registry.mjs   # rebuild catalog+registry so the plan builder sees the linked packs
mkdir -p script; printf '%s' "$CHANNEL" > script/.active-channel   # so render_short.sh can pick the short-form variant

CUT="public/host/${NAME}-cut.mp4"                       # stem: <NAME>-cut  (SRC derives from it)
BASEJSON="script/word-timings/${NAME}-wx.json"
WX="script/word-timings/${NAME}-cut-wx.json"
PLAN="src/methodology/officialTestBeatPlan.ts"
BEATMAP="script/${NAME}-beatmap.md"
SCRIPT_TXT="script/${NAME}.txt"
OUT="out/${NAME}.mp4"
WHISPERX="$HOME/.venvs/whisperx/bin/python"

say(){ printf '\n\033[1;33m▸ %s\033[0m\n' "$*"; }

# preflight: fail with a one-line fix instead of a cryptic error mid-run
[ -x "$WHISPERX" ] || { printf '\n\033[1;31merror:\033[0m whisperX not found at %s\nRun first:  bash scripts/setup.sh\n' "$WHISPERX"; exit 1; }
command -v ffmpeg >/dev/null || { printf '\n\033[1;31merror:\033[0m ffmpeg not on PATH (needed for the cut + render).\nInstall it, e.g.:  brew install ffmpeg\n'; exit 1; }

# One transcription stack (whisperx venv) for BOTH passes. Step 1: a FAST faster-whisper pass
# on the raw take — punctuated word times to locate silences AND flub 'reset reset' cues for
# the dead-space cut (precision doesn't matter yet, punctuation does). Step 3: whisperX wav2vec2
# alignment on the CUT for the 10-20ms beat anchors.
say "1/6  transcribe the raw take (faster-whisper, --fast) — word times for the dead-space cut"
"$WHISPERX" scripts/word_align_x.py "$RAW" --fast

say "2/6  cut dead space -> $CUT   (HARD RULE: every cut lands in a silence, dual-threshold checked)"
python3 scripts/hostcut_plan.py "$RAW" --words "$BASEJSON" --render "$CUT"

say "3/6  whisperX align the cut -> $WX  (10-20ms word times = beat anchors)"
"$WHISPERX" scripts/word_align_x.py "$CUT"

# GREEN-SCREEN channels (bloomers): key the host off its green screen so it composites over the
# animated flower background at render. Produces public/host/<name>-cut-keyed.mov — the exact
# path the plan's GREENSCREEN.src points at (build_matched_plan derives it from the cut).
KEYED=""; GS_PREFIX=""
if [ -n "${CONTENT_ENGINE_PREFS:-}" ]; then
  GS="$(python3 - "$CONTENT_ENGINE_PREFS" <<'PY'
import json, sys, os
try: d = json.load(open(sys.argv[1]))
except Exception: d = {}
g = d.get('greenScreen') or {}
if g.get('enabled') and g.get('background'):
    print('%s\t%s' % (g.get('frameZoom', 1.0), g['background']))
PY
)"
  if [ -n "$GS" ]; then
    GS_ZOOM="${GS%%$'\t'*}"; GS_BG="${GS#*$'\t'}"; GS_PREFIX="${GS_BG%%/*}"
    KEYED="public/host/${NAME}-cut-keyed.mov"
    say "3b/6  green screen — key the host + stage the flower background (channel: $CHANNEL)"
    mkdir -p "public/${GS_PREFIX}/flowers"
    cp "Channels/${CHANNEL}/backgrounds/base.png" "public/${GS_PREFIX}/base.png" 2>/dev/null || true
    cp Channels/"${CHANNEL}"/backgrounds/flowers/*.png "public/${GS_PREFIX}/flowers/" 2>/dev/null || true
    TMP1080="$(mktemp -t gskey).mp4"
    ffmpeg -y -loglevel error -i "$CUT" -vf scale=1920:1080 -r 30 -c:v libx264 -crf 18 -c:a copy "$TMP1080"
    python3 scripts/greenscreen_key.py "$TMP1080" "$KEYED" --frame-zoom "$GS_ZOOM"
    rm -f "$TMP1080"
  fi
fi

say "4/6  build the beat plan (auto device per sentence, snapped to silence)"
# no arrays: expanding an EMPTY array under `set -u` is an error on macOS's bash 3.2 —
# the no-script path (a buyer's first run) died here (caught by the proof run, 2026-07-02)
if [ -f "$SCRIPT_TXT" ]; then
  echo "  using writer's script: $SCRIPT_TXT (phrase-level cut)"
  python3 scripts/build_matched_plan.py "$WX" "$PLAN" --face-x "$FACE_X" --script "$SCRIPT_TXT"
else
  echo "  no script/$NAME.txt — sentence-level beats from the transcript"
  python3 scripts/build_matched_plan.py "$WX" "$PLAN" --face-x "$FACE_X"
fi

say "5/6  beat map — READ THIS before rendering  (+ requirement gate on the plan)"
if [ -f "$SCRIPT_TXT" ]; then
  python3 scripts/beat_map_report.py "$WX" "$PLAN" "$BEATMAP" --script "$SCRIPT_TXT"
else
  python3 scripts/beat_map_report.py "$WX" "$PLAN" "$BEATMAP"
fi
# the ONE-BEAT-ONE-DIAGRAM law is gated BEFORE render too — a plan that violates it never renders
python3 scripts/verify_beat_devices.py "${PLAN%.ts}.plan.json"

# QA the SPOKEN AUDIO for leftover flubs. The beat map shows SCRIPT-corrected text, so a flub
# the cutter missed (a bare restart with no 'reset reset') is INVISIBLE there — this reads what
# was ACTUALLY said and warns loudly so it can't ship silently (Ryan 2026-07-06).
python3 scripts/verify_clean_read.py "$WX" "${PLAN%.ts}.plan.json" || true

if [ "$DO_RENDER" -ne 1 ]; then
  printf '\n\033[1;36mSTOPPED before render, by design.\033[0m Read %s — every row: said / shown / motion / transition.\n' "$BEATMAP"
  printf 'Looks right? Re-run:  scripts/edit_video.sh %s %s --render\n' "$RAW" "$FACE_X"
  printf 'Looks wrong?  Fix the devices cache (script/word-timings/%s-cut-devices.json) or the script text, then re-run WITHOUT --render.\n' "$NAME"
  exit 0
fi

say "6/6  render -> $OUT   (slim public dir so the 2GB copy can't time out)"
node scripts/build_anim_registry.mjs   # discover installed animations (drop-in packs) before rendering
PUB="$(mktemp -d)"; mkdir -p "$PUB/host" "$PUB/cutouts" "$PUB/fx" "$PUB/logos" "$PUB/photos" "$PUB/documents"
cp "$CUT" "$PUB/host/"; cp -R public/cutouts/. "$PUB/cutouts/" 2>/dev/null || true; cp -R public/fx/. "$PUB/fx/" 2>/dev/null || true; cp -R public/logos/. "$PUB/logos/" 2>/dev/null || true; cp -R public/photos/. "$PUB/photos/" 2>/dev/null || true; cp -R public/documents/. "$PUB/documents/" 2>/dev/null || true
# green-screen: the keyed host + the channel's flower assets
[ -n "${KEYED:-}" ] && [ -f "$KEYED" ] && cp "$KEYED" "$PUB/host/" || true
[ -n "${GS_PREFIX:-}" ] && { mkdir -p "$PUB/${GS_PREFIX}"; cp -R "public/${GS_PREFIX}/." "$PUB/${GS_PREFIX}/" 2>/dev/null; } || true
npx remotion render src/methodology/index.ts AutoReel "$OUT" --crf=18 --public-dir="$PUB" --timeout=180000
rm -rf "$PUB"

say "verify — requirement gate (diagram per beat, lit + moving) + alignment + seam-flash"
python3 scripts/verify_beat_devices.py "${PLAN%.ts}.plan.json" "$OUT"
python3 scripts/verify_beat_alignment.py "$WX" "$PLAN"
python3 scripts/verify_brightness.py "$OUT"
python3 scripts/verify_camera.py "${PLAN%.ts}.plan.json" "$OUT"

say "meaning gate — describe-back mute test (needs ANTHROPIC_API_KEY; else manual on the frames)"
if [ -f "$SCRIPT_TXT" ]; then
  python3 scripts/verify_beat_meaning.py "${PLAN%.ts}.plan.json" "$OUT" --script "$SCRIPT_TXT"
else
  python3 scripts/verify_beat_meaning.py "${PLAN%.ts}.plan.json" "$OUT"
fi
printf '\n\033[1;32m✓ gates passed: %s\033[0m\n' "$OUT"
printf 'The gate is NOT the edit: extract stills of EVERY beat and review them eyes-on before reporting.\n'
