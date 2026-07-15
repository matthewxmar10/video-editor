#!/usr/bin/env python3
"""SPOKEN BEAT -> visual beat plan. The writer's SCRIPT is the timeline: each blank-line
paragraph is one SPOKEN BEAT, and ONE visual owns each spoken beat for exactly as long as it
is spoken (whisperX word times). Devices come from the LOCKED structural rotation (host ↔
device, ring glideR → takeover → glideL; a list paragraph becomes a deck) — see
build_beats_spoken. Beats are CONTIGUOUS (no gaps, no half-second flashes) and every cut
snaps into the inter-word silence. Deterministic: same script + same words -> same plan.

  python3 scripts/build_matched_plan.py <words-wx.json> <out.ts> --script script/<name>.txt

(No --script → a script is synthesized from the transcript; the SAME pipeline runs.)
"""
import json
import os
import re
import sys

import classify_beats_llm as C   # the diagrams-cache reader (the agent is the editorial tier)

def _apply_prefs(prefs, path):
    """Overlay one BOUNDED style-knob file onto `prefs` in place (unknown keys ignored —
    preferences can only turn knobs that exist; laws are not knobs)."""
    if not path or not os.path.exists(path):
        return
    try:
        raw = json.load(open(path))
        al = [x for x in (raw.get('scenes', {}).get('allowed') or []) if x in (1, 2, 3)]
        if al:
            prefs['scenes']['allowed'] = al
        g = raw.get('scenes', {}).get('glide')
        if g in ('left', 'right', 'either'):
            prefs['scenes']['glide'] = g
        if 'banned' in (raw.get('animations') or {}):
            prefs['animations']['banned'] = [a for a in (raw['animations'].get('banned') or [])
                                             if isinstance(a, str)]
        # GREEN-SCREEN mode (bloomers): a channel can composite its keyed host over an animated
        # flower background instead of the charcoal grid. Passed through to the plan verbatim.
        if isinstance(raw.get('greenScreen'), dict):
            prefs['greenScreen'] = raw['greenScreen']
    except Exception as e:
        sys.stderr.write('%s unreadable (%s) — skipped\n' % (path, e))


def _load_prefs():
    """BOUNDED style knobs (scenes allowed, glide direction, banned animations). Loads the
    global style-preferences.json, then overlays a PER-CHANNEL Channels/<name>/style.json when
    CONTENT_ENGINE_PREFS points at one (edit_video.sh sets it from the recording's channel
    folder). So each channel edits by its own knobs; the global file is the fallback default."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    prefs = {'scenes': {'allowed': [1, 2, 3], 'glide': 'either'}, 'animations': {'banned': []}, 'greenScreen': None}
    _apply_prefs(prefs, os.path.join(root, 'style-preferences.json'))
    _apply_prefs(prefs, os.environ.get('CONTENT_ENGINE_PREFS'))  # per-channel override
    return prefs

PREFS = _load_prefs()


def _load_installed():
    """The animation kinds ACTUALLY INSTALLED (src/animations/<kind>/), from the generated
    catalog. The plan never emits — and the picker never offers — an animation whose folder
    isn't present, so an empty animations dir yields a caption/host base (no packs installed).
    Falls back to scanning the folders, then to empty."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cat = os.path.join(root, 'src', 'animations', 'catalog.generated.json')
    try:
        return {e['kind'] for e in json.load(open(cat)) if e.get('kind')}
    except Exception:
        pass
    adir = os.path.join(root, 'src', 'animations')
    try:
        return {d for d in os.listdir(adir)
                if not d.startswith('_') and os.path.exists(os.path.join(adir, d, 'index.tsx'))}
    except Exception:
        return set()

INSTALLED = _load_installed()

FPS = 30
MIN_BEAT_S = 2.0
OPEN_S = 2.0   # the opening zoom-out is ALWAYS ~this long, then jump-cuts to the first beat
#                (Ryan 2026-07-01) — regardless of how long the first sentence happens to run.
LEAD = 0.60   # MAX anticipation: the cut lands right after the previous sentence ends (so
#               the OLD beat never carries a fragment of the host recovering/looking away —
#               Ryan 2026-07-02, the big-test "looks left off camera" seam) and the new
#               scene's foundation cascade owns the pre-word gap; only pauses kept longer
#               than this (rare after the hostcut floors) cap the lead.
PAD = 0.02    # keep the cut this far off the previous word's end (never clip it)


def load_sentences(path):
    w = json.load(open(path))
    words = w if isinstance(w, list) else w.get('words', [])
    def gw(x): return (x.get('word') or x.get('t') or '').strip()
    def gs(x): return round(x.get('start', x.get('s')), 2)
    def ge(x): return round(x.get('end', x.get('e')), 2)
    sents, cur = [], []
    for x in words:
        cur.append({'t': gw(x), 's': gs(x), 'e': ge(x)})
        if gw(x).endswith(('.', '?', '!')):
            sents.append(cur); cur = []
    if cur:
        sents.append(cur)
    return sents


def find_phrase(sent, phrase):
    def clean(s): return ''.join(c for c in s.lower() if c.isalnum())
    pw = [clean(p) for p in phrase.split()]
    cw = [clean(x['t']) for x in sent]
    for i in range(len(cw) - len(pw) + 1):
        if cw[i:i + len(pw)] == pw:
            return [{'t': sent[i + k]['t'].strip('.,?!'), 'at': sent[i + k]['s']} for k in range(len(pw))]
    out, j = [], 0
    for p in pw:
        while j < len(cw) and cw[j] != p:
            j += 1
        if j < len(cw):
            out.append({'t': sent[j]['t'].strip('.,?!'), 'at': sent[j]['s']}); j += 1
    return out


def word_time(sents, si, needle):
    for x in sents[si]:
        if needle in x['t'].lower():
            return x['s']
    return sents[si][0]['s']


def quote_emphasis(quote):
    """(emphasis_word, token_index) for the *asterisked* word in a QuoteTakeover string. The
    index mirrors QuoteTakeover.parseQuote (the emphasis PHRASE is one token; the words before
    it split on whitespace) so we know how many words type before the emphasis box wipes in.
    Returns (None, 0) when the quote carries no emphasis."""
    m = re.search(r'\*([^*]+)\*', quote)
    if not m:
        return None, 0
    idx = len(quote[:m.start()].split())          # quote words that type before the emphasis
    emph = m.group(1).strip().split()[0]           # first word of the emphasis phrase
    return emph, idx


def spoken_time(sent, word):
    """Whisper-X start time of `word` in a sentence (exact cleaned match first, then loose)."""
    def clean(s): return ''.join(c for c in s.lower() if c.isalnum())
    c = clean(word)
    for x in sent:
        if clean(x['t']) == c:
            return x['s']
    for x in sent:
        if c and c in clean(x['t']):
            return x['s']
    return None


def esc(s):
    return s.replace('\\', '\\\\').replace("'", "\\'")


def _clean(s):
    return ''.join(c for c in s.lower() if c.isalnum())


def item_anchor(words, item):
    """Anchor a deck item to the word where it is SPOKEN. The ASR may split one item across
    several words ("B-roll" -> 'B','roll'; "sound effects" -> two words), so the cleaned item
    is matched against the running join of up to 4 consecutive cleaned words; the anchor is
    the FIRST word of the span. A single-word item behaves exactly as before (startswith, so
    item 'transition' still hits the word 'transitions,')."""
    key = _clean(item)
    if not key:
        return None
    for j in range(len(words)):
        acc = ''
        for k in range(j, min(j + 4, len(words))):
            acc += _clean(words[k]['t'])
            if acc.startswith(key):
                return words[j]
            if len(acc) >= len(key):
                break
    return None


# emphasis = the strongest CONTENT word of a caption (skip filler/function words and the
# "number one/two/three" scaffolding), preferring the last one so the beat lands on its point.
STOP = {'number', 'one', 'two', 'three', 'your', 'this', 'that', 'with', 'from', 'into', 'here',
        'they', 'them', 'have', 'will', 'what', 'when', 'then', 'than', 'about', 'their', 'were',
        'because', 'which', 'while', 'would', 'could', 'should', 'these', 'those', 'there', 'been',
        'some', 'even', 'also', 'just', 'like', 'made', 'does', 'done', 'much', 'find', 'important'}


def emph(cap):
    best, bl = -1, 0
    for k, w in enumerate(cap):
        c = _clean(w['t'])
        if len(c) >= 4 and c not in STOP and len(c) >= bl:
            bl, best = len(c), k
    return best


# ── HostDress derivation (official template: "host beats are never bare") ──────────────────
BRANDS = {'claude': 'Claude', 'remotion': 'Remotion', 'whisperx': 'WhisperX', 'whisper': 'Whisper'}
NUM_WORDS = {'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
             'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10'}


def count_pop(words):
    """The first spoken NUMBER in a beat -> a big numeral pop on its word ("It does THREE
    important things" plants a glowing 3 the frame it's said). Mechanical: number words +
    digits; any script with a spoken count gets it free."""
    for w in words:
        c = _clean(w['t'])
        if c in NUM_WORDS:
            return {'t': NUM_WORDS[c], 'at': w['s']}
        if c.isdigit():
            return {'t': c, 'at': w['s']}
    return None


def count_fx(words, cap):
    """A COUNT beat ("It does THREE important things…") -> the CountSlots overlay
    (animation #10, rebuilt 2026-07-03 from the approved 2026-07-01 grammar): socket
    wells set the stage from the beat's first frames, the number badges stamp on the
    COUNT word, and each well IGNITES on its own spoken content word — the last on the
    beat's emphasis word. Mechanical: a spoken count of 2-4."""
    num = count_pop(words)
    if not num or not num['t'].isdigit():
        return None
    n = int(num['t'])
    if not 2 <= n <= 4:
        return None
    ei = emph(cap)
    end_at = cap[ei]['at'] if ei >= 0 else words[-1]['s']
    if end_at <= num['at'] + 0.4:
        end_at = words[-1]['s']
    # n-1 ignite anchors: even time-targets between the count and the emphasis word,
    # each SNAPPED to its nearest spoken content word (word-timed, never interpolated)
    cands = [w['s'] for w in words
             if num['at'] + 0.2 < w['s'] < end_at - 0.2
             and len(_clean(w['t'])) >= 4 and _clean(w['t']) not in STOP]
    ignites = []
    for k in range(1, n):
        target = num['at'] + (end_at - num['at']) * k / n
        free = [c for c in cands if c not in ignites]
        ignites.append(min(free, key=lambda c: abs(c - target)) if free else round(target, 2))
    ignites = sorted(ignites) + [end_at]
    return {'at': round(num['at'], 2), 'n': n,
            'ignites': [{'at': round(t, 2)} for t in ignites],
            'doneAt': round(words[-1]['s'], 2)}


# ── host-beat STORY overlays (SB3+, rolling out beat-by-beat) ───────────────────────────
CUT_WORDS = {'cut', 'cuts', 'cutting', 'trim', 'trims', 'trimming', 'remove', 'removes',
             'removed', 'removing'}
DEAD_WORDS = {'dead', 'space', 'spaces', 'silence', 'silences', 'pause', 'pauses'}


FAST_WORDS = {'fast', 'faster', 'quick', 'quickly', 'rapidly'}
CHANNEL_WORDS = {'channel', 'channels', 'youtube', 'video', 'videos'}
BUILD_WORDS = {'build', 'building', 'start', 'starting', 'grow', 'growing', 'creating'}


def channel_sprint(words):
    """A host beat promising SPEED of channel-building ("how FAST you can start BUILDING a
    YouTube CHANNEL") -> the ChannelSprint time-lapse: a mini channel panel pops on the FAST
    word, video tiles rapid-tick and a growth curve draws from the BUILD word to the end of
    that sentence. Mechanical: a FAST word + a CHANNEL word in one beat."""
    fast = next((w for w in words if _clean(w['t']) in FAST_WORDS), None)
    chan = next((w for w in words if _clean(w['t']) in CHANNEL_WORDS), None)
    if not fast or not chan:
        return None
    build = next((w for w in words if w['s'] >= fast['s'] and _clean(w['t']) in BUILD_WORDS), fast)
    end = next((w for w in words if w['s'] >= chan['s'] and w['t'].strip().endswith(('.', '?', '!'))), words[-1])
    # the FOUNDATION (axes stroke) starts WITH THE BEAT — a beat-lead ~0.35s before the
    # first spoken word (Ryan 2026-07-02: "before the spoken word of 'but'"), so the cut
    # always lands on a scene already in motion, never a bare host.
    return {'igniteAt': round(words[0]['s'] - 0.35, 2), 'at': round(fast['s'], 2), 'buildAt': round(build['s'], 2), 'endAt': round(end['s'] + 0.5, 2)}


MONEY_WORDS = {'money', 'make', 'revenue', 'profit', 'earn', 'earnings', 'income'}


MULTI_WORDS = {'multiple', 'many', 'several', 'dozens'}
POINT_WORDS = {'pointing', 'point', 'points', 'funnel', 'funneling', 'feeding', 'converge', 'converging', 'driving'}
PLATFORMS = {'youtube': 'YouTube', 'instagram': 'Instagram', 'tiktok': 'TikTok', 'facebook': 'Facebook', 'twitter': 'X', 'linkedin': 'LinkedIn'}


def pair_fx(words, cap):
    """A takeover beat DESCRIBING the word->visual pairing ("…every spoken word gets paired
    with a matching visual") -> the PairMap self-demo scene (stage up from the beat's first
    frame — never an empty grid). Mechanical: a PAIR word plus 'word(s)' or 'visual(s)' in
    the beat. Pairs run from the first PAIR word to the last 'visual'/final word."""
    pair = next((w for w in words if _clean(w['t']) in PAIR_WORDS), None)
    has_ctx = any(_clean(w['t']) in ('word', 'words', 'visual', 'visuals') for w in words)
    if not pair or not has_ctx:
        return None
    vis = [w for w in words if _clean(w['t']) in ('visual', 'visuals')]
    end = vis[-1]['s'] if vis else words[-1]['s']
    if end <= pair['s'] + 0.4:
        end = min(pair['s'] + 1.5, words[-1]['s'])
    return {'pairStart': round(pair['s'], 2), 'pairEnd': round(end, 2)}
def role_call(words):
    """A host beat ASSIGNING JOBS to the tools ("Claude Code is the BUILDER, Remotion is the
    EDITOR, WhisperX is the LISTENER…") -> RoleCall rows, fully word-anchored: each official
    mark pops on its BRAND word, its role stamps on the ROLE word. Mechanical: a BRANDS hit
    followed within a few words by 'is' + 'the' + a content word. Needs >=2 pairs."""
    out = []
    for idx, w in enumerate(words):
        b = BRANDS.get(_clean(w['t']))
        if not b:
            continue
        seen_is = seen_the = False
        for k in range(idx + 1, min(idx + 7, len(words))):
            c = _clean(words[k]['t'])
            if not seen_is:
                seen_is = c == 'is'
                continue
            if not seen_the:
                seen_the = c == 'the'
                continue
            out.append({'t': b, 'at': round(w['s'], 2), 'role': words[k]['t'].strip('.,?!'), 'roleAt': round(words[k]['s'], 2)})
            break
    return out if len(out) >= 2 else None
def upgrade_fx(words, cap):
    """A glide beat PITCHING upgrades ("keep UPGRADING it with new motion graphics, new
    styles and endless customizations") -> the UpgradeBay: the mini engine core clicks in
    on its 'engine'/'installed' word, then a module chip SNAPS ON per enumerated item.
    Mechanical: an UPGRADE word + 'new <thing>' groups (label = following content words up
    to a spoken-comma boundary); the beat's emphasis word joins as the final chip."""
    if not any(_clean(w['t']) in UPGRADE_WORDS for w in words):
        return None
    items = []
    for idx, w in enumerate(words):
        if _clean(w['t']) == 'new' and idx + 1 < len(words):
            lab = []
            for k in range(idx + 1, min(idx + 3, len(words))):
                c = words[k]['t'].strip()
                if _clean(c) in ('new', 'and'):
                    break
                lab.append(c.strip('.,?!'))
                if c.endswith((',', '.')):
                    break
            if lab:
                items.append({'t': ' '.join(lab), 'at': round(words[idx + 1]['s'], 2)})
    ei = emph(cap)
    if ei >= 0 and not any(cap[ei]['t'].lower() in it['t'].lower() for it in items):
        items.append({'t': cap[ei]['t'], 'at': round(cap[ei]['at'], 2)})
    if len(items) < 2:
        return None
    # FOUNDATION LAW: the core is on stage from the beat cut; the CLICK stays word-timed
    core_at = words[0]['s'] - 0.35
    click_at = next((w['s'] for w in words if _clean(w['t']) in ('installed', 'install')), core_at + 0.3)
    up_at = next(w['s'] for w in words if _clean(w['t']) in UPGRADE_WORDS)
    return {'coreAt': round(core_at, 2), 'clickAt': round(click_at, 2), 'upAt': round(up_at, 2), 'items': items}
def closer_fx(words):
    """The OUTRO closer ("Good QUESTION. I wonder how much MONEY you'd MAKE."): SB9's
    circled '?' returns on the question word, winks once, then MORPHS inside its circle
    into SB10's $ orb on the money word — the question becomes money — flaring on the
    beat's last word and holding to the video's final frame. Mechanical: a QUESTION word
    followed by a MONEY word in one host beat."""
    q = next((w for w in words if _clean(w['t']) in ('question', 'questions')), None)
    m = next((w for w in words if q and w['s'] > q['s'] and _clean(w['t']) in MONEY_WORDS), None)
    if not q or not m:
        return None
    return {'qAt': round(q['s'], 2), 'moneyAt': round(m['s'], 2), 'endAt': round(words[-1]['s'], 2)}


def deck_merge(words, items):
    """A deck whose tail says "…into ONE <artifact>" CONVERGES (SB5: "…into one uploadable
    mp4"): the landed cards collapse into a single glowing artifact card on 'one', flaring
    on the format word. Mechanical: 'one' spoken after the last list item; the artifact word
    is mp4/file/video/package (else the beat's last word)."""
    last_item = items[-1]['at']
    one = next((w for w in words if w['s'] > last_item and _clean(w['t']) == 'one'), None)
    if not one:
        return None
    done = next((w for w in words if w['s'] > one['s'] and _clean(w['t']) in ('mp4', 'file', 'video', 'package')), None)
    return {'at': round(one['s'], 2), 'doneAt': round((done or words[-1])['s'], 2)}


def funnel_fx(words, cap):
    """A glide beat CONVERGING many channels into one destination ("MULTIPLE YouTube and
    Instagram channels … all POINTING to ONE high converting offer") -> the OfferFunnel:
    node wells cascade with the beat cut (the foundation law), platform marks land on
    their spoken words, lines DRAW from every node on the POINT word, the offer orb
    ignites on 'one', flaring on the emphasis word. Mechanical: a MULTI word + a POINT
    word + 'one' after it."""
    if not any(_clean(w['t']) in MULTI_WORDS for w in words):
        return None
    pt = next((w for w in words if _clean(w['t']) in POINT_WORDS), None)
    one = next((w for w in words if pt and w['s'] > pt['s'] and _clean(w['t']) == 'one'), None)
    if not pt or not one:
        return None
    plats, seen = [], set()
    for w in words:
        p = PLATFORMS.get(_clean(w['t']))
        if p and p not in seen:
            seen.add(p)
            plats.append({'t': p, 'at': round(w['s'], 2)})
    fl = next((w for w in words if _clean(w['t']).startswith('faceless')), None)
    ei = emph(cap)
    done = cap[ei]['at'] if ei >= 0 and cap[ei]['at'] > one['s'] else one['s'] + 0.8
    if plats:
        # SUBJECT-EARLY law: the first platform mark mounts with the cut (empty glass
        # wells alone read under the presence floor), the rest stay word-timed
        plats[0]['at'] = round(words[0]['s'] - 0.15, 2)
    out = {'startAt': round(words[0]['s'] - 0.35, 2), 'pointAt': round(pt['s'], 2),
           'oneAt': round(one['s'], 2), 'doneAt': round(done, 2), 'plats': plats}
    if fl:
        out['facelessAt'] = round(fl['s'], 2)
    al = [w for w in words if w['s'] < pt['s'] and _clean(w['t']) == 'all']
    if al:
        # "they ALL were pointing" — every node pulses in unison on its word
        out['allAt'] = round(al[-1]['s'], 2)
    return out


UPGRADE_WORDS = {'upgrade', 'upgrades', 'upgrading', 'upgraded'}
ENGINE_WORDS = {'installed', 'install', 'engine', 'system'}


def diagram_items(cap):
    """The beat's 2-3 KEY WORDS as diagram items (word-timed icon cards) — the motion-first
    takeover default. Deterministic pick: content words scored by length + proper-noun bonus,
    top 3, in spoken order, min 0.6s apart so cards never pile up."""
    def score(w, k):
        t = w['t']
        c = _clean(t)
        if len(c) < 4 or c in STOP:
            return 0
        return len(c) + (3 if k > 0 and t[:1].isupper() else 0) + (2 if w.get('big') else 0)
    ranked = sorted(((score(w, k), k) for k, w in enumerate(cap)), reverse=True)
    picked = []
    for s, k in ranked:
        if s <= 0 or len(picked) == 3:
            break
        if all(abs(cap[k]['at'] - cap[j]['at']) >= 0.6 for j in picked):
            picked.append(k)
    if len(picked) < 2:
        return None
    return [{'t': cap[k]['t'], 'at': cap[k]['at']} for k in sorted(picked)]


# ── STORY DIAGRAMS (Ryan 2026-07-02, supersedes the host↔device rotation): ONE SPOKEN ──
# BEAT = ONE MOTION OVERLAY — a moving diagram matched to that beat's content, alive for
# the WHOLE beat. No bare-host beats, no caption walls. Camera stays deterministic: the
# host rides alternating glides (the spine); `stage: full` takeovers are the deliberate
# absences. Spec source: the diagrams cache / Claude (classify_beats_llm.diagram_decisions),
# else the rule tier below — which ALWAYS returns a diagram, so coverage is total.

VS_WORDS = {'beat', 'beats', 'versus', 'vs', 'against', 'defeated', 'played', 'plays'}
OUT_WORDS = {'out', 'injured', 'suspended', 'banned', 'gone'}
IN_WORDS = {'come', 'coming', 'join', 'joins', 'joining', 'enter', 'enters'}
WALL_WORDS = {'stonewall', 'keeper', 'goalkeeper', 'wall', 'defense'}
TEAM_WORDS = {'players', 'team', 'squad', 'roster', 'group', 'crew'}
PLURAL_COUNT_HINTS = 4   # a count is an enumeration if a plural content word follows within this many words


def proper_nouns(sb_words):
    """Capitalized mid-sentence content words, in spoken order (dedup by cleaned text)."""
    out, seen, prev_end = [], set(), True
    for w in sb_words:
        t = w['t'].strip()
        c = _clean(t)
        if not c:
            continue
        core = t.strip('.,?!')
        if (t[:1].isupper() and not prev_end and not c.isdigit()
                and (len(c) >= 3 or (core.isupper() and len(c) == 2))   # 'US', 'LA' count
                and c not in STOP and c not in seen):
            seen.add(c)
            out.append(w)
        prev_end = t.endswith(('.', '?', '!'))
    return out


def _numval(c):
    if c.isdigit():
        return int(c)
    return int(NUM_WORDS.get(c, 0) or 0)


def _headline(text, at, emph_idx=None):
    """A designed HEADLINE (the scene-grammar claim slot): UPPER display copy + land time."""
    o = {'t': ' '.join(text.split()).upper(), 'at': round(at, 2)}
    if emph_idx is not None:
        o['emph'] = emph_idx
    return o


PAIR_WORDS = {'paired', 'pair', 'pairs', 'pairing', 'matched', 'matching', 'matches'}


def snip_fx(words, cap):
    """A host beat DESCRIBING the dead-space cut ("…cuts out all of the dead spaces…") ->
    the TimelineSnip story overlay, fully word-anchored: the bar builds on 'video' (or just
    before the cut word), the snips ride the cut→dead-space span, the done-glow lands on the
    beat's emphasis word. Mechanical keyword rule: a CUT word + a DEAD word in one beat."""
    cut = next((w for w in words if _clean(w['t']) in CUT_WORDS), None)
    dead = [w for w in words if _clean(w['t']) in DEAD_WORDS]
    if not cut or not dead:
        return None
    last_dead = dead[-1]
    vid = next((w for w in words if _clean(w['t']) == 'video'), None)
    bar_at = vid['s'] if vid and vid['s'] < cut['s'] else max(words[0]['s'], cut['s'] - 1.0)
    ei = emph(cap)
    done_at = cap[ei]['at'] if ei >= 0 and cap[ei]['at'] > last_dead['s'] + 0.5 else min(last_dead['s'] + 2.0, words[-1]['s'])
    return {'barAt': round(bar_at, 2), 'cutStart': round(cut['s'], 2), 'cutEnd': round(last_dead['s'], 2), 'doneAt': round(done_at, 2)}


def power_phrase(cap):
    """The beat's MONEY WORDS: the emphasis word plus its immediate content neighbours
    (contiguous, <=3 words, spoken order) — e.g. "high retention edit" out of SB1. Never a
    transcript wall; power words only (the locked maximalist rule)."""
    ei = emph(cap)
    if ei < 0:
        return []
    def content(w):
        c = _clean(w['t'])
        return len(c) >= 3 and c not in STOP
    lo = ei - 1 if ei - 1 >= 0 and content(cap[ei - 1]) else ei
    hi = ei + 1 if ei + 1 < len(cap) and content(cap[ei + 1]) else ei
    out = [dict(w) for w in cap[lo:hi + 1]]
    for w in out:
        w['big'] = False
    out[ei - lo]['big'] = True
    return out


def brand_chips(words):
    """Spoken brand/tool NAME-DROPS -> chips, each anchored to its spoken word (first mention)."""
    chips = []
    for w in words:
        name = BRANDS.get(_clean(w['t']))
        if name and all(c['t'] != name for c in chips):
            chips.append({'t': name, 'at': w['s']})
    return chips


def build_beats_spoken(phrases, diagrams, script_text):
    """SPOKEN-BEAT beats (Ryan 2026-07-01, LOCKED): the writer's SCRIPT is the TIMELINE. A
    spoken beat (SB) = one PARAGRAPH of the script (blank-line separated) — the atomic unit of
    meaning the edit visualizes. ONE visual owns each whole SB, timed to its spoken words:

        SB slot: host → device → host → device → …    (SB1 is always the avatar)
        ring:    glideR → takeover → glideL → …       (Ryan's EXACT order)

    ONE BEAT PER SPOKEN BEAT — a CUT may exist ONLY at an SB boundary (Ryan 2026-07-01: "you
    started cutting sentences… the spoken script is the timeline that determines everything").
    The plan mirrors the SB map 1:1: 11 spoken beats -> 11 beats. All in-scene life comes from
    the DEVICE's own content-timed motion, never from an extra cut:
      - HOST SB   → ONE shot, the whole spoken beat (the renderer gives it one slow push-in).
      - DEVICE SB → the ring device owns the whole SB **from its first frame to its last**
        (renderer law: overlay.from == beat.start — no fragment of the previous beat's visual
        may ever show inside this one); its caption/cards build word-by-word on the real
        spoken times, so the image matches the sentence for as long as it is spoken.
      - LIST SB   → deck; the stage is up from the boundary and each card spins in on its
        exact spoken item word. Consumes the device slot WITHOUT advancing the ring.

    This is STRUCTURAL and deterministic — same script + same words → same edit. It replaces
    the phrase-level cut (which fragmented spoken beats: a sentence's own comma could yank the
    edit into a different device mid-thought) and the older content-gated policy (which left
    ~80% of the video as bare host). `diagrams` = raw per-SB diagram decisions (the diagrams
    cache / Claude), or None → the deterministic rule tier picks every diagram."""
    words = [w for p in phrases for w in p['words']]
    qt = lambda t: round(round(t * FPS) / FPS, 3)

    def snap(t):
        nxt = min((w for w in words if w['s'] >= t - 0.03), key=lambda w: w['s'], default=None)
        if nxt is None:
            return qt(t)
        prev_end = max([w['e'] for w in words if w['s'] < nxt['s']], default=0.0)
        lo = min(prev_end + PAD, nxt['s'])
        return qt(max(lo, nxt['s'] - LEAD))

    # sentence index per phrase (phrases never straddle a sentence)
    sidx, c = [], 0
    for p in phrases:
        sidx.append(c)
        if p['ends_sentence']:
            c += 1

    # sentence -> spoken-beat map, straight from the script's PARAGRAPHS (the writer's timeline)
    paras = [pp for pp in re.split(r'\n\s*\n', script_text.strip()) if pp.strip()]
    s2p = []
    for pi, para in enumerate(paras):
        n = len([x for x in re.split(r'(?<=[.?!])\s+', para.strip()) if x.strip()])
        s2p += [pi] * max(n, 1)
    if len(s2p) != c:
        sys.stderr.write('WARNING: script splits into %d sentences over %d spoken beats, but the '
                         'aligner saw %d — SB grouping may be off; check the script text\n' % (len(s2p), len(paras), c))

    # group phrases into spoken beats
    groups = []                                   # [(sb_index, [(phrase, sentence_idx), ...])]
    for j, p in enumerate(phrases):
        sb = s2p[min(sidx[j], len(s2p) - 1)] if s2p else 0
        if groups and groups[-1][0] == sb:
            groups[-1][1].append((p, sidx[j]))
        else:
            groups.append((sb, [(p, sidx[j])]))

    # BEAT LENGTH LAW (v5, Ryan 2026-07-03): a beat is 1-2 SENTENCES. Paragraphs still
    # group meaning, but a long paragraph splits at sentence boundaries into <=2-sentence
    # beats — cuts still land only at these boundaries, snapped into silence.
    chunked = []
    for sb, plist in groups:
        cur, cur_sents = [], set()
        for (p, si) in plist:
            if si not in cur_sents and len(cur_sents) == 2:
                chunked.append((sb, cur)); cur, cur_sents = [], set()
            cur.append((p, si)); cur_sents.add(si)
        if cur:
            chunked.append((sb, cur))
    groups = chunked

    # ONE SPOKEN BEAT = ONE MOTION OVERLAY (Ryan 2026-07-02, supersedes the host↔device
    # rotation and the caption-primary glides): EVERY beat carries a content-matched moving
    # diagram spanning the whole SB. The camera is still deterministic — the host is the
    # SPINE, riding alternating glides (R, L, R, …); a spec with stage:'full' becomes the
    # deliberate host absence (storyFull takeover). SB1 keeps the locked IntroStage camera
    # (tight open → zoom-out) with its diagram building in the open half instead of text.
    spec, glide_n, dstate = [], 0, {}
    n_sbs = len(groups)
    for gi, (_, plist) in enumerate(groups):
        sb_words = [w for p, _ in plist for w in p['words']]
        start = plist[0][0]['s']
        # KEEP the writer's punctuation on screen (Ryan 2026-07-06): script_phrases already
        # attached the script's commas/periods to each word ("Argentina,") — DISPLAY them, do
        # not strip. emph() and the fx helpers clean internally, so matching is unaffected.
        # Drop pure verbal fillers (um/uh/er/mm…) from the on-screen caption — whisperX keeps
        # them and script_phrases carries unmatched ad-libs through, but they only read as noise
        # in text. Timing is per-word, so removing one shifts nothing. Only non-words are cut;
        # meaningful discourse words (like, so, you know) are left alone.
        FILLERS = {'um', 'uh', 'er', 'erm', 'mm', 'hmm', 'uhh', 'umm', 'uhm', 'ah'}
        raw = diagrams[gi] if diagrams and gi < len(diagrams) else None
        # Per-beat caption cleanup: the cache may list `drop` words (cleaned form) to remove
        # from THIS beat's caption — for a misheard ad-lib the aligner kept ("too"→"2") that
        # isn't a global filler. Position-specific, so it never touches the same word elsewhere.
        DROP = {_clean(x) for x in (raw.get('drop') if raw else None) or []}
        cap = [{'t': w['t'].strip(), 'at': w['s']} for w in sb_words
               if any(c.isalnum() for c in w['t']) and _clean(w['t']) not in FILLERS
               and _clean(w['t']) not in DROP]
        ei = emph(cap)
        for k, w in enumerate(cap):
            w['big'] = (k == ei)
        # ══ THE SCENE x ANIMATION PICKER (Ryan 2026-07-03 FINAL: avatar ALWAYS on
        # screen, motion graphics only — no text takeovers, no pills) ══
        # SCENE LIBRARY (exactly 3):
        #   1 full avatar + overlay animation     2 glide right + panel animation
        #   3 glide left + panel animation
        # ANIMATION LIBRARY (10, locked by Ryan — add a kind to ANIM_RESOLVE
        # + a component and an 11th is live): timeline, graph, funnel, merge, pairs,
        # stack, roles, upgrade, closer, count (#10, added 2026-07-03).
        ANIM_RESOLVE = {
            'count':    (lambda: count_fx(sb_words, cap),   'count'),
            'funnel':   (lambda: funnel_fx(sb_words, cap),  'funnel'),
            'graph':    (lambda: channel_sprint(sb_words),  'sprint'),
            'timeline': (lambda: snip_fx(sb_words, cap),    'snip'),
            'pairs':    (lambda: pair_fx(sb_words, cap),    'pair'),
            'roles':    (lambda: role_call(sb_words),       'roles'),
            'upgrade':  (lambda: upgrade_fx(sb_words, cap), 'upg'),
            'closer':   (lambda: closer_fx(sb_words),       'closer'),
        }
        if (raw or {}).get('anim') == 'stack':
            # tool/brand stack: 2-4 named marks assembling around the core
            its = []
            for wname in raw.get('items') or []:
                hit = next((x for x in sb_words if _clean(x['t']).startswith(_clean(wname))), None)
                if hit:
                    its.append({'t': wname, 'at': round(hit['s'], 2)})
            if len(its) >= 2:
                raw = dict(raw); raw['_stack_items'] = its
        if raw and 'scene' not in raw and 'anim' not in raw and raw.get('kind'):
            print('  ! beat %d cache entry uses an old schema (kind=%r) — ignored; '
                  're-author as {scene: 1-3, anim}' % (gi + 1, raw.get('kind')), file=sys.stderr)
            raw = None
        scene = int(raw.get('scene', 0)) if raw else 0
        if scene not in (0, 1, 2, 3):
            print('  ! beat %d: scene %r is not in the 3-scene library — rules fallback'
                  % (gi + 1, scene), file=sys.stderr)
            scene = 0
        anim = (raw or {}).get('anim')
        # only build an animation that is actually INSTALLED as a pack; an uninstalled
        # (or removed) kind falls through to caption/host, never a dead plan anchor.
        if anim and anim not in INSTALLED:
            print('  ! beat %d: animation %r is not installed (no src/animations/%s/) — '
                  'caption/host instead' % (gi + 1, anim, anim), file=sys.stderr)
            anim = None
        keys, dg = {}, None
        if anim in ANIM_RESOLVE:
            build, bkey = ANIM_RESOLVE[anim]
            fx = build()
            if fx:
                keys[bkey] = fx
        elif anim == 'section':
            # section title card (an installed pack): a small authored title + optional
            # kicker label, revealed on the spoken cue word, over the full-frame host. The
            # host stays on camera (scene 1); the overlay only announces the new section.
            title = (raw.get('title') or '').strip()
            label = (raw.get('label') or '').strip()
            cueword = raw.get('word')
            at = None
            if cueword:
                hit = next((x for x in sb_words if _clean(x['t']).startswith(_clean(cueword))), None)
                if hit:
                    at = round(hit['s'], 2)
            if at is None and sb_words:
                at = round(sb_words[0]['s'], 2)     # default: land on the beat's first word
            if title and at is not None:
                sec_kv = {'title': title, 'at': round(at, 2)}
                if label:
                    sec_kv['label'] = label
                keys['section'] = sec_kv
        elif anim == 'photo':
            # a real photograph in the open glide panel: authored image path + optional caption,
            # revealed on the spoken cue word. The host glides aside (scene 2/3); avatar stays on.
            img = (raw.get('img') or '').strip()
            label = (raw.get('label') or '').strip()
            cueword = raw.get('word')
            at = None
            if cueword:
                hit = next((x for x in sb_words if _clean(x['t']).startswith(_clean(cueword))), None)
                if hit:
                    at = round(hit['s'], 2)
            if at is None and sb_words:
                at = round(sb_words[0]['s'], 2)
            if img and at is not None:
                ph = {'img': img, 'at': round(at, 2)}
                if label:
                    ph['label'] = label
                keys['photo'] = ph
        elif anim == 'document':
            # a DOCUMENT/ARTICLE screenshot shown BARE in the open glide panel (no card, border,
            # backdrop, or caption) with the host beside it, facing in — the global rule for text
            # visuals. The host glides aside (scene 2/3); avatar stays on. `fit` = whole|top.
            img = (raw.get('img') or '').strip()
            fit = (raw.get('fit') or '').strip()
            cueword = raw.get('word')
            at = None
            if cueword:
                hit = next((x for x in sb_words if _clean(x['t']).startswith(_clean(cueword))), None)
                if hit:
                    at = round(hit['s'], 2)
            if at is None and sb_words:
                at = round(sb_words[0]['s'], 2)
            if img and at is not None:
                dc = {'img': img, 'at': round(at, 2)}
                if fit in ('whole', 'top'):
                    dc['fit'] = fit
                keys['document'] = dc
        elif anim == 'stack' and raw.get('_stack_items'):
            keys['items'] = raw['_stack_items']
        elif anim == 'merge':
            its = []
            for wname in raw.get('items') or []:
                hit = next((x for x in sb_words if _clean(x['t']).startswith(_clean(wname))), None)
                if hit:
                    its.append({'t': wname, 'at': round(hit['s'], 2)})
            if len(its) >= 2:
                keys['items'] = its
                mg = deck_merge(sb_words, its)
                if mg:
                    keys['merge'] = mg
        if anim and dg is None and not keys:
            print('  ! animation %r found no word anchors in beat %d — flagged for authoring'
                  % (anim, gi + 1), file=sys.stderr)
            anim = None
        # ── STYLE PREFERENCES (bounded knobs — style-preferences.json) ──
        if anim and anim in PREFS['animations']['banned']:
            print('  ! beat %d: animation %r is banned by your style preferences — flagged for authoring'
                  % (gi + 1, anim), file=sys.stderr)
            anim, keys = None, {}
        if PREFS['scenes']['glide'] == 'right' and scene == 3:
            scene = 2
        elif PREFS['scenes']['glide'] == 'left' and scene == 2:
            scene = 3
        if scene and scene not in PREFS['scenes']['allowed']:
            fb = next((x for x in (1, 2, 3) if x in PREFS['scenes']['allowed']), 1)
            print('  ! beat %d: scene %d not in your allowed scenes — using %d'
                  % (gi + 1, scene, fb), file=sys.stderr)
            scene = fb
        if not scene:
            # rules fallback: content detectors, but ONLY for animations that are installed
            # (a base with no packs never auto-emits one) — an unmatched beat stays avatar-only
            # and is LOUDLY flagged; the operator authors its animation in the cache
            for k in (k for k in ('timeline', 'graph') if k in INSTALLED):
                build, bkey = ANIM_RESOLVE[k]
                fx = build()
                if fx:
                    scene, anim, keys = 1, k, {bkey: fx}
                    break
            if not scene and 'funnel' in INSTALLED:
                fx = funnel_fx(sb_words, cap)
                if fx:
                    scene, anim, keys = (2 if dstate.get('glide', 0) % 2 == 0 else 3), 'funnel', {'funnel': fx}
                    dstate['glide'] = dstate.get('glide', 0) + 1
            if not scene and gi == 0:
                scene = 1                                     # SB1 becomes the intro asset regardless
            if not scene:
                # UNIVERSAL SCENE RHYTHM (Ryan 2026-07-04): a beat with no authored scene
                # and no content match does NOT sit as a static full-frame host — it takes
                # the next slot in a deterministic host<->glide rotation (glide side
                # alternates each time) so the avatar keeps moving. This is a LAW, not a
                # per-video pick: the AI does not decide scene taste. The creator overrides
                # any individual beat in the diagrams cache; this is only the DEFAULT.
                # Never two hosts in a row (satisfies the variety law by construction).
                rot = dstate.get('rot', 0)
                scene = 1 if rot % 2 else (2 if (rot // 2) % 2 == 0 else 3)  # gR, H, gL, H, gR, …
                dstate['rot'] = rot + 1
        if not anim and dg is None and not keys and gi != 0:
            print('  ! beat %d has NO animation yet — author {scene, anim} in the diagrams '
                  'cache (an avatar-only beat is a TODO, not a style)' % (gi + 1), file=sys.stderr)
        if dg is None:
            dg = {'kind': anim or 'host', 'stage': 'host', '_descriptor': True}
        pr = {'diagram': dg}
        pr.update(keys)
        if gi == 0 and raw and raw.get('phrase'):
            # SB1 boxed-intro ASSET is now OPT-IN (Ryan 2026-07-05): the CORE opens with a
            # plain quick zoom-out (below), not the boxed power-phrase. The boxed intro is a
            # taught/added upgrade (an "intro pack") — it only builds when a diagrams-cache
            # `phrase` explicitly authors it. No cache phrase -> beat 1 falls through to the
            # plain open hook.
            # DUPLICATE LAW (v4.2): the IntroStage whip-pan logo reveal IS the intro
            # device — when chips land, the diagram dies.
            ch = brand_chips(sb_words)
            if ch:
                pr['chips'] = ch
                pr.pop('diagram', None)
            # the POWER PHRASE stacks in its box on EVERY intro (with or without logos).
            # The words are EDITORIAL: a cache `phrase` list (exact script words, last
            # one emphasized unless one is *starred) beats the mechanical picker.
            pw = None
            if raw and raw.get('phrase'):
                pw, star = [], any(x.startswith('*') for x in raw['phrase'])
                for wname in raw['phrase']:
                    big = wname.startswith('*')
                    hit = next((w for w in cap if _clean(w['t']).startswith(_clean(wname.lstrip('*')))), None)
                    if hit:
                        pw.append({'t': hit['t'], 'at': hit['at'], 'big': big})
                if pw and not star:
                    pw[-1]['big'] = True
                if not pw:
                    print('  ! beat 1: no cache phrase word found in the script — mechanical pick used', file=sys.stderr)
            pw = pw or power_phrase(cap)
            if pw:
                pr['phrase'] = [{'t': w['t'], 'at': round(w['at'], 2), 'big': bool(w.get('big'))} for w in pw]
            spec.append(('intro', start, pr))
        elif scene == 1:
            spec.append(('hostZoom', start, pr))
        else:
            if not keys:
                # animation-less glide: the open half carries the WORD-TIMED CAPTION
                # (words are the carrier ladder's legitimate last resort). Without cap
                # the fallback rendered an EMPTY panel (caught by flub-2, 2026-07-04).
                pr['cap'] = [{'t': w['t'], 'at': round(w['at'], 2), 'big': bool(w.get('big'))} for w in cap]
            spec.append(('glideR' if scene == 2 else 'glideL', start, pr))

    if spec and spec[0][0] == 'hostZoom' and spec[0][1] <= 0.6:
        spec[0] = ('open', 0.0, spec[0][2])   # keep any dressing params through the open transform
    elif spec and spec[0][0] == 'intro' and spec[0][1] <= 0.6:
        spec[0] = ('intro', 0.0, spec[0][2])  # the Intro asset owns SB1 from frame 0
    else:
        spec.insert(0, ('open', 0.0, {}))
    # NO early open-cut here: the old "always cut at ~2s" rule put a CUT inside SB1, which the
    # spoken-beat contract forbids (one beat per SB, cuts only at SB boundaries — Ryan
    # 2026-07-01, superseding his earlier 2s-open rule). The renderer still SETTLES the opening
    # pull-out by ~2s (zoomFrac), so the open reads the same — it just doesn't cut.
    starts = [0.0] + [snap(a) for (_, a, _) in spec[1:]]
    ends = starts[1:] + [round(words[-1]['e'] + 0.4, 2)]
    beats = []
    for (style, _, pr), a, b in zip(spec, starts, ends):
        beats.append({'start': round(a, 2), 'dur': round(b - a, 2), 'style': style, **dict(pr)})
    return beats


def to_ts(beats, total, src, video, face_x):
    L = ['// AUTO-GENERATED by scripts/build_matched_plan.py — one matched device per idea, contiguous beats. Do not hand-edit.',
         '// SOURCE (word-timings): %s' % src,
         '// STORY-DIAGRAM law (Ryan 2026-07-02): every spoken beat carries `diagram` — one',
         '// content-matched moving diagram spanning the whole beat. See src/components/vc/.',
         'export type Beat = { start: number; dur: number; style: string; cap?: { t: string; at: number; big?: boolean }[]; phrase?: { t: string; at: number; big?: boolean }[]; chips?: { t: string; at: number }[]; count?: { at: number; n: number; ignites: { at: number }[]; doneAt: number }; snip?: { barAt: number; cutStart: number; cutEnd: number; doneAt: number }; pair?: { pairStart: number; pairEnd: number }; merge?: { at: number; doneAt: number }; roles?: { t: string; at: number; role: string; roleAt: number }[]; rolesDone?: number; upg?: { coreAt: number; clickAt: number; upAt: number; items: { t: string; at: number }[] }; sprint?: { igniteAt: number; at: number; buildAt: number; endAt: number }; funnel?: { startAt: number; pointAt: number; oneAt: number; doneAt: number; facelessAt?: number; allAt?: number; plats: { t: string; at: number }[] }; closer?: { qAt: number; moneyAt: number; endAt: number }; section?: { title: string; at: number; label?: string }; photo?: { img: string; at: number; label?: string }; document?: { img: string; at: number; fit?: string }; diagramItems?: { t: string; at: number }[] };',
         'export const BEATS: Beat[] = [']
    for b in beats:
        parts = ["start: %.2f" % b['start'], "dur: %.2f" % b['dur'], "style: '%s'" % b['style']]
        # `diagram` is gate/beat-map metadata only (all kinds are descriptors now) —
        # it is never emitted to the renderer
        if b.get('cap'):
            parts.append('cap: [%s]' % ', '.join("{ t: '%s', at: %.2f%s }" % (esc(w['t']), w['at'], ', big: true' if w.get('big') else '') for w in b['cap']))
        if b.get('phrase'):
            parts.append('phrase: [%s]' % ', '.join("{ t: '%s', at: %.2f%s }" % (esc(w['t']), w['at'], ', big: true' if w.get('big') else '') for w in b['phrase']))
        if b.get('chips'):
            parts.append('chips: [%s]' % ', '.join("{ t: '%s', at: %.2f }" % (esc(c['t']), c['at']) for c in b['chips']))
        if b.get('count'):
            parts.append('count: { at: %.2f, n: %d, ignites: [%s], doneAt: %.2f }'
                         % (b['count']['at'], b['count']['n'],
                            ', '.join('{ at: %.2f }' % it['at'] for it in b['count']['ignites']),
                            b['count']['doneAt']))
        if b.get('snip'):
            parts.append('snip: { barAt: %.2f, cutStart: %.2f, cutEnd: %.2f, doneAt: %.2f }'
                         % (b['snip']['barAt'], b['snip']['cutStart'], b['snip']['cutEnd'], b['snip']['doneAt']))
        if b.get('merge'):
            parts.append('merge: { at: %.2f, doneAt: %.2f }' % (b['merge']['at'], b['merge']['doneAt']))
        if b.get('pair'):
            parts.append('pair: { pairStart: %.2f, pairEnd: %.2f }' % (b['pair']['pairStart'], b['pair']['pairEnd']))
        if b.get('roles'):
            parts.append('roles: [%s]' % ', '.join("{ t: '%s', at: %.2f, role: '%s', roleAt: %.2f }" % (esc(r['t']), r['at'], esc(r['role']), r['roleAt']) for r in b['roles']))
        if b.get('rolesDone'):
            parts.append('rolesDone: %.2f' % b['rolesDone'])
        if b.get('sprint'):
            parts.append('sprint: { igniteAt: %.2f, at: %.2f, buildAt: %.2f, endAt: %.2f }' % (b['sprint']['igniteAt'], b['sprint']['at'], b['sprint']['buildAt'], b['sprint']['endAt']))
        if b.get('closer'):
            parts.append('closer: { qAt: %.2f, moneyAt: %.2f, endAt: %.2f }' % (b['closer']['qAt'], b['closer']['moneyAt'], b['closer']['endAt']))
        if b.get('section'):
            sc = b['section']
            lab = (", label: '%s'" % esc(sc['label'])) if sc.get('label') else ''
            parts.append("section: { title: '%s', at: %.2f%s }" % (esc(sc['title']), sc['at'], lab))
        if b.get('photo'):
            ph = b['photo']
            lab = (", label: '%s'" % esc(ph['label'])) if ph.get('label') else ''
            parts.append("photo: { img: '%s', at: %.2f%s }" % (esc(ph['img']), ph['at'], lab))
        if b.get('document'):
            dc = b['document']
            ft = (", fit: '%s'" % esc(dc['fit'])) if dc.get('fit') else ''
            parts.append("document: { img: '%s', at: %.2f%s }" % (esc(dc['img']), dc['at'], ft))
        if b.get('funnel'):
            fu = b['funnel']
            fl = ", facelessAt: %.2f" % fu['facelessAt'] if fu.get('facelessAt') else ''
            al = ", allAt: %.2f" % fu['allAt'] if fu.get('allAt') else ''
            parts.append('funnel: { startAt: %.2f, pointAt: %.2f, oneAt: %.2f, doneAt: %.2f%s%s, plats: [%s] }'
                         % (fu['startAt'], fu['pointAt'], fu['oneAt'], fu['doneAt'], fl, al,
                            ', '.join("{ t: '%s', at: %.2f }" % (esc(p['t']), p['at']) for p in fu['plats'])))
        if b.get('upg'):
            parts.append('upg: { coreAt: %.2f, clickAt: %.2f, upAt: %.2f, items: [%s] }' % (b['upg']['coreAt'], b['upg']['clickAt'], b['upg']['upAt'], ', '.join("{ t: '%s', at: %.2f }" % (esc(it['t']), it['at']) for it in b['upg']['items'])))
        if b.get('items'):
            parts.append('diagramItems: [%s]' % ', '.join("{ t: '%s', at: %.2f }" % (esc(w['t']), w['at']) for w in b['items']))
        L.append('  { %s },' % ', '.join(parts))
    # The plan is the ONE per-video artifact: it carries not just the beats but the video
    # source and the face x-anchor (for the glide framing) — so AutoReel is generic and a
    # NEW video needs NO hand-edit of the renderer. All paths are relative to public/.
    L += ['];',
          'export const TOTAL_FRAMES = %d;' % round(total * FPS),
          "export const SRC = '%s';" % esc(video),
          'export const FACE_X = %d;' % round(face_x)]
    # GREEN-SCREEN mode: composite the KEYED host (alpha .mov derived from the cut) over an
    # animated flower background instead of the charcoal grid. null for every non-green channel.
    L.append('export type GreenScreen = { src: string; background: string; flowers: { img: string; x: number; y: number; size: number }[] };')
    gs = PREFS.get('greenScreen')
    if gs and gs.get('enabled') and gs.get('background'):
        keyed = video.rsplit('.', 1)[0] + '-keyed.mov'   # host/<name>-cut.mp4 -> host/<name>-cut-keyed.mov
        obj = {'src': keyed, 'background': gs['background'],
               'flowers': [f for f in (gs.get('flowers') or []) if isinstance(f, dict) and f.get('img')]}
        L.append('export const GREENSCREEN: GreenScreen | null = %s;' % json.dumps(obj))
    else:
        L.append('export const GREENSCREEN: GreenScreen | null = null;')
    return '\n'.join(L) + '\n'


def derive_stem(wx_path):
    """'.../official-test-desktop-cut-wx.json' -> 'official-test-desktop-cut' (the cut's name)."""
    base = os.path.basename(wx_path)
    return re.sub(r'(-wx)?\.json$', '', base)


def parse_opt(flag, default=None):
    if flag in sys.argv:
        return sys.argv[sys.argv.index(flag) + 1]
    return default


def main():
    # usage: build_matched_plan.py <words-wx.json> <out.ts> [--face-x N] [--src host/x.mp4]
    src, out = sys.argv[1], sys.argv[2]
    stem = derive_stem(src)
    video = parse_opt('--src', 'host/%s.mp4' % stem)          # the cut recording, relative to public/
    face_x = float(parse_opt('--face-x', 960))                # face x in the 1920-wide frame (glide framing)
    script = parse_opt('--script')                            # writer's script → phrase-level cut (source of truth for phrasing)
    if script:
        import script_phrases
        script_text = open(script).read()
        words = json.load(open(src))
        ph = script_phrases.phrases(words if isinstance(words, list) else words.get('words', []), script_text)
        # per-SB diagram specs: diagrams cache -> Claude (writes the cache; key from env or
        # .env) -> the deterministic rule tier (LOUDLY — never a silent quality downgrade)
        paras = [pp.strip() for pp in re.split(r'\n\s*\n', script_text.strip()) if pp.strip()]
        diagrams = C.diagram_decisions(paras, src)
        if diagrams is None:
            sys.stderr.write('build_matched_plan: no diagrams cache and no ANTHROPIC_API_KEY '
                             '(env or .env) — rule-tier diagrams (still full coverage). For the '
                             'top tier set a key or commit script/word-timings/<stem>-diagrams.json.\n')
        beats = build_beats_spoken(ph, diagrams, script_text)
    else:
        # ONE ENGINE (v5): no writer's script -> synthesize one from the transcript
        # (each sentence = one paragraph) and run the SAME spoken-beat pipeline.
        import script_phrases
        words = json.load(open(src))
        wl = words if isinstance(words, list) else words.get('words', [])
        S = load_sentences(src)
        script_text = '\n\n'.join(' '.join(x['t'].strip() for x in sent).strip() for sent in S)
        ph = script_phrases.phrases(wl, script_text)
        paras = [pp.strip() for pp in re.split(r'\n\s*\n', script_text.strip()) if pp.strip()]
        diagrams = C.diagram_decisions(paras, src)
        beats = build_beats_spoken(ph, diagrams, script_text)
    total = beats[-1]['start'] + beats[-1]['dur']
    open(out, 'w').write(to_ts(beats, total, src, video, face_x))
    # SIDECAR PLAN JSON — the machine-readable twin of the .ts plan. The requirement gate
    # (verify_beat_devices.py) and the beat map read THIS, not a regex over the TS.
    sidecar = re.sub(r'\.ts$', '.plan.json', out)
    json.dump({'beats': beats, 'total': total, 'wx': src, 'video': video}, open(sidecar, 'w'), indent=1)
    print('wrote %s: %d beats over %.1fs  (SRC=%s faceX=%d)  [+ %s]' % (out, len(beats), total, video, round(face_x), sidecar))
    for b in beats:
        dg = b.get('diagram')
        print('  %5.1f  dur %4.1f  %-10s %s' % (b['start'], b['dur'], b['style'],
              ('%s%s' % (dg['kind'], ' FULL' if dg.get('stage') == 'full' else '')) if dg else '—'))


if __name__ == '__main__':
    main()
