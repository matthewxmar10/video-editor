#!/usr/bin/env python3
"""LLM device-picker (highest quality) with a deterministic cache and a rule-based fallback.

Resolution order for a transcript `<stem>-wx.json`:
  1. `<stem>-devices.json` cache exists  -> use it (deterministic, byte-identical every run).
  2. else ANTHROPIC_API_KEY + `anthropic` SDK -> ask Claude (claude-opus-4-8, structured output),
     write the cache, then use it.  [the editorial brain for a NEW video]
  3. else -> fall back to the rule-based classify_beats (no API dependency).

The LLM/cache emits CONCEPTUAL decisions (device + the words/values it keys on); this module
resolves those to whisperX word TIMES so the cards/quotes/stats land on the spoken cue.
"""
import json
import os
import re
import sys

MODEL = 'claude-opus-4-8'

def _load_env():
    """Load the repo-root .env into os.environ (no python-dotenv dependency).
    Values already set in the environment win — .env only fills gaps."""
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if not os.path.exists(p):
        return
    for line in open(p):
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        if v.strip():
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _clean(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


# ── STORY-DIAGRAM tier (Ryan 2026-07-02: ONE spoken beat = ONE content-matched moving ──
# diagram, for every beat). Same resolution order as the device picker: a committed
# `<stem>-diagrams.json` cache (deterministic, reviewable, byte-identical every run) ->
# Claude with a key -> None (build_matched_plan's rule tier then guarantees coverage).
DIAGRAM_KINDS = (
    "Each beat object: {\"scene\": 1-3, \"anim\": <kind or omit>, ...anchors}. "
    "SCENES (avatar ALWAYS on screen): 1 = full avatar + overlay animation; "
    "2 = avatar glides RIGHT, animation in the left panel; 3 = mirror, panel right. "
    "ANIMATIONS (10, locked): "
    "count (a spoken count of 2-4 things — numbered wells ignite one per thing, "
    "the last on the emphasis word; its home is a GLIDE panel, scene 2/3), "
    "timeline (the editing timeline snips dead space live — cut/edit beats), "
    "graph (a growth curve draws upward — speed/growth/momentum), "
    "funnel (many named things converge to ONE — needs multi/point/one words), "
    "merge (items spin into cards, then collapse into ONE output; `items` = exact item words), "
    "pairs (words pair with matching visuals on a conveyor), "
    "stack (2-4 named tools/parts orbit one core; `items` = the brand words), "
    "roles (brand marks stamped with their spoken roles: X is the builder...), "
    "upgrade (add-on modules snap onto a core — upgrading/extending beats), "
    "closer (a hanging question morphs into the money payoff — outro). "
    "Every animation must BUILD across the whole beat toward its final state. "
    "A beat with no honest fit gets {\"scene\": 1} and is flagged for authoring — "
    "NEVER force-fit an animation whose story shape contradicts the sentence. "
    "VARIETY LAW: the same anim never twice in a row; scene 1 never twice in a row."
)
# V4 REDUNDANCY BUDGET (Ryan 2026-07-02): one claim, ONE carrier. The build strips
# headline/status/tag by default — the visual (image + event / symbol / numeral) states
# the claim once and text that restates it never renders. A spec may still carry a
# headline, but it only renders if the spec sets keepHeadline (the escalation knob
# after a failed mute test — text is earned, never default).
DIAGRAM_COPY_RULES = (
    "ONE CLAIM, ONE CARRIER: pick the strongest visual carrier and DELETE everything that "
    "restates it. Carrier ladder: (1) a real image of the subject with its event happening "
    "TO it (a person's photo X-slammed, an institution's logo refusing appeal chips, a flag "
    "stamped) — name real people/orgs/countries so the imagery tier can source photos; "
    "(2) a universal symbol (red card, gavel); (3) a numeral ONLY when the number itself is "
    "the claim; (4) words, last resort. NO headline unless the frame would be unreadable "
    "muted (then add keepHeadline: true). NO `status` chips when the event already shows the "
    "polarity (X = out/lost, rise-in = subbed in, denial stamp = denied) — they are stripped "
    "at build anyway. NO rows that restate the sentence's vibe without adding a new subject "
    "or event. Item `label`s are DESIGNED short titles (\"Everyone else\"), Title Case, "
    "<=3 words, present only when the image alone cannot disambiguate. Countries get their "
    "real waving-flag photo as the image (TRUE COLOR, never duotoned — a flag's identity IS "
    "its colors, the same exception as the red card glyph). The raw transcript is never shown."
)


def diagrams_cache_path(wx_path):
    return re.sub(r'-wx\.json$', '-diagrams.json', wx_path)


def _ask_claude_diagrams(sb_texts):
    import anthropic  # only imported on the API path
    lines = '\n'.join('[SB%d] %s' % (i + 1, t.replace('\n', ' ')) for i, t in enumerate(sb_texts))
    schema = {'type': 'object', 'additionalProperties': False, 'required': ['beats'],
              'properties': {'beats': {'type': 'array', 'items': {'type': 'object'}}}}
    msg = anthropic.Anthropic().messages.create(
        model=MODEL, max_tokens=6000, output_config={'format': {'type': 'json_schema', 'schema': schema}},
        messages=[{'role': 'user', 'content':
            "You are a motion-graphics editor. Each numbered paragraph below is one SPOKEN BEAT of a "
            "YouTube video. For EVERY beat pick exactly ONE moving-diagram archetype that tells that "
            "beat's story visually (diagrams, not captions). Every `word` field must be copied EXACTLY "
            "from that beat's text (it anchors the animation to the spoken moment; prefer content words "
            "spoken mid-beat, never the first word). Enumerations must stay coherent ACROSS beats: if one "
            "beat plants `slots` n=3, the beats detailing item 1/2/3 use `focus` with the matching `hot` "
            "index. Use `stage`:\"full\" at most twice per video, for the single most spatial beat. "
            "Kinds: " + DIAGRAM_KINDS + "\n" + DIAGRAM_COPY_RULES +
            "\nReturn JSON {\"beats\":[{...}]} — one object per beat IN ORDER, each "
            "{\"index\":N,\"kind\":...,\"stage\":\"panel\"|\"full\",\"headline\":{...},+params}.\n\n" + lines}])
    beats = json.loads(msg.content[0].text)['beats']
    return [next((b for b in beats if b.get('index') == i + 1), {'kind': 'flow'}) for i in range(len(sb_texts))]


def diagram_decisions(sb_texts, wx_path=None):
    """RAW per-spoken-beat diagram specs (the cache format), or None (rules take over).
    Cache -> Claude (writes the cache so every later run is deterministic) -> None."""
    _load_env()
    cp = diagrams_cache_path(wx_path) if wx_path else None
    if cp and os.path.exists(cp):
        d = json.load(open(cp))
        return d.get('beats', d)
    if os.environ.get('ANTHROPIC_API_KEY'):
        try:
            beats = _ask_claude_diagrams(sb_texts)
            if cp:
                json.dump({'version': 1, 'source': MODEL, 'beats': beats}, open(cp, 'w'), indent=1)
            return beats
        except Exception as e:
            sys.stderr.write('LLM diagram pick failed (%s); rule-tier diagrams instead\n' % e)
    return None
