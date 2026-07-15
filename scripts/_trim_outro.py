#!/usr/bin/env python3
"""Remove the spoken "Mind on Religion" channel name from each outro (Matthew is renaming the
channel). Boundaries sit in word-free gaps verified against the whisperX word times."""
import json, subprocess, sys
sys.path.insert(0, 'scripts')
import hostcut

JOBS = [
    # (cut path, wx path, remove [start,end], what it leaves)
    ('public/host/Skep_Leaving-cut.mp4', 'script/word-timings/Skep_Leaving-cut-wx.json',
     898.90, 900.18, 'Matthew. I\'ll see you'),
    ('public/host/Skep_Story-cut.mp4', 'script/word-timings/Skep_Story-cut-wx.json',
     813.25, 814.02, 'tuning in. My name is Matthew'),
]

for src, wxp, cb, ce, note in JOBS:
    W = json.load(open(wxp))
    def in_word(t):
        return any(w['start'] + 0.01 < t < w['end'] - 0.01 for w in W)
    assert not in_word(cb) and not in_word(ce), 'boundary inside a word: %s %.2f/%.2f' % (src, cb, ce)
    dur = hostcut.probe_duration(src)
    keep = [(0.0, round(cb, 3)), (round(ce, 3), round(dur, 3))]
    hostcut.validate_keep_segments(keep, dur)
    out = src.replace('.mp4', '-o.mp4')
    fg = hostcut._build_filtergraph(keep)
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-i', src, '-filter_complex', fg,
           '-map', '[outv]', '-map', '[outa]', '-c:v', 'libx264', '-crf', '18',
           '-preset', 'medium', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', out]
    subprocess.run(cmd, check=True)
    subprocess.run(['mv', out, src], check=True)
    print('trimmed %s: removed [%.2f-%.2f] -> "%s"  (%.1fs)' % (src, cb, ce, note, hostcut.probe_duration(src)))
