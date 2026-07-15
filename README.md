# The Content Engine — Editing Template

Turn a raw talking-head recording into a finished, high-retention edit — automatically. You
write your script as **spoken beats** (one paragraph per idea), record yourself reading it,
and the engine does the rest: cuts the dead space, times captions to your exact spoken
words, moves the camera, and renders one uploadable MP4.

**One rule powers everything: the spoken script is the timeline.** Each paragraph of your
script = one spoken beat = one scene. The engine gives every beat a scene, cuts only at beat
boundaries, and lands every word-timed effect the instant you say it.

## The three gates

The core does three things, each verified before it ships:

1. **Clean audio** — dead space and "reset, reset" flubs removed; every cut lands in silence.
2. **Scenes** — a quick zoom-out open, then a host↔glide rhythm that keeps you moving.
3. **Typewriter** — each glide beat's line types in word-by-word (emphasis word glowing);
   host beats are you on camera. That is the finished base look.

Richer moving diagrams (charts, timelines, growth curves) are **optional animation packs**
you can add later — see below and `MOTION-LIBRARY.md`. The core ships none, and it looks
good without them.

## What's inside

| Piece | What it is |
|---|---|
| `BEAT-MAP.md` | The Beat Map system — how paragraphs become scenes |
| `MOTION-LIBRARY.md` | The base motion (caption + host) and how animation packs extend it |
| `CLAUDE.md` | Instructions for Claude Code — so you can just *ask* for an edit |
| `scripts/` | The pipeline (cut → align → plan → review → scan → render) |
| `src/` | The Remotion renderer + the base carriers |
| `src/animations/` | Where animation packs live (drop a folder in; the core ships none) |
| `script/EXAMPLE-SCRIPT.txt` | A real script in the spoken-beat format |

## Install (once)

1. **Node deps** — `npm install` (needs Node 18+)
2. **Local AI tool** — `bash scripts/setup.sh` (needs Python 3.10–3.13 — whisperX doesn't
   support 3.14+ yet — and ffmpeg on PATH)
3. **Optional: PNG cutouts** — `bash scripts/setup-rembg.sh` (~440MB), only if you want
   background-removed cutout imagery. The core caption/host engine doesn't need it.

Steps 1–2 can run at the same time. Set expectations: setup downloads **~1.3GB and takes 5-10
min** on typical broadband (one WhisperX environment). Your FIRST edit then downloads ~1GB of
speech models once, and the first render fetches headless Chrome — after that everything is
local and fast.

No API keys, no signup. Your Claude Code / Codex subscription IS the editorial brain — see
"just ask Claude" below. `.env.example` only matters if you're generating new HeyGen avatar
takes, which is optional and unrelated to editing.

## Edit a video — the simple way: just ask Claude

1. Open this folder in Claude Code (or Codex).
2. Write your script as blank-line-separated paragraphs → save as `script/<name>.txt` (must
   match what you say on camera — ad-libs are fine).
3. Record yourself reading it. Say "reset, reset" after any flub and keep going — the engine
   removes flubs automatically.
4. Say: *"Edit my video at ~/Desktop/take3.mp4 — the script is script/launch.txt"*

Claude reads `CLAUDE.md`, runs the pipeline, captions every beat, uses any animation packs
you've installed on the beats that fit them, shows you the beat map for approval, renders,
then mute-tests its own work before handing you the file. That's the whole workflow.

## Edit a video — manual (no agent)

```
scripts/edit_video.sh <your-recording>.mp4
```
Builds the plan and **stops** at a human-readable beat map (`script/<name>-beatmap.md`).
Read it — every row shows what's said, what's shown, what moves. Looks right?
```
scripts/edit_video.sh <your-recording>.mp4 --render
```
Your finished edit lands in `out/`. With no animation packs installed, every beat is
caption or host (the base look); the engine scans `src/animations/` before rendering and
uses whatever packs are present.

## Add an animation pack (later)

Animation packs and custom intros are optional upgrades. To install one, drop its folder
into `src/animations/` (or ask Claude to add it) — the pre-render scan discovers it
automatically, no wiring. To create your own, ask Claude: *"build me an animation that does
X and save it to my library."* See `MOTION-LIBRARY.md`.

---
*Note: `src/methodology/officialTestBeatPlan.ts` ships as a generated example from a video
that isn't included — so `npx remotion studio` shows a missing-video canvas until your first
`edit_video.sh` run overwrites the plan with your own recording. That's expected; nothing is
broken.*
