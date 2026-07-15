#!/usr/bin/env python3
"""Generate the Skep_Story diagrams cache. Narrative video: MOSTLY face (scene 1), NO section
titles (per Matthew), left/right caption splits only on the two number lines, and a few punchy
captions on the memorable/thesis beats. Cache is indexed 1:1 with plan beats (beat 0 = open)."""
import json, re

PLAN = json.load(open('src/methodology/officialTestBeatPlan.plan.json'))
WX = json.load(open('script/word-timings/Skep_Story-cut-wx.json'))
beats = PLAN['beats']

def beat_text(b):
    s, e = b['start'], b['start'] + b['dur']
    return ' '.join(w.get('word', w.get('t', '')) for w in WX if s - 0.05 <= w.get('start', w.get('s', 0)) < e)

def norm(t):
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]', ' ', t.lower())).strip()

_FILL = {'um','uh','er','erm','mm','hmm','uhh','umm','uhm','ah'}
def lead_gap(b):
    s, e = b['start'], b['start'] + b['dur']
    for w in WX:
        ws = w.get('start', w.get('s', 0))
        wt = w.get('word', w.get('t', ''))
        if s - 0.02 <= ws < e and any(c.isalnum() for c in wt) \
                and re.sub(r'[^a-z]', '', wt.lower()) not in _FILL:
            return ws - s
    return 0.0
LEAD_MAX = 0.6

def contains(text, phrase):
    return norm(phrase) in norm(text)

# HOMETOWN PHOTOS (Matthew's photos) — shown in the glide panel on the beat that names them.
# (match phrase, {img, label, cue word})
PHOTO_SPECS = [
    ('called Alva',              {'img': 'photos/alva.png',           'label': 'Alva, Oklahoma',        'word': 'Alva'}),
    ('splitting my time heavily', {'img': 'photos/baptistchurch.jpeg', 'label': 'First Baptist Church',   'word': 'Baptist'}),
    ('pastor i was closest to',  {'img': 'photos/nazarenechurch.png', 'label': 'Church of the Nazarene', 'word': 'Nazarene'}),
    ('led people to be a bit hateful', {'img': 'photos/alvahighschool.jpg', 'label': 'Alva High School',   'word': 'high'}),
    ('my own hometown is',       {'img': 'photos/alvastone.png',      'label': 'Alva, Oklahoma',        'word': 'hometown'}),
]

# DATA / NUMBER beats -> caption split (the two percentage lines)
DATA_PHRASES = [
    'to 99',            # "95 to 99% of my town was Christian"
    'to like 80',       # "down to like 80% Christian"
]
# a few PUNCHY captions (memorable / thesis lines), spread across the story
PUNCH_PHRASES = [
    'why are we saying these things',
    'devil has your soul',
    'more empathetic',
    'deeply personal',
    'exposed to different beliefs',
]

cache = []
assigned = {'data': 0, 'punch': 0, 'face': 0}
glide_i, log = 0, []
assigned['photo'] = 0
for i, b in enumerate(beats):
    txt = beat_text(b)
    photo = next((spec for ph, spec in PHOTO_SPECS if contains(txt, ph)), None)
    is_data = any(contains(txt, p) for p in DATA_PHRASES)
    is_punch = any(contains(txt, p) for p in PUNCH_PHRASES)
    if photo:                                   # a real place named -> show its photo (glide)
        scene = 2 if glide_i % 2 == 0 else 3
        glide_i += 1
        cache.append({'scene': scene, 'anim': 'photo', **photo})
        kind = 'photo'
        log.append('%3d  photo  scene%d  %-22s %s' % (i, scene, photo['label'], ' '.join(txt.split()[:8])))
    elif (is_data or is_punch) and lead_gap(b) > LEAD_MAX:
        cache.append({'scene': 1})              # long pre-sentence pause → stay on face
        kind = 'face'
    elif is_data or is_punch:
        scene = 2 if glide_i % 2 == 0 else 3
        glide_i += 1
        cache.append({'scene': scene})
        kind = 'data' if is_data else 'punch'
        log.append('%3d  %-6s scene%d  %s' % (i, kind, scene, ' '.join(txt.split()[:12])))
    else:
        cache.append({'scene': 1})
        kind = 'face'
    assigned[kind] += 1

json.dump({'beats': cache}, open('script/word-timings/Skep_Story-cut-diagrams.json', 'w'), indent=1)
print('wrote cache: %d entries  %s' % (len(cache), assigned))
print('\nNON-FACE beats:')
print('\n'.join(log))
