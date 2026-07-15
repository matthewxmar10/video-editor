# The Beat Map — how your script becomes scenes

**The spoken script is the timeline.** You write your video as SPOKEN BEATS — one
blank-line paragraph per idea — and the engine turns each beat into exactly one scene, timed
to the words you actually say (whisperX gives ~10-20ms word accuracy).

## The contract

```
one paragraph  =  one spoken beat  =  one scene
```

The scene's visual is, by default, a **caption or the host**:

- a **glide** beat slides you to a side panel and types your line into the open half;
- a **host** beat keeps you full-frame with one camera move.

If you've installed an **animation pack**, a beat whose content truly fits one of its
animations gets that moving diagram instead of the caption. No pack, or no honest fit → the
caption stands. That is the finished look, not a fallback.

Other rules:
- A **cut exists only at a beat boundary** — never inside a spoken beat.
- Every cut lands in the **silence between words**, slightly ahead of the next word, so the
  new scene is on screen before the sentence starts.
- Motion *inside* a scene comes from the caption typing in, an animation building, or one
  slow camera move — never a cut.

## The rhythm (which beat gets which scene)

The scene policy is structural, not content-guessed — same script in, same edit out:

```
SB1    OPEN          quick zoom-out hook, then hands into the glide
SB2    glide         ┐
SB3    host          │  scenes rotate: glide → host → glide → host …
SB4    glide         │  glide side alternates; never two hosts in a row
SB5    host          │  the base carrier is the typewriter caption
…                    ┘
```

An installed animation overrides the caption on any beat it fits (authored in the diagrams
cache, or picked by the rules tier). The boxed power-phrase intro is opt-in — author a
`phrase` in the cache to replace the plain open with it.

## The review gate

`scripts/edit_video.sh <recording>.mp4` STOPS before rendering and writes
`script/<name>-beatmap.md` — a table with one row per spoken beat:

| # | Time | Dur | Said | Shown | Motion | Transition → next |
|---|------|-----|------|-------|--------|-------------------|

Read every row. If SAID has stray/missing words, fix your script text. If SHOWN feels wrong
for that line, adjust the diagrams cache (or leave the caption). Only then pass `--render`.

## Example (a base edit, caption + host)

| SB | Said (abbreviated) | Scene |
|---|---|---|
| 1 | "This is a test about chocolate chip cookies." | OPEN — quick zoom-out onto you, hands into the glide |
| 2 | "I had to make this because Claude keeps being non-deterministic…" | Glide RIGHT — your line types in, "non-deterministic" glows |
| 3 | "So naturally, I'm pretty frustrated…" | Host — one shot, one slow push-in |
| 4 | "This is another video I have to record to test consistency…" | Glide LEFT — caption builds, "consistently" glows |
| 5 | "I guess every day is a learning process." | Host |
| 6 | "…it sure does suck when AI is supposed to make this easier…" | Glide RIGHT — caption, "supposed" glows |

*With, say, a Charts pack installed, beat 4's line about a trend could become a growth
curve, and beat 6's contrast a comparison — but only if the story genuinely fits. Nothing is
forced.*

## The gates (run automatically)

- **Clean audio** — every cut verified to land in inter-word silence, beats tile with no gaps
- **Camera** — the render moves exactly as the plan declares (open, pushes, glides)
- **Seam scan** — every rendered frame checked for flashes/dead frames
