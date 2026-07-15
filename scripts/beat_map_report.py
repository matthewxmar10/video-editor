#!/usr/bin/env python3
"""Beat map report — the REVIEW artifact, generated BEFORE any render.

For every beat in the plan: what's SAID (script-corrected when the writer's script is
given — the ASR's mishearings are NOT the truth of what was said), what's SHOWN (the
actual diagram spec — kind, items, anchors; built from the plan itself, never canned
descriptions that can drift from the render), what MOTION plays, and the TRANSITION.

    python3 scripts/beat_map_report.py <words-wx.json> <plan.ts|plan.plan.json> [out.md] [--script script.txt]

Always READ this after build_matched_plan.py, before rendering. If a row's SAID doesn't
match its SHOWN, or a beat looks too long, fix the diagrams cache / script text and
rebuild — don't render to find out.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# legacy (pre-diagram) styles keep honest baseline text
SHOWN_LEGACY = {
    'brollStream': 'B-ROLL STREAM — live editing timeline',
    'open': 'Host (on camera) — opening pull',
    'hostZoom': 'Host (on camera)',
    'glideR': 'Glide RIGHT (host in right panel)',
    'glideL': 'Glide LEFT (host in left panel)',
    'intro': 'INTRO ASSET — tight open → zoom-out',
    'storyFull': 'FULL-STAGE takeover (deliberate host absence)',
}

# One motion line per LIVE animation kind (the locked 10) — what the reviewer should
# expect to SEE moving across the beat. Keep in sync with the components.
KIND_MOTION = {
    'count': 'Socket wells cascade from frame 0 + a rail draws; number badges stamp on the '
             'count word; each well CHARGES (rim arc) then IGNITES its growth icon on its '
             'word; unison pulse on the last word',
    'timeline': 'Raw timeline builds; scissors snip each gray gap; the bar snaps tight and '
                'glows; checkmark badge pops on the emphasis word',
    'graph': 'L-frame + ticks cascade in; the channel tile plants at the origin; the growth '
             'line sweeps the frame to the beat end',
    'funnel': 'Channel chips fan in an arc with posting pings; arrows draw toward one spot; '
              'the $ orb ignites on "one" and flares on the emphasis word',
    'merge': 'Socket wells set the stage from frame 0; cards spin into wells on their item '
             'words; the row COLLAPSES on the merge word and one artifact card pops + flares',
    'pairs': 'Flowing waveform under a pinned playhead; a conveyor chain of clips ignites as '
             'it crosses; beat brackets ride the belt',
    'stack': 'The core arrives full-bleed and shrinks in with a bounce; radio waves ripple; '
             'each mark flies in on its name to orbit, igniting when the last docks',
    'roles': 'Marks pop on their brand words; glowing role words stamp beside them; all rows '
             'pulse once on the beat\'s last word',
    'upgrade': 'The core clicks in; branches grow outward to socket wells; a live micro-demo '
               'pops into each well on its word',
    'closer': 'The hanging "?" sweeps in, winks, and morphs into the glowing $ orb — final '
              'flare held to the last frame',
}


def load_words(wx_path, script_path=None):
    """WhisperX words; when the writer's script is given, word text is SCRIPT-CORRECTED
    (the same mapping the renderer uses) so SAID shows the truth, not ASR mishearings."""
    w = json.load(open(wx_path))
    words = w if isinstance(w, list) else w.get('words', [])
    if script_path and os.path.exists(script_path):
        import script_phrases
        ph = script_phrases.phrases(words, open(script_path).read())
        return [{'t': x['t'], 's': x['s'], 'e': x['e']} for p in ph for x in p['words'] if x['t'].strip()]
    return [{'t': (x.get('word') or x.get('t') or '').strip(),
             's': round(x.get('start', x.get('s', 0)), 2),
             'e': round(x.get('end', x.get('e', 0)), 2)} for x in words]


def load_beats(plan_path):
    """Prefer the sidecar plan JSON (the machine twin); fall back to the TS regex."""
    sidecar = re.sub(r'\.ts$', '.plan.json', plan_path)
    if plan_path.endswith('.json'):
        return json.load(open(plan_path))['beats']
    if os.path.exists(sidecar):
        return json.load(open(sidecar))['beats']
    src = open(plan_path).read()
    beats = []
    for m in re.finditer(r"\{ start: ([\d.]+), dur: ([\d.]+), style: \'(\w+)\'(.*) \},\s*$", src, re.M):
        beats.append({'start': float(m.group(1)), 'dur': float(m.group(2)), 'style': m.group(3)})
    return beats


def said_for(words, start, end):
    ws = [w['t'] for w in words if start - 0.05 <= w['s'] < end - 0.02]
    return ' '.join(ws) if ws else '(no words — pure visual beat)'


def fmt_item(it):
    bits = [it['t']]
    if it.get('mark'):
        bits.append('[%s]' % it['mark'])
    if it.get('hot'):
        bits.append('(hot)')
    return '"%s"@%.1fs %s' % (bits[0], it['at'], ' '.join(bits[1:])) if len(bits) > 1 else '"%s"@%.1fs' % (bits[0], it['at'])


def shown_for(b):
    base = SHOWN_LEGACY.get(b['style'], b['style'])
    dg = b.get('diagram')
    if not dg:
        return base + ' ⚠️ NO DIAGRAM (violates the one-beat-one-diagram law)'
    k = dg['kind']
    d = ('items: ' + ', '.join(fmt_item(i) for i in dg['items'])) if dg.get('items') else ''
    stage = 'FULL STAGE' if dg.get('stage') == 'full' else 'panel'
    hl = dg.get('headline')
    hs = ('HEADLINE "%s"@%.1fs + ' % (hl['t'], hl['at'])) if hl else ''
    return '%s + %sDIAGRAM %s (%s): %s' % (base, hs, k.upper(), stage, d)


DEVICE_KEYS = ('count', 'snip', 'pair', 'merge', 'roles', 'upg', 'sprint', 'funnel',
               'closer', 'items', 'chips', 'phrase')


def is_bare_cut(beats):
    """BARE-CUT law: no intro asset, no glides, no device keys anywhere -> an
    audio-cleaning pass; the renderer does NOTHING to the camera."""
    return all(b['style'] not in ('intro', 'glideR', 'glideL')
               and not any(b.get(k) for k in DEVICE_KEYS) for b in beats)


def motion_for(b, bare=False):
    if bare:
        return 'NONE — bare cut (audio cleaning only, camera untouched)'
    dg = b.get('diagram')
    if dg and KIND_MOTION.get(dg['kind']):
        return KIND_MOTION[dg['kind']]
    return {'open': 'Quick zoom-out hook (~0.65s), then holds into the glide', 'hostZoom': 'ONE slow push-in',
            'intro': 'Tight open → diagonal zoom-out'}.get(b['style'], '')


def build(words, beats, video_name, script_path=None):
    lines = [
        f'# Beat map — {video_name}',
        '',
        ('SAID is SCRIPT-CORRECTED (the writer\'s text on the spoken timeline). ' if script_path else
         'SAID is raw ASR (no script given — spellings may be wrong on screen too!). ')
        + 'SHOWN/MOTION are built from the plan\'s own diagram specs — what you read here is '
          'what renders. Review BEFORE rendering; fix the diagrams cache and rebuild if a row is off.',
        '',
        '| # | Time | Dur | Said (spoken words in this beat) | Shown | Motion | Transition → next |',
        '|---|------|-----|-----------------------------------|-------|--------|---------------------|',
    ]
    problems = 0
    bare = is_bare_cut(beats)
    for i, b in enumerate(beats):
        end = b['start'] + b['dur']
        said = said_for(words, b['start'], end)
        shown = shown_for(b)
        nxt = beats[i + 1] if i + 1 < len(beats) else None
        trans = 'End'
        if nxt:
            nd = nxt.get('diagram')
            trans = 'Hard cut → %s%s' % (SHOWN_LEGACY.get(nxt['style'], nxt['style']).split('(')[0].strip(),
                                         (' [' + nd['kind'] + ']') if nd else '')
        flag = ' ⚠️ LONG BEAT' if b['dur'] >= 12 else ''
        if '⚠️ NO DIAGRAM' in shown:
            problems += 1
        lines.append(f'| {i} | {b["start"]:.2f}s | {b["dur"]:.1f}s | {said} | {shown} | {motion_for(b, bare)} | {trans}{flag} |')
    total = beats[-1]['start'] + beats[-1]['dur']
    n_diag = sum(1 for b in beats if b.get('diagram'))
    kinds = [b['diagram']['kind'] for b in beats if b.get('diagram')]
    lines += [
        '',
        f'**{len(beats)} beats, {total:.1f}s total. Diagrams: {n_diag}/{len(beats)}'
        + (' ⚠️ COVERAGE INCOMPLETE' if n_diag < len(beats) else ' (full coverage)')
        + f'.** Kinds in order: {" → ".join(kinds)}.',
    ]
    if problems:
        lines.append(f'\n⚠️ {problems} beat(s) violate the one-beat-one-diagram law — DO NOT RENDER.')
    return '\n'.join(lines) + '\n'


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    script_path = None
    if '--script' in sys.argv:
        script_path = sys.argv[sys.argv.index('--script') + 1]
    wx_path, plan_path = args[0], args[1]
    out_path = args[2] if len(args) > 2 else re.sub(r'\.ts$', '-beatmap.md', plan_path)
    words = load_words(wx_path, script_path)
    beats = load_beats(plan_path)
    report = build(words, beats, plan_path, script_path)
    open(out_path, 'w').write(report)
    print(report)
    print(f'wrote {out_path}')


if __name__ == '__main__':
    main()
