#!/usr/bin/env python3
"""HostCut — assemble a real-host recording into a tight cut.

The HostCut treatment: a real on-camera recording (Ryan, not the HeyGen clone)
turned into a tight edit. Flubs are marked while recording with a spoken
`reset, reset` cue followed by a full re-read of the sentence; dead space and
flubbed takes are removed with jump cuts (the locked default — see
methodology/host-cut.md).

================================ THE HARD RULE ================================
Every cut boundary MUST land STRICTLY INSIDE a detected SILENCE interval whose
duration is >= min_join_silence. Rendering goes through `render_cut`, which
validates first and refuses (raises) on any violation. There is no public,
ungated path to a rendered file.

Why (Ryan, 2026-06-23): joining two takes *inside* a word or glued phrase is the
one move that produces an audible artifact (a doubled/clipped syllable) AND that
base whisper transcribes as if it were clean, so an automated transcript check
misses it. The recording protocol re-reads the WHOLE sentence after a `reset`,
so clean takes always begin/end in a real pause; legitimate cuts pass by
construction. No situation in this workflow needs a mid-word rejoin, so the
system makes one structurally impossible.

SCOPE (be honest about what the guard does and does not promise):
  * Guarantees, within the silence model: no boundary inside speech; the minimum
    join-silence rules out 60-90ms intra-word plosive gaps; optional
    `forbidden_spans` rejects any kept segment that overlaps a `reset` cue or a
    flubbed take; the rendering primitive is private so the gate cannot be
    skipped.
  * Does NOT and CANNOT decide editorial correctness from audio alone (was the
    RIGHT take kept? was a sentence played twice?). That is verified separately
    by re-transcribing the OUTPUT (word_align) and reading it back — the cue word
    must be gone and the script must read once and clean. Keep both gates.
==============================================================================
"""
import argparse
import re
import subprocess
import sys

MAX_TOL = 0.08          # head/tail exemption tolerance ceiling (hard clamp)
DEFAULT_MIN_JOIN = 0.15  # min duration of a silence a cut may land in (> intra-word stops)
EPS = 0.006              # float-robustness only; NOT a license to cut into speech


class MidWordRejoinError(Exception):
    """A cut boundary would land inside speech (a mid-word / mid-phrase rejoin)."""


class ForbiddenSpanError(Exception):
    """A kept segment overlaps a forbidden span (a `reset` cue or a flubbed take)."""


class CutSpecError(Exception):
    """The keep-segment list is malformed (overlap, non-monotonic, empty, OOB)."""


def probe_duration(src):
    out = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', src],
        capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def merge_intervals(intervals, gap=1e-6):
    """Sort and merge overlapping/touching (start,end) intervals; drop empties.
    `gap` = the largest separation still treated as continuous (default 1us = only
    exact touches). detect_silences passes a small real gap to absorb sub-ms edge
    jitter between the two loudness passes (else one pause reads as two — flub-3)."""
    iv = sorted((float(s), float(e)) for s, e in intervals if e > s)
    out = []
    for s, e in iv:
        if out and s <= out[-1][1] + gap:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def parse_silencedetect(stderr, duration, min_d=0.0):
    """Parse silencedetect output in ONE time-ordered, balanced pass.

    ffmpeg prints `silence_start:`/`silence_end:` in time order. We open on
    start, close on the next end, drop stray ends, and close a still-open
    interval at EOF. A to-EOF silence whose start exceeds the probed `duration`
    (VFR / container-vs-stream skew) is clamped to start+min_d (and warned) so a
    real tail pause is never silently dropped. Returns merged intervals.
    """
    events = re.findall(r'silence_(start|end):\s*(-?[0-9.]+)', stderr)
    intervals = []
    open_s = None
    for kind, val in events:
        v = max(0.0, float(val))
        if kind == 'start':
            if open_s is not None and v > open_s:   # defensive: start without end
                intervals.append((open_s, v))
            open_s = v
        else:                                        # 'end'
            if open_s is not None:
                if v > open_s:
                    intervals.append((open_s, v))
                open_s = None
            # stray end before any start: drop
    if open_s is not None:                           # silence runs to EOF
        end = duration
        if duration <= open_s:
            end = open_s + max(min_d, 1e-3)
            print(f'hostcut: warning: EOF silence_start {open_s:.3f}s exceeds duration '
                  f'{duration:.3f}s; clamping tail silence end to {end:.3f}s', file=sys.stderr)
        intervals.append((open_s, end))
    return merge_intervals(intervals)


def _detect_silences_1(src, noise_db, min_d, duration):
    cmd = ['ffmpeg', '-hide_banner', '-nostats', '-i', src,
           '-af', f'silencedetect=noise={noise_db}dB:d={min_d}', '-f', 'null', '-']
    err = subprocess.run(cmd, capture_output=True, text=True).stderr
    return parse_silencedetect(err, duration, min_d=min_d)


def _intersect_intervals(a, b):
    """Time points silent in BOTH interval sets (sorted, merged inputs)."""
    out, i, j = [], 0, 0
    while i < len(a) and j < len(b):
        s = max(a[i][0], b[j][0])
        e = min(a[i][1], b[j][1])
        if e > s:
            out.append((s, e))
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return out


def detect_silences(src, noise_db=-30.0, min_d=0.06, duration=None, strict_db=-40.0):
    """Detect silence intervals via ffmpeg silencedetect (merged, sorted).

    min_d is deliberately small so the detector reports even short gaps with
    accurate edges; whether a gap is long ENOUGH to cut in is enforced
    separately by min_join_silence in the guard.

    DUAL-THRESHOLD (Ryan 2026-07-01, the "Remotion" bug): a single -30dB pass
    can call a trailing consonant or breath "silence" when it's actually quiet-
    but-audible speech — cutting there clips the word. A time point only
    counts as cuttable silence if it reads silent at BOTH noise_db AND a
    STRICTER strict_db pass (intersection) — a genuinely dead patch of audio
    passes both; a soft word-tail fails the strict pass and is excluded. Pass
    strict_db=None to disable (old single-threshold behavior, for callers that
    already do their own strict check).
    """
    if duration is None:
        duration = probe_duration(src)
    loose = _detect_silences_1(src, noise_db, min_d, duration)
    if strict_db is None:
        return merge_intervals(loose)
    strict = _detect_silences_1(src, strict_db, min_d, duration)
    # SILENCE_JITTER: coalesce slices split by < this by the two passes disagreeing on an
    # edge by a hair (flub-3: 84us). Well below any real sound (soft consonants are 20ms+),
    # so genuinely distinct pauses are never merged.
    SILENCE_JITTER = 0.005
    # The intersection can chop one continuous silence at a threshold boundary into
    # adjacent slices; returning those unmerged made the planner cut one pause TWICE
    # (flub-3, 2026-07-04: a double jump-cut in the "learning process. / And that's fine"
    # gap). This one function is the single source of every silence in the system, so
    # coalescing here fixes it for the pause tiers, the reset detector, AND the HARD RULE
    # guard at once — no call site can miss it.
    return merge_intervals(_intersect_intervals(loose, strict), gap=SILENCE_JITTER)


def _tok(w):
    return re.sub(r'[^a-z]', '', w.lower())


def detect_reset_spans(words, silences, *, min_repeat=2, max_gap=1.2,
                       min_join_silence=DEFAULT_MIN_JOIN):
    """Find spoken `reset, reset` cues and derive the CUT for each flubbed take.

    Protocol (methodology/host-cut.md): a flub is marked by saying the cue and then
    re-reading the WHOLE sentence. The cut for a cue therefore runs from the silence
    after the last COMPLETED sentence (everything spoken since is the flubbed take)
    through the silence after the cue words (the re-read that follows is kept). Cut
    boundaries are placed at the midpoint of a real silence >= min_join_silence, so
    THE HARD RULE passes by construction; a cue with no usable silence on either
    side comes back ok=False (cut=None) so the planner REPORTS it loudly instead of
    silently keeping the flub.

    A single spoken 'reset' does NOT trigger ('reset' is a legitimate content word):
    the cue is >= min_repeat consecutive 'reset' tokens within max_gap of each other.

    words: [{'word','start','end'}, ...] (whisperX timings). silences: (s,e) list.
    Returns [{'cut': (cs,ce)|None, 'forbid': (fs,fe), 'ok': bool,
              'flub_start': s, 'cue_end': e, 'b': str, 'a': str}, ...]
    """
    merged = merge_intervals(silences)

    def mid_of_silence(lo, hi):
        """Midpoint of the longest qualifying silence overlapping (lo, hi), or None."""
        cands = [(s, e) for s, e in merged
                 if e > lo - 1e-6 and s < hi + 1e-6 and (e - s) >= min_join_silence - 1e-9]
        if not cands:
            return None
        s, e = max(cands, key=lambda p: p[1] - p[0])
        mid = (max(s, lo) + min(e, hi)) / 2.0
        return min(max(mid, s + 0.02), e - 0.02)

    groups, i = [], 0
    while i < len(words):
        if _tok(words[i]['word']) == 'reset':
            j = i
            while (j + 1 < len(words) and _tok(words[j + 1]['word']) == 'reset'
                   and float(words[j + 1]['start']) - float(words[j]['end']) <= max_gap):
                j += 1
            if j - i + 1 >= min_repeat:
                groups.append((i, j))
            i = j + 1
        else:
            i += 1

    out, prev_cue_idx = [], -1
    for gi, gj in groups:
        # FIND THE FLUB START. Primary rule (learned from the real reset-reset ground
        # truth, 2026-07-02): the re-read AFTER the cue repeats the flubbed text, and
        # whisper often punctuates an aborted take as a full sentence — so sentence
        # punctuation alone under-cuts. Match the re-read's first content trigram
        # backward into the pre-cue words; the LATEST hit is where the flubbed take
        # begins. Fallback (no trigram match): walk back to the last sentence-ending
        # punctuation, the protocol's whole-sentence re-read case.
        flub_idx = None
        post = [_tok(w['word']) for w in words[gj + 1: gj + 9]]
        for skip in range(0, 3):
            tri = [t for t in post[skip:skip + 3] if t]
            if len(tri) < 3:
                break
            hits = [i for i in range(prev_cue_idx + 1, gi - 2)
                    if [_tok(words[i + d]['word']) for d in range(3)] == tri]
            if hits:
                flub_idx = hits[-1]
                break
        if flub_idx is None:
            k = gi - 1
            while k > prev_cue_idx and not words[k]['word'].strip().endswith(('.', '?', '!')):
                k -= 1
            flub_idx = min(k + 1, gi)
        flub_first = words[flub_idx]
        fs = float(flub_first['start'])
        cue_end = float(words[gj]['end'])
        k = flub_idx - 1
        prev_end = float(words[k]['end']) if k >= 0 else 0.0
        nxt = float(words[gj + 1]['start']) if gj + 1 < len(words) else cue_end + 5.0
        cs = mid_of_silence(prev_end - 0.05, fs + 0.05)
        ce = mid_of_silence(cue_end - 0.05, nxt + 0.05)
        # Base-whisper word times DRIFT in flubbed regions (the aligner struggles on an
        # aborted take), so the tight ce window can miss the real pause the re-read follows.
        # Fall back to the nearest qualifying AUDIO silence in the ~4s after the cue — a
        # `reset,reset` re-read ALWAYS follows a real pause (flub-3, 2026-07-04: a 3.2s
        # silence sat 0.2s past where the word-time window looked, so a real flub was left
        # in). NOTE: only the FORWARD (ce) side gets this — a cs fallback searching backward
        # would grab the silence before the last GOOD sentence and delete kept content; a
        # flub glued to the prior sentence with no clean silence in front stays ok=False.
        if ce is None:
            ce = mid_of_silence(cue_end - 0.10, cue_end + 4.0)
        ok = cs is not None and ce is not None and ce > cs
        out.append({
            'cut': (cs, ce) if ok else None,
            'forbid': (max(fs - 0.01, 0.0), cue_end + 0.01),
            'ok': ok,
            'flub_start': fs,
            'cue_end': cue_end,
            'b': words[k]['word'] if k >= 0 else '[start]',
            'a': words[gj + 1]['word'] if gj + 1 < len(words) else '[end]',
        })
        prev_cue_idx = gj
    return out


def _valid_silence(t, merged, min_dur):
    """True iff t is strictly inside (±EPS) a merged silence of duration >= min_dur."""
    return any((e - s) >= min_dur - 1e-9 and (s - EPS) <= t <= (e + EPS)
               for s, e in merged)


def validate_keep_segments(keep, duration):
    if not keep:
        raise CutSpecError('keep list is empty')
    prev_end = -1.0
    for i, seg in enumerate(keep):
        if len(seg) != 2:
            raise CutSpecError(f'segment {i} is not a (start, end) pair: {seg!r}')
        s, e = float(seg[0]), float(seg[1])
        if e <= s:
            raise CutSpecError(f'segment {i} has end<=start: {s}..{e}')
        if s < -1e-6 or e > duration + 1e-3:
            raise CutSpecError(f'segment {i} out of [0,{duration}] bounds: {s}..{e}')
        if s < prev_end - 1e-6:
            raise CutSpecError(f'segment {i} overlaps/precedes previous (start {s} < prev end {prev_end})')
        prev_end = e


def assert_cuts_in_silence(keep, silences, duration, *, tol=0.05,
                           min_join_silence=DEFAULT_MIN_JOIN, forbidden_spans=None):
    """THE HARD RULE. Raise on any cut boundary that is not strictly inside a
    sufficiently-long silence, or on any kept segment overlapping a forbidden
    span. `tol` only widens the true-source-start/EOF exemption and is clamped.
    """
    tol = min(max(float(tol), 0.0), MAX_TOL)
    validate_keep_segments(keep, duration)
    merged = merge_intervals(silences)

    if forbidden_spans:
        clashes = []
        for i, (s, e) in enumerate(keep):
            for fs, fe in forbidden_spans:
                if s < fe - 1e-9 and fs < e - 1e-9:           # interval overlap
                    clashes.append((i, fs, fe))
        if clashes:
            detail = ', '.join(f'seg{i}∩({fs:.2f},{fe:.2f})s' for i, fs, fe in clashes)
            raise ForbiddenSpanError(
                f'kept segment overlaps a forbidden span (reset cue / flubbed take): {detail}. '
                'Move the boundary fully outside the marked span.')

    n = len(keep)
    bad = []
    for i, (s, e) in enumerate(keep):
        start_is_cut = not (i == 0 and s <= tol)
        end_is_cut = not (i == n - 1 and e >= duration - tol)
        if start_is_cut and not _valid_silence(s, merged, min_join_silence):
            bad.append((i, 'start', s))
        if end_is_cut and not _valid_silence(e, merged, min_join_silence):
            bad.append((i, 'end', e))
    if bad:
        detail = ', '.join(f'seg{i}.{lbl}={t:.3f}s' for i, lbl, t in bad)
        raise MidWordRejoinError(
            'HARD RULE violation — cut boundary not strictly inside a silence of '
            f'>= {min_join_silence}s (would clip or rejoin mid-word): {detail}. '
            'Re-cut so every boundary lands in a real pause; redo the full sentence after a reset.')
    return True


def _build_filtergraph(keep):
    """ffmpeg filter_complex: trim+concat keep segments, A/V in sync.

    PRIVATE on purpose: the only supported way to render is `render_cut`, which
    validates THE HARD RULE first. Do not call this to render around the gate.
    """
    parts = []
    for i, (s, e) in enumerate(keep):
        parts.append(f'[0:v]trim={s:.3f}:{e:.3f},setpts=PTS-STARTPTS[v{i}]')
        parts.append(f'[0:a]atrim={s:.3f}:{e:.3f},asetpts=PTS-STARTPTS[a{i}]')
    labels = ''.join(f'[v{i}][a{i}]' for i in range(len(keep)))
    parts.append(f'{labels}concat=n={len(keep)}:v=1:a=1[outv][outa]')
    return ';'.join(parts)


def render_cut(src, keep, out, *, noise_db=-30.0, min_d=0.06, tol=0.05,
               min_join_silence=DEFAULT_MIN_JOIN, forbidden_spans=None,
               silences=None, duration=None, crf=18, preset='medium'):
    """Validate (THE HARD RULE) then render. If the caller already detected
    silences, pass them (and `duration`) so the bytes are gated against the SAME
    map the plan was reviewed against — never silently re-derived with different
    thresholds. Raises before invoking ffmpeg on any violation.
    """
    if duration is None:
        duration = probe_duration(src)
    if silences is None:
        silences = detect_silences(src, noise_db=noise_db, min_d=min_d, duration=duration)
    assert_cuts_in_silence(keep, silences, duration, tol=tol,
                           min_join_silence=min_join_silence, forbidden_spans=forbidden_spans)
    fg = _build_filtergraph(keep)
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-i', src,
           '-filter_complex', fg, '-map', '[outv]', '-map', '[outa]',
           '-c:v', 'libx264', '-crf', str(crf), '-preset', preset,
           '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', out]
    subprocess.run(cmd, check=True)
    return out


def _parse_ranges(text):
    segs = []
    for chunk in (text or '').split(','):
        chunk = chunk.strip()
        if not chunk:
            continue
        s, e = chunk.split(':')
        segs.append((float(s), float(e)))
    return segs


def main(argv=None):
    ap = argparse.ArgumentParser(description='HostCut: validate + render a real-host cut (no mid-word rejoins).')
    ap.add_argument('src')
    ap.add_argument('--keep', required=True, help='comma list of start:end seconds, e.g. "18.9:42.0,52.6:75.3"')
    ap.add_argument('--out', help='output mp4 (omit with --check-only)')
    ap.add_argument('--check-only', action='store_true', help='validate THE HARD RULE and exit, no render')
    ap.add_argument('--forbid', default='', help='comma list of start:end spans (reset cues / flubs) no kept segment may overlap')
    ap.add_argument('--noise-db', type=float, default=-30.0)
    ap.add_argument('--min-d', type=float, default=0.06)
    ap.add_argument('--min-join-silence', type=float, default=DEFAULT_MIN_JOIN)
    ap.add_argument('--tol', type=float, default=0.05, help=f'head/tail exemption tolerance (clamped to {MAX_TOL}s)')
    ap.add_argument('--crf', type=int, default=18)
    args = ap.parse_args(argv)

    if args.tol > MAX_TOL:
        print(f'hostcut: warning: --tol {args.tol} exceeds ceiling; clamping to {MAX_TOL}s', file=sys.stderr)
    keep = _parse_ranges(args.keep)
    forbidden = _parse_ranges(args.forbid)
    duration = probe_duration(args.src)
    silences = detect_silences(args.src, noise_db=args.noise_db, min_d=args.min_d, duration=duration)
    try:
        assert_cuts_in_silence(keep, silences, duration, tol=args.tol,
                               min_join_silence=args.min_join_silence,
                               forbidden_spans=forbidden or None)
    except (MidWordRejoinError, ForbiddenSpanError, CutSpecError) as exc:
        sys.exit(f'REJECTED: {exc}')
    print(f'OK: {len(keep)} segments, all boundaries land in silence (>= {args.min_join_silence}s).')
    if args.check_only:
        return
    if not args.out:
        sys.exit('need --out to render (or pass --check-only)')
    # Pass the SAME validated map into render so the bytes are gated against it.
    render_cut(args.src, keep, args.out, tol=args.tol, min_join_silence=args.min_join_silence,
               forbidden_spans=forbidden or None, silences=silences, duration=duration, crf=args.crf)
    print(f'wrote {args.out}')


if __name__ == '__main__':
    main()
