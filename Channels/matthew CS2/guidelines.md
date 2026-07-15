# matthew CS2 — editing guidelines

> How the Content Engine should edit videos for this channel. I read this before every edit.
> Refine it by dropping reference clips in ./references/ and telling me.

## Format — TWO modes (ask which, or infer from the request)
- **Highlight mode (default):** highlight reel of one match's best moments — pull only the good bits
  (kill-feed detection + approval gate). Short and tight. This is a gameplay-highlight cut, a NEW
  detection layer (the base engine is script/talking-head driven).
- **Condense mode:** keep MOST of the game as a **standalone video**, only cutting **dead air**
  (stretches with no talking AND no game action). A ~40-min game → ~20-30 min. Run
  `python3 "Channels/matthew CS2/condense_game.py" <vod> <out>` — `--plan-only` first to pick an
  aggressiveness (`--game-thr`: -72 keep-more, **-68 balanced (default)**, -64 tighter, -60 aggressive),
  then render. Keeps deaths / downtime-with-action / talking; cuts silent buy-time, AFK, dead-and-nothing.
  Audio = music-free VOD Track; full frame as recorded (no zoom, nothing keyed). Reaction-emphasis zoom
  is a highlight-mode thing — don't auto-apply it here.
  - Detection is audio-driven: **Game Audio** (a3) for action + **Mic/Voice** (a2) for talking. Note his
    mic is often gated/near-silent (quiet player), so game audio usually drives the trim — that's fine.
- **Short-form:** 9:16 Shorts cut per-segment with `render_short.sh` — never the full video. Only on request.

## Feel & pacing
- **NEVER pad.** The reel is only as long as the good material. If there's 3 minutes of clip-worthy
  stuff, the reel is ~3 minutes. Do NOT stretch it to hit a target length unless Matthew explicitly
  asks for one. Short-and-tight beats long-and-filler every time.

## Order (HARD RULE)
- **Always keep moments in in-game / VOD chronological order.** NEVER regroup or block by category
  (no "aces block", "clutch block", "fails montage"). Fails, frags, clutches, and reactions all play
  in the exact order they happened in the match.

## What's clip-worthy (detect all of these — they interleave in match order)
- **Frags:** aces (5K), multi-kills (3K+).
- **A single kill only counts when it is genuinely SPECIAL** (Matthew 2026-07-14): a wild **AWP flick**,
  a crisp **one-tap** headshot, a **wallbang**, a long-range/across-map pick, a **no-scope**, a
  **jumpshot**. The mechanic itself has to be the highlight.
  - **A plain kill is NOT clip-worthy** — an ordinary headshot in a normal fight, a spray-down, and
    ESPECIALLY a **shared/assisted kill** (`castle wars demon + <teammate>`) do NOT qualify just for
    being a kill/headshot. If a single kill isn't a flick/one-tap/wallbang/no-scope/jumpshot/long-range
    AND there's no multi-kill, clutch, or funny comms/reaction attached, leave it OUT. When unsure, cut it.

## HARD FILTERS (Matthew 2026-07-14) — apply these when deciding what makes the cut
- **Die-quickly rule:** if Matthew dies **pretty quickly (~a few seconds)** after a nice kill, do NOT
  keep the clip. A kill that's immediately punished isn't clip-worthy. (Check the frames after the
  kill for a red death screen.)
- **Assists don't count:** the kill feed credits `KILLER + ASSISTER`. Only keep a line where
  `castle wars demon` is the **KILLER** (FIRST name, left of the `+`). If his name is **SECOND**
  (after the `+`) it's just an assist — exclude it.
  - **Exception:** keep it if it's **multiple kills in a row where his assist carries a flashbang
    icon** — that means HE threw a sick flash that set up the kills. A flash that enables a multi is
    a highlight even though the frags are teammates'.
- **Clutches / round-definers:** winning a 1vX, game-winning defuse/plant, big retakes. Keep the
  lead-in tension (start when it *becomes* the moment), not just the kill frame.
- **Fails & funny:** whiffs, funny/baited deaths, teamkills — flagged, but left IN CHRONOLOGICAL ORDER.
- **Reactions / mic:** loud voice / hype / rage moments — these make clips land; cross-reference with
  the visual event. Detect reaction candidates from **Twitch-chat spam (WTF/LUL/KEKW), mic-energy
  spikes, and facecam motion**, list them at the review gate for Matthew's yes/no (same as the kill
  approval flow), and give every approved reaction the **reaction-emphasis split** (Camera & framing).
- **Clip length:** keep clips **TIGHT** (Matthew 2026-07-14) — a short lead-in, then exit soon after
  the kill. Extend only to track a **follow-up kill or a multi across the round**; otherwise get out.
  Don't linger. (Prior guidance said ~6–12s; default shorter, ~5–8s, unless a sequence justifies more.)

## Detection (VOD-only, no demo)
- Detect from the video: OCR the **kill feed** (top-right) for Matthew's name + kill streaks, read the
  **alive-dots / scoreboard** for clutch state, and use **audio-energy spikes** in the voice track as the
  hype signal. Over-detect, then show Matthew a **candidate list (timestamp + guess + thumbnail) for
  approval BEFORE cutting anything.** If a `.dem` demo is ever provided, detection becomes near-perfect.

## Camera & framing
- Full-frame gameplay (16:9). The facecam stays the size Matthew records it (small corner cam).
- **Reaction emphasis — REACTION clips only.** When a clip earns its place because of a **funny
  thing said / funny face / goofy reaction** (NOT a skill frag), **punch the WHOLE FRAME in on the
  top-left** (where the facecam sits) so the face gets bigger. It's just a **zoom of the normal clip**
  — NO split, NO compositing, NO keying (Matthew asked for this over the split; it's cleaner). Skill/
  frag clips stay full-frame (zoom 1.0). Render it with
  `python3 "Channels/matthew CS2/render_reaction_clip.py" <vod> <start> <end> <out>` — default
  `--zoom 0.5` keeps the **top-left QUARTER** and blows it up to full; smaller `--zoom` = punchier;
  `--anchor X,Y` moves the crop. Output matches the normal clips so everything concats cleanly.
  - The **green screen stays untouched by construction** (a zoom never keys — see Never do).
  - Audio VOD-track index is a script arg; re-probe if a recording's track order differs
    (`ffprobe ... stream_tags=name`).

## Captions & text
- _TBD — none by default; add on request._

## Transitions & overlays
- **Stream badges (drop-in overlays).** Three standalone transparent clips live in
  `transitions/badges/out/` — Twitch `recorded live on twitch` (AK + Scythe of Vitur
  bookends), YouTube `subscribe`, Discord `join the discord`. Self-contained in→hold→out,
  ProRes 4444 with alpha + baked audio; drag onto the timeline over the gameplay. Rebuild /
  tweak with `transitions/badges/build_badges.sh` (see `transitions/badges/README.md`).
- _Otherwise keep cuts clean between moments; refine from ./references/ clips._

## Music & sound
- **ALWAYS strip the Spotify/music track — never ship music (copyright).** Matthew's OBS
  recordings are multi-track and the tracks are NAMED (read them:
  `ffprobe -show_entries stream_tags=name`). Use the **`VOD Track`** for the reel audio — it's
  his purpose-built mix with the music muted (game + mic + voice chat + alerts). NEVER use the
  **`Master Track`**, which has the Spotify music baked in.
  - If a recording has no named `VOD Track`, identify the music track by content (it's the one
    with continuous energy even when the mic is silent — a sustained spectrogram "carpet") and
    exclude it, rebuilding from game + mic (+ voice chat) only. Verify music-free before ship.
  - Source runs quiet (~-51 LUFS) — boost the VOD Track (~+22 dB) with a limiter; avoid
    loudnorm-to-16 (over-amplifies the noise floor).

## Bounded knobs
- Set in ./style.json (scenes allowed, glide direction, banned animations).

## Never do
- Never regroup moments by category — always chronological.
- Never pad the runtime to a target length unprompted.
- **NEVER key / chroma-remove / replace the green screen** on the facecam (Matthew, 2026-07-15) —
  keep it exactly as recorded unless Matthew explicitly asks in that request. Applies everywhere,
  including the reaction-emphasis split.
- Never apply the reaction-emphasis split to a skill/frag clip — it's for funny/reaction moments only.
