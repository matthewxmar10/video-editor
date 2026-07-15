#!/usr/bin/env bash
# setup.sh — one-time install of the local AI tool the CORE engine uses.
# Builds ONE Python environment under ~/.venvs/ — ~1.3GB of downloads,
# 5-10 min on typical broadband. Full pip output streams to a log (path printed below).
#   whisperx  — word-level timing: drives BOTH the dead-space cut and the beat anchors
#               (~10-20ms accurate). This is the whole core pipeline's engine.
#
# PNG cutouts are an imagery add-on, not part of the core — they need a separate ~440MB
# tool (rembg). Install it only when you want cutouts:  bash scripts/setup-rembg.sh
set -euo pipefail
cd "$(dirname "$0")/.."

command -v ffmpeg >/dev/null || { echo "ffmpeg is required. Install it first (e.g. brew install ffmpeg)."; exit 1; }

# whisperX supports Python 3.10-3.13 (NOT 3.14+ yet). Pick a compatible interpreter — a fresh
# machine's default 'python3' is often too new (or too old), which makes pip fail with a
# cryptic "Could not find a version" error. Probe for a supported one and use it explicitly.
PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  command -v "$c" >/dev/null 2>&1 || continue
  v="$("$c" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null)" || continue
  case "$v" in 3.10|3.11|3.12|3.13) PY="$c"; break;; esac
done
[ -n "$PY" ] || {
  echo "error: whisperX needs Python 3.10-3.13 (it doesn't support 3.14+ yet), and none was found on PATH."
  echo "Install one, then re-run this script. On macOS:  brew install python@3.12"
  echo "On Debian/Ubuntu:  sudo apt-get install python3.12 python3.12-venv"
  exit 1
}

say(){ printf '\n\033[1;33m▸ %s\033[0m\n' "$*"; }

# CPU-only torch wheels on Linux — the pipeline is CPU-only by design, and the default
# PyPI wheel drags ~3GB of CUDA libraries. macOS wheels are already CPU-only.
# (Plain string, not an array: empty-array expansion breaks macOS bash 3.2 under set -u.)
TORCH_INDEX=""
[ "$(uname -s)" = "Linux" ] && TORCH_INDEX="--extra-index-url https://download.pytorch.org/whl/cpu"

LOGDIR="$(mktemp -d)"
say "building the whisperX env with $PY ($("$PY" --version 2>&1)) — ~1.3GB, 5-10 min. Live log: $LOGDIR/whisperx.log"

build_whisperx(){
  "$PY" -m venv "$HOME/.venvs/whisperx" 2>/dev/null || true
  "$HOME/.venvs/whisperx/bin/pip" install -q -U pip
  # shellcheck disable=SC2086
  "$HOME/.venvs/whisperx/bin/pip" install $TORCH_INDEX -r scripts/requirements-whisperx.txt
}

if build_whisperx > "$LOGDIR/whisperx.log" 2>&1; then
  say "whisperx venv ready — verifying imports…"
else
  echo "whisperx FAILED — last lines of $LOGDIR/whisperx.log:"; tail -5 "$LOGDIR/whisperx.log"
  echo "setup incomplete — fix the error above and re-run (setup is idempotent)."; exit 1
fi

# sanity check: catch a half-finished install now (both the cut path and the align path import)
if ! "$HOME/.venvs/whisperx/bin/python" -c "from faster_whisper import WhisperModel; import whisperx" 2>/dev/null; then
  echo "whisperx venv built but its imports failed — the install is incomplete."
  echo "Re-run: bash scripts/setup.sh  (it's idempotent)."; exit 1
fi
say "imports OK (faster_whisper + whisperx)"

printf '\n\033[1;32m✓ setup complete.\033[0m The FIRST edit also downloads ~1GB of models once (whisperX small + wav2vec2 aligner) and the first render fetches headless Chrome.\nNow: npm install (fine to run alongside this), then scripts/edit_video.sh <recording>.mp4\nWant PNG cutouts later? bash scripts/setup-rembg.sh (the imagery add-on, ~440MB).\n'
