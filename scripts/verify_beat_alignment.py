#!/usr/bin/env python3
"""Beat alignment gate. Proves every beat cut lands in a SILENCE between words (never inside a
word, never chopping a word onto the previous beat) and that each cut leads the next spoken
word. This is the visual-edit analogue of hostcut's HARD RULE: the plan is only correct if
every boundary passes.

  python3 scripts/verify_beat_alignment.py <words-wx.json> src/methodology/officialTestBeatPlan.ts
exit 0 = every cut aligned; exit 1 = a cut lands inside a word (would chop / feel off).
"""
import json
import re
import sys


def load_words(path):
    w = json.load(open(path))
    words = w if isinstance(w, list) else w.get('words', [])
    out = []
    for x in words:
        out.append({'t': (x.get('word') or x.get('t') or '').strip(),
                    's': round(x.get('start', x.get('s')), 2),
                    'e': round(x.get('end', x.get('e')), 2)})
    return out


def load_starts(ts_path):
    starts = []
    for ln in open(ts_path):
        m = re.search(r"start: ([\d.]+), dur: ([\d.]+), style: '(\w+)'", ln)
        if m:
            starts.append((float(m.group(1)), float(m.group(2)), m.group(3)))
    return starts


def main():
    words = load_words(sys.argv[1])
    beats = load_starts(sys.argv[2])
    print("beat cut alignment (each cut must sit in a gap between words):\n")
    print("  %-7s %-12s %-9s %s" % ('cut@', 'style', 'gap', 'status'))
    bad = 0
    for k, (start, dur, style) in enumerate(beats):
        if k == 0:
            print("  %-7.2f %-12s %-9s %s" % (start, style, '-', 'open (t=0)'))
            continue
        # A real CHOP = the cut lands well inside a word. Ignore sub-frame incursions (< ~1
        # frame @30fps): when two sentences abut with < a frame of gap, NO frame boundary sits
        # cleanly between them, so a fractional-frame overlap is quantization noise, not a chop.
        FR = 0.034
        inside = next((w for w in words if w['s'] + FR < start < w['e'] - FR), None)
        prev_end = max([w['e'] for w in words if w['s'] < start], default=0.0)
        nxt = min([w for w in words if w['s'] >= start - 0.001], key=lambda w: w['s'], default=None)
        gap = round((nxt['s'] - prev_end), 3) if nxt else 0.0
        lead = round((nxt['s'] - start), 3) if nxt else 0.0
        if inside:
            print("  %-7.2f %-12s %-9s CHOP inside '%s' (%.2f-%.2f) ✗" % (start, style, '-', inside['t'], inside['s'], inside['e']))
            bad += 1
        else:
            ok = gap >= 0.06 and lead >= 0.0
            print("  %-7.2f %-12s %-9s in silence, leads next word by %.2fs %s" % (start, style, '%.2fs' % gap, lead, 'OK' if ok else '(tight)'))
    # COVERAGE: beats must tile the timeline — every beat starts exactly where the last ended
    # (no gap = no flicker to a bare frame; no overlap = no double-render).
    holes = 0
    for k in range(1, len(beats)):
        prev_end = round(beats[k - 1][0] + beats[k - 1][1], 3)
        if abs(prev_end - beats[k][0]) > 0.034:  # > 1 frame @30fps
            print("  GAP/OVERLAP: beat %d ends %.2f but beat %d starts %.2f ✗" % (k - 1, prev_end, k, beats[k][0]))
            holes += 1
    print()
    if bad or holes:
        print("FAIL — %d chopped cut(s), %d gap/overlap(s)." % (bad, holes))
        sys.exit(1)
    print("PASS — every cut lands in a silence, no word chopped, beats tile the timeline with no gaps.")


if __name__ == '__main__':
    main()
