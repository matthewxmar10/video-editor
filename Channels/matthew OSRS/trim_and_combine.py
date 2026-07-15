#!/usr/bin/env python3
"""
OSRS channel — trim-and-combine tool.

Purpose
  Matthew drops a folder of raw OSRS recordings plus a trim text file that names,
  per source video, the exact time ranges he wants kept. This cuts every requested
  range frame-accurately and concatenates them end-to-end, in the order they appear
  in the trim file, into one combined video.

  Matthew will tell you explicitly when he wants this run — it is NOT the default for
  every OSRS video. Only run it when he points you at a trim text file.

Trim-file format (one source per non-blank line; blank lines ignored):
    <ID> – <start> to <end>; <start> to <end>; ...
    <ID> – Full clip                       # keep the whole source
  - <ID> is the 3-digit filename prefix (e.g. 026 -> 026-GryDoneNechs.mp4, matched by
    glob "<ID>-*.mp4" in the source folder). Prefixes are unique.
  - The separator after the ID may be an en-dash "–" or a hyphen "-".
  - Multiple ranges for one source are separated by ";".
  - Times are M:SS, MM:SS, or H:MM:SS. "Full clip"/"Full Clip" (case-insensitive) = whole file.
  - CLIP ORDER = the order lines appear in the file (that is the final timeline order).
    Matthew may ask for a specific source to land at the very end — if the trim file
    already lists it last, no reordering is needed; otherwise move that line yourself.

Assumptions / how it works
  - Sources are expected uniform (this channel's exports are 1920x1080 30fps h264 / aac
    48k stereo). The script re-encodes each cut to identical settings anyway, so the
    final concat is a clean stream-copy with no seam glitches even if a source differs.
  - Fast keyframe seek (-ss before -i) keeps deep seeks into multi-GB files quick, and
    re-encoding makes the cut land on the exact requested frame.

Usage
  python3 "Channels/matthew OSRS/trim_and_combine.py" <source_folder> [trim_file] [output.mp4]
    source_folder : folder holding the raw <ID>-*.mp4 recordings and the trim file
    trim_file     : defaults to the first *.txt in source_folder (e.g. trimtimes.txt)
    output.mp4    : defaults to <source_folder>/<folder-name>-combined.mp4

  Needs ffmpeg + ffprobe on PATH.
"""
import glob
import json
import os
import re
import subprocess
import sys
import time


def to_seconds(t):
    parts = [float(p) for p in t.strip().split(":")]
    s = 0.0
    for p in parts:
        s = s * 60 + p
    return s


def duration(path):
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", path]).decode().strip()
    return float(out)


def file_for_id(src_dir, vid):
    matches = sorted(glob.glob(os.path.join(src_dir, f"{vid}-*.mp4")))
    return matches[0] if matches else None


def parse_trim_file(src_dir, txt):
    entries = []
    with open(txt, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            m = re.match(r"^(\d{3})\s*[–\-]\s*(.*)$", line)
            if not m:
                print("  ! skipped unparseable line:", repr(line), file=sys.stderr)
                continue
            vid, rest = m.group(1), m.group(2).strip()
            path = file_for_id(src_dir, vid)
            if not path:
                print(f"  ! no source file for id {vid}", file=sys.stderr)
                continue
            if rest.lower().startswith("full"):
                entries.append({"id": vid, "file": path, "start": 0.0,
                                "end": round(duration(path), 3)})
                continue
            for chunk in rest.split(";"):
                chunk = chunk.strip()
                if not chunk:
                    continue
                cm = re.match(r"^(.*?)\s*to\s*(.*)$", chunk, re.IGNORECASE)
                if not cm:
                    print(f"  ! bad range for {vid}: {chunk!r}", file=sys.stderr)
                    continue
                entries.append({"id": vid, "file": path,
                                "start": round(to_seconds(cm.group(1)), 3),
                                "end": round(to_seconds(cm.group(2)), 3)})
    return entries


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    src_dir = os.path.abspath(sys.argv[1])
    if len(sys.argv) >= 3:
        txt = sys.argv[2]
    else:
        txts = sorted(glob.glob(os.path.join(src_dir, "*.txt")))
        if not txts:
            print("No .txt trim file found in", src_dir, file=sys.stderr)
            sys.exit(1)
        txt = txts[0]
    out = (sys.argv[3] if len(sys.argv) >= 4
           else os.path.join(src_dir, f"{os.path.basename(src_dir)}-combined.mp4"))

    print(f"Trim file : {txt}")
    entries = parse_trim_file(src_dir, txt)
    if not entries:
        print("No clips parsed.", file=sys.stderr)
        sys.exit(1)

    tot = sum(e["end"] - e["start"] for e in entries)
    print(f"Parsed {len(entries)} clips, {tot:.1f}s ({tot/60:.1f} min) total.\n")
    for i, e in enumerate(entries, 1):
        print(f"{i:3d}  {e['id']}  {e['start']:>9.2f} -> {e['end']:>9.2f}  "
              f"({e['end']-e['start']:6.2f}s)  {os.path.basename(e['file'])}")
    print()

    work = os.path.join(src_dir, ".trim_work")
    os.makedirs(work, exist_ok=True)
    listing = []
    t0 = time.time()
    for i, e in enumerate(entries, 1):
        dur = round(e["end"] - e["start"], 3)
        outp = os.path.join(work, f"clip_{i:03d}.mp4")
        listing.append(outp)
        if os.path.exists(outp) and os.path.getsize(outp) > 0:
            print(f"[{i:3d}/{len(entries)}] skip (exists)")
            continue
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{e['start']:.3f}", "-i", e["file"], "-t", f"{dur:.3f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-r", "30", "-fps_mode", "cfr",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-video_track_timescale", "30000", outp,
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(outp) or os.path.getsize(outp) == 0:
            print(f"[{i:3d}] FAILED {os.path.basename(e['file'])} "
                  f"{e['start']}->{e['end']}\n{r.stderr[-1500:]}", file=sys.stderr)
            sys.exit(2)
        print(f"[{i:3d}/{len(entries)}] ok {dur:6.2f}s  {os.path.basename(e['file'])}  "
              f"({time.time()-t0:.0f}s)")

    concat_list = os.path.join(work, "concat.txt")
    with open(concat_list, "w") as f:
        for p in listing:
            f.write(f"file '{p}'\n")

    print("\nConcatenating...")
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                        "-f", "concat", "-safe", "0", "-i", concat_list,
                        "-c", "copy", "-movflags", "+faststart", out],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("CONCAT FAILED\n" + r.stderr[-2000:], file=sys.stderr)
        sys.exit(3)
    print("DONE ->", out)
    print("(intermediate clips left in", work + " — delete when satisfied)")


if __name__ == "__main__":
    main()
