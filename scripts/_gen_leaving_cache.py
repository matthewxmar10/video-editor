#!/usr/bin/env python3
"""Generate the Skep_Leaving diagrams cache from editorial rules (the agent is the brain).
Skepticism-folder style: MOSTLY face (scene 1); left/right caption splits ONLY on data/number
beats; a few punchy captions; a section title+blur card on each of the three deep-dive points.
Cache is indexed 1:1 with plan beats (beat 0 = the open)."""
import json, re

PLAN = json.load(open('src/methodology/officialTestBeatPlan.plan.json'))
WX = json.load(open('script/word-timings/Skep_Leaving-cut-wx.json'))
beats = PLAN['beats']

def beat_text(b):
    s, e = b['start'], b['start'] + b['dur']
    ws = [w['word'] for w in WX if s - 0.05 <= w['start'] < e]
    return ' '.join(ws)

def norm(t):
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]', ' ', t.lower())).strip()

_FILL = {'um','uh','er','erm','mm','hmm','uhh','umm','uhm','ah'}
def lead_gap(b):
    """seconds from the beat's start to its first spoken word — a big gap means a caption
    panel would sit empty at the top of the beat (a dead-spot), so such a beat stays face."""
    s, e = b['start'], b['start'] + b['dur']
    for w in WX:
        ws = w.get('start', w.get('s', 0))
        wt = w.get('word', w.get('t', ''))
        if s - 0.02 <= ws < e and any(c.isalnum() for c in wt) \
                and re.sub(r'[^a-z]', '', wt.lower()) not in _FILL:
            return ws - s
    return 0.0
LEAD_MAX = 0.6

# ── SECTION CARDS: the three deep-dive point openers (distinctive phrases) ──
SECTIONS = [
    ('the first point',                 {'label': 'POINT 1', 'title': 'Aging Out',    'word': 'first'}),
    ('the second point',                {'label': 'POINT 2', 'title': 'Politics',     'word': 'second'}),
    ('the third and biggest reason',    {'label': 'POINT 3', 'title': 'The Internet', 'word': 'third'}),
]
# also accept the ASR variant "the third and the biggest"
SECTION_ALT = {'the third and biggest reason': ['the third and the biggest', 'third and biggest reason']}

# ── DATA / NUMBER beats -> caption split (matched on ASR-robust phrases) ──
DATA_PHRASES = [
    'looking at the trends',            # 78 / 71 / 62 percent
    'religiously unaffiliated',         # 29 percent
    'switched religion',                # 35 percent (ASR: "switched religions")
    '18 to 24',                         # 46 vs 80 percent
    'fell by 25 points',                # liberals 62 -> 37
    '89 to 82',                         # conservatives (ASR: "fell for seven points")
    'negative teachings',               # PRRI 30 percent LGBTQ
    'always been like 99',              # hometown 99 -> 80 percent
]
# ── a few PUNCHY captions (light, spread out) ──
PUNCH_PHRASES = [
    'three main reasons',
    'infuriates me to no end',
    'quiet quitting',
    'loudest institutions',              # the recap ("why is Christianity failing")
]

def contains(text, phrase):
    return norm(phrase) in norm(text)

# HOMETOWN PHOTOS — shown in the glide panel on the beat that names the town.
PHOTO_SPECS = [
    ('permeated smaller towns',   {'img': 'photos/alva.png',      'label': 'Alva, Oklahoma', 'word': 'hometown'}),
    ('everybody you knew believed', {'img': 'photos/alvastone.png', 'label': 'Alva, Oklahoma', 'word': 'hometown'}),
]

cache = []
assigned = {'section': 0, 'photo': 0, 'data': 0, 'punch': 0, 'face': 0}
glide_i = 0
log = []
for i, b in enumerate(beats):
    txt = beat_text(b)
    entry = None
    kind = 'face'
    # hometown photo?
    photo = next((spec for ph, spec in PHOTO_SPECS if contains(txt, ph)), None)
    if photo:
        scene = 2 if glide_i % 2 == 0 else 3
        glide_i += 1
        entry = {'scene': scene, 'anim': 'photo', **photo}
        kind = 'photo'
    # section?
    if entry is None:
        for key, meta in SECTIONS:
            alts = [key] + SECTION_ALT.get(key, [])
            if any(contains(txt, a) for a in alts):
                entry = {'scene': 1, 'anim': 'section', 'title': meta['title'],
                         'label': meta['label'], 'word': meta['word']}
                kind = 'section'
                break
    if entry is None:
        is_data = any(contains(txt, p) for p in DATA_PHRASES)
        is_punch = any(contains(txt, p) for p in PUNCH_PHRASES)
        if (is_data or is_punch) and lead_gap(b) > LEAD_MAX:
            entry, kind = {'scene': 1}, 'face'    # long pre-sentence pause → stay on face, no empty panel
        elif is_data or is_punch:
            scene = 2 if glide_i % 2 == 0 else 3   # alternate right/left
            glide_i += 1
            entry = {'scene': scene}
            # the liberals beat: he said "the Pew Research Study, too" — whisperX heard the
            # "too" as "2"; drop that stray token from the caption (Matthew's note 2026-07-12).
            if contains(txt, 'fell by 25 points'):
                entry['drop'] = ['2']
            kind = 'data' if is_data else 'punch'
        else:
            entry = {'scene': 1}                    # FACE (mostly-face law)
            kind = 'face'
    assigned[kind] += 1
    cache.append(entry)
    if kind != 'face':
        log.append('%3d  %-8s scene%s  %s :: %s' % (
            i, kind, entry.get('scene'),
            (entry.get('label', '') + ' ' + entry.get('title', '')).strip(),
            ' '.join(txt.split()[:12])))

json.dump({'beats': cache}, open('script/word-timings/Skep_Leaving-cut-diagrams.json', 'w'), indent=1)
print('wrote cache: %d entries  %s' % (len(cache), assigned))
print('\nNON-FACE beats:')
print('\n'.join(log))
