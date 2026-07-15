#!/usr/bin/env python3
"""Second-pass trim on the Skep_Leaving cut: remove the fumble (a false-start pause) and the
'um' fillers Matthew flagged. Boundaries are placed in WORD-FREE gaps verified against the
whisperX word times (a precise equivalent of hostcut's silence rule: no boundary sits inside
any word, so nothing clips). Only fillers with a real gap on BOTH sides are cut — an 'um'
wedged against the next word is left, since cutting it would clip the following word."""
import json, re, subprocess, sys
sys.path.insert(0, 'scripts')
import hostcut

SRC = 'public/host/Skep_Leaving-cut.mp4'
OUT = 'public/host/Skep_Leaving-cut2.mp4'
W = json.load(open('script/word-timings/Skep_Leaving-cut-wx.json'))
clean = lambda s: re.sub(r'[^a-z]', '', s.lower())
dur = hostcut.probe_duration(SRC)
MARGIN = 0.06          # leave this much clear of any neighbouring word
MIN_GAP = 0.12         # a side needs at least this gap to cut cleanly

def in_word(t):
    return any(w['start'] + 0.01 < t < w['end'] - 0.01 for w in W)

removals = []
# 1) THE FUMBLE — the ~1.84s hesitation between "…to go" and "to a non-denominational church"
go = next(w for w in W if 340.5 < w['start'] < 341.5 and clean(w['word']) == 'go')
gi = W.index(go)
nxt = W[gi + 1]                                   # "to" at ~343.03
cb, ce = round(go['end'] + 0.15, 3), round(nxt['start'] - 0.15, 3)
removals.append(('FUMBLE', cb, ce))

# 2) the um/uh fillers with a real gap on both sides
for i, w in enumerate(W):
    if clean(w['word']) not in ('um', 'uh', 'umm', 'uhh', 'erm', 'uhm'):
        continue
    prev, nx = W[i - 1], W[i + 1]
    gb, ga = w['start'] - prev['end'], nx['start'] - w['end']
    if gb < MIN_GAP or ga < MIN_GAP:
        print('  LEAVE %-5s [%.2f-%.2f]  gap_before=%.2f gap_after=%.2f (would clip %s)'
              % (w['word'].strip(), w['start'], w['end'], gb, ga,
                 prev['word'] if gb < MIN_GAP else nx['word']))
        continue
    cb = round(max(w['start'] - MARGIN, prev['end'] + MARGIN), 3)
    ce = round(min(w['end'] + MARGIN, nx['start'] - MARGIN), 3)
    removals.append(('FILL:' + w['word'].strip(), cb, ce))

# verify every boundary is word-free, then invert to a KEEP list
for lbl, cb, ce in removals:
    assert not in_word(cb) and not in_word(ce), 'boundary inside a word: %s %s %s' % (lbl, cb, ce)
    print('  CUT   %-11s remove [%.2f-%.2f]  (%.2fs)' % (lbl, cb, ce, ce - cb))

spans = sorted((cb, ce) for _, cb, ce in removals)
keep, cur = [], 0.0
for s, e in spans:
    if s - cur > 0.05:
        keep.append((round(cur, 3), round(s, 3)))
    cur = max(cur, e)
if dur - cur > 0.05:
    keep.append((round(cur, 3), round(dur, 3)))

print('\nremoving %d span(s), %.2fs total; %d keep segments'
      % (len(spans), sum(e - s for s, e in spans), len(keep)))
hostcut.validate_keep_segments(keep, dur)          # structural sanity (monotonic, in-bounds)
fg = hostcut._build_filtergraph(keep)
cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-i', SRC, '-filter_complex', fg,
       '-map', '[outv]', '-map', '[outa]', '-c:v', 'libx264', '-crf', '18',
       '-preset', 'medium', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', OUT]
subprocess.run(cmd, check=True)
print('wrote', OUT, '(%.1fs)' % hostcut.probe_duration(OUT))
