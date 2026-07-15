#!/usr/bin/env python3
"""Align a writer's SCRIPT (the source of truth for phrasing) to whisperX word TIMES.

The engine used to guess sentence/phrase boundaries from whisperX's own punctuation, which is
unreliable (it drops commas the writer intended). Given the real script, we instead take the
writer's commas/periods as authoritative and map them onto the accurate word times via a
sequence alignment (tolerant of typos, "3"/"three", "mp4"/"MP4", dropped/added words).

Returns PHRASES: [{words:[{t,s,e}], s, e, ends_sentence}] — a phrase per comma/period. A long
sentence becomes several phrases so the edit can cut on the writer's phrasing, not sit on one.
"""
import difflib
import re


def _clean(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


def _script_tokens(text):
    """[(clean_word, boundary, raw_word)] — boundary is ',' (phrase end), '.' (sentence
    end) or ''; raw_word is the writer's original spelling (the display truth)."""
    toks = []
    # words (letters/digits/'-) and punctuation runs; '...'/'.'/'?'/'!' => sentence, ',' => phrase.
    # A trailing % stays ON the number (whisperX emits "78%" as one token, so the display truth
    # must keep it too, or a percentage caption loses its sign); _clean() drops it, so matching
    # is unaffected — "78%" script ↔ "78%" ASR still aligns as "78".
    for m in re.finditer(r"[A-Za-z0-9][A-Za-z0-9'\-]*%?|[,.?!]+", text):
        t = m.group(0)
        if re.match(r'[,.?!]', t):
            if not toks:
                continue
            sent = any(c in t for c in '.?!')
            toks[-1] = (toks[-1][0], '.' if sent else ',', toks[-1][2])
        else:
            toks.append((_clean(t), '', t))
    return [(w, b, r) for (w, b, r) in toks if w]


MIN_PHRASE_S = 1.0   # phrases shorter than this fold into a neighbor (no 0.4s "Number one," flashes)


def phrases(words, script_text, min_phrase_s=MIN_PHRASE_S):
    """words: [{t/word, s/start, e/end}] from whisperX; script_text: the writer's script.

    SENTENCES are the writer's (split the script on . ? !) — authoritative, so ad-libs the writer
    didn't type ("to visuals") get absorbed into the sentence they fall in, and the sentence COUNT
    always matches the script (the device map can't desync). PHRASES within a sentence come from
    the writer's commas (∪ whisperX's), so the edit cuts on the writer's phrasing."""
    import re
    def gw(x): return (x.get('word') or x.get('t') or '').strip()
    def gs(x): return round(x.get('start', x.get('s', 0)), 2)
    def ge(x): return round(x.get('end', x.get('e', 0)), 2)
    W = [{'t': gw(x), 's': gs(x), 'e': ge(x)} for x in words]

    # script -> (clean_word, boundary, sentence_idx)
    sent_texts = [s for s in re.split(r'(?<=[.?!])\s+', script_text.strip()) if s.strip()]
    stoks = []
    for si, st in enumerate(sent_texts):
        for (w, b, r) in _script_tokens(st if st.rstrip().endswith(('.', '?', '!')) else st + '.'):
            stoks.append((w, b, si, r))
    sw = [t[0] for t in stoks]
    xw = [_clean(x['t']) for x in W]

    wx_sent = [None] * len(W)   # which script sentence each wx word belongs to
    wx_bound = [''] * len(W)    # phrase boundary carried from the script (',' or '.')
    sm = difflib.SequenceMatcher(a=sw, b=xw, autojunk=False)
    for a0, b0, size in sm.get_matching_blocks():
        for k in range(size):
            wx_sent[b0 + k] = stoks[a0 + k][2]
            if stoks[a0 + k][1]:
                wx_bound[b0 + k] = stoks[a0 + k][1]
    # THE SCRIPT IS THE DISPLAY TRUTH (Ryan 2026-07-02: on-screen text must come from the
    # WRITTEN script — ASR "spells things wrong and ends up giving a different meaning").
    # Every wx word takes the writer's spelling: matched words 1:1; a misheard span
    # ("Ezra Govina" for "Herzegovina") takes the script tokens distributed across it,
    # absorbed extras blank out (t='' — display code skips empties, timing unaffected).
    # Spoken ad-libs the writer didn't type keep their ASR text (they were really said).
    for tag, a0, a1, b0, b1 in sm.get_opcodes():
        if tag == 'equal':
            for k in range(a1 - a0):
                pu = stoks[a0 + k][1]
                W[b0 + k]['t'] = stoks[a0 + k][3] + (pu if pu else '')
        elif tag == 'replace':
            m, n = a1 - a0, b1 - b0
            for k in range(n):
                si = a0 + (k * m) // n if n else a0
                # first occurrence wins; later wx words of an absorbed span blank out
                if k == 0 or (a0 + ((k - 1) * m) // n) != si:
                    pu = stoks[si][1]
                    W[b0 + k]['t'] = stoks[si][3] + (pu if pu else '')
                else:
                    W[b0 + k]['t'] = ''
            # script tokens beyond the span (m > n) fold into the last wx word's text
            if m > n and n > 0:
                extra = [stoks[a0 + j][3] for j in range(((n - 1) * m) // n + 1, m)]
                if extra:
                    last = W[b0 + n - 1]
                    pu = stoks[a1 - 1][1]
                    last['t'] = (last['t'].rstrip('.,') + ' ' + ' '.join(extra) + (pu if pu else '')).strip()
    # ad-libs (unmatched wx words, e.g. Ryan says "And number three..." but the script just
    # says "Number 3...") need a sentence assigned. A run of unmatched words that straddles a
    # sentence TRANSITION (prev sentence before the run < next sentence after it) is usually a
    # spoken LEAD-IN connector ("And", "So", "Now") introducing what follows — assign the run
    # FORWARD, to the next sentence. EXCEPT: if whisperX itself heard a FULL STOP at the end of
    # the run (its last word carries .?!), the run is a TRAILING TAG completing the previous
    # thought ("...times your sentences to visuals.") — assign it BACKWARD. (Timing gaps can't
    # separate these two cases — measured: the pause BEFORE a trailing tag can exceed the pause
    # after it — but whisperX's own punctuation on the ad-lib words can.) A run that doesn't
    # straddle a transition just inherits its neighbor.
    i = 0
    while i < len(W):
        if wx_sent[i] is not None:
            i += 1
            continue
        j = i
        while j < len(W) and wx_sent[j] is None:
            j += 1
        prev = wx_sent[i - 1] if i > 0 else None
        nxt = wx_sent[j] if j < len(W) else None
        if prev is None or nxt is None:
            fill = nxt if prev is None else prev
        elif nxt > prev and W[j - 1]['t'].rstrip().endswith(('.', '?', '!')):
            fill = prev                       # trailing tag — whisperX heard the sentence end here
        else:
            fill = nxt if nxt > prev else prev  # lead-in connector (or no real transition)
        for k in range(i, j):
            wx_sent[k] = fill
        i = j
    # union whisperX's own commas for extra phrase breaks (only within a sentence)
    for i, x in enumerate(W):
        if wx_bound[i] != '.' and x['t'].endswith((',', ';', ':')):
            wx_bound[i] = wx_bound[i] or ','

    raw, cur = [], []
    for i in range(len(W)):
        cur.append(W[i])
        end_sent = (i == len(W) - 1) or (wx_sent[i + 1] != wx_sent[i])
        if end_sent or wx_bound[i]:
            raw.append({'words': cur, 'ends_sentence': end_sent})
            cur = []

    # fold tiny fragments: a lead-in ("Number one,", "Actually,") into the NEXT phrase; a tiny
    # ad-lib TAIL of a multi-phrase sentence ("...visual. And", "...sentences to visuals.") back
    # into the PREVIOUS phrase of that same sentence. A tiny fragment that is its OWN whole
    # sentence ("Good question.") is kept — the previous phrase already ended its sentence.
    merged = []
    i = 0
    while i < len(raw):
        p = raw[i]
        dur = p['words'][-1]['e'] - p['words'][0]['s']
        tiny = dur < min_phrase_s and len(p['words']) <= 3
        if tiny and not p['ends_sentence'] and i + 1 < len(raw):
            raw[i + 1]['words'] = p['words'] + raw[i + 1]['words']; i += 1; continue
        if tiny and merged and not merged[-1]['ends_sentence']:
            merged[-1]['words'] += p['words']
            merged[-1]['ends_sentence'] = merged[-1]['ends_sentence'] or p['ends_sentence']
            i += 1; continue
        merged.append(p); i += 1

    return [{'words': p['words'], 's': p['words'][0]['s'], 'e': p['words'][-1]['e'],
             'ends_sentence': p['ends_sentence']} for p in merged]


if __name__ == '__main__':
    import json
    import sys
    words = json.load(open(sys.argv[1]))
    text = open(sys.argv[2]).read()
    ph = phrases(words if isinstance(words, list) else words.get('words', []), text)
    print('%2s %6s %6s %5s %4s  %s' % ('#', 'start', 'end', 'dur', 'sent', 'phrase'))
    for i, p in enumerate(ph):
        print('%2d %6.2f %6.2f %5.1f %4s  %s' % (i, p['s'], p['e'], p['e'] - p['s'],
              '.' if p['ends_sentence'] else '', ' '.join(w['t'] for w in p['words'])))
