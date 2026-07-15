#!/usr/bin/env python3
"""STAGE-2 GATE — the CAMERA (Ryan 2026-07-04: "very well defined gates for each stage").

Stage 1 (audio clean) is gated by hostcut's HARD RULE + verify_beat_alignment + the
bare-cut source-identity check. Stage 3 (animations) is gated by verify_beat_devices +
the meaning gate. This gate owns Stage 2: the camera must do exactly what the plan
declares — nothing more.

HARD CHECKS (fail the build; each is one number against one threshold):
  1. INTRO REST — the intro's last frames equal the SOURCE frame at scale 1.0
     (diff <= 1.5; encode noise is ~0.4-0.7). Catches boundary offsets AND overlay
     remnants (logos/phrase must have exited) in one measurement.
  2. HOST-BEAT ZOOM — every host beat's endpoints match the planned uniform-rate move.
     Measured as BEST-FIT SCALE: the render frame is compared against the source frame
     under a sweep of candidate scales; an overlay pollutes every candidate equally, so
     the minimizing scale still reveals the true camera (this replaced an overlay-free-
     only check that skipped every beat of the full-library fixture — caught by the
     planted-bug self-test, 2026-07-04). Best-fit must sit within SCALE_TOL of the plan.
     Overlay-free beats additionally get the strict absolute-diff check.

MEASURED, NOT JUDGED (printed for the eyes-on review): the frame-to-frame jump at
every cut, next to that beat's own motion baseline. Overlays legitimately swap at cuts
(the scene change IS the edit), so a hard threshold here would fail designed behavior —
the numbers are for the human pass (gates are not the edit).

Bare plans are skipped: the bare-cut gate in verify_beat_devices owns them outright.

    python3 scripts/verify_camera.py <plan.plan.json> <render.mp4>
"""
import json
import os
import subprocess
import sys

W, H = 1920, 1080
SAMPLE_W, SAMPLE_H = 320, 180
REST_MAX = 1.5      # render == source at scale 1.0 (encode noise ~0.4-0.7)
PUSH_MAX = 2.2      # render == source under the planned zoom (adds resample noise)
SCALE_TOL = 0.0125  # |best-fit scale - planned scale| ceiling (2.5 sweep steps)
SCALE_STEP = 0.005  # sweep resolution
SCALE_HI = 1.13     # sweep ceiling (> HOST_PUSH cap + tolerance)
# ── mirrors of AutoReel's SPANS constants — KEEP IN SYNC ──────────────────────────────
HOST_PUSH = 0.10
BARE_HOST = ('open', 'hostZoom')
DEVICE_KEYS = ('count', 'snip', 'pair', 'merge', 'roles', 'upg', 'sprint', 'funnel',
               'closer', 'section', 'photo', 'items', 'chips', 'phrase')


def sample(mp4, t, scale=None):
    """Full-frame grayscale bytes at time t, optionally under a center zoom transform.

    The frame is FIRST normalized to the 1920x1080 composition stage (cover-fit, exactly
    AutoReel's OffthreadVideo objectFit:cover), so a source shot at a higher resolution
    (e.g. 2560x1440) is compared like-for-like against the render — the camera zoom is then
    a crop ON TOP of that. Without this the gate center-cropped a 1440p source and
    false-failed every host beat (2026-07-12)."""
    cover = 'scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,' % (W, H, W, H)
    vf = cover + 'scale=%d:%d' % (SAMPLE_W, SAMPLE_H)
    if scale and abs(scale - 1.0) > 1e-4:
        vf = cover + 'scale=%d:%d,crop=%d:%d,' % (round(W * scale), round(H * scale), W, H) + 'scale=%d:%d' % (SAMPLE_W, SAMPLE_H)
    p = subprocess.run(
        ['ffmpeg', '-nostdin', '-loglevel', 'error', '-ss', '%.3f' % t, '-i', mp4,
         '-frames:v', '1', '-vf', vf, '-f', 'rawvideo', '-pix_fmt', 'gray', '-'],
        capture_output=True)
    if p.returncode != 0 or len(p.stdout) < SAMPLE_W * SAMPLE_H:
        raise RuntimeError('ffmpeg sample failed at %.2fs: %s' % (t, p.stderr.decode()[-200:]))
    return p.stdout[:SAMPLE_W * SAMPLE_H]


def diff(a, b):
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def media_dur(path):
    """Seconds, or None. Probe checkpoints get clamped inside this so we never sample past end."""
    p = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                        '-of', 'csv=p=0', path], capture_output=True, text=True)
    try:
        return float(p.stdout.strip())
    except (ValueError, AttributeError):
        return None


def media_dims(path):
    """(width, height) or None — the source's native pixel size."""
    p = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                        '-show_entries', 'stream=width,height', '-of', 'csv=p=0', path],
                       capture_output=True, text=True)
    try:
        w, h = p.stdout.strip().split(',')[:2]
        return int(w), int(h)
    except (ValueError, AttributeError):
        return None


def expected_zooms(beats):
    """Replicate AutoReel SPANS for host beats:
    beat index -> (startScale, endScale, overlay_free). ONE RULE (Ryan 2026-07-04): every
    host beat starts at REST (1.0); a beat handing into a glide HOLDS at 1.0 (uncropped for
    a smooth glide), else it pushes IN to 1.0+HOST_PUSH."""
    out = {}
    for i, b in enumerate(beats):
        style = b['style']
        if style not in BARE_HOST:
            continue
        free = not any(b.get(k) for k in DEVICE_KEYS)
        if style == 'open':
            out[i] = (1.1, 1.0, free)   # eased settle — only the 1.0 END is checked
            continue
        nxt = beats[i + 1]['style'] if i + 1 < len(beats) else None
        end = 1.0 if nxt in ('glideR', 'glideL') else 1.0 + HOST_PUSH
        out[i] = (1.0, end, free)
    return out


def best_fit_scale(mp4, src, t):
    """The camera scale at time t, measured: sweep candidate scales on the SOURCE and
    return the one that best matches the RENDER frame. Overlay pixels penalize every
    candidate equally, so the minimum tracks the true camera underneath."""
    frame = sample(mp4, t)
    best, best_d = 1.0, float('inf')
    s = 1.0
    while s <= SCALE_HI + 1e-9:
        d = diff(frame, sample(src, t, scale=s))
        if d < best_d:
            best, best_d = s, d
        s = round(s + SCALE_STEP, 4)
    return best


def main():
    plan_path, mp4 = sys.argv[1], sys.argv[2]
    plan = json.load(open(plan_path))
    beats = plan['beats']
    src = os.path.join('public', plan.get('video', ''))
    bare = all(b['style'] not in ('intro', 'glideR', 'glideL')
               and not any(b.get(k) for k in DEVICE_KEYS) for b in beats)

    print('\nCAMERA GATE — the render moves exactly as the plan declares')
    if bare:
        print('bare plan — skipped (the bare-cut gate owns audio-cleaning passes). OK')
        return
    if not os.path.exists(src):
        print('FAIL — source %s not found (needed to verify the camera against)' % src)
        sys.exit(1)

    # Checkpoints derive from plan beat times, which can round a hair PAST the real media end
    # (the last beat's probe is end-0.10). Clamp every probe inside BOTH the render and source
    # so a short final beat can't make ffmpeg sample past the end and crash the gate.
    _durs = [d for d in (media_dur(mp4), media_dur(src)) if d]
    tmax = round(min(_durs) - 0.05, 2) if _durs else float('inf')
    def clamp(t):
        return round(min(t, tmax), 2)

    # When the SOURCE is shot larger than the 1920x1080 stage (e.g. 2560x1440), the render
    # downscales it (objectFit:cover) while the gate must downscale it too to compare — two
    # different resamplers over H.264, which leaves ~2-4 of mean-abs noise that no camera move
    # explains. The best-fit SCALE check is resampler-robust and still verifies the move
    # exactly; the strict absolute-pixel check is NOT trustworthy under that double-downscale
    # (it can't tell 3.0 of resample noise from a 3.0 overlay), so we defer to the scale check
    # for higher-res sources rather than false-fail every host beat (2026-07-12).
    _sd = media_dims(src)
    src_downscaled = bool(_sd and (_sd[0] > W or _sd[1] > H))
    if src_downscaled:
        print('  note: source is %dx%d (> %dx%d stage) — strict pixel check deferred to the '
              'best-fit SCALE check (resampler-robust); the camera move is still fully verified.'
              % (_sd[0], _sd[1], W, H))

    fails = []

    # 1. INTRO REST — last frames of the intro are the bare source at 1.0
    if beats[0]['style'] == 'intro':
        t = clamp(beats[0]['start'] + beats[0]['dur'] - 0.10)
        d = diff(sample(mp4, t), sample(src, t))
        ok = d <= REST_MAX
        print('  intro ends at REST on the bare frame @%.2fs: diff %.2f <= %.1f  %s'
              % (t, d, REST_MAX, 'OK' if ok else 'FAIL'))
        if not ok:
            fails.append('intro not at rest / overlay remnant (diff %.2f)' % d)

    # 2. HOST-BEAT ZOOM — every host beat matches the plan (best-fit scale for all;
    # strict absolute diff additionally where no overlay pollutes the frame). The
    # 'early' probe sits 0.5s in — past the slide-back blend a glide return carries in
    # its first ~0.4s (probing at +0.1s false-failed there) — and the expected scale is
    # interpolated exactly for the probe time (the move is linear by code).
    for i, (s0, s1, free) in sorted(expected_zooms(beats).items()):
        b = beats[i]
        end = b['start'] + b['dur']
        # a probe whose intended time falls PAST the media end gets clamped to the last valid
        # frame; the strict PIXEL check is unreliable there (a moving host at the boundary under
        # a full push-in reads as a small diff), so only the SCALE check runs on a clamped probe.
        def _probe(ti, tag):
            return (clamp(ti), tag, round(ti, 2) > tmax)
        probes = [_probe(end - 0.10, 'end')]
        if b['style'] != 'open' and b['dur'] > 1.4:   # the open settle is eased — landing only
            # mid-beat: far past the glide-return blend (probes at +0.1s and +0.5s both
            # false-failed inside it) — the linear move makes any probe time exact
            probes.insert(0, _probe(b['start'] + b['dur'] / 2, 'mid'))
        for t, tag, clamped in probes:
            frac = min(max((t - b['start']) / b['dur'], 0.0), 1.0)
            s = s0 + (s1 - s0) * frac
            m = best_fit_scale(mp4, src, t)
            ok = abs(m - s) <= SCALE_TOL
            print('  beat %d %s %s @%.2fs: planned scale %.3f, measured %.3f  %s'
                  % (i, b['style'], tag, t, s, m, 'OK' if ok else 'FAIL'))
            if not ok:
                fails.append('beat %d %s: camera at %.3f, plan says %.3f' % (i, tag, m, s))
            if free and not clamped and not src_downscaled:
                lim = REST_MAX if abs(s - 1.0) < 0.006 else PUSH_MAX
                d = diff(sample(mp4, t), sample(src, t, scale=s))
                if d > lim:
                    print('  beat %d %s %s strict: diff %.2f > %.1f  FAIL' % (i, b['style'], tag, d, lim))
                    fails.append('beat %d %s altered beyond the camera (diff %.2f)' % (i, tag, d))

    # 3. BOUNDARY JUMPS — measured and printed for the eyes-on pass (overlays swap at
    # cuts by design, so these are data, not verdicts)
    print('  boundary jumps (jump vs the beat\'s own motion — big deltas deserve eyes):')
    for i in range(len(beats) - 1):
        T = beats[i + 1]['start']
        base = diff(sample(mp4, round(T - 0.10, 2)), sample(mp4, round(T - 0.03, 2)))
        jump = diff(sample(mp4, round(T - 0.03, 2)), sample(mp4, round(T + 0.03, 2)))
        print('    cut @%.2fs (%s→%s): jump %.2f vs baseline %.2f  (Δ %.2f)'
              % (T, beats[i]['style'], beats[i + 1]['style'], jump, base, jump - base))

    if fails:
        print('FAIL — the camera is off-plan: ' + '; '.join(fails))
        sys.exit(1)
    print('PASS — camera matches the plan at every checkable point.')


if __name__ == '__main__':
    main()
