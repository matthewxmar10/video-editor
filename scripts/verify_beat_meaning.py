#!/usr/bin/env python3
"""THE MEANING GATE — the describe-back mute test (Ryan 2026-07-02: "airtight motion
graphics that create the visual representation of the spoken script").

For every beat: extract the beat's FINAL frame (the state-change law says it must encode
the claim alone), crop to the diagram region, and ask a fresh Claude eye "what claim does
this graphic make?" with NO access to the script. Then compare that read-back against the
beat's actual sentence. A mismatch means the graphic does not say what the host says —
the exact failure the presence/motion gates are blind to.

Requires ANTHROPIC_API_KEY (env or repo .env). Without a key it prints the extraction
manifest and exits 0 with a loud warning — the eyes-on reviewer must run the mute test
by hand on the extracted frames.

    python3 scripts/verify_beat_meaning.py <plan.plan.json> <render.mp4> [--script script.txt]
"""
import base64
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from classify_beats_llm import _load_env  # repo .env loader (values already in env win)

MODEL = 'claude-opus-4-8'
OUTDIR = 'scratch_frames/meaning'


def region_for(style):
    if style in ('glideR', 'intro', 'open'):
        return (60, 120, 1120, 840)   # REGION['left']: cx 620, w 1120
    if style == 'glideL':
        return (740, 120, 1120, 840)  # REGION['right']: cx 1300, w 1120
    return (140, 100, 1640, 880)


def extract(mp4, t, crop, out):
    x, y, w, h = crop
    subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-y', '-ss', '%.3f' % t,
                    '-i', mp4, '-frames:v', '1', '-vf', 'crop=%d:%d:%d:%d' % (w, h, x, y), out],
                   check=True)


def beat_sentence(words, start, end):
    return ' '.join(w['t'] for w in words if start - 0.05 <= w['s'] < end - 0.02)


def ask(client, png_path, sentence):
    img = base64.standard_b64encode(open(png_path, 'rb').read()).decode()
    read = client.messages.create(
        model=MODEL, max_tokens=200,
        messages=[{'role': 'user', 'content': [
            {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png', 'data': img}},
            {'type': 'text', 'text':
                'This is one frame of a motion graphic from a video, shown WITHOUT sound. In one '
                'plain sentence: what claim is this graphic making? If you cannot tell, say '
                '"unclear" and name what confuses you.'}]}])
    claim = read.content[0].text.strip()
    judge = client.messages.create(
        model=MODEL, max_tokens=120,
        messages=[{'role': 'user', 'content':
            'A speaker says: "%s"\n\nA viewer who saw only the accompanying graphic (no sound) '
            'described it as: "%s"\n\nDoes the viewer\'s read MATCH the speaker\'s point — same '
            'subject, same claim, no contradiction? Answer exactly "MATCH" or "MISMATCH", then '
            'a one-sentence reason.' % (sentence, claim)}])
    verdict = judge.content[0].text.strip()
    return claim, verdict


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    plan_path, mp4 = args[0], args[1]
    script_path = sys.argv[sys.argv.index('--script') + 1] if '--script' in sys.argv else None
    plan = json.load(open(plan_path))
    beats = plan['beats']
    wx = plan.get('wx')
    words = []
    if wx and os.path.exists(wx):
        import script_phrases
        raw = json.load(open(wx))
        raw = raw if isinstance(raw, list) else raw.get('words', [])
        if script_path and os.path.exists(script_path):
            ph = script_phrases.phrases(raw, open(script_path).read())
            words = [{'t': x['t'], 's': x['s']} for p in ph for x in p['words'] if x['t'].strip()]
        else:
            words = [{'t': (x.get('word') or '').strip(), 's': round(x.get('start', 0), 2)} for x in raw]

    os.makedirs(OUTDIR, exist_ok=True)
    _load_env()
    key = os.environ.get('ANTHROPIC_API_KEY')
    client = None
    if key:
        try:
            import anthropic
            client = anthropic.Anthropic()
        except Exception as e:
            print('anthropic SDK unavailable (%s) — manual mute test required' % e)

    fails = []
    print('\nMEANING GATE — describe-back mute test on each beat\'s FINAL frame')
    print('-' * 96)
    for i, b in enumerate(beats):
        t = b['start'] + b['dur'] - min(0.4, b['dur'] / 4)
        out = os.path.join(OUTDIR, 'b%d-final.png' % i)
        extract(mp4, t, region_for(b['style']), out)
        sent = beat_sentence(words, b['start'], b['start'] + b['dur']) or '(unknown)'
        if client is None:
            print('%-3d %s  [frame: %s]  — NO KEY: mute-test this frame by hand' % (i, sent[:70], out))
            continue
        claim, verdict = ask(client, out, sent)
        ok = verdict.upper().startswith('MATCH')
        print('%-3d %-7s said: %s' % (i, 'MATCH' if ok else 'MISMATCH', sent[:68]))
        print('    graphic read as: %s' % claim[:90])
        if not ok:
            print('    judge: %s' % verdict[:90])
            fails.append(i)
    print('-' * 96)
    if client is None:
        print('MUTE TEST REQUIRED: frames are in %s/. OPERATING AGENT — describe the claim each '
              'frame makes BEFORE re-reading its sentence, then compare. A mismatch fails the '
              'edit: fix the diagrams cache and re-render.' % OUTDIR)
        return
    if fails:
        print('FAIL — %d beat(s) whose graphic does not say what the host says: %s' % (len(fails), fails))
        sys.exit(1)
    print('PASS — every beat\'s final frame reads back as the spoken claim.')


if __name__ == '__main__':
    main()
