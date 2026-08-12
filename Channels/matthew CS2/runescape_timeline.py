#!/usr/bin/env python3
"""
RuneScape Timelines — assemble a finished video from a FOLDER of clips plus a .txt of cut times.

The .txt is one line per source clip:

    <clip filename> - <start> - <end>; <start> - <end>; ...

  * filename then a hyphen/en-dash, then start-end for each kept range.
  * Multiple ranges from the same clip are separated by semicolons.
  * Times are m:ss or h:mm:ss (e.g. 0:12, 1:04, 1:02:33).
  * "<name> - Full clip" keeps the ENTIRE clip (no trimming).
  * Lines are assembled top-to-bottom; ranges within a line in written order.
  * Lines that can't be read are reported (not silently dropped).

Example:
    fight_at_bandos.mp4 - 0:10 - 0:45; 2:03 - 2:20
    zulrah.mp4 - 1:30 - 1:58
    intro.mp4 - Full clip

Every kept range is cut accurately and re-encoded to a uniform 1080p60 clip, then all are joined —
the same per-segment engine condense uses, so there is no audio/video drift or stutter at the joins.
Run standalone:  python runescape_timeline.py <clips_folder> <cuts.txt> <out.mp4>
"""
import os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import condense_action as ca  # shared render engine

_VID_EXT = (".mp4", ".mov", ".mkv", ".avi", ".m4v", ".ts", ".webm", ".flv")
_TC = re.compile(r"\d{1,2}(?::\d{1,2}){1,2}")  # m:ss, mm:ss or h:mm:ss


def tc_to_sec(t):
    s = 0
    for part in t.split(":"):
        s = s * 60 + int(part)
    return s


def parse_edl(text):
    """Parse the cut-times .txt. Returns (rows, skipped) where rows is
    [(clipname, [(start_s, end_s), ...]), ...] and skipped is [(lineno, text), ...] for lines that
    couldn't be read. An end of None means 'to the end of the clip' (a "Full clip" line)."""
    rows, skipped = [], []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip().replace("–", "-").replace("—", "-")  # en/em dash -> hyphen
        if not line or line.startswith("#"):
            continue
        tcs = list(_TC.finditer(line))
        if tcs:
            name = line[:tcs[0].start()].rstrip(" -\t").strip().strip('"')
            times = [tc_to_sec(m.group(0)) for m in tcs]
            ranges = [(times[i], times[i + 1]) for i in range(0, len(times) - 1, 2)
                      if times[i + 1] > times[i]]
            if name and ranges:
                rows.append((name, ranges))
            else:
                skipped.append((lineno, raw.strip()))
            continue
        # no timecodes: a "<name> - Full clip" line means keep the whole clip
        m = re.match(r"^(.*?)\s*-\s*full\b", line, re.IGNORECASE)
        if m and m.group(1).strip():
            rows.append((m.group(1).strip().strip('"'), [(0.0, None)]))
        else:
            skipped.append((lineno, raw.strip()))
    return rows, skipped


def resolve_clip(folder, name):
    """Find the actual file in `folder` for a name from the .txt (exact, stem, or prefix match)."""
    entries = os.listdir(folder)
    vids = [f for f in entries if f.lower().endswith(_VID_EXT)]
    nlow = name.lower()
    for f in entries:                                   # exact (with extension)
        if f.lower() == nlow:
            return os.path.join(folder, f)
    stem = os.path.splitext(name)[0].lower()
    for f in vids:                                      # match ignoring extension
        if os.path.splitext(f)[0].lower() == stem:
            return os.path.join(folder, f)
    for f in vids:                                      # last resort: prefix
        if f.lower().startswith(nlow):
            return os.path.join(folder, f)
    raise FileNotFoundError(f"no video in the folder matches '{name}'")


def build_segments(folder, edl, out_size="1920,1080", fps=60):
    ow, oh = out_size.split(",")
    vf = f"[0:v:0]scale={ow}:{oh}:flags=lanczos,fps={fps},setsar=1,setpts=PTS-STARTPTS[v]"
    af = "[0:a:0]aresample=48000,asetpts=PTS-STARTPTS[a]"   # keep each clip's own audio, uniform format
    fc = f"{vf};{af}"
    segs = []
    for name, ranges in edl:
        path = resolve_clip(folder, name)
        for s, e in ranges:
            if e is None:                       # "Full clip" -> to the end of the file
                e = ca.probe_dur(path)
            segs.append({"input": path, "ss": float(s), "dur": float(e - s), "fc": fc})
    return segs


def run_timeline(folder, txt_path, out, opts=None, progress=None, log=None):
    opts = opts or ca.default_opts()
    with open(txt_path, encoding="utf-8", errors="replace") as f:
        edl, skipped = parse_edl(f.read())
    if not edl:
        raise RuntimeError("no clip/time lines found in the .txt")
    if skipped and log:
        where = ", ".join(f"L{n}" for n, _ in skipped[:10]) + ("…" if len(skipped) > 10 else "")
        log(f"WARNING: skipped {len(skipped)} unreadable line(s): {where}")
    n_full = sum(1 for _, rs in edl for s, e in rs if e is None)
    segs = build_segments(folder, edl, opts.out_size, opts.fps)
    if log:
        log(f"timeline: {len(edl)} clips, {len(segs)} segments ({n_full} full-clip), "
            f"{sum(s['dur'] for s in segs)/60:.1f} min total")
    return ca.render_and_join(segs, out, opts.preset, opts.crf, fps=opts.fps, progress=progress, log=log)


def main():
    if len(sys.argv) < 4:
        print("usage: python runescape_timeline.py <clips_folder> <cuts.txt> <out.mp4>"); sys.exit(2)
    folder, txt, out = sys.argv[1], sys.argv[2], sys.argv[3]

    def prog(done, total, phase=""):
        print(f"\r  {phase}: {done}/{total}      ", end="", flush=True)
    try:
        res = run_timeline(folder, txt, out, progress=prog, log=print)
        print(f"done -> {res}")
    except Exception as ex:
        print(f"\nERROR: {ex}"); sys.exit(1)


if __name__ == "__main__":
    main()
