#!/usr/bin/env bash
# setup-rembg.sh — the imagery add-on. Installs rembg (background removal) so
# gen_host_cutout.py / fetch_subject_image.py can make transparent PNG cutouts.
# NOT needed by the core caption/host engine — run this only when you want cutouts.
# ~440MB, 2-5 min.
set -euo pipefail
cd "$(dirname "$0")/.."

command -v python3 >/dev/null || { echo "python3 is required. Install it first."; exit 1; }

say(){ printf '\n\033[1;33m▸ %s\033[0m\n' "$*"; }

LOGDIR="$(mktemp -d)"
say "building the rembg env (imagery cutouts) — ~440MB. Live log: $LOGDIR/rembg.log"

build_rembg(){
  python3 -m venv "$HOME/.venvs/rembg" 2>/dev/null || true
  "$HOME/.venvs/rembg/bin/pip" install -q -U pip
  "$HOME/.venvs/rembg/bin/pip" install "rembg[cpu]" pillow
}

if build_rembg > "$LOGDIR/rembg.log" 2>&1; then
  say "rembg venv ready"
else
  echo "rembg FAILED — last lines of $LOGDIR/rembg.log:"; tail -5 "$LOGDIR/rembg.log"
  echo "setup incomplete — fix the error above and re-run (setup is idempotent)."; exit 1
fi

printf '\n\033[1;32m✓ rembg ready.\033[0m First cutout downloads the u2net model once (~170MB).\n'
