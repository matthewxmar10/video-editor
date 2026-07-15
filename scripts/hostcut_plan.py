#!/usr/bin/env python3
"""HostCut planner — tiered, reviewable dead-space trimming.

Turns a recording's silences into a keep-list using GRADED tiers instead of one
blunt threshold, and prints a human-readable PAUSE REPORT (where each pause sits
in the script, how long, what happens to it) so the cut is reviewed before it
renders. Specific pauses can be VETOED from the report by their # so a rhetorical
beat ("All right." -> "Let's get into it.") is left fully intact — duration alone
can't tell a beat from dead air, so the human keeps the final say. The keep-list
is handed to hostcut.render_cut, which enforces THE HARD RULE (every boundary in
silence) — see hostcut.py / methodology/host-cut.md.

RESET CUES are handled AUTOMATICALLY (2026-07-02): every spoken `reset, reset` in
the word timings becomes a CUT FLUB row — the span from the last completed
sentence through the cue is removed and the re-read is kept, no --forbid needed.
Reset rows are vetoable by # like any cut; a cue with no usable silence around it
is printed loudly and left for a manual cut (never silently kept). The render is
additionally gated on the detected forbidden spans (hostcut.ForbiddenSpanError).

Tiers (the "tightness" knob — defaults are the reviewed-natural preset):
  * pause  < SHORT (0.35s)     -> kept untouched (natural cadence)
  * SHORT <= pause < LONG (2s) -> trimmed to MED_FLOOR (0.28s)   (tightened 2026-07-02:
                                  looser floors kept ~0.7s of the host recovering/looking
                                  away between sentences — the big-test seam fragments)
  * pause >= LONG (2s)         -> crushed to LONG_FLOOR (0.22s)   (real dead air)
  * head dead air              -> LEAD (0.15s) lead-in kept
  * tail dead air              -> TAILKEEP (0.30s) kept after last word
  * --keep-pauses 8,12         -> those report #s left fully untouched (no cut)

Usage:
  python3 scripts/hostcut_plan.py <src> --words script/word-timings/<stem>.json
  ... review the report, then add --render <out.mp4> (and --keep-pauses N,... to veto).
Knobs: --short --long --med-floor --long-floor --lead --tailkeep --noise-db
"""
import argparse
import json
import sys

sys.path.insert(0, __file__.rsplit('/', 1)[0])
import hostcut


def find_context(s, e, words, n=2):
    before = [w['word'] for w in words if w['end'] <= s + 0.08][-n:]
    after = [w['word'] for w in words if w['start'] >= e - 0.08][:n]
    return (' '.join(before) or '[start]'), (' '.join(after) or '[end]')


def plan(src, words, *, short=0.35, long=2.0, med_floor=0.28, long_floor=0.22,
         lead=0.15, tailkeep=0.30, noise_db=-30.0, keep_indices=None):
    keep_indices = set(keep_indices or [])
    dur = hostcut.probe_duration(src)
    sil = hostcut.detect_silences(src, noise_db=noise_db, min_d=0.06, duration=dur)
    events, interior, tail = [], list(sil), None

    # RESET CUES — the flub-removal half of the reset methodology, AUTOMATIC (no
    # --forbid): each spoken `reset, reset` becomes a CUT FLUB event spanning from
    # the last completed sentence through the cue; the re-read after it is kept.
    # Vetoable by report # like any cut. A cue with no usable silence around it is
    # printed loudly (never silently kept) — cut that one by hand.
    resets = hostcut.detect_reset_spans(words, sil)
    for r in resets:
        if r['ok']:
            events.append({'at': r['cut'][0], 'dur': r['cut'][1] - r['cut'][0], 'kind': 'RESET',
                           'cut': r['cut'], 'kept': 0.0, 'b': r['b'], 'a': r['a'],
                           'forbid': r['forbid']})
        else:
            events.append({'at': r['forbid'][0], 'dur': r['forbid'][1] - r['forbid'][0],
                           'kind': 'RESET!', 'cut': None, 'kept': r['forbid'][1] - r['forbid'][0],
                           'b': r['b'], 'a': r['a'],
                           'error': 'no usable silence around the flub — cut manually'})
    reset_cuts = [r['cut'] for r in resets if r['ok']]

    def inside_reset(s, e):
        return any(cs - 1e-6 <= s and e <= ce + 1e-6 for cs, ce in reset_cuts)

    if interior and interior[0][0] <= 0.1:               # head dead air
        hs, he = interior.pop(0)
        # trim to the first WORD, not just the detected silence — a breath before
        # speaking ends the "silence" early and left ~0.3-0.5s of the host staring
        # off camera at the top (Ryan, flub-test 2026-07-03). The cut end is
        # lead-in seconds before the first word, wherever the silence ended.
        w0 = words[0]['start'] if words else he
        events.append({'at': 0.0, 'dur': he - hs, 'kind': 'head',
                       'cut': (0.0, max(0.0, max(he, w0) - lead)), 'kept': lead, 'b': '[start]', 'a': ''})
    if interior and interior[-1][1] >= dur - 0.1:         # tail dead air
        ts, te = interior.pop()
        # a trailing silence SHORTER than tailkeep has nothing to cut — emitting the
        # inverted (ts+tailkeep > dur) span used to build a keep segment past EOF and
        # trip CutSpecError on container-vs-stream skewed files (found 2026-07-02)
        tail_cut = (ts + tailkeep, dur) if ts + tailkeep < dur - 1e-3 else None
        tail = {'at': ts, 'dur': te - ts, 'kind': 'tail', 'cut': tail_cut,
                'kept': min(tailkeep, max(dur - ts, 0.0)), 'b': None, 'a': '[end]', 'ts': ts, 'te': te}
    for s, e in interior:                                 # graded interior pauses
        if inside_reset(s, e):
            continue                                       # consumed by a flub cut — not a row
        d = e - s
        b, a = find_context(s, e, words)
        if d < short:
            events.append({'at': s, 'dur': d, 'kind': 'keep', 'cut': None, 'kept': d, 'b': b, 'a': a})
        else:
            floor = med_floor if d < long else long_floor
            half = floor / 2.0
            events.append({'at': s, 'dur': d, 'kind': ('med' if d < long else 'LONG'),
                           'cut': (s + half, e - half), 'kept': floor, 'b': b, 'a': a})
    if tail is not None:
        tail['b'], _ = find_context(tail['ts'], tail['te'], words)
        events.append(tail)

    events.sort(key=lambda x: x['at'])
    idx = 0
    for ev in events:                                     # number the cuts; apply vetoes
        if ev['cut'] is not None:
            idx += 1
            ev['idx'] = idx
            if idx in keep_indices:
                ev['cut'] = None
                ev['vetoed'] = True
        else:
            ev['idx'] = None

    # degenerate/inverted cuts never reach the keep-builder; ends clamp to duration
    cuts = sorted(ev['cut'] for ev in events
                  if ev['cut'] is not None and ev['cut'][1] > ev['cut'][0] + 1e-6)
    keep, pos = [], 0.0
    for cs, ce in cuts:
        cs, ce = min(cs, dur), min(ce, dur)
        if cs > pos + 1e-3:
            keep.append((round(pos, 3), round(cs, 3)))
        pos = max(pos, ce)
    if pos < dur - 1e-3:
        keep.append((round(pos, 3), round(dur, 3)))
    return dur, sil, keep, events


def print_report(src, dur, sil, keep, events, *, short, long, med_floor, long_floor):
    kept = sum(e - s for s, e in keep)
    name = src.rsplit('/', 1)[-1]
    print(f'\nPAUSE PLAN — {name}   ({dur:.1f}s source, {len(sil)} silences)')
    print(f'tiers:  <{short}s keep  ·  {short}-{long}s -> {med_floor}s  ·  >{long}s -> {long_floor}s\n')
    print(f'{"#":>2}  {"at":>7}  {"dur":>7}  {"action":<13} {"-> kept":>8}   context (before -> after)')
    print('-' * 94)
    for ev in events:
        if ev['cut'] is None and not ev.get('vetoed') and 'error' not in ev:
            continue                                       # untouched short pauses omitted for signal
        action = {'head': 'trim head', 'tail': 'trim tail', 'med': 'trim', 'LONG': 'CRUSH',
                  'RESET': 'CUT FLUB', 'RESET!': 'FLUB ?!'}.get(ev['kind'], ev['kind'])
        if ev.get('vetoed'):
            action = 'KEEP (vetoed)'
            kept_s = f'{ev["dur"]:.2f}s'
        else:
            kept_s = f'{ev["kept"]:.2f}s'
        num = ev['idx'] if ev['idx'] else ''
        print(f'{num:>2}  {ev["at"]:>7.1f}  {ev["dur"]:>6.2f}s  {action:<13} {kept_s:>8}   "{ev["b"]}" -> "{ev["a"]}"')
        if ev.get('error'):
            print(f'      ^^ RESET CUE KEPT IN CUT: {ev["error"]}')
    untouched = sum(1 for ev in events if ev['cut'] is None and not ev.get('vetoed') and 'error' not in ev)
    flubs = sum(1 for ev in events if ev['kind'] == 'RESET' and ev['cut'] is not None)
    print('-' * 94)
    print(f'left untouched: {untouched} short pauses (<{short}s)   flubs removed via reset cue: {flubs}')
    forbidden = [ev['forbid'] for ev in events if ev.get('forbid') and ev['cut'] is not None]
    try:
        hostcut.assert_cuts_in_silence(keep, sil, dur, forbidden_spans=forbidden or None)
        gate = 'PASS'
    except Exception as ex:
        gate = f'REJECTED -> {ex}'
    print(f'RESULT: {dur:.1f}s -> {kept:.1f}s   ({len(keep)} segments)   HARD RULE: {gate}')


def main():
    ap = argparse.ArgumentParser(description='HostCut tiered planner + pause report.')
    ap.add_argument('src')
    ap.add_argument('--words', required=True, help='word-timings json for context labels')
    ap.add_argument('--render', help='output mp4 (omit to only print the report)')
    ap.add_argument('--keep-pauses', default='', help='report #s to leave fully untouched, e.g. "8,12"')
    ap.add_argument('--short', type=float, default=0.35)
    ap.add_argument('--long', type=float, default=2.0)
    ap.add_argument('--med-floor', type=float, default=0.28)
    ap.add_argument('--long-floor', type=float, default=0.22)
    ap.add_argument('--lead', type=float, default=0.15)
    ap.add_argument('--tailkeep', type=float, default=0.30)
    ap.add_argument('--noise-db', type=float, default=-30.0)
    ap.add_argument('--crf', type=int, default=18)
    args = ap.parse_args()

    keep_indices = [int(x) for x in args.keep_pauses.replace(' ', '').split(',') if x]
    words = json.loads(open(args.words).read())
    dur, sil, keep, events = plan(
        args.src, words, short=args.short, long=args.long, med_floor=args.med_floor,
        long_floor=args.long_floor, lead=args.lead, tailkeep=args.tailkeep,
        noise_db=args.noise_db, keep_indices=keep_indices)
    print_report(args.src, dur, sil, keep, events, short=args.short, long=args.long,
                 med_floor=args.med_floor, long_floor=args.long_floor)
    if args.render:
        # the render is gated against the SAME forbidden spans the report showed —
        # a kept flub can never reach the bytes silently
        forbidden = [ev['forbid'] for ev in events if ev.get('forbid') and ev['cut'] is not None]
        hostcut.render_cut(args.src, keep, args.render, silences=sil, duration=dur, crf=args.crf,
                           forbidden_spans=forbidden or None)
        print(f'\nwrote {args.render}  ({hostcut.probe_duration(args.render):.1f}s)')


if __name__ == '__main__':
    main()
