#!/usr/bin/env python3
"""QA the SPOKEN AUDIO of the cut for leftover flubs — reads what was actually SAID.

The beat map shows script-corrected text (the writer's clean words laid on the timeline),
so a flub the cutter missed is INVISIBLE there — you'd review a clean-looking map and ship
a video that still says "only two teams have ever, only two teams have ever won...". This
gate reads the raw cut transcript (<stem>-cut-wx.json, BEFORE script-correction) and flags
the fingerprint of an uncut flub so it can never ship silently:

  1. A repeated phrase — >=MINLEN consecutive words said, then said again within WINDOW
     seconds (a false start / restart the host didn't mark with 'reset reset').
  2. A leftover 'reset' cue that stayed in the cut.

Not every repeat is a flub (deliberate anaphora exists), so this WARNS loudly and maps each
hit to its beat for a human/agent to confirm and trim — it does not silently auto-cut.

  python3 scripts/verify_clean_read.py <stem>-cut-wx.json <plan.plan.json>
Exits 1 if anything is flagged (so the pipeline can surface it), 0 on a clean read.
"""
import json
import re
import sys

MINLEN = 4      # consecutive matching words to call it a repeat (avoids "back to back")
WINDOW = 12.0   # seconds: the re-say of a flub follows quickly


def norm(w):
    return re.sub(r'[^a-z0-9]', '', w.lower())


def load_beats(plan_path):
    d = json.load(open(plan_path))
    return d['beats'] if isinstance(d, dict) else d


def beat_of(t, beats):
    for i, b in enumerate(beats):
        if b['start'] - 1e-6 <= t < b['start'] + b['dur']:
            return i
    return len(beats) - 1 if beats else 0


def find_repeats(toks):
    """toks: list of (norm, start, word). Returns non-overlapping repeated spans."""
    n = len(toks)
    flags, covered = [], set()
    for i in range(n):
        if i in covered:
            continue
        best = None
        for j in range(i + MINLEN, n):
            if toks[j][1] - toks[i][1] > WINDOW:
                break
            L = 0
            while i + L < j and j + L < n and toks[i + L][0] == toks[j + L][0]:
                L += 1
            if L >= MINLEN and (best is None or L > best[1]):
                best = (j, L)
        if best:
            j, L = best
            flags.append({'phrase': ' '.join(t[2] for t in toks[i:i + L]),
                          't1': toks[i][1], 't2': toks[j][1]})
            for k in range(i, j + L):
                covered.add(k)
    return flags


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if len(args) < 2:
        sys.exit('usage: verify_clean_read.py <stem>-cut-wx.json <plan.plan.json>')
    words = json.load(open(args[0]))
    beats = load_beats(args[1])
    toks = [(norm(w['word']), float(w['start']), w['word'].strip())
            for w in words if norm(w['word'])]

    repeats = find_repeats(toks)
    resets = [(t[1], t[2]) for t in toks if t[0] == 'reset']

    if not repeats and not resets:
        print('CLEAN READ ✓ — no repeated phrases or stray "reset" cues in the spoken audio.')
        return 0

    print('\033[1;31m⚠ QA — POSSIBLE UNCUT FLUB(S) IN THE SPOKEN AUDIO\033[0m')
    print('  (read from the CUT transcript, not the script — confirm and trim before shipping)')
    print('-' * 92)
    for f in repeats:
        b = beat_of(f['t1'], beats)
        print(f'  beat {b}: phrase repeated  @{f["t1"]:.1f}s then @{f["t2"]:.1f}s  '
              f'— "{f["phrase"]}"')
    for t, w in resets:
        b = beat_of(t, beats)
        print(f'  beat {b}: leftover reset cue @{t:.1f}s ("{w}") — the flub around it was not fully cut')
    print('-' * 92)
    print('FIX: trim the false start (or have the host re-say it with a clear "reset reset"), then re-run.')
    return 1


if __name__ == '__main__':
    sys.exit(main())
