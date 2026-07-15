#!/usr/bin/env python3
"""verify_brightness.py — flash / dead-frame scan for a real-host render.

Reads per-frame average luma (YAVG via ffmpeg signalstats) and flags seam defects
that the transition grammar (methodology/lexicon.md "Transitions") forbids:

  SPIKE        a single frame brighter than BOTH neighbors  -> a 1-frame flash/pop.
  BRIGHT JUMP  a hard frame-to-frame BRIGHTENING (e.g. a dark takeover cut straight
               to bright cream with no cross-dissolve) -> reads as a "camera flash".
               The grammar says cross-dissolve OUT of a dark beat (~9-12 frames),
               so a hard bright jump is a FAIL.
  DARK CUT     a hard DARKENING jump (bright cream -> dark takeover). This is the
               INTENTIONAL hard-cut INTO a dark beat -> reported as INFO, not a fail.

Usage:   python3 scripts/verify_brightness.py render/<name>.mp4 [--fps 30]
Exit 0 = clean, 1 = flagged.
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile


def luma_per_frame(mp4: str):
    fd, path = tempfile.mkstemp(suffix=".txt")
    os.close(fd)
    subprocess.run(
        ["ffmpeg", "-i", mp4, "-vf",
         f"scale=128:72,signalstats,metadata=mode=print:file={path}",
         "-an", "-f", "null", "-"],
        stderr=subprocess.DEVNULL, check=True,
    )
    frames, cur = [], None
    for line in open(path):
        m = re.search(r"frame:(\d+)", line)
        if m:
            cur = int(m.group(1))
        m = re.search(r"YAVG=([\d.]+)", line)
        if m and cur is not None:
            frames.append((cur, float(m.group(1))))
    os.unlink(path)
    return frames


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mp4")
    ap.add_argument("--fps", type=float, default=30)
    ap.add_argument("--spike", type=float, default=30, help="1-frame spike threshold (luma)")
    ap.add_argument("--jump", type=float, default=90, help="hard brightening-jump threshold (luma)")
    args = ap.parse_args()

    fr = luma_per_frame(args.mp4)
    if not fr:
        print("no frames read"); sys.exit(1)

    spikes, bright, cuts = [], [], []
    for i in range(1, len(fr)):
        f, y = fr[i]
        _, yp = fr[i - 1]
        if i < len(fr) - 1:
            _, yn = fr[i + 1]
            if y - yp >= args.spike and y - yn >= args.spike:
                spikes.append((f, yp, y, yn))
        d = y - yp
        if d >= args.jump:
            bright.append((f, yp, y))
        elif d <= -args.jump:
            cuts.append((f, yp, y))

    def t(f):
        return f / args.fps

    print(f"scanned {len(fr)} frames from {args.mp4}")
    fail = False
    if spikes:
        fail = True
        print(f"\nFAIL — {len(spikes)} one-frame SPIKE(s) (flash):")
        for f, a, b, c in spikes:
            print(f"  frame {f} (t={t(f):.2f}s): {a:.0f} -> {b:.0f} -> {c:.0f}")
    if bright:
        fail = True
        print(f"\nFAIL — {len(bright)} hard BRIGHTENING jump(s) (dark->bright, no cross-dissolve):")
        for f, a, b in bright:
            print(f"  frame {f} (t={t(f):.2f}s): {a:.0f} -> {b:.0f}   << cross-dissolve this exit (Fade outStart)")
    if cuts:
        print(f"\nINFO — {len(cuts)} hard DARKENING cut(s) (intentional hard-cut INTO a dark takeover — OK):")
        for f, a, b in cuts:
            print(f"  frame {f} (t={t(f):.2f}s): {a:.0f} -> {b:.0f}")
    if not fail:
        print("\nPASS — no flashes (no 1-frame spikes, no hard brightening jumps).")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
