#!/usr/bin/env python3
"""Generate the transparent host cutout used by QuoteTakeoverLab.

Background-removes a host frame into a tight (bbox-trimmed) transparent PNG so the
QuoteTakeover `cutout` layout can anchor it big on the right. Media is gitignored, so this
regenerates the demo asset deterministically.

Setup (one-time):  python3 -m venv ~/.venvs/rembg && ~/.venvs/rembg/bin/pip install rembg onnxruntime pillow
Run:               ~/.venvs/rembg/bin/python scripts/gen_host_cutout.py [in_frame.png] [out.png]
"""
import os
import sys
try:
    from rembg import remove
except ImportError:
    sys.exit("rembg not found — PNG cutouts are the imagery add-on (not part of the core).\n"
             "Install it:  bash scripts/setup-rembg.sh   (~440MB)\n"
             "Then run this with:  ~/.venvs/rembg/bin/python scripts/gen_host_cutout.py ...")
from PIL import Image

SRC = sys.argv[1] if len(sys.argv) > 1 else "public/frames/seg-01-mid.png"
OUT = sys.argv[2] if len(sys.argv) > 2 else "public/cutouts/host-cut.png"

def main() -> None:
    img = Image.open(SRC).convert("RGBA")
    cut = remove(img)
    bbox = cut.getbbox()  # trim transparent margins → a tight person cutout
    if bbox:
        cut = cut.crop(bbox)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    cut.save(OUT)
    print(f"saved {OUT} {cut.size}")

if __name__ == "__main__":
    main()
