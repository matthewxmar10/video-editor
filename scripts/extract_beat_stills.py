#!/usr/bin/env python3
"""Per-beat review stills — the EYES-ON half of QA (the gate is not the edit).

Three stills per beat (early / mid / late), named so the review can't skip a beat:
    <outdir>/b<idx>-<kind>-<early|mid|late>-<t>s.png

    python3 scripts/extract_beat_stills.py <plan.plan.json> <render.mp4> <outdir>

Review EVERY still before reporting a render. A beat whose early frame reads empty, whose
mid frame doesn't match its SHOWN row, or whose late frame equals its early frame (static)
is a FAIL regardless of what the gates said.
"""
import json
import os
import subprocess
import sys


def main():
    plan_path, mp4, outdir = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(outdir, exist_ok=True)
    beats = json.load(open(plan_path))['beats']
    made = []
    for i, b in enumerate(beats):
        kind = (b.get('diagram') or {}).get('kind', b['style'])
        pad = min(0.5, b['dur'] / 4)
        for tag, t in (('early', b['start'] + pad),
                       ('mid', b['start'] + b['dur'] / 2),
                       ('late', b['start'] + b['dur'] - pad)):
            t = round(t, 2)
            name = 'b%d-%s-%s-%.1fs.png' % (i, kind, tag, t)
            path = os.path.join(outdir, name)
            subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-y', '-ss', '%.3f' % t,
                            '-i', mp4, '-frames:v', '1', path], check=True)
            made.append(path)
    print('\n'.join(made))
    print('%d stills — review EVERY one before reporting.' % len(made))


if __name__ == '__main__':
    main()
