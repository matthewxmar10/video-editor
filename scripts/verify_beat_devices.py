#!/usr/bin/env python3
"""THE REQUIREMENT GATE (Ryan 2026-07-02): "one spoken beat, one motion overlay that has a
diagram that matches that spoken beat, for however long that beat is."

The old gates (cut alignment, brightness flashes) can PASS while the actual requirement
fails — beats with no diagram, diagrams that die early, panels that sit static. This gate
checks the requirement itself, in two layers:

  PLAN layer (always): every beat carries a `diagram` spec; beats tile the timeline; every
  word-anchor the spec references lands INSIDE its beat window (a land outside the window
  is an animation that never plays — a silent lie).

  RENDER layer (with an mp4): for every beat, sample frames across the beat and measure the
  DIAGRAM REGION (the half-panel opposite the host, or the full stage on takeovers):
    - PRESENCE: something bright exists in the region on every sample (max luma) — catches
      "no diagram" / near-black stages.
    - MOTION: consecutive samples differ (mean abs pixel diff) — catches static scenes.

  A FAIL here means the render does NOT meet the spec. Never report a render off this gate
  alone — the gate is not the edit; eyes-on stills of EVERY beat come after (see
  memory: gates-are-not-the-edit) — but a FAIL is always a hard stop.

    python3 scripts/verify_beat_devices.py <plan.plan.json> [render.mp4]
"""
import json
import os
import subprocess
import sys

W, H = 1920, 1080
SAMPLE_W, SAMPLE_H = 320, 180
PRESENCE_YMAX = 100.0   # region max-luma floor: a yellow chip/cream label clears this easily
MOTION_DIFF = 0.65      # mean abs diff (0-255) between samples ~1.5-4s apart; bob+push clears it
BUILD_DIFF = 0.30       # mean abs diff across a 0.5s step INSIDE each third of the beat —
                        # the ALWAYS-BUILDING law (Ryan 2026-07-02: "animations must always
                        # have something building toward the final state"). The global slow
                        # push-zoom alone reads ~0.1 over 0.5s and FAILS; bobs, builds,
                        # breathing halos and events clear it.

# anchor fields that must land inside the beat window
TIME_KEYS = ('winAt', 'landAt', 'hitAt')
# per-kind required anchor fields on the diagram descriptor. The live 10 kinds carry
# their anchors as BEAT keys (checked by the beat-window pass), not descriptor fields,
# so nothing is required here today — add entries when a kind grows descriptor anchors.
REQUIRED = {}


def region_for(beat):
    """(x, y, w, h) of the diagram region for this beat, excluding the host panel."""
    style = beat['style']
    if style in ('glideR', 'intro', 'open'):     # host right / intro camera right → diagram left
        return (0, 120, 1140, 840)
    if style == 'glideL':                         # host left → diagram right
        return (780, 120, 1140, 840)
    return (140, 100, 1640, 880)                  # storyFull / takeovers: the stage


def sample(mp4, t, crop):
    """Raw grayscale bytes of the cropped region at time t (SAMPLE_W x SAMPLE_H)."""
    x, y, w, h = crop
    p = subprocess.run(
        ['ffmpeg', '-nostdin', '-loglevel', 'error', '-ss', '%.3f' % t, '-i', mp4,
         '-frames:v', '1', '-vf', 'crop=%d:%d:%d:%d,scale=%d:%d' % (w, h, x, y, SAMPLE_W, SAMPLE_H),
         '-f', 'rawvideo', '-pix_fmt', 'gray', '-'],
        capture_output=True)
    if p.returncode != 0 or len(p.stdout) < SAMPLE_W * SAMPLE_H:
        raise RuntimeError('ffmpeg sample failed at %.2fs: %s' % (t, p.stderr.decode()[-200:]))
    return p.stdout[:SAMPLE_W * SAMPLE_H]


def stats(buf):
    return sum(buf) / len(buf), max(buf)


def diff(a, b):
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def anchor_times(dg):
    out = [(k, dg[k]) for k in TIME_KEYS if dg.get(k) is not None]
    for key in ('items', 'focus', 'bars'):
        for it in dg.get(key) or []:
            out.append(('%s[%s].at' % (key, it.get('t', '?')), it['at']))
    for key in ('a', 'b'):
        if dg.get(key):
            out.append(('%s.at' % key, dg[key]['at']))
    if dg.get('headline'):
        out.append(('headline.at', dg['headline']['at']))
    return out


def main():
    plan_path = sys.argv[1]
    mp4 = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('-') else None
    plan = json.load(open(plan_path))
    beats = plan['beats']
    fails = []

    # STALENESS: a render OLDER than the plan cannot contain these beats — gating it would
    # be a lie (2026-07-02: a failed re-render left the previous mp4 in place and its
    # "verification" stills were silently from the old edit).
    if mp4 and os.path.getmtime(mp4) < os.path.getmtime(plan_path):
        print('FAIL — %s is OLDER than %s: this render predates the plan it is being '
              'checked against. Re-render before gating.' % (mp4, plan_path))
        sys.exit(1)

    print('\nREQUIREMENT GATE — one content-matched moving diagram per spoken beat')
    print('%-3s %-8s %-6s %-10s %-14s %s' % ('#', 'start', 'dur', 'style', 'diagram', 'checks'))
    print('-' * 96)

    for i, b in enumerate(beats):
        notes = []
        dg = b.get('diagram')
        end = b['start'] + b['dur']
        # contiguity
        if i + 1 < len(beats) and abs(end - beats[i + 1]['start']) > 0.021:
            notes.append('GAP to next beat (%.2f→%.2f)' % (end, beats[i + 1]['start']))
        # the requirement: a diagram on EVERY beat
        if not dg:
            if b.get('chips') and b.get('style') in ('intro', 'open'):
                pass  # the IntroStage brand-chip reveal IS the intro device (duplicate law)
            else:
                notes.append('NO DIAGRAM — the requirement itself')
        else:
            for req in REQUIRED.get(dg['kind'], ()):
                if dg.get(req) in (None, [], ''):
                    notes.append('missing %s.%s' % (dg['kind'], req))
            # v4 redundancy budget: headlines are OPTIONAL (text is earned by a failed
            # mute test, never default) — the meaning gate owns "does it state the claim"
            for name, t in anchor_times(dg):
                if not (b['start'] - 0.03 <= t <= end + 0.03):
                    notes.append('%s=%.2f outside beat %.2f-%.2f (never plays)' % (name, t, b['start'], end))
        # render layer
        if mp4 and dg:
            crop = region_for(b)
            pad = min(0.5, b['dur'] / 4)
            ts = sorted({round(max(b['start'] + pad, 0), 2),
                         round(b['start'] + b['dur'] / 2, 2),
                         round(end - pad, 2)})
            bufs = [sample(mp4, t, crop) for t in ts]
            for t, buf in zip(ts, bufs):
                avg, mx = stats(buf)
                if mx < PRESENCE_YMAX:
                    notes.append('EMPTY region @%.1fs (ymax %.0f < %.0f)' % (t, mx, PRESENCE_YMAX))
            for k in range(len(bufs) - 1):
                d = diff(bufs[k], bufs[k + 1])
                if d < MOTION_DIFF:
                    notes.append('STATIC region %.1f→%.1fs (diff %.2f < %.2f)' % (ts[k], ts[k + 1], d, MOTION_DIFF))
            # ALWAYS-BUILDING: every third of the beat must show real motion over a 0.5s
            # step — three coarse samples can miss a dead stretch (the bare-axis bug)
            if b['dur'] >= 2.4:
                for frac in (0.2, 0.5, 0.8):
                    t0 = round(b['start'] + b['dur'] * frac, 2)
                    t1 = round(min(t0 + 0.5, end - 0.1), 2)
                    if t1 - t0 < 0.3:
                        continue
                    d = diff(sample(mp4, t0, crop), sample(mp4, t1, crop))
                    if d < BUILD_DIFF:
                        notes.append('DEAD @%.1f-%.1fs (diff %.2f < %.2f — nothing building)' % (t0, t1, d, BUILD_DIFF))
        ok = not notes
        kind = (dg['kind'] + ('/FULL' if dg.get('stage') == 'full' else '')) if dg else '—'
        print('%-3d %-8.2f %-6.2f %-10s %-14s %s' % (i, b['start'], b['dur'], b['style'], kind,
                                                     'OK' if ok else '; '.join(notes)))
        if not ok:
            fails.append((i, notes))

    # ── BARE-CUT GATE (Ryan 2026-07-03: "when it's just the audio cleaning process,
    # there should be no changes other than getting the word flubs and spaces out") —
    # a plan with no intro asset, no glides, and no device keys is an audio-cleaning
    # pass: the camera must be UNTOUCHED. Verified optically: the static background
    # corners may not move within a beat OR across a cut. Well-defined goal: max mean
    # corner drift < STILL_MAX at every sampled step (a 0.10 push measured 10-15).
    DEVICE_KEYS = ('count', 'snip', 'pair', 'merge', 'roles', 'upg', 'sprint', 'funnel',
                   'closer', 'section', 'photo', 'items', 'chips', 'phrase')
    bare = all(b['style'] not in ('intro', 'glideR', 'glideL')
               and not any(b.get(k) for k in DEVICE_KEYS) for b in beats)
    if bare and mp4:
        # THE definition, tested directly: the render must be the cut source footage,
        # frame for frame (encode noise ~0.5-0.7; any camera transform prints 2+).
        # Corner-drift was tried first and false-failed on the host's GESTURES —
        # comparing against the source is gesture-proof (both carry the same hands).
        src = os.path.join('public', plan.get('video', ''))
        if not os.path.exists(src):
            print('BARE-CUT GATE: skipped (source %s not found)' % src)
        else:
            BARE_MAX = 1.5
            full = (0, 0, W, H)
            total = beats[-1]['start'] + beats[-1]['dur']
            moved, worst, n = [], 0.0, 0
            for b in beats:
                for frac in (0.25, 0.75):
                    t = round(b['start'] + b['dur'] * frac, 2)
                    if t > total - 0.6:
                        continue
                    d = diff(sample(mp4, t, full), sample(src, t, full))
                    worst, n = max(worst, d), n + 1
                    if d > BARE_MAX:
                        moved.append('@%.1fs render deviates from source (diff %.2f > %.2f)' % (t, d, BARE_MAX))
            if moved:
                fails.append(('bare', ['NOT A BARE CUT: ' + '; '.join(moved[:4])]))
                print('BARE-CUT GATE: FAIL — an audio-cleaning pass altered the picture: %s' % '; '.join(moved[:4]))
            else:
                print('BARE-CUT GATE: OK — render is the source footage, cuts only '
                      '(%d samples, worst frame diff %.2f < %.1f)' % (n, worst, BARE_MAX))

    # ── VARIETY GATE (v4.2, Ryan 2026-07-03: "there is no taste... same old stuff over
    # and over" — differentiation is REQUIRED, not hoped for): the same kind never plays
    # back-to-back, and the generic flow fallback is capped at 2 per video.
    kinds = [((b.get('diagram') or {}).get('kind')) or ('intro-chips' if b.get('chips') else '?')
             for b in beats]
    for i in range(1, len(kinds)):
        if kinds[i] == kinds[i - 1]:
            if kinds[i] in ('host', 'type'):
                print('%-3d note: two %r scenes in a row — fine, but an animation would be stronger' % (i, kinds[i]))
            else:
                print('%-3d VARIETY: %r repeats back-to-back — differentiate' % (i, kinds[i]))
                fails.append((i, ['variety']))
    print('-' * 96)
    if fails:
        print('FAIL — %d beat(s) violate the requirement. The render does NOT meet the spec.' % len(fails))
        sys.exit(1)
    layer = 'plan + render' if mp4 else 'plan only (no mp4 given)'
    print('PASS (%s) — every beat carries a diagram, every anchor lands inside its beat'
          '%s.' % (layer, ', every region is lit and moving' if mp4 else ''))
    print('REMINDER: the gate is not the edit — review eyes-on stills of EVERY beat before reporting.')


if __name__ == '__main__':
    main()
